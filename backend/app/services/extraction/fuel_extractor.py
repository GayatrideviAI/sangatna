"""
services/extraction/fuel_extractor.py
---------------------------------------
Extracts structured data from fuel receipts and purchase records.

Works with:
- Diesel purchase receipts (petrol bunks)
- LPG invoices
- CNG receipts
- Furnace oil invoices
- Generator fuel logs
"""

from app.services.extraction.base_extractor import BaseExtractor

FUEL_PROMPT = """
You are an expert at reading Indian fuel purchase receipts and invoices.

Extract the following information and return
ONLY a valid JSON object with no preamble or markdown.

Required fields:
{
  "supplier_name": "name of fuel supplier or petrol bunk",
  "invoice_number": "invoice or receipt number",
  "consumer_name": "name of buyer on receipt",
  "purchase_date": "YYYY-MM-DD or null",
  "fuel_type": "DIESEL or LPG or CNG or FURNACE_OIL or PETROL or OTHER",
  "quantity": number or null,
  "quantity_unit": "litres or kg or cubic_metres",
  "rate_per_unit": number or null,
  "amount_paid_inr": number or null,
  "vehicle_number": "vehicle registration if shown or null",
  "equipment_id": "generator or equipment ID if shown or null",
  "address": "delivery or purchase address or null",
  "state": "Indian state name or null",
  "gst_number": "GST number if shown or null",
  "notes": "any important observations"
}

Rules:
- Return ONLY the JSON object
- Use null for any field you cannot find
- quantity must be a number
- For LPG: quantity is usually in kg
- For diesel/petrol: quantity is usually in litres
- amount_paid_inr must be a number
"""


class FuelExtractor(BaseExtractor):

    def extract_receipt(self, file_bytes: bytes, mime_type: str) -> dict:
        """Extract data from a fuel receipt or invoice."""
        result = self.extract(file_bytes, mime_type, FUEL_PROMPT)
        result["document_type"] = "FUEL_RECEIPT"
        return result