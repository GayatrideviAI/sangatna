"""
services/production_service.py
--------------------------------
CRUD for production records.
"""

import math
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facility import Facility
from app.models.production import ProductionRecord
from app.schemas.production import (
    ProductionRecordCreate,
    ProductionRecordResponse,
    ProductionRecordUpdate,
    ProductionSummary,
)
from app.utils.financial_year import fy_to_dates


class ProductionService:

    @staticmethod
    async def create_record(
        db: AsyncSession,
        company_id: UUID,
        user_id: UUID,
        payload: ProductionRecordCreate,
    ) -> ProductionRecordResponse:
        record = ProductionRecord(
            company_id=company_id,
            facility_id=payload.facility_id,
            year=payload.year,
            month=payload.month,
            period_label=f"{payload.year}-{payload.month}",
            quantity=payload.quantity,
            unit=payload.unit,
            product=payload.product,
            is_estimated="true" if payload.is_estimated else "false",
            notes=payload.notes,
            created_by=user_id,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return ProductionRecordResponse.model_validate(record)

    @staticmethod
    async def list_records(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID | None = None,
        year: str | None = None,
    ) -> list[ProductionRecordResponse]:
        query = select(ProductionRecord).where(
            ProductionRecord.company_id == company_id
        )
        if facility_id:
            query = query.where(
                ProductionRecord.facility_id == facility_id
            )
        if year:
            query = query.where(ProductionRecord.year == year)

        rows = (
            await db.execute(
                query.order_by(
                    ProductionRecord.year.desc(),
                    ProductionRecord.month.desc(),
                )
            )
        ).scalars().all()
        return [ProductionRecordResponse.model_validate(r) for r in rows]

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID,
        financial_year: str,
    ) -> ProductionSummary:
        """Annual production summary for a facility."""
        facility_result = await db.execute(
            select(Facility).where(
                Facility.id == facility_id,
                Facility.company_id == company_id,
            )
        )
        facility = facility_result.scalar_one_or_none()
        if not facility:
            raise ValueError(f"Facility {facility_id} not found.")

        period_start, period_end = fy_to_dates(financial_year)
        start_year  = period_start.year
        end_year    = period_end.year

        # Get all production records spanning the FY
        rows = (
            await db.execute(
                select(ProductionRecord).where(
                    ProductionRecord.company_id  == company_id,
                    ProductionRecord.facility_id == facility_id,
                ).order_by(
                    ProductionRecord.year,
                    ProductionRecord.month,
                )
            )
        ).scalars().all()

        # Filter to FY months (Apr YYYY to Mar YYYY+1)
        fy_months = []
        for r in rows:
            y = int(r.year)
            m = int(r.month)
            if (y == start_year and m >= 4) or \
               (y == end_year   and m <= 3):
                fy_months.append(r)

        total = sum(float(r.quantity) for r in fy_months)
        unit  = fy_months[0].unit if fy_months else facility.production_unit or "units"

        # Build monthly data
        monthly = []
        for m in range(1, 13):
            # FY month order: Apr=1 ... Mar=12
            actual_month = ((m + 2) % 12) + 1   # Apr=4, May=5 ... Mar=3
            actual_year  = start_year if actual_month >= 4 else end_year
            label        = f"{actual_year}-{str(actual_month).zfill(2)}"
            record       = next(
                (r for r in fy_months if r.period_label == label), None
            )
            monthly.append({
                "period_label": label,
                "quantity":     float(record.quantity) if record else None,
                "unit":         record.unit if record else unit,
                "is_estimated": record.is_estimated if record else None,
                "has_data":     record is not None,
            })

        return ProductionSummary(
            facility_id=facility_id,
            facility_name=facility.name,
            financial_year=financial_year,
            total_quantity=round(total, 2),
            unit=unit,
            months_with_data=len(fy_months),
            months_missing=12 - len(fy_months),
            monthly_data=monthly,
        )

    @staticmethod
    async def update_record(
        db: AsyncSession,
        record_id: UUID,
        company_id: UUID,
        payload: ProductionRecordUpdate,
    ) -> ProductionRecordResponse | None:
        result = await db.execute(
            select(ProductionRecord).where(
                ProductionRecord.id == record_id,
                ProductionRecord.company_id == company_id,
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return None
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "is_estimated":
                setattr(record, field, "true" if value else "false")
            else:
                setattr(record, field, value)
        await db.commit()
        await db.refresh(record)
        return ProductionRecordResponse.model_validate(record)

    @staticmethod
    async def delete_record(
        db: AsyncSession,
        record_id: UUID,
        company_id: UUID,
    ) -> bool:
        result = await db.execute(
            select(ProductionRecord).where(
                ProductionRecord.id == record_id,
                ProductionRecord.company_id == company_id,
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return False
        await db.delete(record)
        await db.commit()
        return True