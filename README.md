# Công ty Cổ phần Dịch vụ Dev

**Công ty phần mềm**: phát triển phần mềm theo yêu cầu cho doanh nghiệp (web, ứng dụng di động, phần mềm quản lý),
triển khai, bảo trì và hỗ trợ sau bán hàng.

## Kho mã nguồn này có gì

| Thư mục | Là gì | Dùng cho |
|---|---|---|
| [`company-projeck/`](company-projeck/README.md) | **Projeck**: hệ thống quản lý dự án & giao việc nội bộ | Vận hành công ty: cơ cấu tổ chức, phân quyền, giao việc, duyệt kết quả |
| [`du-an-khach-hang/`](du-an-khach-hang/README.md) | **Dự án làm cho khách hàng** | Mỗi khách hàng / sản phẩm một thư mục riêng |
| [`du-an-khach-hang/offset-mes/`](du-an-khach-hang/offset-mes/README.md) | **Offset MES**: phần mềm quản lý sản xuất cho xưởng in offset | Dự án khách hàng ngành in |

```
.
├── README.md                    trang giới thiệu công ty (tài liệu này)
├── CLAUDE.md                    luật làm việc của đội AI
├── docs/SO_TAY_CONG_TY_AI.md    sổ tay giao việc cho đội AI (dành cho người)
├── .claude/                     các AI chuyên môn và lệnh /giao-viec
├── company-projeck/             hệ thống nội bộ của công ty
│   ├── server.py, public/       phần mềm Projeck
│   └── docs/                    hướng dẫn triển khai, quy trình giao việc
└── du-an-khach-hang/            các dự án làm cho khách hàng
    └── offset-mes/              phần mềm cho khách hàng ngành in offset
```

## Đội AI làm việc

Công ty vận hành theo mô hình **người giao việc và phê duyệt, đội AI thực hiện**. Gõ `/giao-viec <việc cần làm>`
trong Claude: AI Điều phối lập kế hoạch, rồi các AI Phân tích, Lập trình, Kiểm thử, Rà soát phối hợp với nhau.
Người giao việc chỉ duyệt hai lần: kế hoạch và kết quả.

- Hướng dẫn cho người: [docs/SO_TAY_CONG_TY_AI.md](docs/SO_TAY_CONG_TY_AI.md)
- Luật cho AI: [CLAUDE.md](CLAUDE.md)

## Cơ cấu tổ chức

Mô hình công ty cổ phần theo Luật Doanh nghiệp 2020:

```
Đại hội đồng cổ đông
        │
Hội đồng quản trị ── Ban Kiểm soát
        │
Ban Tổng Giám đốc
        │
├─ Khối Dự án:      Quản lý dự án (PMO) · Phân tích nghiệp vụ (BA)
├─ Khối Kỹ thuật:   Backend · Frontend · Mobile · Thiết kế UI/UX · Kiểm thử (QA/QC) · DevOps · Bảo mật
├─ Khối Khách hàng: Kinh doanh & Marketing · Hỗ trợ khách hàng
└─ Khối Vận hành:   Pháp chế – Hợp đồng · Nhân sự · Kế toán – Tài chính · Hành chính – Văn phòng
```

Chức năng từng bộ phận và quy trình làm một dự án phần mềm cho khách hàng:
[company-projeck/docs/QUY_TRINH_GIAO_VIEC.md](company-projeck/docs/QUY_TRINH_GIAO_VIEC.md).

## Quy trình một dự án khách hàng

Tiếp nhận yêu cầu → báo giá & hợp đồng → phân tích & thiết kế → lập trình → kiểm thử → triển khai
→ nghiệm thu & thanh toán → bảo hành, hỗ trợ.

Mỗi dự án mới: tạo thư mục trong `du-an-khach-hang/`, tạo dự án tương ứng trên Projeck để giao việc và theo dõi tiến độ.

## Chạy nhanh

| Mục đích | Thư mục | Lệnh |
|---|---|---|
| Hệ thống giao việc nội bộ | `company-projeck/` | `python server.py --open` (Windows: nhấp đúp `start_windows.bat`) |
| Chạy thử Projeck với dữ liệu mẫu | `company-projeck/` | `python server.py --demo --port 8090 --open` |
| Phần mềm Offset MES của khách hàng | `du-an-khach-hang/offset-mes/` | `python -m offset_mes desktop` |

Mọi phần mềm chỉ cần Python 3 và SQLite, không cần cài thêm gói.
