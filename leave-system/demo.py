#!/usr/bin/env python3
"""
Demo script for Michaelhouse Leave System
Shows how the system processes leave requests from both channels
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from processors.leave_processor import LeaveProcessor
try:
    from email_bridge.email_handler import PlaceholderEmailBridge, EmailLeaveHandler
except ImportError:
    # Email bridge optional for core demo
    PlaceholderEmailBridge = None
    EmailLeaveHandler = None


def demo_whatsapp_request():
    """Demonstrate WhatsApp leave request processing"""

    print("\n" + "="*70)
    print("DEMO 1: WhatsApp Leave Request (Parent)")
    print("="*70)

    processor = LeaveProcessor()

    # Simulate a WhatsApp message from a parent
    message = """Hi, I'd like to request overnight leave for James this Saturday 8th February.
Please let me know if this is approved."""

    sender_phone = "27603174174"  # Mock parent phone

    print(f"\n[WHATSAPP] Incoming message from {sender_phone}")
    print(f"Message: {message}")

    result = processor.process_parent_request(
        message_text=message,
        sender_identifier=sender_phone,
        channel='whatsapp'
    )

    print(f"\n[SYSTEM] Status: {result['status']}")
    print(f"\n[WHATSAPP] Response sent:")
    print("-" * 70)
    print(result['message'])
    print("-" * 70)


def demo_email_request():
    """Demonstrate Email leave request processing"""

    print("\n" + "="*70)
    print("DEMO 2: Email Leave Request (Parent)")
    print("="*70)

    processor = LeaveProcessor()

    # Simulate an email from a parent
    email_body = """Dear Leave System,

I am writing to request leave for my son Michael Doe (Admin No: 67890) for Friday Supper on 14th February 2025.

Kind regards,
Jane Doe"""

    sender_email = "jane.doe@example.com"  # Mock parent email

    print(f"\n[EMAIL] Incoming email from {sender_email}")
    print(f"Body: {email_body}")

    result = processor.process_parent_request(
        message_text=email_body,
        sender_identifier=sender_email,
        channel='email'
    )

    print(f"\n[SYSTEM] Status: {result['status']}")
    print(f"\n[EMAIL] Response sent:")
    print("-" * 70)
    print(result['message'])
    print("-" * 70)


def demo_closed_weekend():
    """Demonstrate closed weekend handling (E/D block)"""

    print("\n" + "="*70)
    print("DEMO 3: Closed Weekend - Special Leave Required (E Block)")
    print("="*70)

    processor = LeaveProcessor()

    # Request for first weekend of term (closed for E block)
    message = """Please approve overnight leave for Michael (67890) on 18th January 2025.
This is the first weekend of term."""

    sender_email = "jane.doe@example.com"

    print(f"\n[EMAIL] Incoming email from {sender_email}")
    print(f"Body: {message}")

    result = processor.process_parent_request(
        message_text=message,
        sender_identifier=sender_email,
        channel='email'
    )

    print(f"\n[SYSTEM] Status: {result['status']}")
    print(f"\n[EMAIL] Response sent:")
    print("-" * 70)
    print(result['message'])
    print("-" * 70)


def demo_insufficient_balance():
    """Demonstrate insufficient balance rejection"""

    print("\n" + "="*70)
    print("DEMO 4: Insufficient Balance - Rejection")
    print("="*70)

    processor = LeaveProcessor()

    # Note: Mock data shows student 67890 has 2 overnight leaves
    # We'll simulate they've used them all

    message = """Hi, can James (12345) please go out overnight this Saturday?"""

    sender_phone = "27603174174"

    print(f"\n[WHATSAPP] Incoming message from {sender_phone}")
    print(f"Message: {message}")

    # For demo, we'd need to modify mock data, but showing the flow
    result = processor.process_parent_request(
        message_text=message,
        sender_identifier=sender_phone,
        channel='whatsapp'
    )

    print(f"\n[SYSTEM] Status: {result['status']}")
    print(f"\n[WHATSAPP] Response sent:")
    print("-" * 70)
    print(result['message'])
    print("-" * 70)


def demo_housemaster_query():
    """Demonstrate Housemaster balance query"""

    print("\n" + "="*70)
    print("DEMO 5: Housemaster Balance Query")
    print("="*70)

    processor = LeaveProcessor()

    message = "What is the leave balance for student 12345?"
    sender_email = "hm.finningley@michaelhouse.org"

    print(f"\n[EMAIL] Incoming email from {sender_email}")
    print(f"Body: {message}")

    result = processor.process_housemaster_request(
        message_text=message,
        sender_identifier=sender_email,
        channel='email'
    )

    print(f"\n[SYSTEM] Status: {result['status']}")
    print(f"\n[EMAIL] Response sent:")
    print("-" * 70)
    print(result['message'])
    print("-" * 70)


def demo_housemaster_cancellation():
    """Demonstrate Housemaster leave cancellation"""

    print("\n" + "="*70)
    print("DEMO 6: Housemaster Leave Cancellation")
    print("="*70)

    processor = LeaveProcessor()

    message = "Please cancel the leave for student 12345 because of academic concerns."
    sender_email = "hm.finningley@michaelhouse.org"

    print(f"\n[EMAIL] Incoming email from {sender_email}")
    print(f"Body: {message}")

    result = processor.process_housemaster_request(
        message_text=message,
        sender_identifier=sender_email,
        channel='email'
    )

    print(f"\n[SYSTEM] Status: {result['status']}")
    print(f"\n[EMAIL] Response sent:")
    print("-" * 70)
    print(result['message'])
    print("-" * 70)


def demo_day_leave():
    """Demonstrate unlimited day leave approval"""

    print("\n" + "="*70)
    print("DEMO 7: Day Leave - Automatic Approval (Unlimited)")
    print("="*70)

    processor = LeaveProcessor()

    message = "Can James have day leave this Sunday to visit family?"
    sender_phone = "27603174174"

    print(f"\n[WHATSAPP] Incoming message from {sender_phone}")
    print(f"Message: {message}")

    result = processor.process_parent_request(
        message_text=message,
        sender_identifier=sender_phone,
        channel='whatsapp'
    )

    print(f"\n[SYSTEM] Status: {result['status']}")
    print(f"\n[WHATSAPP] Response sent:")
    print("-" * 70)
    print(result['message'])
    print("-" * 70)


def main():
    """Run all demos"""

    print("\n" + "="*70)
    print(" MICHAELHOUSE LEAVE SYSTEM - DEMONSTRATION")
    print("="*70)
    print("\nThis demo shows how the system processes various leave requests")
    print("from both WhatsApp and Email channels, using placeholder tools.\n")

    demos = [
        ("WhatsApp - Overnight Leave", demo_whatsapp_request),
        ("Email - Friday Supper Leave", demo_email_request),
        ("Closed Weekend - Special Leave", demo_closed_weekend),
        ("Insufficient Balance", demo_insufficient_balance),
        ("Housemaster Query", demo_housemaster_query),
        ("Housemaster Cancellation", demo_housemaster_cancellation),
        ("Day Leave - Auto Approval", demo_day_leave),
    ]

    for i, (name, demo_func) in enumerate(demos, 1):
        try:
            demo_func()
            input(f"\n[Press Enter to continue to Demo {i+1}/{len(demos)}...]")
        except KeyboardInterrupt:
            print("\n\nDemo interrupted by user.")
            break
        except Exception as e:
            print(f"\n[ERROR] Demo failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print(" DEMO COMPLETE")
    print("="*70)
    print("\nAll placeholder tools have been demonstrated.")
    print("Ready for integration with actual database and email services.\n")


if __name__ == "__main__":
    main()
