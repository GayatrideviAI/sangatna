"""
api/v1/water_quality.py
------------------------
Water quality sample upload, extraction, and compliance checking.

POST /water/quality/upload          Upload lab report PDF → Claude extracts
POST /water/quality/samples         Create sample manually
GET  /water/quality/samples         List all samples
GET  /water/quality/samples/{id}    Get sample + all readings + compliance
POST /water/quality/samples/{id}/check  Run compliance check on a sample
"""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_company_id, get_current_user, get_db
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.water_quality import (
    ComplianceStatus,
    WaterQualityReading,
    WaterQualitySample,
    WaterType,
)
from app.services.extraction.water_quality_extractor import WaterQualityExtractor
from app.services.intelligence.compliance_checker import ComplianceChecker
from app.utils.storage import save_upload

router = APIRouter(prefix="/water/quality", tags=["Water Quality"])

SUPPORTED_MIME_TYPES = {
    "application/pdf": "application/pdf",
    "image/jpeg":      "image/jpeg",
    "image/png":       "image/png",
}


# ---------------------------------------------------------------------------
# Upload lab report PDF → extract → save readings → check compliance
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a water quality lab report — Claude extracts and checks compliance",
)
async def upload_lab_report(
    file:        UploadFile = File(...),
    facility_id: UUID       = Form(...),
    db:          AsyncSession = Depends(get_db),
    company_id:  UUID       = Depends(get_current_company_id),
    current_user=Depends(get_current_user),
) -> dict:

    mime_type = file.content_type or "application/pdf"
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime_type}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Save file
    file_key = save_upload(file_bytes, file.filename or "lab_report.pdf")

    # Save document record
    document = Document(
        company_id=company_id,
        facility_id=facility_id,
        document_type=DocumentType.WATER_QUALITY_REPORT,
        original_filename=file.filename or "lab_report.pdf",
        s3_key=file_key,
        file_size_bytes=len(file_bytes),
        mime_type=mime_type,
        status=DocumentStatus.PROCESSING,
        uploaded_by=current_user.id,
    )
    db.add(document)
    await db.flush()

    # Step 1 — Claude extracts parameters
    try:
        extractor = WaterQualityExtractor()
        extracted = extractor.extract_report(file_bytes, mime_type)
        document.extracted_data = json.dumps(extracted)
        document.status = DocumentStatus.EXTRACTED
        document.extraction_model = "claude-sonnet-4-6"
    except Exception as e:
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {e}",
        )

    # Step 2 — Create WaterQualitySample
    from datetime import datetime
    collection_date = None
    if extracted.get("collection_date"):
        try:
            collection_date = datetime.strptime(
                extracted["collection_date"], "%Y-%m-%d"
            )
        except ValueError:
            collection_date = datetime.utcnow()

    water_type_str = extracted.get("water_type", "DRINKING")
    try:
        water_type = WaterType[water_type_str]
    except KeyError:
        water_type = WaterType.DRINKING

    sample = WaterQualitySample(
        company_id=company_id,
        facility_id=facility_id,
        document_id=document.id,
        sample_id=extracted.get("sample_id"),
        water_type=water_type,
        collection_date=collection_date or datetime.utcnow(),
        location_desc=extracted.get("location_desc"),
        lab_name=extracted.get("lab_name"),
        lab_report_ref=extracted.get("lab_report_ref"),
        created_by=current_user.id,
    )
    db.add(sample)
    await db.flush()

    # Step 3 — Save individual readings
    readings_data = extracted.get("readings", [])
    checker = ComplianceChecker()
    evaluated = checker.evaluate_all_readings(
        readings_data, water_type_str
    )

    safe_count = 0
    exceeded_count = 0
    reading_objects = []

    for r in evaluated:
        reading = WaterQualityReading(
            sample_id=sample.id,
            company_id=company_id,
            parameter_name=r.get("parameter_name", "Unknown"),
            parameter_code=r.get("parameter_code"),
            category=r.get("category"),
            measured_value=r.get("measured_value"),
            unit=r.get("unit"),
            bis_limit=r.get("bis_limit"),
            cpcb_limit=r.get("cpcb_limit"),
            compliance_status=r.get("overall_status"),
            compliance_notes=r.get("compliance_notes"),
        )
        db.add(reading)
        reading_objects.append(reading)

        if r.get("overall_status") == ComplianceStatus.SAFE:
            safe_count += 1
        elif r.get("overall_status") == ComplianceStatus.EXCEEDS_LIMIT:
            exceeded_count += 1

    # Step 4 — Overall sample compliance status
    sample.parameters_safe = safe_count
    sample.parameters_exceeded = exceeded_count
    sample.overall_status = (
        ComplianceStatus.EXCEEDS_LIMIT
        if exceeded_count > 0
        else ComplianceStatus.SAFE
    )

    # Step 5 — Claude generates plain-language summary
    narrative = checker.generate_summary_narrative(
        sample_info={
            "lab_name":    extracted.get("lab_name"),
            "water_type":  water_type_str,
            "location":    extracted.get("location_desc"),
            "sample_date": extracted.get("collection_date"),
        },
        evaluated_readings=evaluated,
    )

    await db.commit()
    await db.refresh(sample)

    return {
        "message":             "Lab report processed successfully",
        "sample_id":           str(sample.id),
        "document_id":         str(document.id),
        "lab_name":            sample.lab_name,
        "water_type":          water_type_str,
        "collection_date":     extracted.get("collection_date"),
        "parameters_total":    len(reading_objects),
        "parameters_safe":     safe_count,
        "parameters_exceeded": exceeded_count,
        "overall_status":      sample.overall_status.value,
        "compliance_summary":  narrative,
        "readings": [
            {
                "parameter":          r.get("parameter_name"),
                "measured_value":     r.get("measured_value"),
                "unit":               r.get("unit"),
                "status":             r.get("overall_status", "").value
                                      if hasattr(r.get("overall_status"), "value")
                                      else str(r.get("overall_status", "")),
                "notes":              r.get("compliance_notes"),
            }
            for r in evaluated
        ],
    }


# ---------------------------------------------------------------------------
# List samples
# ---------------------------------------------------------------------------

@router.get(
    "/samples",
    summary="List all water quality samples for your company",
)
async def list_samples(
    facility_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> list[dict]:
    query = select(WaterQualitySample).where(
        WaterQualitySample.company_id == company_id
    )
    if facility_id:
        query = query.where(WaterQualitySample.facility_id == facility_id)

    rows = (
        await db.execute(query.order_by(WaterQualitySample.collection_date.desc()))
    ).scalars().all()

    return [
        {
            "id":                   str(s.id),
            "facility_id":          str(s.facility_id),
            "lab_name":             s.lab_name,
            "water_type":           s.water_type.value,
            "collection_date":      s.collection_date.isoformat(),
            "overall_status":       s.overall_status.value if s.overall_status else None,
            "parameters_safe":      s.parameters_safe,
            "parameters_exceeded":  s.parameters_exceeded,
        }
        for s in rows
    ]


# ---------------------------------------------------------------------------
# Get single sample with all readings
# ---------------------------------------------------------------------------

@router.get(
    "/samples/{sample_id}",
    summary="Get a water quality sample with all parameter readings",
)
async def get_sample(
    sample_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(WaterQualitySample).where(
            WaterQualitySample.id == sample_id,
            WaterQualitySample.company_id == company_id,
        )
    )
    sample = result.scalar_one_or_none()
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found.",
        )

    readings = (
        await db.execute(
            select(WaterQualityReading).where(
                WaterQualityReading.sample_id == sample_id
            )
        )
    ).scalars().all()

    return {
        "id":                  str(sample.id),
        "lab_name":            sample.lab_name,
        "lab_report_ref":      sample.lab_report_ref,
        "water_type":          sample.water_type.value,
        "collection_date":     sample.collection_date.isoformat(),
        "location_desc":       sample.location_desc,
        "overall_status":      sample.overall_status.value
                               if sample.overall_status else None,
        "parameters_safe":     sample.parameters_safe,
        "parameters_exceeded": sample.parameters_exceeded,
        "readings": [
            {
                "parameter":        r.parameter_name,
                "category":         r.category,
                "measured_value":   float(r.measured_value)
                                    if r.measured_value else None,
                "unit":             r.unit,
                "bis_limit":        float(r.bis_limit) if r.bis_limit else None,
                "cpcb_limit":       float(r.cpcb_limit) if r.cpcb_limit else None,
                "status":           r.compliance_status.value
                                    if r.compliance_status else None,
                "notes":            r.compliance_notes,
            }
            for r in readings
        ],
    }