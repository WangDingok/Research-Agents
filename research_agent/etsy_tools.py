import os
import requests
import json
import asyncio
from collections import Counter
from typing import List, Dict, Any
from langchain_core.tools import tool
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('ResearchAgentLogger')

class EtsyTool:
    """
    A utility class to interact with the Etsy Scraper API and analyze product trends.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ETSY_API_KEY")
        if not self.api_key:
            raise ValueError("ETSY_API_KEY is not set in environment variables.")
        self.base_url = "https://etsy-scraper.omkar.cloud/etsy"

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Makes a request to the Etsy Scraper API."""
        headers = {"API-Key": self.api_key}
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", headers=headers, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 401: # Invalid API key
                return {"error": "Invalid API key."}
            if response.status_code == 429: # Rate limit exceeded
                return {"error": "Request rate limit exceeded."}
            return {"error": f"HTTP Error: {http_err}"}
        except Exception as e: # Other errors
            return {"error": f"An error occurred: {e}"}

    def search_listings(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Searches for products by keyword."""
        data = self._make_request("search", {"keyword": keyword})
        if "error" in data or "listings" not in data:
            return []
        return data.get("listings", [])[:limit]

    def get_listing_details(self, listing_id: str) -> Dict[str, Any]:
        """Retrieves detailed information for a specific product listing."""
        return self._make_request("listing", {"listing_id": listing_id})

    def analyze_trends_from_listings(self, listings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyzes trends from a list of product listing details."""
        if not listings:
            return {"error": "No listings provided for analysis."}

        all_tags = [tag for listing in listings if listing and "tags" in listing for tag in listing["tags"]]
        all_categories = [cat for listing in listings if listing and "categories" in listing for cat in listing["categories"]]
        prices = [l.get("price_usd") for l in listings if l and l.get("price_usd") is not None]
        bestseller_count = sum(1 for l in listings if l and l.get("flags", {}).get("bestseller"))

        total_listings = len(listings)
        avg_price = sum(prices) / len(prices) if prices else 0
        bestseller_percent = (bestseller_count / total_listings) * 100 if total_listings > 0 else 0

        return {
            "total_listings_analyzed": total_listings,
            "trending_tags": [tag for tag, count in Counter(all_tags).most_common(10)],
            "trending_categories": [cat for cat, count in Counter(all_categories).most_common(5)],
            "average_price_usd": round(avg_price, 2),
            "bestseller_percentage": round(bestseller_percent, 2),
        }

_etsy_tool_instance = None
try:
    _etsy_tool_instance = EtsyTool()
except ValueError as e: # Unable to initialize EtsyTool
    logger.warning(f"Could not initialize EtsyTool, Etsy tools will not be available: {e}")

@tool
async def search_etsy_trends_by_keyword(keyword: str, listings_to_analyze: int = 20) -> str:
    """
    Searches for a keyword on Etsy, retrieves details for top listings,
    and analyzes them to identify product trends. The tool returns popular tags,
    categories, average price, and bestseller percentage.
    """
    if not _etsy_tool_instance:
        return json.dumps({"error": "Etsy tool is not available. Please check ETSY_API_KEY."})

    loop = asyncio.get_running_loop()

    def sync_search_and_analyze():
        search_results = _etsy_tool_instance.search_listings(keyword, limit=listings_to_analyze) # Search for listings
        if not search_results: # No listings found
            return {"error": f"No listings found for keyword '{keyword}'."}

        listing_ids = [listing['listing_id'] for listing in search_results if 'listing_id' in listing]
        listing_details = [_etsy_tool_instance.get_listing_details(lid) for lid in listing_ids]

        return _etsy_tool_instance.analyze_trends_from_listings([d for d in listing_details if d and "error" not in d])

    try: # Perform search and analysis
        analysis_result = await loop.run_in_executor(None, sync_search_and_analyze) # Execute in a separate thread
        logger.info(f"Raw output from Etsy for keyword '{keyword}':\n{json.dumps(analysis_result, ensure_ascii=False, indent=2)}") # Log raw output
        return json.dumps(analysis_result, ensure_ascii=False) # Return JSON result
    except Exception as e: # Handle unexpected errors
        error_message = f"An unexpected error occurred during Etsy trend analysis: {e}" # Construct error message
        logger.error(error_message) # Log error
        return json.dumps({"error": error_message}) # Return error as JSON

etsy_tools = [search_etsy_trends_by_keyword] if _etsy_tool_instance else []
