import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import asyncio
import random
from langchain_core.tools import tool

from research_agent.base.base import BaseToolkit
from research_agent.config import AppConfig, config as default_config


def _get_soup(session, url):
    """Fetch and parse a URL, returning a BeautifulSoup object."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/"
    }
    try:
        res = session.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        return BeautifulSoup(res.text, "lxml" if "lxml" in str(BeautifulSoup) else "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"Error accessing {url}: {e}")
        return None


def _get_featured(session, base_url, country="united-states", mode="month"):
    """Fetch featured trends from Twitter trending site."""
    url = f"{base_url}/{country}/en"
    soup = _get_soup(session, url)
    if not soup:
        return []

    mode_map = {"day": "gun_one_c", "week": "hafta_one_c", "month": "ay_one_c"}
    container_id = mode_map.get(mode.lower(), "ay_one_c")
    container = soup.find("div", id=container_id)
    if not container:
        return []

    results = []
    items = container.select(".one_cikan88")
    for item in items:
        a = item.select_one(".sire_kelime a")
        if not a:
            continue
        keyword = a.get_text(strip=True)
        href = a.get("href", "")
        query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        raw_val = query.get("s", [""])[0]
        raw = urllib.parse.unquote(raw_val).replace('+', ' ')
        results.append({"keyword": keyword, "raw": raw})
    return results


def _get_statistics(session, base_url, country="united-states", mode="30d"):
    """Fetch statistics trends from Twitter trending site."""
    url = f"{base_url}/{country}/statistics"
    soup = _get_soup(session, url)
    if not soup:
        return []

    mode_map = {"24h": "last 24 hours", "7d": "last 7 days", "30d": "last 30 days"}
    target_text = mode_map.get(mode, "last 30 days")
    results = []

    blocks = soup.find_all("div", class_="tablo_s")
    target_block = None
    for block in blocks:
        header = block.find("div", class_="tablo_s_baslik")
        if header and target_text in header.get_text().lower():
            target_block = block
            break

    if not target_block:
        return []

    rows = target_block.select(".tablo_so_siralama")
    for row in rows:
        rank = row.select_one(".tablo_so_sira_no")
        volume = row.select_one(".tablo_so_volume")
        word = row.select_one(".tablo_so_word")
        if not (rank and volume and word):
            continue
        word_text = word.get_text(strip=True)
        if word_text == "-" or not word_text:
            continue
        results.append({
            "rank": rank.get_text(strip=True), "keyword": word_text,
            "volume": volume.get_text(strip=True), "source": row.get("data-src", "")
        })
    return results


class TwitterToolkit(BaseToolkit):
    """Toolkit for Twitter trend scraping tools."""

    def __init__(self, config: AppConfig = None):
        super().__init__(config or default_config)
        cfg = self.config.twitter if hasattr(self.config, 'twitter') else self.config
        self._base_url = cfg.base_url
        self._session = requests.Session()
        self._tools = None

    @property
    def is_available(self) -> bool:
        return True  # Scraping-based, no API key needed

    def get_tools(self) -> list:
        if self._tools is not None:
            return self._tools

        session = self._session
        base_url = self._base_url
        logger = self.logger

        @tool
        async def get_twitter_featured_trends(country: str = "united-states", mode: str = "month") -> str:
            """Retrieves featured topics on Twitter by country and time period.
            Args:
                country: The country name (e.g., 'united-states', 'turkey').
                mode: The time period ('day', 'week', 'month'). Defaults to 'month'.
            Returns:
                A JSON string containing a list of featured keywords.
            """
            try:
                result = await asyncio.to_thread(_get_featured, session, base_url, country, mode)
                logger.info(f"Raw output from Twitter Featured Trends for country '{country}' and mode '{mode}':\n{json.dumps(result, ensure_ascii=False, indent=2)}")
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                error_message = f"Lỗi khi lấy Twitter featured trends: {e}"
                logger.error(error_message)
                return json.dumps({"error": error_message})

        @tool
        async def get_twitter_statistics_trends(country: str = "united-states", mode: str = "30d") -> str:
            """Retrieves Twitter trend statistics by country and time period.
            Args:
                country: The country name (e.g., 'united-states', 'turkey').
                mode: The time period ('24h', '7d', '30d'). Defaults to '30d'.
            Returns:
                A JSON string containing a list of keywords by rank and tweet volume.
            """
            try:
                result = await asyncio.to_thread(_get_statistics, session, base_url, country, mode)
                logger.info(f"Raw output from Twitter Statistics Trends for country '{country}' and mode '{mode}':\n{json.dumps(result, ensure_ascii=False, indent=2)}")
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                error_message = f"Lỗi khi lấy Twitter statistics trends: {e}"
                logger.error(error_message)
                return json.dumps({"error": error_message})

        self._tools = [get_twitter_featured_trends, get_twitter_statistics_trends]
        return self._tools


# --- Backward-compatible module-level exports ---
_twitter_toolkit = TwitterToolkit()
twitter_tools = _twitter_toolkit.get_tools()


if __name__ == "__main__":
    toolkit = TwitterToolkit()
    print("=== FEATURED (MONTH) ===")
    featured_data = _get_featured(toolkit._session, toolkit._base_url, mode="month")
    for i, item in enumerate(featured_data, 1):
        print(f"{i}. {item['keyword']}")

    print("\n=== STATISTICS (30 DAYS) ===")
    stats_data = _get_statistics(toolkit._session, toolkit._base_url, mode="30d")
    for item in stats_data:
        print(f"Rank {item['rank']}: {item['keyword']} - {item['volume']} tweets")
