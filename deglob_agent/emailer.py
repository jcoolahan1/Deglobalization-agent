"""Send the digest over SMTP. All credentials come from environment variables:

  SMTP_HOST      e.g. smtp.gmail.com
  SMTP_PORT      587 (STARTTLS) or 465 (implicit TLS); default 587
  SMTP_USERNAME  login user (for Gmail, your address; use an App Password);
                 leave unset for relays that do not require authentication
  SMTP_PASSWORD  login password / app password
  SMTP_STARTTLS  "false" to disable STARTTLS on non-465 ports (default true)
  DIGEST_FROM    From address (defaults to SMTP_USERNAME)
  DIGEST_TO      recipient address(es), comma-separated
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(subject: str, html_body: str, text_body: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    use_starttls = os.environ.get("SMTP_STARTTLS", "true").lower() != "false"
    sender = os.environ.get("DIGEST_FROM") or username
    recipients = [addr.strip() for addr in os.environ["DIGEST_TO"].split(",") if addr.strip()]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=60) as server:
            if username:
                server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as server:
            if use_starttls:
                server.starttls(context=context)
            if username:
                server.login(username, password)
            server.send_message(msg)
