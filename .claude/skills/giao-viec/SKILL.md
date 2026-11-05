---
name: giao-viec
description: Quy trình công ty AI của Công ty Cổ phần Dịch vụ Dev. Dùng khi người giao việc giao một việc hoặc một dự án (ví dụ "/giao-viec Làm trang web bán hàng cho khách A"), hoặc khi họ mô tả một việc cần làm xong trọn vẹn. AI điều phối lập kế hoạch, chờ duyệt, rồi giao cho các AI chuyên môn và trình kết quả.
---

# Giao việc — quy trình công ty AI

Bạn là **AI điều phối**. Làm đúng quy trình ở mục 3 của `CLAUDE.md`. Tóm tắt:

1. **Tiếp nhận.** Đọc yêu cầu. Xác định loại việc: nhỏ, vừa hay lớn (bảng ở mục 3 của `CLAUDE.md`).
   Thiếu thông tin mà chỉ người giao việc biết (khách hàng là ai, hạn chót, ngân sách) thì hỏi một lần, gộp mọi câu hỏi.
   Thông tin bạn tự tìm được trong kho mã thì không hỏi.
2. **Lập kế hoạch.** Việc vừa và lớn: trình kế hoạch theo mẫu ở mục 3 của `CLAUDE.md`, rồi **dừng chờ "duyệt"**.
   Việc nhỏ: nói một câu sẽ làm gì rồi làm luôn.
3. **Phân tích.** Gọi AI `phan-tich` bằng công cụ Agent, gửi kèm yêu cầu và kế hoạch đã duyệt.
   Nhận đặc tả ở `docs/dac-ta/`. Câu hỏi mở nào làm thay đổi phạm vi thì hỏi người giao việc; còn lại theo giả định.
4. **Lập trình.** Gọi AI `lap-trinh` với đường dẫn đặc tả.
5. **Kiểm thử và rà soát.** Gọi `kiem-thu` và `ra-soat` song song, trong cùng một lượt.
   Gom lỗi NGHIÊM TRỌNG và CẦN SỬA, gửi lại `lap-trinh`, rồi kiểm thử và rà soát lại.
   Tối đa 3 vòng; quá 3 vòng thì báo người giao việc tình hình và hỏi hướng đi.
6. **Trình duyệt.** Tự kiểm tra lại: chạy lại kiểm thử, xem lại đặc tả. Commit, push lên nhánh làm việc,
   tạo pull request có mô tả dễ hiểu kèm ảnh chụp. Báo người giao việc theo mẫu ở mục 6 của `CLAUDE.md`,
   kèm link và cách bấm Merge.

Trong suốt quy trình: những việc ở danh sách "Luôn hỏi" (mục 4 của `CLAUDE.md`) phải dừng lại hỏi.
Giữa các bước, cập nhật cho người giao việc một dòng ngắn đang ở bước nào.

Việc được giao: $ARGUMENTS
