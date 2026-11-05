# Quy trình giao việc — Công ty Cổ phần Dịch vụ Dev

## 1. Cơ cấu tổ chức (mô hình công ty cổ phần)

```
                     Đại hội đồng cổ đông
                              │
             ┌────────────────┴────────────────┐
     Hội đồng quản trị                    Ban Kiểm soát
             │                       (giám sát HĐQT và điều hành)
     Ban Tổng Giám đốc
             │
  ┌──────────┬────────────┬───────────────┬───────────────────┐
Khối Dự án  Khối Kỹ thuật  Khối Khách hàng  Khối Vận hành
─ PMO       ─ Backend      ─ Kinh doanh &   ─ Pháp chế – Hợp đồng
─ BA        ─ Frontend       Marketing      ─ Nhân sự (HR)
            ─ Mobile       ─ Hỗ trợ         ─ Kế toán – Tài chính
            ─ UI/UX          khách hàng     ─ Hành chính – Văn phòng
            ─ QA/QC
            ─ DevOps
            ─ Bảo mật
```

Đại hội đồng cổ đông không nhận việc hằng ngày nên không phải là một bộ phận trong phần mềm; nó chỉ xuất hiện
trên sơ đồ. Hội đồng quản trị và Ban Kiểm soát là bộ phận để giao các việc như chuẩn bị họp HĐQT, kiểm tra báo cáo tài chính.

| Bộ phận | Chức năng | Thường nhận việc |
|---|---|---|
| Hội đồng quản trị | Chiến lược, kế hoạch kinh doanh, bổ nhiệm TGĐ | Phê duyệt kế hoạch năm, nghị quyết HĐQT |
| Ban Kiểm soát | Giám sát tính hợp pháp và báo cáo tài chính | Kiểm tra báo cáo quý, rà soát hợp đồng lớn |
| Ban Tổng Giám đốc | Điều hành hằng ngày | Duyệt dự án, ngân sách, tuyển dụng chủ chốt |
| Quản lý dự án (PMO) | Kế hoạch, tiến độ, rủi ro | Lập kế hoạch sprint, chia việc, báo cáo tiến độ |
| Phân tích nghiệp vụ (BA) | Yêu cầu, đặc tả | User story, tiêu chí nghiệm thu |
| Backend / Frontend / Mobile | Lập trình | Tính năng, sửa lỗi, tối ưu |
| Thiết kế UI/UX | Trải nghiệm, giao diện | Wireframe, prototype, hệ thống thiết kế |
| Kiểm thử (QA/QC) | Chất lượng | Test case, test hồi quy, test tự động |
| DevOps & Hạ tầng | Triển khai, vận hành | CI/CD, máy chủ, giám sát, sao lưu |
| Bảo mật thông tin | An toàn hệ thống | Rà soát bảo mật, phân quyền, xử lý lỗ hổng |
| Hỗ trợ khách hàng | Sau bán hàng, bảo hành dịch vụ | Tiếp nhận sự cố, hướng dẫn khách |
| Kinh doanh & Marketing | Doanh thu | Báo giá, hợp đồng dịch vụ, truyền thông |
| Pháp chế – Hợp đồng | Tuân thủ | Soạn và rà soát hợp đồng, sở hữu trí tuệ |
| Nhân sự (HR) | Con người | Tuyển dụng, đào tạo, đánh giá |
| Kế toán – Tài chính | Tiền | Lương, công nợ, thuế, báo cáo, sổ cổ đông |
| Hành chính – Văn phòng | Hậu cần | Thiết bị, văn phòng phẩm, văn thư |

## 2. Gán vai trò trong phần mềm

| Ai trong công ty | Vai trò Projeck |
|---|---|
| Tổng Giám đốc, Chủ tịch HĐQT, người phụ trách IT | **Quản trị / Tổng Giám đốc** |
| Phó TGĐ, trưởng PMO, quản lý dự án | **Quản lý dự án** |
| Trưởng phòng, trưởng nhóm, Trưởng Ban Kiểm soát | **Trưởng bộ phận** (và bổ nhiệm trong tab *Cơ cấu tổ chức*) |
| Tất cả nhân viên còn lại | **Nhân viên** |

Nên giữ ít người có quyền Quản trị (2–3 người).

## 3. Ai giao việc cho ai

```
Quản trị / Quản lý dự án ──giao──► bất kỳ ai, mọi bộ phận
Trưởng bộ phận ───────────giao──► nhân sự trong bộ phận của mình
Nhân viên ────────────────ghi nhận► việc của chính mình (việc phát sinh)
```

Cần người bộ phận khác hỗ trợ? Trưởng bộ phận **viết bình luận** hoặc nhờ quản lý dự án giao, không giao chéo.
Như vậy mỗi trưởng bộ phận luôn nắm được toàn bộ việc của người mình quản lý.

## 4. Vòng đời một công việc

```
 Chờ làm ──► Đang làm ──► Chờ duyệt ──► Hoàn thành
                 ▲             │
                 └── trả lại ──┘   (người duyệt chuyển về Đang làm + ghi lý do trong bình luận)
```

| Bước | Ai làm | Thao tác trong Projeck | Ai được thông báo |
|---|---|---|---|
| Giao việc | Quản lý / trưởng bộ phận | Tab *Công việc* → **Giao việc mới** | Người được giao |
| Bắt đầu | Người thực hiện | Đổi trạng thái → **Đang làm** | |
| Vướng mắc | Người thực hiện | Mở việc → viết bình luận | Người giao việc |
| Làm xong | Người thực hiện | Đổi trạng thái → **Chờ duyệt** | Người giao việc (tự ghi nhận thì trưởng bộ phận) |
| Duyệt | Người giao việc | Kiểm tra → **Hoàn thành** | Người thực hiện |
| Trả lại | Người giao việc | Đổi về **Đang làm** + bình luận lý do | Người thực hiện |

Nhân viên **không tự đánh dấu Hoàn thành** việc người khác giao, để mọi kết quả đều được kiểm tra.

## 5. Cách viết một công việc tốt

- **Tiêu đề bắt đầu bằng động từ**: "Xây dựng API đăng nhập", không phải "API đăng nhập".
- **Vừa sức 2–16 giờ**. Việc lớn hơn thì chia nhỏ.
- **Luôn có hạn** và **mức ưu tiên**:
  - **Khẩn**: làm ngay, đang ảnh hưởng khách hàng.
  - **Cao**: xong trong tuần.
  - **Thường**: theo kế hoạch sprint.
  - **Thấp**: khi có thời gian.
- **Mô tả ghi rõ tiêu chí hoàn thành**: thế nào là xong, ai kiểm tra, link tài liệu liên quan.
- **Không giao quá sức chứa**: tab *Tổng quan* tô đỏ người có số việc mở vượt sức chứa.

## 6. Quy trình một dự án dịch vụ phần mềm

| # | Giai đoạn | Bộ phận chủ trì | Việc điển hình trong Projeck |
|---|---|---|---|
| 1 | Tiếp nhận khách hàng | Kinh doanh & Marketing | Khảo sát nhu cầu, lập báo giá |
| 2 | Ký hợp đồng | Pháp chế – Hợp đồng, Ban TGĐ | Soạn hợp đồng, rà soát điều khoản, trình ký |
| 3 | Khởi tạo dự án | PMO | Tạo dự án ở tab *Dự án*, chọn quản lý dự án, hạn bàn giao |
| 4 | Phân tích & thiết kế | BA, UI/UX | Đặc tả, user story, wireframe, prototype |
| 5 | Phát triển | Backend, Frontend, Mobile | Chia việc theo sprint 1–2 tuần |
| 6 | Kiểm thử | QA/QC, Bảo mật | Test hồi quy, rà soát bảo mật |
| 7 | Triển khai | DevOps | Môi trường staging, production, giám sát |
| 8 | Nghiệm thu & thanh toán | PMO, Kế toán | Biên bản nghiệm thu, xuất hóa đơn, theo dõi công nợ |
| 9 | Bảo hành, hỗ trợ | Hỗ trợ khách hàng | Mỗi lỗi khách báo thành một công việc mới |

Việc nội bộ (tuyển dụng, lương, mua sắm, họp HĐQT) gom vào một dự án riêng, ví dụ **"Vận hành nội bộ 2026"**.

## 7. Nhịp làm việc hằng ngày, hằng tuần

**Mỗi nhân viên, đầu ngày (5 phút):** mở tab **Việc của tôi**, làm việc quá hạn và Khẩn trước, cập nhật trạng thái.

**Trưởng bộ phận, hằng ngày:** xử lý mục **Chờ tôi duyệt** trong ngày; giao việc mới cho người còn trống.

**Quản lý dự án, họp đầu tuần (30 phút):**
1. Tab *Tổng quan*: xem việc quá hạn, việc chưa giao, người quá tải (thanh đỏ).
2. Tab *Dự án*: xem % tiến độ từng dự án so với hạn bàn giao.
3. Chia lại việc, điều chỉnh hạn, ghi quyết định vào bình luận của công việc liên quan.

**Ban Tổng Giám đốc, hằng tháng:** xem tiến độ dự án, khối lượng từng bộ phận, quyết định tuyển thêm người
hoặc nhận thêm dự án. Quản trị bấm **Xuất dữ liệu** để lưu trữ báo cáo tháng.

## 8. Lộ trình đưa vào sử dụng (2 tuần)

Ngay sau khi tạo tài khoản quản trị, Projeck tạo sẵn dự án **"Triển khai Projeck tại công ty"** với các việc sau,
giao cho quản trị. Làm lần lượt và đánh dấu trên chính hệ thống:

| Ngày | Việc |
|---|---|
| 0 | Cài đặt và chạy máy chủ (đã xong khi thấy màn hình đăng nhập) |
| 1 | Rà soát danh sách bộ phận cho đúng công ty |
| 2 | Tạo tài khoản trưởng bộ phận và quản lý dự án; bổ nhiệm trưởng bộ phận |
| 4 | Tạo tài khoản toàn bộ nhân viên |
| 5 | Tạo dự án thật đầu tiên, giao 5–10 việc thử |
| 6 | Họp 15 phút hướng dẫn nhân viên dùng tab *Việc của tôi* |
| 7 | Kiểm tra sao lưu tự động trong thư mục `backups` |
| 14 | Tổng kết 2 tuần, điều chỉnh quy trình |
