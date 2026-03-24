import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import random
import json
import logging
import asyncio
from langchain_core.tools import tool

logger = logging.getLogger('ResearchAgentLogger')

BASE = "https://www.twitter-trending.com"

# Use Session to optimize connection speed
session = requests.Session()

def get_soup(url):
    # List of User-Agents to rotate (reduces blocking)
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
        # Add a slight random delay of 1-3s to avoid rate limiting
        # time.sleep(random.uniform(1, 3))

        res = session.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        # Prefer 'lxml' if installed, otherwise use 'html.parser'
        return BeautifulSoup(res.text, "lxml" if "lxml" in str(BeautifulSoup) else "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"Error accessing {url}: {e}")
        return None


# ===== 1. FEATURED (Fetch by Day/Week/Month) =====
def get_featured(country="united-states", mode="month"):
    """
    mode: 'day', 'week', 'month' (mặc định month)
    """
    url = f"{BASE}/{country}/en"
    soup = get_soup(url)
    if not soup:
        return []

    # Map ID corresponding to Mode
    mode_map = {
        "day": "gun_one_c",
        "week": "hafta_one_c",
        "month": "ay_one_c"
    }

    container_id = mode_map.get(mode.lower(), "ay_one_c")
    container = soup.find("div", id=container_id)

    if not container:
        return []

    results = []
    items = container.select(".one_cikan88")

    for item in items:
        a = item.select_one(".sire_kelime a")
        if not a: continue

        keyword = a.get_text(strip=True) # Keyword text
        href = a.get("href", "")

        # Giải mã keyword từ URL (ví dụ: Air%2BCanada -> Air Canada)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        raw_val = query.get("s", [""])[0]
        raw = urllib.parse.unquote(raw_val).replace('+', ' ')

        results.append({
            "keyword": keyword,
            "raw": raw
        })

    return results


def get_statistics(country="united-states", mode="30d"):
    """
    mode: '24h', '7d', hoặc '30d' (mặc định 30d)
    """
    url = f"{BASE}/{country}/statistics"
    soup = get_soup(url)
    if not soup:
        return []

    # Bản đồ chuyển đổi mode sang text hiển thị trên web
    # Map to convert mode to web display text
    mode_map = {
        "24h": "last 24 hours",
        "7d": "last 7 days",
        "30d": "last 30 days"
    }

    target_text = mode_map.get(mode, "last 30 days")
    results = []

    # 1. Find all tablo_s blocks
    blocks = soup.find_all("div", class_="tablo_s")

    target_block = None
    for block in blocks:
        header = block.find("div", class_="tablo_s_baslik")
        if header and target_text in header.get_text().lower():
            target_block = block
            break

    if not target_block:
        print(f"No data found for mode: {mode}")
        return []

    # 2. Get data rows from the selected block
    rows = target_block.select(".tablo_so_siralama")

    for row in rows:
        rank = row.select_one(".tablo_so_sira_no")
        volume = row.select_one(".tablo_so_volume")
        word = row.select_one(".tablo_so_word")

        if not (rank and volume and word):
            continue

        word_text = word.get_text(strip=True)
        # Skip empty rows (hyphens)
        if word_text == "-" or not word_text:
            continue

        results.append({
            "rank": rank.get_text(strip=True),
            "keyword": word_text,
            "volume": volume.get_text(strip=True),
            "source": row.get("data-src", "")
        })

    return results


if __name__ == "__main__":
    # 1. Try fetching Featured for the Week
    print("=== FEATURED (WEEK) ===")
    featured_data = get_featured(mode="month")
    for i, item in enumerate(featured_data, 1):
        print(f"{i}. {item['keyword']}")

    # 2. Try fetching Statistics for 30 days (Default)
    print("\n=== STATISTICS (30 DAYS) ===")
    stats_data = get_statistics(mode="30d")
    for item in stats_data:
        print(f"Rank {item['rank']}: {item['keyword']} - {item['volume']} tweets")


@tool
async def get_twitter_featured_trends(country: str = "united-states", mode: str = "month") -> str:
    """Retrieves featured topics on Twitter by country and time period.
    Args:
        country: The country name (e.g., 'united-states', 'turkey').
        mode: The time period ('day', 'week', 'month'). Defaults to 'month'.
    Returns:
        A JSON string containing a list of featured keywords.
    """
    loop = asyncio.get_running_loop()
    try:
        # Run the blocking function in a separate executor
        result = await loop.run_in_executor(None, get_featured, country, mode)
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
    loop = asyncio.get_running_loop()
    try:
        # Run the blocking function in a separate executor
        result = await loop.run_in_executor(None, get_statistics, country, mode)
        logger.info(f"Raw output from Twitter Statistics Trends for country '{country}' and mode '{mode}':\n{json.dumps(result, ensure_ascii=False, indent=2)}")
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        error_message = f"Lỗi khi lấy Twitter statistics trends: {e}"
        logger.error(error_message)
        return json.dumps({"error": error_message})

twitter_tools = [get_twitter_featured_trends, get_twitter_statistics_trends]
