"""Unit tests for WhatsAppClient service."""

import base64
from unittest.mock import patch

import pytest

from app.services.whatsapp_client import WhatsAppClient


class TestWhatsAppClient:
    """Tests for WhatsAppClient service."""

    def test_get_websocket_url_http(self):
        """Test WebSocket URL generation for HTTP API."""
        with patch("app.services.whatsapp_client.settings") as mock_settings:
            mock_settings.WHATSAPP_API_URL = "http://wpp.inovadata.tech"
            mock_settings.WHATSAPP_API_USER = "user"
            mock_settings.WHATSAPP_API_PASSWORD = "pass"

            client = WhatsAppClient("test-device-id")
            url = client.get_websocket_url()

        assert url == "ws://wpp.inovadata.tech/ws?device_id=test-device-id"

    def test_get_websocket_url_https(self):
        """Test WebSocket URL generation for HTTPS API."""
        with patch("app.services.whatsapp_client.settings") as mock_settings:
            mock_settings.WHATSAPP_API_URL = "https://wpp.inovadata.tech"
            mock_settings.WHATSAPP_API_USER = "user"
            mock_settings.WHATSAPP_API_PASSWORD = "pass"

            client = WhatsAppClient("test-device-id")
            url = client.get_websocket_url()

        assert url == "wss://wpp.inovadata.tech/ws?device_id=test-device-id"

    def test_get_websocket_url_with_port(self):
        """Test WebSocket URL generation with port."""
        with patch("app.services.whatsapp_client.settings") as mock_settings:
            mock_settings.WHATSAPP_API_URL = "http://localhost:8080"
            mock_settings.WHATSAPP_API_USER = "user"
            mock_settings.WHATSAPP_API_PASSWORD = "pass"

            client = WhatsAppClient("device-123")
            url = client.get_websocket_url()

        assert url == "ws://localhost:8080/ws?device_id=device-123"

    def test_get_auth_header_with_credentials(self):
        """Test auth header generation with credentials."""
        with patch("app.services.whatsapp_client.settings") as mock_settings:
            mock_settings.WHATSAPP_API_URL = "http://wpp.inovadata.tech"
            mock_settings.WHATSAPP_API_USER = "myuser"
            mock_settings.WHATSAPP_API_PASSWORD = "mypass"

            client = WhatsAppClient("test-device")
            header = client.get_auth_header()

        assert header is not None
        assert "Authorization" in header

        # Verify Basic auth format
        auth_value = header["Authorization"]
        assert auth_value.startswith("Basic ")

        # Decode and verify credentials
        encoded = auth_value.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "myuser:mypass"

    def test_get_auth_header_no_credentials(self):
        """Test auth header returns None when no credentials configured."""
        with patch("app.services.whatsapp_client.settings") as mock_settings:
            mock_settings.WHATSAPP_API_URL = "http://wpp.inovadata.tech"
            mock_settings.WHATSAPP_API_USER = ""
            mock_settings.WHATSAPP_API_PASSWORD = ""

            client = WhatsAppClient("test-device")
            header = client.get_auth_header()

        assert header is None

    def test_client_initialization(self):
        """Test client initialization stores device ID."""
        with patch("app.services.whatsapp_client.settings") as mock_settings:
            mock_settings.WHATSAPP_API_URL = "http://wpp.inovadata.tech"
            mock_settings.WHATSAPP_API_USER = "user"
            mock_settings.WHATSAPP_API_PASSWORD = "pass"

            client = WhatsAppClient("my-device-id")

        assert client.device_id == "my-device-id"
        assert client.base_url == "http://wpp.inovadata.tech"
