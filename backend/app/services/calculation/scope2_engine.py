"""
services/calculation/scope2_engine.py
---------------------------------------
Calculates Scope 2 CO2e emissions from electricity consumption.

Formula:
    CO2e (kg) = Units Consumed (kWh) × Grid Emission Factor (kg CO2e/kWh)

Uses CEA state-wise grid emission factors.
If a facility has a custom_grid_ef set, that takes priority.
"""

import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.emission import EmissionRecord
from app.models.energy import (
    DataEntryMethod,
    EnergyActivity,
    EnergySource,
    EnergyUnit,
)
from app.models.facility import Facility
from app.services.calculation.emission_factors import get_grid_emission_factor


class Scope2Engine:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_electricity_document(
        self,
        document: Document,
        facility: Facility,
    ) -> tuple[EnergyActivity, EmissionRecord]:
        """
        Takes an EXTRACTED electricity bill document and:
        1. Creates an EnergyActivity record
        2. Calculates CO2e
        3. Creates an EmissionRecord
        Returns both records (not yet committed — caller commits).
        """

        # Parse extracted data from Claude
        if not document.extracted_data:
            raise ValueError("Document has no extracted data.")

        data = json.loads(document.extracted_data)

        units_kwh = data.get("units_consumed_kwh")
        if not units_kwh:
            raise ValueError("No units_consumed_kwh found in extracted data.")

        # Parse billing period
        period_start = _parse_date(data.get("billing_period_start"))
        period_end   = _parse_date(data.get("billing_period_end"))

        if not period_start or not period_end:
            raise ValueError("Could not parse billing period from extracted data.")

        # Get emission factor — facility custom EF takes priority
        if facility.custom_grid_ef:
            ef = float(facility.custom_grid_ef)
            ef_source = f"Custom EF set for facility {facility.name}"
        else:
            ef, ef_source = get_grid_emission_factor(facility.state)

        # Calculate CO2e
        co2e_kg = round(float(units_kwh) * ef, 4)

        # Create EnergyActivity record
        energy_activity = EnergyActivity(
            company_id=document.company_id,
            facility_id=facility.id,
            document_id=document.id,
            energy_source=EnergySource.ELECTRICITY,
            quantity=units_kwh,
            unit=EnergyUnit.KWH,
            cost_inr=data.get("amount_paid_inr"),
            period_start=period_start,
            period_end=period_end,
            meter_number=data.get("meter_number"),
            entry_method=DataEntryMethod.DOCUMENT_EXTRACTION,
            notes=f"Extracted from {document.original_filename}",
            created_by=document.uploaded_by,
        )
        self.db.add(energy_activity)
        await self.db.flush()  # get energy_activity.id

        # Create EmissionRecord
        emission_record = EmissionRecord(
            company_id=document.company_id,
            facility_id=facility.id,
            source_type="ELECTRICITY",
            scope="Scope 2",
            activity_id=energy_activity.id,
            activity_table="energy_activities",
            activity_data=units_kwh,
            activity_unit="kWh",
            emission_factor=ef,
            ef_source=ef_source,
            ef_unit="kg CO2e/kWh",
            co2e_kg=co2e_kg,
            period_start=period_start,
            period_end=period_end,
            notes=f"Tamil Nadu grid EF {ef} kg CO2e/kWh × {units_kwh} kWh",
        )
        self.db.add(emission_record)

        return energy_activity, emission_record


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None