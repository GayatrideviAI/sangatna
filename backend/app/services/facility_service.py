"""
services/facility_service.py
-----------------------------
Business logic for facility management.
All facilities are scoped to a company_id — full multi-tenancy.
"""

import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facility import Facility
from app.schemas.facility import (
    FacilityCreate,
    FacilityListResponse,
    FacilityResponse,
    FacilityUpdate,
)


class FacilityService:

    @staticmethod
    async def create_facility(
        db: AsyncSession,
        company_id: UUID,
        payload: FacilityCreate,
    ) -> FacilityResponse:
        facility = Facility(
            company_id=company_id,
            **payload.model_dump(exclude_none=False),
        )
        db.add(facility)
        await db.commit()
        await db.refresh(facility)
        return FacilityResponse.model_validate(facility)

    @staticmethod
    async def get_facility(
        db: AsyncSession,
        facility_id: UUID,
        company_id: UUID,
    ) -> Facility | None:
        result = await db.execute(
            select(Facility).where(
                Facility.id == facility_id,
                Facility.company_id == company_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_facilities(
        db: AsyncSession,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> FacilityListResponse:
        query = select(Facility).where(Facility.company_id == company_id)
        count_query = select(func.count()).select_from(Facility).where(
            Facility.company_id == company_id
        )

        total = (await db.execute(count_query)).scalar_one()
        rows = (
            await db.execute(
                query.order_by(Facility.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return FacilityListResponse(
            items=[FacilityResponse.model_validate(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 1,
        )

    @staticmethod
    async def update_facility(
        db: AsyncSession,
        facility_id: UUID,
        company_id: UUID,
        payload: FacilityUpdate,
    ) -> FacilityResponse | None:
        facility = await FacilityService.get_facility(db, facility_id, company_id)
        if not facility:
            return None
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(facility, field, value)
        await db.commit()
        await db.refresh(facility)
        return FacilityResponse.model_validate(facility)

    @staticmethod
    async def delete_facility(
        db: AsyncSession,
        facility_id: UUID,
        company_id: UUID,
    ) -> bool:
        facility = await FacilityService.get_facility(db, facility_id, company_id)
        if not facility:
            return False
        await db.delete(facility)
        await db.commit()
        return True