"""
services/document_matching_service.py
---------------------------------------
Matches extracted bill data to existing companies and facilities.

Matching strategies in order of confidence:
  1. Consumer number exact match (utility_connections table) → 100%
  2. Company name fuzzy match (difflib)                     → scored
  3. Address / city / state match                           → scored

Returns a MatchResult with:
  - match_type: EXACT / FUZZY / NO_MATCH
  - company:    matched Company or None
  - facility:   matched Facility or None
  - confidence: 0.0 – 1.0
  - suggestions: list of possible matches for user to choose from
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.facility import Facility
from app.models.utility_connection import UtilityConnection


def _similarity(a: str, b: str) -> float:
    """Returns 0.0–1.0 similarity between two strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(
        None,
        a.lower().strip(),
        b.lower().strip(),
    ).ratio()


@dataclass
class MatchResult:
    match_type:  str                  # EXACT / FUZZY / NO_MATCH
    company:     Company | None       # matched company
    facility:    Facility | None      # matched facility
    confidence:  float                # 0.0 – 1.0
    suggestions: list[dict] = field(default_factory=list)
    needs_new_company:  bool = False
    needs_new_facility: bool = False
    extracted_name:     str  = ""
    extracted_address:  str  = ""
    extracted_city:     str  = ""
    extracted_state:    str  = ""


class DocumentMatchingService:

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    @staticmethod
    async def match(
        db: AsyncSession,
        company_id: UUID,           # consultant's own company_id
        extracted: dict,
    ) -> MatchResult:
        """
        Try to match extracted bill data to a known company + facility.
        company_id is the consultant's company — we search across
        all companies they manage plus their own.
        """
        consumer_number  = extracted.get("account_number") or \
                           extracted.get("consumer_number")
        consumer_name    = extracted.get("consumer_name", "")
        address          = extracted.get("address", "")
        state            = extracted.get("state", "")
        city             = _extract_city(address, state)

        # ----------------------------------------------------------
        # Strategy 1 — exact consumer number match
        # ----------------------------------------------------------
        if consumer_number:
            conn_result = await db.execute(
                select(UtilityConnection).where(
                    UtilityConnection.consumer_number == consumer_number
                )
            )
            conn = conn_result.scalar_one_or_none()

            if conn:
                # Load company and facility
                company_result = await db.execute(
                    select(Company).where(Company.id == conn.company_id)
                )
                company = company_result.scalar_one_or_none()

                facility_result = await db.execute(
                    select(Facility).where(Facility.id == conn.facility_id)
                )
                facility = facility_result.scalar_one_or_none()

                return MatchResult(
                    match_type="EXACT",
                    company=company,
                    facility=facility,
                    confidence=1.0,
                    extracted_name=consumer_name,
                    extracted_address=address,
                    extracted_city=city,
                    extracted_state=state,
                )

        # ----------------------------------------------------------
        # Strategy 2 — fuzzy company name match
        # ----------------------------------------------------------
        all_companies_result = await db.execute(select(Company))
        all_companies = all_companies_result.scalars().all()

        best_company      = None
        best_company_score = 0.0

        for company in all_companies:
            score = _similarity(consumer_name, company.name)
            # Also try legal name
            if company.legal_name:
                score = max(score, _similarity(consumer_name, company.legal_name))
            if score > best_company_score:
                best_company_score = score
                best_company = company

        # ----------------------------------------------------------
        # Strategy 3 — if company matched, find best facility
        # ----------------------------------------------------------
        best_facility       = None
        best_facility_score = 0.0

        if best_company and best_company_score >= 0.5:
            facilities_result = await db.execute(
                select(Facility).where(
                    Facility.company_id == best_company.id
                )
            )
            facilities = facilities_result.scalars().all()

            for facility in facilities:
                score = 0.0
                # City match
                if city and facility.city:
                    score = max(score, _similarity(city, facility.city))
                # State match
                if state and facility.state:
                    score = max(score, _similarity(state, facility.state) * 0.6)
                # Address match
                if address and facility.address:
                    score = max(score, _similarity(address, facility.address))

                if score > best_facility_score:
                    best_facility_score = score
                    best_facility = facility

        # ----------------------------------------------------------
        # Build suggestions for user to choose from
        # ----------------------------------------------------------
        suggestions = []
        for company in sorted(
            all_companies,
            key=lambda c: _similarity(consumer_name, c.name),
            reverse=True,
        )[:5]:
            score = _similarity(consumer_name, company.name)
            if score > 0.3:
                suggestions.append({
                    "company_id":   str(company.id),
                    "company_name": company.name,
                    "city":         company.city,
                    "state":        company.state,
                    "score":        round(score, 2),
                })

        # ----------------------------------------------------------
        # Determine match type and what needs to be created
        # ----------------------------------------------------------
        if best_company_score >= 0.75:
            match_type = "FUZZY"
            needs_new_company  = False
            needs_new_facility = best_facility_score < 0.5
        else:
            match_type = "NO_MATCH"
            needs_new_company  = True
            needs_new_facility = True
            best_company  = None
            best_facility = None

        return MatchResult(
            match_type=match_type,
            company=best_company,
            facility=best_facility,
            confidence=round(best_company_score, 2),
            suggestions=suggestions,
            needs_new_company=needs_new_company,
            needs_new_facility=needs_new_facility,
            extracted_name=consumer_name,
            extracted_address=address,
            extracted_city=city,
            extracted_state=state,
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _extract_city(address: str, state: str) -> str:
    """
    Try to extract city from address string.
    Simple heuristic — last meaningful word before state/pincode.
    """
    if not address:
        return ""
    # Remove state name from address to isolate city
    cleaned = address.replace(state, "").strip(" ,")
    # Take the last non-numeric part
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    for part in reversed(parts):
        if part and not part.replace(" ", "").isdigit():
            return part[:100]
    return ""