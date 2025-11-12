"""
Leave Request Processor
Implements the core leave approval workflow per FR1-FR6
"""

from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.leave_models import (
    LeaveType, LeaveStatus, LeaveRequest, StudentInfo,
    ParentInfo, HousemasterInfo
)
from tools.placeholder_tools import LeaveSystemTools


class LeaveProcessor:
    """
    Core leave processing engine
    Implements the sequential decision protocol from requirements
    """

    def __init__(self):
        self.tools = LeaveSystemTools()

    def process_parent_request(
        self,
        message_text: str,
        sender_identifier: str,
        channel: str  # 'whatsapp' or 'email'
    ) -> Dict[str, Any]:
        """
        Main entry point for processing leave requests (FR1-FR6)

        Args:
            message_text: Unstructured request text
            sender_identifier: Phone number or email address
            channel: Communication channel

        Returns:
            Processing result with status and response message
        """

        # FR2: Authentication and Student Linkage
        auth_result = self._authenticate_parent(sender_identifier, channel)
        if not auth_result['authenticated']:
            return {
                'status': 'rejected',
                'reason': 'authentication_failed',
                'message': auth_result['message']
            }

        parent_info = auth_result['parent_info']

        # Parse the request
        from processors.leave_parser import LeaveRequestParser
        parser = LeaveRequestParser()
        parsed_data = parser.parse_request(message_text)

        if not parsed_data['student_identifier']:
            return {
                'status': 'error',
                'reason': 'parse_failed',
                'message': "I couldn't identify which student this request is for. Please include the student's name or admin number."
            }

        # FR2.3: Student/Parent Linkage
        student_record = self.tools.tool_student_parent_linkage(
            parent_info.auth_id,
            parsed_data['student_identifier']
        )

        if not student_record:
            return {
                'status': 'rejected',
                'reason': 'student_linkage_failed',
                'message': f"I couldn't find a student matching '{parsed_data['student_identifier']}' linked to your account. Please check the name or admin number and try again."
            }

        # Build student info
        student_info = StudentInfo(
            admin_number=student_record['adminNumber'],
            first_name=student_record['firstName'],
            last_name=student_record['lastName'],
            house=student_record['house'],
            block=student_record['block'],
            overnight_balance=student_record['balances']['overnight'],
            friday_supper_balance=student_record['balances']['fridaySupper']
        )

        # Create leave request object
        leave_request = LeaveRequest(
            student=student_info,
            parent=parent_info,
            leave_type=parsed_data['leave_type'],
            start_date=parsed_data['start_date'],
            end_date=parsed_data['end_date']
        )

        # FR3-FR5: Process the leave request
        return self._process_leave_eligibility(leave_request)

    def _authenticate_parent(
        self,
        identifier: str,
        channel: str
    ) -> Dict[str, Any]:
        """
        FR2: Authenticate parent via phone or email

        Returns:
            Dict with 'authenticated' bool and 'parent_info' or 'message'
        """

        parent_auth_id = None

        if channel == 'whatsapp':
            # FR2.1: WhatsApp authentication
            parent_auth_id = self.tools.tool_parent_phone_check(identifier)
        elif channel == 'email':
            # FR2.2: Email authentication
            parent_auth_id = self.tools.tool_parent_email_check(identifier)

        if not parent_auth_id:
            return {
                'authenticated': False,
                'message': "I couldn't verify your identity. Please ensure you're using the registered contact details on file."
            }

        parent_info = ParentInfo(
            auth_id=parent_auth_id,
            phone=identifier if channel == 'whatsapp' else None,
            email=identifier if channel == 'email' else None,
            channel=channel
        )

        return {
            'authenticated': True,
            'parent_info': parent_info
        }

    def _process_leave_eligibility(self, leave_request: LeaveRequest) -> Dict[str, Any]:
        """
        FR3-FR5: Check eligibility and process leave

        Sequential checks:
        1. Date validity (FR3.2)
        2. Closed weekend check (FR3.3)
        3. Balance check (FR3.4, FR3.5)
        4. Restriction check (FR3.7)
        5. Final approval or special leave routing (FR4)
        """

        # Check if dates are provided
        if not leave_request.start_date or not leave_request.end_date:
            return {
                'status': 'error',
                'reason': 'missing_dates',
                'message': "I couldn't determine the dates for this leave request. Please specify the start and end dates clearly."
            }

        # FR3.2: Date Validity Check
        date_validity = self.tools.tool_date_validity_check(
            leave_request.student.block,
            leave_request.start_date,
            leave_request.end_date
        )

        if not date_validity['isValid']:
            # Check if it's a closed weekend for E/D block
            if "closed weekend" in date_validity['reason'].lower():
                # FR4.1: Trigger special leave workflow
                return self._route_to_special_leave(leave_request, date_validity['reason'])

            # Otherwise reject
            return self._reject_leave(leave_request, date_validity['reason'])

        # FR3.3: Check if overnight is on non-Saturday night (special leave)
        if leave_request.leave_type == LeaveType.OVERNIGHT:
            if leave_request.start_date.weekday() != 5:  # Not Saturday
                return self._route_to_special_leave(
                    leave_request,
                    "Overnight leave requested for a night other than Saturday to Sunday"
                )

        # FR3.6: Day Leave is automatically approved (unlimited)
        if leave_request.leave_type == LeaveType.DAY_LEAVE:
            return self._approve_leave(leave_request, deduct_balance=False)

        # FR3.7: Restriction Check (for weekend leaves)
        if leave_request.leave_type in [LeaveType.OVERNIGHT, LeaveType.FRIDAY_SUPPER, LeaveType.DAY_LEAVE]:
            is_restricted = self.tools.tool_restriction_check(
                leave_request.student.admin_number,
                leave_request.start_date,
                leave_request.end_date
            )

            if is_restricted:
                return self._reject_leave(
                    leave_request,
                    f"{leave_request.student.full_name} is currently restricted from weekend leave during this period"
                )

        # FR3.4, FR3.5: Balance Check
        if leave_request.leave_type == LeaveType.OVERNIGHT:
            balance = self.tools.tool_leave_balance_check(
                leave_request.student.admin_number,
                'Overnight'
            )
            if balance < 1:
                return self._reject_leave(
                    leave_request,
                    f"{leave_request.student.full_name} has insufficient overnight leave balance (0 remaining)"
                )

        elif leave_request.leave_type == LeaveType.FRIDAY_SUPPER:
            balance = self.tools.tool_leave_balance_check(
                leave_request.student.admin_number,
                'Supper'
            )
            if balance < 1:
                return self._reject_leave(
                    leave_request,
                    f"{leave_request.student.full_name} has insufficient Friday Supper leave balance (0 remaining)"
                )

        # FR4.1: Check if explicit special leave requested
        if leave_request.leave_type == LeaveType.SPECIAL:
            return self._route_to_special_leave(leave_request, "Special leave explicitly requested")

        # All checks passed - approve
        return self._approve_leave(leave_request, deduct_balance=True)

    def _approve_leave(
        self,
        leave_request: LeaveRequest,
        deduct_balance: bool
    ) -> Dict[str, Any]:
        """
        FR5: Approve leave and update register/balance

        Args:
            leave_request: The leave request
            deduct_balance: Whether to deduct from balance

        Returns:
            Approval result with confirmation message
        """

        # FR5.1, FR5.2: Update leave register and reduce balance
        success = self.tools.tool_leave_update(
            student_admin_number=leave_request.student.admin_number,
            leave_type=leave_request.leave_type.value,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
            requesting_parent=leave_request.parent.auth_id,
            student_name=leave_request.student.full_name,
            house=leave_request.student.house,
            block=leave_request.student.block
        )

        if not success:
            return {
                'status': 'error',
                'message': "An error occurred while processing the leave. Please try again or contact the Housemaster."
            }

        # Calculate new balance
        new_balance = None
        if deduct_balance:
            if leave_request.leave_type == LeaveType.OVERNIGHT:
                new_balance = leave_request.student.overnight_balance - 1
                balance_type = "overnight"
            elif leave_request.leave_type == LeaveType.FRIDAY_SUPPER:
                new_balance = leave_request.student.friday_supper_balance - 1
                balance_type = "Friday Supper"

        # FR6.1: Approval notification
        message = self._format_approval_message(leave_request, new_balance, balance_type if deduct_balance else None)

        return {
            'status': 'approved',
            'leave_request': leave_request,
            'message': message
        }

    def _reject_leave(self, leave_request: LeaveRequest, reason: str) -> Dict[str, Any]:
        """
        FR6.2: Reject leave with clear reason

        Args:
            leave_request: The leave request
            reason: Reason for rejection

        Returns:
            Rejection result with notification message
        """

        message = f"""Thank you for your request.

Unfortunately, I'm unable to approve the exeat for {leave_request.student.full_name} on this occasion because {reason}.

If you require this leave to be granted, please contact {leave_request.student.full_name}'s Housemaster directly to request a Special Leave."""

        return {
            'status': 'rejected',
            'reason': reason,
            'leave_request': leave_request,
            'message': message
        }

    def _route_to_special_leave(
        self,
        leave_request: LeaveRequest,
        trigger_reason: str
    ) -> Dict[str, Any]:
        """
        FR4: Route request to Housemaster for special leave approval

        Args:
            leave_request: The leave request
            trigger_reason: Why special leave was triggered

        Returns:
            Pending result with notification message
        """

        # FR4.2: Send email to Housemaster (placeholder)
        housemaster_email = f"hm.{leave_request.student.house.lower()}@michaelhouse.org"

        email_content = f"""Special Leave Request Forwarded

Student: {leave_request.student.full_name} ({leave_request.student.admin_number})
House: {leave_request.student.house}
Block: {leave_request.student.block}

Requesting Parent: {leave_request.parent.auth_id}
Contact: {leave_request.parent.phone or leave_request.parent.email}

Leave Type: {leave_request.leave_type.value}
Dates: {leave_request.start_date.strftime('%d %B %Y %H:%M')} to {leave_request.end_date.strftime('%d %B %Y %H:%M')}

Reason for Special Leave: {trigger_reason}

Please respond with "APPROVE" or "REJECT" to process this request.
"""

        print(f"\n[SPECIAL LEAVE EMAIL SENT TO: {housemaster_email}]")
        print(email_content)
        print("[END EMAIL]\n")

        # FR6.3: Notify parent that request is pending
        message = f"""Thank you for your request.

This leave request for {leave_request.student.full_name} requires special approval as {trigger_reason.lower()}.

I have forwarded your request to the {leave_request.student.house} Housemaster for manual review. You will be notified once a decision has been made.

Thank you for your patience."""

        return {
            'status': 'special_pending',
            'leave_request': leave_request,
            'trigger_reason': trigger_reason,
            'message': message
        }

    def _format_approval_message(
        self,
        leave_request: LeaveRequest,
        new_balance: Optional[int],
        balance_type: Optional[str]
    ) -> str:
        """Format the approval notification message"""

        message = f"""Thank you for submitting your request.

I'm pleased to confirm that the exeat request for {leave_request.student.full_name} for {leave_request.leave_type.value} leave has been approved.

Dates: {leave_request.start_date.strftime('%A %d %B %Y at %H:%M')} to {leave_request.end_date.strftime('%A %d %B %Y at %H:%M')}"""

        if new_balance is not None:
            message += f"\n\nRemaining {balance_type} leave balance: {new_balance}"

        return message

    # ==================== Housemaster Functions (FR9) ====================

    def process_housemaster_request(
        self,
        message_text: str,
        sender_identifier: str,
        channel: str
    ) -> Dict[str, Any]:
        """
        FR9: Process Housemaster queries, cancellations, and restrictions

        Args:
            message_text: Housemaster's request text
            sender_identifier: HM's phone or email
            channel: Communication channel

        Returns:
            Processing result
        """

        # FR9.1: Authenticate Housemaster
        hm_info = self.tools.tool_hm_auth_house_check(sender_identifier)

        if not hm_info:
            return {
                'status': 'error',
                'message': "I couldn't verify your Housemaster credentials. Please ensure you're using your registered contact details."
            }

        housemaster = HousemasterInfo(
            hm_id=hm_info['hmID'],
            house=hm_info['assignedHouse']
        )

        text_lower = message_text.lower()

        # Determine intent
        if 'cancel' in text_lower or 'revoke' in text_lower:
            return self._process_hm_cancellation(message_text, housemaster)

        elif 'restrict' in text_lower or 'restriction' in text_lower or 'block' in text_lower:
            return self._process_hm_restriction(message_text, housemaster)

        elif 'balance' in text_lower or 'how many' in text_lower:
            return self._process_hm_balance_query(message_text, housemaster)

        elif 'leave' in text_lower or 'exeat' in text_lower:
            return self._process_hm_leave_query(message_text, housemaster)

        else:
            return {
                'status': 'error',
                'message': "I didn't understand your request. You can ask about leave balances, view leave history, cancel approved leaves, or set restrictions."
            }

    def _process_hm_cancellation(
        self,
        message_text: str,
        housemaster: HousemasterInfo
    ) -> Dict[str, Any]:
        """FR9.3, FR9.4: Process leave cancellation"""

        # Extract student identifier and reason
        # Simplified parsing for placeholder
        admin_pattern = r'\b(\d{5})\b'
        import re
        match = re.search(admin_pattern, message_text)

        if not match:
            return {
                'status': 'error',
                'message': "Please include the student's admin number to cancel their leave."
            }

        student_admin_number = match.group(1)

        # Extract reason (everything after "because" or "reason:")
        reason = "Housemaster decision"
        if 'because' in message_text.lower():
            reason = message_text.lower().split('because', 1)[1].strip()
        elif 'reason:' in message_text.lower():
            reason = message_text.lower().split('reason:', 1)[1].strip()

        # FR9.4: Cancel and refund balance
        success = self.tools.tool_leave_update(
            student_admin_number=student_admin_number,
            leave_type="",  # Not needed for cancellation
            start_date=datetime.now(),
            end_date=datetime.now(),
            requesting_parent="",
            student_name="",
            house=housemaster.house,
            block="",
            cancellation_details={
                'hmID': housemaster.hm_id,
                'reason': reason
            }
        )

        if success:
            # FR9.5: Parent will be notified (FR6.4)
            return {
                'status': 'success',
                'message': f"Leave cancelled for student {student_admin_number}. The balance has been refunded and the parent will be notified."
            }
        else:
            return {
                'status': 'error',
                'message': "Failed to cancel leave. Please verify the student admin number."
            }

    def _process_hm_restriction(
        self,
        message_text: str,
        housemaster: HousemasterInfo
    ) -> Dict[str, Any]:
        """FR9.6, FR9.7: Process restriction placement"""

        # Extract student admin number and dates
        # Simplified parsing for placeholder
        import re
        admin_pattern = r'\b(\d{5})\b'
        match = re.search(admin_pattern, message_text)

        if not match:
            return {
                'status': 'error',
                'message': "Please include the student's admin number to set a restriction."
            }

        student_admin_number = match.group(1)

        # For placeholder, use reasonable defaults
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days=14)  # 2 weeks
        reason = "Housemaster restriction"

        # FR9.7: Set restriction
        success = self.tools.tool_restriction_update(
            hm_id=housemaster.hm_id,
            student_admin_number=student_admin_number,
            start_date=start_date,
            end_date=end_date,
            reason=reason
        )

        if success:
            return {
                'status': 'success',
                'message': f"Restriction placed on student {student_admin_number} from {start_date.strftime('%d %b')} to {end_date.strftime('%d %b')}."
            }
        else:
            return {
                'status': 'error',
                'message': "Failed to set restriction."
            }

    def _process_hm_balance_query(
        self,
        message_text: str,
        housemaster: HousemasterInfo
    ) -> Dict[str, Any]:
        """FR9.2: Query student balance"""

        # Extract student admin number
        import re
        admin_pattern = r'\b(\d{5})\b'
        match = re.search(admin_pattern, message_text)

        if not match:
            return {
                'status': 'error',
                'message': "Please include the student's admin number to check their balance."
            }

        student_admin_number = match.group(1)

        # FR9.2: Query balance
        result = self.tools.tool_leave_query_hm(
            hm_id=housemaster.hm_id,
            student_admin_number=student_admin_number,
            query_type='balance'
        )

        balances = result.get('balances', {})

        return {
            'status': 'success',
            'message': f"""Leave Balance for Student {student_admin_number}:
Overnight Leave: {balances.get('overnight', 0)} remaining
Friday Supper Leave: {balances.get('fridaySupper', 0)} remaining"""
        }

    def _process_hm_leave_query(
        self,
        message_text: str,
        housemaster: HousemasterInfo
    ) -> Dict[str, Any]:
        """FR9.2: Query student leave history"""

        # Extract student admin number
        import re
        admin_pattern = r'\b(\d{5})\b'
        match = re.search(admin_pattern, message_text)

        if not match:
            return {
                'status': 'error',
                'message': "Please include the student's admin number to view their leave history."
            }

        student_admin_number = match.group(1)

        # FR9.2: Query leaves
        result = self.tools.tool_leave_query_hm(
            hm_id=housemaster.hm_id,
            student_admin_number=student_admin_number,
            query_type='leaves'
        )

        leaves = result.get('leaves', [])

        if not leaves:
            return {
                'status': 'success',
                'message': f"No leave history found for student {student_admin_number}."
            }

        message = f"Leave History for Student {student_admin_number}:\n\n"
        for leave in leaves:
            message += f"• {leave['leaveType']}: {leave['startDate']} to {leave['endDate']} ({leave['status']})\n"

        return {
            'status': 'success',
            'message': message
        }


from datetime import timedelta
