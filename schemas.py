"""Pydantic schemas for Pixel Labs Network Builder."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from enum import Enum


class CategoryEnum(str, Enum):
    CLIENT = "CLIENT"
    REFERRAL_PARTNER = "REFERRAL_PARTNER"
    AGENCY_BUSINESS = "AGENCY_BUSINESS"
    PROFESSIONAL_NETWORK = "PROFESSIONAL_NETWORK"
    OTHER = "OTHER"


class PriorityEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class StatusEnum(str, Enum):
    NEW = "NEW"
    REVIEW = "REVIEW"
    CONNECTION_SENT = "CONNECTION_SENT"
    CONNECTED = "CONNECTED"
    FOLLOW_UP = "FOLLOW_UP"
    NOT_INTERESTED = "NOT_INTERESTED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"


class ProspectCreate(BaseModel):
    """Schema for creating a prospect."""
    name: str
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    bio: Optional[str] = None
    about: Optional[str] = None
    category: Optional[str] = "OTHER"
    score: int = 0
    score_breakdown: Optional[Dict[str, Any]] = None
    priority: Optional[str] = "LOW"
    relationship_type: Optional[str] = "General Professional Network"
    why_relevant: Optional[str] = None
    personalization_point: Optional[str] = None
    connection_note: Optional[str] = None
    follow_up_topic: Optional[str] = None
    notes: Optional[str] = None
    email: Optional[str] = None


class ProspectUpdate(BaseModel):
    """Schema for updating a prospect."""
    status: Optional[str] = None
    notes: Optional[str] = None
    last_action: Optional[str] = None
    connection_note: Optional[str] = None
    follow_up_topic: Optional[str] = None


class ScoreBreakdown(BaseModel):
    """Schema for score breakdown."""
    pixel_labs_target: int = 0
    founder_decision_maker: int = 0
    referral_potential: int = 0
    relevant_industry: int = 0
    relevant_location: int = 0
    relevant_role: int = 0
    personalization_info: int = 0
    professional_network_relevance: int = 0
    total: int = 0


class DailyQueueItem(BaseModel):
    """Schema for a daily queue item."""
    name: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    category: str = "OTHER"
    score: int = 0
    priority: str = "LOW"
    relationship_type: str = "General Professional Network"
    why_relevant: Optional[str] = None
    personalization_point: Optional[str] = None
    connection_note: Optional[str] = None
    follow_up_topic: Optional[str] = None
    linkedin_url: Optional[str] = None


class DailyQueueResponse(BaseModel):
    """Schema for daily queue response."""
    date: str
    total_target: int
    targets: Dict[str, int]
    queue: Dict[str, List[DailyQueueItem]]
    actual_counts: Dict[str, int]


class ExportData(BaseModel):
    """Schema for export data."""
    name: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    category: str = "OTHER"
    score: int = 0
    score_breakdown: Optional[Dict[str, Any]] = None
    priority: str = "LOW"
    relationship_type: str = "General Professional Network"
    why_relevant: Optional[str] = None
    personalization_point: Optional[str] = None
    connection_note: Optional[str] = None
    follow_up_topic: Optional[str] = None
    status: str = "NEW"


class DashboardData(BaseModel):
    """Schema for dashboard data."""
    total_researched: int = 0
    total_connection_sent: int = 0
    total_connected: int = 0
    total_follow_ups: int = 0
    total_not_interested: int = 0
    total_do_not_contact: int = 0
    today_recommended: int = 0
    category_breakdown: Dict[str, int] = {}
    status_breakdown: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    client_connections: int = 0
    network_balance: Dict[str, float] = {}
    current_targets: Dict[str, int] = {}
