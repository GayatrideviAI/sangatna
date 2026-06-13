"""
services/calculation/emission_factors.py
-----------------------------------------
Loads emission factor reference data from JSON files.
Single source of truth for all EF lookups in the calculation engines.
"""

import json
from pathlib import Path

# Path to reference data
REF_DIR = Path(__file__).parent.parent.parent / "reference_data" / "emission_factors"


def _load(filename: str) -> dict:
    with open(REF_DIR / filename) as f:
        return json.load(f)


# Load once at module import — these files are small and static
_GRID = _load("grid_india_state.json")
_FUEL = _load("fuel_ipcc.json")


def get_grid_emission_factor(state: str) -> tuple[float, str]:
    """
    Returns (emission_factor, source_note) for a given Indian state.
    Falls back to national average if state not found.

    Example:
        ef, source = get_grid_emission_factor("Tamil Nadu")
        # ef = 0.82, source = "CEA Version 18 — Tamil Nadu"
    """
    states = _GRID["states"]
    factor = states.get(state) or states.get("default", 0.82)
    source = f"CEA CO2 Baseline Database Version 18 — {state}"
    return factor, source


def get_fuel_emission_factor(fuel_type: str) -> tuple[float, str, str]:
    """
    Returns (emission_factor, unit, source_note) for a fuel type.

    Example:
        ef, unit, source = get_fuel_emission_factor("DIESEL")
        # ef = 2.68, unit = "kg CO2e/litre", source = "IPCC AR6"
    """
    fuels = _FUEL["fuels"]
    fuel = fuels.get(fuel_type.upper())
    if not fuel:
        raise ValueError(f"Unknown fuel type: {fuel_type}")
    return fuel["factor"], fuel["unit"], "IPCC AR6 + MoEFCC India GHG Inventory"