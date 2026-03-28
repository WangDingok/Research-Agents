import json
import serpapi
import pathlib
import matplotlib.pyplot as plt
import math
import asyncio
from datetime import datetime
from typing import List
from langchain_core.tools import tool

from research_agent.base.base import BaseToolkit
from research_agent.config import AppConfig, config as default_config

_run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


def _create_and_save_chart(timeline_data, averages_data, keyword, charts_dir, run_timestamp):
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

        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '_', ',')).rstrip()
        chart_filename = f"{safe_keyword.replace(' ', '_').replace(',', '')}_{run_timestamp}.png"
        chart_path_obj = pathlib.Path(charts_dir) / chart_filename
        plt.savefig(chart_path_obj)
        plt.close()
        return str(chart_path_obj)
    except Exception as e:
        return f"Error creating trend chart: {e}"


class GoogleAISearchToolkit(BaseToolkit):
    """Toolkit for Google AI Search (SGE) via SerpAPI."""

    def __init__(self, config: AppConfig = None):
        super().__init__(config or default_config)
        cfg = self.config.google if hasattr(self.config, 'google') else self.config
        self._api_key = cfg.serpapi_key
        self._client = serpapi.Client(api_key=self._api_key) if self._api_key else None
        self._tools = None

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def get_tools(self) -> list:
        if self._tools is not None:
            return self._tools
        if not self.is_available:
            self._tools = []
            return self._tools

        client = self._client
        logger = self.logger

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
            def sync_search():
                return client.search({"engine": "google_ai_mode", "q": query, "geo": "US"})

            results = await asyncio.to_thread(sync_search)
            results_dict = results.as_dict()
            logger.info(f"Raw output from Google AI Search for query '{query}':\n{json.dumps(results_dict, ensure_ascii=False, indent=2)}")

            output = {
                "reconstructed_markdown": results_dict.get("reconstructed_markdown"),
                "references": results_dict.get("references"),
            }
            return json.dumps(output, ensure_ascii=False)

        self._tools = [google_ai_search]
        return self._tools


class GoogleTrendsToolkit(BaseToolkit):
    """Toolkit for Google Trends analysis via SerpAPI."""

    def __init__(self, config: AppConfig = None):
        super().__init__(config or default_config)
        cfg = self.config.google if hasattr(self.config, 'google') else self.config
        self._api_key = cfg.serpapi_key
        self._client = serpapi.Client(api_key=self._api_key) if self._api_key else None
        self._charts_dir = str(self.config.charts_dir) if hasattr(self.config, 'charts_dir') else str(default_config.charts_dir)
        self._tools = None

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def get_tools(self) -> list:
        if self._tools is not None:
            return self._tools
        if not self.is_available:
            self._tools = []
            return self._tools

        client = self._client
        logger = self.logger
        charts_dir = self._charts_dir
        run_timestamp = _run_timestamp

        @tool
        async def search_google_trends_by_keyword(keyword: List[str], geo: str = "US", timeframe: str = "today 1-m") -> str:
            """
            Searches for trends for a list of keywords on Google Trends over a period of time.
            It processes keywords in batches of up to 5, and for each batch, it returns a summary of trend stability,
            recent spikes, and related rising queries. It also generates and saves a time series chart for each batch.

            Args:
                keyword: A list of keywords to search for. The tool will automatically batch them.
                geo: The geographical region.
                timeframe: The time period.

            Returns:
                A JSON string containing the aggregated search results from all batches.
            """
            # Normalize: LLM may pass keyword as a plain string instead of a list
            kw_list = [keyword] if isinstance(keyword, str) else keyword

            all_batch_results = []

            def sync_search(q: str, data_type: str = "TIMESERIES"):
                return client.search({
                    "engine": "google_trends", "q": q, "geo": geo,
                    "date": timeframe, "data_type": data_type,
                })

            for i in range(0, len(kw_list), 5):
                batch_keywords = kw_list[i:i+5]
                keyword_str = ", ".join(batch_keywords)

                try:
                    results = await asyncio.to_thread(sync_search, keyword_str, "TIMESERIES")
                    results_dict = results.as_dict()
                    logger.info(f"Raw output from Google Trends (TIMESERIES) for keyword batch '{keyword_str}':\n{json.dumps(results_dict, ensure_ascii=False, indent=2)}")

                    simplified_output = {}
                    chart_path = None

                    if "interest_over_time" in results_dict:
                        timeline_data = results_dict["interest_over_time"].get("timeline_data", [])
                        averages_data = results_dict["interest_over_time"].get("averages", [])

                        if timeline_data and averages_data:
                            chart_path = await asyncio.to_thread(
                                _create_and_save_chart, timeline_data, averages_data,
                                keyword_str, charts_dir, run_timestamp
                            )

                        trend_summaries = []
                        if timeline_data and averages_data:
                            for j, query_info in enumerate(averages_data):
                                query = query_info.get("query")
                                if not query:
                                    continue

                                values = []
                                for item in timeline_data:
                                    item_values = item.get("values")
                                    if isinstance(item_values, list) and len(item_values) > j:
                                        value_dict = item_values[j]
                                        if isinstance(value_dict, dict) and "extracted_value" in value_dict:
                                            values.append(value_dict["extracted_value"])
                                if not values:
                                    continue

                                summary = {"query": query}
                                n = len(values)
                                avg = sum(values) / n if n > 0 else 0

                                if n > 1:
                                    variance = sum([(x - avg) ** 2 for x in values]) / n if n > 0 else 0
                                    std_dev = math.sqrt(variance)
                                    stability = "stable" if avg > 0 and (std_dev / avg) <= 0.5 else "volatile"
                                    is_spike = n > 4 and avg > 0 and (sum(values[-4:]) / 4) > (avg * 1.5)

                                    quarter = max(1, n // 4)
                                    early_avg = sum(values[:quarter]) / quarter
                                    recent_avg = sum(values[-quarter:]) / quarter
                                    if early_avg > 0:
                                        change_pct = ((recent_avg - early_avg) / early_avg) * 100
                                    else:
                                        change_pct = 100.0 if recent_avg > 0 else 0.0
                                    if change_pct > 20:
                                        direction = "rising"
                                    elif change_pct < -20:
                                        direction = "declining"
                                    else:
                                        direction = "flat"

                                    summary.update({
                                        "avg_interest": round(avg, 2),
                                        "recent_avg": round(recent_avg, 2),
                                        "stability": stability,
                                        "direction": direction,
                                        "change_pct": round(change_pct, 1),
                                        "is_recent_spike": is_spike,
                                        "peak_value": max(values),
                                        "min_value": min(values),
                                    })
                                else:
                                    summary.update({"avg_interest": round(avg, 2), "direction": "insufficient_data"})
                                trend_summaries.append(summary)

                        if trend_summaries:
                            ranked = sorted(trend_summaries, key=lambda s: s.get("recent_avg", 0), reverse=True)
                            for rank, s in enumerate(ranked, 1):
                                s["rank_in_batch"] = rank
                            simplified_output["interest_summary"] = ranked

                    # Related queries — batch up to 5 keywords comma-separated
                    try:
                        rq_results = await asyncio.to_thread(sync_search, keyword_str, "RELATED_QUERIES")
                        rq_dict = rq_results.as_dict()
                        logger.info(f"Raw output from Google Trends (RELATED_QUERIES) for '{keyword_str}':\n{json.dumps(rq_dict, ensure_ascii=False, indent=2)}")
                        related = rq_dict.get("related_queries", {})
                        rising_queries = [item.get("query") for item in related.get("rising", []) if item.get("query")]
                        top_queries = [item.get("query") for item in related.get("top", []) if item.get("query")]
                        if rising_queries:
                            simplified_output["rising_related_queries"] = rising_queries
                        if top_queries:
                            simplified_output["top_related_queries"] = top_queries
                    except Exception as rq_err:
                        logger.warning(f"Could not fetch related queries for '{keyword_str}': {rq_err}")

                    if chart_path:
                        simplified_output["trend_chart_path"] = chart_path

                    if not simplified_output:
                        all_batch_results.append({"batch_keywords": keyword_str, "error": "No trend data or related queries found."})
                    else:
                        all_batch_results.append({"batch_keywords": keyword_str, "results": simplified_output})

                except Exception as e:
                    error_message = f"An error occurred while processing batch '{keyword_str}': {e}"
                    logger.error(error_message)
                    all_batch_results.append({"batch_keywords": keyword_str, "error": error_message})

            return json.dumps(all_batch_results, ensure_ascii=False)

        self._tools = [search_google_trends_by_keyword]
        return self._tools


# --- Backward-compatible module-level exports ---
_ai_toolkit = GoogleAISearchToolkit()
_trends_toolkit = GoogleTrendsToolkit()
google_ai_search_tools = _ai_toolkit.get_tools()
google_trends_tools = _trends_toolkit.get_tools()
