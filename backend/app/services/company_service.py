"""
services/company_service.py
----------------------------
Business logic for company management.
All database operations for Company live here.
Routers call this — never query the DB directly from routers.
"""

import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdate,
)


class CompanyService:

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @staticmethod
    async def create_company(
        db: AsyncSession,
        payload: CompanyCreate,
    ) -> CompanyResponse:
        company = Company(**payload.model_dump(exclude_none=False))
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return CompanyResponse.model_validate(company)

    # ------------------------------------------------------------------
    # Read one
    # ------------------------------------------------------------------

    @staticmethod
    async def get_company(
        db: AsyncSession,
        company_id: UUID,
    ) -> Company | None:
        result = await db.execute(
            select(Company).where(Company.id == company_id)
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    @staticmethod
    async def list_companies(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        state: str | None = None,
        industry: str | None = None,
    ) -> CompanyListResponse:
        query = select(Company)
        count_query = select(func.count()).select_from(Company)

        if state:
            query = query.where(Company.state == state)
            count_query = count_query.where(Company.state == state)
        if industry:
            query = query.where(Company.industry == industry)
            count_query = count_query.where(Company.industry == industry)

        total = (await db.execute(count_query)).scalar_one()
        rows = (
            await db.execute(
                query.order_by(Company.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return CompanyListResponse(
            items=[CompanyResponse.model_validate(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 1,
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    @staticmethod
    async def update_company(
        db: AsyncSession,
        company_id: UUID,
        payload: CompanyUpdate,
    ) -> CompanyResponse | None:
        company = await CompanyService.get_company(db, company_id)
        if not company:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)

        await db.commit()
        await db.refresh(company)
        return CompanyResponse.model_validate(company)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_company(
        db: AsyncSession,
        company_id: UUID,
    ) -> bool:
        company = await CompanyService.get_company(db, company_id)
        if not company:
            return False
        await db.delete(company)
        await db.commit()
        return True