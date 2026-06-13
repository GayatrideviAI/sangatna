"""
services/consultant_service.py
--------------------------------
Manages the relationship between consultants and their MSME clients.
A consultant must be explicitly linked to a company before they
can access or modify that company's data.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company, ConsultantClient
from app.models.user import User, UserRole


class ConsultantService:

    @staticmethod
    async def assign_client(
        db: AsyncSession,
        consultant_id: UUID,
        client_company_id: UUID,
    ) -> ConsultantClient:
        """Link a consultant to an MSME company."""

        # Verify consultant exists and has CONSULTANT role
        consultant_result = await db.execute(
            select(User).where(User.id == consultant_id)
        )
        consultant = consultant_result.scalar_one_or_none()
        if not consultant:
            raise ValueError("Consultant user not found.")
        if consultant.role != UserRole.CONSULTANT:
            raise ValueError("User is not a CONSULTANT.")

        # Verify client company exists
        company_result = await db.execute(
            select(Company).where(Company.id == client_company_id)
        )
        company = company_result.scalar_one_or_none()
        if not company:
            raise ValueError("Client company not found.")

        # Check if already assigned
        existing = await db.execute(
            select(ConsultantClient).where(
                ConsultantClient.consultant_id == consultant_id,
                ConsultantClient.client_company_id == client_company_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Consultant is already assigned to this company.")

        link = ConsultantClient(
            consultant_id=consultant_id,
            client_company_id=client_company_id,
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return link

    @staticmethod
    async def list_clients(
        db: AsyncSession,
        consultant_id: UUID,
    ) -> list[Company]:
        """List all MSME companies a consultant manages."""
        result = await db.execute(
            select(Company)
            .join(
                ConsultantClient,
                ConsultantClient.client_company_id == Company.id,
            )
            .where(ConsultantClient.consultant_id == consultant_id)
            .order_by(Company.name)
        )
        return result.scalars().all()

    @staticmethod
    async def is_authorised(
        db: AsyncSession,
        consultant_id: UUID,
        client_company_id: UUID,
    ) -> bool:
        """Check if a consultant is authorised to access a company."""
        result = await db.execute(
            select(ConsultantClient).where(
                ConsultantClient.consultant_id == consultant_id,
                ConsultantClient.client_company_id == client_company_id,
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def remove_client(
        db: AsyncSession,
        consultant_id: UUID,
        client_company_id: UUID,
    ) -> bool:
        """Remove a consultant-client link."""
        result = await db.execute(
            select(ConsultantClient).where(
                ConsultantClient.consultant_id == consultant_id,
                ConsultantClient.client_company_id == client_company_id,
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            return False
        await db.delete(link)
        await db.commit()
        return True