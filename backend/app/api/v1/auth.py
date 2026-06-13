"""
api/v1/auth.py
--------------
Authentication endpoints.

POST /auth/register   — create company + first user in one step
POST /auth/login      — returns JWT token
GET  /auth/me         — returns current user info
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth_service import (
    create_access_token,
    get_user_by_email,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new company and first user",
)
async def register(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Check email not already taken
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    # Create company first
    company = Company(
        name=payload.company_name,
        industry=payload.company_industry,
        state=payload.company_state,
        city=payload.company_city,
        msme_category=payload.msme_category,
    )
    db.add(company)
    await db.flush()   # get company.id before creating user

    # Create user
    user = User(
        company_id=company.id,
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        language=payload.language,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        company_id=user.company_id,
        role=user.role,
        full_name=user.full_name,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT token",
)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await get_user_by_email(db, payload.email)

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact your administrator.",
        )

    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        company_id=user.company_id,
        role=user.role,
        full_name=user.full_name,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current logged-in user",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)