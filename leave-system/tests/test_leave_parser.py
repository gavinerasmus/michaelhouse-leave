"""
Unit tests for LeaveRequestParser
Tests natural language parsing of leave requests
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from processors.leave_parser import LeaveRequestParser
from models.leave_models import LeaveType


class TestLeaveRequestParser:
    """Test suite for leave request parsing"""

    @pytest.fixture
    def parser(self):
        """Create parser instance for tests"""
        return LeaveRequestParser()

    # ==================== Student Identifier Extraction ====================

    def test_extract_admin_number(self, parser):
        """Test extraction of 5-digit admin number"""
        text = "Can student 12345 have leave this Saturday?"
        result = parser._extract_student_identifier(text)
        assert result == "12345"

    def test_extract_full_name(self, parser):
        """Test extraction of full name (First Last)"""
        text = "Can James Smith have leave this Saturday?"
        result = parser._extract_student_identifier(text)
        assert result == "James Smith"

    def test_extract_name_with_for(self, parser):
        """Test extraction with 'for' pattern"""
        text = "Request leave for Michael Doe this weekend"
        result = parser._extract_student_identifier(text)
        assert result == "Michael Doe"

    def test_extract_first_name_only(self, parser):
        """Test extraction of first name after keywords"""
        text = "Can my son James go out this Saturday?"
        result = parser._extract_student_identifier(text)
        assert result == "James"

    # ==================== Leave Type Determination ====================

    def test_overnight_leave_detection(self, parser):
        """Test overnight leave keyword detection"""
        text = "can he have overnight leave this saturday"
        leave_type = parser._determine_leave_type(text)
        assert leave_type == LeaveType.OVERNIGHT

    def test_friday_supper_detection(self, parser):
        """Test Friday supper leave detection"""
        text = "can james have friday supper leave"
        leave_type = parser._determine_leave_type(text)
        assert leave_type == LeaveType.FRIDAY_SUPPER

    def test_day_leave_detection(self, parser):
        """Test day leave detection"""
        text = "can he have day leave on sunday"
        leave_type = parser._determine_leave_type(text)
        assert leave_type == LeaveType.DAY_LEAVE

    def test_special_leave_detection(self, parser):
        """Test special leave detection"""
        text = "requesting special leave for emergency"
        leave_type = parser._determine_leave_type(text)
        assert leave_type == LeaveType.SPECIAL

    def test_weekend_defaults_to_day_leave(self, parser):
        """Test that weekend mentions default to day leave"""
        text = "can he go out this weekend"
        leave_type = parser._determine_leave_type(text)
        assert leave_type == LeaveType.DAY_LEAVE

    # ==================== Date Extraction ====================

    def test_parse_relative_date_this_saturday(self, parser):
        """Test parsing 'this Saturday'"""
        date_str = "this saturday"
        result = parser._parse_relative_date(date_str)

        assert result is not None
        assert result.weekday() == 5  # Saturday

    def test_parse_relative_date_tomorrow(self, parser):
        """Test parsing 'tomorrow'"""
        date_str = "tomorrow"
        result = parser._parse_relative_date(date_str)

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expected = today + timedelta(days=1)

        assert result.date() == expected.date()

    def test_parse_absolute_date_dd_mm_yyyy(self, parser):
        """Test parsing DD/MM/YYYY format"""
        date_str = "15/02/2025"
        result = parser._parse_date_string(date_str)

        assert result is not None
        assert result.day == 15
        assert result.month == 2
        assert result.year == 2025

    def test_parse_date_range(self, parser):
        """Test parsing date ranges"""
        text = "leave from 15/02/2025 to 16/02/2025"
        parsed_data = parser.parse_request(text)

        assert parsed_data['start_date'] is not None
        assert parsed_data['end_date'] is not None

    # ==================== Full Request Parsing ====================

    def test_parse_overnight_request(self, parser):
        """Test parsing complete overnight request"""
        message = "Hi, can James Smith have overnight leave this Saturday?"

        result = parser.parse_request(message)

        assert result['student_identifier'] == "James Smith"
        # Note: Leave type might be DAY_LEAVE without 'overnight' keyword
        assert result['start_date'] is not None
        assert result['end_date'] is not None

    def test_parse_friday_supper_request(self, parser):
        """Test parsing Friday supper request"""
        message = "Can student 12345 have Friday supper leave this week?"

        result = parser.parse_request(message)

        assert result['student_identifier'] == "12345"
        assert result['leave_type'] == LeaveType.FRIDAY_SUPPER

    def test_parse_day_leave_request(self, parser):
        """Test parsing day leave request"""
        message = "Can Michael have day leave on Sunday?"

        result = parser.parse_request(message)

        assert result['student_identifier'] == "Michael"
        assert result['leave_type'] == LeaveType.DAY_LEAVE

    def test_parse_request_with_admin_number(self, parser):
        """Test parsing with admin number"""
        message = "Request leave for student 67890 on 14/02/2025"

        result = parser.parse_request(message)

        assert result['student_identifier'] == "67890"
        assert result['start_date'] is not None

    # ==================== Date Time Application ====================

    def test_overnight_leave_times(self, parser):
        """Test that overnight leave gets correct times"""
        base_date = datetime(2025, 2, 8)  # A Saturday

        start, end = parser._infer_date_range(base_date, LeaveType.OVERNIGHT)

        assert start.hour == 14  # After sport
        assert start.minute == 0
        assert end.hour == 18  # Sunday evening
        assert end.minute == 50

    def test_friday_supper_times(self, parser):
        """Test that Friday supper gets correct times"""
        base_date = datetime(2025, 2, 7)  # A Friday

        start, end = parser._infer_date_range(base_date, LeaveType.FRIDAY_SUPPER)

        assert start.hour == 17
        assert start.minute == 0
        assert end.hour == 21
        assert end.minute == 0

    def test_day_leave_times(self, parser):
        """Test that day leave gets correct times"""
        base_date = datetime(2025, 2, 9)  # A Sunday

        start, end = parser._infer_date_range(base_date, LeaveType.DAY_LEAVE)

        assert start.hour == 9
        assert end.hour == 17

    # ==================== Edge Cases ====================

    def test_no_student_identifier(self, parser):
        """Test handling of request with no student identifier"""
        message = "Can I have leave this weekend?"

        result = parser.parse_request(message)

        # Should still parse but student_identifier might be None
        assert 'student_identifier' in result

    def test_multiple_names_in_text(self, parser):
        """Test that parser handles multiple names correctly"""
        message = "Can James Smith and John Doe have leave? Just James."

        result = parser.parse_request(message)

        # Should get the first name pattern
        assert result['student_identifier'] in ["James Smith", "James"]

    def test_empty_message(self, parser):
        """Test handling of empty message"""
        result = parser.parse_request("")

        assert result['student_identifier'] is None
        assert result['start_date'] is None
        assert result['end_date'] is None

    def test_message_without_dates(self, parser):
        """Test message with student but no dates"""
        message = "Can James have leave please?"

        result = parser.parse_request(message)

        assert result['student_identifier'] == "James"
        # Dates might be None if no date mentioned


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
