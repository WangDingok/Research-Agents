import os
import json
import serpapi
import pathlib
import matplotlib.pyplot as plt
import math
import asyncio
import logging
from datetime import datetime
from typing import List
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('ResearchAgentLogger')
run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

@tool
async def google_ai_search(query: str) -> str:
    """
    Performs a search using Google's AI-powered search mode (SGE).
    This tool is useful for getting a comprehensive AI-generated summary of a topic,
    often including niche ideas, key points, and product suggestions.

    Args:
        query: The search query.

    Returns:
        A JSON string containing AI-generated text blocks and search results.
    """
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        return "Error: SERPAPI_API_KEY is not set in the environment."

    client = serpapi.Client(api_key=api_key)

    def sync_search():
        """Cuộc gọi tìm kiếm đồng bộ để chạy trong một executor."""
        params = {
            "engine": "google_ai_mode",
            "q": query,
            "geo": "US",
        }
        return client.search(params)

    results = await asyncio.to_thread(sync_search)
    results_dict = results.as_dict()
    logger.info(f"Raw output from Google AI Search for query '{query}':\n{json.dumps(results_dict, ensure_ascii=False, indent=2)}")

    # Return the most important parts for the agent to coordinate analysis
    output = {
        "reconstructed_markdown": results_dict.get("reconstructed_markdown"),
        "references": results_dict.get("references"),
        #"text_blocks": results_dict.get("text_blocks"),
    }
    return json.dumps(output, ensure_ascii=False)

def _create_and_save_chart(timeline_data, averages_data, keyword, run_timestamp):
    """Synchronous function to create and save a chart, designed to run in a separate thread."""
    try:
        queries = [q.get("query") for q in averages_data if q.get("query")]
        dates = [item["date"] for item in timeline_data]

        plt.figure(figsize=(12, 6))

        for i, query in enumerate(queries):
            query_dates, query_values = [], []
            for item in timeline_data:
                item_values = item.get("values")
                if isinstance(item_values, list) and len(item_values) > i:
                    value_dict = item_values[i]
                    if isinstance(value_dict, dict) and "extracted_value" in value_dict:
                        query_dates.append(item["date"])
                        query_values.append(value_dict["extracted_value"])
            if query_values:
                plt.plot(query_dates, query_values, label=query, marker='o', linestyle='-')

        plt.xlabel("Date")
        plt.ylabel("Interest Score")
        plt.title(f"Google Trends Interest Over Time for: {keyword}")
        plt.legend()
        plt.grid(True)
        tick_spacing = max(1, len(dates) // 10) if len(dates) > 10 else 1
        plt.xticks(dates[::tick_spacing], rotation=45, ha="right")
        plt.tight_layout()

        # Save charts to a dedicated output directory.
        output_dir = pathlib.Path("output/trend_charts")
        output_dir.mkdir(exist_ok=True)
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '_', ',')).rstrip()
        chart_filename = f"{safe_keyword.replace(' ', '_').replace(',', '')}_{run_timestamp}.png"
        chart_path_obj = output_dir / chart_filename
        plt.savefig(chart_path_obj)
        plt.close() # Close the plot to free up memory
        chart_path = str(chart_path_obj)
        logger.info(f"Trend chart created and saved at: {chart_path}")
        return chart_path
    except Exception as e:
        error_message = f"Error creating trend chart: {e}"
        logger.error(error_message)
        return error_message

@tool(parse_docstring=True)
async def search_google_trends_by_keyword(keyword: str, geo: str = "US", timeframe: str = "today 1-m") -> str:
    """
    Searches for trends for one or more specific keywords (up to 5) on Google Trends over a period of time.
    It returns a summary of the trend's stability, recent spikes, and related rising queries.
    It also generates and saves a time series chart of the trend.

    Args:
        keyword: A string of keywords to search for (up to 5).
        geo: The geographical region.
        timeframe: The time period.

    Returns:
        A JSON string containing the search result text blocks.
    """
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        return "Error: SERPAPI_API_KEY is not set in the environment."

    client = serpapi.Client(api_key=api_key)

    def sync_search():
        """Synchronous search call to run in an executor."""
        params = {
            "engine": "google_trends",
            "q": keyword,
            "geo": geo,
            "date": timeframe,
            "data_type": "TIMESERIES", # This often includes related queries as well
        }
        return client.search(params)

    results = await asyncio.to_thread(sync_search)
    results_dict = results.as_dict()
    logger.info(f"Raw output from Google Trends for keyword '{keyword}':\n{json.dumps(results_dict, ensure_ascii=False, indent=2)}")

    simplified_output = {}
    chart_path = None

    # Process "Interest Over Time" and "Trend Analysis"
    if "interest_over_time" in results_dict:
        timeline_data = results_dict["interest_over_time"].get("timeline_data", [])
        averages_data = results_dict["interest_over_time"].get("averages", [])

        # Generate and save chart
        if timeline_data and averages_data:
            chart_path = await asyncio.to_thread(
                _create_and_save_chart,
                timeline_data,
                averages_data,
                keyword,
                run_timestamp
            )

        trend_summaries = []
        if timeline_data and averages_data:
            for i, query_info in enumerate(averages_data):
                query = query_info.get("query")
                if not query:
                    continue

                values = []
                for item in timeline_data:
                    item_values = item.get("values")
                    if isinstance(item_values, list) and len(item_values) > i:
                        value_dict = item_values[i]
                        if isinstance(value_dict, dict) and "extracted_value" in value_dict:
                            values.append(value_dict["extracted_value"])
                if not values:
                    continue

                summary = { "query": query }
                n = len(values)
                avg = sum(values) / n if n > 0 else 0

                if n > 1:
                    n = len(values)
                    variance = sum([(x - avg) ** 2 for x in values]) / n if n > 0 else 0
                    std_dev = math.sqrt(variance)
                    stability = "stable" if avg > 0 and (std_dev / avg) <= 0.5 else "volatile"
                    is_spike = n > 4 and avg > 0 and (sum(values[-4:]) / 4) > (avg * 1.5)
                    trend_description = (f"The trend for '{query}' is {stability} with an average interest score of {avg:.2f} (std dev: {std_dev:.2f}).")
                    if is_spike:
                        trend_description += " It has experienced a recent spike in interest."
                    summary.update({"stability": stability, "is_recent_spike": is_spike, "trend_description": trend_description})
                else:
                    summary["trend_description"] = f"Not enough data to analyze trend for '{query}'. Average interest is {avg:.2f}."
                trend_summaries.append(summary)
        if trend_summaries:
            simplified_output["interest_summary"] = trend_summaries

    # Process "Related Queries"
    if "related_queries" in results_dict:
        related = results_dict.get("related_queries", {})
        rising_queries = [item.get("query") for item in related.get("rising", []) if item.get("query")]
        top_queries = [item.get("query") for item in related.get("top", []) if item.get("query")]

        if rising_queries:
            simplified_output["rising_related_queries"] = rising_queries
        if top_queries:
            simplified_output["top_related_queries"] = top_queries

    if chart_path:
        simplified_output["trend_chart_path"] = chart_path

    if not simplified_output:
        return json.dumps({"error": "No trend data or related queries found."})

    return json.dumps(simplified_output, ensure_ascii=False)


@tool
async def get_google_trending_now(geo: str = "US") -> str:
    """Retrieves general trending topics on Google Trends for a specific region."""
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        return "Error: SERPAPI_API_KEY is not set in the environment."

    client = serpapi.Client(api_key=api_key)

    def sync_search():
        """Cuộc gọi tìm kiếm đồng bộ để chạy trong một executor."""
        params = {
            "engine": "google_trends_trending_now",
            "geo": geo,
            "hours": 168,
            "no_cache": False,
        }
        return client.search(params)

    results = await asyncio.to_thread(sync_search)
    results_dict = results.as_dict()
    logger.info(f"Raw output from Google Trends (Trending Now) for geo '{geo}':\n{json.dumps(results_dict, ensure_ascii=False, indent=2)}")

    # Process results to limit the number and remove unnecessary data
    if "trending_searches" in results_dict and isinstance(
        results_dict.get("trending_searches"), list
    ):
        top_trends = results_dict["trending_searches"][:20]
        simplified_trends = []
        for trend in top_trends:
            if isinstance(trend, dict):
                simplified_trends.append({
                    "query": trend.get("query"),
                    "trend_breakdown": (trend.get("trend_breakdown") or [])[:10],
                    #"search_volume": trend.get("search_volume"),
                    #"increase_percentage": trend.get("increase_percentage"),
                    #"categories": trend.get("categories"),
                    #"start_timestamp": trend.get("start_timestamp")
                })
        results_dict = {"trending_searches": simplified_trends}

    return json.dumps(results_dict, ensure_ascii=False)

google_ai_search_tools = [google_ai_search]
google_trends_tools = [search_google_trends_by_keyword, get_google_trending_now]
