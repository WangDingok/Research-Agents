# Deep Research Agent — Hướng dẫn sử dụng

Chào mừng bạn đến với **Deep Research Agent** — hệ thống nghiên cứu thị trường tự động theo mô hình **multi-agent**.

Thay vì trả lời từ một nguồn duy nhất, agent sẽ tự động điều phối nhiều sub-agent chuyên biệt, thu thập dữ liệu từ nhiều nguồn song song, rồi tổng hợp thành một báo cáo có chiều sâu để bạn ra quyết định nhanh hơn.

---

## Bốn kỹ năng cốt lõi

Agent được trang bị 4 skill có thể kết hợp linh hoạt tùy theo yêu cầu:

### 🔍 Skill 1 — Khám phá Trend (`skill_discover_trends`)
**Dùng khi:** Bạn chưa có niche cụ thể và muốn tìm cơ hội mới.

Agent sẽ quét Google AI Search, Google Trends và web để tìm các chủ đề đang tăng trưởng, phân loại theo độ bền (event-based, seasonal, cultural, viral, community) và lọc bỏ các trend ngắn hạn dưới 7 ngày.

**Ví dụ yêu cầu:**
> Tìm cho tôi 5 niche áo thun đang có tín hiệu tăng trưởng tháng này, ưu tiên trend sống lâu hơn 2 tuần.

---

### ✅ Skill 2 — Xác minh & Đánh giá Trend (`skill_validate_trends`)
**Dùng khi:** Bạn đã có danh sách niche và muốn biết cái nào đáng đầu tư nhất.

Agent sẽ kiểm tra chéo tín hiệu trên **Google Trends** (độ ổn định, spike, related queries), **Etsy** (engagement score, số listing, mức giá, fav/view rate), **TikTok**, **Reddit** và **Twitter/X**. Kết quả là một bảng so sánh với điểm tổng hợp cho từng niche.

**Ví dụ yêu cầu:**
> Đánh giá 3 niche sau: hockey shirt, funny cat shirt, family reunion shirt. Cái nào ổn định hơn, ít cạnh tranh hơn trên Etsy?

---

### 🏆 Skill 3 — Lấy Top Sản phẩm (`skill_find_top_products`)
**Dùng khi:** Bạn muốn xem sản phẩm đang bán chạy để lấy cảm hứng thiết kế hoặc đánh giá mặt bằng giá.

Agent gọi Etsy API để lấy top listing theo keyword, trả về hình ảnh sản phẩm, tên shop, mức giá, số favorites, lượt xem và link mua trực tiếp — hiển thị dạng bảng ngay trong chat.

**Ví dụ yêu cầu:**
> Cho tôi xem top 5 áo thun bán chạy nhất với keyword "minimalist cat" trên Etsy trong 30 ngày qua.

---

### 📄 Skill 4 — Viết Báo cáo (`skill_write_report`)
**Dùng khi:** Bạn muốn có một báo cáo hoàn chỉnh để lưu trữ hoặc chia sẻ.

Agent tổng hợp toàn bộ dữ liệu thu thập được (Google Trends, Etsy, social signals) thành một báo cáo có cấu trúc rõ ràng: tóm tắt thực thi, phân tích theo nguồn, bảng so sánh niche, khuyến nghị hành động và danh sách nguồn tham khảo.

**Ví dụ yêu cầu:**
> Nghiên cứu toàn diện niche "comfort colors shirt" và viết báo cáo đầy đủ cho tôi.

---

## Nguồn dữ liệu

| Nguồn | Cung cấp thông tin gì |
|---|---|
| **Google AI Search** | Góc nhìn tổng quan, ý tưởng ngách, chủ đề liên quan |
| **Google Trends** | Độ ổn định, xu hướng tăng/giảm, spike gần đây, related queries |
| **Tavily Web Search** | Xác minh từ bài báo, blog, diễn đàn, website |
| **Etsy** | Listing, giá, engagement score, fav/view rate, top sản phẩm |
| **TikTok** | Viral score, view count, video trending theo niche |
| **Reddit** | Thảo luận cộng đồng, viral posts, subreddit liên quan |
| **Twitter/X** | Trending topics, thảo luận thời gian thực |

---

## Cách viết prompt hiệu quả

Prompt tốt gồm 3 thành phần:

```
[Đối tượng nghiên cứu] + [Phạm vi/Thời gian] + [Đầu ra mong muốn]
```

| Thành phần | Ví dụ |
|---|---|
| Đối tượng | niche, keyword, nhóm sản phẩm, chủ đề |
| Phạm vi | 7 ngày / 30 ngày, thị trường US, Etsy, social |
| Đầu ra | so sánh, xếp hạng, top sản phẩm, ý tưởng thiết kế, báo cáo |

---

## Ví dụ prompt theo từng mục đích

**Khám phá trend mới:**
> Tìm 5 niche áo thun có tín hiệu tăng trưởng trên thị trường US tháng 3/2026. Ưu tiên trend bền hơn 2 tuần, tránh chủ đề chính trị thoáng qua.

**So sánh niche:**
> So sánh 3 niche: hockey shirt, family reunion shirt, funny cat shirt. Cho tôi biết niche nào ổn định hơn, ít cạnh tranh hơn và có tiềm năng bán tốt hơn trên Etsy.

**Phân tích + Top sản phẩm:**
> Phân tích niche "minimalist cat tshirt" trên Etsy 30 ngày qua. Kiểm tra Google Trends, sau đó cho tôi xem top 5 sản phẩm bán chạy nhất và kết luận có nên làm sản phẩm hay không.

**Báo cáo toàn diện:**
> Nghiên cứu toàn diện niche "comfort colors shirt": khám phá, xác minh tín hiệu trên Google Trends + Etsy + Reddit + TikTok, lấy top sản phẩm và viết báo cáo đầy đủ.

**Tìm cảm hứng thiết kế:**
> Lấy top 10 sản phẩm bán chạy nhất trên Etsy cho các keyword: "funny cat shirt", "cottagecore shirt", "dark academia shirt". Tôi muốn xem hình ảnh và giá để lấy cảm hứng.

---

## Lưu ý quan trọng

- **Biểu đồ và thẻ sản phẩm Etsy** sẽ xuất hiện tự động trong chat khi có dữ liệu phù hợp.
- Agent ưu tiên các trend **sống lâu hơn 10 ngày**. Các niche chỉ hot do scandal hoặc tin tức 1 ngày sẽ bị lọc bỏ.
- Nếu yêu cầu quá mơ hồ, agent sẽ hỏi thêm để làm rõ trước khi bắt đầu nghiên cứu.
- Để có kết quả tốt nhất, hãy **chỉ định phạm vi thời gian** (7 ngày / 30 ngày) và **thị trường mục tiêu** (US, global…) trong prompt.

## Kết quả bạn sẽ thấy trong giao diện

Trong lúc chạy, giao diện có thể hiển thị:

- Các bước tool/sub-agent đang được gọi.
- Nội dung tóm tắt từ từng nguồn nghiên cứu.
- Biểu đồ xu hướng nếu công cụ tạo chart.
- Top listing Etsy với hình ảnh, giá, lượt yêu thích và link sản phẩm.
- Câu trả lời cuối cùng đã được tổng hợp.

## Mẹo để có kết quả tốt hơn

- Hãy nói rõ **thị trường** bạn quan tâm, ví dụ US hay global.
- Nếu cần quyết định kinh doanh, hãy yêu cầu agent **xếp hạng và giải thích vì sao**.
- Nếu đã có keyword, hãy đưa danh sách cụ thể để agent so sánh trực tiếp.
- Nếu bạn muốn đào sâu thiết kế, hãy yêu cầu thêm phần **ý tưởng hình ảnh, phong cách và thông điệp**.

## Lưu ý thực tế

- Một số nguồn dữ liệu cần API key hợp lệ ở phía hệ thống.
- Kết quả tốt nhất đến từ việc đối chiếu nhiều nguồn, không nên xem một chỉ số đơn lẻ là kết luận tuyệt đối.
- Agent phù hợp nhất cho **nghiên cứu, khám phá cơ hội, và đánh giá sơ bộ**, không thay thế hoàn toàn kiểm chứng kinh doanh ngoài thực tế.

Bạn có thể bắt đầu bằng một câu hỏi tự nhiên bằng tiếng Việt hoặc tiếng Anh. Nếu chưa biết hỏi gì, hãy thử:

> Gợi ý cho tôi 5 niche áo thun có tín hiệu tăng trưởng bền trong 30 ngày gần đây, rồi chọn ra 2 niche đáng làm nhất.
