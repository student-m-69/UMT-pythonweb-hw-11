"""Sending the address-verification email.

When SMTP is not configured (``MAIL_SERVER`` empty) the verification link is
written to the application log instead, so the whole flow stays testable
locally without a mailbox.
"""

import logging

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors

from src.conf.config import settings
from src.services import auth as auth_service

logger = logging.getLogger("uvicorn.error")

EMAIL_TEMPLATE = """\
<html>
  <body>
    <p>Hello {username},</p>
    <p>Thank you for registering in Contacts API. Please confirm your email
       address by opening the link below:</p>
    <p><a href="{link}">Confirm email</a></p>
    <p>If you did not register, simply ignore this message.</p>
  </body>
</html>
"""


async def send_verification_email(email: str, username: str, host: str) -> None:
    """Email the confirmation link for ``email``; ``host`` is the API base URL."""
    token = auth_service.create_email_token(email)
    link = f"{host}api/auth/confirmed_email/{token}"

    if not settings.mail_server:
        logger.warning(
            "SMTP is not configured; verification link for %s: %s", email, link
        )
        return

    conf = ConnectionConfig(
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=settings.mail_password,
        MAIL_FROM=settings.mail_from,
        MAIL_PORT=settings.mail_port,
        MAIL_SERVER=settings.mail_server,
        MAIL_FROM_NAME=settings.mail_from_name,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    message = MessageSchema(
        subject="Confirm your email — Contacts API",
        recipients=[email],
        body=EMAIL_TEMPLATE.format(username=username, link=link),
        subtype=MessageType.html,
    )

    try:
        await FastMail(conf).send_message(message)
    except ConnectionErrors:
        # The user can always ask for a re-send via /api/auth/request_email.
        logger.exception("Failed to send the verification email to %s", email)
