# Hướng dẫn sử dụng Offset MES

Offset MES là phần mềm ERP cho xưởng in offset: quản lý báo giá, đơn hàng, tiến trình sản xuất
theo danh sách bước, kho giấy, lịch máy và công nợ. Phần mềm chạy trên PC, dữ liệu lưu trong máy.

---

## 1. Cài đặt và chạy

### Cách A — Dùng file ứng dụng Windows (khuyến nghị cho xưởng)
1. Nhận file `OffsetMES.exe` từ người phụ trách kỹ thuật.
2. Nhấp đúp `OffsetMES.exe`. Trình duyệt sẽ tự mở địa chỉ `http://127.0.0.1:8765/`.
   Một cửa sổ dòng lệnh màu đen cũng hiện ra: **đừng đóng khi đang làm việc**, vì đóng là phần mềm dừng.
3. Khi xong việc, đóng cửa sổ dòng lệnh đó (hoặc nhấn Ctrl+C) để thoát.

> Dữ liệu nằm ở `%APPDATA%\OffsetMES\offset_mes.db`. **Sao lưu file này định kỳ** (xem mục 9).

### Cách B — Chạy từ mã nguồn (Python 3.10+)
```bash
python3 -m offset_mes desktop                  # mở như ứng dụng PC
python3 -m offset_mes --port 8000              # máy chủ web, truy cập từ máy khác trong mạng nội bộ
```

### Đóng gói file .exe (dành cho kỹ thuật viên)
Trên máy Windows có Python 3.10+, trong thư mục mã nguồn chạy:
```bat
scripts\build_windows.bat
```
File kết quả: `dist\OffsetMES.exe`.

---

## 2. Lần đầu sử dụng: tạo tài khoản quản trị

Khi mở phần mềm lần đầu, màn hình **Thiết lập tài khoản quản trị** sẽ hiện ra.

- **Tên đăng nhập:** tùy chọn, 3–32 ký tự gồm chữ, số, dấu `_` hoặc `.` (ví dụ `giamdoc.lan`).
- **Họ tên:** tên hiển thị trong nhật ký và trên các thao tác.
- **Mật khẩu:** tối thiểu 8 ký tự. Hãy chọn mật khẩu riêng, không dùng chung.

Sau khi tạo xong, hệ thống tự đăng nhập. Màn hình này **chỉ xuất hiện một lần**; các tài khoản sau được tạo trong mục *Tài khoản*.

### Quên mật khẩu quản trị
Trên máy chạy phần mềm, mở dòng lệnh tại thư mục cài đặt và chạy:
```bash
OffsetMES.exe create-admin --user giamdoc.lan
```
(Với mã nguồn: `python3 -m offset_mes create-admin --user giamdoc.lan`.)
Lệnh sẽ hỏi mật khẩu mới và đặt lại cho đúng tài khoản đó, đồng thời khôi phục quyền quản trị.

---

## 3. Tài khoản và phân quyền

| Vai trò | Được làm gì |
|---|---|
| **Quản trị viên (ADMIN)** | Toàn quyền. Tạo/khóa tài khoản, đặt lại mật khẩu, sửa mẫu tiến trình. |
| **Quản lý sản xuất (MANAGER)** | Toàn quyền vận hành: khách, báo giá, đơn, kho, máy, thu tiền. Không quản lý tài khoản, không sửa mẫu tiến trình. |
| **Kinh doanh (SALES)** | Khách hàng, tính và lưu báo giá, khách chốt đơn. Không thu tiền. |
| **Vận hành (OPERATOR)** | Đánh dấu hoàn thành bước tiến trình, chuyển trạng thái đơn, xếp máy, nhập kho giấy. |
| **Kế toán (ACCOUNTANT)** | Xem dữ liệu và ghi nhận thu tiền hóa đơn. |

Nguyên tắc:
- Hệ thống luôn có **ít nhất một quản trị viên đang hoạt động**; không thể hạ quyền hoặc khóa người cuối cùng.
- Khi khóa tài khoản hoặc đổi mật khẩu, phiên đăng nhập của người đó bị đăng xuất ngay.
- Mỗi người tự đổi mật khẩu bằng nút **Đổi mật khẩu** trên thanh đầu.

### Tạo tài khoản cho nhân viên (quản trị viên)
1. Vào tab **Tài khoản** → mục *Tạo tài khoản mới*.
2. Nhập tên đăng nhập, họ tên, mật khẩu tạm và chọn vai trò → **Tạo tài khoản**.
3. Báo nhân viên tự đổi mật khẩu ngay lần đăng nhập đầu (nút **Đổi mật khẩu**). Phần mềm chưa bắt buộc đổi, nên đây là việc của quản trị viên.

Để khóa nhân viên nghỉ việc: tab **Tài khoản** → nút **Khóa**. Để đặt lại mật khẩu: nhập mật khẩu mới ở cột *Đặt lại mật khẩu* → **Đặt**.

---

## 4. Luồng làm việc chuẩn

```
Báo giá ──khách chốt──► Đơn NEW ──► PREPRESS ──► (xếp máy) ──► PLATE ──► PRINTING ──► FINISHING ──► QC ──► READY ──► DELIVERED ──► CLOSED
                                                                                                    ▲ làm lại │
                                                                                                    └─────────┘
```

| Trạng thái | Việc cần làm | Ai thường làm |
|---|---|---|
| NEW | Đơn vừa được khách chốt | Kinh doanh |
| PREPRESS | Kiểm tra file, chốt proof, xếp khung in | Prepress |
| PLATE | Xuất và làm bản kẽm (đơn phải đã xếp máy) | Vận hành |
| PRINTING | Chạy thử, căn màu, in hàng loạt. **Giấy được xuất khỏi kho ở bước này.** | Vận hành máy |
| FINISHING | Cắt, bế, gấp, đóng quyển, cán màng | Gia công |
| QC | Kiểm tra theo mẫu duyệt. Nếu lỗi, chuyển ngược về FINISHING để làm lại. | QC |
| READY | Đóng gói, dán nhãn | Kho |
| DELIVERED | Đã giao khách. **Hóa đơn được phát hành tự động.** | Kinh doanh / Kế toán |
| CLOSED | Khách đã thanh toán đủ | Kế toán |

---

## 5. Tiến trình sản xuất theo danh sách bước

Mỗi đơn có một **danh sách bước** (checklist) sinh từ *mẫu tiến trình*. Ví dụ mẫu mặc định:

1. (PREPRESS) Kiểm tra file & chốt proof với khách
2. (PREPRESS) Xếp khung in (imposition)
3. (PLATE) Xuất và làm bản kẽm
4. (PRINTING) Chạy thử & căn màu
5. (PRINTING) In hàng loạt
6. (FINISHING) Cắt / bế
7. (FINISHING) Gấp / đóng quyển / cán màng
8. (QC) Kiểm tra chất lượng theo mẫu duyệt
9. (READY) Đóng gói, dán nhãn

### Cách làm việc với tiến trình
1. Vào tab **Đơn hàng**, bấm **Tiến trình** ở dòng đơn cần xem.
2. Tick vào từng bước khi xong. Hệ thống ghi **người làm** và **thời điểm**.
3. Thanh tiến độ hiển thị tỷ lệ hoàn thành (ví dụ 4/9 = 44%).
4. Khi đã hoàn thành **mọi bước của công đoạn hiện tại**, nút chuyển sang công đoạn tiếp theo mới cho phép.
   Nếu cố chuyển khi còn bước chưa xong, phần mềm báo rõ bước nào còn thiếu.
5. Cần bước riêng cho đơn (ví dụ "đóng dấu logo khách lên bản")? Trong màn hình tiến trình, chọn công đoạn,
   nhập tên bước và bấm **+ Thêm bước**. Bước này cũng phải xong trước khi qua công đoạn.
6. Bỏ tick nhầm: bấm lại vào ô đã tick. Thao tác này cũng được ghi vào nhật ký.
7. Cuối màn hình có **Nhật ký** ghi lại mọi thay đổi: ai làm gì, lúc nào, chuyển từ trạng thái nào.

### Sửa mẫu tiến trình (quản trị viên)
Tab **Quy trình**:
- Đổi công đoạn hoặc tên bước trực tiếp trong bảng.
- **+ Thêm bước** để thêm dòng mới; **Xóa** để bỏ dòng.
- **Lưu mẫu**: áp dụng cho các **đơn tạo từ nay về sau**. Đơn đang chạy giữ nguyên danh sách bước cũ.
- **Khôi phục mặc định** đưa mẫu về cấu hình ban đầu.

> Mẫu phải có ít nhất một bước, mỗi bước phải có tên và thuộc một công đoạn hợp lệ.

---

## 6. Các nghiệp vụ hằng ngày

### 6.1 Thêm khách hàng, giấy, máy in
Tab **Kho & máy**: điền form tương ứng và bấm **Thêm**. Giấy có thể nhập thêm bằng ô *Nhập thêm* (kg).

### 6.2 Tính báo giá
1. Tab **Báo giá**: chọn khách, loại giấy, máy in, kích thước thành phẩm, số lượng, số màu.
2. Bấm **Tính giá** để xem thử (không lưu). Kết quả gồm số sản phẩm/tờ, số tờ, kg giấy, giờ máy, tổng có VAT.
3. Bấm **Lưu báo giá** để lưu. Khi khách đồng ý, bấm **Khách chốt** ở dòng báo giá đó → đơn mới được tạo.

Các tham số mặc định (lề kẹp máy, hao hụt, số tờ chạy thử, lợi nhuận, VAT 10%) do kỹ thuật viên cấu hình trong mã nguồn; cần điều chỉnh thì báo người phụ trách.

### 6.3 Xếp lịch máy
Tab **Đơn hàng**: ở cột *Lịch máy*, chọn máy rồi bấm **Xếp**. Đơn sẽ nối vào hàng đợi của máy đó.
Đơn phải còn ở NEW, PREPRESS hoặc PLATE.

### 6.4 Nhập kho giấy
Tab **Kho & máy** → mục *Giấy trong kho* → ô *Nhập thêm* → **Nhập**. Giấy dưới 50 kg được cảnh báo ở tab Tổng quan.

### 6.5 Thu tiền
Tab **Hóa đơn**: nhập số tiền khách trả vào ô → **Ghi nhận**. Thu đủ tiền, đơn tự chuyển sang CLOSED.

### 6.6 Xem tổng quan
Tab **Tổng quan**: số đơn theo trạng thái, doanh thu đã xuất hóa đơn, công nợ phải thu, giấy sắp hết, máy in.

---

## 7. Xử lý lỗi thường gặp

| Thông báo | Nguyên nhân | Cách xử lý |
|---|---|---|
| "Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đã khóa" | Nhập sai hoặc tài khoản bị khóa | Kiểm tra lại; nhờ quản trị viên mở khóa hoặc đặt lại mật khẩu |
| "Cần đăng nhập" (401) | Phiên đã hết hạn (12 giờ) hoặc phần mềm vừa khởi động lại | Đăng nhập lại |
| "Tài khoản không có quyền..." (403) | Vai trò không được phép thao tác | Nhờ người có quyền, hoặc quản trị viên đổi vai trò |
| "Chưa hoàn thành tiến trình ..." | Còn bước chưa tick trong công đoạn hiện tại | Mở **Tiến trình**, tick đủ bước rồi chuyển tiếp |
| "Không đủ giấy ..." | Kho không đủ kg cho đơn | Nhập thêm giấy, rồi thử lại |
| "Máy ... không đủ số màu" | Số màu đơn vượt quá số màu của máy | Chọn máy khác hoặc giảm số màu |
| "Cần xếp lịch máy trước khi làm bản" | Đơn chưa có máy | Xếp lịch máy ở tab Đơn hàng |
| Trang trắng hoặc không mở được | Cổng 8765 đang bị chương trình khác dùng | Đóng ứng dụng cũ rồi mở lại (phần mềm tự chọn cổng khác nếu bận) |

---

## 8. Mẹo sử dụng
- Mọi bảng có thể cuộn ngang trên màn hình nhỏ.
- Dùng ô **Lọc trạng thái** ở tab Đơn hàng để xem nhanh đơn đang ở một công đoạn.
- Trang tự chuyển giao diện sáng/tối theo cài đặt hệ điều hành.

---

## 9. Sao lưu và khôi phục dữ liệu
- **Sao lưu:** khi phần mềm đang đóng, sao chép file `offset_mes.db` (Windows: `%APPDATA%\OffsetMES\offset_mes.db`)
  sang ổ USB hoặc ổ mạng. Nên làm hằng ngày hoặc cuối mỗi ca.
- **Khôi phục:** đóng phần mềm, chép file sao lưu đè lên file cũ, mở lại.
- **Chuyển máy:** sao chép file `.db` sang máy mới đúng thư mục dữ liệu rồi mở phần mềm.

> Không mở file `.db` bằng chương trình khác khi phần mềm đang chạy.

---

## 10. Bảo mật
- Đặt mật khẩu mạnh cho quản trị viên; không chia sẻ tài khoản cá nhân.
- Phần mềm mặc định chỉ nhận kết nối từ chính máy đó (`127.0.0.1`). Chỉ mở cho máy khác trong mạng nội bộ
  khi cần, và không đưa ra internet nếu chưa có tường lửa và HTTPS.
- Mật khẩu được lưu dưới dạng băm PBKDF2-SHA256, không lưu dạng gốc.
- Khi nhân viên nghỉ việc: khóa tài khoản ngay trong tab **Tài khoản**.

---

## 11. Hỗ trợ
Ghi lại: mã đơn (JOB-xxxxx), thao tác đang làm, thông báo lỗi nguyên văn, và ảnh màn hình. Gửi cho người phụ trách kỹ thuật.
