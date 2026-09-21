"""Importers module for CSV, XLSX, and JSON files."""
import csv
import json
import io
import os
import pandas as pd
from database import get_connection, add_activity
from models import Prospect
from scoring import score_prospect, generate_why_relevant, generate_personalization_point, generate_connection_note

def _str_breakdown(breakdown):
    """Convert dict breakdown to JSON string."""
    return json.dumps(breakdown, ensure_ascii=False)


def import_csv(file_content: bytes, filename: str = "data.csv") -> dict:
    """Import prospects from CSV data."""
    results = {"imported": 0, "skipped": 0, "errors": [], "prospects": []}

    try:
        text = file_content.decode("utf-8") if isinstance(file_content, bytes) else file_content
        reader = csv.DictReader(io.StringIO(text))

        conn = get_connection()
        cursor = conn.cursor()

        for row in reader:
            try:
                prospect_data = {
                    "name": row.get("name", "").strip(),
                    "linkedin_url": row.get("linkedin_url", "").strip() or None,
                    "company": row.get("company", "").strip() or None,
                    "job_title": row.get("job_title", "").strip() or None,
                    "location": row.get("location", "").strip() or None,
                    "industry": row.get("industry", "").strip() or None,
                    "bio": row.get("bio", "").strip() or None,
                    "about": row.get("about", "").strip() or None,
                    "email": row.get("email", "").strip() or None,
                    "notes": row.get("notes", "").strip() or None,
                }

                if not prospect_data["name"]:
                    results["skipped"] += 1
                    continue

                prospect = Prospect(**prospect_data)
                breakdown = score_prospect(prospect)
                prospect.score = breakdown["total"]
                prospect.score_breakdown = breakdown
                prospect.priority = "HIGH" if breakdown["total"] >= 55 else ("MEDIUM" if breakdown["total"] >= 30 else "LOW")
                prospect.why_relevant = generate_why_relevant(prospect, breakdown)
                prospect.personalization_point = generate_personalization_point(prospect)
                prospect.connection_note = generate_connection_note(prospect, breakdown)

                # Check for duplicates
                existing = check_duplicate(cursor, prospect)
                if existing:
                    results["skipped"] += 1
                    continue

                # Insert into database
                cursor.execute("""
                    INSERT OR IGNORE INTO prospects (name, linkedin_url, company, job_title, location, 
                    industry, bio, about, category, score, score_breakdown, priority, 
                    relationship_type, why_relevant, personalization_point, connection_note, 
                    date_added, status, email, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prospect.name, prospect.linkedin_url, prospect.company, prospect.job_title,
                    prospect.location, prospect.industry, prospect.bio, prospect.about,
                    prospect.category, prospect.score, _str_breakdown(prospect.score_breakdown),
                    prospect.priority, prospect.relationship_type, prospect.why_relevant,
                    prospect.personalization_point, prospect.connection_note,
                    prospect.date_added, prospect.status, prospect.email, prospect.notes,
                ))

                prospect.id = cursor.lastrowid
                results["imported"] += 1
                results["prospects"].append(prospect.to_dict())
                add_activity(prospect.id, "IMPORTED", f"Imported from {filename}")

            except Exception as e:
                results["errors"].append(f"Row error: {str(e)}")
                results["skipped"] += 1

        conn.commit()
        conn.close()

    except Exception as e:
        results["errors"].append(f"Import error: {str(e)}")

    return results


def import_xlsx(file_content: bytes, filename: str = "data.xlsx") -> dict:
    """Import prospects from XLSX data."""
    results = {"imported": 0, "skipped": 0, "errors": [], "prospects": []}

    try:
        df = pd.read_excel(io.BytesIO(file_content))
        records = df.to_dict(orient="records")

        conn = get_connection()
        cursor = conn.cursor()

        for row in records:
            try:
                prospect_data = {
                    "name": str(row.get("name", "")).strip(),
                    "linkedin_url": str(row.get("linkedin_url", "")).strip() or None,
                    "company": str(row.get("company", "")).strip() or None,
                    "job_title": str(row.get("job_title", "")).strip() or None,
                    "location": str(row.get("location", "")).strip() or None,
                    "industry": str(row.get("industry", "")).strip() or None,
                    "bio": str(row.get("bio", "")).strip() or None,
                    "about": str(row.get("about", "")).strip() or None,
                    "email": str(row.get("email", "")).strip() or None,
                    "notes": str(row.get("notes", "")).strip() or None,
                }

                if not prospect_data["name"]:
                    results["skipped"] += 1
                    continue

                prospect = Prospect(**prospect_data)
                breakdown = score_prospect(prospect)
                prospect.score = breakdown["total"]
                prospect.score_breakdown = breakdown
                prospect.priority = "HIGH" if breakdown["total"] >= 55 else ("MEDIUM" if breakdown["total"] >= 30 else "LOW")
                prospect.why_relevant = generate_why_relevant(prospect, breakdown)
                prospect.personalization_point = generate_personalization_point(prospect)
                prospect.connection_note = generate_connection_note(prospect, breakdown)

                existing = check_duplicate(cursor, prospect)
                if existing:
                    results["skipped"] += 1
                    continue

                cursor.execute("""
                    INSERT OR IGNORE INTO prospects (name, linkedin_url, company, job_title, location, 
                    industry, bio, about, category, score, score_breakdown, priority, 
                    relationship_type, why_relevant, personalization_point, connection_note, 
                    date_added, status, email, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prospect.name, prospect.linkedin_url, prospect.company, prospect.job_title,
                    prospect.location, prospect.industry, prospect.bio, prospect.about,
                    prospect.category, prospect.score, _str_breakdown(prospect.score_breakdown),
                    prospect.priority, prospect.relationship_type, prospect.why_relevant,
                    prospect.personalization_point, prospect.connection_note,
                    prospect.date_added, prospect.status, prospect.email, prospect.notes,
                ))

                prospect.id = cursor.lastrowid
                results["imported"] += 1
                results["prospects"].append(prospect.to_dict())
                add_activity(prospect.id, "IMPORTED", f"Imported from {filename}")

            except Exception as e:
                results["errors"].append(f"Row error: {str(e)}")
                results["skipped"] += 1

        conn.commit()
        conn.close()

    except Exception as e:
        results["errors"].append(f"Import error: {str(e)}")

    return results


def import_json(file_content: bytes, filename: str = "data.json") -> dict:
    """Import prospects from JSON data."""
    results = {"imported": 0, "skipped": 0, "errors": [], "prospects": []}

    try:
        text = file_content.decode("utf-8") if isinstance(file_content, bytes) else file_content
        data = json.loads(text)

        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise ValueError("JSON must be an array or object")

        conn = get_connection()
        cursor = conn.cursor()

        for row in data:
            try:
                prospect_data = {
                    "name": str(row.get("name", "")).strip(),
                    "linkedin_url": row.get("linkedin_url", "") or None,
                    "company": row.get("company", "") or None,
                    "job_title": row.get("job_title", "") or None,
                    "location": row.get("location", "") or None,
                    "industry": row.get("industry", "") or None,
                    "bio": row.get("bio", "") or None,
                    "about": row.get("about", "") or None,
                    "email": row.get("email", "") or None,
                    "notes": row.get("notes", "") or None,
                }

                if not prospect_data["name"]:
                    results["skipped"] += 1
                    continue

                prospect = Prospect(**prospect_data)
                breakdown = score_prospect(prospect)
                prospect.score = breakdown["total"]
                prospect.score_breakdown = breakdown
                prospect.priority = "HIGH" if breakdown["total"] >= 55 else ("MEDIUM" if breakdown["total"] >= 30 else "LOW")
                prospect.why_relevant = generate_why_relevant(prospect, breakdown)
                prospect.personalization_point = generate_personalization_point(prospect)
                prospect.connection_note = generate_connection_note(prospect, breakdown)

                existing = check_duplicate(cursor, prospect)
                if existing:
                    results["skipped"] += 1
                    continue

                cursor.execute("""
                    INSERT OR IGNORE INTO prospects (name, linkedin_url, company, job_title, location, 
                    industry, bio, about, category, score, score_breakdown, priority, 
                    relationship_type, why_relevant, personalization_point, connection_note, 
                    date_added, status, email, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prospect.name, prospect.linkedin_url, prospect.company, prospect.job_title,
                    prospect.location, prospect.industry, prospect.bio, prospect.about,
                    prospect.category, prospect.score, _str_breakdown(prospect.score_breakdown),
                    prospect.priority, prospect.relationship_type, prospect.why_relevant,
                    prospect.personalization_point, prospect.connection_note,
                    prospect.date_added, prospect.status, prospect.email, prospect.notes,
                ))

                prospect.id = cursor.lastrowid
                results["imported"] += 1
                results["prospects"].append(prospect.to_dict())
                add_activity(prospect.id, "IMPORTED", f"Imported from {filename}")

            except Exception as e:
                results["errors"].append(f"Row error: {str(e)}")
                results["skipped"] += 1

        conn.commit()
        conn.close()

    except Exception as e:
        results["errors"].append(f"Import error: {str(e)}")

    return results


def check_duplicate(cursor, prospect: Prospect) -> bool:
    """Check if a prospect already exists in the database."""
    if prospect.linkedin_url:
        cursor.execute("SELECT id FROM prospects WHERE linkedin_url = ?", (prospect.linkedin_url,))
        if cursor.fetchone():
            return True

    if prospect.email:
        cursor.execute("SELECT id FROM prospects WHERE email = ?", (prospect.email,))
        if cursor.fetchone():
            return True

    cursor.execute("SELECT id FROM prospects WHERE name = ? AND company = ?",
                   (prospect.name, prospect.company))
    if cursor.fetchone():
        return True

    return False


def manual_add_prospect(data: dict) -> dict:
    """Add a prospect manually entered by the user."""
    conn = get_connection()
    cursor = conn.cursor()

    prospect = Prospect(
        name=data.get("name", ""),
        linkedin_url=data.get("linkedin_url"),
        company=data.get("company"),
        job_title=data.get("job_title"),
        location=data.get("location"),
        industry=data.get("industry"),
        bio=data.get("bio"),
        about=data.get("about"),
        category=data.get("category", "OTHER"),
        email=data.get("email"),
        notes=data.get("notes"),
    )

    breakdown = score_prospect(prospect)
    prospect.score = breakdown["total"]
    prospect.score_breakdown = breakdown
    prospect.priority = "HIGH" if breakdown["total"] >= 55 else ("MEDIUM" if breakdown["total"] >= 30 else "LOW")
    prospect.why_relevant = generate_why_relevant(prospect, breakdown)
    prospect.personalization_point = generate_personalization_point(prospect)
    prospect.connection_note = generate_connection_note(prospect, breakdown)

    existing = check_duplicate(cursor, prospect)
    if existing:
        conn.close()
        return {"success": False, "message": "Prospect already exists in database."}

    cursor.execute("""
        INSERT INTO prospects (name, linkedin_url, company, job_title, location, industry, 
        bio, about, category, score, score_breakdown, priority, relationship_type, 
        why_relevant, personalization_point, connection_note, date_added, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        prospect.name, prospect.linkedin_url, prospect.company, prospect.job_title,
        prospect.location, prospect.industry, prospect.bio, prospect.about,
        prospect.category, prospect.score, _str_breakdown(prospect.score_breakdown),
        prospect.priority, prospect.relationship_type, prospect.why_relevant,
        prospect.personalization_point, prospect.connection_note,
        prospect.date_added or "datetime('now')", "NEW",
    ))

    prospect.id = cursor.lastrowid
    conn.commit()
    conn.close()

    add_activity(prospect.id, "MANUAL_ADD", "Added manually")
    return {"success": True, "prospect": prospect.to_dict()}
