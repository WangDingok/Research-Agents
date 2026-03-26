---
name: design-inspirator
description: 
  Sử dụng sau khi đã xác định được một niche/trend cụ thể. Skill này sẽ tìm kiếm và thu thập các nguồn cảm hứng thiết kế, ý tưởng sản phẩm, bảng màu, và các ví dụ thực tế từ web và các trang thương mại điện tử để hỗ trợ quá trình sáng tạo.
---

**Khai thác và Tìm cảm hứng (Chạy song song)**
1.  **Mục tiêu**: Thu thập thông tin để phục vụ thiết kế sản phẩm theo trend.
2.  **Hành động**: Với mỗi trend, khởi chạy đồng thời các agent sau:
    *   Giao cho `tavily-search-agent` với vai trò mở rộng: yêu cầu nó tìm kiếm các ý tưởng thiết kế, mẫu áo thun phổ biến, bảng màu, và các sản phẩm liên quan.
    *   Giao cho `google-ai-search-agent` để tìm các ví dụ về sản phẩm trên các nền tảng thương mại điện tử khác nhau.
