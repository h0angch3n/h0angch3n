# Sổ tay công ty AI — Công ty Cổ phần Dịch vụ Dev

Dành cho **người giao việc**. Bạn không cần biết lập trình.

Bạn giao việc bằng một câu. Một đội AI tự lập kế hoạch, làm, kiểm tra lẫn nhau. Bạn chỉ phê duyệt **hai lần**:
lúc bắt đầu (kế hoạch) và lúc kết thúc (kết quả).

---

## 1. Đội AI gồm những ai

| AI | Giống vai trò nào trong công ty | Làm gì |
|---|---|---|
| **AI Điều phối** | Tổng Giám đốc điều hành | Nói chuyện với bạn, lập kế hoạch, chia việc, gom kết quả, trình duyệt |
| **AI Phân tích** | Nhân viên phân tích nghiệp vụ | Viết rõ từng chức năng và "thế nào là đạt" |
| **AI Lập trình** | Lập trình viên | Viết phần mềm theo bản mô tả |
| **AI Kiểm thử** | Nhân viên kiểm tra chất lượng | Dùng thử như khách hàng, tìm lỗi |
| **AI Rà soát** | Trưởng nhóm kỹ thuật, chuyên viên bảo mật | Soát lỗi, lỗ hổng bảo mật trước khi trình bạn |

AI Kiểm thử và AI Rà soát **không được sửa** phần mềm, chỉ được báo lỗi. Cách chia này giống công ty thật: người làm
và người kiểm tra là hai người khác nhau, nên lỗi khó lọt qua.

## 2. Một việc đi qua những bước nào

```
Bạn giao việc
   │
   ▼
AI Điều phối lập kế hoạch ──► ⏸ BẠN DUYỆT KẾ HOẠCH (trả lời "duyệt")
   │
   ▼
AI Phân tích viết mô tả chi tiết
   │
   ▼
AI Lập trình làm ◄──────────┐
   │                        │ có lỗi thì trả về sửa
   ▼                        │ (tự động, tối đa 3 vòng)
AI Kiểm thử + AI Rà soát ───┘
   │ hết lỗi
   ▼
AI Điều phối trình kết quả ──► ⏸ BẠN DUYỆT KẾT QUẢ (bấm Merge trên GitHub)
```

Việc nhỏ (sửa chữ, sửa một lỗi rõ ràng) thì bỏ qua bước duyệt kế hoạch: AI làm luôn rồi trình kết quả.

## 3. Cách giao việc

1. Mở ứng dụng Claude (hoặc trang claude.ai/code), tạo phiên làm việc mới với kho mã **h0angch3n/h0angch3n**.
2. Gõ lệnh **`/giao-viec`** rồi viết việc cần làm. Ví dụ:

   > /giao-viec Làm trang web giới thiệu công ty, có trang dịch vụ, trang liên hệ, xem tốt trên điện thoại.

   > /giao-viec Khách hàng là phòng khám nha khoa, cần phần mềm đặt lịch hẹn cho bệnh nhân, hạn 1 tháng.

   > /giao-viec Thêm vào Projeck chức năng xuất báo cáo tháng ra file Excel.

**Viết yêu cầu thế nào cho tốt:** nói **ai dùng**, **để làm gì**, **hạn chót** (nếu có). Không cần nói cách làm
kỹ thuật. Thiếu gì, AI sẽ hỏi bạn một lần.

## 4. Bạn phê duyệt thế nào

**Duyệt kế hoạch:** AI gửi một khung "KẾ HOẠCH" gồm mục tiêu, sẽ làm gì, không làm gì, mất bao lâu.
- Đồng ý: trả lời **duyệt**.
- Muốn đổi: viết điều muốn đổi, ví dụ "bỏ trang tin tức, thêm trang tuyển dụng".

**Duyệt kết quả:** AI gửi báo cáo "ĐÃ XONG" kèm đường link GitHub.
1. Đọc phần **Kết quả** và **Chưa kiểm tra / còn hạn chế**.
2. Đồng ý: mở link, kéo xuống cuối trang, bấm nút xanh **Merge pull request**, rồi **Confirm merge**.
3. Chưa đồng ý: trả lời AI điều muốn sửa. AI sửa xong sẽ trình lại.

## 5. Những việc AI luôn hỏi bạn trước

Kể cả khi đang tự chạy, AI phải dừng lại hỏi trước khi:
- gửi email, tin nhắn ra ngoài, hay công bố bất cứ thứ gì;
- làm bất cứ việc gì liên quan đến **tiền**: mua dịch vụ, gói trả phí, báo giá cho khách;
- **xóa** dữ liệu, file, dự án;
- đưa phần mềm lên Internet hoặc lên máy của khách hàng;
- cấp quyền truy cập, chia sẻ tài liệu cho người khác;
- hứa hẹn với khách hàng về hạn, phạm vi, giá;
- làm khác với kế hoạch bạn đã duyệt.

Và **chỉ bạn mới bấm Merge**: không AI nào tự đưa kết quả vào bản chính thức.

## 6. Cần biết

- **AI có thể sai.** Vì vậy hai lần duyệt của bạn là cần thiết. Nhìn kỹ mục "Chưa kiểm tra / còn hạn chế" trong báo cáo.
- **AI chỉ làm khi phiên làm việc đang mở**, hoặc khi bạn đặt lịch cho nó. Nó không tự chạy ngầm mãi.
- **Mỗi việc dùng hạn mức của gói Claude.** Việc lớn chạy nhiều AI cùng lúc dùng nhiều hơn. Chia việc lớn thành giai đoạn để kiểm soát.
- **AI không làm được việc ngoài đời:** ký hợp đồng, chuyển tiền, gặp khách. Những việc đó vẫn là của bạn
  và nhân sự thật, ghi trên Projeck.
- Luật làm việc của đội AI nằm trong file `CLAUDE.md` ở gốc kho mã. Muốn đổi luật, ví dụ "việc dưới 1 ngày không cần
  duyệt kế hoạch", thì nói với AI: "Sửa sổ tay: …". Thay đổi đó cũng sẽ được trình bạn duyệt như mọi việc khác.
