# Deep Research Agent cho nghiên cứu trend

Chào mừng bạn đến với **Deep Research Agent**.

Đây là agent nghiên cứu thị trường theo mô hình **đa tác tử**. Thay vì chỉ trả lời một lần, hệ thống sẽ tự chia công việc cho nhiều sub-agent chuyên trách, rồi tổng hợp lại thành một báo cáo dễ đọc.

## Agent này làm được gì?

Agent phù hợp khi bạn cần:

- tìm **trend mới** hoặc niche có tín hiệu tăng trưởng;
- kiểm tra một trend có **bền** hay chỉ tăng đột biến ngắn hạn;
- phân tích thị trường **Etsy** theo từ khóa, mức giá, độ cạnh tranh và sản phẩm nổi bật;
- tham khảo thêm tín hiệu từ **Google Search/Google Trends**, **Twitter/X**, và **web search**;
- tổng hợp kết quả thành một **báo cáo nghiên cứu** để ra quyết định nhanh hơn.

## Các nguồn dữ liệu chính

- **Google AI Search**: lấy góc nhìn tổng quan, ý tưởng ngách và chủ đề liên quan.
- **Google Trends**: xem độ ổn định, xu hướng tăng/giảm, spike gần đây và truy vấn liên quan.
- **Tavily Web Search**: xác minh thông tin từ bài báo, blog, diễn đàn và website.
- **Etsy**: phân tích listing, giá, mức độ yêu thích, lượt xem và top sản phẩm.
- **Twitter/X trends**: tham khảo các chủ đề đang được bàn luận.

## Quy trình nghiên cứu mặc định

Khi bạn gửi một yêu cầu, agent thường đi theo luồng này:

1. Hiểu mục tiêu nghiên cứu của bạn.
2. Gọi các sub-agent phù hợp để khám phá hoặc xác minh dữ liệu.
3. So sánh tín hiệu giữa nhiều nguồn thay vì dựa vào một nơi duy nhất.
4. Trả về kết luận kèm diễn giải rõ ràng.
5. Nếu có dữ liệu phù hợp, giao diện sẽ hiển thị thêm **biểu đồ** và **thẻ sản phẩm Etsy**.

## Bạn nên hỏi như thế nào?

Prompt tốt thường có 3 phần:

- **đối tượng nghiên cứu**: niche, keyword, nhóm sản phẩm, chủ đề;
- **phạm vi**: 7 ngày, 30 ngày, thị trường US, Etsy, social;
- **đầu ra mong muốn**: so sánh, xếp hạng, top sản phẩm, ý tưởng thiết kế, báo cáo cuối cùng.

Ví dụ:

> Phân tích xu hướng áo thun minimalist cat trên Etsy trong 30 ngày qua, kiểm tra thêm Google Trends và cho tôi kết luận có nên làm sản phẩm hay không.

> So sánh 3 niche: hockey shirt, family reunion shirt, funny cat shirt. Tôi muốn biết niche nào ổn định hơn, ít cạnh tranh hơn và có tiềm năng bán tốt hơn trên Etsy.

> Tìm các trend áo thun có khả năng sống lâu hơn 2 tuần, tránh các chủ đề chỉ hot do scandal hoặc tin tức thoáng qua.

## Kết quả bạn sẽ thấy trong giao diện

Trong lúc chạy, giao diện có thể hiển thị:

- các bước tool/sub-agent đang được gọi;
- nội dung tóm tắt từ từng nguồn nghiên cứu;
- biểu đồ xu hướng nếu công cụ tạo chart;
- top listing Etsy với hình ảnh, giá, lượt yêu thích và link sản phẩm;
- câu trả lời cuối cùng đã được tổng hợp.

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
