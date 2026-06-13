"""
api/v1/documents.py
--------------------
Document upload and Claude extraction endpoints.

POST /documents/upload          Upload a bill or report PDF
GET  /documents/                List all documents for company
GET  /documents/{id}            Get document + extracted data
POST /documents/{id}/extract    Re-run Claude extraction on a document
"""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_company_id, get_current_user, get_db
from app.models.document import Document, DocumentStatus, DocumentType
from app.schemas.document import DocumentResponse
from app.services.extraction.electricity_extractor import ElectricityExtractor
from app.utils.storage import save_upload

from sqlalchemy import select
from app.models.company import Company
from app.models.facility import Facility
from app.api.deps import get_active_company_id


router = APIRouter(prefix="/documents", tags=["Documents"])

SUPPORTED_MIME_TYPES = {
    "application/pdf":  "application/pdf",
    "image/jpeg":       "image/jpeg",
    "image/png":        "image/png",
    "image/webp":       "image/webp",
}


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a bill or report and extract data with Claude",
)

@router.post(
    "/smart-upload",
    status_code=status.HTTP_200_OK,
    summary="Smart upload — Claude reads bill and matches to company/facility",
    description=(
        "Upload a bill without selecting a company or facility. "
        "SANGATNA reads the bill, matches it to known companies, "
        "and tells you what it found or what needs to be created."
    ),
)
async def smart_upload(
    file:          UploadFile = File(...),
    document_type: DocumentType = Form(...),
    db:            AsyncSession = Depends(get_db),
    company_id:    UUID = Depends(get_active_company_id),
    current_user=Depends(get_current_user),
) -> dict:
    from app.services.document_matching_service import DocumentMatchingService

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
    file_key = save_upload(file_bytes, file.filename or "upload.pdf")

    # Step 1 — extract with Claude
    try:
        extracted = _run_extraction(document_type, file_bytes, mime_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {e}",
        )

    # Step 2 — match to existing company/facility
    match = await DocumentMatchingService.match(
        db=db,
        company_id=company_id,
        extracted=extracted,
    )

    # Step 3 — build response based on match result
    response = {
        "file_key":       file_key,
        "file_name":      file.filename,
        "file_size_bytes": len(file_bytes),
        "mime_type":      mime_type,
        "document_type":  document_type.value,
        "extracted":      extracted,
        "match_type":     match.match_type,
        "confidence":     match.confidence,
        "extracted_name": match.extracted_name,
        "extracted_address": match.extracted_address,
        "extracted_city": match.extracted_city,
        "extracted_state": match.extracted_state,
    }

    if match.match_type == "EXACT":
        # Perfect match — auto-map, show confirmation
        response.update({
            "action":       "AUTO_MAPPED",
            "message":      f"Matched to {match.facility.name} — {match.company.name}",
            "company_id":   str(match.company.id),
            "company_name": match.company.name,
            "facility_id":  str(match.facility.id),
            "facility_name": match.facility.name,
        })

    elif match.match_type == "FUZZY" and not match.needs_new_facility:
        # Company and facility both found with good confidence
        response.update({
            "action":       "CONFIRM_MATCH",
            "message":      (
                f"We think this bill belongs to {match.company.name} — "
                f"{match.facility.name}. Is that correct?"
            ),
            "company_id":   str(match.company.id),
            "company_name": match.company.name,
            "facility_id":  str(match.facility.id),
            "facility_name": match.facility.name,
            "suggestions":  match.suggestions,
        })

    elif match.match_type == "FUZZY" and match.needs_new_facility:
        # Company found but facility is new
        response.update({
            "action":         "NEW_FACILITY_NEEDED",
            "message":        (
                f"We matched this to {match.company.name} but couldn't find "
                f"a facility at {match.extracted_city or match.extracted_address}. "
                f"Shall we add a new facility to {match.company.name}?"
            ),
            "company_id":     str(match.company.id),
            "company_name":   match.company.name,
            "facility_id":    None,
            "suggested_facility": {
                "name":    match.extracted_city
                           or f"{match.company.name} — {match.extracted_state}",
                "city":    match.extracted_city,
                "state":   match.extracted_state,
                "address": match.extracted_address,
            },
            "suggestions": match.suggestions,
        })

    else:
        # No match — new company entirely
        response.update({
            "action":       "NEW_COMPANY_NEEDED",
            "message":      (
                f"We couldn't find '{match.extracted_name}' in your system. "
                f"Was this uploaded by mistake, or shall we create a new company?"
            ),
            "company_id":   None,
            "facility_id":  None,
            "suggested_company": {
                "name":    match.extracted_name,
                "city":    match.extracted_city,
                "state":   match.extracted_state,
                "address": match.extracted_address,
            },
            "suggestions":  match.suggestions,
        })

    return response


@router.post(
    "/smart-upload/confirm",
    status_code=status.HTTP_201_CREATED,
    summary="Confirm smart upload — save document after user confirms match",
)
async def smart_upload_confirm(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    current_user=Depends(get_current_user),
) -> dict:
    """
    Called after user confirms (or corrects) the match.
    Payload must contain:
      file_key, document_type, extracted (dict),
      company_id, facility_id,
      action: CONFIRMED / CREATE_FACILITY / CREATE_COMPANY
      new_facility (if CREATE_FACILITY): {name, city, state, address}
      new_company  (if CREATE_COMPANY):  {name, city, state}
    """
    import json
    from app.models.document import Document, DocumentStatus

    action        = payload.get("action")
    file_key      = payload.get("file_key")
    doc_type_str  = payload.get("document_type")
    extracted     = payload.get("extracted", {})
    target_company_id  = payload.get("company_id")
    target_facility_id = payload.get("facility_id")

    # Create facility if needed
    if action == "CREATE_FACILITY":
        new_fac = payload.get("new_facility", {})
        facility = Facility(
            company_id=UUID(target_company_id),
            name=new_fac.get("name", "New Facility"),
            state=new_fac.get("state", ""),
            city=new_fac.get("city"),
            address=new_fac.get("address"),
        )
        db.add(facility)
        await db.flush()
        target_facility_id = str(facility.id)

    # Create company + facility if needed
    elif action == "CREATE_COMPANY":
        new_co  = payload.get("new_company", {})
        new_fac = payload.get("new_facility", {})

        new_company = Company(
            name=new_co.get("name", extracted.get("consumer_name", "New Company")),
            city=new_co.get("city"),
            state=new_co.get("state"),
        )
        db.add(new_company)
        await db.flush()
        target_company_id = str(new_company.id)

        # Link consultant to new company
        from app.models.company import ConsultantClient
        from app.models.user import UserRole
        if current_user.role == UserRole.CONSULTANT:
            link = ConsultantClient(
                consultant_id=current_user.id,
                client_company_id=new_company.id,
            )
            db.add(link)

        facility = Facility(
            company_id=new_company.id,
            name=new_fac.get("name", new_co.get("city", "Main Facility")),
            state=new_co.get("state", ""),
            city=new_co.get("city"),
            address=new_fac.get("address"),
        )
        db.add(facility)
        await db.flush()
        target_facility_id = str(facility.id)

    # Save document
    document = Document(
        company_id=UUID(target_company_id),
        facility_id=UUID(target_facility_id) if target_facility_id else None,
        document_type=DocumentType[doc_type_str],
        original_filename=payload.get("file_name", "upload.pdf"),
        s3_key=file_key,
        file_size_bytes=payload.get("file_size_bytes"),
        mime_type=payload.get("mime_type", "application/pdf"),
        status=DocumentStatus.EXTRACTED,
        extracted_data=json.dumps(extracted),
        extraction_model="claude-sonnet-4-6",
        uploaded_by=current_user.id,
    )
    db.add(document)
    await db.flush()

    # Auto-register utility connection
    if doc_type_str == "ELECTRICITY_BILL" and target_facility_id:
        try:
            from app.services.utility_connection_service import (
                UtilityConnectionService,
            )
            await UtilityConnectionService.register_from_extraction(
                db=db,
                company_id=UUID(target_company_id),
                facility_id=UUID(target_facility_id),
                document_id=document.id,
                extracted_data=extracted,
                utility_type="ELECTRICITY",
            )
        except Exception:
            pass

    # Auto-calculate emissions
    if doc_type_str == "ELECTRICITY_BILL" and target_facility_id:
        try:
            from app.models.facility import Facility as FacilityModel
            from app.services.calculation.scope2_engine import Scope2Engine
            fac_result = await db.execute(
                select(FacilityModel).where(
                    FacilityModel.id == UUID(target_facility_id)
                )
            )
            fac = fac_result.scalar_one_or_none()
            if fac:
                engine = Scope2Engine(db)
                await engine.process_electricity_document(document, fac)
        except Exception:
            pass

    elif doc_type_str == "WATER_BILL" and target_facility_id:
        try:
            await _create_water_quantity_record(
                db=db,
                company_id=UUID(target_company_id),
                facility_id=UUID(target_facility_id),
                document_id=document.id,
                extracted=extracted,
                user_id=current_user.id,
            )
        except Exception:
            pass

    elif doc_type_str == "FUEL_RECEIPT" and target_facility_id:
        try:
            await _create_fuel_energy_record(
                db=db,
                company_id=UUID(target_company_id),
                facility_id=UUID(target_facility_id),
                document_id=document.id,
                extracted=extracted,
                user_id=current_user.id,
            )
        except Exception:
            pass

    await db.commit()
    await db.refresh(document)

    return {
        "message":      "Document saved successfully.",
        "document_id":  str(document.id),
        "company_id":   target_company_id,
        "facility_id":  target_facility_id,
        "status":       "EXTRACTED",
    }

async def upload_document(
    file:            UploadFile = File(...),
    document_type:   DocumentType = Form(...),
    facility_id:     UUID | None = Form(default=None),
    db:              AsyncSession = Depends(get_db),
    company_id:      UUID = Depends(get_current_company_id),
    current_user=Depends(get_current_user),
) -> DocumentResponse:

    # Validate file type
    mime_type = file.content_type or "application/pdf"
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime_type}. Use PDF, JPEG, or PNG.",
        )

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Save to local storage
    file_key = save_upload(file_bytes, file.filename or "upload.pdf")

    # Create document record
    document = Document(
        company_id=company_id,
        facility_id=facility_id,
        document_type=document_type,
        original_filename=file.filename or "upload.pdf",
        s3_key=file_key,
        file_size_bytes=len(file_bytes),
        mime_type=mime_type,
        status=DocumentStatus.PROCESSING,
        uploaded_by=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Run Claude extraction synchronously for now
    # (will move to Celery async task in next iteration)
    try:
        extracted = _run_extraction(document_type, file_bytes, mime_type)
        document.extracted_data = json.dumps(extracted)
        document.status = DocumentStatus.EXTRACTED
        document.extraction_model = "claude-sonnet-4-6"
    except Exception as e:
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        await db.commit()
        await db.refresh(document)
        return DocumentResponse.model_validate(document)

    # Auto-register utility connection BEFORE final commit
    if document_type == DocumentType.ELECTRICITY_BILL and facility_id:
        try:
            from app.services.utility_connection_service import (
                UtilityConnectionService,
            )
            await UtilityConnectionService.register_from_extraction(
                db=db,
                company_id=company_id,
                facility_id=facility_id,
                document_id=document.id,
                extracted_data=extracted,
                utility_type="ELECTRICITY",
            )
        except Exception:
            pass  # Never block upload if connection registration fails

        # Auto-create water quantity record from extracted water bill
        if document_type == DocumentType.WATER_BILL and facility_id:
            try:
                await _create_water_quantity_record(
                    db=db,
                    company_id=company_id,
                    facility_id=facility_id,
                    document_id=document.id,
                    extracted=extracted,
                    user_id=current_user.id,
                )
            except Exception:
                pass  # Never block upload

        # Auto-create fuel energy record from extracted fuel receipt
        if document_type == DocumentType.FUEL_RECEIPT and facility_id:
            try:
                await _create_fuel_energy_record(
                    db=db,
                    company_id=company_id,
                    facility_id=facility_id,
                    document_id=document.id,
                    extracted=extracted,
                    user_id=current_user.id,
                )
            except Exception:
                pass
    # Single commit for everything
    await db.commit()
    await db.refresh(document)
    return DocumentResponse.model_validate(document)



@router.get(
    "/",
    response_model=list[DocumentResponse],
    summary="List all documents for your company",
)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> list[DocumentResponse]:
    from sqlalchemy import select
    rows = (
        await db.execute(
            select(Document)
            .where(Document.company_id == company_id)
            .order_by(Document.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [DocumentResponse.model_validate(r) for r in rows]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document and extracted data",
)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> DocumentResponse:
    from sqlalchemy import select
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )
    return DocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/extract",
    response_model=DocumentResponse,
    summary="Re-run Claude extraction on an existing document",
)
async def re_extract(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> DocumentResponse:
    from sqlalchemy import select
    from app.utils.storage import read_file

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    file_bytes = read_file(document.s3_key)
    document.status = DocumentStatus.PROCESSING
    await db.commit()

    try:
        extracted = _run_extraction(
            document.document_type, file_bytes, document.mime_type
        )
        document.extracted_data = json.dumps(extracted)
        document.status = DocumentStatus.EXTRACTED
        document.extraction_model = "claude-sonnet-4-6"
        # Update utility connection with latest bill data
        if document.document_type == DocumentType.ELECTRICITY_BILL \
                and document.facility_id:
            try:
                from app.services.utility_connection_service import (
                    UtilityConnectionService,
                )
                await UtilityConnectionService.register_from_extraction(
                    db=db,
                    company_id=company_id,
                    facility_id=document.facility_id,
                    document_id=document.id,
                    extracted_data=extracted,
                    utility_type="ELECTRICITY",
                )
            except Exception:
                pass
    except Exception as e:
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)

    await db.commit()
    await db.refresh(document)
    return DocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/calculate",
    summary="Calculate Scope 2 emissions from an extracted electricity bill",
)
async def calculate_emissions(
    document_id: UUID,
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> dict:
    from sqlalchemy import select
    from app.services.calculation.scope2_engine import Scope2Engine

    # Load document
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    if document.status != DocumentStatus.EXTRACTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document must be EXTRACTED before calculating emissions.",
        )

    # Load facility
    facility_result = await db.execute(
        select(Facility).where(
            Facility.id == facility_id,
            Facility.company_id == company_id,
        )
    )
    facility = facility_result.scalar_one_or_none()
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facility not found.",
        )

    # Run Scope 2 calculation
    engine = Scope2Engine(db)
    energy_activity, emission_record = await engine.process_electricity_document(
        document, facility
    )
    await db.commit()
    await db.refresh(emission_record)

    return {
        "message": "Scope 2 emissions calculated successfully",
        "facility": facility.name,
        "state": facility.state,
        "units_consumed_kwh": float(energy_activity.quantity),
        "grid_emission_factor": float(emission_record.emission_factor),
        "ef_source": emission_record.ef_source,
        "co2e_kg": float(emission_record.co2e_kg),
        "co2e_tonnes": round(float(emission_record.co2e_kg) / 1000, 4),
        "period_start": emission_record.period_start.strftime("%Y-%m-%d"),
        "period_end": emission_record.period_end.strftime("%Y-%m-%d"),
        "energy_activity_id": str(energy_activity.id),
        "emission_record_id": str(emission_record.id),
    }

# ---------------------------------------------------------------------------
# Internal dispatcher
# ---------------------------------------------------------------------------
def _run_extraction(
    document_type: DocumentType,
    file_bytes: bytes,
    mime_type: str,
) -> dict:
    """Route to the correct extractor based on document type."""
    if document_type == DocumentType.ELECTRICITY_BILL:
        from app.services.extraction.electricity_extractor import ElectricityExtractor
        return ElectricityExtractor().extract_bill(file_bytes, mime_type)

    if document_type == DocumentType.WATER_BILL:
        from app.services.extraction.water_bill_extractor import WaterBillExtractor
        return WaterBillExtractor().extract_bill(file_bytes, mime_type)

    if document_type == DocumentType.WATER_QUALITY_REPORT:
        from app.services.extraction.water_quality_extractor import WaterQualityExtractor
        return WaterQualityExtractor().extract_report(file_bytes, mime_type)

    if document_type == DocumentType.FUEL_RECEIPT:
        from app.services.extraction.fuel_extractor import FuelExtractor
        return FuelExtractor().extract_receipt(file_bytes, mime_type)

    # For other types — extract raw text and return as notes
    from app.services.extraction.base_extractor import BaseExtractor
    extractor = BaseExtractor()
    result = extractor.extract(
        file_bytes,
        mime_type,
        "Extract all text and data from this document and return as JSON "
        "with a 'raw_text' field and any structured data you can identify.",
    )
    result["document_type"] = document_type.value
    return result

async def _create_water_quantity_record(
    db,
    company_id,
    facility_id,
    document_id,
    extracted: dict,
    user_id,
) -> None:
    """
    Auto-creates a WaterQuantityRecord after a water bill is extracted.
    Same pattern as Scope 2 auto-calculation for electricity bills.
    """
    from datetime import datetime
    from app.models.water_quantity import WaterQuantityRecord, WaterSource, WaterCategory

    quantity_kl = extracted.get("quantity_kl")
    if not quantity_kl:
        return

    # Parse period
    def parse_date(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None

    period_start = parse_date(extracted.get("billing_period_start"))
    period_end   = parse_date(extracted.get("billing_period_end"))
    if not period_start or not period_end:
        return

    # Map extracted source to enum
    source_map = {
        "MUNICIPAL":     WaterSource.MUNICIPAL,
        "GROUNDWATER":   WaterSource.GROUNDWATER,
        "TANKER":        WaterSource.TANKER,
        "SURFACE_WATER": WaterSource.SURFACE_WATER,
    }
    water_source = source_map.get(
        extracted.get("water_source", "").upper(),
        WaterSource.MUNICIPAL,
    )

    record = WaterQuantityRecord(
        company_id=company_id,
        facility_id=facility_id,
        document_id=document_id,
        water_source=water_source,
        water_category=WaterCategory.WITHDRAWAL,
        quantity_kl=quantity_kl,
        cost_inr=extracted.get("amount_paid_inr"),
        period_start=period_start,
        period_end=period_end,
        meter_number=extracted.get("meter_number"),
        entry_method="DOCUMENT_EXTRACTION",
        notes=f"Auto-extracted from water bill",
        created_by=user_id,
    )
    db.add(record)

    async def _create_fuel_energy_record(
    db,
    company_id,
    facility_id,
    document_id,
    extracted: dict,
    user_id,
) -> None:
        """
        Auto-creates an EnergyActivity + EmissionRecord after
        a fuel receipt is extracted. Same pattern as electricity.
        """
    from datetime import datetime
    from app.models.energy import (
        EnergyActivity, EnergySource, EnergyUnit, DataEntryMethod
    )
    from app.services.energy_service import EnergyService

    quantity = extracted.get("quantity")
    if not quantity:
        return

    def parse_date(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None

    purchase_date = parse_date(extracted.get("purchase_date"))
    if not purchase_date:
        return

    # Map fuel type to EnergySource enum
    fuel_map = {
        "DIESEL":      EnergySource.DIESEL,
        "LPG":         EnergySource.LPG,
        "CNG":         EnergySource.CNG,
        "FURNACE_OIL": EnergySource.FURNACE_OIL,
        "PETROL":      EnergySource.DIESEL,  # treated as diesel for EF
    }
    fuel_type = extracted.get("fuel_type", "DIESEL").upper()
    energy_source = fuel_map.get(fuel_type, EnergySource.DIESEL)

    # Map unit
    unit_str = extracted.get("quantity_unit", "litres").lower()
    unit = EnergyUnit.KG if unit_str == "kg" else EnergyUnit.LITRES

    activity = EnergyActivity(
        company_id=company_id,
        facility_id=facility_id,
        document_id=document_id,
        energy_source=energy_source,
        quantity=quantity,
        unit=unit,
        cost_inr=extracted.get("amount_paid_inr"),
        period_start=purchase_date,
        period_end=purchase_date,
        entry_method=DataEntryMethod.DOCUMENT_EXTRACTION,
        notes=f"Auto-extracted from fuel receipt",
        created_by=user_id,
    )
    db.add(activity)
    await db.flush()

    # Auto-calculate Scope 1 emissions
    from sqlalchemy import select
    from app.models.facility import Facility
    facility_result = await db.execute(
        select(Facility).where(Facility.id == facility_id)
    )
    facility = facility_result.scalar_one_or_none()
    if facility:
        await EnergyService._calculate_emissions(db, activity, company_id)