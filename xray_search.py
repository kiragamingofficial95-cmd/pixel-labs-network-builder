"""X-Ray Search Engine - Find LinkedIn profiles via Google/DuckDuckGo search.

No LinkedIn login required. Searches DuckDuckGo (scraper-friendly) for:
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
from urllib.parse import quote_plus
import httpx

logger = logging.getLogger(__name__)


class XRaySearcher:
    """Finds LinkedIn profiles via X-Ray search - no login needed.
    
    Uses DuckDuckGo HTML (no CAPTCHA, no blocks) as primary,
    with Playwright Google as fallback.
    """

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    # ==========================================
    # METHOD 1: DuckDuckGo HTML (fast, no blocks)
    # ==========================================
    async def _search_ddg(self, query: str, max_results: int = 25) -> list:
        """Search DuckDuckGo HTML version - no CAPTCHA, no blocks."""
        results = []
        html_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        logger.info(f"[DDG] Searching: {query}")

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                resp = await client.get(html_url)
                logger.info(f"[DDG] Status: {resp.status_code}, Length: {len(resp.text)}")

                if resp.status_code != 200:
                    logger.warning(f"[DDG] Non-200 status: {resp.status_code}")
                    return results

                html = resp.text

                # Parse DuckDuckGo HTML results
                # Each result is in a <div class="result"> block
                result_blocks = re.findall(
                    r'<div class="result[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                    html, re.DOTALL
                )

                if not result_blocks:
                    # Fallback: just find all links
                    result_blocks = [html]

                for block in result_blocks:
                    # Extract URL from href
                    urls = re.findall(r'href="(https?://[^"]*linkedin\.com/in/[^"]*)"', block)
                    for url in urls:
                        # Clean the URL (DuckDuckGo wraps URLs)
                        if "uddg=" in url:
                            url_match = re.search(r'uddg=([^&]+)', url)
                            if url_match:
                                from urllib.parse import unquote
                                url = unquote(url_match.group(1))

                        if "linkedin.com/in/" not in url:
                            continue

                        # Clean URL
                        url = url.split("?")[0].split("#")[0]
                        if not url.endswith("/"):
                            pass  # Keep as-is

                        # Extract title near this URL
                        title_match = re.search(
                            rf'href="[^"]*{re.escape(url.split("linkedin.com")[1])}[^"]*"[^>]*>([^<]+)',
                            block
                        )
                        title = title_match.group(1).strip() if title_match else ""

                        # Extract snippet
                        snippet_match = re.findall(r'<a class="result__snippet"[^>]*>([^<]+)', block)
                        snippet = snippet_match[0].strip() if snippet_match else ""

                        if url not in [r.get("url") for r in results]:
                            results.append({
                                "url": url,
                                "title": title,
                                "snippet": snippet,
                            })

                        if len(results) >= max_results:
                            break

                logger.info(f"[DDG] Found {len(results)} LinkedIn profiles")

        except Exception as e:
            logger.error(f"[DDG] Error: {e}")

        return results[:max_results]

    # ==========================================
    # METHOD 2: Playwright Google (fallback)
    # ==========================================
    async def start(self):
        """Start Playwright browser (only needed for Google fallback)."""
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
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

    async def _search_google(self, query: str, max_results: int = 25, pages: int = 2) -> list:
        """Search Google using Playwright (fallback)."""
        results = []
        if not self.page:
            return results

        for page_num in range(pages):
            start = page_num * 10
            google_url = f"https://www.google.com/search?q={quote_plus(query)}&start={start}&hl=en"

            try:
                await self.page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2 + random.uniform(1, 3))

                page_url = self.page.url
                if "sorry" in page_url.lower():
                    logger.warning("[GOOGLE] CAPTCHA detected, stopping")
                    break

                containers = await self.page.query_selector_all("div.g")
                if not containers:
                    containers = await self.page.query_selector_all("div[data-sokoban-container]")

                for container in containers:
                    try:
                        link = await container.query_selector("a")
                        if not link:
                            continue
                        url = await link.get_attribute("href") or ""
                        if not url.startswith("http") or "linkedin.com/in/" not in url:
                            continue

                        title_el = await container.query_selector("h3")
                        title = (await title_el.inner_text()).strip() if title_el else ""

                        snippet_el = await container.query_selector("[data-sncf], [data-snf], div.VwiC3b")
                        snippet = ""
                        if snippet_el:
                            try:
                                snippet = (await snippet_el.inner_text()).strip()
                            except Exception:
                                pass

                        if url not in [r.get("url") for r in results]:
                            results.append({"url": url, "title": title, "snippet": snippet})
                    except Exception:
                        continue

                if page_num < pages - 1:
                    await asyncio.sleep(3 + random.uniform(2, 4))

            except Exception as e:
                logger.error(f"[GOOGLE] Error page {page_num}: {e}")
                continue

        return results[:max_results]

    # ==========================================
    # Main search method (tries DDG first, then Google)
    # ==========================================
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
        """Search for LinkedIn profiles. Tries DuckDuckGo first, then Google."""

        if all_keywords and len(all_keywords) > 1:
            return await self._search_multi_keyword(all_keywords, title, company, location, industry, max_results, pages_to_search)

        query = self._build_xray_query(keywords, title, company, location, industry)
        logger.info(f"[XRAY] Query: {query}")

        # Try DuckDuckGo first (no blocks)
        results = await self._search_ddg(query, max_results)

        # If DDG found nothing, try Google via Playwright
        if not results:
            logger.info("[XRAY] DDG found 0, trying Google via Playwright...")
            try:
                await self.start()
                results = await self._search_google(query, max_results, pages=min(pages_to_search, 2))
            except Exception as e:
                logger.error(f"[XRAY] Google fallback error: {e}")
            finally:
                await self.stop()

        # Parse results into profiles
        all_profiles = []
        for r in results:
            profile = self._parse_xray_result(r)
            if profile.get("name"):
                all_profiles.append(profile)

        # Deduplicate
        seen = set()
        unique = []
        for p in all_profiles:
            url = p.get("linkedin_url", "")
            if url and url not in seen:
                seen.add(url)
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
        """Run separate searches for each keyword, combine and deduplicate."""
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

            # Search DDG for this keyword
            results = await self._search_ddg(query, per_keyword)

            for r in results:
                profile = self._parse_xray_result(r)
                if profile.get("name"):
                    profile["search_keyword"] = kw
                    all_profiles.append(profile)
                    logger.info(f"[XRAY] + {profile['name']} ({kw})")

            # Small delay between keywords
            await asyncio.sleep(1 + random.uniform(0.5, 1.5))

        # Deduplicate
        seen = set()
        unique = []
        for p in all_profiles:
            url = p.get("linkedin_url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(p)

        logger.info(f"[XRAY] Multi-keyword total: {len(unique)} unique")
        return {
            "success": True,
            "query": " | ".join(queries_used),
            "keywords_searched": keywords_list,
            "total": len(unique),
            "profiles": unique[:max_results],
        }

    async def scrape_public_profile(self, linkedin_url: str) -> dict:
        """Scrape a public LinkedIn profile page using httpx (no browser needed)."""
        if not linkedin_url.startswith("http"):
            linkedin_url = "https://www.linkedin.com/in/" + linkedin_url

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                resp = await client.get(linkedin_url)
                html = resp.text

                profile = {"linkedin_url": linkedin_url}

                # Extract name from meta tags or title
                name_match = re.search(r'<title>([^|<]+)', html)
                if name_match:
                    raw = name_match.group(1).strip()
                    # "John Smith | LinkedIn" -> "John Smith"
                    raw = raw.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
                    if raw:
                        profile["name"] = raw

                # Try og:title
                if not profile.get("name"):
                    og_match = re.search(r'property="og:title"\s+content="([^"]+)"', html)
                    if og_match:
                        profile["name"] = og_match.group(1).split("|")[0].strip()

                # Extract headline
                headline_match = re.search(r'class="text-body-medium[^"]*"[^>]*>([^<]+)', html)
                if headline_match:
                    headline = headline_match.group(1).strip()
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

                # Extract location
                loc_match = re.search(r'<span[^>]*class="[^"]*t-black--light[^"]*"[^>]*>([^<]+)', html)
                if loc_match:
                    profile["location"] = loc_match.group(1).strip()

                # Extract about from meta description
                desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
                if desc_match:
                    profile["bio"] = desc_match.group(1)[:1000]

                # Extract structured data (JSON-LD)
                jsonld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                if jsonld_match:
                    try:
                        ld = json.loads(jsonld_match.group(1))
                        if isinstance(ld, dict):
                            if ld.get("name"):
                                profile["name"] = ld["name"]
                            if ld.get("jobTitle"):
                                profile["job_title"] = ld["jobTitle"]
                            if ld.get("worksFor", {}).get("name"):
                                profile["company"] = ld["worksFor"]["name"]
                            if ld.get("address", {}).get("addressLocality"):
                                profile["location"] = ld["address"]["addressLocality"]
                            if ld.get("description"):
                                profile["bio"] = ld["description"][:1000]
                    except Exception:
                        pass

                profile["scraped_at"] = datetime.now().isoformat()

                if profile.get("name"):
                    return {"success": True, "profile": profile}
                else:
                    return {"error": "Could not extract profile data"}

        except Exception as e:
            return {"error": str(e)[:300]}

    def _parse_xray_result(self, result: dict) -> dict:
        """Parse a search result into profile data."""
        profile = {
            "linkedin_url": result.get("url", ""),
            "source": "xray_search",
            "scraped_at": datetime.now().isoformat(),
        }

        title = result.get("title", "")
        snippet = result.get("snippet", "")

        # Parse title
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

        # Parse snippet
        if snippet:
            loc_match = re.search(r'(?:Location|Located in|Based in)[:\s]+([^·\n]+)', snippet, re.I)
            if loc_match:
                profile["location"] = loc_match.group(1).strip()
            if not profile.get("bio"):
                profile["bio"] = snippet[:500]

        # Fallback: extract name from URL
        if not profile.get("name"):
            url = profile.get("linkedin_url", "")
            match = re.search(r'linkedin\.com/in/([^/?]+)', url)
            if match:
                slug = match.group(1)
                name = slug.replace("-", " ").title()
                profile["name"] = name

        return profile

    def _build_xray_query(self, keywords, title, company, location, industry) -> str:
        """Build X-Ray search query."""
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
xray = XRaySearcher()
