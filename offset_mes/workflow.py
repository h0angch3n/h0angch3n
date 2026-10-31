"""Vòng đời đơn hàng in offset, từ khi nhận đơn đến khi đóng công nợ.

NEW -> PREPRESS (chuẩn bị file, duyệt ui)
    -> PLATE    (làm bản kẽm, xếp lịch máy)
    -> PRINTING (in; xuất giấy khỏi kho)
    -> FINISHING (cắt, gấp, cán, đóng sách...)
    -> QC       (kiểm tra chất lượng)
    -> READY    (đóng gói, sẵn sàng giao)
    -> DELIVERED (giao hàng; phát hành hóa đơn)
    -> CLOSED   (đã thu đủ tiền)
QC có thể trả về FINISHING để làm lại. Có thể hủy trước khi in.
"""
from __future__ import annotations

STATUSES = [
    "NEW", "PREPRESS", "PLATE", "PRINTING", "FINISHING",
    "QC", "READY", "DELIVERED", "CLOSED", "CANCELLED",
]

TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"PREPRESS", "CANCELLED"},
    "PREPRESS": {"PLATE", "CANCELLED"},
    "PLATE": {"PRINTING", "CANCELLED"},
    "PRINTING": {"FINISHING"},
    "FINISHING": {"QC"},
    "QC": {"READY", "FINISHING"},
    "READY": {"DELIVERED"},
    "DELIVERED": {"CLOSED"},
    "CLOSED": set(),
    "CANCELLED": set(),
}


class InvalidTransition(Exception):
    pass


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, set())


def ensure_transition(current: str, target: str) -> None:
    if target not in STATUSES:
        raise InvalidTransition(f"Trạng thái không tồn tại: {target}")
    if not can_transition(current, target):
        raise InvalidTransition(f"Không thể chuyển từ {current} sang {target}")
