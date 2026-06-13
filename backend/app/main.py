"""
main.py
-------
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

from app.api.v1.companies import router as companies_router
from app.api.v1.auth import router as auth_router

# Import all models so SQLAlchemy registers them
# Must use full import path to avoid clashing with the `app` FastAPI instance
import app.models.company
import app.models.user
import app.models.facility
import app.models.document
import app.models.energy
import app.models.water_quantity
import app.models.water_quality
import app.models.emission
import app.models.report

from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.facilities import router as facilities_router
from app.api.v1.documents import router as documents_router
from app.api.v1.energy import router as energy_router
from app.api.v1.water_quantity import router as water_quantity_router
from app.api.v1.water_quality import router as water_quality_router
from app.api.v1.emissions import router as emissions_router
from app.api.v1.consultants import router as consultants_router
from app.api.v1.utility_connections import router as utility_connections_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    print(f"SANGATNA starting — environment: {settings.ENVIRONMENT}")
    yield
    print("SANGATNA shutting down.")


app = FastAPI(
    title="SANGATNA ESG Platform",
    description="AI-powered ESG measurement and reporting for MSMEs",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(companies_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }

# Routers
app.include_router(auth_router,     prefix="/api/v1")
app.include_router(companies_router, prefix="/api/v1")
app.include_router(facilities_router, prefix="/api/v1")
app.include_router(documents_router,  prefix="/api/v1")
app.include_router(energy_router,     prefix="/api/v1")
app.include_router(water_quantity_router, prefix="/api/v1")
app.include_router(water_quality_router,  prefix="/api/v1")
app.include_router(emissions_router,      prefix="/api/v1")
app.include_router(consultants_router,    prefix="/api/v1")
app.include_router(utility_connections_router, prefix="/api/v1")
