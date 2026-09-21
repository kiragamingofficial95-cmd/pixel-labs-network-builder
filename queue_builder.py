"""Daily networking queue builder for Pixel Labs Network Builder."""
from database import get_connection
from models import Prospect
from config import CATEGORY_PRESETS, CATEGORY_KEYS, CATEGORY_LABELS
from schemas import DailyQueueItem
from datetime import date


def build_daily_queue(target: int = 20) -> dict:
    """Build a balanced daily networking queue.

    Ensures category diversity by distributing prospects across categories.
    """
    # Get category targets
    preset = CATEGORY_PRESETS.get(target, CATEGORY_PRESETS[20])
    if target == 10:
        targets = {"clients": 3, "referral_partners": 3, "agency_business": 2, "professional_network": 2}
    elif target == 15:
        targets = {"clients": 4, "referral_partners": 4, "agency_business": 4, "professional_network": 3}
    else:
        targets = preset

    # Adjust if total doesn't match target
    total_from_preset = sum(targets.values())
    if total_from_preset < target:
        targets["clients"] += (target - total_from_preset)
    elif total_from_preset > target:
        # Reduce from the largest category
        max_key = max(targets, key=targets.get)
        targets[max_key] -= (total_from_preset - target)

    conn = get_connection()
    cursor = conn.cursor()

    # Build network balance awareness
    cursor.execute("SELECT category, COUNT(*) as count FROM prospects WHERE status != 'DO_NOT_CONTACT' GROUP BY category")
    category_counts = {row["category"]: row["count"] for row in cursor.fetchall()}

    # Check for network balance - if one category dominates, boost underrepresented ones
    total_active = sum(category_counts.values())
    if total_active > 0:
        client_pct = category_counts.get("CLIENT", 0) / total_active
        if client_pct > 0.6:
            # Network is too concentrated in clients, boost others
            targets["referral_partners"] += 1
            targets["agency_business"] += 1
            targets["clients"] -= 2
            targets["professional_network"] += 1

    # Normalize targets to exactly match the requested number
    current_total = sum(targets.values())
    if current_total != target:
        diff = target - current_total
        if diff > 0:
            targets["professional_network"] += diff
        else:
            excess_key = max(targets, key=targets.get)
            targets[excess_key] += diff  # diff is negative

    queue = {
        "CLIENT": [],
        "REFERRAL_PARTNER": [],
        "AGENCY_BUSINESS": [],
        "PROFESSIONAL_NETWORK": [],
        "OTHER": [],
    }

    category_order = ["CLIENT", "REFERRAL_PARTNER", "AGENCY_BUSINESS", "PROFESSIONAL_NETWORK"]
    targets_remaining = dict(targets)

    for cat in category_order:
        count_needed = targets_remaining.get(cat.lower().replace("_", "_"), 0)
        if count_needed <= 0:
            continue

        # Check how many we already have in queue from this category
        # Select highest-scoring prospects from this category that haven't been contacted
        placeholders = ",".join(["?" for _ in range(len(category_order))])
        excluded_statuses = ("DO_NOT_CONTACT",)

        # Get available prospects in this category, sorted by score descending
        cursor.execute(f"""
            SELECT * FROM prospects 
            WHERE category = ? AND status != 'DO_NOT_CONTACT'
            ORDER BY score DESC, RANDOM()
            LIMIT ?
        """, (cat, count_needed * 3))  # Get more to filter later

        candidates = cursor.fetchall()

        # Filter out already in today's queue or already connected
        selected = []
        for row in candidates:
            if len(selected) >= count_needed:
                break
            prospect = Prospect.from_row(row)
            # Skip if already sent connection
            if prospect.status in ("CONNECTION_SENT", "CONNECTED", "FOLLOW_UP"):
                continue
            selected.append(prospect)

        queue[cat] = selected[:count_needed]

    # Fill remaining slots from OTHER or highest remaining
    total_queued = sum(len(v) for v in queue.values())
    if total_queued < target:
        needed = target - total_queued
        cursor.execute(f"""
            SELECT * FROM prospects 
            WHERE status NOT IN ('DO_NOT_CONTACT', 'CONNECTION_SENT', 'CONNECTED', 'FOLLOW_UP')
            AND category = 'OTHER'
            ORDER BY score DESC, RANDOM()
            LIMIT ?
        """, (needed * 2,))
        for row in cursor.fetchall():
            if len(queue["OTHER"]) >= needed:
                break
            queue["OTHER"].append(Prospect.from_row(row))

    # Format the queue
    formatted_queue = {}
    category_counts_actual = {}

    for cat_key in category_order + ["OTHER"]:
        cat_prospects = queue[cat_key]
        formatted_queue[CATEGORY_LABELS.get(cat_key, cat_key)] = []

        for prospect in cat_prospects:
            item = DailyQueueItem(
                name=prospect.name,
                job_title=prospect.job_title,
                company=prospect.company,
                category=prospect.category,
                score=prospect.score,
                priority=prospect.priority,
                relationship_type=prospect.relationship_type,
                why_relevant=prospect.why_relevant,
                personalization_point=prospect.personalization_point,
                connection_note=prospect.connection_note,
                follow_up_topic=prospect.follow_up_topic,
                linkedin_url=prospect.linkedin_url,
            )
            formatted_queue[CATEGORY_LABELS.get(cat_key, cat_key)].append(item.to_dict())

        category_counts_actual[CATEGORY_LABELS.get(cat_key, cat_key)] = len(formatted_queue[CATEGORY_LABELS.get(cat_key, cat_key)])

    # Create today's target record
    today = date.today().isoformat()
    cursor.execute("SELECT id FROM daily_targets WHERE target_date = ?", (today,))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("UPDATE daily_targets SET total_target = ?, clients_count = ?, referral_partners_count = ?, agency_business_count = ?, professional_network_count = ? WHERE target_date = ?",
                       (target, targets.get("clients", 5), targets.get("referral_partners", 5),
                        targets.get("agency_business", 5), targets.get("professional_network", 5), today))
    else:
        cursor.execute("INSERT INTO daily_targets (target_date, total_target, clients_count, referral_partners_count, agency_business_count, professional_network_count) VALUES (?, ?, ?, ?, ?, ?)",
                       (today, target, targets.get("clients", 5), targets.get("referral_partners", 5),
                        targets.get("agency_business", 5), targets.get("professional_network", 5)))
    conn.commit()
    conn.close()

    return {
        "date": today,
        "total_target": target,
        "targets": targets,
        "queue": formatted_queue,
        "actual_counts": category_counts_actual,
    }


def get_queue_stats():
    """Get statistics about the current queue."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT category, COUNT(*) as count FROM prospects WHERE status = 'NEW' GROUP BY category")
    new_by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) as total FROM prospects WHERE status = 'NEW'")
    total_new = cursor.fetchone()["total"]

    cursor.execute("SELECT category, COUNT(*) as count FROM prospects WHERE status = 'CONNECTION_SENT' GROUP BY category")
    sent_by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("SELECT category, COUNT(*) as count FROM prospects WHERE status = 'CONNECTED' GROUP BY category")
    connected_by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

    today = date.today().isoformat()
    cursor.execute("SELECT COUNT(*) as count FROM prospects WHERE date_added = ?", (today,))
    today_count = cursor.fetchone()["count"]

    conn.close()

    return {
        "total_new": total_new,
        "new_by_category": new_by_category,
        "sent_by_category": sent_by_category,
        "connected_by_category": connected_by_category,
        "today_count": today_count,
    }
