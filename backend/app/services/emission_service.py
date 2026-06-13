"""
services/emission_service.py
-----------------------------
Aggregates emission records for reporting.
Feeds the BRSR generator and dashboard KPIs.
"""

import math
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emission import EmissionRecord
from app.models.facility import Facility
from app.schemas.emission import (
    EmissionRecordListResponse,
    EmissionRecordResponse,
    EmissionSummary,
    FacilityEmissionSummary,
)


class EmissionService:

    # ------------------------------------------------------------------
    # List raw records
    # ------------------------------------------------------------------

    @staticmethod
    async def list_records(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID | None = None,
        scope: str | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> EmissionRecordListResponse:
        from sqlalchemy import func

        query = select(EmissionRecord).where(
            EmissionRecord.company_id == company_id
        )
        count_query = select(func.count()).select_from(
            EmissionRecord
        ).where(EmissionRecord.company_id == company_id)

        if facility_id:
            query = query.where(EmissionRecord.facility_id == facility_id)
            count_query = count_query.where(
                EmissionRecord.facility_id == facility_id
            )
        if scope:
            query = query.where(EmissionRecord.scope == scope)
            count_query = count_query.where(EmissionRecord.scope == scope)
        if period_start:
            query = query.where(EmissionRecord.period_start >= period_start)
            count_query = count_query.where(
                EmissionRecord.period_start >= period_start
            )
        if period_end:
            query = query.where(EmissionRecord.period_end <= period_end)
            count_query = count_query.where(
                EmissionRecord.period_end <= period_end
            )

        total = (await db.execute(count_query)).scalar_one()
        rows = (
            await db.execute(
                query.order_by(EmissionRecord.period_start.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return EmissionRecordListResponse(
            items=[
                EmissionRecordResponse(
                    **{
                        c.key: getattr(r, c.key)
                        for c in EmissionRecord.__table__.columns
                    },
                    co2e_tonnes=round(float(r.co2e_kg) / 1000, 6),
                )
                for r in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 1,
        )

    # ------------------------------------------------------------------
    # Summary — company level, feeds BRSR
    # ------------------------------------------------------------------

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        company_id: UUID,
        period_start: datetime,
        period_end: datetime,
        financial_year: str,
    ) -> EmissionSummary:
        """
        Rolls up all Scope 1 and Scope 2 emissions for a company
        across all facilities for the given period.
        """
        # Load all facilities for this company
        facilities_result = await db.execute(
            select(Facility).where(Facility.company_id == company_id)
        )
        facilities = facilities_result.scalars().all()
        facility_map = {f.id: f for f in facilities}

        # Load all emission records for the period
        records_result = await db.execute(
            select(EmissionRecord).where(
                EmissionRecord.company_id == company_id,
                EmissionRecord.period_start >= period_start,
                EmissionRecord.period_end <= period_end,
            )
        )
        records = records_result.scalars().all()

        # Aggregate by facility
        facility_data: dict[UUID, dict] = {}

        for record in records:
            fid = record.facility_id
            if fid not in facility_data:
                facility_data[fid] = {
                    "scope1_kg":  0.0,
                    "scope2_kg":  0.0,
                    "scope1_sources": {},
                    "scope2_sources": {},
                    "count": 0,
                }

            co2e = float(record.co2e_kg)
            source = record.source_type

            if record.scope == "Scope 1":
                facility_data[fid]["scope1_kg"] += co2e
                facility_data[fid]["scope1_sources"][source] = (
                    facility_data[fid]["scope1_sources"].get(source, 0) + co2e
                )
            elif record.scope == "Scope 2":
                facility_data[fid]["scope2_kg"] += co2e
                facility_data[fid]["scope2_sources"][source] = (
                    facility_data[fid]["scope2_sources"].get(source, 0) + co2e
                )

            facility_data[fid]["count"] += 1

        # Build facility summaries
        facility_summaries = []
        total_scope1_kg = 0.0
        total_scope2_kg = 0.0

        for fid, data in facility_data.items():
            facility = facility_map.get(fid)
            if not facility:
                continue

            s1 = round(data["scope1_kg"] / 1000, 4)
            s2 = round(data["scope2_kg"] / 1000, 4)
            total_scope1_kg += data["scope1_kg"]
            total_scope2_kg += data["scope2_kg"]

            # Convert source breakdowns to tonnes
            s1_sources = {
                k: round(v / 1000, 4)
                for k, v in data["scope1_sources"].items()
            }
            s2_sources = {
                k: round(v / 1000, 4)
                for k, v in data["scope2_sources"].items()
            }

            facility_summaries.append(
                FacilityEmissionSummary(
                    facility_id=fid,
                    facility_name=facility.name,
                    state=facility.state,
                    scope1_co2e_tonnes=s1,
                    scope2_co2e_tonnes=s2,
                    total_co2e_tonnes=round(s1 + s2, 4),
                    scope1_sources=s1_sources,
                    scope2_sources=s2_sources,
                    record_count=data["count"],
                )
            )

        # Find top emission source across all records
        all_sources: dict[str, float] = {}
        for record in records:
            src = record.source_type
            all_sources[src] = (
                all_sources.get(src, 0) + float(record.co2e_kg)
            )
        top_source = (
            max(all_sources, key=all_sources.get)
            if all_sources
            else None
        )

        total_s1 = round(total_scope1_kg / 1000, 4)
        total_s2 = round(total_scope2_kg / 1000, 4)

        return EmissionSummary(
            company_id=company_id,
            financial_year=financial_year,
            period_start=period_start,
            period_end=period_end,
            scope1_co2e_tonnes=total_s1,
            scope2_co2e_tonnes=total_s2,
            total_co2e_tonnes=round(total_s1 + total_s2, 4),
            facilities=facility_summaries,
            top_source=top_source,
            intensity_per_kwh=None,
            generated_at=datetime.now(timezone.utc),
        )