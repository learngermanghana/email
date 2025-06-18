# utils/email_utils.py

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Attachment,
    FileContent,
    FileName,
    FileType,
    Disposition,
)

def send_emails(
    api_key,
    sender_email,
    recipients,
    subject,
    message,
    attachment_bytes=None,
    attachment_filename=None,
    attachment_type=None
):
    sent = 0
    failed = []
    for email in recipients:
        try:
            msg = Mail(
                from_email=sender_email,
                to_emails=email,
                subject=subject,
                html_content=message.replace("\n", "<br>")
            )
            if attachment_bytes and attachment_filename and attachment_type:
                msg.attachment = Attachment(
                    FileContent(attachment_bytes),
                    FileName(attachment_filename),
                    FileType(attachment_type),
                    Disposition("attachment")
                )
            client = SendGridAPIClient(api_key)
            client.send(msg)
            sent += 1
        except Exception as e:
            failed.append((email, str(e)))
    return sent, failed
