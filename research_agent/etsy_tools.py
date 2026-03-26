import json
from datetime import datetime
from typing import List

import pandas as pd
from langchain_core.tools import tool

from research_agent.etsy_analyzer import EtsyTrendAnalyzer, API_KEY


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
    if not API_KEY:
        return json.dumps({"error": "ETSY_API_KEY không được thiết lập."})
    
    try:
        analyzer = EtsyTrendAnalyzer(api_key=API_KEY)
        results = analyzer.run_analysis(keywords=keywords, days_back=days_back)
        
        # Chuyển đổi các đối tượng không thể tuần tự hóa
        def default_converter(o):
            if isinstance(o, (pd.Timestamp, datetime)):
                return o.isoformat()
            if hasattr(o, 'item'): # for numpy int64 etc.
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
    if not API_KEY:
        return json.dumps({"error": "ETSY_API_KEY không được thiết lập."})

    try:
        analyzer = EtsyTrendAnalyzer(api_key=API_KEY)
        result = {}
        for kw in keywords:
            print(f"\n--- Lấy top {top_n} sản phẩm cho: '{kw}' ---")
            listings = analyzer._fetch_listings(keywords=kw, days_back=days_back, max_items=100)
            result[kw] = analyzer._get_top_listings(listings, kw, top_n=top_n)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Lỗi khi lấy top listings: {str(e)}"})


# Export tools
etsy_tools = [search_etsy_trends_by_keyword, get_etsy_top_listings]

# ==================== VÍ DỤ SỬ DỤNG KHI CHẠY TRỰC TIẾP ====================
if __name__ == "__main__":
    # Để debug, chúng ta sẽ gọi trực tiếp hàm bên trong tool.
    # Khi một hàm được trang trí bằng @tool, nó sẽ trở thành một đối tượng StructuredTool.
    # Hàm gốc có thể được truy cập thông qua thuộc tính .func.

    # 1. Chế độ phân tích chung
    print("="*80)
    print("CHẾ ĐỘ 1: PHÂN TÍCH THỊ TRƯỜNG CHUNG")
    print("="*80)
    # Gọi hàm gốc bằng .func
    general_result_json = search_etsy_trends_by_keyword.func(keywords=[], days_back=30)
    print("\nKẾT QUẢ PHÂN TÍCH CHUNG (JSON):")
    print(general_result_json)

    # 2. Chế độ phân tích theo từ khóa
    print("\n\n" + "="*80)
    print("CHẾ ĐỘ 2: PHÂN TÍCH THEO TỪ KHÓA")
    print("="*80)
    test_keywords = ["hockey"]
    # Gọi hàm gốc bằng .func
    keyword_result_json = search_etsy_trends_by_keyword.func(keywords=test_keywords, days_back=30)
    print("\nKẾT QUẢ PHÂN TÍCH TỪ KHÓA (JSON):")
    print(keyword_result_json)