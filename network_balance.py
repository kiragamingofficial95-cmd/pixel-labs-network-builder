"""Network balance analyzer for Pixel Labs Network Builder."""
from database import get_connection


def get_network_balance() -> dict:
    """Analyze network balance and provide recommendations."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT category, COUNT(*) as count FROM prospects WHERE status != 'DO_NOT_CONTACT' GROUP BY category")
    rows = cursor.fetchall()
    conn.close()

    total = sum(row["count"] for row in rows)
    if total == 0:
        return {
            "balance": {},
            "total": 0,
            "is_balanced": True,
            "message": "No prospects in the database yet. Import or add prospects to start building your network.",
            "recommendations": [],
        }

    category_labels = {
        "CLIENT": "Clients",
        "REFERRAL_PARTNER": "Referral Partners",
        "AGENCY_BUSINESS": "Agency / Business",
        "PROFESSIONAL_NETWORK": "Professional Network",
        "OTHER": "Other",
    }

    balance = {}
    for row in rows:
        cat = row["category"]
        count = row["count"]
        pct = (count / total) * 100
        balance[cat] = {"count": count, "percentage": round(pct, 1)}

    # Check balance
    client_pct = balance.get("CLIENT", {}).get("percentage", 0)
    is_balanced = 30 <= client_pct <= 50  # Clients should be 30-50% of active network

    message = ""
    recommendations = []

    if client_pct > 50:
        message = f"Your network is currently heavily concentrated in potential clients ({client_pct:.0f}%)."
        recommendations.append("Consider adding more referral partners and agency connections.")
        recommendations.append("A balanced network includes people who can refer, collaborate, and teach.")
    elif client_pct < 20 and total > 5:
        message = f"Your network has very few potential clients ({client_pct:.0f}% of active network)."
        recommendations.append("Consider adding more potential clients to balance your network.")
    elif is_balanced:
        message = "Your network is well balanced across categories."
    else:
        message = f"Your network distribution: Clients {client_pct:.0f}% of active network."

    # Suggest category to boost
    if balance:
        min_cat = min(balance, key=lambda k: balance[k]["percentage"])
        max_cat = max(balance, key=lambda k: balance[k]["percentage"])
        if balance[min_cat]["percentage"] < 15 and total > 5:
            recommendations.append(f"Boost {category_labels.get(min_cat, min_cat)} - currently at only {balance[min_cat]['percentage']:.0f}%.")

    return {
        "balance": balance,
        "total": total,
        "is_balanced": is_balanced,
        "message": message,
        "recommendations": recommendations,
        "category_labels": category_labels,
    }


def get_category_recommendation_adjustments(current_targets: dict) -> dict:
    """Suggest adjustments to category targets based on current network balance."""
    balance = get_network_balance()
    adjustments = dict(current_targets)

    if not balance["balance"]:
        return adjustments

    client_pct = balance["balance"].get("CLIENT", {}).get("percentage", 0)
    ref_pct = balance["balance"].get("REFERRAL_PARTNER", {}).get("percentage", 0)
    agency_pct = balance["balance"].get("AGENCY_BUSINESS", {}).get("percentage", 0)
    prof_pct = balance["balance"].get("PROFESSIONAL_NETWORK", {}).get("percentage", 0)

    if client_pct > 50:
        adjustments["referral_partners"] = min(adjustments.get("referral_partners", 5) + 1, 8)
        adjustments["agency_business"] = min(adjustments.get("agency_business", 5) + 1, 8)
        adjustments["clients"] = max(adjustments.get("clients", 5) - 1, 2)
        adjustments["professional_network"] = min(adjustments.get("professional_network", 5) + 1, 8)
    elif ref_pct < 15 and balance["total"] > 5:
        adjustments["referral_partners"] = min(adjustments.get("referral_partners", 5) + 1, 8)

    # Re-normalize to 20 total if possible
    total = sum(adjustments.values())
    if total != 20:
        diff = 20 - total
        max_key = max(adjustments, key=adjustments.get)
        adjustments[max_key] += diff

    return adjustments
