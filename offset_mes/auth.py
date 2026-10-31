"""Xác thực, băm mật khẩu và phân quyền theo vai trò.

- Mật khẩu băm bằng PBKDF2-SHA256 (thư viện chuẩn).
- Phiên đăng nhập lưu trong bộ nhớ, có thời hạn; khởi động lại ứng dụng thì phải đăng nhập lại.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

PBKDF2_ITER = 200_000
SESSION_TTL = 12 * 3600
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,32}$")
MIN_PASSWORD_LEN = 8

ROLES = {
    "ADMIN": "Quản trị viên — toàn quyền, quản lý tài khoản và quy trình",
    "MANAGER": "Quản lý sản xuất — toàn quyền vận hành, không quản lý tài khoản",
    "SALES": "Kinh doanh — khách hàng, báo giá, chốt đơn",
    "OPERATOR": "Vận hành — cập nhật tiến trình, xếp máy, chuyển trạng thái đơn",
    "ACCOUNTANT": "Kế toán — xem và ghi nhận thu tiền hóa đơn",
}

# Quyền: "read" xem; còn lại là hành động cụ thể. "*" = toàn quyền.
PERMS: dict[str, set[str]] = {
    "ADMIN": {"*"},
    "MANAGER": {"read", "customer.write", "quote.write", "job.write", "job.step",
                "stock.write", "machine.write", "invoice.pay"},
    "SALES": {"read", "customer.write", "quote.write"},
    "OPERATOR": {"read", "job.write", "job.step", "stock.write"},
    "ACCOUNTANT": {"read", "invoice.pay"},
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITER)
    return f"pbkdf2_sha256${PBKDF2_ITER}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
    return hmac.compare_digest(digest.hex(), digest_hex)


def allowed(role: str, perm: str) -> bool:
    granted = PERMS.get(role, set())
    return "*" in granted or perm in granted


def validate_username(username: str) -> None:
    if not USERNAME_RE.match(username or ""):
        raise ValueError("Tên đăng nhập 3–32 ký tự: chữ, số, dấu _ hoặc .")


def validate_password(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LEN} ký tự")


class Sessions:
    def __init__(self) -> None:
        self._tokens: dict[str, tuple[int, float]] = {}

    def create(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = (user_id, time.time() + SESSION_TTL)
        return token

    def user_id(self, token: str | None) -> int | None:
        if not token:
            return None
        entry = self._tokens.get(token)
        if entry is None:
            return None
        user_id, expires = entry
        if time.time() > expires:
            self._tokens.pop(token, None)
            return None
        return user_id

    def revoke(self, token: str | None) -> None:
        if token:
            self._tokens.pop(token, None)

    def revoke_user(self, user_id: int) -> None:
        for token, (uid, _) in list(self._tokens.items()):
            if uid == user_id:
                self._tokens.pop(token, None)
