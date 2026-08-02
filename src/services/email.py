"""Sending the verification and password-reset emails.

When SMTP is not configured (``MAIL_SERVER`` empty) the link is written to
the application log instead, so both flows stay testable locally without a
mailbox.
"""

import logging

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors

from src.conf.config import settings
from src.services import auth as auth_service

logger = logging.getLogger("uvicorn.error")

VERIFICATION_TEMPLATE = """\
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

RESET_TEMPLATE = """\
<html>
  <body>
    <p>Hello {username},</p>
    <p>We received a request to reset your Contacts API password. Send your
       new password with a POST request to the address below within one week:</p>
    <p><a href="{link}">{link}</a></p>
    <p>If you did not ask for a reset, simply ignore this message — the
       password stays unchanged.</p>
  </body>
</html>
"""


async def _send(subject: str, recipient: str, html: str, link: str) -> None:
    """Deliver ``html`` to ``recipient``, or log ``link`` when SMTP is absent.

    Args:
        subject: The subject line.
        recipient: The destination address.
        html: The rendered message body.
        link: The action link, logged verbatim when no mail server is set.
    """
    if not settings.mail_server:
        logger.warning(
            "SMTP is not configured; link for %s: %s", recipient, link
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
        subject=subject, recipients=[recipient], body=html, subtype=MessageType.html
    )

    try:
        await FastMail(conf).send_message(message)
    except ConnectionErrors:
        # The user can always ask for a re-send.
        logger.exception("Failed to send '%s' to %s", subject, recipient)


async def send_verification_email(email: str, username: str, host: str) -> None:
    """Email the address-confirmation link.

    Args:
        email: The address to verify.
        username: The name used in the greeting.
        host: The API base URL the link should point at.
    """
    token = auth_service.create_email_token(email)
    link = f"{host}api/auth/confirmed_email/{token}"
    await _send(
        "Confirm your email — Contacts API",
        email,
        VERIFICATION_TEMPLATE.format(username=username, link=link),
        link,
    )


async def send_password_reset_email(email: str, username: str, host: str) -> None:
    """Email the password-reset link.

    Args:
        email: The address that asked for the reset.
        username: The name used in the greeting.
        host: The API base URL the link should point at.
    """
    token = auth_service.create_email_token(email, scope="password_reset")
    link = f"{host}api/auth/reset_password/{token}"
    await _send(
        "Reset your password — Contacts API",
        email,
        RESET_TEMPLATE.format(username=username, link=link),
        link,
    )
