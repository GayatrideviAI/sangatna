"""
services/extraction/water_quality_extractor.py
------------------------------------------------
Extracts structured water quality parameters from lab report PDFs.

Works with:
- NABL accredited lab reports
- TWAD Board reports (Tamil Nadu)
- Private lab reports (Intertek, SGS, etc.)
- Municipal water test certificates
"""

from app.services.extraction.base_extractor import BaseExtractor

WATER_QUALITY_PROMPT = """
You are an expert at reading Indian water quality laboratory reports.

Extract ALL water quality parameters from this lab report and return
ONLY a valid JSON object with no preamble or markdown.

Return this exact structure:
{
  "lab_name": "name of laboratory",
  "lab_report_ref": "report/certificate number",
  "sample_id": "sample ID from report",
  "collection_date": "YYYY-MM-DD or null",
  "water_type": "DRINKING or WASTEWATER or GROUNDWATER or SURFACE_WATER or PROCESS",
  "location_desc": "sample collection location description",
  "consumer_name": "name of client/consumer on report",
  "address": "address on report",
  "readings": [
    {
      "parameter_name": "exact parameter name e.g. pH, BOD, Lead",
      "parameter_code": "short code if shown e.g. DO, TDS",
      "category": "Physical or Chemical or Biological",
      "measured_value": number or null,
      "unit": "unit of measurement e.g. mg/L, NTU, CFU/100mL",
      "method": "test method if shown e.g. IS 3025"
    }
  ],
  "notes": "any important observations from the report"
}

Rules:
- Extract EVERY parameter shown in the report
- measured_value must be a number, not a string
- Use null for any field you cannot find
- Return ONLY the JSON object
"""


class WaterQualityExtractor(BaseExtractor):

    def extract_report(self, file_bytes: bytes, mime_type: str) -> dict:
        """Extract water quality parameters from a lab report PDF."""
        result = self.extract(file_bytes, mime_type, WATER_QUALITY_PROMPT)
        result["document_type"] = "WATER_QUALITY_REPORT"
        return result