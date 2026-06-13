"""
services/intelligence/compliance_checker.py
--------------------------------------------
Evaluates water quality readings against BIS IS:10500 and CPCB limits.

For each parameter:
  - Normalizes the parameter name using alias map
  - Looks up the limit from the correct standard
  - Compares the measured value
  - Returns SAFE / EXCEEDS_LIMIT / NO_LIMIT / NO_DATA

Also uses Claude to generate a plain-language compliance summary
that an MSME owner can understand without ESG expertise.
"""

import json
from pathlib import Path

import anthropic

from app.config import settings
from app.models.water_quality import ComplianceStatus

CLAUDE_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Load compliance standards once at module import
# ---------------------------------------------------------------------------

STD_DIR = (
    Path(__file__).parent.parent.parent
    / "reference_data"
    / "compliance_standards"
)


def _load_standard(filename: str) -> dict:
    with open(STD_DIR / filename) as f:
        return json.load(f)


_BIS  = _load_standard("bis_10500.json")
_CPCB = _load_standard("cpcb_effluent.json")


# ---------------------------------------------------------------------------
# Parameter name aliases
# Maps lab report names → our standard JSON keys
# ---------------------------------------------------------------------------

PARAMETER_ALIASES = {
    "ph value":                     "pH",
    "ph":                           "pH",
    "total dissolved solids":       "TDS",
    "tds":                          "TDS",
    "total hardness (caco3)":       "Hardness",
    "total hardness":               "Hardness",
    "hardness":                     "Hardness",
    "chlorides (as cl)":            "Chloride",
    "chlorides":                    "Chloride",
    "chloride":                     "Chloride",
    "iron (as fe)":                 "Iron",
    "iron":                         "Iron",
    "nitrates":                     "Nitrate",
    "nitrate":                      "Nitrate",
    "fluorides":                    "Fluoride",
    "fluoride":                     "Fluoride",
    "manganese (as mn)":            "Manganese",
    "manganese":                    "Manganese",
    "lead (as pb)":                 "Lead",
    "lead":                         "Lead",
    "arsenic (as as)":              "Arsenic",
    "arsenic":                      "Arsenic",
    "mercury (as hg)":              "Mercury",
    "mercury":                      "Mercury",
    "cadmium (as cd)":              "Cadmium",
    "cadmium":                      "Cadmium",
    "chromium (as cr)":             "Chromium",
    "chromium":                     "Chromium",
    "dissolved oxygen":             "DO",
    "do":                           "DO",
    "total coliforms":              "Total Coliform",
    "total coliform":               "Total Coliform",
    "e.coli":                       "E. coli",
    "e. coli":                      "E. coli",
    "ecoli":                        "E. coli",
    "biochemical oxygen demand":    "BOD",
    "bod":                          "BOD",
    "chemical oxygen demand":       "COD",
    "cod":                          "COD",
    "turbidity":                    "Turbidity",
    "electrical conductivity":      "Electrical Conductivity",
    "sulfates (as so4)":            "Sulfate",
    "sulphates (as so4)":           "Sulfate",
    "sulfates (as so4)":            "Sulfate",
    "sulfates":                     "Sulfate",
    "sulphates":                    "Sulfate",
    "calcium (as ca)":              "Calcium",
    "magnesium (as mg)":            "Magnesium",
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ComplianceChecker:

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # ------------------------------------------------------------------
    # Single parameter evaluation
    # ------------------------------------------------------------------

    def evaluate_reading(
        self,
        parameter_name: str,
        measured_value: float | None,
        water_type: str,
    ) -> dict:
        """
        Evaluate a single parameter reading against the relevant standard.

        Returns a dict with:
            bis_limit, cpcb_limit, overall_status, compliance_notes
        """
        if measured_value is None:
            return self._no_data_result()

        is_wastewater = water_type in ("WASTEWATER", "TREATED_EFFLUENT")
        standard      = _CPCB if is_wastewater else _BIS
        standard_name = "CPCB" if is_wastewater else "BIS IS:10500"
        params        = standard.get("parameters", {})

        # Normalize parameter name via alias map
        normalized = PARAMETER_ALIASES.get(parameter_name.lower())
        param = None

        if normalized:
            param = params.get(normalized)
        if not param:
            param = params.get(parameter_name)
        if not param:
            param = params.get(
                next(
                    (k for k in params if k.lower() == parameter_name.lower()),
                    None,
                )
            )

        if not param:
            return {
                "bis_limit":        None,
                "cpcb_limit":       None,
                "overall_status":   ComplianceStatus.NO_LIMIT,
                "compliance_notes": (
                    f"No {standard_name} limit defined for {parameter_name}."
                ),
            }

        min_val = param.get("min")
        max_val = param.get("max")
        unit    = param.get("unit", "")

        exceeded     = False
        notes_parts  = []

        if max_val is not None and measured_value > max_val:
            exceeded = True
            notes_parts.append(
                f"Exceeds {standard_name} maximum of {max_val} {unit} "
                f"(measured: {measured_value} {unit})"
            )
        if min_val is not None and measured_value < min_val:
            exceeded = True
            notes_parts.append(
                f"Below {standard_name} minimum of {min_val} {unit} "
                f"(measured: {measured_value} {unit})"
            )
        if not exceeded:
            notes_parts.append(
                f"Within {standard_name} limit "
                f"({measured_value} {unit} — acceptable range: "
                f"{min_val or '—'} to {max_val or '—'} {unit})"
            )

        status     = (
            ComplianceStatus.EXCEEDS_LIMIT
            if exceeded
            else ComplianceStatus.SAFE
        )
        bis_limit  = max_val if not is_wastewater else None
        cpcb_limit = max_val if is_wastewater else None

        return {
            "bis_limit":        bis_limit,
            "cpcb_limit":       cpcb_limit,
            "overall_status":   status,
            "compliance_notes": " | ".join(notes_parts),
        }

    # ------------------------------------------------------------------
    # Evaluate a full list of readings
    # ------------------------------------------------------------------

    def evaluate_all_readings(
        self,
        readings: list[dict],
        water_type: str,
    ) -> list[dict]:
        """
        Evaluate a list of readings.
        Each reading dict must have: parameter_name, measured_value.
        Returns the same list with compliance fields added.
        """
        return [
            {
                **r,
                **self.evaluate_reading(
                    r["parameter_name"],
                    r.get("measured_value"),
                    water_type,
                ),
            }
            for r in readings
        ]

    # ------------------------------------------------------------------
    # Claude plain-language summary
    # ------------------------------------------------------------------

    def generate_summary_narrative(
        self,
        sample_info: dict,
        evaluated_readings: list[dict],
    ) -> str:
        """
        Uses Claude to write a plain-language compliance summary
        for the MSME owner. No ESG jargon.
        """
        exceeded = [
            r for r in evaluated_readings
            if r.get("overall_status") == ComplianceStatus.EXCEEDS_LIMIT
        ]
        safe = [
            r for r in evaluated_readings
            if r.get("overall_status") == ComplianceStatus.SAFE
        ]

        prompt = f"""You are an environmental compliance expert helping an Indian MSME
understand their water quality test results in simple language.

Sample information:
{json.dumps(sample_info, indent=2)}

Parameters that EXCEED limits ({len(exceeded)} parameters):
{json.dumps([
    {
        "parameter": r["parameter_name"],
        "value": r.get("measured_value"),
        "notes": r.get("compliance_notes"),
    }
    for r in exceeded
], indent=2)}

Parameters that are SAFE ({len(safe)} parameters):
{json.dumps([r["parameter_name"] for r in safe], indent=2)}

Write a brief (3-4 sentences) plain-language summary for the MSME owner that:
1. States clearly whether their water is compliant or not
2. Highlights the most serious issues if any
3. Suggests one immediate action if there are violations
4. Uses simple language — no technical jargon

Respond with just the summary text, no headings or bullet points."""

        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _no_data_result(self) -> dict:
        return {
            "bis_limit":        None,
            "cpcb_limit":       None,
            "overall_status":   ComplianceStatus.NO_DATA,
            "compliance_notes": "No measured value available.",
        }