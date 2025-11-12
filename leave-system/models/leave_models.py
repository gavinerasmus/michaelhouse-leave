"""
Data Models for Michaelhouse Leave System
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum


class LeaveType(Enum):
    """Types of leave requests"""
    OVERNIGHT = "Overnight"
    FRIDAY_SUPPER = "Friday Supper"
    DAY_LEAVE = "Day Leave"
    SPECIAL = "Special"


class LeaveStatus(Enum):
    """Status of leave requests"""
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
    SPECIAL_PENDING = "Special Leave Pending"


@dataclass
class StudentInfo:
    """Student information"""
    admin_number: str
    first_name: str
    last_name: str
    house: str
    block: str  # Grade: A, B, C, D, E
    overnight_balance: int
    friday_supper_balance: int

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class ParentInfo:
    """Parent information"""
    auth_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    channel: str = "unknown"  # 'whatsapp' or 'email'


@dataclass
class LeaveRequest:
    """Leave request details"""
    student: StudentInfo
    parent: ParentInfo
    leave_type: LeaveType
    start_date: datetime
    end_date: datetime
    status: LeaveStatus = LeaveStatus.PENDING
    rejection_reason: Optional[str] = None
    special_leave_reason: Optional[str] = None
    housemaster_notes: Optional[str] = None


@dataclass
class HousemasterInfo:
    """Housemaster information"""
    hm_id: str
    house: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class LeaveRecord:
    """Complete leave record in the register"""
    leave_id: str
    student_admin_number: str
    student_first_name: str
    student_last_name: str
    student_house: str
    student_block: str
    leave_type: LeaveType
    start_date: datetime
    end_date: datetime
    requesting_parent: str
    approved_date: datetime
    departure_timestamp: Optional[datetime] = None
    driver_id_capture: Optional[str] = None
    status: LeaveStatus = LeaveStatus.APPROVED
    cancelled_by_hm: Optional[str] = None
    cancellation_reason: Optional[str] = None
    cancelled_date: Optional[datetime] = None


@dataclass
class Restriction:
    """Student leave restriction"""
    student_admin_number: str
    hm_id: str
    start_date: datetime
    end_date: datetime
    reason: str
    active: bool = True
