import os
import logging
from email.message import EmailMessage
import aiosmtplib
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_password = os.environ.get("SMTP_PASSWORD")
        self.from_email = os.environ.get("FROM_EMAIL", self.smtp_user)

        # Setup Jinja2 for email templates
        template_dir = os.path.join(
            os.path.dirname(__file__), "../../presentation/web/templates/emails"
        )
        if not os.path.exists(template_dir):
            os.makedirs(template_dir, exist_ok=True)

        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))

    async def send_password_reset_email(self, to_email: str, reset_link: str):
        """Sends a password recovery email with the reset link."""
        subject = "Recuperação de Senha | WhatSeller Pro"

        # In a real scenario, we'd use a template. For now, a clean HTML string.
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #6366f1;">WhatSeller Pro</h2>
                    <p>Olá,</p>
                    <p>Recebemos uma solicitação para redefinir a senha da sua conta.</p>
                    <p>Para prosseguir com a alteração, clique no botão abaixo:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" 
                           style="background-color: #6366f1; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                           Redefinir Minha Senha
                        </a>
                    </div>
                    <p>Se você não solicitou esta alteração, pode ignorar este e-mail com segurança.</p>
                    <p style="font-size: 0.8rem; color: #777; margin-top: 40px;">
                        Este link expirará em 1 hora por razões de segurança.
                    </p>
                </div>
            </body>
        </html>
        """

        await self._send_email(to_email, subject, html_content, reset_link)

    async def _send_email(
        self, to_email: str, subject: str, html_content: str, reset_link: str = None
    ):
        if not self.smtp_user or not self.smtp_password:
            logger.warning(
                "⚠️ SMTP não configurado. O e-mail para %s NÃO foi enviado.", to_email
            )
            if reset_link:
                logger.warning("🔗 LINK DE RECUPERAÇÃO (PARA TESTE): %s", reset_link)
            return

        message = EmailMessage()
        message["From"] = self.from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(
            "Para visualizar esta mensagem, utilize um leitor de e-mail compatível com HTML."
        )
        message.add_alternative(html_content, subtype="html")

        try:
            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True if self.smtp_port == 587 else False,
                use_tls=True if self.smtp_port == 465 else False,
            )
            logger.info("Email sent successfully to %s", to_email)
        except Exception as e:
            logger.error("Failed to send email to %s: %s", to_email, str(e))
            raise e
