"""History service for Pixel Labs Network Builder."""
from datetime import datetime, date
from database import get_connection, add_activity


def _now():
    """Get current datetime string."""
    return datetime.now().isoformat()


def mark_action(prospect_id: int, action: str, notes: str = "", details: str = ""):
    """Mark an action on a prospect."""
    conn = get_connection()
    cursor = conn.cursor()

    valid_actions = {
        "REVIEW": "REVIEW",
        "CONNECTION_SENT": "CONNECTION_SENT",
        "CONNECTED": "CONNECTED",
        "FOLLOW_UP": "FOLLOW_UP",
        "NOT_INTERESTED": "NOT_INTERESTED",
        "DO_NOT_CONTACT": "DO_NOT_CONTACT",
    }

    if action not in valid_actions:
        conn.close()
        return {"success": False, "message": f"Invalid action: {action}"}

    cursor.execute("UPDATE prospects SET status = ?, last_action = ?, notes = ? WHERE id = ?",
                   (action, _now(), notes, prospect_id))
    add_activity(prospect_id, action, details or notes)
    conn.commit()
    conn.close()
    return {"success": True, "action": action}


def add_note(prospect_id: int, note: str):
    """Add a note to a prospect."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE prospects SET notes = ?, last_action = ? WHERE id = ?",
                   (note, _now(), prospect_id))
    conn.commit()
    conn.close()
    return {"success": True}


def update_follow_up(prospect_id: int, topic: str):
    """Update follow-up topic for a prospect."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE prospects SET follow_up_topic = ?, last_action = ? WHERE id = ?",
                   (topic, _now(), prospect_id))
    conn.commit()
    conn.close()
    return {"success": True}


def get_history(limit: int = 50, offset: int = 0):
    """Get activity history."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT al.*, p.name, p.company, p.category 
        FROM activity_log al 
        LEFT JOIN prospects p ON al.prospect_id = p.id 
        ORDER BY al.timestamp DESC 
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cursor.fetchall()

    history = []
    for row in rows:
        history.append({
            "id": row["id"],
            "prospect_id": row["prospect_id"],
            "name": row["name"],
            "company": row["company"],
            "category": row["category"],
            "action": row["action"],
            "details": row["details"],
            "timestamp": row["timestamp"],
        })

    conn.close()
    return history


def get_daily_stats():
    """Get today's action statistics."""
    today = date.today().isoformat()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT status, COUNT(*) as count FROM prospects WHERE date_added = ? GROUP BY status", (today,))
    today_stats = {row["status"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT COUNT(*) as total FROM prospects 
        WHERE date_added = ? AND (status = 'CONNECTION_SENT' OR status = 'CONNECTED')
    """, (today,))
    sent_today = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE date_added = ?", (today,))
    total_today = cursor.fetchone()["total"]

    conn.close()
    return {
        "today": today,
        "stats": today_stats,
        "connection_sent_or_connected": sent_today,
        "total_today": total_today,
    }
