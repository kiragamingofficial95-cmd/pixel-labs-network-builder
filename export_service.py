"""Export service for Pixel Labs Network Builder."""
import csv
import io
import os
from datetime import datetime
from database import get_connection
from models import Prospect
from config import CATEGORY_LABELS


def export_queue_csv(category: str = None, status: str = None) -> dict:
    """Export prospects to CSV format."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM prospects WHERE 1=1"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY score DESC, category"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "name", "job_title", "company", "location", "linkedin_url", "category",
        "score", "score_breakdown", "priority", "relationship_type",
        "why_relevant", "personalization_point", "connection_note",
        "follow_up_topic", "status"
    ])

    for row in rows:
        prospect = Prospect.from_row(row)
        writer.writerow([
            prospect.name,
            prospect.job_title or "",
            prospect.company or "",
            prospect.location or "",
            prospect.linkedin_url or "",
            CATEGORY_LABELS.get(prospect.category, prospect.category),
            prospect.score,
            str(prospect.score_breakdown),
            prospect.priority,
            prospect.relationship_type or "",
            prospect.why_relevant or "",
            prospect.personalization_point or "",
            prospect.connection_note or "",
            prospect.follow_up_topic or "",
            prospect.status,
        ])

    csv_content = output.getvalue()
    filename = f"linkedin_networking_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join("data", filename)
    os.makedirs("data", exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        f.write(csv_content)

    return {
        "success": True,
        "filename": filename,
        "filepath": filepath,
        "count": len(rows),
        "csv_content": csv_content,
        "download_url": f"/api/export/download/{filename}",
    }


def export_queue_csv_content(category: str = None, status: str = None) -> str:
    """Export prospects to CSV content string."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM prospects WHERE 1=1"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY score DESC, category"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "name", "job_title", "company", "location", "linkedin_url", "category",
        "score", "score_breakdown", "priority", "relationship_type",
        "why_relevant", "personalization_point", "connection_note",
        "follow_up_topic", "status"
    ])

    for row in rows:
        prospect = Prospect.from_row(row)
        writer.writerow([
            prospect.name,
            prospect.job_title or "",
            prospect.company or "",
            prospect.location or "",
            prospect.linkedin_url or "",
            CATEGORY_LABELS.get(prospect.category, prospect.category),
            prospect.score,
            str(prospect.score_breakdown),
            prospect.priority,
            prospect.relationship_type or "",
            prospect.why_relevant or "",
            prospect.personalization_point or "",
            prospect.connection_note or "",
            prospect.follow_up_topic or "",
            prospect.status,
        ])

    return output.getvalue()
