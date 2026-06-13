"""
database.py
-----------
Sets up SQLAlchemy async engine and session factory.

AsyncSessionLocal  — used in FastAPI dependency injection (async)
SyncSessionLocal   — used in Celery workers (sync)
Base               — all ORM models inherit from this
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


# --- Async engine (FastAPI) ---
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_development,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- Sync engine (Celery workers) ---
SYNC_DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg", "postgresql+psycopg2"
)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


# --- Base class for all ORM models ---
class Base(DeclarativeBase):
    pass
