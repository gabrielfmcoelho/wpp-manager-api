"""HTTP client for WhatsApp API integration."""

import base64
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.core.exceptions import WhatsAppAPIError

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """HTTP client for communicating with the WhatsApp API server."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.base_url = settings.WHATSAPP_API_URL
        self.auth = (
            (settings.WHATSAPP_API_USER, settings.WHATSAPP_API_PASSWORD)
            if settings.WHATSAPP_API_USER
            else None
        )
        logger.debug(f"WhatsAppClient initialized: base_url={self.base_url}, auth={'set' if self.auth else 'none'}")

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Make an HTTP request to the WhatsApp API."""
        url = f"{self.base_url}{path}"
        logger.info(f"WhatsApp API request: {method} {url} (device: {self.device_id})")

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = kwargs.pop("headers", {})
            headers["X-Device-Id"] = self.device_id

            try:
                response = await client.request(
                    method,
                    url,
                    auth=self.auth,
                    headers=headers,
                    **kwargs,
                )

                logger.info(f"WhatsApp API response: {response.status_code}")

                if response.status_code >= 400:
                    logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
                    raise WhatsAppAPIError(response.text)

                return response.json()

            except httpx.RequestError as e:
                logger.error(f"WhatsApp API connection error: {e}")
                raise WhatsAppAPIError(f"Connection error: {e}")

    async def send_message(self, phone: str, message: str) -> dict[str, Any]:
        """Send a text message to a phone number."""
        return await self._request(
            "POST",
            "/send/message",
            json={"phone": phone, "message": message},
        )

    async def send_image(
        self,
        phone: str,
        image_url: str,
        caption: str = "",
    ) -> dict[str, Any]:
        """Send an image to a phone number."""
        return await self._request(
            "POST",
            "/send/image",
            data={"phone": phone, "caption": caption, "image_url": image_url},
        )

    async def send_audio(self, phone: str, audio_url: str) -> dict[str, Any]:
        """Send an audio file to a phone number."""
        return await self._request(
            "POST",
            "/send/audio",
            data={"phone": phone, "audio_url": audio_url},
        )

    async def send_video(
        self,
        phone: str,
        video_url: str,
        caption: str = "",
    ) -> dict[str, Any]:
        """Send a video to a phone number."""
        return await self._request(
            "POST",
            "/send/video",
            data={"phone": phone, "caption": caption, "video_url": video_url},
        )

    async def send_document(
        self,
        phone: str,
        document_url: str,
        filename: str = "",
    ) -> dict[str, Any]:
        """Send a document to a phone number."""
        return await self._request(
            "POST",
            "/send/document",
            data={"phone": phone, "document_url": document_url, "filename": filename},
        )

    async def get_chats(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get list of chats."""
        return await self._request(
            "GET",
            "/chats",
            params={"limit": limit, "offset": offset},
        )

    async def get_messages(
        self,
        phone: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get messages from a specific chat."""
        return await self._request(
            "GET",
            f"/messages/{phone}",
            params={"limit": limit, "offset": offset},
        )

    async def get_status(self) -> dict[str, Any]:
        """Get device connection status."""
        return await self._request("GET", "/app/status")

    async def get_qr_code(self) -> dict[str, Any]:
        """
        Get QR code for login.

        Returns:
            dict with 'results.qr_link' containing URL to QR code image
            and 'results.qr_duration' with validity period in seconds
        """
        return await self._request("GET", "/app/login")

    async def logout(self) -> dict[str, Any]:
        """Logout from WhatsApp."""
        return await self._request("GET", "/app/logout")

    async def login_with_code(self, phone: str) -> dict[str, Any]:
        """
        Login using pairing code instead of QR code.

        Args:
            phone: Phone number to pair with (e.g., "5511999999999")

        Returns:
            dict with 'results.pairing_code' containing the 8-character pairing code
        """
        return await self._request("GET", "/app/login-with-code", params={"phone": phone})

    async def reconnect(self) -> dict[str, Any]:
        """
        Attempt to reconnect a disconnected device.

        Returns:
            dict with connection status
        """
        return await self._request("GET", "/app/reconnect")

    async def get_contacts(self) -> dict[str, Any]:
        """Get all contacts."""
        return await self._request("GET", "/contacts")

    async def get_profile_picture(self, phone: str) -> dict[str, Any]:
        """Get profile picture URL for a contact."""
        return await self._request("GET", f"/contacts/{phone}/picture")

    def get_websocket_url(self) -> str:
        """Get WebSocket URL for real-time event connection."""
        parsed = urlparse(self.base_url)
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_host = parsed.netloc
        return f"{ws_scheme}://{ws_host}/ws?device_id={self.device_id}"

    def get_auth_header(self) -> dict[str, str] | None:
        """Get authentication header for WebSocket connection."""
        if not self.auth:
            return None
        credentials = f"{self.auth[0]}:{self.auth[1]}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
