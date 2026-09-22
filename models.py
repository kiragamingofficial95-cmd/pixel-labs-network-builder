"""Database models for Pixel Labs Network Builder."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import sqlite3
import json
from datetime import datetime


@dataclass
class Prospect:
    """Represents a LinkedIn prospect."""
    id: Optional[int] = None
    name: str = ""
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    bio: Optional[str] = None
    about: Optional[str] = None
    category: str = "OTHER"
    score: int = 0
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    priority: str = "LOW"
    relationship_type: str = "General Professional Network"
    why_relevant: Optional[str] = None
    personalization_point: Optional[str] = None
    connection_note: Optional[str] = None
    follow_up_topic: Optional[str] = None
    date_added: Optional[str] = None
    status: str = "NEW"
    last_action: Optional[str] = None
    notes: Optional[str] = None
    email: Optional[str] = None
    icp_score: float = 0
    icp_breakdown: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "linkedin_url": self.linkedin_url,
            "company": self.company,
            "job_title": self.job_title,
            "location": self.location,
            "industry": self.industry,
            "bio": self.bio,
            "about": self.about,
            "category": self.category,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "priority": self.priority,
            "relationship_type": self.relationship_type,
            "why_relevant": self.why_relevant,
            "personalization_point": self.personalization_point,
            "connection_note": self.connection_note,
            "follow_up_topic": self.follow_up_topic,
            "date_added": self.date_added,
            "status": self.status,
            "last_action": self.last_action,
            "notes": self.notes,
            "email": self.email,
            "icp_score": self.icp_score,
            "icp_breakdown": self.icp_breakdown,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Prospect":
        """Create a Prospect from a database row."""
        score_breakdown = {}
        try:
            score_breakdown = json.loads(row["score_breakdown"]) if row["score_breakdown"] else {}
        except (json.JSONDecodeError, TypeError):
            score_breakdown = {}

        icp_breakdown = {}
        try:
            icp_breakdown = json.loads(row["icp_breakdown"]) if row["icp_breakdown"] else {}
        except (json.JSONDecodeError, TypeError):
            icp_breakdown = {}

        return cls(
            id=row["id"],
            name=row["name"] or "",
            linkedin_url=row.get("linkedin_url"),
            company=row.get("company"),
            job_title=row.get("job_title"),
            location=row.get("location"),
            industry=row.get("industry"),
            bio=row.get("bio"),
            about=row.get("about"),
            category=row.get("category", "OTHER"),
            score=row.get("score", 0),
            score_breakdown=score_breakdown,
            priority=row.get("priority", "LOW"),
            relationship_type=row.get("relationship_type", "General Professional Network"),
            why_relevant=row.get("why_relevant"),
            personalization_point=row.get("personalization_point"),
            connection_note=row.get("connection_note"),
            follow_up_topic=row.get("follow_up_topic"),
            date_added=row.get("date_added"),
            status=row.get("status", "NEW"),
            last_action=row.get("last_action"),
            notes=row.get("notes"),
            email=row.get("email"),
            icp_score=row.get("icp_score", 0),
            icp_breakdown=icp_breakdown,
        )
