"""
api/v1/consultants.py
----------------------
Endpoints for managing consultant-client relationships.

POST   /consultants/clients              Assign an MSME to a consultant
GET    /consultants/clients              List all clients for logged-in consultant
DELETE /consultants/clients/{company_id} Remove a client assignment
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import UserRole
from app.schemas.company import CompanyResponse
from app.services.consultant_service import ConsultantService

router = APIRouter(prefix="/consultants", tags=["Consultants"])


@router.post(
    "/clients",
    status_code=status.HTTP_201_CREATED,
    summary="Assign an MSME company to your consultant account",
    description=(
        "After registering an MSME via POST /companies, "
        "call this endpoint to link them to your consultant account. "
        "You can then pass X-Client-Company-ID in any request header "
        "to act on their behalf."
    ),
)
async def assign_client(
    client_company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles([UserRole.CONSULTANT])),
) -> dict:
    try:
        link = await ConsultantService.assign_client(
            db,
            consultant_id=current_user.id,
            client_company_id=client_company_id,
        )
        return {
            "message":          "Client assigned successfully.",
            "consultant_id":    str(link.consultant_id),
            "client_company_id": str(link.client_company_id),
            "assigned_at":      link.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/clients",
    response_model=list[CompanyResponse],
    summary="List all MSME clients assigned to you",
)
async def list_clients(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles([UserRole.CONSULTANT])),
) -> list[CompanyResponse]:
    companies = await ConsultantService.list_clients(
        db, consultant_id=current_user.id
    )
    return [CompanyResponse.model_validate(c) for c in companies]


@router.delete(
    "/clients/{client_company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an MSME client from your account",
)
async def remove_client(
    client_company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles([UserRole.CONSULTANT])),
) -> None:
    removed = await ConsultantService.remove_client(
        db,
        consultant_id=current_user.id,
        client_company_id=client_company_id,
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client assignment not found.",
        )