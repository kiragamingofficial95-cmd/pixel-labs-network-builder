"""AI client module for Pixel Labs Network Builder."""
import json
from openai import OpenAI
from config import OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL


class AIClient:
    """OpenAI-compatible AI client for personalization."""

    def __init__(self):
        """Initialize the AI client."""
        self.client = None
        self.available = False
        self.model = OPENAI_MODEL or "gpt-4o-mini"

        if OPENAI_API_KEY:
            try:
                base_url = OPENAI_BASE_URL or "https://api.openai.com/v1"
                self.client = OpenAI(base_url=base_url, api_key=OPENAI_API_KEY)
                self.available = True
            except Exception:
                self.client = None
                self.available = False

    def generate_personalization(self, prospect_data: dict) -> dict:
        """Generate AI-powered personalization for a prospect.

        Only makes claims supported by the supplied information.
        Never hallucinates.
        """
        if not self.available or not self.client:
            return {
                "why_relevant": "Insufficient information for AI personalization.",
                "personalization_point": "Insufficient information for personalization.",
                "connection_note": "Insufficient information for personalization.",
                "follow_up_topic": "Insufficient information for personalization.",
            }

        name = prospect_data.get("name", "")
        company = prospect_data.get("company", "")
        job_title = prospect_data.get("job_title", "")
        bio = prospect_data.get("bio", "")
        about = prospect_data.get("about", "")
        industry = prospect_data.get("industry", "")
        location = prospect_data.get("location", "")

        all_text = " ".join(filter(None, [bio, about]))
        if len(all_text) < 20 and not job_title and not industry:
            return {
                "why_relevant": "Insufficient information for AI personalization.",
                "personalization_point": "Insufficient information for personalization.",
                "connection_note": "Insufficient information for personalization.",
                "follow_up_topic": "Insufficient information for personalization.",
            }

        prompt = (
            "You are a professional networking research assistant for Pixel Labs.\n\n"
            "Pixel Labs builds high-converting websites and digital systems for contractors, "
            "landscapers, and local service businesses. We help businesses generate more qualified inquiries.\n\n"
            "Generate personalization data for this prospect using ONLY the information provided below. "
            "Do NOT invent facts or make claims not supported by the data.\n\n"
            f"Prospect Information:\n"
            f"- Name: {name}\n"
            f"- Company: {company}\n"
            f"- Job Title: {job_title}\n"
            f"- Industry: {industry}\n"
            f"- Location: {location}\n"
            f"- Bio: {bio or 'None provided'}\n"
            f"- About: {about or 'None provided'}\n\n"
            "Return ONLY a JSON object with exactly these fields:\n"
            "{\n"
            '    "why_relevant": "Explain why relevant (max 150 chars). Say \"Insufficient information\" if not enough data.",\n'
            '    "personalization_point": "A genuine point based ONLY on supplied data (max 150 chars). Say \"Insufficient information\" if not enough data.",\n'
            '    "connection_note": "A short connection request under 300 chars. Non-salesy, honest, natural. Say \"Insufficient information\" if not enough data.",\n'
            '    "follow_up_topic": "A suggested conversation topic (max 150 chars). Say \"Insufficient information\" if not enough data."\n'
            "}\n\n"
            "IMPORTANT: Never invent facts. Only use information explicitly provided above."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()

            # Try to parse JSON from response
            try:
                # Find JSON in the response
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    result = json.loads(json_str)
                    return {
                        "why_relevant": result.get("why_relevant", "Insufficient information for personalization."),
                        "personalization_point": result.get("personalization_point", "Insufficient information for personalization."),
                        "connection_note": result.get("connection_note", "Insufficient information for personalization."),
                        "follow_up_topic": result.get("follow_up_topic", "Insufficient information for personalization."),
                    }
            except (json.JSONDecodeError, ValueError):
                pass

            return {
                "why_relevant": "Insufficient information for AI personalization.",
                "personalization_point": "Insufficient information for AI personalization.",
                "connection_note": "Insufficient information for AI personalization.",
                "follow_up_topic": "Insufficient information for AI personalization.",
            }
        except Exception:
            return {
                "why_relevant": "Insufficient information for AI personalization.",
                "personalization_point": "Insufficient information for AI personalization.",
                "connection_note": "Insufficient information for AI personalization.",
                "follow_up_topic": "Insufficient information for AI personalization.",
            }
