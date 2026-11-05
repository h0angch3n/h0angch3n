# Projeck — Hệ thống quản lý dự án & giao việc cho công ty lập trình

Ứng dụng web chạy ngay trên trình duyệt, **không cần cài đặt, không cần máy chủ**. Có sẵn đủ 15 bộ phận
của một công ty phần mềm, nhân sự mẫu, dự án mẫu. Mở lên là giao việc được ngay.

## Chạy ngay

**Cách 1:** nhấp đúp vào `index.html` (mở bằng Chrome, Edge hoặc Firefox).

**Cách 2:** chạy máy chủ web nhỏ để cả văn phòng cùng mở trong mạng LAN:

```bash
cd company-projeck
python3 -m http.server 8080
```

Sau đó mở `http://localhost:8080` (hoặc `http://<IP-máy-bạn>:8080` từ máy khác).

> Dữ liệu lưu trong trình duyệt (localStorage) **của từng máy**. Muốn sao lưu hoặc chuyển sang máy khác,
> bấm **Xuất JSON**, rồi **Nhập JSON** ở máy kia. Lưu file JSON vào Google Drive để có bản sao lưu.

## Chức năng

| Màn hình | Làm được gì |
|---|---|
| **Tổng quan** | Số việc theo trạng thái, việc quá hạn, việc chưa giao, % hoàn thành, **tải công việc từng người** so với sức chứa (đỏ khi quá tải) |
| **Công việc** | **Giao việc mới** (dự án, người thực hiện, ưu tiên, hạn, ước lượng giờ, mô tả). Bảng Kanban 4 cột *Chờ làm → Đang làm → Chờ duyệt → Hoàn thành*. Kéo thả thẻ, đổi người làm ngay trên thẻ. Lọc theo dự án, bộ phận, nhân sự, từ khóa |
| **Dự án** | Tạo dự án (mã tự sinh `PRJ-xxx`), bộ phận chủ trì, quản lý dự án, thời gian, tiến độ %, trạng thái |
| **Nhân sự** | Thêm người, xếp vào bộ phận, kỹ năng, sức chứa (số việc mở tối đa) |
| **Bộ phận** | Danh sách bộ phận, chức năng, trưởng bộ phận, số người, việc đang mở; thêm/xóa bộ phận |

## Sơ đồ tổ chức

```
                         Ban Giám đốc (CEO, CTO)
                                   │
     ┌──────────────┬──────────────┼───────────────┬──────────────────┐
  Khối Dự án      Khối Kỹ thuật           Khối Khách hàng      Khối Vận hành
  ─ PMO           ─ Backend                ─ Kinh doanh &       ─ Nhân sự (HR)
  ─ Phân tích       ─ Frontend               Marketing          ─ Kế toán – Tài chính
    nghiệp vụ (BA)  ─ Mobile                ─ Hỗ trợ khách hàng ─ Hành chính – Văn phòng
                  ─ Thiết kế UI/UX
                  ─ Kiểm thử (QA/QC)
                  ─ DevOps & Hạ tầng
                  ─ Bảo mật thông tin
```

| Bộ phận | Chức năng chính | Thường nhận việc gì |
|---|---|---|
| Ban Giám đốc | Chiến lược, ngân sách, phê duyệt | Duyệt dự án, duyệt tuyển dụng, ký hợp đồng |
| Quản lý dự án (PMO) | Lập kế hoạch, chia việc, theo dõi tiến độ | Kế hoạch sprint, báo cáo tiến độ, quản lý rủi ro |
| Phân tích nghiệp vụ (BA) | Yêu cầu và đặc tả | Đặc tả tính năng, user story, tiêu chí nghiệm thu |
| Backend | API, CSDL, tích hợp | Xây API, thiết kế CSDL, sửa lỗi máy chủ |
| Frontend | Giao diện web | Dựng màn hình, tối ưu hiệu năng web |
| Mobile | App iOS/Android | Tính năng app, phát hành lên store |
| Thiết kế UI/UX | Trải nghiệm & giao diện | Wireframe, prototype, hệ thống thiết kế |
| Kiểm thử (QA/QC) | Chất lượng | Test case, test hồi quy, test tự động, báo lỗi |
| DevOps & Hạ tầng | Triển khai, vận hành | CI/CD, máy chủ, giám sát, sao lưu |
| Bảo mật thông tin | An toàn hệ thống | Rà soát bảo mật, phân quyền, xử lý lỗ hổng |
| Hỗ trợ khách hàng | Sau bán hàng | Tiếp nhận sự cố, hướng dẫn sử dụng |
| Kinh doanh & Marketing | Doanh thu | Báo giá, hợp đồng, chiến dịch truyền thông |
| Nhân sự (HR) | Con người | Tuyển dụng, đào tạo, đánh giá |
| Kế toán – Tài chính | Tiền | Lương, công nợ, hóa đơn, báo cáo |
| Hành chính – Văn phòng | Hậu cần | Thiết bị, văn phòng phẩm, văn thư |

Nhân sự trong dữ liệu mẫu là **tên giả định**. Hãy xóa và thêm nhân sự thật ở tab **Nhân sự**.

## Quy trình giao việc đề xuất

1. **Kinh doanh** ký hợp đồng → **Ban Giám đốc** duyệt → **PMO** tạo dự án ở tab *Dự án*.
2. **BA** viết đặc tả; **PMO** chia thành công việc nhỏ (mỗi việc 2–16 giờ), giao cho từng người ở tab *Công việc*.
3. Người thực hiện chuyển thẻ **Chờ làm → Đang làm** khi bắt đầu, **→ Chờ duyệt** khi xong.
4. Trưởng nhóm / **QA** kiểm tra rồi chuyển **→ Hoàn thành**, hoặc trả về *Đang làm* kèm ghi chú.
5. **DevOps** triển khai bản đã duyệt; **Hỗ trợ khách hàng** tiếp nhận phản hồi, lỗi mới thành công việc mới.
6. Hằng tuần PMO xem tab *Tổng quan*: xử lý việc quá hạn, chia lại việc cho người đang quá tải.

Quy ước mức ưu tiên: **Khẩn** (làm ngay, ảnh hưởng khách hàng) · **Cao** (trong tuần) · **Thường** (theo sprint) · **Thấp** (khi rảnh).

## Cấu trúc mã nguồn

```
company-projeck/
├── index.html   khung trang và thanh điều hướng
├── style.css    giao diện (tự đổi sáng/tối theo hệ điều hành)
├── app.js       dữ liệu mẫu, lưu trữ, 5 màn hình, giao việc, kéo thả
└── README.md    tài liệu này
```

Mã dùng JavaScript thuần, không thư viện ngoài, nên chạy được cả khi không có Internet.

## Hướng phát triển tiếp

- Máy chủ + cơ sở dữ liệu dùng chung (Node.js/Python + PostgreSQL) để nhiều người cùng xem một bộ dữ liệu theo thời gian thực.
- Đăng nhập và phân quyền theo vai trò (Giám đốc, PM, Trưởng bộ phận, Nhân viên).
- Bình luận, đính kèm file, lịch sử thay đổi trên từng công việc.
- Thông báo email/Zalo khi được giao việc hoặc sắp đến hạn.
