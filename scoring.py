"""Scoring engine for Pixel Labs Network Builder."""
import re
from config import SCORING_WEIGHTS
from models import Prospect


# Industry keywords that match Pixel Labs' target market
PIXEL_LABS_TARGET_INDUSTRIES = [
    "contracting", "contractor", "landscaping", "landscaper", "home services",
    "home service", "service business", "service business owner", "local service",
    "plumbing", "electrical", "hvac", "roofing", "painting", "flooring",
    "construction", "renovation", "remodeling", "handyman", "exteriors",
    "pool", "pest control", "roofing", "siding", "windows", "gutters",
    "lawn care", "tree service", "fencing", "deck", "pressure washing",
    "janitorial", "commercial cleaning", "property management",
    "real estate", "mortgage", "insurance", "lawyer", "attorney",
    "medical", "dental", "chiropractic", "veterinary", "healthcare",
    "restaurant", "food service", "retail", "e-commerce", "saas",
]

REFERRAL_INDUSTRIES = [
    "marketing", "seo", "digital marketing", "advertising", "branding",
    "web design", "web development", "developer", "designer", "consultant",
    "consulting", "freelance", "freelancer", "agency", "saaS",
    "lead generation", "copywriting", "content marketing", "social media",
    "analytics", "ppc", "google ads", "facebook ads", "email marketing",
    "business consultant", "business coaching", "strategy", "growth",
    "public relations", "pr", "video production", "photography",
]

RELEVANT_ROLES = [
    "founder", "owner", "ceo", "cto", "coo", "president", "director",
    "manager", "partner", "principal", "operator", "entrepreneur",
    "business development", "bd", "vp", "vp of", "head of",
    "marketing manager", "growth manager", "digital lead",
]

LOCATION_KEYWORDS = []  # Could be configured by user


def analyze_text(text: str) -> dict:
    """Analyze text for keywords and return keyword matches."""
    if not text:
        return {}
    text_lower = text.lower()
    matches = {}
    matches["target_industry"] = any(kw in text_lower for kw in PIXEL_LABS_TARGET_INDUSTRIES)
    matches["referral_industry"] = any(kw in text_lower for kw in REFERRAL_INDUSTRIES)
    matches["relevant_role"] = any(kw in text_lower for kw in RELEVANT_ROLES)
    return matches


def score_prospect(prospect: Prospect) -> dict:
    """Score a prospect and return score breakdown."""
    breakdown = {
        "pixel_labs_target": 0,
        "founder_decision_maker": 0,
        "referral_potential": 0,
        "relevant_industry": 0,
        "relevant_location": 0,
        "relevant_role": 0,
        "personalization_info": 0,
        "professional_network_relevance": 0,
    }

    # Combine all text fields for analysis
    all_text_parts = []
    if prospect.bio:
        all_text_parts.append(prospect.bio)
    if prospect.about:
        all_text_parts.append(prospect.about)
    if prospect.job_title:
        all_text_parts.append(prospect.job_title)
    if prospect.industry:
        all_text_parts.append(prospect.industry)
    if prospect.company:
        all_text_parts.append(prospect.company)
    if prospect.notes:
        all_text_parts.append(prospect.notes)
    all_text = " ".join(all_text_parts)

    matches = analyze_text(all_text)

    # Score: Pixel Labs target/client fit
    if matches.get("target_industry"):
        breakdown["pixel_labs_target"] = SCORING_WEIGHTS["pixel_labs_target"]
    elif prospect.category == "CLIENT":
        breakdown["pixel_labs_target"] = int(SCORING_WEIGHTS["pixel_labs_target"] * 0.7)

    # Score: Founder/Owner/Decision Maker
    if matches.get("relevant_role") or any(kw in (prospect.job_title or "").lower() for kw in ["founder", "owner", "ceo", "president", "partner", "principle"]):
        breakdown["founder_decision_maker"] = SCORING_WEIGHTS["founder_decision_maker"]
    elif prospect.category in ["CLIENT", "AGENCY_BUSINESS"]:
        breakdown["founder_decision_maker"] = int(SCORING_WEIGHTS["founder_decision_maker"] * 0.5)

    # Score: Referral partner potential
    if matches.get("referral_industry") or prospect.category == "REFERRAL_PARTNER":
        breakdown["referral_potential"] = SCORING_WEIGHTS["referral_potential"]
    elif "marketing" in all_text.lower() or "web" in all_text.lower() or "seo" in all_text.lower():
        breakdown["referral_potential"] = int(SCORING_WEIGHTS["referral_potential"] * 0.7)

    # Score: Relevant industry
    if matches.get("target_industry") or matches.get("referral_industry") or prospect.category != "OTHER":
        breakdown["relevant_industry"] = SCORING_WEIGHTS["relevant_industry"]
    elif prospect.industry and any(w in prospect.industry.lower() for w in ["business", "services", "tech", "digital", "marketing"]):
        breakdown["relevant_industry"] = int(SCORING_WEIGHTS["relevant_industry"] * 0.6)

    # Score: Relevant location
    if prospect.location:
        breakdown["relevant_location"] = SCORING_WEIGHTS["relevant_location"]

    # Score: Relevant role/marketing/web/SEO/business
    if matches.get("relevant_role") or any(kw in (prospect.job_title or "").lower() for kw in ["marketing", "seo", "web", "development", "design", "sales"]):
        breakdown["relevant_role"] = SCORING_WEIGHTS["relevant_role"]
    elif prospect.category == "PROFESSIONAL_NETWORK":
        breakdown["relevant_role"] = int(SCORING_WEIGHTS["relevant_role"] * 0.6)

    # Score: Personalization information available
    if prospect.bio or prospect.about or prospect.notes:
        breakdown["personalization_info"] = SCORING_WEIGHTS["personalization_info"]

    # Score: Professional/network relevance
    if prospect.category == "PROFESSIONAL_NETWORK" or any(
        kw in all_text.lower() for kw in ["industry", "professional", "association", "community"]
    ):
        breakdown["professional_network_relevance"] = SCORING_WEIGHTS["professional_network_relevance"]

    total = sum(breakdown.values())

    # Apply ICP profile scoring if available
    try:
        from icp_profile import get_active_icp, score_prospect_against_icp
        icp_profile = get_active_icp()
        if icp_profile:
            prospect_data = {
                "name": prospect.name,
                "job_title": prospect.job_title or "",
                "company": prospect.company or "",
                "location": prospect.location or "",
                "industry": prospect.industry or "",
                "bio": prospect.bio or "",
                "about": prospect.about or "",
                "notes": prospect.notes or "",
            }
            icp_result = score_prospect_against_icp(prospect_data, icp_profile)
            breakdown["icp_score"] = icp_result["icp_score"]
            breakdown["icp_breakdown"] = icp_result["breakdown"]
            # Boost total score based on ICP match
            if icp_result["meets_icp"]:
                total += int(icp_result["icp_score"] * 0.3)  # ICP contributes up to 30% boost
    except Exception:
        pass

    # Determine priority
    if total >= 55:
        priority = "HIGH"
    elif total >= 30:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    # Determine category if not set
    if prospect.category == "OTHER":
        if breakdown["pixel_labs_target"] >= 15:
            prospect.category = "CLIENT"
        elif breakdown["referral_potential"] >= 10:
            prospect.category = "REFERRAL_PARTNER"
        elif breakdown["founder_decision_maker"] >= 10:
            prospect.category = "AGENCY_BUSINESS"
        else:
            prospect.category = "PROFESSIONAL_NETWORK"

    breakdown["total"] = total

    # Determine relationship type
    if prospect.category == "CLIENT":
        prospect.relationship_type = "Potential Client"
    elif prospect.category == "REFERRAL_PARTNER":
        prospect.relationship_type = "Potential Referral Partner"
    elif prospect.category == "AGENCY_BUSINESS":
        prospect.relationship_type = "Potential Collaborator"
    elif prospect.category == "PROFESSIONAL_NETWORK":
        prospect.relationship_type = "Industry Connection"
    else:
        prospect.relationship_type = "General Professional Network"

    return breakdown


def generate_why_relevant(prospect: Prospect, breakdown: dict) -> str:
    """Generate explanation of why this person is relevant."""
    reasons = []
    all_text = " ".join(filter(None, [prospect.bio, prospect.about, prospect.job_title, prospect.industry]))

    if breakdown["pixel_labs_target"] >= 15:
        reasons.append("Strong fit for Pixel Labs' target market of service businesses")
    if breakdown["founder_decision_maker"] >= 15:
        reasons.append("Founder or decision-maker with purchasing authority")
    if breakdown["referral_potential"] >= 10:
        reasons.append("Works in a field that commonly refers clients to web/SEO services")
    if breakdown["relevant_role"] >= 10:
        reasons.append("Works in a relevant role (marketing, web, business development)")
    if breakdown["relevant_industry"] >= 5:
        reasons.append("Operates in a relevant industry")
    if breakdown["personalization_info"] >= 5 and prospect.bio:
        reasons.append("Bio/background provides useful personalization information")

    if not reasons:
        reasons.append("Relevant to building a diverse professional network")

    return "; ".join(reasons)


def generate_personalization_point(prospect: Prospect) -> str:
    """Generate a personalization point based on available data."""
    parts = []

    if prospect.company:
        parts.append(f"their work at {prospect.company}")
    if prospect.job_title:
        parts.append(f"their role as {prospect.job_title}")
    if prospect.industry:
        parts.append(f"their work in {prospect.industry}")
    if prospect.location:
        parts.append(f"their location in {prospect.location}")
    if prospect.bio and len(prospect.bio) > 20:
        bio_snippet = prospect.bio[:100].rsplit(' ', 1)[0] + "..."
        parts.append(f"their background: {bio_snippet}")

    if not parts:
        return "Insufficient information for personalization."

    return "Learned about " + ", and ".join(parts[:3]) + "."


def generate_connection_note(prospect: Prospect, breakdown: dict) -> str:
    """Generate a connection request suggestion."""
    all_text = " ".join(filter(None, [prospect.bio, prospect.about, prospect.job_title]))
    matches = analyze_text(all_text)

    name = prospect.name.split()[0] if prospect.name else "there"
    company = prospect.company or "your company"

    if matches.get("target_industry") or prospect.category == "CLIENT":
        return (
            f"Hey {name} — came across {company} while looking at local service businesses. "
            f"I'm building Pixel Labs around websites and digital systems for service companies. "
            f"Would be great to connect."
        )[:299]
    elif matches.get("referral_industry") or prospect.category == "REFERRAL_PARTNER":
        return (
            f"Hi {name} — I've been following the {prospect.industry or 'marketing'} space and "
            f"noticed your work at {company}. I'm building Pixel Labs around web and SEO systems "
            f"for service businesses. Would love to connect and see how we might help each other."
        )[:299]
    elif breakdown["founder_decision_maker"] >= 15:
        return (
            f"Hi {name} — loved what I saw at {company}. I'm building Pixel Labs around digital "
            f"systems for local businesses. Would be great to connect with a fellow business owner."
        )[:299]
    else:
        return (
            f"Hi {name} — came across your profile while building my professional network around "
            f"digital services and local business. I'm Pixel Labs, focused on websites and digital "
            f"systems for service companies. Would be great to connect."
        )[:299]
