"""Tools package — all platform-specific toolkits grouped by domain."""
from research_agent.tools.research import (
    TavilyToolkit,
    think,
    skill_discover_trends,
    skill_validate_trends,
    skill_find_top_products,
    skill_write_report,
    fetch_webpage_content,
    fetch_webpage_content_async,
    tavily_search,
    tavily_search_async,
)
from research_agent.tools.google import GoogleAISearchToolkit, GoogleTrendsToolkit
from research_agent.tools.reddit import RedditToolkit
from research_agent.tools.twitter import TwitterToolkit
from research_agent.tools.tiktok import tiktok_tools, close_tiktok_instance
from research_agent.tools.etsy import EtsyToolkit

__all__ = [
    "TavilyToolkit", "think",
    "skill_discover_trends", "skill_validate_trends",
    "skill_find_top_products", "skill_write_report",
    "fetch_webpage_content", "fetch_webpage_content_async",
    "tavily_search", "tavily_search_async",
    "GoogleAISearchToolkit", "GoogleTrendsToolkit",
    "RedditToolkit",
    "TwitterToolkit",
    "tiktok_tools", "close_tiktok_instance",
    "EtsyToolkit",
]
