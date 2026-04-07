import pytest
from unittest.mock import AsyncMock, patch
from core.infrastructure.services.email_service import EmailService


@pytest.fixture
def email_service():
    # Setup service with some fake credentials for testing
    with patch.dict(
        "os.environ",
        {
            "SMTP_SERVER": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test_user",
            "SMTP_PASSWORD": "test_password",
            "FROM_EMAIL": "noreply@test.com",
        },
    ):
        return EmailService()


@pytest.mark.asyncio
async def test_send_password_reset_email_calls_smtp(email_service):
    # Mock aiosmtplib.send
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        to_email = "test@example.com"
        reset_link = "http://localhost:8000/reset?token=123"

        await email_service.send_password_reset_email(to_email, reset_link)

        # Verify call was made
        assert mock_send.called

        # Verify message details
        sent_message = mock_send.call_args[0][0]
        assert sent_message["To"] == to_email
        assert sent_message["Subject"] == "Recuperação de Senha | WhatSeller Pro"
        assert reset_link in sent_message.get_payload()[1].get_content()


@pytest.mark.asyncio
async def test_email_service_logs_without_credentials():
    # Create service instance without credentials
    with patch.dict("os.environ", {}, clear=True):
        service = EmailService()
        service.smtp_user = None
        service.smtp_password = None

        with patch("core.infrastructure.services.email_service.logger") as mock_logger:
            to_email = "test@example.com"
            reset_link = "http://localhost:8000/reset?token=123"

            await service.send_password_reset_email(to_email, reset_link)

            # Should have logged warnings
            assert mock_logger.warning.called
            # One warning for SMTP missing, one for the link
            assert mock_logger.warning.call_count >= 2

            # Check if link was logged
            link_logged = any(
                reset_link in str(call) for call in mock_logger.warning.call_args_list
            )
            assert link_logged
