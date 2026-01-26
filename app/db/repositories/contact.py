"""Contact repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import Contact


class ContactRepository(BaseRepository[Contact]):
    """Repository for contact operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Contact)

    async def list(
        self,
        *,
        device_id: UUID | None = None,
        device_ids: list[UUID] | None = None,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        is_blocked: bool | None = None,
        is_group: bool | None = None,
    ) -> tuple[list[Contact], int]:
        """List contacts for device(s) with optional filtering."""
        # Build base query
        base_query = select(Contact)

        # Filter by device(s)
        if device_id:
            base_query = base_query.where(Contact.device_id == device_id)
        elif device_ids:
            base_query = base_query.where(Contact.device_id.in_(device_ids))

        if search:
            search_term = f"%{search}%"
            base_query = base_query.where(
                or_(
                    Contact.name.ilike(search_term),
                    Contact.push_name.ilike(search_term),
                    Contact.phone_number.ilike(search_term),
                )
            )

        if is_blocked is not None:
            base_query = base_query.where(Contact.is_blocked == is_blocked)

        if is_group is not None:
            base_query = base_query.where(Contact.is_group == is_group)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items
        stmt = base_query.order_by(Contact.name, Contact.phone_number).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_device(self, device_id: UUID, contact_id: UUID) -> Contact | None:
        """Get a contact ensuring it belongs to the device."""
        stmt = select(Contact).where(
            Contact.id == contact_id,
            Contact.device_id == device_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_phone(self, device_id: UUID, phone_number: str) -> Contact | None:
        """Get contact by phone number for a device."""
        stmt = select(Contact).where(
            Contact.device_id == device_id,
            Contact.phone_number == phone_number,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_jid(self, device_id: UUID, whatsapp_jid: str) -> Contact | None:
        """Get contact by WhatsApp JID for a device."""
        stmt = select(Contact).where(
            Contact.device_id == device_id,
            Contact.whatsapp_jid == whatsapp_jid,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        device_id: UUID,
        phone_number: str,
        whatsapp_jid: str | None = None,
        **kwargs,
    ) -> tuple[Contact, bool]:
        """Get existing contact or create a new one. Returns (contact, created)."""
        # Try to find existing contact
        contact = await self.get_by_phone(device_id, phone_number)
        if contact:
            return contact, False

        # Create JID if not provided
        if not whatsapp_jid:
            # Remove non-numeric characters for JID
            clean_number = "".join(filter(str.isdigit, phone_number))
            whatsapp_jid = f"{clean_number}@s.whatsapp.net"

        # Create new contact
        contact = await self.create(
            device_id=device_id,
            phone_number=phone_number,
            whatsapp_jid=whatsapp_jid,
            **kwargs,
        )
        return contact, True
