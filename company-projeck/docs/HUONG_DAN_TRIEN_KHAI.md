# Hướng dẫn triển khai Projeck — Công ty Cổ phần Dịch vụ Dev

Tài liệu cho người phụ trách IT/DevOps. Thời gian triển khai: khoảng 30 phút cho máy chủ, 1–2 ngày để tạo
tài khoản và hướng dẫn mọi người.

## 1. Chọn máy chủ

Projeck cần **một máy bật trong giờ làm việc**; mọi người khác chỉ cần trình duyệt.

| Phương án | Phù hợp khi | Ghi chú |
|---|---|---|
| Một máy tính trong văn phòng (Windows) | Dưới ~50 người, làm việc tại văn phòng | Đơn giản nhất. Cài IP tĩnh cho máy này |
| Máy chủ Linux / NAS trong văn phòng | Muốn chạy 24/7 | Chạy như dịch vụ hệ thống (mục 6) |
| VPS trên Internet | Có người làm từ xa | **Bắt buộc** đặt sau HTTPS (mục 7) |

## 2. Cài đặt trên Windows

1. Cài **Python 3.9 trở lên** tại https://www.python.org/downloads/. Khi cài, tick ô **"Add python.exe to PATH"**.
2. Chép thư mục `company-projeck` vào máy chủ, ví dụ `C:\Projeck`.
   Có thể để trong `G:\My Drive\Claude AI\Công ty Dev`: Projeck **không** đặt cơ sở dữ liệu trong thư mục đó
   (xem mục 4), nên Google Drive không làm hỏng dữ liệu.
3. Nhấp đúp **`start_windows.bat`**. Cửa sổ đen hiện địa chỉ, ví dụ:
   ```
    Máy này mở:          http://localhost:8080
    Máy khác cùng mạng:  http://192.168.1.20:8080
   ```
4. Trình duyệt tự mở trang **Thiết lập lần đầu**: nhập tên công ty, họ tên và tài khoản quản trị.
5. **Giữ cửa sổ đen mở** trong giờ làm việc. Đóng cửa sổ là dừng hệ thống.

Lần đầu chạy, Windows có thể hỏi về **Tường lửa (Firewall)**: chọn **Cho phép trên mạng riêng (Private)**,
nếu không, máy khác sẽ không vào được.

Muốn tự chạy khi bật máy: nhấn `Win + R`, gõ `shell:startup`, tạo shortcut tới `start_windows.bat` trong thư mục đó.

## 3. Cho nhân viên truy cập

- Gửi cho mọi người địa chỉ **"Máy khác cùng mạng"**, ví dụ `http://192.168.1.20:8080`.
- Trên điện thoại: kết nối cùng Wi-Fi văn phòng, mở địa chỉ trên. Nên "Thêm vào màn hình chính".
- Địa chỉ IP đổi khi khởi động lại router → đặt **IP tĩnh** cho máy chủ (trong router: DHCP reservation).
- Đổi cổng nếu 8080 bị trùng: `python server.py --port 8081`.

**Không** mở trực tiếp file `public/index.html`; luôn mở qua địa chỉ máy chủ.

## 4. Dữ liệu được lưu ở đâu

| Thứ | Vị trí mặc định (Windows) | Ghi chú |
|---|---|---|
| Cơ sở dữ liệu | `%LOCALAPPDATA%\Projeck\projeck.db` | Trên ổ cục bộ, **không** đồng bộ Google Drive. Đồng bộ một file SQLite đang mở có thể làm hỏng dữ liệu |
| Sao lưu tự động | thư mục `backups\` cạnh `server.py` | Mỗi ngày một bản, giữ 14 bản gần nhất. Nếu thư mục Projeck nằm trong Google Drive, bản sao lưu tự lên Drive: có sẵn bản sao ngoài văn phòng |
| Dữ liệu dùng thử | `%LOCALAPPDATA%\Projeck\projeck-demo.db` | Tách riêng, xóa thoải mái |

Trên Linux, cơ sở dữ liệu nằm ở `~/.local/share/Projeck/`. Đổi vị trí bằng `--db` và `--backup-dir`.

## 5. Sao lưu và khôi phục

- **Tự động**: mỗi lần khởi động và mỗi 24 giờ máy chủ còn chạy. Cửa sổ đen in dòng `[sao lưu] ...`.
- **Sao lưu ngay**: `python server.py backup`.
- **Xuất JSON** (nút trên giao diện, chỉ quản trị): đọc được bằng mắt, dùng để lưu trữ hoặc báo cáo.

Khôi phục từ một bản sao lưu:
1. Đóng cửa sổ máy chủ.
2. Chép file `backups\projeck-YYYYMMDD-HHMMSS.db` đè lên `%LOCALAPPDATA%\Projeck\projeck.db`
   (xóa thêm `projeck.db-wal` và `projeck.db-shm` nếu có).
3. Chạy lại `start_windows.bat`.

Mỗi tháng nên **thử khôi phục một lần** vào máy khác để chắc bản sao lưu dùng được.

## 6. Chạy 24/7 trên Linux (systemd)

```ini
# /etc/systemd/system/projeck.service
[Unit]
Description=Projeck - Cong ty Co phan Dich vu Dev
After=network.target

[Service]
User=projeck
WorkingDirectory=/opt/projeck
ExecStart=/usr/bin/python3 /opt/projeck/server.py --port 8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now projeck
```

## 7. Mở ra Internet (người làm từ xa)

Máy chủ Projeck nói HTTP thường. Trên Internet phải có **HTTPS**, nếu không mật khẩu đi qua mạng ở dạng đọc được.
Cách đơn giản: chạy Projeck chỉ nghe nội bộ (`--host 127.0.0.1`) và đặt **Caddy** phía trước (tự cấp chứng chỉ HTTPS):

```
# Caddyfile
projeck.congtydev.vn {
    reverse_proxy 127.0.0.1:8080
}
```

Phương án thay thế không cần mở cổng: VPN nội bộ (WireGuard, Tailscale) để nhân viên từ xa vào mạng văn phòng.

## 8. Cập nhật phiên bản mới

1. Sao lưu: `python server.py backup`.
2. Đóng máy chủ, chép đè các file mới (`server.py`, `public/`, …). **Không** cần đụng tới cơ sở dữ liệu.
3. Chạy lại. Bảng dữ liệu mới (nếu có) được tạo tự động.

## 9. Sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| "Chưa cài Python" khi mở `start_windows.bat` | Cài lại Python, nhớ tick "Add python.exe to PATH" |
| Máy khác không vào được | Kiểm tra Tường lửa Windows cho phép Python; hai máy cùng mạng; dùng đúng IP in ra |
| "Không mở được cổng 8080" | Có chương trình khác dùng cổng: `python server.py --port 8081` |
| Quên mật khẩu quản trị | Trên máy chủ: `python server.py reset-password <tên đăng nhập>` |
| Nhân viên quên mật khẩu | Quản trị vào tab Nhân sự → **Đặt lại MK** |
| Trang báo "Không kết nối được máy chủ" | Cửa sổ máy chủ đã bị đóng: chạy lại `start_windows.bat` |
