"""
Leave Request Parser
Extracts structured data from unstructured text requests
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.leave_models import LeaveType


class LeaveRequestParser:
    """Parses natural language leave requests"""

    # Common date patterns
    DATE_PATTERNS = [
        # Full date formats
        r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',  # 15/02/2025 or 15-02-2025
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',  # 15 February 2025
        # Relative dates
        r'(this\s+(?:saturday|sunday|weekend|friday))',
        r'(next\s+(?:saturday|sunday|weekend|friday))',
        r'(tomorrow)',
        r'(today)',
    ]

    # Leave type indicators
    OVERNIGHT_INDICATORS = [
        'overnight', 'sleep over', 'stay over', 'saturday night', 'weekend leave'
    ]

    SUPPER_INDICATORS = [
        'friday supper', 'supper', 'friday evening', 'friday night out'
    ]

    DAY_LEAVE_INDICATORS = [
        'day leave', 'day trip', 'saturday out', 'sunday out', 'day out'
    ]

    SPECIAL_INDICATORS = [
        'special leave', 'special permission', 'emergency', 'urgent'
    ]

    def __init__(self):
        self.weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }

    def parse_request(self, message_text: str) -> Dict[str, Any]:
        """
        Parse unstructured leave request text

        Args:
            message_text: Natural language request

        Returns:
            Parsed data dictionary with student_identifier, dates, leave_type
        """
        text_lower = message_text.lower()

        # Extract student identifier (name or admin number)
        student_identifier = self._extract_student_identifier(message_text)

        # Determine leave type
        leave_type = self._determine_leave_type(text_lower)

        # Extract dates
        start_date, end_date = self._extract_dates(text_lower, leave_type)

        return {
            "student_identifier": student_identifier,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "raw_text": message_text
        }

    def _extract_student_identifier(self, text: str) -> Optional[str]:
        """Extract student name or admin number from text"""

        # Check for admin number (5 digits)
        admin_pattern = r'\b(\d{5})\b'
        admin_match = re.search(admin_pattern, text)
        if admin_match:
            return admin_match.group(1)

        # Check for "for [Name]" pattern
        for_pattern = r'for\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        for_match = re.search(for_pattern, text)
        if for_match:
            return for_match.group(1)

        # Check for capitalized names (first and last name)
        name_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
        name_match = re.search(name_pattern, text)
        if name_match:
            return name_match.group(1)

        # Check for just first name after common words
        first_name_pattern = r'(?:for|my son|student)\s+([A-Z][a-z]+)'
        first_name_match = re.search(first_name_pattern, text, re.IGNORECASE)
        if first_name_match:
            return first_name_match.group(1)

        return None

    def _determine_leave_type(self, text: str) -> LeaveType:
        """Determine leave type from text"""

        # Check for special leave
        if any(indicator in text for indicator in self.SPECIAL_INDICATORS):
            return LeaveType.SPECIAL

        # Check for overnight
        if any(indicator in text for indicator in self.OVERNIGHT_INDICATORS):
            return LeaveType.OVERNIGHT

        # Check for Friday supper
        if any(indicator in text for indicator in self.SUPPER_INDICATORS):
            return LeaveType.FRIDAY_SUPPER

        # Check for day leave
        if any(indicator in text for indicator in self.DAY_LEAVE_INDICATORS):
            return LeaveType.DAY_LEAVE

        # Default: analyze dates to determine
        # If mentions weekend or Saturday/Sunday, likely day leave unless overnight specified
        if 'saturday' in text or 'sunday' in text or 'weekend' in text:
            return LeaveType.DAY_LEAVE

        # Default to overnight if unclear
        return LeaveType.OVERNIGHT

    def _extract_dates(
        self,
        text: str,
        leave_type: LeaveType
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Extract start and end dates from text"""

        # Look for explicit date ranges
        date_range_pattern = r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s*(?:to|-|until)\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'
        range_match = re.search(date_range_pattern, text)

        if range_match:
            start_str, end_str = range_match.groups()
            start_date = self._parse_date_string(start_str)
            end_date = self._parse_date_string(end_str)
            return self._apply_leave_times(start_date, end_date, leave_type)

        # Look for single date mentions
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                base_date = self._parse_relative_date(date_str)

                if base_date:
                    return self._infer_date_range(base_date, leave_type)

        # No dates found
        return None, None

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse various date string formats"""

        # Try different date formats
        formats = [
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%d/%m/%y',
            '%d-%m-%y',
            '%d %B %Y',
            '%d %b %Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _parse_relative_date(self, date_str: str) -> Optional[datetime]:
        """Parse relative dates like 'this Saturday', 'tomorrow'"""

        date_str_lower = date_str.lower()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Today/tomorrow
        if 'today' in date_str_lower:
            return today
        if 'tomorrow' in date_str_lower:
            return today + timedelta(days=1)

        # This/next weekday
        for day_name, day_num in self.weekdays.items():
            if day_name in date_str_lower:
                current_weekday = today.weekday()
                days_ahead = day_num - current_weekday

                if 'next' in date_str_lower:
                    # Next week
                    days_ahead += 7 if days_ahead > 0 else 7
                elif 'this' in date_str_lower or days_ahead < 0:
                    # This coming occurrence
                    days_ahead += 7 if days_ahead <= 0 else 0

                return today + timedelta(days=days_ahead)

        # Try parsing as absolute date
        return self._parse_date_string(date_str)

    def _infer_date_range(
        self,
        base_date: datetime,
        leave_type: LeaveType
    ) -> Tuple[datetime, datetime]:
        """Infer end date based on leave type and single date"""

        if leave_type == LeaveType.OVERNIGHT:
            # Saturday after sport to Sunday 18:50
            if base_date.weekday() == 5:  # Saturday
                start = base_date.replace(hour=14, minute=0)  # After sport ~14:00
                end = (base_date + timedelta(days=1)).replace(hour=18, minute=50)
                return start, end

        elif leave_type == LeaveType.FRIDAY_SUPPER:
            # Friday 17:00 to 21:00
            if base_date.weekday() == 4:  # Friday
                start = base_date.replace(hour=17, minute=0)
                end = base_date.replace(hour=21, minute=0)
                return start, end

        elif leave_type == LeaveType.DAY_LEAVE:
            # Same day, reasonable hours
            start = base_date.replace(hour=9, minute=0)
            end = base_date.replace(hour=17, minute=0)
            return start, end

        # Default: full day
        start = base_date.replace(hour=9, minute=0)
        end = base_date.replace(hour=17, minute=0)
        return start, end

    def _apply_leave_times(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        leave_type: LeaveType
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Apply proper times based on leave type"""

        if not start_date or not end_date:
            return start_date, end_date

        if leave_type == LeaveType.OVERNIGHT:
            # Saturday 14:00 to Sunday 18:50
            start_date = start_date.replace(hour=14, minute=0)
            end_date = end_date.replace(hour=18, minute=50)

        elif leave_type == LeaveType.FRIDAY_SUPPER:
            # Friday 17:00 to 21:00
            start_date = start_date.replace(hour=17, minute=0)
            end_date = end_date.replace(hour=21, minute=0)

        elif leave_type == LeaveType.DAY_LEAVE:
            # 9:00 to 17:00
            start_date = start_date.replace(hour=9, minute=0)
            end_date = end_date.replace(hour=17, minute=0)

        return start_date, end_date
