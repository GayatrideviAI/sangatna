"""
api/deps.py
-----------
FastAPI dependency injection helpers.

Key dependency: get_active_company_id
--------------------------------------
For MSME_OWNER  → always returns their own company_id
For CONSULTANT  → returns X-Client-Company-ID header if provided and
                  verified, otherwise returns their own company_id

This single dependency makes every endpoint multi-tenant aware.
"""

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.user import UserRole

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Decode JWT Bearer token and return the User ORM object."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from app.services.auth_service import decode_token, get_user_by_id
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    user = await get_user_by_id(db, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )
    return user


# ---------------------------------------------------------------------------
# Multi-tenant company resolution
# ---------------------------------------------------------------------------

async def get_active_company_id(
    x_client_company_id: UUID | None = Header(
        default=None,
        alias="X-Client-Company-ID",
        description=(
            "Consultants pass this header to act on behalf of a client MSME. "
            "MSME owners leave this blank — their own company is always used."
        ),
    ),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """
    Resolves which company the current request is acting on.

    MSME_OWNER  → always their own company_id, header ignored
    CONSULTANT  → X-Client-Company-ID if provided and authorised
                  otherwise their own company_id
    """
    # MSME owners always work on their own company
    if current_user.role != UserRole.CONSULTANT:
        return current_user.company_id

    # Consultant with no header → their own company
    if not x_client_company_id:
        return current_user.company_id

    # Consultant with header → verify they are authorised
    from app.services.consultant_service import ConsultantService
    authorised = await ConsultantService.is_authorised(
        db,
        consultant_id=current_user.id,
        client_company_id=x_client_company_id,
    )
    if not authorised:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"You are not authorised to access company "
                f"{x_client_company_id}. "
                f"Ask an admin to assign this client to your account."
            ),
        )
    return x_client_company_id


# Backwards compatible alias — old name still works
get_current_company_id = get_active_company_id


# ---------------------------------------------------------------------------
# Role enforcement
# ---------------------------------------------------------------------------

def require_roles(allowed_roles: list):
    async def _check(current_user=Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted.",
            )
        return current_user
    return _check