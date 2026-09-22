"""AI client module for Pixel Labs Network Builder.

Filters and enriches LinkedIn profiles via Groq API.
Only qualifies profiles with REAL data - bio, experience, about section.
"""
import json
import os
from openai import OpenAI
from config import AI_BASE_URL, AI_API_KEY, AI_MODEL, AI_PROVIDER


def _has_minimum_data(profile: dict) -> bool:
    """Check if profile has enough data for Groq to make a real decision.

    A profile with just a name and title is NOT enough.
    We need at least bio OR experience OR about section OR a descriptive headline/job_title.
    """
    bio = (profile.get("bio") or "").strip()
    about = (profile.get("about") or "").strip()
    experience = (profile.get("experience") or "").strip()
    headline = (profile.get("headline") or "").strip()
    job_title = (profile.get("job_title") or "").strip()

    # Use headline or job_title for the headline check
    effective_headline = headline if headline else job_title

    # Need at least 50 chars of real content to qualify
    has_bio = len(bio) >= 50
    has_about = len(about) >= 50
    has_experience = len(experience) >= 50
    has_headline = len(effective_headline) >= 20

    # At least one substantive field
    return has_bio or has_about or has_experience or has_headline


def _build_profile_text(i: int, p: dict) -> str:
    """Build detailed profile text for Groq analysis."""
    lines = [f"Profile {i+1}:"]
    lines.append(f"Name: {p.get('name', 'N/A')}")
    lines.append(f"Title: {p.get('job_title', 'N/A')}")
    lines.append(f"Company: {p.get('company', 'N/A')}")
    lines.append(f"Industry: {p.get('industry', 'N/A')}")
    lines.append(f"Location: {p.get('location', 'N/A')}")

    # Headline - often has the best signal
    headline = p.get("headline", "")
    if headline:
        lines.append(f"Headline: {headline}")

    # Bio - what they write about themselves
    bio = (p.get("bio") or "")[:800]
    if bio:
        lines.append(f"Bio/Summary: {bio}")

    # About section - detailed self-description
    about = (p.get("about") or "")[:800]
    if about:
        lines.append(f"About: {about}")

    # Experience - job history, responsibilities
    experience = (p.get("experience") or "")[:600]
    if experience:
        lines.append(f"Experience: {experience}")

    # Current role details
    current_role = p.get("current_role", "")
    if current_role:
        lines.append(f"Current Role Details: {current_role}")

    # Education
    education = (p.get("education") or "")[:300]
    if education:
        lines.append(f"Education: {education}")

    lines.append("---")
    return "\n".join(lines)


class AIClient:
    """AI client for ICP filtering and profile enrichment."""

    def __init__(self):
        self.client = None
        self.available = False
        self.model = AI_MODEL
        self.provider = AI_PROVIDER

        if AI_API_KEY:
            try:
                self.client = OpenAI(base_url=AI_BASE_URL, api_key=AI_API_KEY)
                self.available = True
            except Exception:
                self.client = None
                self.available = False

    def filter_profiles_by_icp(self, profiles: list, icp_criteria: dict) -> dict:
        """Filter profiles against ICP using Groq.

        Only sends profiles with REAL data (bio, experience, about).
        Empty/insufficient profiles are marked as "insufficient_data" and skipped.
        """
        if not self.available or not profiles:
            return {"filtered": [], "total_input": len(profiles), "message": "AI not available"}

        # Separate profiles with enough data vs not enough
        qualified_for_scoring = []
        skipped_insufficient = []

        for i, p in enumerate(profiles[:50]):
            if _has_minimum_data(p):
                p["_original_index"] = i
                qualified_for_scoring.append(p)
            else:
                skipped_insufficient.append({
                    "index": i + 1,
                    "name": p.get("name", "Unknown"),
                    "icp_score": 0,
                    "meets_icp": False,
                    "reason": "Insufficient profile data - no bio, experience, or about section",
                    "data_quality": "insufficient",
                })

        if not qualified_for_scoring:
            return {
                "filtered": skipped_insufficient,
                "total_input": len(profiles),
                "qualified": 0,
                "insufficient_data": len(skipped_insufficient),
                "message": f"No profiles with enough data to qualify ({len(skipped_insufficient)} skipped)",
            }

        # Build profile text with full data
        profiles_text = []
        for i, p in enumerate(qualified_for_scoring):
            profiles_text.append(_build_profile_text(i + 1, p))

        profiles_combined = "\n\n".join(profiles_text)

        prompt = f"""You are a B2B sales intelligence analyst for Pixel Labs.

Pixel Labs builds high-converting websites, landing pages, and digital marketing systems for:
- Contractors (HVAC, plumbing, electrical, roofing, painting)
- Landscapers and lawn care companies
- Home service businesses (cleaning, pest control, handyman)
- Local service businesses that need more customers

You are evaluating LinkedIn profiles to find people who:
1. OWN or LEAD a local service business (not employees at big companies)
2. Would BENEFIT from a better website/digital presence
3. Are in a position to DECIDE on hiring a web agency
4. Have enough profile data to make a real assessment

ICP Criteria:
- Target Industries: {', '.join(icp_criteria.get('target_industries', [])) or 'Any local service business'}
- Target Titles: {', '.join(icp_criteria.get('target_titles', [])) or 'Owner, CEO, Founder, President'}
- Target Keywords: {', '.join(icp_criteria.get('target_keywords', [])) or 'service, local, contractor'}
- Exclude Keywords: {', '.join(icp_criteria.get('exclude_keywords', [])) or 'software, SaaS, corporate'}
- Target Locations: {', '.join(icp_criteria.get('target_locations', [])) or 'Any'}

Profiles to evaluate:
{profiles_combined}

For EACH profile, analyze their bio, experience, and about section to determine:
1. Do they OWN/LEAD a local service business? (not just work at one)
2. Would they benefit from Pixel Labs services?
3. Are they a decision-maker?
4. Is there enough data to make this call?

Return ONLY a JSON array with one object per profile:
{{
    "index": 1,
    "name": "Profile Name",
    "icp_score": 85,
    "meets_icp": true,
    "data_quality": "rich" | "moderate" | "thin",
    "reason": "Specific evidence from their profile about why they do/don't fit",
    "decision_maker": true/false,
    "business_type": "contractor" | "landscaper" | "home_services" | "agency" | "other",
    "estimated_revenue": "$500K-$1M" | "unknown",
    "pain_signals": ["outdated website", "no online booking", etc],
    "referral_potential": "high" | "medium" | "low" | "none"
}}

Scoring guide:
- 90-100: Perfect fit - owns local service business, clear need, decision maker
- 70-89: Good fit - likely owns/leads relevant business, some signals
- 50-69: Maybe - has some relevant traits but unclear
- 30-49: Unlikely - doesn't match core ICP
- 0-29: Not a fit - wrong industry, employee not owner, no relevant signals

IMPORTANT:
- Only use information ACTUALLY in the profile data. Never invent facts.
- A person with NO bio/about/experience should get data_quality: "thin" and score 0-20
- A person with a RICH bio showing they run a landscaping company should score 80+
- Be SPECIFIC in reasons - quote their actual profile text"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000,
            )
            content = response.choices[0].message.content.strip()

            try:
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    results = json.loads(json_str)

                    # Add back the skipped insufficient profiles
                    all_results = results + skipped_insufficient

                    # Sort by score descending
                    all_results.sort(key=lambda x: x.get("icp_score", 0), reverse=True)

                    qualified_count = len([r for r in results if r.get("meets_icp")])

                    return {
                        "filtered": all_results,
                        "total_input": len(profiles),
                        "qualified": qualified_count,
                        "insufficient_data": len(skipped_insufficient),
                        "scored": len(results),
                        "message": f"Scored {len(results)} profiles ({qualified_count} qualified), {len(skipped_insufficient)} skipped (insufficient data)",
                    }
            except (json.JSONDecodeError, ValueError):
                pass

            return {"filtered": [], "total_input": len(profiles), "message": "Failed to parse AI response"}
        except Exception as e:
            return {"filtered": [], "total_input": len(profiles), "message": f"AI error: {str(e)[:100]}"}

    def enrich_profiles(self, profiles: list) -> list:
        """Enrich qualified profiles with deep AI analysis.

        Only enriches profiles with score >= 60 and sufficient data.
        Sends FULL bio, experience, about to Groq for real insights.
        """
        if not self.available or not profiles:
            return []

        enriched = []
        for profile in profiles[:20]:
            # Skip profiles without enough data
            if not _has_minimum_data(profile):
                enriched.append({
                    "name": profile.get("name", ""),
                    "enriched": False,
                    "reason": "Insufficient data for enrichment",
                })
                continue

            name = profile.get("name", "N/A")
            title = profile.get("job_title", "")
            company = profile.get("company", "")
            industry = profile.get("industry", "")
            location = profile.get("location", "")
            bio = (profile.get("bio") or "")[:1000]
            about = (profile.get("about") or "")[:1000]
            experience = (profile.get("experience") or "")[:800]
            headline = profile.get("headline", "")
            education = (profile.get("education") or "")[:300]

            prompt = f"""You are a B2B sales intelligence analyst for Pixel Labs Network Builder.

Pixel Labs builds high-converting websites and digital marketing systems for contractors, landscapers, and local service businesses.

Analyze this LinkedIn profile in depth and generate actionable intelligence.

PROFILE DATA:
- Name: {name}
- Headline: {headline}
- Title: {title}
- Company: {company}
- Industry: {industry}
- Location: {location}
- Bio: {bio}
- About: {about}
- Experience: {experience}
- Education: {education}

Generate a detailed analysis as JSON:
{{
    "name": "{name}",
    "company": "{company}",
    "enriched": true,

    "business_analysis": {{
        "type": "contractor" | "landscaper" | "home_services" | "agency" | "other",
        "estimated_size": "solo" | "small (2-10)" | "medium (10-50)" | "large (50+)" | "unknown",
        "estimated_revenue": "$0-100K" | "$100K-500K" | "$500K-1M" | "$1M+" | "unknown",
        "years_in_business": "estimated years",
        "service_area": "local" | "regional" | "national"
    }},

    "digital_presence_analysis": {{
        "likely_has_website": true/false/unknown,
        "website_quality_guess": "professional" | "basic" | "outdated" | "none",
        "seo_awareness": "high" | "medium" | "low" | "none",
        "social_media_presence": "active" | "minimal" | "none"
    }},

    "pain_points": [
        "Specific problem Pixel Labs could solve based on their profile",
        "Another pain point inferred from their business type",
        "Third pain point based on industry patterns"
    ],

    "pixel_labs_fit": {{
        "score": 85,
        "why": "Specific reason based on their actual profile text",
        "best_service": "website_redesign" | "landing_pages" | "seo" | "full_package",
        "estimated_budget": "$2K-5K" | "$5K-10K" | "$10K+" | "unknown"
    }},

    "outreach_strategy": {{
        "angle": "Specific, genuine angle for reaching out based on their profile",
        "personalization": "What to mention in first message based on their content",
        "best_channel": "linkedin_dm" | "email" | "phone" | "referral",
        "timing": "best time to reach out based on their activity"
    }},

    "referral_analysis": {{
        "potential": "high" | "medium" | "low" | "none",
        "why": "Reason based on their network and business type",
        "who_they_might_know": "Type of people in their network who could be Pixel Labs clients"
    }}
}}

IMPORTANT: Only use information ACTUALLY in the profile. Never invent facts.
Quote their actual bio/about text to support your analysis."""

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1500,
                )
                content = response.choices[0].message.content.strip()

                try:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        enrichment = json.loads(content[start:end])
                        enrichment["name"] = name
                        enrichment["company"] = company
                        enrichment["enriched"] = True
                        enriched.append(enrichment)
                    else:
                        enriched.append({"name": name, "enriched": False, "reason": "No JSON in response"})
                except (json.JSONDecodeError, ValueError):
                    enriched.append({"name": name, "enriched": False, "reason": "JSON parse error"})
            except Exception as e:
                enriched.append({"name": name, "enriched": False, "reason": str(e)[:100]})

        return enriched

    def filter_and_enrich_all(self, profiles: list, icp_criteria: dict) -> dict:
        """Filter profiles by ICP, then enrich only the qualified ones.

        Step 1: Filter all profiles (skips insufficient data automatically)
        Step 2: Enrich only qualified profiles (score >= 60)
        """
        filter_result = self.filter_profiles_by_icp(profiles, icp_criteria)

        if not filter_result.get("filtered"):
            return filter_result

        # Get qualified profiles (score >= 60, with real data)
        qualified = [f for f in filter_result["filtered"]
                     if f.get("icp_score", 0) >= 60 and f.get("data_quality") != "insufficient"]

        # Convert filtered results back to profile format for enrichment
        qualified_profiles = []
        for q in qualified:
            idx = q.get("index", 0) - 1
            if 0 <= idx < len(profiles):
                profile = profiles[idx].copy()
                profile["icp_score"] = q.get("icp_score", 0)
                profile["icp_reason"] = q.get("reason", "")
                profile["data_quality"] = q.get("data_quality", "unknown")
                qualified_profiles.append(profile)

        # Enrich only the qualified ones
        enrichment_results = self.enrich_profiles(qualified_profiles)

        return {
            "total_input": len(profiles),
            "scored": filter_result.get("scored", 0),
            "insufficient_data": filter_result.get("insufficient_data", 0),
            "qualified": len(qualified),
            "enriched": len(enrichment_results),
            "filter_result": filter_result,
            "enrichment_results": enrichment_results,
            "message": f"Scored {filter_result.get('scored', 0)}, {len(qualified)} qualified, {len(enrichment_results)} enriched",
        }


# Singleton instance
ai_client = AIClient()
