"""Configuration module for Pixel Labs Network Builder."""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# AI Provider Configuration
# Supports: OpenAI, Groq (OpenAI-compatible), or any provider
# ============================================
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq")  # "openai" or "groq"

# Groq Configuration
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# OpenAI Configuration (fallback)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Use Groq if available, otherwise OpenAI
if GROQ_API_KEY and AI_PROVIDER == "groq":
    AI_BASE_URL = GROQ_BASE_URL
    AI_API_KEY = GROQ_API_KEY
    AI_MODEL = GROQ_MODEL
else:
    AI_BASE_URL = OPENAI_BASE_URL
    AI_API_KEY = OPENAI_API_KEY
    AI_MODEL = OPENAI_MODEL

# Application Settings
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
SECRET_KEY = os.getenv("SECRET_KEY", "pixel-labs-secret-key-change-me")

# Database - use /tmp on Vercel/serverless, local data folder otherwise
if os.getenv("VERCEL"):
    DATABASE_URL = "/tmp/pixel_labs.db"
else:
    DATABASE_URL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pixel_labs.db")

# Daily Networking Targets
DAILY_TARGET = int(os.getenv("DAILY_TARGET", "20"))
DEFAULT_CLIENTS_PER_DAY = int(os.getenv("CLIENTS_PER_DAY", "5"))
DEFAULT_REFERRAL_PARTNERS_PER_DAY = int(os.getenv("REFERRAL_PARTNERS_PER_DAY", "5"))
DEFAULT_AGENCY_BUSINESS_PER_DAY = int(os.getenv("AGENCY_BUSINESS_PER_DAY", "5"))
DEFAULT_PROFESSIONAL_NETWORK_PER_DAY = int(os.getenv("PROFESSIONAL_NETWORK_PER_DAY", "5"))

# Category distribution presets
CATEGORY_PRESETS = {
    10: {"clients": 3, "referral_partners": 3, "agency_business": 2, "professional_network": 2},
    15: {"clients": 4, "referral_partners": 4, "agency_business": 4, "professional_network": 3},
    20: {"clients": 5, "referral_partners": 5, "agency_business": 5, "professional_network": 5},
}

SCORING_WEIGHTS = {
    "pixel_labs_target": 25,
    "founder_decision_maker": 20,
    "referral_potential": 15,
    "relevant_industry": 10,
    "relevant_location": 10,
    "relevant_role": 10,
    "personalization_info": 5,
    "professional_network_relevance": 5,
}

CATEGORY_LABELS = {
    "CLIENT": "Client",
    "REFERRAL_PARTNER": "Referral Partner",
    "AGENCY_BUSINESS": "Agency / Business",
    "PROFESSIONAL_NETWORK": "Professional Network",
    "OTHER": "Other",
}

PRIORITY_LABELS = {
    "HIGH": "High Relevance",
    "MEDIUM": "Medium Relevance",
    "LOW": "Low Relevance",
}

RELATIONSHIP_TYPES = [
    "Potential Client",
    "Potential Referral Partner",
    "Potential Collaborator",
    "Industry Connection",
    "Peer",
    "Mentor / Knowledge Connection",
    "General Professional Network",
]

CATEGORY_KEYS = ["clients", "referral_partners", "agency_business", "professional_network"]
