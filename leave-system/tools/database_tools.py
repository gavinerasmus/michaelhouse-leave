"""
Production Database Tools for Michaelhouse Leave System
Replaces placeholder_tools.py with real PostgreSQL database queries
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
import uuid

load_dotenv()


class DatabaseTools:
    """Production database implementation of LeaveSystemTools"""

    def __init__(self, db_config: Optional[Dict[str, str]] = None):
        """
        Initialize database connection

        Args:
            db_config: Optional database configuration dict
                      If not provided, reads from environment variables
        """
        if db_config is None:
            db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': os.getenv('DB_PORT', '5432'),
                'database': os.getenv('DB_NAME', 'michaelhouse_leave'),
                'user': os.getenv('DB_USER', 'leave_user'),
                'password': os.getenv('DB_PASSWORD', '')
            }

        self.db_config = db_config
        self._connection = None

    def _get_connection(self):
        """Get or create database connection"""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(**self.db_config)
        return self._connection

    def _execute_query(self, query: str, params: tuple = None, fetch_one: bool = False):
        """
        Execute a database query

        Args:
            query: SQL query string
            params: Query parameters tuple
            fetch_one: If True, fetch one result, else fetch all

        Returns:
            Query results as dict or list of dicts
        """
        conn = self._get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)

            if query.strip().upper().startswith('SELECT'):
                if fetch_one:
                    return dict(cur.fetchone()) if cur.rowcount > 0 else None
                else:
                    return [dict(row) for row in cur.fetchall()]
            else:
                conn.commit()
                return cur.rowcount > 0

    # ==================== Authentication Tools ====================

    def tool_parent_phone_check(self, phone_number: str) -> Optional[str]:
        """
        Authenticate Parent by Phone

        Args:
            phone_number: WhatsApp phone number

        Returns:
            parentAuthId or None if not found
        """
        query = """
            SELECT parent_id
            FROM parents
            WHERE phone = %s AND active = true
        """
        result = self._execute_query(query, (phone_number,), fetch_one=True)
        return result['parent_id'] if result else None

    def tool_parent_email_check(self, email_address: str) -> Optional[str]:
        """
        Authenticate Parent by Email

        Args:
            email_address: Parent's email address

        Returns:
            parentAuthId or None if not found
        """
        query = """
            SELECT parent_id
            FROM parents
            WHERE LOWER(email) = LOWER(%s) AND active = true
        """
        result = self._execute_query(query, (email_address,), fetch_one=True)
        return result['parent_id'] if result else None

    def tool_hm_auth_house_check(self, identifier: str) -> Optional[Dict[str, str]]:
        """
        Authenticate Housemaster and map to House

        Args:
            identifier: Phone number or email address

        Returns:
            Dict with hmID and assignedHouse, or None
        """
        query = """
            SELECT hm_id, house as assigned_house
            FROM housemasters
            WHERE (LOWER(email) = LOWER(%s) OR phone = %s)
              AND active = true
        """
        result = self._execute_query(query, (identifier, identifier), fetch_one=True)

        if result:
            return {
                'hmID': result['hm_id'],
                'assignedHouse': result['assigned_house']
            }
        return None

    # ==================== Student Linkage Tools ====================

    def tool_student_parent_linkage(
        self,
        parent_auth_id: str,
        requested_student_identifier: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify Student belongs to Parent

        Args:
            parent_auth_id: Authenticated parent ID
            requested_student_identifier: Student name or admin number

        Returns:
            Student record with admin no, name, house, block, balances
        """
        # Get current term for balance lookup
        current_term_query = """
            SELECT term_number, year
            FROM term_config
            WHERE CURRENT_DATE BETWEEN start_date AND end_date
            LIMIT 1
        """
        term_info = self._execute_query(current_term_query, fetch_one=True)

        if not term_info:
            # Default to term 1 if no current term
            term_info = {'term_number': 1, 'year': datetime.now().year}

        # Main query with joins
        query = """
            SELECT
                s.admin_number,
                s.first_name,
                s.last_name,
                s.house,
                s.block,
                COALESCE(lb.overnight_remaining, 3) as overnight_balance,
                COALESCE(lb.friday_supper_remaining, 3) as friday_supper_balance
            FROM students s
            JOIN student_parents sp ON s.id = sp.student_id
            JOIN parents p ON sp.parent_id = p.id
            LEFT JOIN leave_balances lb ON s.id = lb.student_id
                AND lb.term_number = %s
                AND lb.year = %s
            WHERE p.parent_id = %s
              AND (s.admin_number = %s
                   OR LOWER(s.first_name) LIKE LOWER(%s)
                   OR LOWER(s.last_name) LIKE LOWER(%s))
              AND s.active = true
            LIMIT 1
        """

        params = (
            term_info['term_number'],
            term_info['year'],
            parent_auth_id,
            requested_student_identifier,
            f'%{requested_student_identifier}%',
            f'%{requested_student_identifier}%'
        )

        result = self._execute_query(query, params, fetch_one=True)

        if not result:
            return None

        return {
            "adminNumber": result['admin_number'],
            "firstName": result['first_name'],
            "lastName": result['last_name'],
            "house": result['house'],
            "block": result['block'],
            "balances": {
                "overnight": result['overnight_balance'],
                "fridaySupper": result['friday_supper_balance']
            }
        }

    # ==================== Leave Balance Tools ====================

    def tool_leave_balance_check(
        self,
        student_admin_number: str,
        leave_type: str  # 'Overnight' or 'Supper'
    ) -> int:
        """
        Check remaining leave balance

        Args:
            student_admin_number: Student's admin number
            leave_type: 'Overnight' or 'Supper'

        Returns:
            Remaining balance count
        """
        # Get current term
        current_term_query = """
            SELECT term_number, year
            FROM term_config
            WHERE CURRENT_DATE BETWEEN start_date AND end_date
            LIMIT 1
        """
        term_info = self._execute_query(current_term_query, fetch_one=True)

        if not term_info:
            return 0

        if leave_type.lower() == 'overnight':
            column = 'overnight_remaining'
        else:
            column = 'friday_supper_remaining'

        query = f"""
            SELECT lb.{column}
            FROM leave_balances lb
            JOIN students s ON lb.student_id = s.id
            WHERE s.admin_number = %s
              AND lb.term_number = %s
              AND lb.year = %s
        """

        params = (student_admin_number, term_info['term_number'], term_info['year'])
        result = self._execute_query(query, params, fetch_one=True)

        return result[column] if result else 0

    # ==================== Date Validation Tools ====================

    def tool_date_validity_check(
        self,
        student_block: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Check if dates are permissible

        Args:
            student_block: Student's grade block (A-E)
            start_date: Leave start date/time
            end_date: Leave end date/time

        Returns:
            Dict with isValid: bool and reason: str
        """
        # Check if within term dates
        term_query = """
            SELECT term_number, start_date, end_date
            FROM term_config
            WHERE %s::date BETWEEN start_date AND end_date
               OR %s::date BETWEEN start_date AND end_date
        """
        term_result = self._execute_query(
            term_query,
            (start_date.date(), end_date.date()),
            fetch_one=True
        )

        if not term_result:
            return {
                "isValid": False,
                "reason": "Dates fall outside of term dates"
            }

        # Check for closed weekends (E and D blocks only)
        if student_block in ['E', 'D']:
            closed_query = """
                SELECT cw.weekend_date, cw.reason
                FROM closed_weekends cw
                JOIN term_config tc ON cw.term_id = tc.id
                WHERE cw.block = %s
                  AND tc.term_number = %s
                  AND tc.year = EXTRACT(YEAR FROM %s::date)
                  AND cw.weekend_date BETWEEN %s::date AND %s::date
            """

            params = (
                student_block,
                term_result['term_number'],
                start_date,
                start_date.date(),
                end_date.date()
            )

            closed_result = self._execute_query(closed_query, params, fetch_one=True)

            if closed_result:
                return {
                    "isValid": False,
                    "reason": f"Falls on closed weekend for {student_block} Block ({closed_result['reason']})"
                }

        return {
            "isValid": True,
            "reason": ""
        }

    # ==================== Restriction Tools ====================

    def tool_restriction_check(
        self,
        student_admin_number: str,
        start_date: datetime,
        end_date: datetime
    ) -> bool:
        """
        Check for active leave restrictions

        Args:
            student_admin_number: Student's admin number
            start_date: Requested leave start
            end_date: Requested leave end

        Returns:
            True if restricted, False if not
        """
        query = """
            SELECT COUNT(*) as count
            FROM leave_restrictions lr
            JOIN students s ON lr.student_id = s.id
            WHERE s.admin_number = %s
              AND lr.active = true
              AND lr.start_date <= %s
              AND lr.end_date >= %s
        """

        params = (student_admin_number, end_date, start_date)
        result = self._execute_query(query, params, fetch_one=True)

        return result['count'] > 0 if result else False

    def tool_restriction_update(
        self,
        hm_id: str,
        student_admin_number: str,
        start_date: datetime,
        end_date: datetime,
        reason: str = ""
    ) -> bool:
        """
        Set/Clear Student Leave Restriction

        Args:
            hm_id: Housemaster ID
            student_admin_number: Student's admin number
            start_date: Restriction start date
            end_date: Restriction end date
            reason: Reason for restriction

        Returns:
            True if successful
        """
        query = """
            INSERT INTO leave_restrictions (
                student_id, student_admin_number, hm_id, start_date, end_date, reason, active
            )
            SELECT s.id, s.admin_number, h.id, %s, %s, %s, true
            FROM students s, housemasters h
            WHERE s.admin_number = %s AND h.hm_id = %s
        """

        params = (start_date, end_date, reason, student_admin_number, hm_id)
        return self._execute_query(query, params)

    # ==================== Leave Management Tools ====================

    def tool_leave_update(
        self,
        student_admin_number: str,
        leave_type: str,
        start_date: datetime,
        end_date: datetime,
        requesting_parent: str,
        student_name: str,
        house: str,
        block: str,
        departure_timestamp: Optional[datetime] = None,
        driver_id_capture: Optional[str] = None,
        cancellation_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update leave register and balance / Log departure / Cancel leave

        Args:
            student_admin_number: Student's admin number
            leave_type: Type of leave
            start_date: Leave start
            end_date: Leave end
            requesting_parent: Parent name/ID
            student_name: Student's full name
            house: Student's house
            block: Student's block/grade
            departure_timestamp: When student departed (for Guard app)
            driver_id_capture: Driver ID data (NFR)
            cancellation_details: If cancelling (hmID, reason)

        Returns:
            True if successful
        """
        conn = self._get_connection()

        try:
            with conn.cursor() as cur:
                # Handle cancellation
                if cancellation_details:
                    # Cancel leave and refund balance
                    cancel_query = """
                        UPDATE leave_register lr
                        SET status = 'Cancelled',
                            cancelled_by_hm_id = (SELECT id FROM housemasters WHERE hm_id = %s),
                            cancellation_reason = %s,
                            cancelled_date = CURRENT_TIMESTAMP
                        WHERE lr.student_admin_number = %s
                          AND lr.status = 'Approved'
                          AND lr.departure_timestamp IS NULL
                        RETURNING leave_type
                    """

                    cur.execute(cancel_query, (
                        cancellation_details.get('hmID'),
                        cancellation_details.get('reason'),
                        student_admin_number
                    ))

                    cancelled_leave = cur.fetchone()

                    if cancelled_leave:
                        # Refund balance if applicable
                        cancelled_type = cancelled_leave[0]
                        if cancelled_type == 'Overnight':
                            refund_column = 'overnight_remaining'
                        elif cancelled_type == 'Friday Supper':
                            refund_column = 'friday_supper_remaining'
                        else:
                            refund_column = None

                        if refund_column:
                            refund_query = f"""
                                UPDATE leave_balances lb
                                SET {refund_column} = {refund_column} + 1
                                FROM students s
                                WHERE lb.student_id = s.id
                                  AND s.admin_number = %s
                            """
                            cur.execute(refund_query, (student_admin_number,))

                    conn.commit()
                    return True

                # Handle departure logging
                if departure_timestamp:
                    departure_query = """
                        UPDATE leave_register
                        SET departure_timestamp = %s,
                            driver_id_capture = %s
                        WHERE student_admin_number = %s
                          AND status = 'Approved'
                          AND start_date <= %s
                          AND end_date >= %s
                          AND departure_timestamp IS NULL
                    """

                    cur.execute(departure_query, (
                        departure_timestamp,
                        driver_id_capture,
                        student_admin_number,
                        departure_timestamp,
                        departure_timestamp
                    ))

                    conn.commit()
                    return cur.rowcount > 0

                # Handle new leave approval
                # 1. Insert into leave register
                name_parts = student_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ''

                leave_id = f"LEAVE_{uuid.uuid4().hex[:8].upper()}"

                insert_query = """
                    INSERT INTO leave_register (
                        leave_id, student_id, student_admin_number,
                        student_first_name, student_last_name, student_house, student_block,
                        leave_type, start_date, end_date,
                        requesting_parent_id, requesting_parent_name,
                        approved_date, status
                    )
                    SELECT
                        %s, s.id, s.admin_number,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        p.id, p.first_name || ' ' || p.last_name,
                        CURRENT_TIMESTAMP, 'Approved'
                    FROM students s
                    LEFT JOIN parents p ON p.parent_id = %s
                    WHERE s.admin_number = %s
                """

                cur.execute(insert_query, (
                    leave_id, first_name, last_name, house, block,
                    leave_type, start_date, end_date,
                    requesting_parent, student_admin_number
                ))

                # 2. Deduct balance if applicable
                if leave_type == 'Overnight':
                    balance_column = 'overnight_remaining'
                elif leave_type == 'Friday Supper':
                    balance_column = 'friday_supper_remaining'
                else:
                    balance_column = None

                if balance_column:
                    # Get current term
                    cur.execute("""
                        SELECT term_number, year
                        FROM term_config
                        WHERE CURRENT_DATE BETWEEN start_date AND end_date
                        LIMIT 1
                    """)
                    term_info = cur.fetchone()

                    if term_info:
                        update_balance_query = f"""
                            UPDATE leave_balances lb
                            SET {balance_column} = {balance_column} - 1
                            FROM students s
                            WHERE lb.student_id = s.id
                              AND s.admin_number = %s
                              AND lb.term_number = %s
                              AND lb.year = %s
                        """

                        cur.execute(update_balance_query, (
                            student_admin_number,
                            term_info[0],
                            term_info[1]
                        ))

                conn.commit()
                return True

        except Exception as e:
            conn.rollback()
            print(f"Error in tool_leave_update: {e}")
            return False

    def tool_leave_lookup(
        self,
        student_admin_number: str,
        current_timestamp: datetime
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve active approved leave for Guard app

        Args:
            student_admin_number: Student's admin number
            current_timestamp: Current date/time

        Returns:
            List of active leave records or None
        """
        query = """
            SELECT
                leave_type,
                start_date,
                end_date,
                student_first_name || ' ' || student_last_name as student_name,
                requesting_parent_name,
                departure_timestamp IS NOT NULL as departed
            FROM leave_register
            WHERE student_admin_number = %s
              AND status = 'Approved'
              AND start_date <= %s
              AND end_date >= %s
              AND departure_timestamp IS NULL
        """

        results = self._execute_query(query, (student_admin_number, current_timestamp, current_timestamp))

        if not results:
            return None

        return [{
            'leaveType': r['leave_type'],
            'startDate': r['start_date'],
            'endDate': r['end_date'],
            'studentName': r['student_name'],
            'requestingParent': r['requesting_parent_name'],
            'departed': r['departed']
        } for r in results]

    def tool_leave_query_hm(
        self,
        hm_id: str,
        student_admin_number: str,
        query_type: str = "leaves"  # 'leaves' or 'balance'
    ) -> Dict[str, Any]:
        """
        Retrieve specific student leave history or balance for Housemaster

        Args:
            hm_id: Housemaster ID
            student_admin_number: Student's admin number
            query_type: Type of query ('leaves' or 'balance')

        Returns:
            Leave details or balance information
        """
        if query_type == "balance":
            # Get current term balance
            query = """
                SELECT
                    s.admin_number as student_admin_number,
                    COALESCE(lb.overnight_remaining, 3) as overnight,
                    COALESCE(lb.friday_supper_remaining, 3) as friday_supper
                FROM students s
                LEFT JOIN leave_balances lb ON s.id = lb.student_id
                LEFT JOIN term_config tc ON lb.term_number = tc.term_number
                    AND lb.year = tc.year
                    AND CURRENT_DATE BETWEEN tc.start_date AND tc.end_date
                WHERE s.admin_number = %s
            """

            result = self._execute_query(query, (student_admin_number,), fetch_one=True)

            if result:
                return {
                    "studentAdminNumber": result['student_admin_number'],
                    "balances": {
                        "overnight": result['overnight'],
                        "fridaySupper": result['friday_supper']
                    }
                }

        else:  # query_type == "leaves"
            query = """
                SELECT
                    leave_type,
                    TO_CHAR(start_date, 'YYYY-MM-DD') as start_date,
                    TO_CHAR(end_date, 'YYYY-MM-DD') as end_date,
                    status,
                    departure_timestamp IS NOT NULL as departed
                FROM leave_register
                WHERE student_admin_number = %s
                ORDER BY start_date DESC
                LIMIT 10
            """

            results = self._execute_query(query, (student_admin_number,))

            return {
                "studentAdminNumber": student_admin_number,
                "leaves": [{
                    'leaveType': r['leave_type'],
                    'startDate': r['start_date'],
                    'endDate': r['end_date'],
                    'status': r['status'],
                    'departed': r['departed']
                } for r in results]
            }

        return {}

    # ==================== Term Configuration Tools ====================

    def tool_term_config_read(
        self,
        config_type: str,
        block: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Read term configuration

        Args:
            config_type: Type of config to read ('term_dates' or 'closed_weekends')
            block: Student block (for closed weekends)

        Returns:
            Configuration data
        """
        if config_type == "term_dates":
            query = """
                SELECT
                    term_number,
                    TO_CHAR(start_date, 'YYYY-MM-DD') as start,
                    TO_CHAR(end_date, 'YYYY-MM-DD') as end
                FROM term_config
                WHERE year = EXTRACT(YEAR FROM CURRENT_DATE)
                ORDER BY term_number
            """

            results = self._execute_query(query)
            return {
                f"term{r['term_number']}": {
                    "start": r['start'],
                    "end": r['end']
                }
                for r in results
            }

        elif config_type == "closed_weekends" and block:
            query = """
                SELECT
                    TO_CHAR(cw.weekend_date, 'YYYY-MM-DD') as date,
                    cw.reason
                FROM closed_weekends cw
                JOIN term_config tc ON cw.term_id = tc.id
                WHERE cw.block = %s
                  AND tc.year = EXTRACT(YEAR FROM CURRENT_DATE)
                ORDER BY cw.weekend_date
            """

            results = self._execute_query(query, (block,))

            return {
                "block": block,
                "closedWeekends": [{
                    'date': r['date'],
                    'reason': r['reason']
                } for r in results]
            }

        return {}

    def tool_term_config_write(
        self,
        config_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Write/update term configuration

        Args:
            config_type: Type of config to write
            data: Configuration data

        Returns:
            True if successful
        """
        # Implementation depends on admin UI requirements
        # For now, just return True
        print(f"[TOOL] Term config write requested: {config_type}")
        print(f"       Data: {data}")
        return True

    def close(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            self._connection.close()

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
