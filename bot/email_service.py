"""
Email service for authentication system
Supports Mailgun API and SMTP for sending verification emails
"""

import asyncio
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiohttp
import aiosmtplib
from decouple import config
from jinja2 import Template

logger = logging.getLogger(__name__)

# Email configuration
EMAIL_PROVIDER = config("EMAIL_PROVIDER", default="mailgun")  # mailgun or smtp
MAILGUN_API_KEY = config("MAILGUN_API_KEY", default="")
MAILGUN_DOMAIN = config("MAILGUN_DOMAIN", default="")
MAILGUN_API_URL = config("MAILGUN_API_URL", default="https://api.mailgun.net/v3")

# SMTP configuration (fallback)
SMTP_HOST = config("SMTP_HOST", default="smtp.gmail.com")
SMTP_PORT = config("SMTP_PORT", default=587, cast=int)
SMTP_USERNAME = config("SMTP_USERNAME", default="")
SMTP_PASSWORD = config("SMTP_PASSWORD", default="")
SMTP_USE_TLS = config("SMTP_USE_TLS", default=True, cast=bool)

# Email settings
FROM_EMAIL = config("FROM_EMAIL", default="noreply@localhost")
FROM_NAME = config("FROM_NAME", default="dYdX Trading Bot")
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:8000")


class EmailTemplates:
    """Email templates for different types of notifications"""

    EMAIL_VERIFICATION = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Email Verification - {{ app_name }}</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background-color: #f8f9fa; padding: 20px; text-align: center; }
            .content { padding: 20px; }
            .button { 
                display: inline-block; 
                padding: 12px 24px; 
                background-color: #007bff; 
                color: white; 
                text-decoration: none; 
                border-radius: 4px; 
                margin: 20px 0;
            }
            .code { 
                font-family: monospace; 
                font-size: 24px; 
                font-weight: bold; 
                color: #007bff; 
                background-color: #f8f9fa; 
                padding: 10px; 
                text-align: center; 
                border-radius: 4px;
                margin: 20px 0;
            }
            .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{{ app_name }}</h1>
                <h2>Email Verification Required</h2>
            </div>
            <div class="content">
                <p>Hello {{ username }},</p>
                <p>You need to verify your email address to complete your 2FA setup.</p>
                
                <p><strong>Your verification code is:</strong></p>
                <div class="code">{{ verification_code }}</div>
                
                <p>Or click the button below to verify automatically:</p>
                <a href="{{ verification_link }}" class="button">Verify Email Address</a>
                
                <p><strong>Important:</strong></p>
                <ul>
                    <li>This code will expire in {{ expires_in }} minutes</li>
                    <li>If you didn't request this verification, please ignore this email</li>
                    <li>Never share this code with anyone</li>
                </ul>
            </div>
            <div class="footer">
                <p>This is an automated message from {{ app_name }}. Please do not reply to this email.</p>
                <p>Generated at {{ timestamp }}</p>
            </div>
        </div>
    </body>
    </html>
    """

    PASSWORD_RESET = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Password Reset - {{ app_name }}</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background-color: #f8f9fa; padding: 20px; text-align: center; }
            .content { padding: 20px; }
            .button { 
                display: inline-block; 
                padding: 12px 24px; 
                background-color: #dc3545; 
                color: white; 
                text-decoration: none; 
                border-radius: 4px; 
                margin: 20px 0;
            }
            .warning { background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 4px; margin: 20px 0; }
            .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{{ app_name }}</h1>
                <h2>Password Reset Request</h2>
            </div>
            <div class="content">
                <p>Hello {{ username }},</p>
                <p>We received a request to reset your password. Click the button below to set a new password:</p>
                
                <a href="{{ reset_link }}" class="button">Reset Password</a>
                
                <div class="warning">
                    <p><strong>Security Notice:</strong></p>
                    <ul>
                        <li>This link will expire in {{ expires_in }} hour(s)</li>
                        <li>If you didn't request this reset, please ignore this email</li>
                        <li>Request made from IP: {{ ip_address }}</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>This is an automated message from {{ app_name }}. Please do not reply to this email.</p>
                <p>Generated at {{ timestamp }}</p>
            </div>
        </div>
    </body>
    </html>
    """

    @staticmethod
    def get_template(template_type: str) -> Template:
        """Get Jinja2 template by type"""
        templates = {
            "email_verification": EmailTemplates.EMAIL_VERIFICATION,
            "password_reset": EmailTemplates.PASSWORD_RESET,
        }

        template_content = templates.get(template_type)
        if not template_content:
            raise ValueError(f"Unknown template type: {template_type}")

        return Template(template_content)


class MailgunEmailService:
    """Mailgun API email service"""

    def __init__(self):
        self.api_key = MAILGUN_API_KEY
        self.domain = MAILGUN_DOMAIN
        self.api_url = f"{MAILGUN_API_URL}/{self.domain}"

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send email using Mailgun API"""
        if not self.api_key or not self.domain:
            logger.error("Mailgun API key or domain not configured")
            return False

        data = {
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to": to_email,
            "subject": subject,
            "html": html_content,
        }

        if text_content:
            data["text"] = text_content

        auth = aiohttp.BasicAuth("api", self.api_key)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/messages", auth=auth, data=data
                ) as response:
                    if response.status == 200:
                        logger.info(f"Email sent successfully to {to_email}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Mailgun API error: {response.status} - {error_text}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Error sending email via Mailgun: {e}")
            return False


class SMTPEmailService:
    """SMTP email service (fallback)"""

    def __init__(self):
        self.host = SMTP_HOST
        self.port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.use_tls = SMTP_USE_TLS

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send email using SMTP"""
        if not self.username or not self.password:
            logger.error("SMTP credentials not configured")
            return False

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        message["To"] = to_email

        if text_content:
            text_part = MIMEText(text_content, "plain")
            message.attach(text_part)

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                start_tls=self.use_tls,
                username=self.username,
                password=self.password,
            )
            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error sending email via SMTP: {e}")
            return False


class EmailService:
    """Main email service that uses configured provider"""

    def __init__(self):
        if EMAIL_PROVIDER.lower() == "mailgun":
            self.provider = MailgunEmailService()
        else:
            self.provider = SMTPEmailService()

    async def send_email_verification(
        self,
        to_email: str,
        username: str,
        verification_code: str,
        verification_token: str,
        expires_in_minutes: int = 15,
    ) -> bool:
        """Send email verification message"""
        template = EmailTemplates.get_template("email_verification")

        verification_link = (
            f"{FRONTEND_URL}/auth/verify-email?token={verification_token}"
        )

        html_content = template.render(
            app_name="dYdX Trading Bot",
            username=username,
            verification_code=verification_code,
            verification_link=verification_link,
            expires_in=expires_in_minutes,
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        subject = "Email Verification Required - dYdX Trading Bot"

        return await self.provider.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=f"Your verification code is: {verification_code}",
        )

    async def send_password_reset(
        self,
        to_email: str,
        username: str,
        reset_token: str,
        ip_address: str,
        expires_in_hours: int = 1,
    ) -> bool:
        """Send password reset email"""
        template = EmailTemplates.get_template("password_reset")

        reset_link = f"{FRONTEND_URL}/auth/reset-password?token={reset_token}"

        html_content = template.render(
            app_name="dYdX Trading Bot",
            username=username,
            reset_link=reset_link,
            expires_in=expires_in_hours,
            ip_address=ip_address,
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        subject = "Password Reset Request - dYdX Trading Bot"

        return await self.provider.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=f"Password reset link: {reset_link}",
        )

    async def send_test_email(self, to_email: str) -> bool:
        """Send test email to verify configuration"""
        html_content = """
        <html>
        <body>
            <h2>Email Configuration Test</h2>
            <p>This is a test email from dYdX Trading Bot.</p>
            <p>If you received this, your email configuration is working correctly!</p>
            <p>Sent at: {timestamp}</p>
        </body>
        </html>
        """.format(timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))

        return await self.provider.send_email(
            to_email=to_email,
            subject="Email Configuration Test - dYdX Trading Bot",
            html_content=html_content,
            text_content="This is a test email from dYdX Trading Bot.",
        )


# Global email service instance
email_service = EmailService()


async def send_email_verification(
    to_email: str,
    username: str,
    verification_code: str,
    verification_token: str,
    expires_in_minutes: int = 15,
) -> bool:
    """Convenience function to send email verification"""
    return await email_service.send_email_verification(
        to_email, username, verification_code, verification_token, expires_in_minutes
    )


async def send_password_reset_email(
    to_email: str,
    username: str,
    reset_token: str,
    ip_address: str,
    expires_in_hours: int = 1,
) -> bool:
    """Convenience function to send password reset email"""
    return await email_service.send_password_reset(
        to_email, username, reset_token, ip_address, expires_in_hours
    )


if __name__ == "__main__":
    # Test email service
    async def test_email():
        print("Testing email service...")

        # Test email configuration
        test_email = "test@example.com"
        result = await email_service.send_test_email(test_email)

        if result:
            print("✅ Email test successful")
        else:
            print("❌ Email test failed")

        # Test verification email
        result = await send_email_verification(
            to_email=test_email,
            username="testuser",
            verification_code="123456",
            verification_token="test-token-123",
        )

        if result:
            print("✅ Verification email test successful")
        else:
            print("❌ Verification email test failed")

    asyncio.run(test_email())
