"""
services/extraction/water_bill_extractor.py
--------------------------------------------
Extracts structured data from water bills using Claude.

Works with:
- TWAD (Tamil Nadu Water Supply and Drainage Board)
- Municipal corporation water bills
- Industrial water supply invoices
- Borewell/tanker invoices
"""

from app.services.extraction.base_extractor import BaseExtractor

WATER_BILL_PROMPT = """
You are an expert at reading Indian water utility bills and invoices.

Extract the following information from this water bill and return
ONLY a valid JSON object with no preamble or markdown.

Required fields:
{
  "utility_name": "name of water board or supplier e.g. TWAD, Chennai Metro Water",
  "account_number": "consumer/account number",
  "consumer_name": "name on the bill",
  "billing_period_start": "YYYY-MM-DD or null",
  "billing_period_end": "YYYY-MM-DD or null",
  "quantity_kl": number or null,
  "quantity_unit": "KL or litres or cubic metres",
  "amount_paid_inr": number or null,
  "meter_number": "meter number or null",
  "water_source": "MUNICIPAL or GROUNDWATER or TANKER or SURFACE_WATER or OTHER",
  "water_category": "WITHDRAWAL or CONSUMPTION",
  "supply_type": "Drinking or Industrial or Commercial or null",
  "due_date": "YYYY-MM-DD or null",
  "address": "supply address or null",
  "state": "Indian state name or null",
  "notes": "any important observations about the bill"
}

Rules:
- Return ONLY the JSON object, no explanation
- Use null for any field you cannot find
- quantity_kl must be a number in kilolitres
  (convert if needed: 1000 litres = 1 KL, 1 cubic metre = 1 KL)
- amount_paid_inr must be a number
"""


class WaterBillExtractor(BaseExtractor):

    def extract_bill(self, file_bytes: bytes, mime_type: str) -> dict:
        """Extract data from a water bill PDF or image."""
        result = self.extract(file_bytes, mime_type, WATER_BILL_PROMPT)
        result["document_type"] = "WATER_BILL"
        return result