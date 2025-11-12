"""
Email Bridge for Leave System
Handles email receipt and sending

NOTE: This is a placeholder implementation
In production, integrate with actual email service (IMAP/SMTP, Gmail API, etc.)
"""

import imaplib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import message_from_bytes
from typing import Dict, Any, Optional, List
from datetime import datetime


class EmailBridge:
    """
    Email communication bridge for the leave system
    Monitors inbox and sends responses
    """

    def __init__(
        self,
        imap_server: str = "imap.gmail.com",
        smtp_server: str = "smtp.gmail.com",
        email_address: str = "",
        password: str = "",
        port_imap: int = 993,
        port_smtp: int = 587
    ):
        """
        Initialize email bridge

        Args:
            imap_server: IMAP server address
            smtp_server: SMTP server address
            email_address: School email address
            password: Email password (use app-specific password for Gmail)
            port_imap: IMAP port (default 993 for SSL)
            port_smtp: SMTP port (default 587 for TLS)
        """
        self.imap_server = imap_server
        self.smtp_server = smtp_server
        self.email_address = email_address
        self.password = password
        self.port_imap = port_imap
        self.port_smtp = port_smtp

    def connect_imap(self) -> Optional[imaplib.IMAP4_SSL]:
        """
        Connect to IMAP server

        Returns:
            IMAP connection or None on failure
        """
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.port_imap)
            mail.login(self.email_address, self.password)
            return mail
        except Exception as e:
            print(f"[EMAIL] Failed to connect to IMAP: {e}")
            return None

    def fetch_unread_emails(self) -> List[Dict[str, Any]]:
        """
        Fetch unread emails from inbox

        Returns:
            List of email dictionaries with sender, subject, body, date
        """
        mail = self.connect_imap()
        if not mail:
            return []

        try:
            mail.select('inbox')

            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')

            if status != 'OK':
                return []

            email_ids = messages[0].split()
            emails = []

            for email_id in email_ids:
                # Fetch email data
                status, msg_data = mail.fetch(email_id, '(RFC822)')

                if status != 'OK':
                    continue

                # Parse email
                msg = message_from_bytes(msg_data[0][1])

                # Extract relevant fields
                from_addr = msg.get('From', '')
                subject = msg.get('Subject', '')
                date_str = msg.get('Date', '')

                # Extract sender email from "Name <email@domain.com>" format
                if '<' in from_addr:
                    sender_email = from_addr.split('<')[1].split('>')[0]
                else:
                    sender_email = from_addr

                # Extract body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                else:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

                emails.append({
                    'id': email_id.decode(),
                    'from': sender_email,
                    'subject': subject,
                    'body': body,
                    'date': date_str,
                    'timestamp': datetime.now()
                })

            mail.close()
            mail.logout()

            return emails

        except Exception as e:
            print(f"[EMAIL] Error fetching emails: {e}")
            try:
                mail.close()
                mail.logout()
            except:
                pass
            return []

    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Send an email

        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            reply_to: Optional reply-to address

        Returns:
            True if sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_address
            msg['To'] = to_address
            msg['Subject'] = subject

            if reply_to:
                msg['Reply-To'] = reply_to

            # Add body
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)

            # Send via SMTP
            server = smtplib.SMTP(self.smtp_server, self.port_smtp)
            server.starttls()
            server.login(self.email_address, self.password)
            server.send_message(msg)
            server.quit()

            print(f"[EMAIL] Sent to {to_address}")
            return True

        except Exception as e:
            print(f"[EMAIL] Failed to send email: {e}")
            return False

    def mark_as_read(self, email_id: str) -> bool:
        """
        Mark an email as read

        Args:
            email_id: Email ID to mark

        Returns:
            True if successful
        """
        mail = self.connect_imap()
        if not mail:
            return False

        try:
            mail.select('inbox')
            mail.store(email_id.encode(), '+FLAGS', '\\Seen')
            mail.close()
            mail.logout()
            return True
        except Exception as e:
            print(f"[EMAIL] Failed to mark as read: {e}")
            return False


class EmailLeaveHandler:
    """
    Handles leave requests received via email
    Integrates with LeaveProcessor
    """

    def __init__(self, email_bridge: EmailBridge):
        """
        Initialize email leave handler

        Args:
            email_bridge: Configured EmailBridge instance
        """
        self.email_bridge = email_bridge

    def process_incoming_emails(self):
        """
        Main loop: fetch and process unread emails
        """
        from ..processors.leave_processor import LeaveProcessor

        processor = LeaveProcessor()

        print("[EMAIL HANDLER] Checking for new emails...")

        emails = self.email_bridge.fetch_unread_emails()

        if not emails:
            print("[EMAIL HANDLER] No new emails")
            return

        print(f"[EMAIL HANDLER] Found {len(emails)} unread email(s)")

        for email_data in emails:
            print(f"\n[EMAIL HANDLER] Processing email from {email_data['from']}")
            print(f"                Subject: {email_data['subject']}")

            # Determine if it's a parent or housemaster request
            is_housemaster = 'hm.' in email_data['from'] or 'housemaster' in email_data['subject'].lower()

            if is_housemaster:
                # Process housemaster request
                result = processor.process_housemaster_request(
                    message_text=email_data['body'],
                    sender_identifier=email_data['from'],
                    channel='email'
                )
            else:
                # Process parent leave request
                result = processor.process_parent_request(
                    message_text=email_data['body'],
                    sender_identifier=email_data['from'],
                    channel='email'
                )

            # Send response
            response_subject = self._generate_subject(result, email_data['subject'])
            self.email_bridge.send_email(
                to_address=email_data['from'],
                subject=response_subject,
                body=result['message']
            )

            # Mark as read
            self.email_bridge.mark_as_read(email_data['id'])

            print(f"[EMAIL HANDLER] Response sent: {result['status']}")

    def _generate_subject(self, result: Dict[str, Any], original_subject: str) -> str:
        """Generate appropriate response subject"""

        if result['status'] == 'approved':
            return f"Re: {original_subject} - Leave APPROVED"
        elif result['status'] == 'rejected':
            return f"Re: {original_subject} - Leave DECLINED"
        elif result['status'] == 'special_pending':
            return f"Re: {original_subject} - Special Leave Review Required"
        else:
            return f"Re: {original_subject}"


# ==================== Placeholder Email Service ====================

class PlaceholderEmailBridge(EmailBridge):
    """
    Placeholder email bridge for testing without actual email server
    Simulates email receipt and sending
    """

    def __init__(self):
        """Initialize placeholder (no credentials needed)"""
        self.mock_inbox = []
        self.sent_emails = []

    def fetch_unread_emails(self) -> List[Dict[str, Any]]:
        """Return mock emails"""
        # For testing, return empty
        return self.mock_inbox

    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None
    ) -> bool:
        """Simulate sending email"""
        print(f"\n{'='*60}")
        print(f"[EMAIL SENT]")
        print(f"To: {to_address}")
        print(f"Subject: {subject}")
        print(f"{'='*60}")
        print(body)
        print(f"{'='*60}\n")

        self.sent_emails.append({
            'to': to_address,
            'subject': subject,
            'body': body,
            'timestamp': datetime.now()
        })

        return True

    def add_mock_email(
        self,
        from_address: str,
        subject: str,
        body: str
    ):
        """Add a mock email to inbox for testing"""
        self.mock_inbox.append({
            'id': str(len(self.mock_inbox) + 1),
            'from': from_address,
            'subject': subject,
            'body': body,
            'date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S'),
            'timestamp': datetime.now()
        })
