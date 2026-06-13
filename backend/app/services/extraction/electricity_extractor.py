"""
services/extraction/electricity_extractor.py
---------------------------------------------
Extracts structured data from electricity bills using Claude.

Works with:
- TANGEDCO (Tamil Nadu)
- BESCOM (Karnataka)
- MSEDCL (Maharashtra)
- Any Indian state electricity board bill
- Scanned PDFs and image bills
"""

from app.services.extraction.base_extractor import BaseExtractor

ELECTRICITY_PROMPT = """
You are an expert at reading Indian electricity bills.

Extract the following information from this electricity bill and return
ONLY a valid JSON object with no preamble or markdown.

Required fields:
{
  "utility_name": "name of electricity board e.g. TANGEDCO",
  "account_number": "consumer/account number",
  "consumer_name": "name on the bill",
  "billing_period_start": "YYYY-MM-DD or null",
  "billing_period_end": "YYYY-MM-DD or null",
  "units_consumed_kwh": number or null,
  "amount_paid_inr": number or null,
  "meter_number": "meter number or null",
  "tariff_category": "Industrial/Commercial/Domestic or null",
  "sanctioned_load_kw": number or null,
  "supply_voltage": "LT/HT or null",
  "due_date": "YYYY-MM-DD or null",
  "address": "supply address or null",
  "state": "Indian state name or null",
  "notes": "any important observations about the bill"
}

Rules:
- Return ONLY the JSON object, no explanation
- Use null for any field you cannot find
- units_consumed_kwh must be a number (not a string)
- amount_paid_inr must be a number (not a string)
- If you see multiple meter readings, sum them into units_consumed_kwh
"""


class ElectricityExtractor(BaseExtractor):

    def extract_bill(self, file_bytes: bytes, mime_type: str) -> dict:
        """Extract data from an electricity bill PDF or image."""
        result = self.extract(file_bytes, mime_type, ELECTRICITY_PROMPT)
        result["document_type"] = "ELECTRICITY_BILL"
        return result