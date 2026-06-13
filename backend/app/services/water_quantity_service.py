"""
services/water_quantity_service.py
------------------------------------
Business logic for water quantity records.
Tracks withdrawal, consumption, recycled, and discharged
volumes per facility for BRSR water intensity reporting.
"""

import math
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facility import Facility
from app.models.water_quantity import WaterCategory, WaterQuantityRecord
from app.schemas.water_quantity import (
    WaterQuantityCreate,
    WaterQuantityListResponse,
    WaterQuantityResponse,
    WaterQuantityUpdate,
    WaterSummary,
)


class WaterQuantityService:

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @staticmethod
    async def create_record(
        db: AsyncSession,
        company_id: UUID,
        user_id: UUID,
        payload: WaterQuantityCreate,
    ) -> WaterQuantityResponse:
        record = WaterQuantityRecord(
            company_id=company_id,
            facility_id=payload.facility_id,
            water_source=payload.water_source,
            water_category=payload.water_category,
            quantity_kl=payload.quantity_kl,
            cost_inr=payload.cost_inr,
            period_start=payload.period_start,
            period_end=payload.period_end,
            meter_number=payload.meter_number,
            entry_method="MANUAL",
            notes=payload.notes,
            created_by=user_id,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return WaterQuantityResponse.model_validate(record)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    async def get_record(
        db: AsyncSession,
        record_id: UUID,
        company_id: UUID,
    ) -> WaterQuantityRecord | None:
        result = await db.execute(
            select(WaterQuantityRecord).where(
                WaterQuantityRecord.id == record_id,
                WaterQuantityRecord.company_id == company_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_records(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID | None = None,
        water_category: WaterCategory | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> WaterQuantityListResponse:

        query = select(WaterQuantityRecord).where(
            WaterQuantityRecord.company_id == company_id
        )
        count_query = select(func.count()).select_from(
            WaterQuantityRecord
        ).where(WaterQuantityRecord.company_id == company_id)

        if facility_id:
            query = query.where(
                WaterQuantityRecord.facility_id == facility_id
            )
            count_query = count_query.where(
                WaterQuantityRecord.facility_id == facility_id
            )
        if water_category:
            query = query.where(
                WaterQuantityRecord.water_category == water_category
            )
            count_query = count_query.where(
                WaterQuantityRecord.water_category == water_category
            )
        if period_start:
            query = query.where(
                WaterQuantityRecord.period_start >= period_start
            )
            count_query = count_query.where(
                WaterQuantityRecord.period_start >= period_start
            )
        if period_end:
            query = query.where(
                WaterQuantityRecord.period_end <= period_end
            )
            count_query = count_query.where(
                WaterQuantityRecord.period_end <= period_end
            )

        total = (await db.execute(count_query)).scalar_one()
        rows = (
            await db.execute(
                query.order_by(WaterQuantityRecord.period_start.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return WaterQuantityListResponse(
            items=[WaterQuantityResponse.model_validate(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 1,
        )

    # ------------------------------------------------------------------
    # Summary — feeds BRSR and dashboard
    # ------------------------------------------------------------------

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> WaterSummary:
        """
        Aggregated water data for a facility and period.
        Calculates water intensity if production volume is available.
        """
        facility_result = await db.execute(
            select(Facility).where(
                Facility.id == facility_id,
                Facility.company_id == company_id,
            )
        )
        facility = facility_result.scalar_one_or_none()
        if not facility:
            raise ValueError(f"Facility {facility_id} not found.")

        rows = (
            await db.execute(
                select(WaterQuantityRecord).where(
                    WaterQuantityRecord.company_id == company_id,
                    WaterQuantityRecord.facility_id == facility_id,
                    WaterQuantityRecord.period_start >= period_start,
                    WaterQuantityRecord.period_end <= period_end,
                )
            )
        ).scalars().all()

        total_withdrawal = sum(
            float(r.quantity_kl)
            for r in rows
            if r.water_category == WaterCategory.WITHDRAWAL
        )
        total_consumption = sum(
            float(r.quantity_kl)
            for r in rows
            if r.water_category == WaterCategory.CONSUMPTION
        )
        total_recycled = sum(
            float(r.quantity_kl)
            for r in rows
            if r.water_category == WaterCategory.RECYCLED
        )
        total_discharged = sum(
            float(r.quantity_kl)
            for r in rows
            if r.water_category == WaterCategory.DISCHARGED
        )
        total_cost = sum(
            float(r.cost_inr) for r in rows if r.cost_inr
        )

        return WaterSummary(
            facility_id=facility_id,
            facility_name=facility.name,
            state=facility.state,
            period_start=period_start,
            period_end=period_end,
            total_withdrawal_kl=round(total_withdrawal, 2),
            total_consumption_kl=round(total_consumption, 2),
            total_recycled_kl=round(total_recycled, 2),
            total_discharged_kl=round(total_discharged, 2),
            total_cost_inr=round(total_cost, 2),
            water_intensity=None,  # populated when production data is available
            record_count=len(rows),
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    @staticmethod
    async def update_record(
        db: AsyncSession,
        record_id: UUID,
        company_id: UUID,
        payload: WaterQuantityUpdate,
    ) -> WaterQuantityResponse | None:
        record = await WaterQuantityService.get_record(
            db, record_id, company_id
        )
        if not record:
            return None
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        await db.commit()
        await db.refresh(record)
        return WaterQuantityResponse.model_validate(record)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_record(
        db: AsyncSession,
        record_id: UUID,
        company_id: UUID,
    ) -> bool:
        record = await WaterQuantityService.get_record(
            db, record_id, company_id
        )
        if not record:
            return False
        await db.delete(record)
        await db.commit()
        return True