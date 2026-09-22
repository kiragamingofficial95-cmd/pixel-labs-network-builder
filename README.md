# Pixel Labs Network Builder

A professional LinkedIn networking research and recommendation assistant that helps you build a relevant, diverse, and credible professional network around Pixel Labs.

## Overview

Pixel Labs Network Builder is a **research and recommendation tool** — NOT a LinkedIn automation bot. It helps you decide:

- **WHO** should I consider connecting with?
- **WHY** are they relevant?
- **WHAT** kind of relationship could this become?
- **WHAT** genuine personalization could I use?

**You** make the final decision and manually send every LinkedIn connection request.

## Features

- 📊 **Dashboard** — Real-time network statistics and balance visualization
- 📥 **Import** — Import prospects from CSV, Excel (XLSX), or JSON files
- ➕ **Manual Add** — Add individual prospects with full details
- 🎯 **Daily Queue** — Balanced networking queue with configurable daily targets (10/15/20/25/30/40/50)
- 📝 **Relevance Scoring** — Transparent 0-100 scores with detailed breakdowns
- 🤖 **AI Personalization** — Optional AI-powered personalization using OpenAI-compatible APIs
- 📄 **CSV Export** — Export your networking queue as CSV
- 📜 **History & Activity** — Full activity log and tracking
- ⚖️ **Network Balance** — Detects and alerts when your network is too concentrated
- 🔒 **Privacy First** — All data stored locally, no LinkedIn scraping or automation

## Quick Start

### 1. Installation

```bash
cd pixel-labs-network-builder
pip install -r requirements.txt
```

### 2. Environment Setup

Copy the example environment file and configure:

```bash
copy .env.example .env
```

Edit `.env` to add your OpenAI API key (optional):

```env
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

> **Note:** AI personalization is optional. Without an API key, the tool still provides rule-based scoring and personalization suggestions.

### 3. Run the Application

```bash
python main.py
```

Open your browser to: **http://localhost:8000**

### Using Termux (Android)

```bash
pkg update && pkg upgrade
pkg install python
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Usage Guide

### Importing Prospects

You can import prospects from:
- **CSV files** — Fields: `name`, `job_title`, `company`, `linkedin_url`, `location`, `industry`, `bio`, `about`, `notes`, `email`
- **Excel files (.xlsx/.xls)** — Same field names
- **JSON files** — Array of objects with the same field names

Fields may be missing — the system gracefully handles incomplete data.

### The Daily Queue

The daily queue generates balanced recommendations across four categories:

| Daily Target | Clients | Referral Partners | Agency/Business | Professional Network |
|:---:|:---:|:---:|:---:|:---:|
| 10/day | 3 | 3 | 2 | 2 |
| 15/day | 4 | 4 | 4 | 3 |
| 20/day | 5 | 5 | 5 | 5 |

The queue automatically adjusts if your network is too concentrated in one category.

### Understanding Scores

Each prospect receives a score from 0-100 based on:

| Criteria | Points |
|---|---|
| Strong Pixel Labs target/client fit | +25 |
| Founder/Owner/Decision maker | +20 |
| Strong referral-partner potential | +15 |
| Relevant industry | +10 |
| Relevant location | +10 |
| Relevant marketing/web/SEO/business role | +10 |
| Useful personalization information available | +5 |
| Strong professional/network relevance | +5 |

Scores are transparent — you can see the full breakdown for each person.

### Network Balance

The tool monitors your network balance and provides recommendations:

- If clients exceed 50% of your active network, it recommends adding more referral partners and agency connections
- The daily queue automatically adjusts to include more prospects from underrepresented categories
- The dashboard shows a visual breakdown of your network distribution

### Marking People as Connected

For each person, you can mark their status:
- **👀 Review** — Under consideration
- **✉️ Connection Sent** — You've manually sent a connection request
- **🤝 Connected** — They accepted your connection
- **🔄 Follow Up** — Plan to follow up
- **👀 Not Interested** — Not relevant
- **🚫 Do Not Contact** — Do not reach out

Every action is tracked in the history log.

### Exporting

Click "Export CSV" on the Queue page to download your current networking queue as a CSV file.

### Manual Adding

You can add prospects one-by-one using the "Add Prospect Manually" form on the Import page.

## AI Personalization

If you configure an OpenAI-compatible API key, the tool can generate AI-powered personalization for each prospect. The AI will:

- Only make claims supported by the supplied information
- Never hallucinate or invent facts
- Return "Insufficient information for personalization" when data is limited

To use AI:
1. Set `OPENAI_API_KEY` in your `.env` file
2. Set `OPENAI_BASE_URL` if using a non-OpenAI compatible provider
3. Set `OPENAI_MODEL` to choose the model (default: `gpt-4o-mini`)

## Privacy & Safety

This tool is designed with privacy as a core principle:

- ✅ All data stored locally in SQLite database
- ✅ API keys stored only in `.env` file
- ✅ No LinkedIn passwords, cookies, or session tokens
- ✅ No browser automation or scraping
- ✅ No data uploaded to external services
- ✅ You manually review and send every connection request

**This is NOT a LinkedIn automation bot.** It is a "Professional Network Research + Recommendation Assistant."

## Project Structure

```
pixel-labs-network-builder/
├── main.py                 # FastAPI application entry point
├── config.py               # Application configuration
├── database.py             # SQLite database setup
├── models.py               # Data models
├── schemas.py              # Pydantic schemas
├── scoring.py              # Relevance scoring engine
├── ai_client.py            # AI provider client
├── importers.py            # CSV/XLSX/JSON importers
├── router.py               # API routes
├── queue_builder.py        # Daily networking queue builder
├── network_balance.py      # Network balance analyzer
├── export_service.py       # CSV export service
├── history_service.py      # History and activity tracking
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
├── .env                    # Your environment variables
├── data/                   # SQLite database
├── templates/              # HTML templates
│   ├── dashboard.html
│   ├── import.html
│   ├── queue.html
│   ├── person_details.html
│   ├── history.html
│   └── settings.html
└── static/                 # Static assets
    ├── css/style.css
    └── js/app.js
```

## Contributing

This is a local tool for personal use. Feel free to modify it to suit your needs.

## License

MIT License
