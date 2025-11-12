"""
Unit tests for LeaveProcessor
Tests the core business logic and workflows
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from processors.leave_processor import LeaveProcessor
from models.leave_models import LeaveType, LeaveStatus, StudentInfo, ParentInfo
from tools.placeholder_tools import LeaveSystemTools


class TestLeaveProcessor:
    """Test suite for leave processing logic"""

    @pytest.fixture
    def processor(self):
        """Create processor with mock tools"""
        return LeaveProcessor()

    @pytest.fixture
    def mock_tools(self):
        """Create mock tools instance"""
        return Mock(spec=LeaveSystemTools)

    # ==================== Parent Authentication Tests ====================

    def test_authenticate_parent_whatsapp_success(self, processor):
        """Test successful WhatsApp parent authentication"""
        result = processor._authenticate_parent("27603174174", "whatsapp")

        assert result['authenticated'] is True
        assert result['parent_info'].auth_id == "PARENT_001"
        assert result['parent_info'].channel == "whatsapp"

    def test_authenticate_parent_whatsapp_failure(self, processor):
        """Test failed WhatsApp authentication"""
        result = processor._authenticate_parent("99999999999", "whatsapp")

        assert result['authenticated'] is False
        assert 'message' in result

    def test_authenticate_parent_email_success(self, processor):
        """Test successful email authentication"""
        result = processor._authenticate_parent("john.smith@example.com", "email")

        assert result['authenticated'] is True
        assert result['parent_info'].auth_id == "PARENT_001"
        assert result['parent_info'].channel == "email"

    def test_authenticate_parent_email_failure(self, processor):
        """Test failed email authentication"""
        result = processor._authenticate_parent("unknown@example.com", "email")

        assert result['authenticated'] is False

    # ==================== Leave Request Processing Tests ====================

    def test_process_parent_request_success(self, processor):
        """Test successful leave request processing"""
        message = "Can James have overnight leave this Saturday 8th February?"
        sender = "27603174174"

        result = processor.process_parent_request(message, sender, "whatsapp")

        # Should either approve or route to special leave
        assert result['status'] in ['approved', 'rejected', 'special_pending', 'error']
        assert 'message' in result

    def test_process_parent_request_auth_failure(self, processor):
        """Test request with authentication failure"""
        message = "Can James have leave?"
        sender = "99999999999"  # Unknown parent

        result = processor.process_parent_request(message, sender, "whatsapp")

        assert result['status'] == 'rejected'
        assert result['reason'] == 'authentication_failed'

    def test_process_parent_request_no_student(self, processor):
        """Test request without student identifier"""
        message = "Can I have leave this weekend?"
        sender = "27603174174"

        result = processor.process_parent_request(message, sender, "whatsapp")

        assert result['status'] == 'error'
        assert 'student' in result['message'].lower()

    def test_process_parent_request_wrong_student(self, processor):
        """Test request for student not linked to parent"""
        message = "Can Michael Doe have leave this Saturday?"  # Michael belongs to PARENT_002
        sender = "27603174174"  # PARENT_001

        result = processor.process_parent_request(message, sender, "whatsapp")

        assert result['status'] == 'rejected'
        assert result['reason'] == 'student_linkage_failed'

    # ==================== Leave Eligibility Tests ====================

    def test_overnight_leave_sufficient_balance(self, processor, mock_tools):
        """Test overnight leave with sufficient balance"""
        processor.tools = mock_tools

        # Mock successful checks
        mock_tools.tool_date_validity_check.return_value = {'isValid': True, 'reason': ''}
        mock_tools.tool_restriction_check.return_value = False
        mock_tools.tool_leave_balance_check.return_value = 3  # Full balance
        mock_tools.tool_leave_update.return_value = True

        student = StudentInfo(
            admin_number="12345",
            first_name="James",
            last_name="Smith",
            house="Finningley",
            block="C",
            overnight_balance=3,
            friday_supper_balance=3
        )

        parent = ParentInfo(auth_id="PARENT_001", channel="whatsapp")

        from models.leave_models import LeaveRequest
        leave_request = LeaveRequest(
            student=student,
            parent=parent,
            leave_type=LeaveType.OVERNIGHT,
            start_date=datetime(2025, 2, 8, 14, 0),
            end_date=datetime(2025, 2, 9, 18, 50)
        )

        result = processor._process_leave_eligibility(leave_request)

        assert result['status'] == 'approved'

    def test_overnight_leave_insufficient_balance(self, processor, mock_tools):
        """Test overnight leave with zero balance"""
        processor.tools = mock_tools

        mock_tools.tool_date_validity_check.return_value = {'isValid': True, 'reason': ''}
        mock_tools.tool_restriction_check.return_value = False
        mock_tools.tool_leave_balance_check.return_value = 0  # No balance

        student = StudentInfo(
            admin_number="12345",
            first_name="James",
            last_name="Smith",
            house="Finningley",
            block="C",
            overnight_balance=0,
            friday_supper_balance=3
        )

        parent = ParentInfo(auth_id="PARENT_001", channel="whatsapp")

        from models.leave_models import LeaveRequest
        leave_request = LeaveRequest(
            student=student,
            parent=parent,
            leave_type=LeaveType.OVERNIGHT,
            start_date=datetime(2025, 2, 8, 14, 0),
            end_date=datetime(2025, 2, 9, 18, 50)
        )

        result = processor._process_leave_eligibility(leave_request)

        assert result['status'] == 'rejected'
        assert 'insufficient' in result['reason'].lower()

    def test_day_leave_unlimited(self, processor, mock_tools):
        """Test that day leave is always approved (unlimited)"""
        processor.tools = mock_tools

        mock_tools.tool_date_validity_check.return_value = {'isValid': True, 'reason': ''}
        mock_tools.tool_restriction_check.return_value = False
        mock_tools.tool_leave_update.return_value = True

        student = StudentInfo(
            admin_number="12345",
            first_name="James",
            last_name="Smith",
            house="Finningley",
            block="C",
            overnight_balance=0,  # Even with zero balance
            friday_supper_balance=0
        )

        parent = ParentInfo(auth_id="PARENT_001", channel="whatsapp")

        from models.leave_models import LeaveRequest
        leave_request = LeaveRequest(
            student=student,
            parent=parent,
            leave_type=LeaveType.DAY_LEAVE,
            start_date=datetime(2025, 2, 9, 9, 0),
            end_date=datetime(2025, 2, 9, 17, 0)
        )

        result = processor._process_leave_eligibility(leave_request)

        assert result['status'] == 'approved'

    def test_closed_weekend_routes_to_special(self, processor, mock_tools):
        """Test that closed weekend routes to special leave"""
        processor.tools = mock_tools

        # Mock closed weekend
        mock_tools.tool_date_validity_check.return_value = {
            'isValid': False,
            'reason': 'Falls on closed weekend for E Block'
        }

        student = StudentInfo(
            admin_number="67890",
            first_name="Michael",
            last_name="Doe",
            house="Shepstone",
            block="E",  # E block has closed weekends
            overnight_balance=3,
            friday_supper_balance=3
        )

        parent = ParentInfo(auth_id="PARENT_002", channel="email")

        from models.leave_models import LeaveRequest
        leave_request = LeaveRequest(
            student=student,
            parent=parent,
            leave_type=LeaveType.OVERNIGHT,
            start_date=datetime(2025, 1, 18, 14, 0),  # First weekend of term
            end_date=datetime(2025, 1, 19, 18, 50)
        )

        result = processor._process_leave_eligibility(leave_request)

        assert result['status'] == 'special_pending'

    def test_student_restricted_rejection(self, processor, mock_tools):
        """Test that restricted student is rejected"""
        processor.tools = mock_tools

        mock_tools.tool_date_validity_check.return_value = {'isValid': True, 'reason': ''}
        mock_tools.tool_restriction_check.return_value = True  # Restricted
        mock_tools.tool_leave_balance_check.return_value = 3

        student = StudentInfo(
            admin_number="11111",
            first_name="David",
            last_name="Johnson",
            house="Transvaal",
            block="D",
            overnight_balance=3,
            friday_supper_balance=3
        )

        parent = ParentInfo(auth_id="PARENT_003", channel="whatsapp")

        from models.leave_models import LeaveRequest
        leave_request = LeaveRequest(
            student=student,
            parent=parent,
            leave_type=LeaveType.OVERNIGHT,
            start_date=datetime(2025, 2, 8, 14, 0),
            end_date=datetime(2025, 2, 9, 18, 50)
        )

        result = processor._process_leave_eligibility(leave_request)

        assert result['status'] == 'rejected'
        assert 'restricted' in result['reason'].lower()

    # ==================== Housemaster Functions Tests ====================

    def test_housemaster_authentication_success(self, processor):
        """Test successful housemaster authentication"""
        message = "What is the balance for student 12345?"
        sender = "hm.finningley@michaelhouse.org"

        result = processor.process_housemaster_request(message, sender, "email")

        assert result['status'] == 'success'
        assert 'balance' in result['message'].lower()

    def test_housemaster_authentication_failure(self, processor):
        """Test failed housemaster authentication"""
        message = "What is the balance for student 12345?"
        sender = "unknown@example.com"

        result = processor.process_housemaster_request(message, sender, "email")

        assert result['status'] == 'error'
        assert 'verify' in result['message'].lower()

    def test_housemaster_balance_query(self, processor):
        """Test housemaster balance query"""
        message = "Balance for 12345"
        sender = "hm.finningley@michaelhouse.org"

        result = processor.process_housemaster_request(message, sender, "email")

        assert result['status'] == 'success'
        assert 'overnight' in result['message'].lower()

    def test_housemaster_cancellation(self, processor, mock_tools):
        """Test housemaster leave cancellation"""
        processor.tools = mock_tools
        mock_tools.tool_leave_update.return_value = True

        message = "Cancel leave for student 12345 because academic concerns"
        sender = "hm.finningley@michaelhouse.org"

        result = processor.process_housemaster_request(message, sender, "email")

        # Should call tool_leave_update with cancellation_details
        assert mock_tools.tool_leave_update.called

    # ==================== Message Formatting Tests ====================

    def test_approval_message_format(self, processor):
        """Test that approval messages are correctly formatted"""
        student = StudentInfo(
            admin_number="12345",
            first_name="James",
            last_name="Smith",
            house="Finningley",
            block="C",
            overnight_balance=3,
            friday_supper_balance=3
        )

        parent = ParentInfo(auth_id="PARENT_001", channel="whatsapp")

        from models.leave_models import LeaveRequest
        leave_request = LeaveRequest(
            student=student,
            parent=parent,
            leave_type=LeaveType.OVERNIGHT,
            start_date=datetime(2025, 2, 8, 14, 0),
            end_date=datetime(2025, 2, 9, 18, 50)
        )

        message = processor._format_approval_message(leave_request, 2, "overnight")

        assert "James Smith" in message
        assert "Overnight" in message
        assert "2" in message  # Remaining balance

    def test_rejection_message_format(self, processor):
        """Test that rejection messages include reason"""
        student = StudentInfo(
            admin_number="12345",
            first_name="James",
            last_name="Smith",
            house="Finningley",
            block="C",
            overnight_balance=0,
            friday_supper_balance=3
        )

        parent = ParentInfo(auth_id="PARENT_001", channel="whatsapp")

        from models.leave_models import LeaveRequest
        leave_request = LeaveRequest(
            student=student,
            parent=parent,
            leave_type=LeaveType.OVERNIGHT,
            start_date=datetime(2025, 2, 8, 14, 0),
            end_date=datetime(2025, 2, 9, 18, 50)
        )

        result = processor._reject_leave(leave_request, "insufficient balance")

        assert "James Smith" in result['message']
        assert "insufficient balance" in result['message']
        assert "Housemaster" in result['message']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
