"""LinkedIn profile search and enrichment helper.

Uses Groq API to filter and enrich profiles imported via CSV/JSON/manual entry.
LinkedIn scraping is NOT supported - profiles must be imported manually.
"""

import json
import csv
import io
import re
from typing import Optional
from ai_client import ai_client
from database import get_connection


def import_linkedin_connections_csv(csv_content: str) -> dict:
    """Import LinkedIn connections exported as CSV.

    LinkedIn allows exporting connections via:
    Settings > Data Privacy > Get a copy of your data > Connections

    Returns count of imported profiles.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    imported = 0
    skipped = 0

    conn = get_connection()
    cursor = conn.cursor()

    for row in reader:
        # LinkedIn CSV has: First Name, Last Name, Email Address, Company, Position, etc.
        first_name = (row.get("First Name") or row.get("firstName") or "").strip()
        last_name = (row.get("Last Name") or row.get("lastName") or "").strip()
        name = f"{first_name} {last_name}".strip()

        if not name:
            skipped += 1
            continue

        email = (row.get("Email Address") or row.get("email") or "").strip()
        company = (row.get("Company") or row.get("company") or "").strip()
        title = (row.get("Position") or row.get("title") or row.get("jobTitle") or "").strip()
        linkedin_url = (row.get("URL") or row.get("linkedinUrl") or row.get("Profile URL") or "").strip()

        # Skip duplicates
        cursor.execute(
            "SELECT id FROM prospects WHERE name = ? AND company = ?",
            (name, company)
        )
        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute(
            """INSERT INTO prospects (name, job_title, company, location, industry, bio, linkedin_url, email, status)
               VALUES (?, ?, ?, '', '', ?, ?, ?, 'NEW')""",
            (name, title, company, f"LinkedIn connection: {company}", linkedin_url, email)
        )
        imported += 1

    conn.commit()
    conn.close()

    return {"imported": imported, "skipped": skipped, "total": imported + skipped}


def import_linkedin_profiles_json(profiles: list) -> dict:
    """Import LinkedIn profiles from JSON data.

    Each profile should have: name, company, title, linkedin_url, etc.
    """
    imported = 0
    skipped = 0

    conn = get_connection()
    cursor = conn.cursor()

    for profile in profiles:
        name = (profile.get("name") or profile.get("fullName") or "").strip()
        if not name:
            skipped += 1
            continue

        company = (profile.get("company") or profile.get("organization") or "").strip()
        title = (profile.get("title") or profile.get("jobTitle") or profile.get("job_title") or "").strip()
        location = (profile.get("location") or profile.get("geoLocation") or "").strip()
        industry = (profile.get("industry") or "").strip()
        bio = (profile.get("bio") or profile.get("summary") or profile.get("about") or "").strip()
        linkedin_url = (profile.get("linkedin_url") or profile.get("url") or profile.get("profileUrl") or "").strip()
        email = (profile.get("email") or "").strip()

        # Skip duplicates
        cursor.execute(
            "SELECT id FROM prospects WHERE name = ? AND company = ?",
            (name, company)
        )
        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute(
            """INSERT INTO prospects (name, job_title, company, location, industry, bio, linkedin_url, email, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NEW')""",
            (name, title, company, location, industry, bio, linkedin_url, email)
        )
        imported += 1

    conn.commit()
    conn.close()

    return {"imported": imported, "skipped": skipped, "total": imported + skipped}


def search_and_filter_profiles(
    query: str = "",
    industry: str = "",
    title: str = "",
    location: str = "",
    min_icp_score: int = 60,
    use_ai: bool = True
) -> dict:
    """Search imported profiles and optionally filter by ICP using AI.

    This searches the LOCAL database of already-imported profiles.
    It does NOT scrape LinkedIn.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Build search query
    conditions = []
    params = []

    if query:
        conditions.append("(name LIKE ? OR company LIKE ? OR job_title LIKE ? OR bio LIKE ?)")
        q = f"%{query}%"
        params.extend([q, q, q, q])

    if industry:
        conditions.append("industry LIKE ?")
        params.append(f"%{industry}%")

    if title:
        conditions.append("job_title LIKE ?")
        params.append(f"%{title}%")

    if location:
        conditions.append("location LIKE ?")
        params.append(f"%{location}%")

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    cursor.execute(f"SELECT * FROM prospects WHERE {where_clause}", params)
    rows = cursor.fetchall()
    conn.close()

    profiles = []
    for row in rows:
        profiles.append({
            "id": row["id"],
            "name": row["name"],
            "job_title": row.get("job_title", ""),
            "company": row.get("company", ""),
            "location": row.get("location", ""),
            "industry": row.get("industry", ""),
            "bio": row.get("bio", ""),
            "linkedin_url": row.get("linkedin_url", ""),
            "icp_score": row.get("icp_score", 0),
            "status": row.get("status", "NEW"),
        })

    # Optionally filter by ICP score
    if min_icp_score > 0:
        profiles = [p for p in profiles if (p.get("icp_score") or 0) >= min_icp_score]

    # Optionally use AI to re-score and filter
    ai_results = None
    if use_ai and ai_client.available and profiles:
        from icp_profile import get_active_icp
        icp_profile = get_active_icp()
        if icp_profile:
            icp_criteria = {
                "target_industries": icp_profile.get("target_industries", []),
                "target_titles": icp_profile.get("target_titles", []),
                "target_keywords": icp_profile.get("target_keywords", []),
                "exclude_keywords": icp_profile.get("exclude_keywords", []),
                "target_locations": icp_profile.get("target_locations", []),
            }
            ai_results = ai_client.filter_profiles_by_icp(profiles, icp_criteria)

    return {
        "total_found": len(profiles),
        "profiles": profiles,
        "ai_filtered": ai_results,
    }


def enrich_single_profile(profile_id: int) -> dict:
    """Enrich a single profile with AI-generated insights."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prospects WHERE id = ?", (profile_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Profile not found"}

    profile = {
        "name": row["name"],
        "job_title": row.get("job_title", ""),
        "company": row.get("company", ""),
        "location": row.get("location", ""),
        "industry": row.get("industry", ""),
        "bio": row.get("bio", ""),
        "about": row.get("about", ""),
    }

    enriched = ai_client.enrich_profiles([profile])
    if enriched:
        return enriched[0]
    return {"error": "Enrichment failed"}
