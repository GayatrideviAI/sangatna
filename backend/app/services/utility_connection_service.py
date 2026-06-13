"""
services/utility_connection_service.py
----------------------------------------
Manages utility connections per facility.

Key behaviour:
  - Called automatically after every successful bill extraction
  - Creates a new connection if none exists for this consumer number
  - Updates last_bill_date if connection already exists
  - Detects missing billing periods when BRSR is requested
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utility_connection import UtilityConnection


class UtilityConnectionService:

    # ------------------------------------------------------------------
    # Auto-register from extracted bill data
    # ------------------------------------------------------------------

    @staticmethod
    async def register_from_extraction(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID,
        document_id: UUID,
        extracted_data: dict,
        utility_type: str = "ELECTRICITY",
    ) -> UtilityConnection:
        """
        Called automatically after Claude extracts a bill.
        Creates or updates the utility connection record.
        """
        consumer_number  = extracted_data.get("account_number")
        meter_number     = extracted_data.get("meter_number")
        utility_provider = extracted_data.get("utility_name")
        tariff_category  = extracted_data.get("tariff_category")
        supply_voltage   = extracted_data.get("supply_voltage")
        sanctioned_load  = str(extracted_data.get("sanctioned_load_kw", ""))

        # Parse bill period end as last_bill_date
        last_bill_date = None
        period_end_str = extracted_data.get("billing_period_end")
        if period_end_str:
            try:
                last_bill_date = datetime.strptime(period_end_str, "%Y-%m-%d")
            except ValueError:
                pass

        # Check if connection already exists for this facility + type
        existing_result = await db.execute(
            select(UtilityConnection).where(
                UtilityConnection.facility_id == facility_id,
                UtilityConnection.utility_type == utility_type,
                UtilityConnection.consumer_number == consumer_number,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update last bill info
            if last_bill_date:
                existing.last_bill_date  = last_bill_date
            existing.last_document_id    = document_id
            existing.meter_number        = meter_number or existing.meter_number
            existing.utility_provider    = utility_provider or existing.utility_provider
            await db.commit()
            await db.refresh(existing)
            return existing

        # Create new connection
        connection = UtilityConnection(
            company_id=company_id,
            facility_id=facility_id,
            utility_type=utility_type,
            utility_provider=utility_provider,
            consumer_number=consumer_number,
            meter_number=meter_number,
            tariff_category=tariff_category,
            supply_voltage=supply_voltage,
            sanctioned_load=sanctioned_load,
            first_bill_date=last_bill_date,
            last_bill_date=last_bill_date,
            last_document_id=document_id,
        )
        db.add(connection)
        await db.commit()
        await db.refresh(connection)
        return connection

    # ------------------------------------------------------------------
    # List connections for a company
    # ------------------------------------------------------------------

    @staticmethod
    async def list_connections(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID | None = None,
    ) -> list[UtilityConnection]:
        query = select(UtilityConnection).where(
            UtilityConnection.company_id == company_id
        )
        if facility_id:
            query = query.where(
                UtilityConnection.facility_id == facility_id
            )
        result = await db.execute(
            query.order_by(UtilityConnection.utility_provider)
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Detect missing billing periods
    # ------------------------------------------------------------------

    @staticmethod
    async def get_coverage_gaps(
        db: AsyncSession,
        company_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> list[dict]:
        """
        For each utility connection, checks whether all billing periods
        within the requested date range have data.
        Returns a list of gaps — missing months per connection.
        Used by the BRSR generator to flag incomplete data.
        """
        from app.models.energy import EnergyActivity, EnergySource
        from sqlalchemy import and_

        connections = await UtilityConnectionService.list_connections(
            db, company_id
        )
        gaps = []

        for conn in connections:
            # Find all energy activities for this facility in the period
            activities_result = await db.execute(
                select(EnergyActivity).where(
                    and_(
                        EnergyActivity.company_id  == company_id,
                        EnergyActivity.facility_id == conn.facility_id,
                        EnergyActivity.energy_source == EnergySource.ELECTRICITY,
                        EnergyActivity.period_start >= period_start,
                        EnergyActivity.period_end   <= period_end,
                    )
                ).order_by(EnergyActivity.period_start)
            )
            activities = activities_result.scalars().all()

            # Calculate expected number of bills
            months_in_period = (
                (period_end.year - period_start.year) * 12
                + period_end.month - period_start.month
                 + 1  # inclusive of both start and end month
            )
            cycle = int(conn.billing_cycle_months or 2)
            expected_bills = max(1, months_in_period // cycle)
            actual_bills   = len(activities)

            if actual_bills < expected_bills:
                gaps.append({
                    "facility_id":      str(conn.facility_id),
                    "utility_provider": conn.utility_provider,
                    "consumer_number":  conn.consumer_number,
                    "utility_type":     conn.utility_type,
                    "expected_bills":   expected_bills,
                    "actual_bills":     actual_bills,
                    "missing_bills":    expected_bills - actual_bills,
                    "last_bill_date":   conn.last_bill_date.isoformat()
                                        if conn.last_bill_date else None,
                    "message": (
                        f"{expected_bills - actual_bills} bill(s) missing "
                        f"for {conn.utility_provider} "
                        f"(consumer: {conn.consumer_number})"
                    ),
                })

        return gaps