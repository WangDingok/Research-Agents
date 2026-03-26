---
name: trend-validator
description: 
  Sử dụng để xác minh và đánh giá sâu các 'niche ứng viên' đã được phát hiện. Skill này sẽ điều phối các sub-agent để phân tích dữ liệu xu hướng (Google Trends) và tìm kiếm các cuộc thảo luận của cộng đồng, nhằm xác định xem một niche có thực sự bền vững và được công chúng quan tâm hay không.
---

**Sàng lọc và Đánh giá sâu (Chạy song song)**
1.  **Mục tiêu**: Với các niche ứng viên, xác minh độ bền vững và tìm hiểu thảo luận của cộng đồng.
2.  **Hành động**: Với các niche, khởi chạy đồng thời các agent sau:
    *   Giao cho `google-trends-agent` để phân tích biểu đồ xu hướng và sự ổn định (nhóm 5 niche chạy đồng thời).
    *   Giao cho `tavily-search-agent` với vai trò mở rộng: yêu cầu nó tìm kiếm các cuộc thảo luận trên các diễn đàn, blog và các trang cộng đồng để đánh giá tâm lý công chúng (chạy từng niche đơn lẻ).