"""X-Ray Search Engine - Find LinkedIn profiles via Google search.

No LinkedIn login required. Uses Google to find public LinkedIn profiles:
  site:linkedin.com/in/ "landscaping" "owner" "Texas"

Then scrapes the public profile page for available info.
"""

import asyncio
import random
import re
import json
import os
from datetime import datetime
from urllib.parse import quote_plus
from playwright.async_api import async_playwright, Browser, Page


class XRaySearcher:
    """Finds LinkedIn profiles via Google X-Ray search - no login needed."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.page = None
        self.playwright = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        self.page = await context.new_page()

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def search_xray(
        self,
        keywords: str = "",
        title: str = "",
        company: str = "",
        location: str = "",
        industry: str = "",
        max_results: int = 25,
        pages_to_search: int = 3,
        all_keywords: list = None,
    ) -> dict:
        """Search Google for LinkedIn profiles using X-Ray technique.

        Supports multi-keyword search:
        - keywords="landscaping" -> single search
        - all_keywords=["landscaping", "HVAC", "plumbing"] -> separate searches per keyword

        Builds Google queries like:
          site:linkedin.com/in/ "landscaping" "owner" "Texas"
        """
        # If multiple keywords, run separate searches
        if all_keywords and len(all_keywords) > 1:
            return await self._search_multi_keyword(all_keywords, title, company, location, industry, max_results, pages_to_search)

        # Single keyword search
        query = self._build_xray_query(keywords, title, company, location, industry)
        all_profiles = []
        start = 0

        for page_num in range(pages_to_search):
            start = page_num * 10
            google_url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}"

            try:
                await self.page.goto(google_url, wait_until="domcontentloaded")
                await asyncio.sleep(2 + random.uniform(1, 3))

                # Handle consent/cookie popups
                await self._handle_google_consent()

                # Extract search results
                results = await self._extract_google_results()

                for r in results:
                    url = r.get("url", "")
                    if "linkedin.com/in/" in url:
                        profile = self._parse_xray_result(r)
                        if profile.get("name"):
                            all_profiles.append(profile)

                # Random delay between pages
                if page_num < pages_to_search - 1:
                    await asyncio.sleep(3 + random.uniform(2, 5))

            except Exception as e:
                continue

        # Deduplicate by URL
        seen = set()
        unique = []
        for p in all_profiles:
            url = p.get("linkedin_url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(p)
            elif not url:
                unique.append(p)

        return {
            "success": True,
            "query": query,
            "total": len(unique),
            "profiles": unique[:max_results],
        }

    async def _search_multi_keyword(
        self, keywords_list: list, title: str, company: str,
        location: str, industry: str, max_results: int, pages_to_search: int,
    ) -> dict:
        """Run separate Google searches for each keyword, combine and deduplicate.

        Distributes max_results evenly across keywords.
        Example: 3 keywords, 30 total -> 10 per keyword
        """
        per_keyword = max(1, max_results // len(keywords_list))
        all_profiles = []
        queries_used = []

        for kw in keywords_list:
            kw = kw.strip()
            if not kw:
                continue

            query = self._build_xray_query(kw, title, company, location, industry)
            queries_used.append(query)

            for page_num in range(min(pages_to_search, 2)):  # Fewer pages per keyword
                start = page_num * 10
                google_url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}"

                try:
                    await self.page.goto(google_url, wait_until="domcontentloaded")
                    await asyncio.sleep(2 + random.uniform(1, 3))

                    await self._handle_google_consent()
                    results = await self._extract_google_results()

                    for r in results:
                        url = r.get("url", "")
                        if "linkedin.com/in/" in url:
                            profile = self._parse_xray_result(r)
                            if profile.get("name"):
                                profile["search_keyword"] = kw
                                all_profiles.append(profile)

                    if page_num < pages_to_search - 1:
                        await asyncio.sleep(3 + random.uniform(2, 4))

                except Exception:
                    continue

        # Deduplicate by URL
        seen = set()
        unique = []
        for p in all_profiles:
            url = p.get("linkedin_url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(p)
            elif not url:
                unique.append(p)

        return {
            "success": True,
            "query": " | ".join(queries_used),
            "keywords_searched": keywords_list,
            "total": len(unique),
            "profiles": unique[:max_results],
        }

    async def scrape_public_profile(self, linkedin_url: str) -> dict:
        """Scrape a public LinkedIn profile page (no login required).

        Public profiles show: name, headline, location, about, experience.
        """
        # Ensure it's a full URL
        if not linkedin_url.startswith("http"):
            linkedin_url = "https://www.linkedin.com/in/" + linkedin_url

        try:
            await self.page.goto(linkedin_url, wait_until="domcontentloaded")
            await asyncio.sleep(3 + random.uniform(1, 2))

            profile = {"linkedin_url": linkedin_url}

            # Name
            el = await self.page.query_selector("h1.text-heading-xlarge")
            if el:
                profile["name"] = (await el.inner_text()).strip()

            # Headline (title + company)
            el = await self.page.query_selector("div.text-body-medium.break-words")
            if el:
                headline = (await el.inner_text()).strip()
                profile["headline"] = headline
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
            el = await self.page.query_selector("span.text-body-small.inline.t-black--light.break-words")
            if el:
                profile["location"] = (await el.inner_text()).strip()

            # About
            el = await self.page.query_selector("section.pv-about-section")
            if el:
                text = await el.inner_text()
                profile["bio"] = text.replace("About\n", "").strip()[:2000]

            # Experience section
            el = await self.page.query_selector("section#experience")
            if el:
                text = await el.inner_text()
                profile["experience"] = text[:1500]
                # Try to extract current role
                exp_items = await el.query_selector_all("li")
                if exp_items:
                    first_exp = await exp_items[0].inner_text()
                    profile["current_role"] = first_exp[:300]

            # Education
            el = await self.page.query_selector("section#education")
            if el:
                text = await el.inner_text()
                profile["education"] = text[:500]

            profile["scraped_at"] = datetime.now().isoformat()
            return {"success": True, "profile": profile}

        except Exception as e:
            return {"error": str(e)[:300]}

    async def _handle_google_consent(self):
        """Handle Google cookie consent popup."""
        try:
            # Try common consent button selectors
            for selector in [
                "button#L2AGLb",
                "button[aria-label='Accept all']",
                "button:has-text('Accept all')",
                "button:has-text('I agree')",
            ]:
                btn = await self.page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
                    break
        except Exception:
            pass

    async def _extract_google_results(self) -> list:
        """Extract search results from Google search page."""
        results = []

        # Wait for results to load
        await self.page.wait_for_selector("div.g, div[data-sokoban-container]", timeout=10000)

        # Get all result containers
        containers = await self.page.query_selector_all("div.g")
        if not containers:
            containers = await self.page.query_selector_all("div[data-sokoban-container]")

        for container in containers:
            try:
                # Get link
                link = await container.query_selector("a")
                if not link:
                    continue

                url = await link.get_attribute("href") or ""
                if not url.startswith("http"):
                    continue

                # Get title
                title_el = await container.query_selector("h3")
                title = (await title_el.inner_text()).strip() if title_el else ""

                # Get snippet
                snippet_el = await container.query_selector("div[data-sncf], span.aCOpRe, div.VwiC3b")
                snippet = (await snippet_el.inner_text()).strip() if snippet_el else ""

                results.append({
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                })
            except Exception:
                continue

        return results

    def _parse_xray_result(self, result: dict) -> dict:
        """Parse a Google X-Ray search result into profile data."""
        profile = {
            "linkedin_url": result.get("url", ""),
            "source": "xray_google",
            "scraped_at": datetime.now().isoformat(),
        }

        title = result.get("title", "")
        snippet = result.get("snippet", "")

        # Parse title: "John Smith - CEO at Company | LinkedIn"
        title_clean = title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
        if " - " in title_clean:
            parts = title_clean.split(" - ", 1)
            profile["name"] = parts[0].strip()
            rest = parts[1].strip()
            if " at " in rest.lower():
                job_parts = rest.split(" at ", 1)
                profile["job_title"] = job_parts[0].strip()
                profile["company"] = job_parts[1].strip()
            elif " @ " in rest:
                job_parts = rest.split(" @ ", 1)
                profile["job_title"] = job_parts[0].strip()
                profile["company"] = job_parts[1].strip()
            else:
                profile["job_title"] = rest
        elif " | " in title_clean:
            parts = title_clean.split(" | ", 1)
            profile["name"] = parts[0].strip()
        else:
            profile["name"] = title_clean

        # Parse snippet for more info
        if snippet:
            # Look for location patterns
            loc_match = re.search(r'(?:Location|Located in|Based in)[:\s]+([^·\n]+)', snippet, re.I)
            if loc_match:
                profile["location"] = loc_match.group(1).strip()

            # Look for industry
            ind_match = re.search(r'(?:Industry|Sector)[:\s]+([^·\n]+)', snippet, re.I)
            if ind_match:
                profile["industry"] = ind_match.group(1).strip()

            # Use snippet as bio if no other bio
            if not profile.get("bio"):
                profile["bio"] = snippet[:500]

        return profile

    def _build_xray_query(self, keywords, title, company, location, industry) -> str:
        """Build Google X-Ray search query for LinkedIn profiles."""
        parts = ['site:linkedin.com/in/']

        if keywords:
            parts.append(f'"{keywords}"')
        if title:
            parts.append(f'"{title}"')
        if company:
            parts.append(f'"{company}"')
        if location:
            parts.append(f'"{location}"')
        if industry:
            parts.append(f'"{industry}"')

        # If no specific terms, use a default for Pixel Labs ICP
        if len(parts) == 1:
            parts.append('"contractor" OR "landscaping" OR "home services"')

        return " ".join(parts)


# Singleton
xray = XRaySearcher(headless=True)
