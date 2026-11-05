"""Nghiệp vụ xưởng in: người dùng, khách hàng, kho giấy, máy in, báo giá, đơn hàng,
tiến trình sản xuất (checklist theo công đoạn), lịch máy, hóa đơn.

Lưu trữ bằng SQLite (thư viện chuẩn). Quy tắc nghiệp vụ nằm ở đây; phân quyền
theo vai trò được kiểm tra ở lớp API (server.py).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta

from . import auth, calc
from .workflow import STATUSES, TRANSITIONS, InvalidTransition, ensure_transition

# Công đoạn mặc định: (trạng thái đơn chứa bước, tên bước). Có thể sửa trong Quy trình.
DEFAULT_TEMPLATE: list[tuple[str, str]] = [
    ("PREPRESS", "Kiểm tra file & chốt proof với khách"),
    ("PREPRESS", "Xếp khung in (imposition)"),
    ("PLATE", "Xuất và làm bản kẽm"),
    ("PRINTING", "Chạy thử & căn màu"),
    ("PRINTING", "In hàng loạt"),
    ("FINISHING", "Cắt / bế"),
    ("FINISHING", "Gấp / đóng quyển / cán màng"),
    ("QC", "Kiểm tra chất lượng theo mẫu duyệt"),
    ("READY", "Đóng gói, dán nhãn"),
]
TEMPLATE_STAGES = [s for s in STATUSES if s not in ("NEW", "CLOSED", "CANCELLED")]
# Chuyển ngược để làm lại: không bị cổng tiến trình chặn.
REWORK_TRANSITIONS = {("QC", "FINISHING")}
TERMINAL = {"CLOSED", "CANCELLED"}


class DomainError(Exception):
    """Lỗi nghiệp vụ; server map sang HTTP 400/401/403/404/409."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    tax_code TEXT
);
CREATE TABLE IF NOT EXISTS paper_stock (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    gsm REAL NOT NULL,
    sheet_w REAL NOT NULL,
    sheet_h REAL NOT NULL,
    price_per_kg REAL NOT NULL,
    stock_kg REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    max_colors INTEGER NOT NULL,
    sheets_per_hour REAL NOT NULL,
    hour_rate REAL NOT NULL,
    makeready_hours REAL NOT NULL DEFAULT 0.5,
    available_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS process_template (
    seq INTEGER PRIMARY KEY,
    stage TEXT NOT NULL,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    paper_id INTEGER NOT NULL REFERENCES paper_stock(id),
    params TEXT NOT NULL,
    result TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    quote_id INTEGER NOT NULL REFERENCES quotes(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    paper_id INTEGER NOT NULL REFERENCES paper_stock(id),
    status TEXT NOT NULL,
    params TEXT NOT NULL,
    result TEXT NOT NULL,
    machine_id INTEGER REFERENCES machines(id),
    scheduled_start TEXT,
    scheduled_end TEXT,
    paper_issued INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_steps (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    seq INTEGER NOT NULL,
    stage TEXT NOT NULL,
    name TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    done_by TEXT,
    done_at TEXT
);
CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    note TEXT,
    actor TEXT,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_logs (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    stage TEXT NOT NULL,
    machine_id INTEGER REFERENCES machines(id),
    good_qty INTEGER NOT NULL DEFAULT 0,
    scrap_qty INTEGER NOT NULL DEFAULT 0,
    downtime_min INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    actor TEXT,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id),
    number TEXT NOT NULL UNIQUE,
    amount REAL NOT NULL,
    paid REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    issued_at TEXT NOT NULL
);
"""

INK_MAX_DEFAULT = 4


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class Service:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()
        self.sessions = auth.Sessions()
        self.db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('plate_price', '150000')")
        if self.db.execute("SELECT COUNT(*) FROM process_template").fetchone()[0] == 0:
            self.db.executemany(
                "INSERT INTO process_template (seq, stage, name) VALUES (?, ?, ?)",
                [(i + 1, s, n) for i, (s, n) in enumerate(DEFAULT_TEMPLATE)])
        self.db.commit()

    # ---- helpers -------------------------------------------------------
    def _one(self, sql: str, args=()) -> dict:
        row = self.db.execute(sql, args).fetchone()
        if row is None:
            raise DomainError("Không tìm thấy bản ghi", 404)
        return dict(row)

    def _all(self, sql: str, args=()) -> list[dict]:
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def _write(self, sql: str, args=()) -> int:
        cur = self.db.execute(sql, args)
        self.db.commit()
        return cur.lastrowid

    def _plate_price(self) -> float:
        return float(self._one("SELECT value FROM settings WHERE key = 'plate_price'")["value"])

    # ---- tài khoản & đăng nhập -----------------------------------------
    def has_users(self) -> bool:
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0

    def setup_admin(self, username: str, password: str, full_name: str = "") -> dict:
        """Tạo tài khoản quản trị đầu tiên. Chỉ hoạt động khi chưa có người dùng nào."""
        with self.lock:
            if self.has_users():
                raise DomainError("Hệ thống đã được khởi tạo; hãy đăng nhập", 409)
            return self.create_user(username, password, full_name, "ADMIN")

    def create_user(self, username: str, password: str, full_name: str, role: str) -> dict:
        with self.lock:
            try:
                auth.validate_username(username)
                auth.validate_password(password)
            except ValueError as exc:
                raise DomainError(str(exc)) from exc
            if role not in auth.ROLES:
                raise DomainError("Vai trò không hợp lệ")
            exists = self.db.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            if exists:
                raise DomainError("Tên đăng nhập đã tồn tại", 409)
            uid = self._write(
                "INSERT INTO users (username, password_hash, full_name, role, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (username, auth.hash_password(password), full_name, role, _iso(_now())))
            return self.get_user(uid)

    def get_user(self, user_id: int) -> dict:
        with self.lock:
            row = self._one(
                "SELECT id, username, full_name, role, active, created_at FROM users WHERE id = ?",
                (user_id,))
            row["active"] = bool(row["active"])
            return row

    def list_users(self) -> list[dict]:
        with self.lock:
            rows = self._all(
                "SELECT id, username, full_name, role, active, created_at FROM users ORDER BY id")
            for r in rows:
                r["active"] = bool(r["active"])
            return rows

    def update_user(self, user_id: int, role: str | None = None, active: bool | None = None,
                    full_name: str | None = None, password: str | None = None) -> dict:
        with self.lock:
            user = self.get_user(user_id)
            if role is not None and role not in auth.ROLES:
                raise DomainError("Vai trò không hợp lệ")
            new_role = role or user["role"]
            new_active = user["active"] if active is None else bool(active)
            if user["role"] == "ADMIN" and (new_role != "ADMIN" or not new_active):
                if self._active_admin_count() <= 1:
                    raise DomainError("Phải còn ít nhất một quản trị viên đang hoạt động", 409)
            if role is not None:
                self._write("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            if active is not None:
                self._write("UPDATE users SET active = ? WHERE id = ?", (int(new_active), user_id))
            if full_name is not None:
                self._write("UPDATE users SET full_name = ? WHERE id = ?", (full_name, user_id))
            if password:
                try:
                    auth.validate_password(password)
                except ValueError as exc:
                    raise DomainError(str(exc)) from exc
                self._write("UPDATE users SET password_hash = ? WHERE id = ?",
                            (auth.hash_password(password), user_id))
            if active is False or password:
                self.sessions.revoke_user(user_id)
            return self.get_user(user_id)

    def _active_admin_count(self) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND active = 1").fetchone()[0]

    def login(self, username: str, password: str) -> dict:
        with self.lock:
            row = self.db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            ok = row is not None and bool(row["active"]) and auth.verify_password(
                password, row["password_hash"])
            if not ok:
                raise DomainError("Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đã khóa", 401)
            return {"token": self.sessions.create(row["id"]), "user": self.get_user(row["id"])}

    def logout(self, token: str | None) -> None:
        with self.lock:
            self.sessions.revoke(token)

    def user_for_token(self, token: str | None) -> dict | None:
        with self.lock:
            uid = self.sessions.user_id(token)
            if uid is None:
                return None
            try:
                user = self.get_user(uid)
            except DomainError:
                return None
            return user if user["active"] else None

    def change_own_password(self, user_id: int, old: str, new: str) -> None:
        with self.lock:
            row = self._one("SELECT password_hash FROM users WHERE id = ?", (user_id,))
            if not auth.verify_password(old, row["password_hash"]):
                raise DomainError("Mật khẩu hiện tại không đúng", 400)
            self.update_user(user_id, password=new)

    # ---- danh mục ------------------------------------------------------
    def add_customer(self, name: str, phone: str = "", tax_code: str = "") -> dict:
        with self.lock:
            if not name:
                raise DomainError("Thiếu tên khách hàng")
            cid = self._write(
                "INSERT INTO customers (name, phone, tax_code) VALUES (?, ?, ?)",
                (name, phone, tax_code))
            return self._one("SELECT * FROM customers WHERE id = ?", (cid,))

    def list_customers(self) -> list[dict]:
        with self.lock:
            return self._all("SELECT * FROM customers ORDER BY name")

    def add_paper(self, name: str, gsm: float, sheet_w: float, sheet_h: float,
                  price_per_kg: float, stock_kg: float = 0) -> dict:
        with self.lock:
            if gsm <= 0 or sheet_w <= 0 or sheet_h <= 0 or price_per_kg < 0:
                raise DomainError("Thông số giấy không hợp lệ")
            pid = self._write(
                "INSERT INTO paper_stock (name, gsm, sheet_w, sheet_h, price_per_kg, stock_kg)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, gsm, sheet_w, sheet_h, price_per_kg, stock_kg))
            return self._one("SELECT * FROM paper_stock WHERE id = ?", (pid,))

    def restock_paper(self, paper_id: int, kg: float) -> dict:
        with self.lock:
            if kg <= 0:
                raise DomainError("Số kg nhập kho phải lớn hơn 0")
            self._one("SELECT id FROM paper_stock WHERE id = ?", (paper_id,))
            self._write("UPDATE paper_stock SET stock_kg = stock_kg + ? WHERE id = ?", (kg, paper_id))
            return self._one("SELECT * FROM paper_stock WHERE id = ?", (paper_id,))

    def list_papers(self) -> list[dict]:
        with self.lock:
            return self._all("SELECT * FROM paper_stock ORDER BY name")

    def add_machine(self, name: str, sheets_per_hour: float, hour_rate: float,
                    max_colors: int = INK_MAX_DEFAULT, makeready_hours: float = 0.5) -> dict:
        with self.lock:
            if sheets_per_hour <= 0 or max_colors <= 0:
                raise DomainError("Thông số máy không hợp lệ")
            mid = self._write(
                "INSERT INTO machines (name, max_colors, sheets_per_hour, hour_rate,"
                " makeready_hours, available_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, max_colors, sheets_per_hour, hour_rate, makeready_hours, _iso(_now())))
            return self._one("SELECT * FROM machines WHERE id = ?", (mid,))

    def list_machines(self) -> list[dict]:
        with self.lock:
            return self._all("SELECT * FROM machines ORDER BY id")

    def set_plate_price(self, price: float) -> None:
        with self.lock:
            self._write("INSERT OR REPLACE INTO settings (key, value) VALUES ('plate_price', ?)",
                        (str(price),))

    # ---- quy trình tiến trình (mẫu) -----------------------------------
    def get_process_template(self) -> list[dict]:
        with self.lock:
            return self._all("SELECT stage, name FROM process_template ORDER BY seq")

    def set_process_template(self, steps: list[dict]) -> list[dict]:
        """Thay toàn bộ mẫu tiến trình. Chỉ áp dụng cho đơn tạo sau này."""
        with self.lock:
            if not isinstance(steps, list) or not steps:
                raise DomainError("Mẫu tiến trình phải có ít nhất một bước")
            clean = []
            for s in steps:
                stage = str(s.get("stage", ""))
                name = str(s.get("name", "")).strip()
                if stage not in TEMPLATE_STAGES:
                    raise DomainError(f"Công đoạn không hợp lệ: {stage}")
                if not name:
                    raise DomainError("Tên bước không được để trống")
                clean.append((stage, name))
            self.db.execute("BEGIN")
            try:
                self.db.execute("DELETE FROM process_template")
                self.db.executemany(
                    "INSERT INTO process_template (seq, stage, name) VALUES (?, ?, ?)",
                    [(i + 1, st, nm) for i, (st, nm) in enumerate(clean)])
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return self.get_process_template()

    # ---- báo giá -------------------------------------------------------
    def _build(self, p: dict) -> tuple[calc.Spec, dict, calc.Rates, dict, dict]:
        """Chuyển tham số thô thành Spec + tài nguyên đã chọn (giấy, máy)."""
        try:
            paper = self._one("SELECT * FROM paper_stock WHERE id = ?", (int(p["paper_id"]),))
            machine_id = p.get("machine_id")
            if machine_id:
                machine = self._one("SELECT * FROM machines WHERE id = ?", (int(machine_id),))
            else:
                machines = self._all("SELECT * FROM machines ORDER BY sheets_per_hour DESC")
                machine = machines[0] if machines else None
            if machine is None:
                raise DomainError("Chưa có máy in nào trong hệ thống")

            front = int(p.get("colors_front", 4))
            back = int(p.get("colors_back", 0))
            if max(front, back) > machine["max_colors"]:
                raise DomainError(
                    f"Máy {machine['name']} chỉ in tối đa {machine['max_colors']} màu/mặt")

            spec = calc.Spec(
                quantity=int(p["quantity"]),
                piece=calc.Size(float(p["piece_w"]), float(p["piece_h"])),
                sheet=calc.Size(paper["sheet_w"], paper["sheet_h"]),
                gsm=paper["gsm"],
                colors_front=front,
                colors_back=back,
                finishing_per_piece=float(p.get("finishing_per_piece", 0)),
                spoilage_pct=float(p.get("spoilage_pct", calc.DEFAULT_SPOILAGE_PCT)),
                margin_pct=float(p.get("margin_pct", calc.DEFAULT_MARGIN_PCT)),
            )
            rates = calc.Rates(
                paper_per_kg=paper["price_per_kg"],
                plate_price=self._plate_price(),
                press_hour_rate=machine["hour_rate"],
                press_sheets_per_hour=machine["sheets_per_hour"],
                makeready_hours=machine["makeready_hours"],
            )
            return spec, paper, rates, machine, {"front": front, "back": back}
        except (KeyError, TypeError, ValueError) as exc:
            raise DomainError(f"Tham số không hợp lệ: {exc}") from exc

    def estimate(self, params: dict) -> dict:
        """Tính báo giá nhưng không lưu."""
        with self.lock:
            spec, paper, rates, machine, _ = self._build(params)
            try:
                result = calc.estimate(spec, rates)
            except ValueError as exc:
                raise DomainError(str(exc)) from exc
            result["paper"] = paper["name"]
            result["machine"] = machine["name"]
            return result

    def create_quote(self, params: dict) -> dict:
        with self.lock:
            customer_id = int(params["customer_id"])
            self._one("SELECT id FROM customers WHERE id = ?", (customer_id,))
            result = self.estimate(params)
            qid = self._write(
                "INSERT INTO quotes (customer_id, paper_id, params, result, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (customer_id, int(params["paper_id"]), json.dumps(params),
                 json.dumps(result), _iso(_now())))
            return self.get_quote(qid)

    def get_quote(self, quote_id: int) -> dict:
        with self.lock:
            q = self._one("SELECT * FROM quotes WHERE id = ?", (quote_id,))
            q["params"] = json.loads(q["params"])
            q["result"] = json.loads(q["result"])
            return q

    def list_quotes(self) -> list[dict]:
        with self.lock:
            rows = self._all("SELECT id FROM quotes ORDER BY id DESC")
            return [self.get_quote(r["id"]) for r in rows]

    def accept_quote(self, quote_id: int, actor: str = "system") -> dict:
        """Khách chốt báo giá -> tạo đơn NEW kèm bảng tiến trình theo mẫu hiện hành."""
        with self.lock:
            q = self.get_quote(quote_id)
            if q["status"] != "DRAFT":
                raise DomainError("Báo giá này đã được chốt", 409)
            seq = self._one("SELECT COUNT(*) AS n FROM jobs")["n"] + 1
            template = self._all("SELECT stage, name FROM process_template ORDER BY seq")
            now = _iso(_now())
            try:
                self.db.execute("BEGIN")
                cur = self.db.execute(
                    "INSERT INTO jobs (code, quote_id, customer_id, paper_id, status, params,"
                    " result, created_at, updated_at) VALUES (?, ?, ?, ?, 'NEW', ?, ?, ?, ?)",
                    (f"JOB-{seq:05d}", quote_id, q["customer_id"], q["paper_id"],
                     json.dumps(q["params"]), json.dumps(q["result"]), now, now))
                job_id = cur.lastrowid
                self.db.executemany(
                    "INSERT INTO job_steps (job_id, seq, stage, name) VALUES (?, ?, ?, ?)",
                    [(job_id, i + 1, t["stage"], t["name"]) for i, t in enumerate(template)])
                self.db.execute(
                    "INSERT INTO job_events (job_id, from_status, to_status, note, actor, at)"
                    " VALUES (?, NULL, 'NEW', 'Khách chốt báo giá', ?, ?)", (job_id, actor, now))
                self.db.execute("UPDATE quotes SET status = 'ACCEPTED' WHERE id = ?", (quote_id,))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return self.get_job(job_id)

    # ---- đơn hàng & tiến trình ----------------------------------------
    def _hydrate_job(self, row: dict) -> dict:
        row["params"] = json.loads(row["params"])
        row["result"] = json.loads(row["result"])
        row["paper_issued"] = bool(row["paper_issued"])
        row["allowed_next"] = sorted(TRANSITIONS.get(row["status"], set()))
        return row

    def _steps(self, job_id: int) -> list[dict]:
        rows = self._all("SELECT * FROM job_steps WHERE job_id = ? ORDER BY seq, id", (job_id,))
        for r in rows:
            r["done"] = bool(r["done"])
        return rows

    @staticmethod
    def _progress(steps: list[dict]) -> dict:
        total = len(steps)
        done = sum(1 for s in steps if s["done"])
        return {"done": done, "total": total,
                "percent": round(100 * done / total) if total else 100}

    def get_job(self, job_id: int) -> dict:
        with self.lock:
            job = self._hydrate_job(self._one("SELECT * FROM jobs WHERE id = ?", (job_id,)))
            job["steps"] = self._steps(job_id)
            job["progress"] = self._progress(job["steps"])
            job["output"] = self.output_summary(job)
            job["events"] = self._all(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,))
            job["invoice"] = self.db.execute(
                "SELECT * FROM invoices WHERE job_id = ?", (job_id,)).fetchone()
            job["invoice"] = dict(job["invoice"]) if job["invoice"] else None
            return job

    def list_jobs(self, status: str | None = None) -> list[dict]:
        with self.lock:
            if status:
                rows = self._all("SELECT * FROM jobs WHERE status = ? ORDER BY id DESC", (status,))
            else:
                rows = self._all("SELECT * FROM jobs ORDER BY id DESC")
            out = []
            for r in rows:
                job = self._hydrate_job(r)
                job["progress"] = self._progress(self._steps(job["id"]))
                out.append(job)
            return out

    def _ensure_open(self, job: dict) -> None:
        if job["status"] in TERMINAL:
            raise DomainError("Đơn đã đóng hoặc đã hủy", 409)

    def add_step(self, job_id: int, stage: str, name: str, actor: str = "system") -> dict:
        """Thêm bước riêng cho một đơn (ví dụ yêu cầu đặc biệt của khách)."""
        with self.lock:
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            self._ensure_open(job)
            if stage not in TEMPLATE_STAGES:
                raise DomainError(f"Công đoạn không hợp lệ: {stage}")
            name = (name or "").strip()
            if not name:
                raise DomainError("Tên bước không được để trống")
            seq = self._one(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM job_steps WHERE job_id = ?",
                (job_id,))["n"]
            self._write("INSERT INTO job_steps (job_id, seq, stage, name) VALUES (?, ?, ?, ?)",
                        (job_id, seq, stage, name))
            self._event(job_id, job["status"], job["status"], f"Thêm bước: {name}", actor)
            self.db.commit()
            return self.get_job(job_id)

    def set_step_done(self, job_id: int, step_id: int, done: bool, actor: str = "system") -> dict:
        """Đánh dấu hoàn thành / bỏ hoàn thành một bước (có lưu người và thời điểm)."""
        with self.lock:
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            self._ensure_open(job)
            step = self._one("SELECT * FROM job_steps WHERE id = ? AND job_id = ?",
                             (step_id, job_id))
            now = _iso(_now())
            self._write(
                "UPDATE job_steps SET done = ?, done_by = ?, done_at = ? WHERE id = ?",
                (int(bool(done)), actor if done else None, now if done else None, step_id))
            verb = "Hoàn thành" if done else "Bỏ đánh dấu"
            self._event(job_id, job["status"], job["status"], f"{verb} bước: {step['name']}", actor)
            self.db.commit()
            return self.get_job(job_id)

    def _pending_steps(self, job_id: int, stage: str) -> list[dict]:
        return [s for s in self._steps(job_id) if s["stage"] == stage and not s["done"]]

    def _event(self, job_id: int, frm: str | None, to: str, note: str, actor: str) -> None:
        self.db.execute(
            "INSERT INTO job_events (job_id, from_status, to_status, note, actor, at)"
            " VALUES (?, ?, ?, ?, ?, ?)", (job_id, frm, to, note, actor, _iso(_now())))

    def transition(self, job_id: int, target: str, note: str = "", actor: str = "system") -> dict:
        with self.lock:
            job = self._hydrate_job(self._one("SELECT * FROM jobs WHERE id = ?", (job_id,)))
            try:
                ensure_transition(job["status"], target)
            except InvalidTransition as exc:
                raise DomainError(str(exc), 409) from exc

            if (job["status"], target) not in REWORK_TRANSITIONS:
                pending = self._pending_steps(job_id, job["status"])
                if pending:
                    names = "; ".join(s["name"] for s in pending)
                    raise DomainError(f"Chưa hoàn thành tiến trình {job['status']}: {names}", 409)

            now = _iso(_now())
            try:
                self.db.execute("BEGIN")
                if target == "PRINTING":
                    self._issue_paper(job)
                if target == "PLATE" and job["machine_id"] is None:
                    raise DomainError("Cần xếp lịch máy trước khi làm bản", 409)
                self.db.execute(
                    "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                    (target, now, job_id))
                self.db.execute(
                    "INSERT INTO job_events (job_id, from_status, to_status, note, actor, at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (job_id, job["status"], target, note, actor, now))
                if target == "DELIVERED":
                    self._issue_invoice(job_id, job["result"]["total"], now)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return self.get_job(job_id)

    def _issue_paper(self, job: dict) -> None:
        """Xuất giấy khỏi kho khi bắt đầu in (chỉ một lần)."""
        if job["paper_issued"]:
            return
        need = job["result"]["paper_kg"]
        paper = self._one("SELECT * FROM paper_stock WHERE id = ?", (job["paper_id"],))
        if paper["stock_kg"] < need:
            raise DomainError(
                f"Không đủ giấy {paper['name']}: cần {need} kg, còn {paper['stock_kg']} kg", 409)
        self.db.execute(
            "UPDATE paper_stock SET stock_kg = stock_kg - ? WHERE id = ?", (need, paper["id"]))
        self.db.execute("UPDATE jobs SET paper_issued = 1 WHERE id = ?", (job["id"],))

    def _issue_invoice(self, job_id: int, amount: float, now: str) -> None:
        number = f"HD-{_now().strftime('%Y%m%d')}-{job_id:05d}"
        self.db.execute(
            "INSERT INTO invoices (job_id, number, amount, paid, status, issued_at)"
            " VALUES (?, ?, ?, 0, 'UNPAID', ?)", (job_id, number, amount, now))

    def schedule(self, job_id: int, machine_id: int, actor: str = "system") -> dict:
        """Xếp đơn vào hàng đợi máy (lập lịch hữu hạn công suất)."""
        with self.lock:
            job = self._hydrate_job(self._one("SELECT * FROM jobs WHERE id = ?", (job_id,)))
            if job["status"] not in ("NEW", "PREPRESS", "PLATE"):
                raise DomainError("Chỉ xếp lịch cho đơn chưa in", 409)
            machine = self._one("SELECT * FROM machines WHERE id = ?", (machine_id,))
            ink = max(int(job["params"].get("colors_front", 4)),
                      int(job["params"].get("colors_back", 0)))
            if ink > machine["max_colors"]:
                raise DomainError(f"Máy {machine['name']} không đủ số màu", 409)

            hours = job["result"]["press_hours"]
            start = max(_now(), datetime.fromisoformat(machine["available_at"]))
            end = start + timedelta(hours=hours)
            try:
                self.db.execute("BEGIN")
                self.db.execute(
                    "UPDATE jobs SET machine_id = ?, scheduled_start = ?, scheduled_end = ?,"
                    " updated_at = ? WHERE id = ?",
                    (machine_id, _iso(start), _iso(end), _iso(_now()), job_id))
                self.db.execute(
                    "UPDATE machines SET available_at = ? WHERE id = ?", (_iso(end), machine_id))
                self._event(job_id, job["status"], job["status"],
                            f"Xếp lịch máy {machine['name']}", actor)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return self.get_job(job_id)

    # ---- sản lượng thực tế ---------------------------------------------
    def log_production(self, job_id: int, stage: str, good_qty: int, scrap_qty: int = 0,
                       downtime_min: int = 0, machine_id: int | None = None,
                       note: str = "", actor: str = "system") -> dict:
        """Ghi nhận sản lượng đạt, phế phẩm, thời gian dừng máy của một công đoạn."""
        with self.lock:
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            self._ensure_open(job)
            if stage not in TEMPLATE_STAGES:
                raise DomainError(f"Công đoạn không hợp lệ: {stage}")
            try:
                good, scrap, down = int(good_qty), int(scrap_qty), int(downtime_min)
            except (TypeError, ValueError) as exc:
                raise DomainError("Số lượng phải là số nguyên") from exc
            if good < 0 or scrap < 0 or down < 0 or (good == 0 and scrap == 0 and down == 0):
                raise DomainError("Số liệu phải ≥ 0 và phải có ít nhất một giá trị khác 0")
            if machine_id is not None:
                self._one("SELECT id FROM machines WHERE id = ?", (int(machine_id),))
            now = _iso(_now())
            self._write(
                "INSERT INTO production_logs (job_id, stage, machine_id, good_qty, scrap_qty,"
                " downtime_min, note, actor, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, stage, machine_id, good, scrap, down, note, actor, now))
            return self.get_job(job_id)

    def production_logs(self, job_id: int) -> list[dict]:
        with self.lock:
            self._one("SELECT id FROM jobs WHERE id = ?", (job_id,))
            return self._all(
                "SELECT l.*, m.name AS machine_name FROM production_logs l"
                " LEFT JOIN machines m ON m.id = l.machine_id"
                " WHERE l.job_id = ? ORDER BY l.id", (job_id,))

    def output_summary(self, job: dict) -> dict:
        """Tổng hợp sản lượng so với kế hoạch (số lượng đặt và định mức phế phẩm)."""
        row = self._one(
            "SELECT COALESCE(SUM(good_qty), 0) AS good, COALESCE(SUM(scrap_qty), 0) AS scrap,"
            " COALESCE(SUM(downtime_min), 0) AS downtime FROM production_logs WHERE job_id = ?",
            (job["id"],))
        planned = int(job["params"]["quantity"])
        good, scrap = int(row["good"]), int(row["scrap"])
        planned_waste = job["result"]["waste_sheets"]
        return {
            "planned_qty": planned,
            "good_qty": good,
            "scrap_qty": scrap,
            "remaining_qty": max(0, planned - good),
            "percent": round(100 * min(good, planned) / planned) if planned else 100,
            "scrap_pct": round(100 * scrap / (good + scrap), 2) if good + scrap else 0.0,
            "planned_waste_sheets": planned_waste,
            "downtime_min": int(row["downtime"]),
        }

    # ---- hóa đơn & công nợ --------------------------------------------
    def pay_invoice(self, invoice_id: int, amount: float, actor: str = "system") -> dict:
        with self.lock:
            if amount <= 0:
                raise DomainError("Số tiền thanh toán phải lớn hơn 0")
            inv = self._one("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
            paid = min(inv["amount"], inv["paid"] + amount)
            status = "PAID" if paid >= inv["amount"] else "PARTIAL"
            try:
                self.db.execute("BEGIN")
                self.db.execute(
                    "UPDATE invoices SET paid = ?, status = ? WHERE id = ?",
                    (paid, status, invoice_id))
                if status == "PAID":
                    job = self._one("SELECT * FROM jobs WHERE id = ?", (inv["job_id"],))
                    if job["status"] == "DELIVERED":
                        now = _iso(_now())
                        self.db.execute(
                            "UPDATE jobs SET status = 'CLOSED', updated_at = ? WHERE id = ?",
                            (now, job["id"]))
                        self.db.execute(
                            "INSERT INTO job_events (job_id, from_status, to_status, note, actor, at)"
                            " VALUES (?, 'DELIVERED', 'CLOSED', 'Đã thu đủ tiền', ?, ?)",
                            (job["id"], actor, now))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return self._one("SELECT * FROM invoices WHERE id = ?", (invoice_id,))

    def list_invoices(self) -> list[dict]:
        with self.lock:
            return self._all("SELECT * FROM invoices ORDER BY id DESC")

    # ---- tổng quan -----------------------------------------------------
    def dashboard(self) -> dict:
        with self.lock:
            counts = {s: 0 for s in STATUSES}
            for r in self._all("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"):
                counts[r["status"]] = r["n"]
            receivable = self._one(
                "SELECT COALESCE(SUM(amount - paid), 0) AS v FROM invoices WHERE status != 'PAID'")["v"]
            revenue = self._one("SELECT COALESCE(SUM(amount), 0) AS v FROM invoices")["v"]
            low_stock = self._all(
                "SELECT id, name, stock_kg FROM paper_stock WHERE stock_kg < 50 ORDER BY stock_kg")
            return {
                "jobs_by_status": counts,
                "revenue_invoiced": revenue,
                "receivable": receivable,
                "low_stock_papers": low_stock,
                "machines": self.list_machines(),
            }
