"""
schemas/report.py
-----------------
Pydantic v2 schemas for report request / response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.report import ReportFormat, ReportStatus, ReportType


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ReportRequest(BaseModel):
    """Trigger generation of a new report."""

    report_type: ReportType = Field(
        ...,
        description="BRSR | INVESTOR_ESG | CSR_FUNDING | WATER_QUALITY | CARBON_SUMMARY",
        examples=[ReportType.BRSR],
    )
    report_format: ReportFormat = Field(
        default=ReportFormat.PDF,
        description="Output format. PDF is the default.",
    )
    period_start: datetime = Field(
        ...,
        description="Start of the reporting period (ISO 8601).",
        examples=["2025-04-01T00:00:00"],
    )
    period_end: datetime = Field(
        ...,
        description="End of the reporting period (ISO 8601).",
        examples=["2026-03-31T23:59:59"],
    )
    financial_year: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}$",
        description="Indian financial year e.g. '2025-26'. Auto-derived if omitted.",
        examples=["2025-26"],
    )

    @model_validator(mode="after")
    def period_end_after_start(self) -> "ReportRequest":
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start")
        return self

    @model_validator(mode="after")
    def derive_financial_year(self) -> "ReportRequest":
        """
        Auto-fill financial_year from period_start.
        Indian FY: April 1 to March 31.
        FY 2025-26 = April 1 2025 to March 31 2026.
        """
        if not self.financial_year:
            y = self.period_start.year
            m = self.period_start.month
            if m >= 4:
                self.financial_year = f"{y}-{str(y + 1)[2:]}"
            else:
                self.financial_year = f"{y - 1}-{str(y)[2:]}"
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ReportResponse(BaseModel):
    """Full report metadata returned after creation or fetch."""

    id:             UUID
    company_id:     UUID
    report_type:    ReportType
    report_format:  ReportFormat
    status:         ReportStatus
    period_start:   datetime
    period_end:     datetime
    financial_year: Optional[str]

    # Available once status == READY
    file_url:           Optional[str]  = None
    file_size_bytes:    Optional[int]  = None
    page_count:         Optional[int]  = None

    # Job tracking
    celery_task_id:     Optional[str]  = None
    error_message:      Optional[str]  = None
    generation_seconds: Optional[int]  = None

    requested_by: Optional[UUID]
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}


class ReportListItem(BaseModel):
    """Lightweight row used in paginated list responses."""

    id:             UUID
    report_type:    ReportType
    report_format:  ReportFormat
    status:         ReportStatus
    financial_year: Optional[str]
    period_start:   datetime
    period_end:     datetime
    file_url:       Optional[str] = None
    created_at:     datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    """Paginated list of reports for a company."""

    items:     list[ReportListItem]
    total:     int
    page:      int
    page_size: int
    pages:     int