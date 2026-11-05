# Projeck — Hệ thống quản lý dự án & giao việc của Công ty Cổ phần Dịch vụ Dev

Phần mềm nội bộ để **Ban Tổng Giám đốc, quản lý dự án, trưởng bộ phận và nhân viên** giao việc, nhận việc,
báo tiến độ và duyệt kết quả trên **một dữ liệu dùng chung**. Chạy trên một máy trong văn phòng, mọi người
mở bằng trình duyệt (máy tính hoặc điện thoại) qua mạng nội bộ.

- **Không cần cài thêm gì** ngoài Python 3.9+. Dữ liệu lưu bằng SQLite, có sao lưu tự động mỗi ngày.
- **Cơ cấu công ty cổ phần có sẵn**: Hội đồng quản trị, Ban Kiểm soát, Ban Tổng Giám đốc và 15 khối/bộ phận chức năng.
- **Phân quyền 4 vai trò**: Quản trị / Tổng Giám đốc · Quản lý dự án · Trưởng bộ phận · Nhân viên.
- **Quy trình duyệt**: nhân viên làm xong chuyển *Chờ duyệt*, người giao việc duyệt *Hoàn thành* hoặc trả lại.
- **Thông báo, bình luận, lịch sử thay đổi** trên từng công việc.

## Chạy nhanh

| Mục đích | Windows | Lệnh tương đương |
|---|---|---|
| Dùng thật | nhấp đúp `start_windows.bat` | `python server.py --open` |
| Xem thử với dữ liệu mẫu | nhấp đúp `chay_thu_demo.bat` | `python server.py --demo --port 8090 --open` |

Lần đầu chạy thật, trang web yêu cầu **tạo tài khoản quản trị** (Tổng Giám đốc). Sau đó vào tab **Việc của tôi**
và làm theo dự án **"Triển khai Projeck tại công ty"** được tạo sẵn (9 bước).

Chế độ dùng thử có sẵn 20 nhân sự mẫu, mật khẩu chung `demo123`: `ceo` (Tổng Giám đốc), `pm` (Quản lý dự án),
`be` (Trưởng Backend), `be2` (Nhân viên Backend). Dữ liệu thử nằm ở file riêng, không lẫn với dữ liệu thật.

## Tài liệu

- [Hướng dẫn triển khai](docs/HUONG_DAN_TRIEN_KHAI.md): cài đặt, mạng nội bộ, sao lưu, khôi phục, cập nhật, đưa lên Internet.
- [Quy trình giao việc](docs/QUY_TRINH_GIAO_VIEC.md): cơ cấu tổ chức, ai giao việc cho ai, vòng đời một công việc, quy ước hằng ngày.

## Các màn hình

| Tab | Dùng để |
|---|---|
| **Việc của tôi** | Việc mình cần làm (quá hạn và khẩn lên đầu), việc chờ mình duyệt, việc mình đã giao |
| **Tổng quan** | Số việc theo trạng thái, việc quá hạn, việc chưa giao, % hoàn thành, tải công việc từng người |
| **Công việc** | Giao việc mới, bảng Kanban 4 cột, lọc theo dự án / bộ phận / người / từ khóa |
| **Dự án** | Tạo dự án (mã `PRJ-xxx` tự sinh), quản lý dự án, tiến độ %, trạng thái |
| **Nhân sự** | Tạo tài khoản, xếp bộ phận, phân vai trò, đặt lại mật khẩu, cho nghỉ |
| **Cơ cấu tổ chức** | Sơ đồ tổ chức, tên công ty, bộ phận, bổ nhiệm trưởng bộ phận |

## Quyền theo vai trò

| Thao tác | Quản trị / TGĐ | Quản lý dự án | Trưởng bộ phận | Nhân viên |
|---|:-:|:-:|:-:|:-:|
| Xem toàn bộ công việc, dự án, nhân sự | ✓ | ✓ | ✓ | ✓ |
| Tạo / sửa / đóng dự án | ✓ | ✓ | | |
| Giao việc cho bất kỳ ai | ✓ | ✓ | | |
| Giao việc trong bộ phận mình | ✓ | ✓ | ✓ | |
| Tự ghi nhận việc cho chính mình | ✓ | ✓ | ✓ | ✓ |
| Đổi trạng thái việc được giao (đến *Chờ duyệt*) | ✓ | ✓ | ✓ | ✓ |
| Duyệt *Hoàn thành* | ✓ | ✓ | ✓ | chỉ việc tự tạo |
| Bình luận trên công việc | ✓ | ✓ | ✓ | ✓ |
| Tạo tài khoản, phân vai trò, sửa cơ cấu, đổi tên công ty, xuất dữ liệu | ✓ | | | |

Máy chủ kiểm tra lại mọi quyền; giao diện chỉ ẩn những nút không dùng được.

## Cấu trúc mã nguồn

```
company-projeck/
├── server.py              máy chủ: API, đăng nhập, phân quyền, thông báo, sao lưu (thư viện chuẩn Python)
├── public/
│   ├── index.html         khung trang
│   ├── style.css          giao diện (tự đổi sáng/tối theo hệ điều hành)
│   └── app.js             6 màn hình, giao việc, kéo thả, chi tiết công việc
├── start_windows.bat      chạy thật trên Windows
├── chay_thu_demo.bat      chạy thử với dữ liệu mẫu
├── tests/test_server.py   kiểm thử tự động (quyền, quy trình duyệt, sao lưu)
└── docs/                  hướng dẫn triển khai và quy trình giao việc
```

Kiểm thử:

```bash
python -m unittest discover -s tests -v
```

## Bảo mật

- Mật khẩu băm PBKDF2-SHA256 (200.000 vòng); phiên đăng nhập bằng cookie HttpOnly, SameSite=Strict, hạn 14 ngày.
- Khóa đăng nhập 1 phút sau 5 lần sai mật khẩu liên tiếp.
- Mọi thao tác ghi bắt buộc gửi JSON (chặn giả mạo yêu cầu từ trang khác); có Content-Security-Policy.
- Máy chủ chạy HTTP thường, dùng cho **mạng nội bộ**. Muốn mở ra Internet, đặt sau HTTPS (xem hướng dẫn triển khai).
