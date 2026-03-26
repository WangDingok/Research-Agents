---
name: trend-discovery
description: 
  Sử dụng ở giai đoạn đầu của quy trình nghiên cứu để khám phá các chủ đề và niche có tiềm năng trở thành trend. Skill này sẽ điều phối nhiều sub-agent (Twitter, Google Trends, Tavily) để thu thập một danh sách 'ứng cử viên' trend từ nhiều nguồn khác nhau.
---

**Khám phá Trend Toàn diện**
1.  **Mục tiêu**: Tạo một danh sách các niche trend tiềm năng từ nhiều nguồn.
2.  **Hành động**: Khởi chạy đồng thời các agent sau:
    *   Giao cho `twitter-search-agent` để tìm các chủ đề đang được thảo luận sôi nổi trên mạng xã hội.
    *   Giao cho `google-trends-agent` để tìm các chủ đề có lượt tìm kiếm tăng đột biến.
    *   Giao cho `tavily-search-agent` để tìm các bài báo, tin tức gần đây về các xu hướng mới nổi.
3.  **Tổng hợp**: Sau khi tất cả các agent hoàn thành, tổng hợp một danh sách các khóa ứng viên từ kết quả của chúng.