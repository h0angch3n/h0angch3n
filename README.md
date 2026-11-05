# Công ty Cổ phần Dịch vụ Dev — kho mã nguồn

Kho này chứa hai sản phẩm độc lập:

| Thư mục | Sản phẩm | Dùng cho |
|---|---|---|
| [`company-projeck/`](company-projeck/README.md) | **Projeck** — quản lý dự án & giao việc nội bộ | Vận hành Công ty Cổ phần Dịch vụ Dev: cơ cấu công ty cổ phần, phân quyền, giao việc, duyệt kết quả |
| `offset_mes/` (tài liệu bên dưới) | **Offset MES** — ERP sản xuất cho xưởng in offset | Sản phẩm phần mềm làm cho khách hàng ngành in |

Hai sản phẩm không dùng chung mã hay dữ liệu, đều chỉ cần Python 3 và SQLite.
Hướng dẫn triển khai Projeck: [company-projeck/docs/HUONG_DAN_TRIEN_KHAI.md](company-projeck/docs/HUONG_DAN_TRIEN_KHAI.md) ·
Quy trình giao việc: [company-projeck/docs/QUY_TRINH_GIAO_VIEC.md](company-projeck/docs/QUY_TRINH_GIAO_VIEC.md).

---

# Offset MES — ERP sản xuất thu nhỏ toàn trình cho xưởng in offset

Phần mềm chạy trên PC cho xưởng in offset vừa và nhỏ: đi từ **báo giá → đơn hàng → tiến trình sản xuất
theo danh sách bước → giao hàng → hóa đơn → thu tiền**, với kho giấy, lịch máy và phân quyền người dùng.

- **Tài khoản quản trị tự đặt:** lần chạy đầu tiên, tự tạo tài khoản quản trị với tên và mật khẩu của bạn.
- **Phân quyền theo vai trò:** Quản trị, Quản lý sản xuất, Kinh doanh, Vận hành, Kế toán.
- **Tiến trình theo danh sách bước:** mỗi đơn có checklist sinh từ mẫu; không chuyển công đoạn khi còn bước chưa xong.
- **Nhật ký đầy đủ:** ai làm bước nào, lúc nào, chuyển trạng thái nào.
- **Hướng dẫn sử dụng tiếng Việt:** [docs/HUONG_DAN_SU_DUNG.md](docs/HUONG_DAN_SU_DUNG.md).

Chỉ dùng **thư viện chuẩn Python 3.10+** và **SQLite**, không cần cài thêm gói.

## Chạy nhanh

```bash
python3 -m offset_mes desktop                 # mở như ứng dụng PC, tự mở trình duyệt
python3 -m offset_mes --port 8000             # máy chủ web (mạng nội bộ)
python3 -m offset_mes create-admin --user giamdoc.lan   # tạo / đặt lại tài khoản quản trị
```

Đóng gói file `.exe` cho Windows: chạy `scripts\build_windows.bat` (kết quả `dist\OffsetMES.exe`).
Lưu ý: script này chưa được chạy thử trên Windows trong môi trường phát triển; nên kiểm tra trên một máy thật trước khi triển khai.

Kiểm thử:

```bash
python3 -m unittest discover -s tests -t . -v
```

> **Nâng cấp từ phiên bản 0.1:** cấu trúc CSDL đã thay đổi (thêm người dùng, bước tiến trình, cột người thực hiện).
> Hãy xóa file `offset_mes.db` cũ hoặc dùng đường dẫn `--db` mới trước khi chạy.

## Luồng nghiệp vụ

```
Khách ──► Báo giá ──khách chốt──► NEW ─► PREPRESS ─► PLATE ─► PRINTING ─► FINISHING ─► QC ─► READY ─► DELIVERED ─► CLOSED
                                    │ tạo bảng tiến trình          │ xếp máy    │ xuất giấy     ▲ lỗi: làm lại │ hóa đơn  │ thu đủ tiền
                                    └──────────────────────────────┘                               └──────────┘
```

Cổng tiến trình: muốn rời một công đoạn, mọi bước của công đoạn đó phải được đánh dấu xong.
Riêng QC → FINISHING (làm lại) không bị cổng chặn.

## Kiến trúc

| Module | Nội dung |
|---|---|
| `offset_mes/calc.py` | Thuần tính toán: xếp bản (thử cả hai chiều xoay), số tờ, kg giấy, giờ máy, giá vốn → lợi nhuận → VAT |
| `offset_mes/workflow.py` | Máy trạng thái vòng đời đơn |
| `offset_mes/auth.py` | Băm mật khẩu PBKDF2-SHA256, phiên đăng nhập, ma trận quyền theo vai trò |
| `offset_mes/service.py` | Nghiệp vụ + SQLite: người dùng, khách, kho giấy, máy, báo giá, đơn, tiến trình, lịch máy, hóa đơn |
| `offset_mes/server.py` | REST API JSON; mỗi route khai báo quyền cần có; `dispatch()` thuần để kiểm thử |
| `offset_mes/launcher.py` | Chạy như ứng dụng PC: máy chủ cục bộ + mở trình duyệt; dữ liệu ở `%APPDATA%\OffsetMES` |
| `offset_mes/static/index.html` | Giao diện một trang (tiếng Việt), không framework |
| `run_desktop.py` | Điểm vào cho ứng dụng PC và file `.exe` |

## Bảo mật

- Mật khẩu băm PBKDF2-SHA256 (200.000 vòng), không lưu dạng gốc.
- Phiên đăng nhập hết hạn sau 12 giờ; khóa tài khoản hoặc đổi mật khẩu sẽ đăng xuất phiên hiện có.
- Luôn còn ít nhất một quản trị viên đang hoạt động.
- Mặc định chỉ lắng nghe `127.0.0.1`. Chưa có HTTPS: không đưa ra internet khi chưa có tường lửa và TLS.
- Phiên lưu trong bộ nhớ: khởi động lại ứng dụng thì phải đăng nhập lại.

## API chính

Tất cả route (trừ `/api/setup-status`, `/api/setup`, `/api/login`) cần header `Authorization: Bearer <token>`.

| Method | Đường dẫn | Quyền |
|---|---|---|
| POST | `/api/setup`, `/api/login`, `/api/logout`, `/api/me/password` | công khai / đăng nhập |
| GET/POST | `/api/users`, `POST /api/users/{id}` | ADMIN |
| GET/PUT | `/api/process-template` | đọc: mọi người · sửa: ADMIN |
| GET/POST | `/api/customers`, `/api/papers`, `/api/machines`, `POST /api/papers/{id}/restock` | đọc: mọi người · ghi: theo vai trò |
| POST | `/api/quotes/estimate`, `/api/quotes`, `/api/quotes/{id}/accept` | SALES, MANAGER, ADMIN |
| GET | `/api/jobs`, `/api/jobs/{id}` (có `steps`, `progress`, `events`) | mọi người |
| POST | `/api/jobs/{id}/transition`, `/schedule`, `/steps` | OPERATOR trở lên |
| GET/POST | `/api/jobs/{id}/production` | đọc: mọi người · ghi: OPERATOR trở lên |
| POST | `/api/jobs/{id}/steps/{step_id}` `{"done": true}` | OPERATOR trở lên |
| POST | `/api/invoices/{id}/pay` | ACCOUNTANT, MANAGER, ADMIN |
| GET | `/api/dashboard`, `/api/invoices`, `/api/quotes` | mọi người |

Mã lỗi: 401 chưa đăng nhập · 403 không đủ quyền · 404 không tìm thấy · 409 vi phạm quy tắc nghiệp vụ · 400 dữ liệu sai.

## Lộ trình đề xuất

1. **Prepress:** nhận file PDF, kiểm tra độ phân giải/màu/tràn mép, duyệt proof trực tuyến cho khách.
2. **Kho mực & bản kẽm:** định mức mực theo diện tích phủ; theo dõi tồn bản kẽm và tái sử dụng bản lặp.
3. **Ghi nhận sản lượng thực tế (đã có cơ bản):** cần thêm đối chiếu với định mức theo máy và báo cáo hiệu suất.
4. **Tiến trình nâng cao:** mẫu theo loại sản phẩm (danh thiếp, tờ rơi, sách…), ghi nhận người phụ trách từng công đoạn.
5. **Tích hợp:** xuất hóa đơn điện tử, cổng khách hàng theo dõi đơn, xuất dữ liệu kế toán.
6. **Bảo mật nâng cao:** HTTPS nội bộ, buộc đổi mật khẩu lần đầu, nhật ký đăng nhập, sao lưu tự động.

## Giới hạn hiện tại

- Xếp bản đơn giản (một loại sản phẩm trên mỗi tờ); chưa gang-run nhiều thiết kế khác nhau.
- Định mức chi phí (lề kẹp, hao hụt, chạy thử, lợi nhuận, VAT) đang là hằng số trong mã nguồn.
- Lịch máy là hàng đợi nối tiếp đơn giản, chưa tối ưu theo ưu tiên hay ngày giao.
- Chưa có kiểm thử giao diện tự động; giao diện đã được kiểm tra cú pháp và thao tác API thật.
