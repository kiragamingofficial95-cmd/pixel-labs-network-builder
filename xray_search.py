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
import logging
from datetime import datetime
from urllib.parse import quote_plus, urlencode
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


class XRaySearcher:
    """Finds LinkedIn profiles via Google X-Ray search - no login needed."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1920,1080",
            ],
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)
        self.page = await self.context.new_page()

    async def stop(self):
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.browser = None
        self.playwright = None
        self.page = None

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
        """Search Google for LinkedIn profiles using X-Ray technique."""
        logger.info(f"[XRAY] Starting search: keywords={keywords}, all_keywords={all_keywords}")

        if all_keywords and len(all_keywords) > 1:
            return await self._search_multi_keyword(all_keywords, title, company, location, industry, max_results, pages_to_search)

        query = self._build_xray_query(keywords, title, company, location, industry)
        logger.info(f"[XRAY] Query: {query}")
        all_profiles = []

        for page_num in range(pages_to_search):
            start = page_num * 10
            google_url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}&hl=en"

            try:
                logger.info(f"[XRAY] Page {page_num + 1}: {google_url}")
                await self.page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2 + random.uniform(1, 3))

                # Handle consent/cookie popups
                await self._handle_google_consent()

                # Check if we got blocked
                page_title = await self.page.title()
                page_url = self.page.url
                logger.info(f"[XRAY] Page title: {page_title}, URL: {page_url}")

                # Detect CAPTCHA or block
                if "sorry" in page_url.lower() or "captcha" in page_title.lower():
                    logger.warning("[XRAY] Google CAPTCHA/block detected!")
                    break

                # Extract search results
                results = await self._extract_google_results()
                logger.info(f"[XRAY] Found {len(results)} raw results on page {page_num + 1}")

                for r in results:
                    url = r.get("url", "")
                    if "linkedin.com/in/" in url:
                        profile = self._parse_xray_result(r)
                        if profile.get("name"):
                            all_profiles.append(profile)
                            logger.info(f"[XRAY]   + {profile['name']}")

                if page_num < pages_to_search - 1:
                    await asyncio.sleep(3 + random.uniform(2, 5))

            except Exception as e:
                logger.error(f"[XRAY] Error on page {page_num + 1}: {e}")
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

        logger.info(f"[XRAY] Total unique profiles: {len(unique)}")
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
        """Run separate Google searches for each keyword, combine and deduplicate."""
        logger.info(f"[XRAY] Multi-keyword search: {keywords_list}")
        per_keyword = max(1, max_results // len(keywords_list))
        all_profiles = []
        queries_used = []

        for kw in keywords_list:
            kw = kw.strip()
            if not kw:
                continue

            query = self._build_xray_query(kw, title, company, location, industry)
            queries_used.append(query)
            logger.info(f"[XRAY] Searching keyword: '{kw}' -> {query}")

            for page_num in range(min(pages_to_search, 2)):
                start = page_num * 10
                google_url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}&hl=en"

                try:
                    logger.info(f"[XRAY]   Page {page_num + 1}: {google_url}")
                    await self.page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2 + random.uniform(1, 3))

                    await self._handle_google_consent()

                    page_url = self.page.url
                    if "sorry" in page_url.lower():
                        logger.warning(f"[XRAY]   Block detected for '{kw}', skipping...")
                        break

                    results = await self._extract_google_results()
                    logger.info(f"[XRAY]   Found {len(results)} results for '{kw}'")

                    for r in results:
                        url = r.get("url", "")
                        if "linkedin.com/in/" in url:
                            profile = self._parse_xray_result(r)
                            if profile.get("name"):
                                profile["search_keyword"] = kw
                                all_profiles.append(profile)
                                logger.info(f"[XRAY]     + {profile['name']}")

                    if page_num < pages_to_search - 1:
                        await asyncio.sleep(3 + random.uniform(2, 4))

                except Exception as e:
                    logger.error(f"[XRAY]   Error for '{kw}' page {page_num + 1}: {e}")
                    continue

            # Pause between keywords
            await asyncio.sleep(2 + random.uniform(1, 3))

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

        logger.info(f"[XRAY] Multi-keyword total: {len(unique)} unique profiles from {len(all_profiles)} raw")
        return {
            "success": True,
            "query": " | ".join(queries_used),
            "keywords_searched": keywords_list,
            "total": len(unique),
            "profiles": unique[:max_results],
        }

    async def scrape_public_profile(self, linkedin_url: str) -> dict:
        """Scrape a public LinkedIn profile page (no login required)."""
        if not linkedin_url.startswith("http"):
            linkedin_url = "https://www.linkedin.com/in/" + linkedin_url

        try:
            await self.page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3 + random.uniform(1, 2))

            profile = {"linkedin_url": linkedin_url}

            # Name
            el = await self.page.query_selector("h1.text-heading-xlarge")
            if el:
                profile["name"] = (await el.inner_text()).strip()

            # Headline
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

            # Experience
            el = await self.page.query_selector("section#experience")
            if el:
                text = await el.inner_text()
                profile["experience"] = text[:1500]
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
        """Handle Google cookie consent popup - multiple approaches."""
        try:
            # Method 1: Direct button IDs
            for selector in [
                "button#L2AGLb",
                "button#W0wltc",
                "button[aria-label='Accept all']",
                "button[aria-label='Reject all']",
                "[data-idom-class*='consent'] button",
            ]:
                try:
                    btn = await self.page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(2)
                        logger.info(f"[XRAY] Clicked consent button: {selector}")
                        return
                except Exception:
                    continue

            # Method 2: Look for any button with consent text
            buttons = await self.page.query_selector_all("button")
            for btn in buttons:
                try:
                    text = (await btn.inner_text()).lower().strip()
                    if any(phrase in text for phrase in ["accept all", "i agree", "agree", "accept", "reject all"]):
                        if await btn.is_visible():
                            await btn.click()
                            await asyncio.sleep(2)
                            logger.info(f"[XRAY] Clicked consent button by text: {text}")
                            return
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"[XRAY] Consent handling: {e}")

    async def _extract_google_results(self) -> list:
        """Extract search results from Google search page with multiple fallback selectors."""
        results = []

        # Try multiple selector strategies
        containers = []

        # Strategy 1: div.g (standard Google results)
        try:
            containers = await self.page.query_selector_all("div.g")
        except Exception:
            pass

        # Strategy 2: data-sokoban-container
        if not containers:
            try:
                containers = await self.page.query_selector_all("div[data-sokoban-container]")
            except Exception:
                pass

        # Strategy 3: T1Uudb (alternative result class)
        if not containers:
            try:
                containers = await self.page.query_selector_all("div.T1Uudb")
            except Exception:
                pass

        # Strategy 4: Just find all links that go to LinkedIn
        if not containers:
            try:
                links = await self.page.query_selector_all("a[href*='linkedin.com/in/']")
                for link in links:
                    url = await link.get_attribute("href") or ""
                    if url.startswith("http") and "linkedin.com/in/" in url:
                        # Try to get surrounding text
                        title = ""
                        try:
                            h3 = await link.query_selector("h3")
                            if h3:
                                title = (await h3.inner_text()).strip()
                        except Exception:
                            pass
                        if not title:
                            title = (await link.inner_text()).strip()

                        results.append({
                            "url": url,
                            "title": title,
                            "snippet": "",
                        })
                return results
            except Exception:
                pass

        logger.info(f"[XRAY] Found {len(containers)} result containers")

        for container in containers:
            try:
                link = await container.query_selector("a")
                if not link:
                    continue

                url = await link.get_attribute("href") or ""
                if not url.startswith("http"):
                    continue

                title_el = await container.query_selector("h3")
                title = (await title_el.inner_text()).strip() if title_el else ""

                snippet_el = await container.query_selector("[data-sncf], [data-snf], span.st, div.VwiC3b, div[data-sncf]")
                snippet = ""
                if snippet_el:
                    try:
                        snippet = (await snippet_el.inner_text()).strip()
                    except Exception:
                        pass

                if url and title:
                    results.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                    })
            except Exception as e:
                logger.debug(f"[XRAY] Error extracting result: {e}")
                continue

        # If still no results, try page content dump for debugging
        if not results:
            try:
                content = await self.page.content()
                # Check for LinkedIn links anywhere in page
                linkedin_links = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[^\s"\'<>]+', content)
                logger.info(f"[XRAY] Found {len(linkedin_links)} LinkedIn links in page HTML")
                for url in set(linkedin_links):
                    url = url.split("?")[0]  # Clean URL
                    if url not in [r["url"] for r in results]:
                        results.append({
                            "url": url,
                            "title": "",
                            "snippet": "",
                        })
            except Exception:
                pass

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
        elif " · " in title_clean:
            parts = title_clean.split(" · ", 1)
            profile["name"] = parts[0].strip()
        else:
            profile["name"] = title_clean

        # Parse snippet for more info
        if snippet:
            loc_match = re.search(r'(?:Location|Located in|Based in)[:\s]+([^·\n]+)', snippet, re.I)
            if loc_match:
                profile["location"] = loc_match.group(1).strip()

            ind_match = re.search(r'(?:Industry|Sector)[:\s]+([^·\n]+)', snippet, re.I)
            if ind_match:
                profile["industry"] = ind_match.group(1).strip()

            if not profile.get("bio"):
                profile["bio"] = snippet[:500]

        # Try to extract name from URL if not found
        if not profile.get("name"):
            url = profile.get("linkedin_url", "")
            match = re.search(r'linkedin\.com/in/([^/?]+)', url)
            if match:
                slug = match.group(1)
                name = slug.replace("-", " ").title()
                profile["name"] = name

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

        if len(parts) == 1:
            parts.append('"contractor" OR "landscaping" OR "home services"')

        return " ".join(parts)


# Singleton
xray = XRaySearcher(headless=True)
