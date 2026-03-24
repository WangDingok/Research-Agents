"""Research Tools.

This module provides search and content processing utilities for the research agent,
using Tavily for URL discovery and fetching full webpage content.
"""

import httpx
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from typing_extensions import Annotated, Literal
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch and convert webpage content to markdown.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Webpage content as markdown
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return markdownify(response.text)
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


@tool
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
    fetch_content: bool = False,
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs. Can optionally fetch the full content of webpages.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 5)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')
        fetch_content: If True, fetches the full content of each URL as markdown.
                       If False (default), returns the content snippets from the search results to save costs.

    Returns:
        Formatted search results with snippets or full webpage content.
    """
    # Get current date and date 3 months ago
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    # Use Tavily to discover URLs
    search_results = tavily_client.search(
        query,
        max_results=max_results,
        topic=topic,
        # start_date=start_date.strftime("%Y-%m-%d"),
        # end_date=end_date.strftime("%Y-%m-%d"),
        time_range='month',
        country="united states"
    )

    # Fetch full content for each URL if requested
    result_texts = []
    for result in search_results.get("results", []):
        url = result["url"]
        title = result["title"]

        if fetch_content:
            # Fetch webpage content
            content = fetch_webpage_content(url)
        else:
            # Use the snippet from the search result to save costs
            content = result.get("content", "No snippet available.")

        result_text = f"""## {title}
**URL:** {url}

{content}

---
"""
        result_texts.append(result_text)

    # Format final response
    response = f"""🔍 Found {len(result_texts)} result(s) for '{query}':

{chr(10).join(result_texts)}"""

    return response


@tool(parse_docstring=True)
def think(reflection: str) -> str:
    """Công cụ để tư duy, lập kế hoạch và phản ánh một cách có hệ thống.

    Sử dụng công cụ này như một "bảng nháp" nội bộ để cấu trúc suy nghĩ của bạn.
    Nó cho phép bạn dừng lại, phân tích tình hình và quyết định các bước tiếp theo một cách rõ ràng.

    When to use:
    - **Trước khi hành động**: Để lập kế hoạch các bước hoặc chia nhỏ một nhiệm vụ phức tạp.
    - **Sau khi nhận thông tin**: Để phân tích kết quả từ một công cụ khác (ví dụ: `tavily_search`, `google-trends-agent`) và rút ra những hiểu biết chính.
    - **Khi gặp bế tắc**: Để đánh giá lại tình hình và xem xét các hướng tiếp cận khác.
    - **Trước khi đưa ra câu trả lời cuối cùng**: Để cấu trúc và tóm tắt các phát hiện của bạn.

    Nội dung phản ánh nên giải quyết:
    1.  **Mục tiêu hiện tại**: Tôi đang cố gắng đạt được điều gì ở bước này?
    2.  **Phân tích thông tin**: Tôi đã có thông tin gì? Thông tin đó có ý nghĩa gì?
    3.  **Đánh giá khoảng trống**: Tôi còn thiếu thông tin gì để hoàn thành mục tiêu?
    4.  **Quyết định chiến lược**: Bước tiếp theo hợp lý nhất là gì? (ví dụ: gọi một công cụ khác, kết hợp kết quả, hay kết thúc và báo cáo).

    Args:
        reflection: Ghi lại chi tiết suy nghĩ, phân tích, kế hoạch và các bước tiếp theo của bạn.

    Returns:
        Xác nhận rằng suy nghĩ đã được ghi lại để ra quyết định.
    """
    return f"Suy nghĩ đã được ghi lại: {reflection}"
