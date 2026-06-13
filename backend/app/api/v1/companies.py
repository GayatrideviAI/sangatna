"""
api/v1/companies.py
-------------------
FastAPI router for company (MSME) management.

Endpoints
---------
POST   /companies/          Register a new MSME company
GET    /companies/          List all companies (paginated)
GET    /companies/{id}      Get a single company
PATCH  /companies/{id}      Update company details
DELETE /companies/{id}      Delete a company
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdate,
)
from app.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.post(
    "/",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new MSME company",
)
async def create_company(
    payload: CompanyCreate,
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    return await CompanyService.create_company(db, payload)


@router.get(
    "/",
    response_model=CompanyListResponse,
    summary="List all companies",
)
async def list_companies(
    page:      int          = Query(default=1, ge=1),
    page_size: int          = Query(default=20, ge=1, le=100),
    state:     str | None   = Query(default=None),
    industry:  str | None   = Query(default=None),
    db: AsyncSession        = Depends(get_db),
) -> CompanyListResponse:
    return await CompanyService.list_companies(
        db, page=page, page_size=page_size,
        state=state, industry=industry,
    )


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get a single company",
)
async def get_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    company = await CompanyService.get_company(db, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found.",
        )
    return CompanyResponse.model_validate(company)


@router.patch(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Update company details",
)
async def update_company(
    company_id: UUID,
    payload:    CompanyUpdate,
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    company = await CompanyService.update_company(db, company_id, payload)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found.",
        )
    return company


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a company",
)
async def delete_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await CompanyService.delete_company(db, company_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found.",
        )