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
