"""ICP Profile module for Pixel Labs Network Builder.

Allows users to define their Ideal Customer Profile criteria and
automatically score prospects against those criteria.
"""
import json
from database import get_connection
from config import SCORING_WEIGHTS


def init_icp_profile():
    """Initialize the ICP profiles table."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS icp_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'Default ICP',
            is_active INTEGER DEFAULT 1,
            target_industries TEXT DEFAULT '[]',
            target_locations TEXT DEFAULT '[]',
            target_titles TEXT DEFAULT '[]',
            target_company_types TEXT DEFAULT '[]',
            target_keywords TEXT DEFAULT '[]',
            exclude_keywords TEXT DEFAULT '[]',
            industry_weight REAL DEFAULT 25,
            location_weight REAL DEFAULT 15,
            title_weight REAL DEFAULT 20,
            company_weight REAL DEFAULT 15,
            keyword_weight REAL DEFAULT 10,
            exclude_weight REAL DEFAULT -15,
            max_score REAL DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert default profile if none exists
    cursor.execute("SELECT COUNT(*) as count FROM icp_profiles")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("""
            INSERT INTO icp_profiles (name, target_industries, target_titles, target_keywords,
                industry_weight, location_weight, title_weight, company_weight, keyword_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Default ICP",
            json.dumps(["contracting", "landscaping", "home services", "construction", "plumbing",
                       "electrical", "hvac", "roofing", "painting", "flooring", "restaurant",
                       "real estate", "property management", "medical", "dental", "veterinary",
                       "marketing", "seo", "web design", "agency"]),
            json.dumps(["owner", "founder", "ceo", "president", "director", "partner", "manager",
                       "marketing manager", "growth manager"]),
            json.dumps(["service", "local", "business", "residential", "commercial", "home"]),
            25, 15, 20, 15, 10
        ))
        conn.commit()

    conn.close()


def get_active_icp():
    """Get the active ICP profile."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM icp_profiles WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        init_icp_profile()
        return get_active_icp()

    return {
        "id": row["id"],
        "name": row["name"],
        "is_active": bool(row["is_active"]),
        "target_industries": json.loads(row["target_industries"] or "[]"),
        "target_locations": json.loads(row["target_locations"] or "[]"),
        "target_titles": json.loads(row["target_titles"] or "[]"),
        "target_company_types": json.loads(row["target_company_types"] or "[]"),
        "target_keywords": json.loads(row["target_keywords"] or "[]"),
        "exclude_keywords": json.loads(row["exclude_keywords"] or "[]"),
        "industry_weight": row["industry_weight"],
        "location_weight": row["location_weight"],
        "title_weight": row["title_weight"],
        "company_weight": row["company_weight"],
        "keyword_weight": row["keyword_weight"],
        "exclude_weight": row["exclude_weight"],
        "max_score": row["max_score"],
    }


def save_icp_profile(profile_id: int, data: dict):
    """Save an ICP profile."""
    conn = get_connection()
    cursor = conn.cursor()

    # Deactivate other profiles if this one is being set active
    if data.get("is_active", False):
        cursor.execute("UPDATE icp_profiles SET is_active = 0 WHERE is_active = 1")

    cursor.execute("""
        UPDATE icp_profiles SET 
            name = ?, is_active = ?, target_industries = ?, target_locations = ?,
            target_titles = ?, target_company_types = ?, target_keywords = ?,
            exclude_keywords = ?, industry_weight = ?, location_weight = ?,
            title_weight = ?, company_weight = ?, keyword_weight = ?,
            exclude_weight = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        data.get("name", "Default ICP"),
        1 if data.get("is_active", False) else 0,
        json.dumps(data.get("target_industries", [])),
        json.dumps(data.get("target_locations", [])),
        json.dumps(data.get("target_titles", [])),
        json.dumps(data.get("target_company_types", [])),
        json.dumps(data.get("target_keywords", [])),
        json.dumps(data.get("exclude_keywords", [])),
        data.get("industry_weight", 25),
        data.get("location_weight", 15),
        data.get("title_weight", 20),
        data.get("company_weight", 15),
        data.get("keyword_weight", 10),
        data.get("exclude_weight", -15),
        profile_id
    ))
    conn.commit()
    conn.close()
    return {"success": True}


def create_icp_profile(data: dict):
    """Create a new ICP profile."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO icp_profiles (name, target_industries, target_locations, target_titles,
            target_company_types, target_keywords, exclude_keywords, industry_weight,
            location_weight, title_weight, company_weight, keyword_weight, exclude_weight)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("name", "New ICP Profile"),
        json.dumps(data.get("target_industries", [])),
        json.dumps(data.get("target_locations", [])),
        json.dumps(data.get("target_titles", [])),
        json.dumps(data.get("target_company_types", [])),
        json.dumps(data.get("target_keywords", [])),
        json.dumps(data.get("exclude_keywords", [])),
        data.get("industry_weight", 25),
        data.get("location_weight", 15),
        data.get("title_weight", 20),
        data.get("company_weight", 15),
        data.get("keyword_weight", 10),
        data.get("exclude_weight", -15),
    ))
    conn.commit()
    profile_id = cursor.lastrowid
    conn.close()
    return {"success": True, "id": profile_id}


def get_all_icp_profiles():
    """Get all ICP profiles."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, is_active, industry_weight, location_weight, title_weight, "
        "company_weight, keyword_weight, exclude_weight, created_at "
        "FROM icp_profiles ORDER BY is_active DESC, created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_icp_profile(profile_id: int):
    """Delete an ICP profile."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM icp_profiles WHERE id = ?", (profile_id,))
    conn.commit()
    conn.close()
    return {"success": True}


def score_prospect_against_icp(prospect_data: dict, icp_profile: dict = None) -> dict:
    """Score a prospect against the ICP profile.

    Returns score breakdown and whether they match the ICP.
    """
    if icp_profile is None:
        icp_profile = get_active_icp()

    breakdown = {
        "industry_match": 0,
        "location_match": 0,
        "title_match": 0,
        "company_match": 0,
        "keyword_match": 0,
        "exclusion_penalty": 0,
        "icp_total": 0,
    }

    all_text = " ".join(filter(None, [
        prospect_data.get("bio", ""),
        prospect_data.get("about", ""),
        prospect_data.get("job_title", ""),
        prospect_data.get("industry", ""),
        prospect_data.get("company", ""),
        prospect_data.get("location", ""),
        prospect_data.get("notes", ""),
    ])).lower()

    name = prospect_data.get("name", "").lower()
    company = prospect_data.get("company", "").lower()
    title = prospect_data.get("job_title", "").lower()
    industry = prospect_data.get("industry", "").lower()
    location = prospect_data.get("location", "").lower()

    # Industry matching
    target_industries = [i.lower() for i in icp_profile.get("target_industries", [])]
    industry_match = any(
        kw in all_text for kw in target_industries
    ) or any(kw in (industry or "") for kw in target_industries)
    if industry_match:
        breakdown["industry_match"] = icp_profile.get("industry_weight", 25)

    # Location matching
    target_locations = [l.lower() for l in icp_profile.get("target_locations", [])]
    location_match = any(kw in (location or "") for kw in target_locations)
    if location_match:
        breakdown["location_match"] = icp_profile.get("location_weight", 15)

    # Title matching
    target_titles = [t.lower() for t in icp_profile.get("target_titles", [])]
    title_match = any(tk in title for tk in target_titles) or any(tk in all_text for tk in target_titles)
    if title_match:
        breakdown["title_match"] = icp_profile.get("title_weight", 20)

    # Company type matching
    target_company_types = [c.lower() for c in icp_profile.get("target_company_types", [])]
    company_match = any(ct in (company or "") for ct in target_company_types)
    if company_match:
        breakdown["company_match"] = icp_profile.get("company_weight", 15)

    # Keyword matching
    target_keywords = [k.lower() for k in icp_profile.get("target_keywords", [])]
    keyword_match = any(kw in all_text for kw in target_keywords)
    if keyword_match:
        breakdown["keyword_match"] = icp_profile.get("keyword_weight", 10)

    # Exclusion penalty
    exclude_keywords = [k.lower() for k in icp_profile.get("exclude_keywords", [])]
    exclusion_match = any(kw in all_text for kw in exclude_keywords)
    if exclusion_match:
        breakdown["exclusion_penalty"] = icp_profile.get("exclude_weight", -15)

    icp_total = (breakdown["industry_match"] + breakdown["location_match"] +
                 breakdown["title_match"] + breakdown["company_match"] +
                 breakdown["keyword_match"] + breakdown["exclusion_penalty"])

    icp_total = max(0, min(icp_total, icp_profile.get("max_score", 100)))
    breakdown["icp_total"] = icp_total

    # Determine if they match ICP
    meets_threshold = icp_total >= (icp_profile.get("max_score", 100) * 0.5)

    return {
        "icp_score": round(icp_total, 1),
        "meets_icp": meets_threshold,
        "breakdown": breakdown,
        "industry_match": industry_match,
        "location_match": location_match,
        "title_match": title_match,
        "company_match": company_match,
        "keyword_match": keyword_match,
        "exclusion_triggered": exclusion_match,
    }


def update_prospect_icp_score(prospect_id: int, icp_score: float, icp_breakdown: dict):
    """Update a prospect's ICP score in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE prospects SET score = ?, score_breakdown = ?, priority = ? WHERE id = ?
    """, (
        round(icp_score),
        json.dumps(icp_breakdown),
        "HIGH" if icp_score >= 55 else ("MEDIUM" if icp_score >= 30 else "LOW"),
        prospect_id
    ))
    conn.commit()
    conn.close()
