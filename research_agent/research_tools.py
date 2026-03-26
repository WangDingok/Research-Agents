"""Research Tools.

This module provides search and content processing utilities for the research agent,
using Tavily for URL discovery and fetching full webpage content.
"""

import httpx
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from typing import List
from typing_extensions import Annotated, Literal
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncio
import json

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

async def fetch_webpage_content_async(url: str, timeout: float = 10.0) -> str:
    """Asynchronously fetch and convert webpage content to markdown."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return markdownify(response.text)
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


@tool
async def tavily_search(
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
    def sync_search():
        """Synchronous search call to run in an executor."""
        return tavily_client.search(
            query,
            max_results=max_results,
            topic=topic,
            time_range='month',
            country="united states"
        )

    # Run the synchronous search in a separate thread to avoid blocking the event loop.
    search_results_json = await asyncio.to_thread(sync_search)

    results = search_results_json.get("results", [])
    result_texts = []

    # Prepare content fetching tasks if needed
    if fetch_content and results:
        content_tasks = [fetch_webpage_content_async(res["url"]) for res in results]
        contents = await asyncio.gather(*content_tasks)
    else:
        contents = [res.get("content", "No snippet available.") for res in results]

    # Combine results with content
    for i, result in enumerate(results):
        url = result["url"]
        title = result["title"]
        content = contents[i]

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

@tool
async def tavily_search_async(
    queries: List[str],
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    fetch_content: bool = False,
) -> str:
    """Search the web asynchronously for information on a list of queries and return results in a batch.

    Args:
        queries: A list of search queries to execute in parallel.
        max_results: Maximum number of results to return for each query (default: 3).
        topic: Topic filter for each query - 'general', 'news', or 'finance' (default: 'general').
        fetch_content: If True, fetches the full content of each URL as markdown.
                       If False (default), returns content snippets.

    Returns:
        A JSON string containing a list of search results for each query.
    """

    async def _search_one(query: str):
        try:
            def sync_search():
                """Synchronous search call to run in an executor."""
                return tavily_client.search(
                    query,
                    max_results=max_results,
                    topic=topic,
                    time_range='month',
                    country="united states"
                )

            # Run the synchronous search in a separate thread.
            search_results = await asyncio.to_thread(sync_search)
            result_texts = []
            for result in search_results.get("results", []):
                url = result["url"]
                title = result["title"]

                if fetch_content:
                    content = await fetch_webpage_content_async(url)
                else:
                    content = result.get("content", "No snippet available.")

                result_text = f"""## {title}
**URL:** {url}

{content}

---
"""
                result_texts.append(result_text)

            response = f"""🔍 Found {len(result_texts)} result(s) for '{query}':

{chr(10).join(result_texts)}"""
            return {"query": query, "results": response}
        except Exception as e:
            return {"query": query, "error": f"An error occurred: {str(e)}"}

    tasks = [_search_one(q) for q in queries]
    all_results = await asyncio.gather(*tasks)

    return json.dumps(all_results, ensure_ascii=False)


@tool
def skill_discover_trends() -> str:
    """Kỹ năng khám phá trend: cách tìm các chủ đề/niche đang lan truyền phù hợp để làm áo.

    Gọi khi người dùng muốn tìm trend mới, chủ đề hot, hoặc niche tiềm năng
    mà chưa có danh sách keyword cụ thể.

    Returns:
        Hướng dẫn cách khám phá trend từ nhiều nguồn song song.
    """
    return """
**Kỹ năng: Khám phá Trend**

Khởi chạy ĐỒNG THỜI 3 agent sau:
1.  `google-ai-search-agent` — Tìm các trend đang nổi. Khi giao task, yêu cầu agent:
    - Loại bỏ trend chết nhanh (dưới 7 ngày). Chỉ lấy trend bền từ 10 ngày trở lên.
    - Ưu tiên: EVENT-BASED (sự kiện có lịch), SEASONAL (mùa/lễ), CULTURE (phong trào/meme lâu dài),
      VIRAL TOPIC (lan truyền rộng, dễ hiểu), IDENTITY/COMMUNITY (pride, fandom, nghề nghiệp...).
    - Loại bỏ: tin chính trị thoáng qua, scandal cá nhân, sự kiện 1 ngày.
2.  `twitter-search-agent` — Tìm các niche đang được thảo luận sôi nổi trên mạng xã hội.
3.  `etsy-search-agent` — Gọi `search_etsy_trends_by_keyword` với `keywords=[]` để lấy
    tổng quan thị trường áo thun: top tags, phân bố giá, mức cạnh tranh, tags thành công.

Sau khi có kết quả: tổng hợp danh sách keyword ứng viên, phân loại theo 5 loại trend trên.
"""


@tool
def skill_validate_trends() -> str:
    """Kỹ năng xác minh trend: cách đánh giá độ bền, tâm lý cộng đồng và tiềm năng Etsy của keywords.

    Gọi khi đã có danh sách keyword và muốn biết keyword nào thực sự đáng đầu tư,
    hoặc khi người dùng hỏi về tiềm năng của một trend/niche cụ thể.

    Returns:
        Hướng dẫn cách xác minh trend từ nhiều nguồn song song.
    """
    return """
**Kỹ năng: Xác minh Trend**

Khởi chạy ĐỒNG THỜI 3 agent sau:
1.  `google-trends-agent` — Phân tích biểu đồ xu hướng và sự ổn định theo thời gian
    (rising/stable/declining, spike gần đây, so sánh các keyword).
2.  `tavily-search-agent` — Tìm thảo luận trên diễn đàn, blog, cộng đồng để đánh giá
    tâm lý công chúng và xác nhận trend không phải thoáng qua.
3.  `etsy-search-agent` — Dùng `search_etsy_trends_by_keyword` để phân tích thị trường ngách:
    engagement, mức giá, mức cạnh tranh, seller concentration.

Sau khi có kết quả: chọn lọc danh sách keyword cuối cùng đáng đầu tư dựa trên cả 3 nguồn.
"""


@tool
def skill_find_top_products() -> str:
    """Kỹ năng tìm sản phẩm bán chạy: cách lấy top listings Etsy và ý tưởng thiết kế cho keywords.

    Gọi khi người dùng muốn xem sản phẩm thực tế đang bán chạy,
    hoặc muốn tìm cảm hứng thiết kế cho một trend/niche cụ thể.

    Returns:
        Hướng dẫn cách lấy sản phẩm bán chạy và tìm cảm hứng thiết kế song song.
    """
    return """
**Kỹ năng: Tìm sản phẩm bán chạy + Cảm hứng thiết kế**

Khởi chạy ĐỒNG THỜI 3 agent sau:
1.  `etsy-search-agent` — Dùng `get_etsy_top_listings` để lấy TOP sản phẩm bán chạy nhất
    cho mỗi keyword: hình ảnh, link, giá, lượt thích, lượt xem, tên shop.
    Dữ liệu sẽ hiển thị trực quan trên Chat UI.
2.  `google-ai-search-agent` — Tìm ý tưởng thiết kế, mẫu áo thun, bảng màu liên quan đến keyword.
3.  `tavily-search-agent` — Tìm ví dụ thiết kế và sản phẩm liên quan trên web.
"""


@tool
def skill_write_report() -> str:
    """Kỹ năng viết báo cáo: chuẩn định dạng, trích dẫn nguồn và tổng hợp kết quả nghiên cứu.

    Gọi trước khi soạn báo cáo tổng hợp cuối cùng để đảm bảo đúng chuẩn trình bày.

    Returns:
        Hướng dẫn định dạng và viết báo cáo chuyên nghiệp.
    """
    return """
**Kỹ năng: Viết Báo cáo**

**Tổng hợp nội dung:**
- Nêu bật những xu hướng được xác nhận từ nhiều nguồn nhất.
- Hợp nhất trích dẫn: mỗi URL duy nhất chỉ có một số trích dẫn, đánh số tuần tự.

**Định dạng:**
- Dùng ## cho phần chính, ### cho phần phụ.
- Viết đoạn văn phân tích sâu, không chỉ liệt kê gạch đầu dòng.
- KHÔNG dùng ngôn ngữ tự tham chiếu ("Tôi đã tìm thấy..."). Viết như báo cáo chuyên nghiệp.

**Trích dẫn nguồn:**
- Trích dẫn ngay trong văn bản: [1], [2], [3].
- Kết thúc bằng `### Nguồn` liệt kê toàn bộ:
  [1] Tiêu đề: URL
  [2] Tiêu đề: URL

Ví dụ inline: "Xu hướng A đang tăng mạnh trên TikTok [1] và được đưa tin rộng rãi [2]."
"""


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
