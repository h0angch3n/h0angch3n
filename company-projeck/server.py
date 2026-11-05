#!/usr/bin/env python3
"""Projeck — máy chủ quản lý dự án & giao việc của Công ty Cổ phần Dịch vụ Dev.

Chỉ dùng thư viện chuẩn Python 3.9+ và SQLite, không cần cài thêm gói.

    python server.py                          # chạy thật, cổng 8080, dữ liệu lưu trên ổ máy này
    python server.py --open                   # như trên và tự mở trình duyệt
    python server.py --demo                   # chạy thử với dữ liệu mẫu (cơ sở dữ liệu riêng)
    python server.py reset-password <tên>     # đặt lại mật khẩu khi quên
    python server.py backup                   # sao lưu ngay một bản
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import sqlite3
import sys
import threading
import time
import traceback
import webbrowser
from contextlib import closing
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
PUBLIC = BASE / "public"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

ROLES = {"admin": "Quản trị / Tổng Giám đốc", "pm": "Quản lý dự án", "lead": "Trưởng bộ phận", "staff": "Nhân viên"}
STATUSES = {"todo": "Chờ làm", "doing": "Đang làm", "review": "Chờ duyệt", "done": "Hoàn thành"}
PRIORITIES = {"urgent": "Khẩn", "high": "Cao", "normal": "Thường", "low": "Thấp"}
PROJECT_STATUS = {"active": "Đang chạy", "paused": "Tạm dừng", "closed": "Đã đóng"}
COOKIE = "projeck_session"
SESSION_DAYS = 14
BACKUP_KEEP = 14
MAX_BODY = 1_000_000
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
USERNAME_RE = re.compile(r"^[a-z0-9._-]{2,32}$")

COMPANY_NAME = "Công ty Cổ phần Dịch vụ Dev"

# Cơ cấu công ty cổ phần (Luật Doanh nghiệp 2020): Đại hội đồng cổ đông → Hội đồng quản trị
# (+ Ban Kiểm soát) → Tổng Giám đốc điều hành các khối chức năng.
DEPARTMENTS = [
    ("Hội đồng quản trị", "Quyết định chiến lược, kế hoạch kinh doanh; bổ nhiệm Tổng Giám đốc; giám sát điều hành"),
    ("Ban Kiểm soát", "Kiểm tra tính hợp pháp, trung thực của quản lý điều hành và báo cáo tài chính"),
    ("Ban Tổng Giám đốc", "Điều hành hằng ngày; phê duyệt dự án, ngân sách và nhân sự chủ chốt"),
    ("Quản lý dự án (PMO)", "Lập kế hoạch, chia việc, theo dõi tiến độ, quản trị rủi ro"),
    ("Phân tích nghiệp vụ (BA)", "Thu thập yêu cầu, viết đặc tả, cầu nối khách hàng – kỹ thuật"),
    ("Phát triển Backend", "API, cơ sở dữ liệu, dịch vụ nền, tích hợp hệ thống"),
    ("Phát triển Frontend", "Giao diện web, hiệu năng và trải nghiệm phía người dùng"),
    ("Phát triển Mobile", "Ứng dụng iOS và Android"),
    ("Thiết kế UI/UX", "Nghiên cứu người dùng, wireframe, prototype, hệ thống thiết kế"),
    ("Kiểm thử (QA/QC)", "Kế hoạch test, test thủ công và tự động, kiểm soát chất lượng"),
    ("DevOps & Hạ tầng", "CI/CD, máy chủ, cloud, giám sát, sao lưu"),
    ("Bảo mật thông tin", "Đánh giá bảo mật, kiểm soát truy cập, tuân thủ"),
    ("Hỗ trợ khách hàng", "Tiếp nhận và xử lý yêu cầu, sự cố, bảo hành dịch vụ cho khách hàng"),
    ("Kinh doanh & Marketing", "Tìm khách hàng, báo giá, hợp đồng dịch vụ, truyền thông"),
    ("Pháp chế – Hợp đồng", "Soạn thảo, rà soát hợp đồng; tuân thủ pháp luật; sở hữu trí tuệ"),
    ("Nhân sự (HR)", "Tuyển dụng, đào tạo, đánh giá hiệu suất, chế độ"),
    ("Kế toán – Tài chính", "Thanh toán, công nợ, lương, thuế, báo cáo tài chính, sổ cổ đông"),
    ("Hành chính – Văn phòng", "Cơ sở vật chất, thiết bị, văn thư, mua sắm"),
]

# Dự án "Triển khai Projeck" tạo sẵn cho tài khoản quản trị: đây là kế hoạch đưa hệ thống vào dùng.
# (tiêu đề, ưu tiên, trạng thái, hạn sau N ngày, giờ ước lượng, mô tả)
ROLLOUT_TASKS = [
    ("Cài đặt và chạy máy chủ Projeck", "high", "done", 0, 1,
     "Đã xong khi bạn thấy màn hình này. Máy chạy server.py cần bật trong giờ làm việc."),
    ("Rà soát danh sách bộ phận cho đúng công ty", "high", "todo", 1, 1,
     "Tab Cơ cấu tổ chức: sửa tên, xóa bộ phận không có, thêm bộ phận còn thiếu."),
    ("Tạo tài khoản cho trưởng bộ phận và quản lý dự án", "high", "todo", 2, 2,
     "Tab Nhân sự: mỗi người một tên đăng nhập, mật khẩu tạm, đúng bộ phận và vai trò. "
     "Gửi riêng cho từng người, nhắc đổi mật khẩu ở lần đăng nhập đầu."),
    ("Bổ nhiệm trưởng bộ phận trong tab Cơ cấu tổ chức", "normal", "todo", 2, 0.5,
     "Trưởng bộ phận nhận thông báo duyệt việc của nhân viên trong bộ phận."),
    ("Tạo tài khoản cho toàn bộ nhân viên", "normal", "todo", 4, 2,
     "Có thể giao cho Nhân sự (HR) nếu đã cấp quyền Quản trị cho HR."),
    ("Tạo dự án thật đầu tiên và giao 5–10 việc thử", "normal", "todo", 5, 2,
     "Tab Dự án → Tạo dự án. Tab Công việc → Giao việc mới. Mỗi việc 2–16 giờ, có hạn, có tiêu chí hoàn thành."),
    ("Họp 15 phút hướng dẫn nhân viên dùng tab Việc của tôi", "normal", "todo", 6, 1,
     "Quy ước: bắt đầu làm → Đang làm; xong → Chờ duyệt; vướng → viết bình luận trong công việc."),
    ("Kiểm tra sao lưu tự động trong thư mục backups", "high", "todo", 7, 0.5,
     "Máy chủ tự sao lưu mỗi ngày. Mở thư mục backups xem có file mới; thử khôi phục một lần."),
    ("Tổng kết sau 2 tuần dùng Projeck và điều chỉnh quy trình", "low", "todo", 14, 1,
     "Xem tab Tổng quan: việc quá hạn, người quá tải. Điều chỉnh cách chia việc và hạn."),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, descr TEXT NOT NULL DEFAULT '', head_id INTEGER
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '', dept_id INTEGER, role TEXT NOT NULL DEFAULT 'staff',
    skills TEXT NOT NULL DEFAULT '', capacity INTEGER NOT NULL DEFAULT 6, pw_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, dept_id INTEGER,
    owner_id INTEGER, start TEXT NOT NULL DEFAULT '', due TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active', descr TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, title TEXT NOT NULL,
    descr TEXT NOT NULL DEFAULT '', assignee_id INTEGER, creator_id INTEGER,
    priority TEXT NOT NULL DEFAULT 'normal', status TEXT NOT NULL DEFAULT 'todo',
    due TEXT NOT NULL DEFAULT '', estimate REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, user_id INTEGER,
    kind TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, task_id INTEGER, body TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_activity_task ON activity(task_id);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);
"""


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------- tiện ích

def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def add_days(n: int) -> str:
    return (dt.date.today() + dt.timedelta(days=n)).isoformat()


def hash_password(password: str, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc.hex(), digest)


def default_data_dir() -> Path:
    """Cơ sở dữ liệu nằm trên ổ cục bộ, KHÔNG nằm trong thư mục Google Drive:
    đồng bộ một file SQLite đang mở có thể làm hỏng dữ liệu."""
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "Projeck"


def connect(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        if not conn.execute("SELECT 1 FROM departments LIMIT 1").fetchone():
            conn.executemany("INSERT INTO departments(name, descr) VALUES (?, ?)", DEPARTMENTS)
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES ('company_name', ?)", (COMPANY_NAME,))
        conn.commit()


def backup_db(db_path, backup_dir, keep: int = BACKUP_KEEP) -> Path:
    """Sao lưu an toàn khi máy chủ đang chạy (dùng API backup của SQLite)."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"projeck-{dt.datetime.now():%Y%m%d-%H%M%S}.db"
    with closing(connect(db_path)) as src, closing(sqlite3.connect(str(target))) as dst:
        src.backup(dst)
    old = sorted(backup_dir.glob("projeck-*.db"))
    for f in old[:-keep] if keep else []:
        try:
            f.unlink()
        except OSError:
            pass
    return target


def text(body: dict, key: str, limit: int, required: bool = False, label: str = "") -> str:
    value = body.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, (str, int, float)):
        raise ApiError(400, f"Giá trị không hợp lệ: {label or key}")
    value = str(value).strip()
    if required and not value:
        raise ApiError(400, f"Vui lòng nhập {label or key}")
    if len(value) > limit:
        raise ApiError(400, f"{label or key} quá dài (tối đa {limit} ký tự)")
    return value


def opt_int(value):
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, "Mã không hợp lệ")


def date_field(value) -> str:
    value = (value or "").strip() if isinstance(value, str) else ""
    if value and not DATE_RE.match(value):
        raise ApiError(400, "Ngày không hợp lệ (định dạng YYYY-MM-DD)")
    return value


def choice(value, options: dict, label: str) -> str:
    if value not in options:
        raise ApiError(400, f"{label} không hợp lệ")
    return value


def number(value, lo: float, hi: float, label: str) -> float:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        raise ApiError(400, f"{label} không hợp lệ")
    if not lo <= n <= hi:
        raise ApiError(400, f"{label} phải trong khoảng {lo:g}–{hi:g}")
    return n


def row_or_404(conn, table: str, row_id, what: str) -> sqlite3.Row:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (opt_int(row_id),)).fetchone()
    if not row:
        raise ApiError(404, f"Không tìm thấy {what}")
    return row


def active_user(conn, user_id):
    """Trả về người dùng đang làm việc, None nếu bỏ trống; lỗi nếu mã không tồn tại."""
    user_id = opt_int(user_id)
    if user_id is None:
        return None
    row = conn.execute("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,)).fetchone()
    if not row:
        raise ApiError(400, "Nhân sự không tồn tại hoặc đã nghỉ")
    return row


def dept_or_none(conn, dept_id):
    dept_id = opt_int(dept_id)
    if dept_id is None:
        return None
    if not conn.execute("SELECT 1 FROM departments WHERE id = ?", (dept_id,)).fetchone():
        raise ApiError(400, "Bộ phận không tồn tại")
    return dept_id


def dept_id_by_name(conn, name: str):
    row = conn.execute("SELECT id FROM departments WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else None


def company_name(conn) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = 'company_name'").fetchone()
    return row["value"] if row else COMPANY_NAME


def public_user(r) -> dict:
    return {k: r[k] for k in ("id", "username", "name", "title", "dept_id", "role", "skills", "capacity", "active")}


def require_role(me, *roles):
    if me["role"] not in roles:
        raise ApiError(403, "Bạn không có quyền thực hiện thao tác này")


# ---------------------------------------------------------------- quyền giao việc

def is_manager(me) -> bool:
    return me["role"] in ("admin", "pm")


def can_assign_to(me, assignee) -> bool:
    """Quản lý giao cho bất kỳ ai; trưởng bộ phận giao trong bộ phận mình; nhân viên chỉ tự nhận việc."""
    if is_manager(me):
        return True
    if assignee is None:
        return me["role"] == "lead"
    if me["role"] == "lead":
        return assignee["dept_id"] is not None and assignee["dept_id"] == me["dept_id"]
    return assignee["id"] == me["id"]


def can_edit_task(me, task, assignee) -> bool:
    if is_manager(me):
        return True
    if me["role"] == "lead":
        return (task["creator_id"] == me["id"] or task["assignee_id"] is None
                or (assignee is not None and assignee["dept_id"] == me["dept_id"]))
    return task["assignee_id"] == me["id"] or task["creator_id"] == me["id"]


def user_by_id(conn, user_id):
    if user_id is None:
        return None
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def user_name(conn, user_id) -> str:
    row = user_by_id(conn, user_id)
    return row["name"] if row else "Chưa giao"


def notify(conn, user_id, task_id, body: str, actor_id) -> None:
    if user_id is None or user_id == actor_id:
        return
    conn.execute("INSERT INTO notifications(user_id, task_id, body, created_at) VALUES (?, ?, ?, ?)",
                 (user_id, task_id, body, now()))


def log(conn, task_id, user_id, kind: str, body: str) -> None:
    conn.execute("INSERT INTO activity(task_id, user_id, kind, body, created_at) VALUES (?, ?, ?, ?, ?)",
                 (task_id, user_id, kind, body, now()))


def reviewer_of(conn, task) -> int | None:
    """Người duyệt: người giao việc; nếu tự giao cho mình thì là trưởng bộ phận."""
    if task["creator_id"] and task["creator_id"] != task["assignee_id"]:
        return task["creator_id"]
    assignee = user_by_id(conn, task["assignee_id"])
    if assignee and assignee["dept_id"]:
        dept = conn.execute("SELECT head_id FROM departments WHERE id = ?", (assignee["dept_id"],)).fetchone()
        if dept and dept["head_id"]:
            return dept["head_id"]
    return None


# ---------------------------------------------------------------- tạo dữ liệu

def create_user(conn, *, username, name, password, role="staff", dept_id=None, title="", skills="", capacity=6) -> int:
    username = (username or "").strip().lower()
    if not USERNAME_RE.match(username):
        raise ApiError(400, "Tên đăng nhập 2–32 ký tự, chỉ gồm chữ không dấu, số, dấu . _ -")
    if len(password or "") < 6:
        raise ApiError(400, "Mật khẩu tối thiểu 6 ký tự")
    if not (name or "").strip():
        raise ApiError(400, "Vui lòng nhập họ tên")
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        raise ApiError(400, "Tên đăng nhập đã tồn tại")
    cur = conn.execute(
        "INSERT INTO users(username, name, title, dept_id, role, skills, capacity, pw_hash, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (username, name.strip(), title, dept_id, role, skills, int(capacity), hash_password(password), now()))
    return cur.lastrowid


def next_code(conn) -> str:
    nums = [int(re.sub(r"\D", "", r["code"]) or 0) for r in conn.execute("SELECT code FROM projects")]
    return f"PRJ-{(max(nums) if nums else 0) + 1:03d}"


def insert_project(conn, *, name, dept_id, owner_id, start="", due="", descr="", status="active") -> int:
    cur = conn.execute(
        "INSERT INTO projects(code, name, dept_id, owner_id, start, due, status, descr, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (next_code(conn), name, dept_id, owner_id, start, due, status, descr, now()))
    return cur.lastrowid


def insert_task(conn, *, project_id, title, creator_id, assignee_id=None, descr="", priority="normal",
                status="todo", due="", estimate=0.0) -> int:
    ts = now()
    cur = conn.execute(
        "INSERT INTO tasks(project_id, title, descr, assignee_id, creator_id, priority, status, due, estimate,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (project_id, title, descr, assignee_id, creator_id, priority, status, due, estimate, ts, ts))
    log(conn, cur.lastrowid, creator_id, "change", f"Tạo công việc, giao cho {user_name(conn, assignee_id)}")
    return cur.lastrowid


def seed_rollout(conn, admin_id: int) -> None:
    pid = insert_project(conn, name="Triển khai Projeck tại công ty", dept_id=dept_id_by_name(conn, "Ban Tổng Giám đốc"),
                         owner_id=admin_id, start=add_days(0), due=add_days(14),
                         descr="Các bước đưa hệ thống giao việc vào dùng cho toàn công ty")
    for title, pri, status, due, est, descr in ROLLOUT_TASKS:
        insert_task(conn, project_id=pid, title=title, creator_id=admin_id, assignee_id=admin_id, descr=descr,
                    priority=pri, status=status, due=add_days(due), estimate=est)


def seed_demo(conn) -> None:
    """Dữ liệu mẫu để chạy thử. Mật khẩu chung: demo123."""
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return
    d = lambda name: dept_id_by_name(conn, name)  # noqa: E731
    people = [
        ("ceo", "Lê Thành Đạt", "Ban Tổng Giám đốc", "Tổng Giám đốc", "admin", "Điều hành"),
        ("chutich", "Trương Văn Hùng", "Hội đồng quản trị", "Chủ tịch HĐQT", "admin", "Chiến lược"),
        ("bks", "Kiều Thị Mai", "Ban Kiểm soát", "Trưởng Ban Kiểm soát", "lead", "Kiểm toán nội bộ"),
        ("cto", "Võ Hoàng Nam", "Ban Tổng Giám đốc", "Phó Tổng Giám đốc kỹ thuật (CTO)", "pm", "Kiến trúc hệ thống"),
        ("pm", "Nguyễn Minh Anh", "Quản lý dự án (PMO)", "Trưởng PMO", "pm", "Agile, Scrum"),
        ("ba", "Châu Ngọc Diệp", "Phân tích nghiệp vụ (BA)", "Business Analyst", "lead", "Đặc tả"),
        ("be", "Trần Quốc Bảo", "Phát triển Backend", "Trưởng nhóm Backend", "lead", "Node.js, PostgreSQL"),
        ("be2", "Lâm Tuấn Kiệt", "Phát triển Backend", "Backend Developer", "staff", "Java, Spring"),
        ("fe", "Phạm Thu Hà", "Phát triển Frontend", "Trưởng nhóm Frontend", "lead", "React"),
        ("mob", "Vũ Đức Long", "Phát triển Mobile", "Mobile Developer", "lead", "Flutter"),
        ("ux", "Hoàng Lan Chi", "Thiết kế UI/UX", "UI/UX Designer", "lead", "Figma"),
        ("qa", "Đỗ Hải Yến", "Kiểm thử (QA/QC)", "QA Lead", "lead", "Playwright"),
        ("ops", "Bùi Văn Khoa", "DevOps & Hạ tầng", "DevOps Engineer", "lead", "Docker"),
        ("sec", "Ngô Gia Huy", "Bảo mật thông tin", "Security Engineer", "lead", "OWASP"),
        ("sup", "Lý Thanh Tâm", "Hỗ trợ khách hàng", "Trưởng CSKH", "lead", "CRM"),
        ("sales", "Đặng Minh Quân", "Kinh doanh & Marketing", "Account Manager", "lead", "Đàm phán"),
        ("legal", "Tạ Quang Vinh", "Pháp chế – Hợp đồng", "Chuyên viên pháp chế", "lead", "Hợp đồng, SHTT"),
        ("hr", "Trịnh Thu Trang", "Nhân sự (HR)", "Chuyên viên nhân sự", "lead", "Tuyển dụng"),
        ("fin", "Phan Ngọc Ánh", "Kế toán – Tài chính", "Kế toán trưởng", "lead", "Kế toán"),
        ("admin1", "Mai Đình Sơn", "Hành chính – Văn phòng", "Nhân viên hành chính", "lead", "Mua sắm"),
    ]
    ids = {}
    for username, name, dept, title, role, skills in people:
        ids[username] = create_user(conn, username=username, name=name, password="demo123", role=role,
                                    dept_id=d(dept), title=title, skills=skills)
        if role in ("lead", "admin") or username == "pm":
            conn.execute("UPDATE departments SET head_id = ? WHERE id = ? AND head_id IS NULL", (ids[username], d(dept)))
    seed_rollout(conn, ids["ceo"])
    p1 = insert_project(conn, name="Website thương mại điện tử cho khách hàng A", dept_id=d("Quản lý dự án (PMO)"),
                        owner_id=ids["pm"], start=add_days(-14), due=add_days(45),
                        descr="Web bán hàng, trang quản trị, thanh toán online")
    p2 = insert_project(conn, name="Ứng dụng mobile đặt lịch", dept_id=d("Phát triển Mobile"),
                        owner_id=ids["pm"], start=add_days(-3), due=add_days(75),
                        descr="App iOS/Android đặt lịch hẹn, thông báo đẩy")
    tasks = [
        (p1, "Lập kế hoạch sprint 1 và phân công", "pm", "pm", "normal", "done", -12, 3),
        (p1, "Viết đặc tả yêu cầu giỏ hàng & thanh toán", "ba", "pm", "high", "done", -8, 8),
        (p1, "Thiết kế wireframe trang sản phẩm", "ux", "pm", "high", "review", 2, 8),
        (p1, "Xây dựng API đơn hàng", "be", "pm", "urgent", "doing", 5, 16),
        (p1, "API thanh toán VNPay", "be2", "be", "high", "todo", 9, 12),
        (p1, "Dựng giao diện trang danh sách sản phẩm", "fe", "pm", "normal", "doing", 7, 12),
        (p1, "Thiết lập pipeline CI/CD và môi trường staging", "ops", "pm", "high", "todo", 4, 10),
        (p1, "Rà soát bảo mật luồng đăng nhập", "sec", "pm", "high", "todo", -1, 6),
        (p1, "Viết kịch bản kiểm thử hồi quy", "qa", "pm", "normal", "todo", 10, 6),
        (p2, "Khung ứng dụng Flutter và điều hướng", "mob", "pm", "high", "doing", 6, 12),
        (p2, "API đặt lịch và thông báo đẩy", "be2", "be", "normal", "todo", 12, 14),
        (p2, "Tài liệu hướng dẫn sử dụng cho khách", "sup", "pm", "low", "todo", 40, 4),
    ]
    for pid, title, who, by, pri, status, due, est in tasks:
        insert_task(conn, project_id=pid, title=title, creator_id=ids[by], assignee_id=ids[who],
                    priority=pri, status=status, due=add_days(due), estimate=est)


# ---------------------------------------------------------------- API

FIELD_LABELS = {"title": "Tiêu đề", "descr": "Mô tả", "project_id": "Dự án", "assignee_id": "Người thực hiện",
                "priority": "Ưu tiên", "status": "Trạng thái", "due": "Hạn", "estimate": "Ước lượng (giờ)"}


def describe(conn, field, value) -> str:
    if field == "status":
        return STATUSES.get(value, value)
    if field == "priority":
        return PRIORITIES.get(value, value)
    if field == "assignee_id":
        return user_name(conn, value)
    if field == "project_id":
        row = conn.execute("SELECT code FROM projects WHERE id = ?", (value,)).fetchone()
        return row["code"] if row else "?"
    if field == "due":
        return "/".join(reversed(value.split("-"))) if value else "không đặt"
    if field == "estimate":
        return f"{value:g}h"
    return str(value)


class Api:
    def __init__(self, handler: "Handler", conn: sqlite3.Connection, me):
        self.h = handler
        self.conn = conn
        self.me = me

    # --- tài khoản
    def bootstrap(self, body):
        has_users = self.conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
        return {"needs_setup": not has_users, "me": public_user(self.me) if self.me else None,
                "company": company_name(self.conn)}

    def setup(self, body):
        with self.h.app.lock:
            if self.conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise ApiError(403, "Hệ thống đã có tài khoản quản trị")
            uid = create_user(self.conn, username=text(body, "username", 32, True, "tên đăng nhập"),
                              name=text(body, "name", 80, True, "họ tên"), password=str(body.get("password", "")),
                              role="admin", dept_id=dept_id_by_name(self.conn, "Ban Tổng Giám đốc"), title="Tổng Giám đốc")
            self.conn.execute("UPDATE departments SET head_id = ? WHERE name = 'Ban Tổng Giám đốc'", (uid,))
            company = text(body, "company", 160)
            if company:
                self.conn.execute("UPDATE settings SET value = ? WHERE key = 'company_name'", (company,))
            seed_rollout(self.conn, uid)
            self.conn.commit()
        self.start_session(uid)
        return {"ok": True}

    def login(self, body):
        username = text(body, "username", 64).lower()
        password = str(body.get("password", ""))
        key = (self.h.client_address[0], username)
        fails = self.h.app.login_fails.get(key)
        recent = fails if fails and time.time() - fails[1] < 60 else None
        if recent and recent[0] >= 5:
            raise ApiError(429, "Sai mật khẩu quá nhiều lần, hãy thử lại sau 1 phút")
        row = self.conn.execute("SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
        if not row or not check_password(password, row["pw_hash"]):
            self.h.app.login_fails[key] = ((recent[0] if recent else 0) + 1, time.time())
            raise ApiError(401, "Sai tên đăng nhập hoặc mật khẩu")
        self.h.app.login_fails.pop(key, None)
        self.start_session(row["id"])
        return {"ok": True}

    def start_session(self, user_id):
        token = secrets.token_urlsafe(32)
        expires = (dt.datetime.now() + dt.timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
        self.conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        self.conn.execute("INSERT INTO sessions(token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires))
        self.h.extra_headers.append(("Set-Cookie", f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; "
                                                   f"Max-Age={SESSION_DAYS * 86400}"))

    def logout(self, body):
        token = self.h.session_token()
        if token:
            self.conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        self.h.extra_headers.append(("Set-Cookie", f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"))
        return {"ok": True}

    def change_password(self, body):
        if not check_password(str(body.get("old_password", "")), self.me["pw_hash"]):
            raise ApiError(400, "Mật khẩu hiện tại không đúng")
        new = str(body.get("new_password", ""))
        if len(new) < 6:
            raise ApiError(400, "Mật khẩu mới tối thiểu 6 ký tự")
        self.conn.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (hash_password(new), self.me["id"]))
        self.conn.execute("DELETE FROM sessions WHERE user_id = ? AND token != ?", (self.me["id"], self.h.session_token()))
        return {"ok": True}

    # --- dữ liệu tổng
    def state(self, body):
        q = lambda sql, *a: [dict(r) for r in self.conn.execute(sql, a)]  # noqa: E731
        unread = self.conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                                   (self.me["id"],)).fetchone()[0]
        return {
            "me": public_user(self.me),
            "company": company_name(self.conn),
            "departments": q("SELECT id, name, descr, head_id FROM departments ORDER BY id"),
            "users": [public_user(r) for r in self.conn.execute("SELECT * FROM users ORDER BY name")],
            "projects": q("SELECT * FROM projects ORDER BY id"),
            "tasks": q("SELECT * FROM tasks ORDER BY id"),
            "unread": unread,
        }

    def export(self, body):
        require_role(self.me, "admin")
        data = self.state(body)
        data["activity"] = [dict(r) for r in self.conn.execute("SELECT * FROM activity ORDER BY id")]
        data["exported_at"] = now()
        return data

    def settings_update(self, body):
        require_role(self.me, "admin")
        if "company" in body:
            self.conn.execute("UPDATE settings SET value = ? WHERE key = 'company_name'",
                              (text(body, "company", 160, True, "tên công ty"),))
        return {"ok": True}

    # --- thông báo
    def notifications(self, body):
        rows = self.conn.execute(
            "SELECT n.*, t.title AS task_title FROM notifications n LEFT JOIN tasks t ON t.id = n.task_id"
            " WHERE n.user_id = ? ORDER BY n.id DESC LIMIT 40", (self.me["id"],))
        return {"items": [dict(r) for r in rows]}

    def notifications_read(self, body):
        self.conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (self.me["id"],))
        return {"ok": True}

    # --- bộ phận
    def dept_create(self, body):
        require_role(self.me, "admin")
        cur = self.conn.execute("INSERT INTO departments(name, descr) VALUES (?, ?)",
                                (text(body, "name", 80, True, "tên bộ phận"), text(body, "descr", 200)))
        return 201, {"id": cur.lastrowid}

    def dept_update(self, body, dept_id):
        require_role(self.me, "admin")
        d = row_or_404(self.conn, "departments", dept_id, "bộ phận")
        name = text(body, "name", 80, True, "tên bộ phận") if "name" in body else d["name"]
        descr = text(body, "descr", 200) if "descr" in body else d["descr"]
        head_id = d["head_id"]
        if "head_id" in body:
            head = active_user(self.conn, body["head_id"])
            if head and head["dept_id"] != d["id"]:
                raise ApiError(400, "Trưởng bộ phận phải là nhân sự thuộc bộ phận này")
            head_id = head["id"] if head else None
        self.conn.execute("UPDATE departments SET name = ?, descr = ?, head_id = ? WHERE id = ?",
                          (name, descr, head_id, d["id"]))
        return {"ok": True}

    def dept_delete(self, body, dept_id):
        require_role(self.me, "admin")
        d = row_or_404(self.conn, "departments", dept_id, "bộ phận")
        if self.conn.execute("SELECT 1 FROM users WHERE dept_id = ? AND active = 1", (d["id"],)).fetchone():
            raise ApiError(400, "Hãy chuyển nhân sự sang bộ phận khác trước khi xóa")
        self.conn.execute("UPDATE users SET dept_id = NULL WHERE dept_id = ?", (d["id"],))
        self.conn.execute("UPDATE projects SET dept_id = NULL WHERE dept_id = ?", (d["id"],))
        self.conn.execute("DELETE FROM departments WHERE id = ?", (d["id"],))
        return {"ok": True}

    # --- nhân sự
    def user_create(self, body):
        require_role(self.me, "admin")
        uid = create_user(
            self.conn, username=text(body, "username", 32, True, "tên đăng nhập"),
            name=text(body, "name", 80, True, "họ tên"), password=str(body.get("password", "")),
            role=choice(body.get("role", "staff"), ROLES, "Vai trò"), dept_id=dept_or_none(self.conn, body.get("dept_id")),
            title=text(body, "title", 80), skills=text(body, "skills", 200),
            capacity=int(number(body.get("capacity", 6), 0, 50, "Sức chứa")))
        return 201, {"id": uid}

    def user_update(self, body, user_id):
        require_role(self.me, "admin")
        u = row_or_404(self.conn, "users", user_id, "nhân sự")
        fields = {}
        if "name" in body:
            fields["name"] = text(body, "name", 80, True, "họ tên")
        for key, limit in (("title", 80), ("skills", 200)):
            if key in body:
                fields[key] = text(body, key, limit)
        if "capacity" in body:
            fields["capacity"] = int(number(body["capacity"], 0, 50, "Sức chứa"))
        if "role" in body:
            fields["role"] = choice(body["role"], ROLES, "Vai trò")
            if u["id"] == self.me["id"] and fields["role"] != "admin":
                raise ApiError(400, "Không thể tự bỏ quyền quản trị của chính mình")
        if "dept_id" in body:
            fields["dept_id"] = dept_or_none(self.conn, body["dept_id"])
            if fields["dept_id"] != u["dept_id"]:
                self.conn.execute("UPDATE departments SET head_id = NULL WHERE head_id = ?", (u["id"],))
        if "active" in body and body["active"]:
            fields["active"] = 1
        if body.get("password"):
            if len(str(body["password"])) < 6:
                raise ApiError(400, "Mật khẩu tối thiểu 6 ký tự")
            fields["pw_hash"] = hash_password(str(body["password"]))
            self.conn.execute("DELETE FROM sessions WHERE user_id = ?", (u["id"],))
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            self.conn.execute(f"UPDATE users SET {sets} WHERE id = ?", (*fields.values(), u["id"]))
        return {"ok": True}

    def user_deactivate(self, body, user_id):
        """Cho nghỉ việc: giữ lại tên trong lịch sử, bỏ giao các việc chưa xong."""
        require_role(self.me, "admin")
        u = row_or_404(self.conn, "users", user_id, "nhân sự")
        if u["id"] == self.me["id"]:
            raise ApiError(400, "Không thể tự khóa tài khoản của chính mình")
        open_tasks = self.conn.execute("SELECT id FROM tasks WHERE assignee_id = ? AND status != 'done'", (u["id"],))
        for t in open_tasks.fetchall():
            self.conn.execute("UPDATE tasks SET assignee_id = NULL, updated_at = ? WHERE id = ?", (now(), t["id"]))
            log(self.conn, t["id"], self.me["id"], "change", f"Bỏ giao vì {u['name']} đã nghỉ")
        self.conn.execute("UPDATE users SET active = 0 WHERE id = ?", (u["id"],))
        self.conn.execute("UPDATE departments SET head_id = NULL WHERE head_id = ?", (u["id"],))
        self.conn.execute("UPDATE projects SET owner_id = NULL WHERE owner_id = ?", (u["id"],))
        self.conn.execute("DELETE FROM sessions WHERE user_id = ?", (u["id"],))
        return {"ok": True}

    # --- dự án
    def project_create(self, body):
        require_role(self.me, "admin", "pm")
        owner = active_user(self.conn, body.get("owner_id"))
        pid = insert_project(self.conn, name=text(body, "name", 160, True, "tên dự án"),
                             dept_id=dept_or_none(self.conn, body.get("dept_id")),
                             owner_id=owner["id"] if owner else None, start=date_field(body.get("start")),
                             due=date_field(body.get("due")), descr=text(body, "descr", 300))
        return 201, {"id": pid}

    def project_update(self, body, project_id):
        require_role(self.me, "admin", "pm")
        p = row_or_404(self.conn, "projects", project_id, "dự án")
        fields = {}
        if "name" in body:
            fields["name"] = text(body, "name", 160, True, "tên dự án")
        if "descr" in body:
            fields["descr"] = text(body, "descr", 300)
        if "dept_id" in body:
            fields["dept_id"] = dept_or_none(self.conn, body["dept_id"])
        if "owner_id" in body:
            owner = active_user(self.conn, body["owner_id"])
            fields["owner_id"] = owner["id"] if owner else None
        for key in ("start", "due"):
            if key in body:
                fields[key] = date_field(body[key])
        if "status" in body:
            fields["status"] = choice(body["status"], PROJECT_STATUS, "Trạng thái dự án")
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            self.conn.execute(f"UPDATE projects SET {sets} WHERE id = ?", (*fields.values(), p["id"]))
        return {"ok": True}

    def project_delete(self, body, project_id):
        require_role(self.me, "admin", "pm")
        p = row_or_404(self.conn, "projects", project_id, "dự án")
        sub = "SELECT id FROM tasks WHERE project_id = ?"
        self.conn.execute(f"DELETE FROM activity WHERE task_id IN ({sub})", (p["id"],))
        self.conn.execute(f"DELETE FROM notifications WHERE task_id IN ({sub})", (p["id"],))
        self.conn.execute("DELETE FROM tasks WHERE project_id = ?", (p["id"],))
        self.conn.execute("DELETE FROM projects WHERE id = ?", (p["id"],))
        return {"ok": True}

    # --- công việc
    def task_create(self, body):
        me = self.me
        project = row_or_404(self.conn, "projects", body.get("project_id"), "dự án")
        if project["status"] == "closed":
            raise ApiError(400, "Dự án đã đóng, không thể thêm việc")
        assignee = active_user(self.conn, body.get("assignee_id"))
        if assignee is None and me["role"] == "staff":
            assignee = me
        if not can_assign_to(me, assignee):
            raise ApiError(403, "Bạn chỉ được giao việc cho " + (
                "nhân sự trong bộ phận của mình" if me["role"] == "lead" else "chính mình"))
        tid = insert_task(
            self.conn, project_id=project["id"], title=text(body, "title", 160, True, "tiêu đề"),
            creator_id=me["id"], assignee_id=assignee["id"] if assignee else None, descr=text(body, "descr", 2000),
            priority=choice(body.get("priority", "normal"), PRIORITIES, "Mức ưu tiên"),
            due=date_field(body.get("due")), estimate=number(body.get("estimate", 0), 0, 1000, "Ước lượng"))
        if assignee:
            notify(self.conn, assignee["id"], tid, f"{me['name']} giao cho bạn: {body['title'].strip()}", me["id"])
        return 201, {"id": tid}

    def task_update(self, body, task_id):
        me = self.me
        t = row_or_404(self.conn, "tasks", task_id, "công việc")
        assignee = user_by_id(self.conn, t["assignee_id"])
        if not can_edit_task(me, t, assignee):
            raise ApiError(403, "Bạn không có quyền sửa công việc này")
        full = me["role"] != "staff" or t["creator_id"] == me["id"]
        changes = {}
        for field in FIELD_LABELS:
            if field not in body:
                continue
            if not full and field != "status":
                raise ApiError(403, "Bạn chỉ được cập nhật trạng thái của việc được giao")
            raw = body[field]
            if field == "title":
                value = text(body, "title", 160, True, "tiêu đề")
            elif field == "descr":
                value = text(body, "descr", 2000)
            elif field == "project_id":
                value = row_or_404(self.conn, "projects", raw, "dự án")["id"]
            elif field == "assignee_id":
                new = active_user(self.conn, raw)
                value = new["id"] if new else None
                if value != t["assignee_id"] and not can_assign_to(me, new):
                    raise ApiError(403, "Bạn không được giao việc cho người này")
            elif field == "priority":
                value = choice(raw, PRIORITIES, "Mức ưu tiên")
            elif field == "status":
                value = choice(raw, STATUSES, "Trạng thái")
            elif field == "due":
                value = date_field(raw)
            else:
                value = number(raw, 0, 1000, "Ước lượng")
            if value != t[field]:
                changes[field] = value
        if changes.get("status") == "done" and me["role"] == "staff" and t["creator_id"] != me["id"]:
            raise ApiError(403, 'Hãy chuyển sang "Chờ duyệt"; người giao việc sẽ duyệt hoàn thành')
        if not changes:
            return {"ok": True}

        sets = ", ".join(f"{k} = ?" for k in changes)
        self.conn.execute(f"UPDATE tasks SET {sets}, updated_at = ? WHERE id = ?", (*changes.values(), now(), t["id"]))
        parts = []
        for field, value in changes.items():
            if field == "descr":
                parts.append("Sửa mô tả")
            else:
                parts.append(f"{FIELD_LABELS[field]}: {describe(self.conn, field, t[field])} → "
                             f"{describe(self.conn, field, value)}")
        log(self.conn, t["id"], me["id"], "change", "; ".join(parts))

        updated = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (t["id"],)).fetchone()
        title = updated["title"]
        if "assignee_id" in changes:
            notify(self.conn, changes["assignee_id"], t["id"], f"{me['name']} giao cho bạn: {title}", me["id"])
        status = changes.get("status")
        if status == "review":
            notify(self.conn, reviewer_of(self.conn, updated), t["id"], f"{me['name']} gửi duyệt: {title}", me["id"])
        elif status == "done":
            notify(self.conn, updated["assignee_id"], t["id"], f"{me['name']} đã duyệt hoàn thành: {title}", me["id"])
        elif status in ("todo", "doing") and t["status"] in ("review", "done"):
            notify(self.conn, updated["assignee_id"], t["id"], f"{me['name']} trả lại để làm tiếp: {title}", me["id"])
        return {"ok": True}

    def task_delete(self, body, task_id):
        t = row_or_404(self.conn, "tasks", task_id, "công việc")
        if not (is_manager(self.me) or t["creator_id"] == self.me["id"]):
            raise ApiError(403, "Chỉ người giao việc hoặc quản lý mới xóa được")
        self.conn.execute("DELETE FROM activity WHERE task_id = ?", (t["id"],))
        self.conn.execute("DELETE FROM notifications WHERE task_id = ?", (t["id"],))
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (t["id"],))
        return {"ok": True}

    def task_activity(self, body, task_id):
        t = row_or_404(self.conn, "tasks", task_id, "công việc")
        rows = self.conn.execute(
            "SELECT a.id, a.kind, a.body, a.created_at, a.user_id, u.name AS user_name FROM activity a"
            " LEFT JOIN users u ON u.id = a.user_id WHERE a.task_id = ? ORDER BY a.id", (t["id"],))
        return {"items": [dict(r) for r in rows]}

    def task_comment(self, body, task_id):
        t = row_or_404(self.conn, "tasks", task_id, "công việc")
        msg = text(body, "body", 2000, True, "nội dung bình luận")
        log(self.conn, t["id"], self.me["id"], "comment", msg)
        for uid in {t["assignee_id"], t["creator_id"]}:
            notify(self.conn, uid, t["id"], f"{self.me['name']} bình luận trong: {t['title']}", self.me["id"])
        return 201, {"ok": True}


# (phương thức, đường dẫn, hàm, cần đăng nhập)
ROUTES = [
    ("GET", r"/api/bootstrap", "bootstrap", False),
    ("POST", r"/api/setup", "setup", False),
    ("POST", r"/api/login", "login", False),
    ("POST", r"/api/logout", "logout", False),
    ("POST", r"/api/me/password", "change_password", True),
    ("GET", r"/api/state", "state", True),
    ("GET", r"/api/export", "export", True),
    ("PATCH", r"/api/settings", "settings_update", True),
    ("GET", r"/api/notifications", "notifications", True),
    ("POST", r"/api/notifications/read", "notifications_read", True),
    ("POST", r"/api/departments", "dept_create", True),
    ("PATCH", r"/api/departments/(\d+)", "dept_update", True),
    ("DELETE", r"/api/departments/(\d+)", "dept_delete", True),
    ("POST", r"/api/users", "user_create", True),
    ("PATCH", r"/api/users/(\d+)", "user_update", True),
    ("DELETE", r"/api/users/(\d+)", "user_deactivate", True),
    ("POST", r"/api/projects", "project_create", True),
    ("PATCH", r"/api/projects/(\d+)", "project_update", True),
    ("DELETE", r"/api/projects/(\d+)", "project_delete", True),
    ("POST", r"/api/tasks", "task_create", True),
    ("PATCH", r"/api/tasks/(\d+)", "task_update", True),
    ("DELETE", r"/api/tasks/(\d+)", "task_delete", True),
    ("GET", r"/api/tasks/(\d+)/activity", "task_activity", True),
    ("POST", r"/api/tasks/(\d+)/comments", "task_comment", True),
]
COMPILED = [(m, re.compile(f"^{p}$"), fn, auth) for m, p, fn, auth in ROUTES]


class App:
    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.login_fails: dict = {}


class Handler(BaseHTTPRequestHandler):
    server_version = "Projeck"
    app: App = None  # gán khi tạo máy chủ

    def log_message(self, fmt, *args):
        if os.environ.get("PROJECK_QUIET"):
            return
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PATCH(self):
        self.dispatch("PATCH")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def session_token(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return cookie[COOKIE].value if COOKIE in cookie else None

    def current_user(self, conn):
        token = self.session_token()
        if not token:
            return None
        return conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token = ? AND s.expires_at > ? AND u.active = 1", (token, now())).fetchone()

    def read_json(self) -> dict:
        ctype = self.headers.get("Content-Type", "")
        if not ctype.startswith("application/json"):
            # Chặn form giả mạo từ trang khác (CSRF): trình duyệt không gửi được JSON chéo trang.
            raise ApiError(415, "Yêu cầu phải dùng JSON")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ApiError(413, "Dữ liệu gửi lên quá lớn")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "JSON không hợp lệ")
        if not isinstance(data, dict):
            raise ApiError(400, "JSON không hợp lệ")
        return data

    def dispatch(self, method):
        self.extra_headers = []
        path = urlparse(self.path).path
        if method == "GET" and path in STATIC:
            return self.send_static(*STATIC[path])
        if not path.startswith("/api/"):
            return self.send_json(404, {"error": "Không tìm thấy"})
        conn = connect(self.app.db_path)
        try:
            for m, pattern, fn, auth in COMPILED:
                match = pattern.match(path)
                if match and m == method:
                    break
            else:
                raise ApiError(404, "Không tìm thấy")
            body = self.read_json() if method != "GET" else {}
            me = self.current_user(conn)
            if auth and not me:
                raise ApiError(401, "Vui lòng đăng nhập")
            result = getattr(Api(self, conn, me), fn)(body, *match.groups())
            conn.commit()
            status, payload = result if isinstance(result, tuple) else (200, result)
            self.send_json(status, payload)
        except ApiError as e:
            conn.rollback()
            self.send_json(e.status, {"error": e.message})
        except Exception:  # noqa: BLE001
            conn.rollback()
            traceback.print_exc()
            self.send_json(500, {"error": "Lỗi máy chủ, xem cửa sổ chạy server.py"})
        finally:
            conn.close()

    def security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                         "frame-ancestors 'none'")
        for k, v in self.extra_headers:
            self.send_header(k, v)

    def send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        self.end_headers()
        self.wfile.write(data)

    def send_static(self, filename, ctype):
        try:
            data = (PUBLIC / filename).read_bytes()
        except OSError:
            return self.send_json(404, {"error": "Thiếu file giao diện " + filename})
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.security_headers()
        self.end_headers()
        self.wfile.write(data)


def make_server(db_path, host="0.0.0.0", port=8080) -> ThreadingHTTPServer:
    init_db(db_path)
    handler = type("BoundHandler", (Handler,), {"app": App(db_path)})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def lan_ip() -> str | None:
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
            s.connect(("10.255.255.255", 1))  # không gửi gói tin, chỉ để biết IP mạng nội bộ
            return s.getsockname()[0]
    except OSError:
        return None


def start_backup_loop(db_path, backup_dir):
    def loop():
        while True:
            try:
                path = backup_db(db_path, backup_dir)
                print(f"[sao lưu] {path}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[sao lưu] LỖI: {e}", flush=True)
            time.sleep(24 * 3600)
    threading.Thread(target=loop, daemon=True).start()


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="Projeck — quản lý dự án & giao việc")
    p.add_argument("command", nargs="?", default="serve", choices=["serve", "reset-password", "backup"])
    p.add_argument("username", nargs="?", help="tên đăng nhập (cho reset-password)")
    p.add_argument("--host", default="0.0.0.0", help="0.0.0.0 = cho máy khác trong mạng truy cập")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--db", help="đường dẫn file dữ liệu (mặc định: %%LOCALAPPDATA%%\\Projeck\\projeck.db)")
    p.add_argument("--backup-dir", default=str(BASE / "backups"), help="thư mục sao lưu (mặc định: ./backups)")
    p.add_argument("--demo", action="store_true", help="chạy thử với dữ liệu mẫu, tách riêng dữ liệu thật")
    p.add_argument("--open", action="store_true", help="tự mở trình duyệt")
    args = p.parse_args(argv)

    db_path = Path(args.db) if args.db else default_data_dir() / ("projeck-demo.db" if args.demo else "projeck.db")
    init_db(db_path)

    if args.command == "reset-password":
        if not args.username:
            p.error("cần tên đăng nhập: python server.py reset-password <tên>")
        pw = getpass.getpass("Mật khẩu mới (tối thiểu 6 ký tự): ")
        if len(pw) < 6:
            print("Mật khẩu quá ngắn.")
            return 1
        with closing(connect(db_path)) as conn:
            cur = conn.execute("UPDATE users SET pw_hash = ?, active = 1 WHERE username = ?",
                               (hash_password(pw), args.username.lower()))
            conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE username = ?)",
                         (args.username.lower(),))
            conn.commit()
        print("Đã đặt lại mật khẩu." if cur.rowcount else "Không có tài khoản này.")
        return 0 if cur.rowcount else 1

    if args.command == "backup":
        print(f"Đã sao lưu: {backup_db(db_path, args.backup_dir)}")
        return 0

    if args.demo:
        with closing(connect(db_path)) as conn:
            seed_demo(conn)
            conn.commit()

    try:
        server = make_server(db_path, args.host, args.port)
    except OSError as e:
        print(f"Không mở được cổng {args.port}: {e}. Thử: python server.py --port 8081")
        return 1
    if not args.demo:
        start_backup_loop(db_path, args.backup_dir)

    url = f"http://localhost:{args.port}"
    print("=" * 64)
    with closing(connect(db_path)) as conn:
        print(f" {company_name(conn).upper()} — Projeck quản lý dự án & giao việc"
              + ("  [DÙNG THỬ]" if args.demo else ""))
    print(f" Máy này mở:          {url}")
    ip = lan_ip()
    if ip and args.host == "0.0.0.0":
        print(f" Máy khác cùng mạng:  http://{ip}:{args.port}")
    print(f" Dữ liệu:             {db_path}")
    if args.demo:
        print(" Tài khoản thử (mật khẩu demo123): ceo (Tổng Giám đốc), pm (Quản lý dự án),")
        print("                                   be (Trưởng Backend), be2 (Nhân viên Backend)")
    else:
        print(f" Sao lưu tự động:     {Path(args.backup_dir).resolve()} (mỗi ngày, giữ {BACKUP_KEEP} bản)")
    print(" Giữ cửa sổ này mở trong giờ làm việc. Nhấn Ctrl+C để dừng.")
    print("=" * 64, flush=True)
    if args.open:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng máy chủ.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
