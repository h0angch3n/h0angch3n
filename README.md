# Offset MES — Phần mềm quản lý sản xuất thu nhỏ toàn trình cho xưởng in offset

Hệ thống phục vụ một xưởng in offset vừa và nhỏ đi từ **báo giá → đơn hàng → chuẩn bị bản → in → gia công sau in → QC → giao hàng → hóa đơn → thu tiền**,
với kho giấy và lịch máy được cập nhật theo từng bước.

Phiên bản hiện tại (`0.1.0`) chỉ dùng **thư viện chuẩn Python 3.10+** và **SQLite**, không cần cài thêm gói nào.

## Chạy thử

```bash
python3 -m offset_mes --port 8000 --db offset_mes.db
# mở http://127.0.0.1:8000
```

Chạy kiểm thử:

```bash
python3 -m unittest discover -s tests -t . -v
```

## Luồng nghiệp vụ

```
Khách hàng ──► Báo giá (tính số tờ, giấy, giờ máy, giá)
                  │ khách chốt
                  ▼
              Đơn hàng NEW ──► PREPRESS ──(xếp lịch máy)──► PLATE ──► PRINTING ──► FINISHING ──► QC ──► READY ──► DELIVERED ──► CLOSED
                                                                       │ xuất giấy khỏi kho            ▲ làm lại │        │ tạo hóa đơn    │ thu đủ tiền
                                                                                                      └─────────┘        ▼
                                                                                                                    Công nợ
```

| Module | Nội dung |
|---|---|
| `offset_mes/calc.py` | Thuần tính toán: xếp bản (`ups`, thử cả hai chiều xoay), số tờ = chạy + hao hụt + chạy thử căn màu, khối lượng giấy (kg), giờ máy, giá vốn → lợi nhuận → VAT 10% |
| `offset_mes/workflow.py` | Máy trạng thái vòng đời đơn; không cho nhảy cóc bước; QC có thể trả về gia công |
| `offset_mes/service.py` | Nghiệp vụ + SQLite: khách hàng, kho giấy, máy in, báo giá, đơn hàng, lịch máy, hóa đơn, thu tiền, tổng quan |
| `offset_mes/server.py` | REST API JSON (`dispatch` thuần để kiểm thử) và phục vụ giao diện tĩnh |
| `offset_mes/static/index.html` | Giao diện web một trang (tiếng Việt), không framework |

### Quy tắc nghiệp vụ đã mã hóa

- **Xếp bản:** lề kẹp máy 10 mm, khe cắt 3 mm, tràn mép 3 mm mỗi cạnh; chọn chiều xoay cho số sản phẩm/tờ lớn hơn.
- **Số tờ:** `ceil(SL / ups) + hao hụt% + 20 × số màu` (tờ chạy thử/căn màu).
- **Giấy:** khối lượng tờ = dài × rộng × gsm; giá tính theo VND/kg của loại giấy.
- **Máy:** không nhận đơn nếu số màu mặt trước/sau vượt quá số màu tối đa của máy; lịch máy xếp nối tiếp theo `available_at`.
- **Kho giấy:** chỉ xuất kho **một lần** khi chuyển sang `PRINTING`; thiếu giấy thì giữ nguyên trạng thái và báo lỗi 409.
- **Bản kẽm:** chưa làm bản (`PLATE`) thì bắt buộc đã xếp lịch máy.
- **Hóa đơn:** phát hành tự động khi đơn sang `DELIVERED`; đơn tự chuyển `CLOSED` khi thu đủ tiền.

## API chính

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET/POST | `/api/customers` | Khách hàng |
| GET/POST | `/api/papers`, `POST /api/papers/{id}/restock` | Kho giấy |
| GET/POST | `/api/machines` | Máy in |
| POST | `/api/quotes/estimate` | Tính báo giá (không lưu) |
| GET/POST | `/api/quotes`, `POST /api/quotes/{id}/accept` | Báo giá và chốt thành đơn |
| GET | `/api/jobs?status=` , `GET /api/jobs/{id}` | Đơn hàng kèm lịch sử và hóa đơn |
| POST | `/api/jobs/{id}/transition` `{"to": "..."}` | Chuyển trạng thái |
| POST | `/api/jobs/{id}/schedule` `{"machine_id": n}` | Xếp lịch máy |
| GET | `/api/invoices`, `POST /api/invoices/{id}/pay` `{"amount": n}` | Hóa đơn, công nợ |
| GET | `/api/dashboard` | Tổng quan: đơn theo trạng thái, doanh thu, công nợ, giấy sắp hết |

Ví dụ báo giá:

```bash
curl -X POST localhost:8000/api/quotes/estimate -H 'Content-Type: application/json' -d '{
  "paper_id": 1, "machine_id": 1, "piece_w": 90, "piece_h": 54, "quantity": 1000,
  "colors_front": 4, "colors_back": 4, "finishing_per_piece": 0, "margin_pct": 25
}'
```

## Lộ trình đề xuất

1. **Hoàn thiện nghiệp vụ lõi (đang có):** báo giá, đơn, kho giấy, lịch máy, hóa đơn.
2. **Prepress:** nhận file PDF, kiểm tra độ phân giải/màu/tràn mép, duyệt proof trực tuyến cho khách.
3. **Kho mực & bản kẽm:** định mức mực theo diện tích phủ, theo dõi tồn bản kẽm và tái sử dụng bản in lặp.
4. **MES trên xưởng:** ghi nhận sản lượng và phế phẩm theo từng máy, đo thời gian thực để điều chỉnh định mức.
5. **Gia công sau in:** quy trình cắt, gấp, đóng sách, cán màng, với công đoạn và người phụ trách.
6. **Tích hợp:** xuất hóa đơn điện tử, cổng khách hàng để theo dõi đơn, kết nối kế toán.
7. **Đa người dùng:** phân quyền (kinh doanh, prepress, vận hành máy, kế toán) và đăng nhập.

## Giới hạn hiện tại

- Chưa có đăng nhập/phân quyền; chỉ phù hợp chạy nội bộ trên mạng LAN tin cậy (mặc định bind `127.0.0.1`).
- Mô hình xếp bản là đơn giản (một loại sản phẩm trên mỗi tờ); chưa hỗ trợ xếp nhiều thiết kế khác nhau trên cùng khổ (gang-run).
- Giá mực và thời gian setup được quy về thông số máy/bảng giá cố định; chưa có định mức theo từng loại giấy/mực.
- Lịch máy là hàng đợi nối tiếp đơn giản, chưa tối ưu theo ưu tiên hay ngày giao.
