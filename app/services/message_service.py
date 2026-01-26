"""Message processing service."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ContactRepository, MessageRepository
from app.models import Contact
from app.models.message import MessageDirection, MessageStatus
from app.services.whatsapp_client import WhatsAppClient


class MessageService:
    """Service for handling message sending and receiving."""

    def __init__(self, db: AsyncSession, device_id: UUID):
        self.db = db
        self.device_id = device_id
        self.message_repo = MessageRepository(db)
        self.contact_repo = ContactRepository(db)
        self.whatsapp_client = WhatsAppClient(str(device_id))

    async def send_message(
        self,
        phone: str,
        content: str,
        content_type: str = "text",
        media_url: str | None = None,
    ) -> dict:
        """Send a message and record it in the database."""
        # Get or create contact
        contact, _ = await self.contact_repo.get_or_create(
            device_id=self.device_id,
            phone_number=phone,
        )

        # Create message record with pending status
        message = await self.message_repo.create(
            device_id=self.device_id,
            contact_id=contact.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            content_type=content_type,
            content=content,
            media_url=media_url,
        )

        try:
            # Send via WhatsApp API based on content type
            if content_type == "text":
                result = await self.whatsapp_client.send_message(phone, content)
            elif content_type == "image" and media_url:
                result = await self.whatsapp_client.send_image(phone, media_url, content or "")
            elif content_type == "audio" and media_url:
                result = await self.whatsapp_client.send_audio(phone, media_url)
            elif content_type == "video" and media_url:
                result = await self.whatsapp_client.send_video(phone, media_url, content or "")
            elif content_type == "document" and media_url:
                result = await self.whatsapp_client.send_document(phone, media_url)
            else:
                result = await self.whatsapp_client.send_message(phone, content)

            # Update message with WhatsApp ID and sent status
            whatsapp_message_id = result.get("messageId") or result.get("id")
            message = await self.message_repo.update(
                message,
                whatsapp_message_id=whatsapp_message_id,
                status=MessageStatus.SENT,
            )

            return {
                "success": True,
                "message_id": str(message.id),
                "whatsapp_message_id": whatsapp_message_id,
            }

        except Exception as e:
            # Update message status to failed
            await self.message_repo.update(
                message,
                status=MessageStatus.FAILED,
                extra_data={"error": str(e)},
            )
            raise

    async def process_incoming_message(self, data: dict) -> Contact | None:
        """Process an incoming message from webhook.

        Args:
            data: The incoming message data from WhatsApp webhook

        Returns:
            The contact who sent the message, or None if invalid
        """
        # Extract message data
        sender_phone = data.get("from", "").replace("@s.whatsapp.net", "")
        if not sender_phone:
            return None

        # Get or create contact
        contact, _ = await self.contact_repo.get_or_create(
            device_id=self.device_id,
            phone_number=sender_phone,
            whatsapp_jid=data.get("from"),
            push_name=data.get("pushName"),
            is_group=data.get("isGroup", False),
        )

        # Determine content type
        content_type = "text"
        content = data.get("body", "")
        media_url = None

        if data.get("hasMedia"):
            media_type = data.get("type", "")
            if media_type in ["image", "audio", "video", "document"]:
                content_type = media_type
            media_url = data.get("mediaUrl")
            if not content:
                content = data.get("caption", "")

        # Create message record
        await self.message_repo.create(
            device_id=self.device_id,
            contact_id=contact.id,
            whatsapp_message_id=data.get("id"),
            direction=MessageDirection.INBOUND,
            status=MessageStatus.DELIVERED,
            content_type=content_type,
            content=content,
            media_url=media_url,
            extra_data=data,
        )

        return contact
