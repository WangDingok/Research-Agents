import json
from datetime import datetime
from typing import List

import pandas as pd
from langchain_core.tools import tool

from research_agent.base.base import BaseToolkit
from research_agent.config import AppConfig, config as default_config
from research_agent.tools.etsy.analyzer import EtsyTrendAnalyzer


class EtsyToolkit(BaseToolkit):
    """Toolkit for Etsy market analysis tools."""

    def __init__(self, config: AppConfig = None):
        super().__init__(config or default_config)
        cfg = self.config.etsy if hasattr(self.config, 'etsy') else self.config
        self._api_key = cfg.api_key
        self._tools = None

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_analyzer(self) -> EtsyTrendAnalyzer:
        return EtsyTrendAnalyzer(api_key=self._api_key)

    def get_tools(self) -> list:
        if self._tools is not None:
            return self._tools
        if not self.is_available:
            self._tools = []
            return self._tools

        toolkit = self

        @tool
        def search_etsy_trends_by_keyword(keywords: List[str], days_back: int = 30) -> str:
            """
            Phân tích xu hướng thị trường áo thun trên Etsy.
            - Nếu keywords=[] (rỗng): Phân tích tổng quan thị trường chung — dashboard discovery gồm top tags, phân bố giá, mức cạnh tranh, phân khúc giá, tags thành công.
            - Nếu keywords=["kw1", "kw2"]: Phân tích từng niche — thống kê, biểu đồ so sánh (2+ keywords).
            Luôn tạo biểu đồ trực quan (chart_paths trong JSON output).

            Args:
                keywords: Danh sách từ khóa/niche. Truyền [] để phân tích thị trường chung.
                days_back: Số ngày quay lại để phân tích dữ liệu.

            Returns:
                Chuỗi JSON chứa kết quả phân tích + đường dẫn biểu đồ.
            """
            try:
                analyzer = toolkit._get_analyzer()
                results = analyzer.run_analysis(keywords=keywords, days_back=days_back)

                def default_converter(o):
                    if isinstance(o, (pd.Timestamp, datetime)):
                        return o.isoformat()
                    if hasattr(o, 'item'):
                        return o.item()
                    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

                return json.dumps(results, ensure_ascii=False, indent=2, default=default_converter)
            except Exception as e:
                return json.dumps({"error": f"Đã xảy ra lỗi trong quá trình phân tích Etsy: {str(e)}"})

        @tool
        def get_etsy_top_listings(keywords: List[str], top_n: int = 5, days_back: int = 30) -> str:
            """
            Lấy danh sách sản phẩm bán chạy nhất (top listings) trên Etsy cho mỗi keyword.
            Trả về hình ảnh, shop, link, giá, favorites, views — dùng để hiển thị trên Chat UI.
            KHÔNG phân tích thống kê hay tạo biểu đồ. Chỉ lấy sản phẩm top.

            Args:
                keywords: Danh sách các từ khóa/niche cần lấy top sản phẩm.
                top_n: Số sản phẩm top cho mỗi keyword (mặc định 5).
                days_back: Số ngày quay lại để tìm sản phẩm.

            Returns:
                Một chuỗi JSON chứa top listings cho mỗi keyword.
            """
            try:
                analyzer = toolkit._get_analyzer()
                result = {}
                for kw in keywords:
                    print(f"\n--- Lấy top {top_n} sản phẩm cho: '{kw}' ---")
                    listings = analyzer._fetch_listings(keywords=kw, days_back=days_back, max_items=100)
                    result[kw] = analyzer._get_top_listings(listings, kw, top_n=top_n)
                return json.dumps(result, ensure_ascii=False, indent=2)
            except Exception as e:
                return json.dumps({"error": f"Lỗi khi lấy top listings: {str(e)}"})

        self._tools = [search_etsy_trends_by_keyword, get_etsy_top_listings]
        return self._tools


# --- Backward-compatible module-level exports ---
_etsy_toolkit = EtsyToolkit()
etsy_tools = _etsy_toolkit.get_tools()


# ==================== VÍ DỤ SỬ DỤNG KHI CHẠY TRỰC TIẾP ====================
if __name__ == "__main__":
    toolkit = EtsyToolkit()
    tools = toolkit.get_tools()
    search_tool = tools[0]

    print("="*80)
    print("CHẾ ĐỘ 1: PHÂN TÍCH THỊ TRƯỜNG CHUNG")
    print("="*80)
    general_result_json = search_tool.func(keywords=[], days_back=30)
    print("\nKẾT QUẢ PHÂN TÍCH CHUNG (JSON):")
    print(general_result_json)

    print("\n\n" + "="*80)
    print("CHẾ ĐỘ 2: PHÂN TÍCH THEO TỪ KHÓA")
    print("="*80)
    test_keywords = ["hockey"]
    keyword_result_json = search_tool.func(keywords=test_keywords, days_back=30)
    print("\nKẾT QUẢ PHÂN TÍCH TỪ KHÓA (JSON):")
    print(keyword_result_json)