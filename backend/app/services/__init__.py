# Import all models here so SQLAlchemy registers them together
# Order matters — parent models before child models

from app.models.company import Company
from app.models.user import User
from app.models.facility import Facility
from app.models.document import Document
from app.models.energy import EnergyActivity
from app.models.water_quantity import WaterQuantityRecord
from app.models.water_quality import WaterQualitySample, WaterQualityReading
from app.models.emission import EmissionRecord
from app.models.report import Report

__all__ = [
    "Company",
    "User",
    "Facility",
    "Document",
    "EnergyActivity",
    "WaterQuantityRecord",
    "WaterQualitySample",
    "WaterQualityReading",
    "EmissionRecord",
    "Report",
]