"""Main FastAPI router for Pixel Labs Network Builder."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Body
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, date
import json
import os

from database import get_connection, init_db, get_stats
from models import Prospect
from schemas import *
from scoring import score_prospect, generate_why_relevant, generate_personalization_point, generate_connection_note
from importers import import_csv, import_xlsx, import_json, manual_add_prospect
from queue_builder import build_daily_queue, get_queue_stats
from network_balance import get_network_balance, get_category_recommendation_adjustments
from export_service import export_queue_csv, export_queue_csv_content
from history_service import mark_action, add_note, update_follow_up, get_history, get_daily_stats
from config import DAILY_TARGET
from ai_client import AIClient

router = APIRouter()
ai_client = AIClient()


# ============== PROSPECTS ==============

@router.get("/prospects")
def get_prospects(
    category: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("score", enum=["score", "name", "date_added"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
):
    """Get all prospects with filtering and sorting."""
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
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if search:
        search_term = f"%{search}%"
        query += " AND (name LIKE ? OR company LIKE ? OR job_title LIKE ? OR notes LIKE ?)"
        params.extend([search_term, search_term, search_term, search_term])

    order_map = {"score": "score", "name": "name", "date_added": "date_added"}
    order_col = order_map.get(sort_by, "score")
    query += f" ORDER BY {order_col} {'DESC' if sort_order == 'desc' else 'ASC'}"
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    total_query = "SELECT COUNT(*) as count FROM prospects WHERE 1=1"
    total_params = list(params[:-2])
    cursor.execute(total_query, total_params)
    total = cursor.fetchone()["count"]

    prospects = [Prospect.from_row(row).to_dict() for row in rows]
    conn.close()

    return {"prospects": prospects, "total": total, "limit": limit, "offset": offset}


@router.get("/prospects/{prospect_id}")
def get_prospect(prospect_id: int):
    """Get a single prospect by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Prospect not found")

    return Prospect.from_row(row).to_dict()


@router.post("/prospects")
def create_prospect(prospect_data: ProspectCreate):
    """Create a new prospect manually."""
    result = manual_add_prospect(prospect_data.model_dump())
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@router.post("/prospects/{prospect_id}/action")
def update_prospect_action(prospect_id: int, action_data: ProspectUpdate):
    """Update a prospect's status or notes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Prospect not found")

    updates = []
    params = []
    for field in ["status", "notes", "last_action", "connection_note", "follow_up_topic"]:
        val = getattr(action_data, field)
        if val is not None:
            updates.append(f"{field} = ?")
            params.append(val)

    params.append(prospect_id)
    cursor.execute(f"UPDATE prospects SET {', '.join(updates)} WHERE id = ?", params)
    add_activity(prospect_id, action_data.status or "UPDATED", "; ".join([f"{k}={v}" for k, v in action_data.model_dump().items() if v is not None]))
    conn.commit()
    conn.close()
    return {"success": True, "prospect_id": prospect_id}


@router.delete("/prospects/{prospect_id}")
def delete_prospect(prospect_id: int):
    """Delete a prospect."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM prospects WHERE id = ?", (prospect_id,))
    cursor.execute("DELETE FROM activity_log WHERE prospect_id = ?", (prospect_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ============== IMPORT ==============

@router.post("/import/csv")
async def import_csv_file(file: UploadFile = File(...)):
    """Import prospects from a CSV file."""
    content = await file.read()
    result = import_csv(content, file.filename)
    return {"success": True, "import_result": result}


@router.post("/import/xlsx")
async def import_xlsx_file(file: UploadFile = File(...)):
    """Import prospects from an XLSX file."""
    content = await file.read()
    result = import_xlsx(content, file.filename)
    return {"success": True, "import_result": result}


@router.post("/import/json")
async def import_json_file(file: UploadFile = File(...)):
    """Import prospects from a JSON file."""
    content = await file.read()
    result = import_json(content, file.filename)
    return {"success": True, "import_result": result}


@router.post("/import/manual")
def import_manual(prospect_data: ProspectCreate):
    """Add a prospect manually."""
    result = manual_add_prospect(prospect_data.model_dump())
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


# ============== DAILY QUEUE ==============

@router.get("/queue")
def get_daily_queue(target: int = Query(DAILY_TARGET, ge=5, le=50)):
    """Get today's balanced networking queue."""
    queue = build_daily_queue(target)
    return queue


@router.get("/queue/stats")
def get_queue_stats_endpoint():
    """Get queue statistics."""
    return get_queue_stats()


# ============== DASHBOARD ==============

@router.get("/dashboard")
def get_dashboard():
    """Get dashboard data."""
    stats = get_stats()
    balance = get_network_balance()
    queue_stats = get_queue_stats()
    daily_stats = get_daily_stats()

    # Get today's queue
    queue = build_daily_queue(DAILY_TARGET)

    # Network balance percentages
    network_balance = {}
    total_active = stats.get("total_researched", 0) - stats.get("total_do_not_contact", 0)
    if total_active > 0:
        for cat_key in ["CLIENT", "REFERRAL_PARTNER", "AGENCY_BUSINESS", "PROFESSIONAL_NETWORK"]:
            count = stats.get(f"count_{cat_key.lower()}", 0)
            network_balance[cat_key] = round((count / total_active) * 100, 1) if count > 0 else 0.0

    # Current daily targets
    current_targets = queue.get("targets", {})

    dashboard = {
        "today": daily_stats.get("today", date.today().isoformat()),
        "total_researched": stats["total_researched"],
        "total_connection_sent": stats["total_connection_sent"],
        "total_connected": stats["total_connected"],
        "total_follow_ups": stats["total_follow_ups"],
        "total_not_interested": stats["total_not_interested"],
        "total_do_not_contact": stats["total_do_not_contact"],
        "today_recommended": stats.get("today_recommended", 0),
        "category_breakdown": stats.get("category_breakdown", {}),
        "status_breakdown": stats.get("status_breakdown", {}),
        "network_balance": network_balance,
        "queue": queue,
        "current_targets": current_targets,
        "client_connections": stats.get("client_connections", 0),
        "queue_stats": queue_stats,
        "daily_stats": daily_stats,
    }

    return dashboard


# ============== NETWORK BALANCE ==============

@router.get("/balance")
def get_balance():
    """Get network balance analysis."""
    return get_network_balance()


# ============== EXPORT ==============

@router.get("/export")
def export_csv(category: Optional[str] = None, status: Optional[str] = None):
    """Export queue to CSV."""
    result = export_queue_csv(category, status)
    return result


@router.get("/export/content")
def export_csv_content(category: Optional[str] = None, status: Optional[str] = None):
    """Get CSV content for export."""
    content = export_queue_csv_content(category, status)
    return {"csv": content}


# ============== HISTORY ==============

@router.get("/history")
def get_history_endpoint(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """Get activity history."""
    return get_history(limit, offset)


@router.get("/history/daily")
def get_daily_history():
    """Get today's history stats."""
    return get_daily_stats()


# ============== AI ==============

@router.get("/ai/status")
def ai_status():
    """Check if AI is available."""
    return {
        "available": ai_client.available,
        "model": ai_client.model,
    }


@router.post("/ai/personalize")
def ai_personalize(prospect_data: dict):
    """Get AI-powered personalization for a prospect."""
    result = ai_client.generate_personalization(prospect_data)
    return result


# ============== SETTINGS ==============

@router.get("/settings")
def get_settings():
    """Get application settings."""
    from config import (DAILY_TARGET, DEFAULT_CLIENTS_PER_DAY, DEFAULT_REFERRAL_PARTNERS_PER_DAY,
                       DEFAULT_AGENCY_BUSINESS_PER_DAY, DEFAULT_PROFESSIONAL_NETWORK_PER_DAY,
                       CATEGORY_PRESETS)
    return {
        "daily_target": DAILY_TARGET,
        "category_presets": CATEGORY_PRESETS,
        "ai_available": ai_client.available,
        "ai_model": ai_client.model,
    }


@router.post("/settings/target")
def set_target(target_data: dict):
    """Set daily networking target."""
    from database import get_connection
    target = target_data.get("target", DAILY_TARGET)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('daily_target', ?)", (str(target),))
    conn.commit()
    conn.close()
    return {"success": True, "target": target}


# ============== ICP PROFILES ==============

@router.get("/icp")
def get_icp():
    """Get the active ICP profile."""
    from icp_profile import get_active_icp
    return get_active_icp()


@router.get("/icp/all")
def get_all_icp():
    """Get all ICP profiles."""
    from icp_profile import get_all_icp_profiles
    return get_all_icp_profiles()


@router.post("/icp")
def create_icp(data: dict):
    """Create a new ICP profile."""
    from icp_profile import create_icp_profile
    return create_icp_profile(data)


@router.put("/icp/{profile_id}")
def update_icp(profile_id: int, data: dict):
    """Update an ICP profile."""
    from icp_profile import save_icp_profile
    return save_icp_profile(profile_id, data)


@router.delete("/icp/{profile_id}")
def delete_icp(profile_id: int):
    """Delete an ICP profile."""
    from icp_profile import delete_icp_profile
    return delete_icp_profile(profile_id)


@router.get("/icp/score/{prospect_id}")
def score_prospect_icp(prospect_id: int):
    """Score a prospect against the ICP profile."""
    from icp_profile import get_active_icp, score_prospect_against_icp, update_prospect_icp_score
    from database import get_connection

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Prospect not found")

    prospect_data = {
        "name": row["name"],
        "job_title": row.get("job_title", ""),
        "company": row.get("company", ""),
        "location": row.get("location", ""),
        "industry": row.get("industry", ""),
        "bio": row.get("bio", ""),
        "about": row.get("about", ""),
        "notes": row.get("notes", ""),
    }

    icp_profile = get_active_icp()
    icp_result = score_prospect_against_icp(prospect_data, icp_profile)

    # Update the prospect with the ICP score
    update_prospect_icp_score(prospect_id, icp_result["icp_score"], icp_result["breakdown"])

    return icp_result


@router.get("/icp/batch-score")
def batch_score_icp():
    """Score all NEW prospects against the ICP profile."""
    from icp_profile import get_active_icp, score_prospect_against_icp, update_prospect_icp_score
    from database import get_connection

    icp_profile = get_active_icp()
    if not icp_profile:
        return {"message": "No active ICP profile found"}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prospects WHERE status = 'NEW'")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        prospect_data = {
            "name": row["name"],
            "job_title": row.get("job_title", ""),
            "company": row.get("company", ""),
            "location": row.get("location", ""),
            "industry": row.get("industry", ""),
            "bio": row.get("bio", ""),
            "about": row.get("about", ""),
            "notes": row.get("notes", ""),
        }
        icp_result = score_prospect_against_icp(prospect_data, icp_profile)
        update_prospect_icp_score(row["id"], icp_result["icp_score"], icp_result["breakdown"])
        results.append({
            "id": row["id"],
            "name": row["name"],
            "icp_score": icp_result["icp_score"],
            "meets_icp": icp_result["meets_icp"],
        })

    return {"scored": len(results), "results": results}


# ============== AI ENRICHMENT ==============

@router.post("/ai/filter-and-enrich")
def filter_and_enrich(data: dict):
    """Filter all prospects by ICP using AI, then enrich qualified ones.

    Expected data:
    - profiles: list of prospect dicts (optional, defaults to DB)
    - icp_criteria: dict with target_industries, target_titles, etc.
    """
    from ai_client import ai_client
    from database import get_connection
    from icp_profile import get_active_icp

    # Get profiles from DB if not provided
    profiles = data.get("profiles")
    if not profiles:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM prospects WHERE status != 'DO_NOT_CONTACT'")
        rows = cursor.fetchall()
        conn.close()
        profiles = []
        for row in rows:
            profiles.append({
                "name": row["name"],
                "job_title": row.get("job_title"),
                "company": row.get("company"),
                "location": row.get("location"),
                "industry": row.get("industry"),
                "bio": row.get("bio"),
                "about": row.get("about"),
                "notes": row.get("notes"),
                "linkedin_url": row.get("linkedin_url"),
            })

    icp_criteria = data.get("icp_criteria")
    if not icp_criteria:
        icp_profile = get_active_icp()
        if icp_profile:
            icp_criteria = {
                "target_industries": icp_profile.get("target_industries", []),
                "target_titles": icp_profile.get("target_titles", []),
                "target_keywords": icp_profile.get("target_keywords", []),
                "exclude_keywords": icp_profile.get("exclude_keywords", []),
                "target_locations": icp_profile.get("target_locations", []),
            }

    if not profiles:
        return {"message": "No profiles found", "total": 0}

    result = ai_client.filter_and_enrich_all(profiles, icp_criteria)
    return result


@router.post("/ai/enrich")
def enrich_profiles(data: dict):
    """Enrich already-qualified profiles with AI insights."""
    from ai_client import ai_client

    profiles = data.get("profiles", [])
    if not profiles:
        return {"message": "No profiles provided"}

    results = ai_client.enrich_profiles(profiles)
    return {"enriched": len(results), "results": results}


@router.get("/ai/status")
def ai_status():
    """Check AI provider status."""
    from ai_client import ai_client
    return {
        "available": ai_client.available,
        "provider": ai_client.provider,
        "model": ai_client.model,
        "base_url": AI_BASE_URL,
    }


# ============== LINKEDIN HELPERS ==============

@router.post("/linkedin/import-csv")
def import_linkedin_csv(data: dict):
    """Import LinkedIn connections from CSV export.

    LinkedIn allows exporting connections via:
    Settings > Data Privacy > Get a copy of your data > Connections

    Pass the CSV content as { "csv_content": "..." }
    """
    from linkedin_helper import import_linkedin_connections_csv

    csv_content = data.get("csv_content", "")
    if not csv_content:
        return {"error": "No CSV content provided"}

    return import_linkedin_connections_csv(csv_content)


@router.post("/linkedin/import-json")
def import_linkedin_json(data: dict):
    """Import LinkedIn profiles from JSON data.

    Pass an array of profile objects as { "profiles": [...] }
    """
    from linkedin_helper import import_linkedin_profiles_json

    profiles = data.get("profiles", [])
    if not profiles:
        return {"error": "No profiles provided"}

    return import_linkedin_profiles_json(profiles)


@router.get("/linkedin/search")
def search_profiles(
    query: str = "",
    industry: str = "",
    title: str = "",
    location: str = "",
    min_icp_score: int = 0,
    use_ai: bool = True,
):
    """Search imported profiles with optional AI filtering.

    This searches the LOCAL database of already-imported profiles.
    It does NOT scrape LinkedIn.
    """
    from linkedin_helper import search_and_filter_profiles
    return search_and_filter_profiles(query, industry, title, location, min_icp_score, use_ai)


@router.post("/linkedin/enrich/{profile_id}")
def enrich_linkedin_profile(profile_id: int):
    """Enrich a single profile with AI-generated insights."""
    from linkedin_helper import enrich_single_profile
    return enrich_single_profile(profile_id)


# ============== LINKEDIN SCRAPING ==============

@router.post("/linkedin/login")
async def linkedin_login(data: dict):
    """Login to LinkedIn for scraping.

    Pass { "email": "...", "password": "..." }
    """
    from linkedin_scraper import scraper

    email = data.get("email", "")
    password = data.get("password", "")

    if not email or not password:
        return {"error": "Email and password required"}

    await scraper.start()
    result = await scraper.login(email, password)
    await scraper.stop()
    return result


@router.post("/linkedin/scrape-search")
async def scrape_linkedin_search(data: dict):
    """Search LinkedIn for profiles and scrape them.

    Pass {
        "keywords": "landscaping owner",
        "title": "CEO",
        "company": "",
        "location": "Texas",
        "industry": "",
        "max_results": 25,
        "filter_by_icp": true,
        "enrich_qualified": true
    }

    Scrapes LinkedIn search results, stores profiles in DB,
    then uses Groq to filter by ICP and enrich qualified ones.
    """
    from linkedin_scraper import scraper
    from database import get_connection
    from icp_profile import get_active_icp
    from ai_client import ai_client

    keywords = data.get("keywords", "")
    title = data.get("title", "")
    company = data.get("company", "")
    location = data.get("location", "")
    industry = data.get("industry", "")
    max_results = data.get("max_results", 25)
    filter_by_icp = data.get("filter_by_icp", True)
    enrich_qualified = data.get("enrich_qualified", True)

    # Step 1: Scrape LinkedIn
    await scraper.start()
    search_result = await scraper.search_profiles(
        keywords=keywords,
        title=title,
        company=company,
        location=location,
        industry=industry,
        max_results=max_results,
    )
    await scraper.stop()

    if search_result.get("error"):
        return {"error": search_result["error"]}

    profiles = search_result.get("profiles", [])

    # Step 2: Store in database
    conn = get_connection()
    cursor = conn.cursor()
    stored = 0
    skipped = 0
    stored_profiles = []

    for p in profiles:
        name = p.get("name", "").strip()
        if not name:
            skipped += 1
            continue

        company_val = p.get("company", "")
        # Deduplicate
        cursor.execute("SELECT id FROM prospects WHERE name = ? AND company = ?", (name, company_val))
        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute(
            """INSERT INTO prospects (name, job_title, company, location, industry, bio, linkedin_url, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW')""",
            (
                name,
                p.get("job_title", ""),
                company_val,
                p.get("location", ""),
                industry,
                p.get("bio", ""),
                p.get("linkedin_url", ""),
            )
        )
        stored_profiles.append({
            "id": cursor.lastrowid,
            "name": name,
            "job_title": p.get("job_title", ""),
            "company": company_val,
            "location": p.get("location", ""),
            "bio": p.get("bio", ""),
            "linkedin_url": p.get("linkedin_url", ""),
        })
        stored += 1

    conn.commit()
    conn.close()

    result = {
        "scraped": len(profiles),
        "stored": stored,
        "skipped": skipped,
        "profiles": stored_profiles,
    }

    # Step 3: Filter by ICP using Groq
    if filter_by_icp and stored_profiles and ai_client.available:
        icp_profile = get_active_icp()
        if icp_profile:
            icp_criteria = {
                "target_industries": icp_profile.get("target_industries", []),
                "target_titles": icp_profile.get("target_titles", []),
                "target_keywords": icp_profile.get("target_keywords", []),
                "exclude_keywords": icp_profile.get("exclude_keywords", []),
                "target_locations": icp_profile.get("target_locations", []),
            }
            filter_result = ai_client.filter_profiles_by_icp(stored_profiles, icp_criteria)
            result["icp_filter"] = filter_result

            # Step 4: Enrich qualified profiles
            if enrich_qualified and filter_result.get("filtered"):
                qualified = [f for f in filter_result["filtered"] if f.get("icp_score", 0) >= 60]
                qualified_profiles = []
                for q in qualified:
                    idx = q.get("index", 0) - 1
                    if 0 <= idx < len(stored_profiles):
                        qualified_profiles.append(stored_profiles[idx])

                if qualified_profiles:
                    enrichment = ai_client.enrich_profiles(qualified_profiles)
                    result["enrichment"] = enrichment
                    result["qualified_count"] = len(qualified)
                    result["enriched_count"] = len(enrichment)

    return result


@router.post("/linkedin/scrape-profile")
async def scrape_single_profile(data: dict):
    """Scrape a single LinkedIn profile page.

    Pass { "url": "https://www.linkedin.com/in/username/" }
    """
    from linkedin_scraper import scraper
    from database import get_connection

    url = data.get("url", "")
    if not url:
        return {"error": "LinkedIn URL required"}

    # Normalize URL
    if not url.startswith("http"):
        url = "https://www.linkedin.com/in/" + url

    await scraper.start()
    result = await scraper.scrape_profile(url)
    await scraper.stop()

    if result.get("error"):
        return {"error": result["error"]}

    profile = result.get("profile", {})

    # Store in database
    conn = get_connection()
    cursor = conn.cursor()

    name = profile.get("name", "")
    company = profile.get("company", "")

    # Check duplicate
    cursor.execute("SELECT id FROM prospects WHERE name = ? AND company = ?", (name, company))
    existing = cursor.fetchone()

    if existing:
        prospect_id = existing["id"]
        # Update existing
        cursor.execute(
            """UPDATE prospects SET job_title = COALESCE(?, job_title),
               location = COALESCE(?, location), bio = COALESCE(?, bio),
               linkedin_url = COALESCE(?, linkedin_url)
               WHERE id = ?""",
            (profile.get("job_title"), profile.get("location"), profile.get("bio"), url, prospect_id)
        )
    else:
        cursor.execute(
            """INSERT INTO prospects (name, job_title, company, location, industry, bio, linkedin_url, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW')""",
            (
                name,
                profile.get("job_title", ""),
                company,
                profile.get("location", ""),
                "",
                profile.get("bio", ""),
                url,
            )
        )
        prospect_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "success": True,
        "prospect_id": prospect_id,
        "profile": profile,
        "action": "updated" if existing else "created",
    }


@router.post("/linkedin/scrape-and-enrich")
async def scrape_and_enrich(data: dict):
    """Full pipeline: scrape LinkedIn search -> store -> ICP filter -> enrich.

    Pass {
        "keywords": "landscaping company owner Texas",
        "max_results": 10,
        "icp_criteria": { ... }  // optional, uses active ICP if not provided
    }
    """
    from linkedin_scraper import scraper
    from database import get_connection
    from icp_profile import get_active_icp
    from ai_client import ai_client

    keywords = data.get("keywords", "")
    max_results = data.get("max_results", 10)
    icp_criteria = data.get("icp_criteria")

    if not keywords:
        return {"error": "Keywords required"}

    # Step 1: Scrape
    await scraper.start()
    search_result = await scraper.search_profiles(keywords=keywords, max_results=max_results)
    await scraper.stop()

    if search_result.get("error"):
        return {"error": search_result["error"]}

    profiles = search_result.get("profiles", [])
    if not profiles:
        return {"message": "No profiles found", "profiles": []}

    # Step 2: Store
    conn = get_connection()
    cursor = conn.cursor()
    stored_profiles = []

    for p in profiles:
        name = p.get("name", "").strip()
        if not name:
            continue
        company_val = p.get("company", "")

        cursor.execute("SELECT id FROM prospects WHERE name = ? AND company = ?", (name, company_val))
        if cursor.fetchone():
            continue

        cursor.execute(
            """INSERT INTO prospects (name, job_title, company, location, bio, linkedin_url, status)
               VALUES (?, ?, ?, ?, ?, ?, 'NEW')""",
            (name, p.get("job_title", ""), company_val, p.get("location", ""), p.get("bio", ""), p.get("linkedin_url", ""))
        )
        stored_profiles.append({
            "id": cursor.lastrowid,
            "name": name,
            "job_title": p.get("job_title", ""),
            "company": company_val,
            "location": p.get("location", ""),
            "bio": p.get("bio", ""),
            "linkedin_url": p.get("linkedin_url", ""),
        })

    conn.commit()
    conn.close()

    # Step 3: ICP Filter + Enrich via Groq
    if not icp_criteria:
        icp_profile = get_active_icp()
        if icp_profile:
            icp_criteria = {
                "target_industries": icp_profile.get("target_industries", []),
                "target_titles": icp_profile.get("target_titles", []),
                "target_keywords": icp_profile.get("target_keywords", []),
                "exclude_keywords": icp_profile.get("exclude_keywords", []),
                "target_locations": icp_profile.get("target_locations", []),
            }

    result = {
        "scraped": len(profiles),
        "stored": len(stored_profiles),
        "profiles": stored_profiles,
    }

    if icp_criteria and stored_profiles and ai_client.available:
        # Filter
        filter_result = ai_client.filter_profiles_by_icp(stored_profiles, icp_criteria)
        result["icp_filter"] = filter_result

        # Enrich qualified
        qualified = [f for f in filter_result.get("filtered", []) if f.get("icp_score", 0) >= 60]
        qualified_profiles = []
        for q in qualified:
            idx = q.get("index", 0) - 1
            if 0 <= idx < len(stored_profiles):
                qualified_profiles.append(stored_profiles[idx])

        if qualified_profiles:
            enrichment = ai_client.enrich_profiles(qualified_profiles)
            result["enrichment"] = enrichment
            result["qualified_count"] = len(qualified)
            result["enriched_count"] = len(enrichment)

    return result


# ============== X-RAY SEARCH (Google) ==============

@router.post("/xray/search")
async def xray_search(data: dict):
    """Search Google for LinkedIn profiles using X-Ray technique.

    Supports multi-keyword search:
    - keywords="landscaping" -> single search
    - all_keywords=["landscaping", "HVAC", "plumbing"] -> separate searches per keyword
    """
    try:
        from xray_search import xray

        # Parse keywords - support both single and multi
        keywords = data.get("keywords", "")
        all_keywords = data.get("all_keywords", [])

        # If keywords string contains commas, split into list
        if keywords and "," in keywords:
            all_keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        elif keywords and not all_keywords:
            all_keywords = [keywords]

        await xray.start()
        result = await xray.search_xray(
            keywords=keywords,
            all_keywords=all_keywords if len(all_keywords) > 1 else None,
            title=data.get("title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            industry=data.get("industry", ""),
            max_results=data.get("max_results", 25),
            pages_to_search=data.get("pages_to_search", 3),
        )
        await xray.stop()
        return result
    except Exception as e:
        return {"error": str(e)[:500], "profiles": [], "total": 0}


@router.post("/xray/scrape-profile")
async def xray_scrape_profile(data: dict):
    """Scrape a single public LinkedIn profile (no login needed)."""
    try:
        from xray_search import xray
        url = data.get("url", "")
        if not url:
            return {"error": "LinkedIn URL required"}
        await xray.start()
        result = await xray.scrape_public_profile(url)
        await xray.stop()
        return result
    except Exception as e:
        return {"error": str(e)[:500]}


@router.post("/xray/search-and-store")
async def xray_search_and_store(data: dict):
    """X-Ray Google search -> scrape profiles -> store in DB. Supports multi-keyword."""
    from xray_search import xray
    from database import get_connection

    keywords = data.get("keywords", "")
    all_keywords = data.get("all_keywords", [])

    if keywords and "," in keywords:
        all_keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    elif keywords and not all_keywords:
        all_keywords = [keywords]

    title = data.get("title", "")
    company = data.get("company", "")
    location = data.get("location", "")
    industry = data.get("industry", "")
    max_results = data.get("max_results", 10)

    # Step 1: X-Ray search Google
    await xray.start()
    search_result = await xray.search_xray(
        keywords=keywords,
        all_keywords=all_keywords if len(all_keywords) > 1 else None,
        title=title, company=company,
        location=location, industry=industry,
        max_results=max_results, pages_to_search=2,
    )
    profiles = search_result.get("profiles", [])

    # Step 2: Scrape each public profile
    enriched_profiles = []
    for p in profiles[:max_results]:
        url = p.get("linkedin_url", "")
        if url:
            try:
                detail = await xray.scrape_public_profile(url)
                if detail.get("success") and detail.get("profile"):
                    merged = {**p, **detail["profile"]}
                    enriched_profiles.append(merged)
                else:
                    enriched_profiles.append(p)
            except Exception:
                enriched_profiles.append(p)
            await asyncio.sleep(2 + random.uniform(1, 3))
    await xray.stop()

    # Step 3: Store in database
    conn = get_connection()
    cursor = conn.cursor()
    stored = 0
    skipped = 0

    for p in enriched_profiles:
        name = p.get("name", "").strip()
        if not name:
            skipped += 1
            continue
        company_val = p.get("company", "")
        cursor.execute("SELECT id FROM prospects WHERE name = ? AND company = ?", (name, company_val))
        if cursor.fetchone():
            skipped += 1
            continue
        cursor.execute(
            """INSERT INTO prospects (name, job_title, company, location, industry, bio, linkedin_url, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW')""",
            (name, p.get("job_title", ""), company_val, p.get("location", ""),
             p.get("industry", ""), p.get("bio", ""), p.get("linkedin_url", ""))
        )
        stored += 1

    conn.commit()
    conn.close()

    return {
        "search_query": search_result.get("query", ""),
        "found": len(profiles),
        "scraped_details": len(enriched_profiles),
        "stored": stored,
        "skipped": skipped,
        "profiles": enriched_profiles,
    }


@router.post("/xray/full-pipeline")
async def xray_full_pipeline(data: dict):
    """Full pipeline: X-Ray search -> scrape -> store -> ICP filter -> enrich via Groq. Supports multi-keyword."""
    from xray_search import xray
    from database import get_connection
    from icp_profile import get_active_icp
    from ai_client import ai_client

    keywords = data.get("keywords", "")
    all_keywords = data.get("all_keywords", [])

    if keywords and "," in keywords:
        all_keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    elif keywords and not all_keywords:
        all_keywords = [keywords]

    title = data.get("title", "")
    company = data.get("company", "")
    location = data.get("location", "")
    industry = data.get("industry", "")
    max_results = data.get("max_results", 10)
    icp_criteria = data.get("icp_criteria")

    if not keywords and not title:
        return {"error": "At least keywords or title required"}

    # Step 1: X-Ray search
    await xray.start()
    search_result = await xray.search_xray(
        keywords=keywords,
        all_keywords=all_keywords if len(all_keywords) > 1 else None,
        title=title, company=company,
        location=location, industry=industry,
        max_results=max_results, pages_to_search=2,
    )
    profiles = search_result.get("profiles", [])

    # Step 2: Scrape each profile
    detailed_profiles = []
    for p in profiles[:max_results]:
        url = p.get("linkedin_url", "")
        if url:
            try:
                detail = await xray.scrape_public_profile(url)
                if detail.get("success") and detail.get("profile"):
                    merged = {**p, **detail["profile"]}
                    detailed_profiles.append(merged)
                else:
                    detailed_profiles.append(p)
            except Exception:
                detailed_profiles.append(p)
            await asyncio.sleep(2 + random.uniform(1, 3))
    await xray.stop()

    if not detailed_profiles:
        return {"message": "No profiles found", "profiles": []}

    # Step 3: Store in DB
    conn = get_connection()
    cursor = conn.cursor()
    stored_profiles = []

    for p in detailed_profiles:
        name = p.get("name", "").strip()
        if not name:
            continue
        company_val = p.get("company", "")
        cursor.execute("SELECT id FROM prospects WHERE name = ? AND company = ?", (name, company_val))
        if cursor.fetchone():
            continue
        cursor.execute(
            """INSERT INTO prospects (name, job_title, company, location, industry, bio, linkedin_url, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW')""",
            (name, p.get("job_title", ""), company_val, p.get("location", ""),
             p.get("industry", ""), p.get("bio", ""), p.get("linkedin_url", ""))
        )
        stored_profiles.append({
            "id": cursor.lastrowid, "name": name,
            "job_title": p.get("job_title", ""), "company": company_val,
            "location": p.get("location", ""), "industry": p.get("industry", ""),
            "bio": p.get("bio", ""), "linkedin_url": p.get("linkedin_url", ""),
        })
    conn.commit()
    conn.close()

    result = {
        "search_query": search_result.get("query", ""),
        "found": len(profiles),
        "stored": len(stored_profiles),
        "profiles": stored_profiles,
    }

    # Step 4: ICP filter + Enrich via Groq
    if not icp_criteria:
        icp_profile = get_active_icp()
        if icp_profile:
            icp_criteria = {
                "target_industries": icp_profile.get("target_industries", []),
                "target_titles": icp_profile.get("target_titles", []),
                "target_keywords": icp_profile.get("target_keywords", []),
                "exclude_keywords": icp_profile.get("exclude_keywords", []),
                "target_locations": icp_profile.get("target_locations", []),
            }

    if icp_criteria and stored_profiles and ai_client.available:
        filter_result = ai_client.filter_profiles_by_icp(stored_profiles, icp_criteria)
        result["icp_filter"] = filter_result

        qualified = [f for f in filter_result.get("filtered", []) if f.get("icp_score", 0) >= 60]
        qualified_profiles = []
        for q in qualified:
            idx = q.get("index", 0) - 1
            if 0 <= idx < len(stored_profiles):
                qualified_profiles.append(stored_profiles[idx])

        if qualified_profiles:
            enrichment = ai_client.enrich_profiles(qualified_profiles)
            result["enrichment"] = enrichment
            result["qualified_count"] = len(qualified)
            result["enriched_count"] = len(enrichment)

    return result
