"""LinkedIn Profile Scraper using Playwright.

Searches LinkedIn for profiles, extracts data, and stores in database.
Then Groq AI filters by ICP and enriches qualified profiles.
"""

import asyncio
import json
import random
import re
import time
from datetime import datetime
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page


class LinkedInScraper:
    """Scrapes LinkedIn profiles using Playwright browser automation."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.logged_in = False
        self.cookie_file = "data/linkedin_cookies.json"

    async def start(self):
        """Start the browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        # Remove webdriver detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        self.page = await context.new_page()

    async def stop(self):
        """Stop the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def login(self, email: str, password: str) -> dict:
        """Login to LinkedIn with email/password."""
        try:
            await self.page.goto("https://www.linkedin.com/login", wait_until="networkidle")
            await asyncio.sleep(2)

            # Fill email
            await self.page.fill('input[name="session_key"]', email)
            await asyncio.sleep(0.5)

            # Fill password
            await self.page.fill('input[name="session_password"]', password)
            await asyncio.sleep(0.5)

            # Click login
            await self.page.click('button[type="submit"]')
            await asyncio.sleep(5)

            # Check if we need to handle security challenge
            if "challenge" in self.page.url or "checkpoint" in self.page.url:
                return {"success": False, "error": "Security challenge detected. Please log in manually first."}

            # Check if logged in
            if "feed" in self.page.url or "mynetwork" in self.page.url or "linkedin.com/in/" in self.page.url:
                self.logged_in = True
                # Save cookies
                await self._save_cookies()
                return {"success": True, "message": "Logged in successfully"}

            # Try visiting feed to verify
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="networkidle")
            await asyncio.sleep(2)

            if "login" not in self.page.url:
                self.logged_in = True
                await self._save_cookies()
                return {"success": True, "message": "Logged in successfully"}

            return {"success": False, "error": "Login failed. Check credentials."}

        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    async def login_with_cookies(self) -> bool:
        """Try to login using saved cookies."""
        import os
        if not os.path.exists(self.cookie_file):
            return False

        try:
            with open(self.cookie_file, "r") as f:
                cookies = json.load(f)

            await self.page.context.add_cookies(cookies)
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="networkidle")
            await asyncio.sleep(3)

            if "login" not in self.page.url:
                self.logged_in = True
                return True
            return False
        except Exception:
            return False

    async def _save_cookies(self):
        """Save cookies for future sessions."""
        import os
        os.makedirs("data", exist_ok=True)
        cookies = await self.page.context.cookies()
        with open(self.cookie_file, "w") as f:
            json.dump(cookies, f)

    async def search_profiles(
        self,
        keywords: str = "",
        title: str = "",
        company: str = "",
        location: str = "",
        industry: str = "",
        max_results: int = 25,
    ) -> dict:
        """Search LinkedIn for profiles matching criteria.

        Returns scraped profile data.
        """
        if not self.logged_in:
            # Try cookies first
            if not await self.login_with_cookies():
                return {"error": "Not logged in. Please login first via /api/linkedin/login"}

        profiles = []
        search_url = self._build_search_url(keywords, title, company, location, industry)

        try:
            await self.page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(3 + random.uniform(1, 3))

            # Scroll to load more results
            for scroll in range(min(max_results // 10 + 1, 5)):
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2 + random.uniform(0.5, 1.5))

            # Extract profile cards from search results
            profile_cards = await self.page.query_selector_all("li.reusable-search__result-container")

            if not profile_cards:
                # Try alternative selectors
                profile_cards = await self.page.query_selector_all("div.entity-result")

            for card in profile_cards[:max_results]:
                try:
                    profile = await self._extract_profile_from_card(card)
                    if profile and profile.get("name"):
                        profiles.append(profile)
                except Exception:
                    continue

            # Deduplicate
            seen = set()
            unique = []
            for p in profiles:
                key = (p.get("name", ""), p.get("company", ""))
                if key not in seen:
                    seen.add(key)
                    unique.append(p)

            return {
                "success": True,
                "total": len(unique),
                "profiles": unique,
                "search_url": search_url,
            }

        except Exception as e:
            return {"error": str(e)[:300]}

    async def scrape_profile(self, linkedin_url: str) -> dict:
        """Scrape a single LinkedIn profile page for detailed info."""
        if not self.logged_in:
            if not await self.login_with_cookies():
                return {"error": "Not logged in"}

        try:
            await self.page.goto(linkedin_url, wait_until="networkidle")
            await asyncio.sleep(3 + random.uniform(1, 3))

            profile = {}

            # Name
            name_el = await self.page.query_selector("h1.text-heading-xlarge")
            if name_el:
                profile["name"] = (await name_el.inner_text()).strip()

            # Headline / Title
            headline_el = await self.page.query_selector("div.text-body-medium.break-words")
            if headline_el:
                headline = (await headline_el.inner_text()).strip()
                profile["headline"] = headline
                # Parse company from headline
                if " at " in headline.lower():
                    parts = headline.split(" at ", 1)
                    profile["job_title"] = parts[0].strip()
                    profile["company"] = parts[1].strip()
                elif " @ " in headline:
                    parts = headline.split(" @ ", 1)
                    profile["job_title"] = parts[0].strip()
                    profile["company"] = parts[1].strip()
                else:
                    profile["job_title"] = headline

            # Location
            loc_el = await self.page.query_selector("span.text-body-small.inline.t-black--light.break-words")
            if loc_el:
                profile["location"] = (await loc_el.inner_text()).strip()

            # About section
            about_section = await self.page.query_selector("section.pv-about-section")
            if about_section:
                about_text = await about_section.inner_text()
                profile["bio"] = about_text.replace("About\n", "").strip()[:2000]

            # Experience
            exp_section = await self.page.query_selector("section#experience")
            if exp_section:
                exp_text = await exp_section.inner_text()
                profile["experience"] = exp_text[:1000]

            # Education
            edu_section = await self.page.query_selector("section#education")
            if edu_section:
                edu_text = await edu_section.inner_text()
                profile["education"] = edu_text[:500]

            # Connections count
            conn_el = await self.page.query_selector("span.t-bold")
            if conn_el:
                profile["connections"] = (await conn_el.inner_text()).strip()

            profile["linkedin_url"] = linkedin_url
            profile["scraped_at"] = datetime.now().isoformat()

            return {"success": True, "profile": profile}

        except Exception as e:
            return {"error": str(e)[:300]}

    async def _extract_profile_from_card(self, card) -> dict:
        """Extract profile data from a search result card."""
        profile = {}

        # Name and URL
        name_link = await card.query_selector("a.app-aware-link span[aria-hidden='true']")
        if not name_link:
            name_link = await card.query_selector("span.entity-result__title-text a span")
        if name_link:
            profile["name"] = (await name_link.inner_text()).strip()

        # Profile URL
        url_el = await card.query_selector("a.app-aware-link")
        if not url_el:
            url_el = await card.query_selector("a[href*='/in/']")
        if url_el:
            href = await url_el.get_attribute("href")
            if href:
                profile["linkedin_url"] = href.split("?")[0]

        # Title / Headline
        title_el = await card.query_selector("div.entity-result__primary-subtitle")
        if not title_el:
            title_el = await card.query_selector("span.entity-result__primary-subtitle")
        if title_el:
            title_text = (await title_el.inner_text()).strip()
            if " at " in title_text.lower():
                parts = title_text.split(" at ", 1)
                profile["job_title"] = parts[0].strip()
                profile["company"] = parts[1].strip()
            elif " @ " in title_text:
                parts = title_text.split(" @ ", 1)
                profile["job_title"] = parts[0].strip()
                profile["company"] = parts[1].strip()
            else:
                profile["job_title"] = title_text

        # Location
        loc_el = await card.query_selector("div.entity-result__secondary-subtitle")
        if not loc_el:
            loc_el = await card.query_selector("span.entity-result__secondary-subtitle")
        if loc_el:
            profile["location"] = (await loc_el.inner_text()).strip()

        # Snippet / Description
        snippet_el = await card.query_selector("p.entity-result__snippet")
        if snippet_el:
            profile["bio"] = (await snippet_el.inner_text()).strip()

        profile["scraped_at"] = datetime.now().isoformat()
        return profile

    def _build_search_url(self, keywords, title, company, location, industry) -> str:
        """Build LinkedIn People search URL."""
        base = "https://www.linkedin.com/search/results/people/"
        params = []

        if keywords:
            params.append(f"keywords={keywords.replace(' ', '%20')}")
        if title:
            params.append(f"keywords={title.replace(' ', '%20')}")
        if company:
            params.append(f"keywords={company.replace(' ', '%20')}")
        if location:
            params.append(f"geoUrn=%5B%22103644278%22%5D")  # US default, can be enhanced
        if industry:
            params.append(f"keywords={industry.replace(' ', '%20')}")

        if not params:
            params.append("keywords=contractor")

        return base + "?" + "&".join(params)


# Singleton
scraper = LinkedInScraper(headless=True)
