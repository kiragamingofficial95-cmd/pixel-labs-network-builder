"""AI client module for Pixel Labs Network Builder.

Supports Groq and OpenAI-compatible APIs for ICP filtering and profile enrichment.
"""
import json
import os
from openai import OpenAI
from config import AI_BASE_URL, AI_API_KEY, AI_MODEL, AI_PROVIDER


class AIClient:
    """AI client for ICP filtering and profile enrichment."""

    def __init__(self):
        """Initialize the AI client."""
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
        """Filter profiles against ICP criteria using AI.

        Returns filtered and scored profiles with reasoning.
        """
        if not self.available or not profiles:
            return {"filtered": [], "total_input": len(profiles), "message": "AI not available"}

        # Prepare profiles for batch processing
        profiles_text = []
        for i, p in enumerate(profiles[:50]):  # Limit to 50 for batch processing
            profiles_text.append(
                f"Profile {i+1}:\n"
                f"Name: {p.get('name', 'N/A')}\n"
                f"Title: {p.get('job_title', 'N/A')}\n"
                f"Company: {p.get('company', 'N/A')}\n"
                f"Industry: {p.get('industry', 'N/A')}\n"
                f"Location: {p.get('location', 'N/A')}\n"
                f"Bio: {p.get('bio', 'N/A')[:200]}\n"
                "---"
            )

        profiles_combined = "\n\n".join(profiles_text)

        prompt = f"""You are an ICP (Ideal Customer Profile) filtering expert for Pixel Labs Network Builder.

Pixel Labs builds high-converting websites and digital systems for contractors, landscapers, and local service businesses.

Given the following ICP criteria and prospect profiles, score each profile and return ONLY valid JSON.

ICP Criteria:
- Target Industries: {', '.join(icp_criteria.get('target_industries', []))}
- Target Titles: {', '.join(icp_criteria.get('target_titles', []))}
- Target Keywords: {', '.join(icp_criteria.get('target_keywords', []))}
- Exclude Keywords: {', '.join(icp_criteria.get('exclude_keywords', []))}
- Target Locations: {', '.join(icp_criteria.get('target_locations', []))}

Prospect Profiles:
{profiles_combined}

For each profile, return a JSON object with:
- "index": the profile number (1-based)
- "icp_score": score from 0-100 based on fit
- "meets_icp": true/false
- "reason": brief explanation
- "enrichment": AI-generated enrichment data including:
  - "company_size": estimated company size
  - "tech_stack_indicators": relevant tech indicators
  - "pain_points": potential pain points Pixel Labs could solve
  - "engagement_score": estimated likelihood of engagement

Return ONLY a JSON array of objects, one per profile. Do not include any other text.

IMPORTANT: Only use information from the profile data provided. Never invent facts."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000,
            )
            content = response.choices[0].message.content.strip()

            # Parse JSON from response
            try:
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    results = json.loads(json_str)
                    return {
                        "filtered": results,
                        "total_input": len(profiles),
                        "message": f"Filtered {len(results)} profiles",
                    }
            except (json.JSONDecodeError, ValueError):
                pass

            return {"filtered": [], "total_input": len(profiles), "message": "Failed to parse AI response"}
        except Exception as e:
            return {"filtered": [], "total_input": len(profiles), "message": f"AI error: {str(e)[:50]}"}

    def enrich_profiles(self, profiles: list) -> list:
        """Enrich profiles with AI-generated insights for qualified prospects.

        Takes profiles that scored well on ICP and enriches them with:
        - Pain points
        - Tech stack indicators
        - Engagement likelihood
        - Outreach angles
        """
        if not self.available or not profiles:
            return []

        enriched = []
        for profile in profiles[:20]:  # Limit to 20 for batch enrichment
            bio_text = profile.get("bio", "") or ""
            company = profile.get("company", "") or ""
            title = profile.get("job_title", "") or ""
            industry = profile.get("industry", "") or ""

            prompt = f"""You are a professional networking intelligence analyst for Pixel Labs Network Builder.

Pixel Labs builds high-converting websites and digital systems for contractors, landscapers, and local service businesses.

Given this prospect profile, generate enrichment insights. Return ONLY valid JSON.

Profile:
- Name: {profile.get('name', 'N/A')}
- Title: {title}
- Company: {company}
- Industry: {industry}
- Location: {profile.get('location', 'N/A')}
- Bio: {bio_text[:500]}

Generate enrichment insights including:
1. "company_size": estimated number of employees
2. "tech_stack_indicators": what tech stack they might use
3. "pain_points": top 3 pain points Pixel Labs could solve
4. "engagement_score": 1-10 likelihood they'd engage with Pixel Labs
5. "outreach_angle": a genuine, honest angle for initial outreach
6. "icp_fit_score": 0-100 overall ICP fit score
7. "referral_potential": could they refer clients to Pixel Labs? (yes/no/maybe)

Return ONLY a JSON object. No other text."""

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=500,
                )
                content = response.choices[0].message.content.strip()

                try:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        enrichment = json.loads(content[start:end])
                        enrichment["name"] = profile.get("name", "")
                        enrichment["company"] = company
                        enrichment["enriched"] = True
                        enriched.append(enrichment)
                    else:
                        enriched.append({"name": profile.get("name", ""), "enriched": False})
                except (json.JSONDecodeError, ValueError):
                    enriched.append({"name": profile.get("name", ""), "enriched": False})
            except Exception:
                enriched.append({"name": profile.get("name", ""), "enriched": False})

        return enriched

    def filter_and_enrich_all(self, profiles: list, icp_criteria: dict) -> dict:
        """Filter profiles by ICP, then enrich qualified ones.

        Step 1: Filter all profiles against ICP
        Step 2: Enrich only qualified profiles
        """
        # Step 1: Filter
        filter_result = self.filter_profiles_by_icp(profiles, icp_criteria)

        if not filter_result.get("filtered"):
            return filter_result

        # Get qualified profiles (score >= 60)
        qualified = [f for f in filter_result["filtered"] if f.get("icp_score", 0) >= 60]

        # Convert filtered results back to profile format for enrichment
        qualified_profiles = []
        for q in qualified:
            idx = q.get("index", 0) - 1
            if 0 <= idx < len(profiles):
                profile = profiles[idx].copy()
                profile["icp_score"] = q.get("icp_score", 0)
                profile["icp_reason"] = q.get("reason", "")
                qualified_profiles.append(profile)

        # Step 2: Enrich qualified profiles
        enrichment_results = self.enrich_profiles(qualified_profiles)

        return {
            "total_input": len(profiles),
            "icp_filtered": len(filter_result["filtered"]),
            "qualified": len(qualified),
            "enriched": len(enrichment_results),
            "filter_result": filter_result,
            "enrichment_results": enrichment_results,
            "message": f"Found {len(qualified)} qualified profiles, enriched {len(enrichment_results)}",
        }


# Singleton instance
ai_client = AIClient()
