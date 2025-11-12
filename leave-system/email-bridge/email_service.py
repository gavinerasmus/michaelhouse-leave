#!/usr/bin/env python3
"""
Email Monitoring Service for Michaelhouse Leave System
Monitors IMAP inbox for leave requests and sends responses via SMTP
"""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import time
import os
import sys
from pathlib import Path
from datetime import datetime
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from processors.leave_processor import LeaveProcessor
from tools.database_tools import DatabaseTools

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/leave-email-service.log' if os.path.exists('/var/log') else 'email-service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('email_service')


class EmailLeaveService:
    """Email monitoring service for leave requests"""

    def __init__(self):
        """Initialize email service with configuration"""
        # Email configuration
        self.imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
        self.imap_port = int(os.getenv('IMAP_PORT', '993'))
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_address = os.getenv('LEAVE_EMAIL')
        self.email_password = os.getenv('LEAVE_EMAIL_PASSWORD')

        # Monitoring configuration
        self.check_interval = int(os.getenv('EMAIL_CHECK_INTERVAL', '60'))  # seconds
        self.mark_as_read = os.getenv('EMAIL_MARK_AS_READ', 'true').lower() == 'true'

        # Initialize leave processor
        try:
            logger.info("Initializing leave processor with database tools...")
            tools = DatabaseTools()
            self.processor = LeaveProcessor()
            self.processor.tools = tools
            logger.info("✓ Database tools initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize database tools: {e}")
            logger.info("Using placeholder tools")
            self.processor = LeaveProcessor()

        # Validate configuration
        if not self.email_address or not self.email_password:
            raise ValueError("LEAVE_EMAIL and LEAVE_EMAIL_PASSWORD must be set in environment")

    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            logger.info(f"✓ Connected to IMAP server: {self.imap_server}")
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to IMAP: {e}")
            raise

    def connect_smtp(self) -> smtplib.SMTP:
        """Connect to SMTP server"""
        try:
            smtp = smtplib.SMTP(self.smtp_server, self.smtp_port)
            smtp.starttls()
            smtp.login(self.email_address, self.email_password)
            logger.info(f"✓ Connected to SMTP server: {self.smtp_server}")
            return smtp
        except Exception as e:
            logger.error(f"Failed to connect to SMTP: {e}")
            raise

    def decode_email_subject(self, subject: str) -> str:
        """Decode email subject from various encodings"""
        decoded_parts = decode_header(subject)
        decoded_subject = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    decoded_subject += part.decode(encoding or 'utf-8')
                except:
                    decoded_subject += part.decode('utf-8', errors='ignore')
            else:
                decoded_subject += part

        return decoded_subject

    def extract_email_body(self, msg: email.message.Message) -> str:
        """Extract plain text body from email message"""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                # Get plain text content
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        pass
        else:
            # Simple message
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(msg.get_payload())

        return body.strip()

    def send_email_response(self, to_address: str, subject: str, body: str) -> bool:
        """Send email response"""
        try:
            smtp = self.connect_smtp()

            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to_address
            msg['Subject'] = f"Re: {subject}" if not subject.startswith('Re:') else subject

            msg.attach(MIMEText(body, 'plain'))

            smtp.send_message(msg)
            smtp.quit()

            logger.info(f"✓ Email sent to {to_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_address}: {e}")
            return False

    def process_email(self, mail: imaplib.IMAP4_SSL, email_id: bytes) -> None:
        """Process a single email"""
        try:
            # Fetch email
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                logger.warning(f"Failed to fetch email {email_id}")
                return

            # Parse email
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Extract sender
            from_header = msg.get('From', '')
            sender_email = email.utils.parseaddr(from_header)[1]

            # Extract subject
            subject = self.decode_email_subject(msg.get('Subject', 'No Subject'))

            # Extract body
            body = self.extract_email_body(msg)

            logger.info(f"Processing email from {sender_email}: {subject[:50]}...")

            # Determine if this is a leave request or housemaster query
            is_housemaster = (
                'hm.' in sender_email.lower() or
                'housemaster' in sender_email.lower() or
                'balance' in subject.lower() or
                'balance' in body.lower() or
                'cancel' in body.lower() or
                'restrict' in body.lower()
            )

            # Process request
            if is_housemaster:
                logger.info("Processing as housemaster request")
                result = self.processor.process_housemaster_request(
                    message_text=body,
                    sender_identifier=sender_email,
                    channel='email'
                )
            else:
                logger.info("Processing as parent request")
                result = self.processor.process_parent_request(
                    message_text=body,
                    sender_identifier=sender_email,
                    channel='email'
                )

            # Send response
            response_sent = self.send_email_response(
                to_address=sender_email,
                subject=subject,
                body=result['message']
            )

            if response_sent:
                logger.info(f"✓ Processed email: status={result['status']}")

                # Mark as read if configured
                if self.mark_as_read:
                    mail.store(email_id, '+FLAGS', '\\Seen')
            else:
                logger.error("Failed to send response email")

        except Exception as e:
            logger.error(f"Error processing email {email_id}: {e}", exc_info=True)

    def check_inbox(self) -> int:
        """Check inbox for new emails and process them"""
        try:
            mail = self.connect_imap()

            # Select inbox
            mail.select('INBOX')

            # Search for unseen emails
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                logger.warning("Failed to search for emails")
                mail.logout()
                return 0

            email_ids = messages[0].split()

            if not email_ids:
                logger.debug("No new emails")
                mail.logout()
                return 0

            logger.info(f"Found {len(email_ids)} new email(s)")

            # Process each email
            for email_id in email_ids:
                self.process_email(mail, email_id)

            mail.logout()
            return len(email_ids)

        except Exception as e:
            logger.error(f"Error checking inbox: {e}", exc_info=True)
            return 0

    def run(self) -> None:
        """Run email monitoring service"""
        logger.info("=" * 70)
        logger.info("Michaelhouse Leave System - Email Monitoring Service")
        logger.info("=" * 70)
        logger.info(f"IMAP Server: {self.imap_server}")
        logger.info(f"SMTP Server: {self.smtp_server}")
        logger.info(f"Email: {self.email_address}")
        logger.info(f"Check Interval: {self.check_interval} seconds")
        logger.info(f"Mark as Read: {self.mark_as_read}")
        logger.info("=" * 70)
        logger.info("Service started. Monitoring inbox...")

        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:
                processed = self.check_inbox()

                if processed > 0:
                    logger.info(f"Processed {processed} email(s)")

                # Reset error counter on success
                consecutive_errors = 0

                # Wait before next check
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                logger.info("\nService stopped by user")
                break

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in main loop ({consecutive_errors}/{max_consecutive_errors}): {e}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.critical("Too many consecutive errors. Stopping service.")
                    break

                # Wait before retry (exponential backoff)
                wait_time = min(60, self.check_interval * (2 ** consecutive_errors))
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)


def main():
    """Main entry point"""
    try:
        service = EmailLeaveService()
        service.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please set LEAVE_EMAIL and LEAVE_EMAIL_PASSWORD in .env file")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
