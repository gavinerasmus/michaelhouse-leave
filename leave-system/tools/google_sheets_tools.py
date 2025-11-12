"""
Google Sheets Backend for Leave System

This provides a Google Sheets implementation of the LeaveSystemTools interface,
allowing the system to use Google Sheets as a database backend for testing/demo purposes.

Setup:
1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create a service account and download credentials JSON
4. Share your Google Sheet with the service account email
5. Set GOOGLE_SHEETS_CREDENTIALS_PATH and GOOGLE_SHEET_ID in .env
"""

import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import uuid

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Warning: Google Sheets dependencies not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    raise

from tools.placeholder_tools import LeaveSystemTools


class GoogleSheetsTools(LeaveSystemTools):
    """
    Google Sheets implementation of leave system tools.

    Sheet Structure:
    - Sheet 1: "parents" - Parent information
    - Sheet 2: "students" - Student information
    - Sheet 3: "student_parents" - Parent-student linkages
    - Sheet 4: "leave_balances" - Leave balances per student
    - Sheet 5: "leave_register" - Leave request records
    - Sheet 6: "restrictions" - Student restrictions
    - Sheet 7: "term_config" - Term dates configuration
    - Sheet 8: "closed_weekends" - Closed weekend configuration
    - Sheet 9: "housemasters" - Housemaster information
    """

    def __init__(self, credentials_path: Optional[str] = None, sheet_id: Optional[str] = None):
        """
        Initialize Google Sheets backend.

        Args:
            credentials_path: Path to service account JSON credentials
            sheet_id: Google Sheets document ID
        """
        # Get configuration from environment if not provided
        self.credentials_path = credentials_path or os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
        self.sheet_id = sheet_id or os.getenv('GOOGLE_SHEET_ID')

        if not self.credentials_path:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS_PATH not set in environment")
        if not self.sheet_id:
            raise ValueError("GOOGLE_SHEET_ID not set in environment")

        # Initialize Google Sheets API
        self.service = self._initialize_service()
        self.cache = {}  # Simple cache for repeated lookups

    def _initialize_service(self):
        """Initialize Google Sheets API service."""
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            service = build('sheets', 'v4', credentials=creds)
            return service
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Sheets API: {e}")

    def _read_sheet(self, sheet_name: str, range_spec: str = "A:Z") -> List[List[Any]]:
        """Read data from a sheet."""
        try:
            range_name = f"{sheet_name}!{range_spec}"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()
            return result.get('values', [])
        except HttpError as e:
            print(f"Error reading sheet {sheet_name}: {e}")
            return []

    def _write_sheet(self, sheet_name: str, range_spec: str, values: List[List[Any]]):
        """Write data to a sheet."""
        try:
            range_name = f"{sheet_name}!{range_spec}"
            body = {'values': values}
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
        except HttpError as e:
            print(f"Error writing to sheet {sheet_name}: {e}")
            raise

    def _append_sheet(self, sheet_name: str, values: List[List[Any]]):
        """Append data to a sheet."""
        try:
            range_name = f"{sheet_name}!A:Z"
            body = {'values': values}
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
        except HttpError as e:
            print(f"Error appending to sheet {sheet_name}: {e}")
            raise

    def _find_row(self, sheet_name: str, column_index: int, value: str) -> Optional[int]:
        """Find row index where column contains value (1-indexed)."""
        data = self._read_sheet(sheet_name)
        for idx, row in enumerate(data):
            if idx == 0:  # Skip header
                continue
            if len(row) > column_index and row[column_index] == value:
                return idx + 1  # 1-indexed
        return None

    # ==================== Parent Authentication ====================

    def tool_parent_phone_check(self, phone_number: str) -> Optional[str]:
        """
        Check if phone number belongs to registered parent.
        Sheet: parents | Columns: id, phone, email, first_name, last_name, active
        """
        data = self._read_sheet("parents")
        if not data:
            return None

        # Find parent by phone (column index 1)
        for row in data[1:]:  # Skip header
            if len(row) > 5 and row[1] == phone_number and row[5].lower() == 'true':
                return row[0]  # Return parent_id

        return None

    def tool_parent_email_check(self, email_address: str) -> Optional[str]:
        """
        Check if email belongs to registered parent.
        Sheet: parents | Columns: id, phone, email, first_name, last_name, active
        """
        data = self._read_sheet("parents")
        if not data:
            return None

        # Find parent by email (column index 2)
        for row in data[1:]:  # Skip header
            if len(row) > 5 and row[2].lower() == email_address.lower() and row[5].lower() == 'true':
                return row[0]  # Return parent_id

        return None

    # ==================== Student Data ====================

    def tool_student_parent_linkage(
        self,
        parent_auth_id: str,
        requested_student_identifier: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify parent-student linkage and return student data.
        Sheets: students, student_parents, leave_balances
        """
        # Check linkage first
        linkages = self._read_sheet("student_parents")
        student_id = None

        for row in linkages[1:]:  # Skip header
            if len(row) >= 2 and row[1] == parent_auth_id:  # parent_id column
                # Check if this student matches the identifier
                potential_student_id = row[0]
                student_data = self._get_student_by_id(potential_student_id)

                if student_data and (
                    student_data['admin_number'] == requested_student_identifier or
                    requested_student_identifier.lower() in student_data['first_name'].lower() or
                    requested_student_identifier.lower() in student_data['last_name'].lower()
                ):
                    student_id = potential_student_id
                    break

        if not student_id:
            return None

        # Get full student data including balances
        student = self._get_student_by_id(student_id)
        if not student:
            return None

        # Get balances
        balances = self._get_current_balances(student_id)

        return {
            "adminNumber": student['admin_number'],
            "firstName": student['first_name'],
            "lastName": student['last_name'],
            "house": student['house'],
            "block": student['block'],
            "balances": balances
        }

    def _get_student_by_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Get student by ID."""
        data = self._read_sheet("students")
        for row in data[1:]:
            if len(row) > 6 and row[0] == student_id and row[6].lower() == 'true':
                return {
                    "id": row[0],
                    "admin_number": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "house": row[4],
                    "block": row[5],
                    "active": row[6]
                }
        return None

    def tool_get_student_by_admin_number(self, admin_number: str) -> Optional[Dict[str, Any]]:
        """Get student by admin number."""
        data = self._read_sheet("students")
        for row in data[1:]:
            if len(row) > 6 and row[1] == admin_number and row[6].lower() == 'true':
                return {
                    "student_id": row[0],
                    "admin_number": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "house": row[4],
                    "block": row[5]
                }
        return None

    def tool_check_parent_student_linkage(self, parent_id: str, student_id: str) -> bool:
        """Check if parent-student linkage exists."""
        data = self._read_sheet("student_parents")
        for row in data[1:]:
            if len(row) >= 2 and row[0] == student_id and row[1] == parent_id:
                return True
        return False

    # ==================== Leave Balances ====================

    def tool_check_leave_balance(self, student_id: str) -> Optional[Dict[str, int]]:
        """Get student's current leave balance."""
        return self._get_current_balances(student_id)

    def _get_current_balances(self, student_id: str) -> Dict[str, int]:
        """Get current term balances for student."""
        data = self._read_sheet("leave_balances")
        current_year = datetime.now().year
        current_term = self._get_current_term()

        for row in data[1:]:
            if len(row) >= 5 and row[0] == student_id and row[1] == str(current_year) and row[2] == current_term:
                return {
                    "overnight_remaining": int(row[3]),
                    "friday_supper_remaining": int(row[4])
                }

        # Default if not found
        return {
            "overnight_remaining": 3,
            "friday_supper_remaining": 3
        }

    def _get_current_term(self) -> str:
        """Determine current term from date."""
        month = datetime.now().month
        if month >= 1 and month <= 3:
            return "Term 1"
        elif month >= 4 and month <= 6:
            return "Term 2"
        elif month >= 7 and month <= 9:
            return "Term 3"
        else:
            return "Term 4"

    def tool_deduct_leave_balance(
        self,
        student_id: str,
        leave_type: str,
        amount: int = 1
    ) -> bool:
        """Deduct from student's leave balance."""
        data = self._read_sheet("leave_balances")
        current_year = str(datetime.now().year)
        current_term = self._get_current_term()

        # Find the row
        row_index = None
        for idx, row in enumerate(data[1:], start=2):  # Start from row 2 (skip header)
            if len(row) >= 5 and row[0] == student_id and row[1] == current_year and row[2] == current_term:
                row_index = idx
                break

        if not row_index:
            return False

        # Update the balance
        if leave_type == "overnight":
            col = "D"  # overnight_remaining column
            current = int(data[row_index - 1][3])
            new_value = max(0, current - amount)
        elif leave_type == "friday_supper":
            col = "E"  # friday_supper_remaining column
            current = int(data[row_index - 1][4])
            new_value = max(0, current - amount)
        else:
            return False

        # Write back
        self._write_sheet("leave_balances", f"{col}{row_index}", [[new_value]])
        return True

    # ==================== Date Validation ====================

    def tool_check_date_in_term(self, requested_date: date) -> bool:
        """Check if date falls within a term."""
        data = self._read_sheet("term_config")

        for row in data[1:]:
            if len(row) >= 4:
                try:
                    start = datetime.strptime(row[2], "%Y-%m-%d").date()
                    end = datetime.strptime(row[3], "%Y-%m-%d").date()
                    if start <= requested_date <= end:
                        return True
                except ValueError:
                    continue

        return False

    def tool_check_closed_weekend(self, block_letter: str, weekend_date: date) -> bool:
        """Check if weekend is closed for a specific block."""
        data = self._read_sheet("closed_weekends")

        for row in data[1:]:
            if len(row) >= 3:
                try:
                    closed_date = datetime.strptime(row[1], "%Y-%m-%d").date()
                    if row[0] == block_letter and closed_date == weekend_date:
                        return True
                except ValueError:
                    continue

        return False

    # ==================== Restrictions ====================

    def tool_check_student_restrictions(
        self,
        student_id: str,
        check_date: date
    ) -> Optional[Dict[str, Any]]:
        """Check for active restrictions on student."""
        data = self._read_sheet("restrictions")

        for row in data[1:]:
            if len(row) >= 6 and row[0] == student_id and row[5].lower() == 'true':
                try:
                    start = datetime.strptime(row[2], "%Y-%m-%d").date()
                    end = datetime.strptime(row[3], "%Y-%m-%d").date()

                    if start <= check_date <= end:
                        return {
                            "restriction_id": row[1],
                            "reason": row[4],
                            "start_date": row[2],
                            "end_date": row[3]
                        }
                except ValueError:
                    continue

        return None

    # ==================== Leave Register ====================

    def tool_register_leave(
        self,
        student_id: str,
        leave_type: str,
        start_datetime: datetime,
        end_datetime: datetime,
        requested_by: str,
        channel: str
    ) -> str:
        """Register a new leave request."""
        leave_id = f"LEAVE-{uuid.uuid4().hex[:12].upper()}"

        row = [
            leave_id,
            student_id,
            leave_type,
            start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "approved",
            requested_by,
            channel,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "true"  # active
        ]

        self._append_sheet("leave_register", [row])
        return leave_id

    def tool_get_leave_by_id(self, leave_id: str) -> Optional[Dict[str, Any]]:
        """Get leave record by ID."""
        data = self._read_sheet("leave_register")

        for row in data[1:]:
            if len(row) >= 10 and row[0] == leave_id:
                return {
                    "leave_id": row[0],
                    "student_id": row[1],
                    "leave_type": row[2],
                    "start_datetime": row[3],
                    "end_datetime": row[4],
                    "status": row[5],
                    "requested_by": row[6],
                    "channel": row[7]
                }

        return None

    def tool_cancel_leave(self, leave_id: str, reason: str) -> bool:
        """Cancel a leave request."""
        data = self._read_sheet("leave_register")

        for idx, row in enumerate(data[1:], start=2):
            if len(row) >= 10 and row[0] == leave_id:
                # Update status to cancelled
                self._write_sheet("leave_register", f"F{idx}", [["cancelled"]])
                self._write_sheet("leave_register", f"J{idx}", [["false"]])  # Set active=false
                return True

        return False

    # ==================== Housemaster Functions ====================

    def tool_get_student_leave_history(
        self,
        student_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent leave history for student."""
        data = self._read_sheet("leave_register")
        history = []

        for row in data[1:]:
            if len(row) >= 10 and row[1] == student_id and row[9].lower() == 'true':
                history.append({
                    "leave_id": row[0],
                    "leave_type": row[2],
                    "start_datetime": row[3],
                    "end_datetime": row[4],
                    "status": row[5]
                })

        # Sort by start datetime descending and limit
        history.sort(key=lambda x: x['start_datetime'], reverse=True)
        return history[:limit]


def create_sheets_template_instructions():
    """
    Returns instructions for setting up the Google Sheets template.
    """
    return """
# Google Sheets Template Setup

## Sheet Structure

Create a Google Sheets document with the following sheets:

### Sheet 1: "parents"
Columns: id | phone | email | first_name | last_name | active

Example:
parent-001 | 27603174174 | john@example.com | John | Smith | true

### Sheet 2: "students"
Columns: id | admin_number | first_name | last_name | house | block | active

Example:
student-001 | 12345 | James | Smith | Finningley | E | true

### Sheet 3: "student_parents"
Columns: student_id | parent_id

Example:
student-001 | parent-001

### Sheet 4: "leave_balances"
Columns: student_id | year | term | overnight_remaining | friday_supper_remaining

Example:
student-001 | 2025 | Term 1 | 3 | 3

### Sheet 5: "leave_register"
Columns: leave_id | student_id | leave_type | start_datetime | end_datetime | status | requested_by | channel | created_at | active

Example:
LEAVE-ABC123 | student-001 | overnight | 2025-01-15 14:00:00 | 2025-01-16 18:50:00 | approved | 27603174174 | whatsapp | 2025-01-10 10:30:00 | true

### Sheet 6: "restrictions"
Columns: student_id | restriction_id | start_date | end_date | reason | active

Example:
student-001 | REST-001 | 2025-01-10 | 2025-01-20 | disciplinary | true

### Sheet 7: "term_config"
Columns: year | term | start_date | end_date

Example:
2025 | Term 1 | 2025-01-15 | 2025-03-20

### Sheet 8: "closed_weekends"
Columns: block_letter | weekend_date | reason

Example:
E | 2025-02-15 | Inter-house competition

### Sheet 9: "housemasters"
Columns: id | email | phone | house | first_name | last_name | active

Example:
hm-001 | hm.finningley@michaelhouse.org | 27831112222 | Finningley | David | Jones | true

## Setup Steps

1. Create a new Google Sheet
2. Add the 9 sheets with the column headers above
3. Add sample data for testing
4. Note the Sheet ID from the URL (between /d/ and /edit)
5. Share the sheet with your service account email (found in credentials JSON)
"""
