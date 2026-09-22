"""Database module for Pixel Labs Network Builder."""
import sqlite3
import os
from datetime import datetime
from config import DATABASE_URL


def get_connection():
    """Get a database connection."""
    os.makedirs(os.path.dirname(DATABASE_URL) or ".", exist_ok=True)
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize all database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            linkedin_url TEXT,
            company TEXT,
            job_title TEXT,
            location TEXT,
            industry TEXT,
            bio TEXT,
            about TEXT,
            category TEXT DEFAULT 'OTHER',
            score INTEGER DEFAULT 0,
            score_breakdown TEXT DEFAULT '{}',
            priority TEXT DEFAULT 'LOW',
            relationship_type TEXT DEFAULT 'General Professional Network',
            why_relevant TEXT,
            personalization_point TEXT,
            connection_note TEXT,
            follow_up_topic TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'NEW',
            last_action TIMESTAMP,
            notes TEXT,
            email TEXT,
            UNIQUE(name, company)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_date DATE UNIQUE,
            total_target INTEGER DEFAULT 20,
            clients_count INTEGER DEFAULT 5,
            referral_partners_count INTEGER DEFAULT 5,
            agency_business_count INTEGER DEFAULT 5,
            professional_network_count INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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

    # Add ICP columns to prospects if not exist
    cursor.execute("PRAGMA table_info(prospects)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "icp_score" not in columns:
        cursor.execute("ALTER TABLE prospects ADD COLUMN icp_score REAL DEFAULT 0")
    if "icp_breakdown" not in columns:
        cursor.execute("ALTER TABLE prospects ADD COLUMN icp_breakdown TEXT DEFAULT '{}'")

    conn.commit()
    conn.close()

    # Initialize default ICP profile
    from icp_profile import init_icp_profile
    init_icp_profile()


def get_stats():
    """Get network statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}
    cursor.execute("SELECT COUNT(*) as total FROM prospects")
    stats["total_researched"] = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE status = 'CONNECTION_SENT' OR status = 'CONNECTED'")
    stats["total_connection_sent"] = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE status = 'CONNECTED'")
    stats["total_connected"] = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE status = 'FOLLOW_UP'")
    stats["total_follow_ups"] = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE status = 'NOT_INTERESTED'")
    stats["total_not_interested"] = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE status = 'DO_NOT_CONTACT'")
    stats["total_do_not_contact"] = cursor.fetchone()["total"]

    for cat_key in ["CLIENT", "REFERRAL_PARTNER", "AGENCY_BUSINESS", "PROFESSIONAL_NETWORK", "OTHER"]:
        cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE category = ?", (cat_key,))
        stats[f"count_{cat_key.lower()}"] = cursor.fetchone()["total"]

    cursor.execute("SELECT category, COUNT(*) as total FROM prospects GROUP BY category")
    stats["category_breakdown"] = {row["category"]: row["total"] for row in cursor.fetchall()}

    cursor.execute("SELECT status, COUNT(*) as total FROM prospects GROUP BY status")
    stats["status_breakdown"] = {row["status"]: row["total"] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE category = 'CLIENT' AND (status = 'CONNECTION_SENT' OR status = 'CONNECTED')")
    stats["client_connections"] = cursor.fetchone()["total"]

    cursor.execute("SELECT status, COUNT(*) as total FROM prospects WHERE date_added = date('now')")
    stats["today_recommended"] = cursor.fetchone()["total"]

    conn.close()
    return stats


def add_activity(prospect_id, action, details=""):
    """Log an activity."""
    conn = get_connection()
    conn.execute("INSERT INTO activity_log (prospect_id, action, details) VALUES (?, ?, ?)",
                 (prospect_id, action, details))
    conn.commit()
    conn.close()
