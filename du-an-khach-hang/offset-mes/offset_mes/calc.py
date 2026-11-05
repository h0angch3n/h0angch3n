"""Tính toán thuần (không phụ thuộc DB) cho xưởng in offset.

Gồm: xếp bản (số sản phẩm trên một tờ in), số tờ cần in (kể cả hao phí),
khối lượng giấy, thời gian máy, và giá báo giá.
Tiền tệ: VND (làm tròn về số nguyên).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

BLEED_MM = 3                   # tràn mép mỗi cạnh
GRIPPER_MM = 10                # mép kẹp tờ của máy, không in được
GAP_MM = 3                     # khoảng cách giữa các sản phẩm (đường dao cắt)
MAKEREADY_SHEETS_PER_INK = 20  # tờ chạy thử/căn màu cho mỗi màu mực (mỗi mặt)
DEFAULT_SPOILAGE_PCT = 3.0     # hao hụt chạy máy (%)
DEFAULT_MARGIN_PCT = 25.0      # lợi nhuận gộp mục tiêu (%)
VAT_PCT = 10.0                 # thuế GTGT


@dataclass(frozen=True)
class Size:
    w: float  # mm
    h: float  # mm


@dataclass(frozen=True)
class Spec:
    quantity: int
    piece: Size              # kích thước thành phẩm (đã cắt)
    sheet: Size              # khổ tờ giấy in
    gsm: float               # định lượng giấy g/m²
    colors_front: int = 4
    colors_back: int = 0
    finishing_per_piece: float = 0.0   # phí gia công sau in (VND/cái)
    spoilage_pct: float = DEFAULT_SPOILAGE_PCT
    margin_pct: float = DEFAULT_MARGIN_PCT


@dataclass(frozen=True)
class Rates:
    paper_per_kg: float          # VND/kg giấy
    plate_price: float           # VND/bản kẽm
    press_hour_rate: float       # VND/giờ máy
    press_sheets_per_hour: float # tốc độ máy (tờ/giờ)
    makeready_hours: float = 0.5 # thời gian setup máy (giờ)


def ups(sheet: Size, piece: Size, gripper: float = GRIPPER_MM, gap: float = GAP_MM) -> int:
    """Số sản phẩm tối đa xếp trên một tờ, thử cả hai chiều xoay."""
    pw = piece.w + 2 * BLEED_MM
    ph = piece.h + 2 * BLEED_MM
    best = 0
    for a, b in ((pw, ph), (ph, pw)):
        cols = math.floor((sheet.w - gripper + gap) / (a + gap))
        rows = math.floor((sheet.h + gap) / (b + gap))
        best = max(best, cols * rows)
    if best <= 0:
        raise ValueError("Kích thước thành phẩm lớn hơn khổ tờ giấy")
    return best


def sheet_kg(sheet: Size, gsm: float) -> float:
    """Khối lượng một tờ giấy (kg)."""
    return (sheet.w / 1000) * (sheet.h / 1000) * gsm / 1000


def estimate(spec: Spec, rates: Rates) -> dict:
    """Tính số tờ, khối lượng giấy, thời gian máy và giá báo giá."""
    if spec.quantity <= 0:
        raise ValueError("Số lượng phải lớn hơn 0")
    if spec.colors_front < 0 or spec.colors_back < 0:
        raise ValueError("Số màu không hợp lệ")

    n_up = ups(spec.sheet, spec.piece)
    ink_units = spec.colors_front + spec.colors_back  # tổng số lượt màu (cả hai mặt)

    run_sheets = math.ceil(spec.quantity / n_up)
    waste_sheets = math.ceil(run_sheets * spec.spoilage_pct / 100)
    makeready_sheets = MAKEREADY_SHEETS_PER_INK * ink_units
    total_sheets = run_sheets + waste_sheets + makeready_sheets

    paper_kg = total_sheets * sheet_kg(spec.sheet, spec.gsm)
    paper_cost = paper_kg * rates.paper_per_kg
    plate_cost = ink_units * rates.plate_price

    press_hours = rates.makeready_hours + (run_sheets + waste_sheets) / rates.press_sheets_per_hour
    press_cost = press_hours * rates.press_hour_rate

    finishing_cost = spec.finishing_per_piece * spec.quantity
    cost = paper_cost + plate_cost + press_cost + finishing_cost
    price = cost * (1 + spec.margin_pct / 100)
    vat = price * VAT_PCT / 100
    total = round(price + vat)

    return {
        "ups": n_up,
        "run_sheets": run_sheets,
        "waste_sheets": waste_sheets,
        "makeready_sheets": makeready_sheets,
        "total_sheets": total_sheets,
        "paper_kg": round(paper_kg, 3),
        "press_hours": round(press_hours, 3),
        "cost": {
            "paper": round(paper_cost),
            "plates": round(plate_cost),
            "press": round(press_cost),
            "finishing": round(finishing_cost),
            "total": round(cost),
        },
        "margin_pct": spec.margin_pct,
        "subtotal": round(price),
        "vat": round(vat),
        "total": total,
        "unit_price": round(total / spec.quantity),
    }
