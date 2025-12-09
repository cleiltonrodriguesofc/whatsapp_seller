from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from django.conf import settings
import requests
import json

class WhatsAppConnectViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.whatsapp_connect_url = reverse("core:whatsapp_connect")

    def test_whatsapp_connect_view_get(self):
        """Test that the whatsapp_connect view renders correctly."""
        response = self.client.get(self.whatsapp_connect_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/whatsapp_connect.html")
        self.assertContains(response, "Pasos para iniciar sesión")
        self.assertContains(response, "Gerando QR Code...")

class WhatsAppAPIStatusViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.whatsapp_api_status_url = reverse("core:whatsapp_api_status")
        self.microservice_url = getattr(settings, "MICROSERVICE_URL", "http://localhost:3001")

    @patch("requests.get")
    def test_whatsapp_api_status_success(self, mock_requests_get):
        """Test that whatsapp_api_status returns microservice status on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "qr_ready",
            "connected": False,
            "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        }
        mock_requests_get.return_value = mock_response

        response = self.client.get(self.whatsapp_api_status_url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {
                "status": "qr_ready",
                "connected": False,
                "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
            },
        )
        mock_requests_get.assert_called_once_with(f"{self.microservice_url}/api/status", timeout=5)

    @patch("requests.get")
    def test_whatsapp_api_status_microservice_error(self, mock_requests_get):
        """Test that whatsapp_api_status handles microservice errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_requests_get.return_value = mock_response

        response = self.client.get(self.whatsapp_api_status_url)
        self.assertEqual(response.status_code, 200) # Django returns 200 even if microservice has error
        self.assertJSONEqual(
            response.content.decode(),
            {
                "status": "error",
                "connected": False,
                "error": "Microservice returned status 500"
            },
        )
        mock_requests_get.assert_called_once_with(f"{self.microservice_url}/api/status", timeout=5)

    @patch("requests.get")
    def test_whatsapp_api_status_connection_error(self, mock_requests_get):
        """Test that whatsapp_api_status handles connection errors to microservice."""
        mock_requests_get.side_effect = requests.exceptions.RequestException("Connection refused")

        response = self.client.get(self.whatsapp_api_status_url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {
                "status": "error",
                "connected": False,
                "error": "Failed to connect to microservice: Connection refused"
            },
        )
        mock_requests_get.assert_called_once_with(f"{self.microservice_url}/api/status", timeout=5)

class WhatsAppAPIRestartViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.whatsapp_api_restart_url = reverse("core:whatsapp_api_restart")
        self.microservice_url = getattr(settings, "MICROSERVICE_URL", "http://localhost:3001")

    @patch("requests.post")
    def test_whatsapp_api_restart_success(self, mock_requests_post):
        """Test that whatsapp_api_restart returns success on microservice restart."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "message": "Cliente reiniciado"}
        mock_requests_post.return_value = mock_response

        response = self.client.post(self.whatsapp_api_restart_url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {"success": True, "message": "Cliente reiniciado"},
        )
        mock_requests_post.assert_called_once_with(f"{self.microservice_url}/api/restart", timeout=10)

    @patch("requests.post")
    def test_whatsapp_api_restart_microservice_error(self, mock_requests_post):
        """Test that whatsapp_api_restart handles microservice errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_requests_post.return_value = mock_response

        response = self.client.post(self.whatsapp_api_restart_url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {"success": False, "error": "Microservice returned status 500"},
        )
        mock_requests_post.assert_called_once_with(f"{self.microservice_url}/api/restart", timeout=10)

    @patch("requests.post")
    def test_whatsapp_api_restart_connection_error(self, mock_requests_post):
        """Test that whatsapp_api_restart handles connection errors to microservice."""
        mock_requests_post.side_effect = requests.exceptions.RequestException("Connection refused")

        response = self.client.post(self.whatsapp_api_restart_url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {"success": False, "error": "Failed to connect to microservice: Connection refused"},
        )
        mock_requests_post.assert_called_once_with(f"{self.microservice_url}/api/restart", timeout=10)

class WhatsAppAPISendMessageViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.whatsapp_api_send_message_url = reverse("core:whatsapp_api_send_message")
        self.microservice_url = getattr(settings, "MICROSERVICE_URL", "http://localhost:3001")

    @patch("requests.post")
    def test_whatsapp_api_send_message_success(self, mock_requests_post):
        """Test that whatsapp_api_send_message sends message successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "message": "Mensagem enviada com sucesso"}
        mock_requests_post.return_value = mock_response

        payload = {"phone": "+5511999999999", "message": "Test message"}
        response = self.client.post(self.whatsapp_api_send_message_url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {"success": True, "message": "Mensagem enviada com sucesso"},
        )
        mock_requests_post.assert_called_once_with(f"{self.microservice_url}/api/send-message", json=payload, timeout=10)

    def test_whatsapp_api_send_message_missing_fields(self):
        """Test that whatsapp_api_send_message handles missing fields."""
        payload = {"phone": "+5511999999999"} # Missing message
        response = self.client.post(self.whatsapp_api_send_message_url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {"success": False, "error": "Phone and message are required"},
        )

    @patch("requests.post")
    def test_whatsapp_api_send_message_microservice_error(self, mock_requests_post):
        """Test that whatsapp_api_send_message handles microservice errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_requests_post.return_value = mock_response

        payload = {"phone": "+5511999999999", "message": "Test message"}
        response = self.client.post(self.whatsapp_api_send_message_url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {"success": False, "error": "Microservice returned status 500"},
        )
        mock_requests_post.assert_called_once_with(f"{self.microservice_url}/api/send-message", json=payload, timeout=10)

    @patch("requests.post")
    def test_whatsapp_api_send_message_connection_error(self, mock_requests_post):
        """Test that whatsapp_api_send_message handles connection errors to microservice."""
        mock_requests_post.side_effect = requests.exceptions.RequestException("Connection refused")

        payload = {"phone": "+5511999999999", "message": "Test message"}
        response = self.client.post(self.whatsapp_api_send_message_url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode(),
            {"success": False, "error": "Failed to connect to microservice: Connection refused"},
        )
        mock_requests_post.assert_called_once_with(f"{self.microservice_url}/api/send-message", json=payload, timeout=10)



