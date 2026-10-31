"""Nghiệp vụ xưởng in: khách hàng, kho giấy, máy in, báo giá, đơn hàng, lịch máy, hóa đơn.

Lưu trữ bằng SQLite (thư viện chuẩn). Mọi thao tác đi qua lớp Service để
đảm bảo quy tắc nghiệp vụ (kiểm tra tồn kho, chuyển trạng thái, số màu máy...).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta

from . import calc
from .workflow import STATUSES, TRANSITIONS, InvalidTransition, ensure_transition


class DomainError(Exception):
    """Lỗi nghiệp vụ; server map sang HTTP 400/404/409 tùy `code`."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


SCHEMA = """
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
CREATE TABLE IF NOT EXISTS plate_price (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    price REAL NOT NULL
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
CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    note TEXT,
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


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


class Service:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()
        self.db.execute(
            "INSERT OR IGNORE INTO plate_price (id, price) VALUES (1, 150000)"
        )
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

    # ---- danh mục ------------------------------------------------------
    def add_customer(self, name: str, phone: str = "", tax_code: str = "") -> dict:
        with self.lock:
            if not name:
                raise DomainError("Thiếu tên khách hàng")
            cid = self._write(
                "INSERT INTO customers (name, phone, tax_code) VALUES (?, ?, ?)",
                (name, phone, tax_code),
            )
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
                (name, gsm, sheet_w, sheet_h, price_per_kg, stock_kg),
            )
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
                (name, max_colors, sheets_per_hour, hour_rate, makeready_hours, _iso(_now())),
            )
            return self._one("SELECT * FROM machines WHERE id = ?", (mid,))

    def list_machines(self) -> list[dict]:
        with self.lock:
            return self._all("SELECT * FROM machines ORDER BY id")

    def set_plate_price(self, price: float) -> None:
        with self.lock:
            self._write("UPDATE plate_price SET price = ? WHERE id = 1", (price,))

    # ---- báo giá -------------------------------------------------------
    def _build(self, p: dict) -> tuple[calc.Spec, dict, calc.Rates, dict, dict]:
        """Chuyển tham số thô thành Spec + tài nguyên đã chọn (giấy, máy)."""
        try:
            paper = self._one("SELECT * FROM paper_stock WHERE id = ?", (int(p["paper_id"]),))
            machine_id = p.get("machine_id")
            machine = None
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
                    f"Máy {machine['name']} chỉ in tối đa {machine['max_colors']} màu/mặt"
                )

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
                plate_price=self._one("SELECT price FROM plate_price WHERE id = 1")["price"],
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
                 json.dumps(result), _iso(_now())),
            )
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

    def accept_quote(self, quote_id: int) -> dict:
        """Khách chốt báo giá -> tạo đơn hàng ở trạng thái NEW."""
        with self.lock:
            q = self.get_quote(quote_id)
            if q["status"] != "DRAFT":
                raise DomainError("Báo giá này đã được chốt", 409)
            seq = self._one("SELECT COUNT(*) AS n FROM jobs")["n"] + 1
            now = _iso(_now())
            try:
                self.db.execute("BEGIN")
                cur = self.db.execute(
                    "INSERT INTO jobs (code, quote_id, customer_id, paper_id, status, params,"
                    " result, created_at, updated_at) VALUES (?, ?, ?, ?, 'NEW', ?, ?, ?, ?)",
                    (f"JOB-{seq:05d}", quote_id, q["customer_id"], q["paper_id"],
                     json.dumps(q["params"]), json.dumps(q["result"]), now, now),
                )
                job_id = cur.lastrowid
                self.db.execute(
                    "INSERT INTO job_events (job_id, from_status, to_status, note, at)"
                    " VALUES (?, NULL, 'NEW', 'Khách chốt báo giá', ?)", (job_id, now),
                )
                self.db.execute("UPDATE quotes SET status = 'ACCEPTED' WHERE id = ?", (quote_id,))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return self.get_job(job_id)

    # ---- đơn hàng ------------------------------------------------------
    def _hydrate_job(self, row: dict) -> dict:
        row["params"] = json.loads(row["params"])
        row["result"] = json.loads(row["result"])
        row["paper_issued"] = bool(row["paper_issued"])
        row["allowed_next"] = sorted(TRANSITIONS.get(row["status"], set()))
        return row

    def get_job(self, job_id: int) -> dict:
        with self.lock:
            job = self._hydrate_job(self._one("SELECT * FROM jobs WHERE id = ?", (job_id,)))
            job["events"] = self._all(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,))
            job["invoice"] = _row(self.db.execute(
                "SELECT * FROM invoices WHERE job_id = ?", (job_id,)).fetchone())
            return job

    def list_jobs(self, status: str | None = None) -> list[dict]:
        with self.lock:
            if status:
                rows = self._all("SELECT * FROM jobs WHERE status = ? ORDER BY id DESC", (status,))
            else:
                rows = self._all("SELECT * FROM jobs ORDER BY id DESC")
            return [self._hydrate_job(r) for r in rows]

    def transition(self, job_id: int, target: str, note: str = "") -> dict:
        with self.lock:
            job = self._hydrate_job(self._one("SELECT * FROM jobs WHERE id = ?", (job_id,)))
            try:
                ensure_transition(job["status"], target)
            except InvalidTransition as exc:
                raise DomainError(str(exc), 409) from exc

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
                    "INSERT INTO job_events (job_id, from_status, to_status, note, at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (job_id, job["status"], target, note, now))
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

    def schedule(self, job_id: int, machine_id: int) -> dict:
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
            self.db.execute("BEGIN")
            try:
                self.db.execute(
                    "UPDATE jobs SET machine_id = ?, scheduled_start = ?, scheduled_end = ?,"
                    " updated_at = ? WHERE id = ?",
                    (machine_id, _iso(start), _iso(end), _iso(_now()), job_id))
                self.db.execute(
                    "UPDATE machines SET available_at = ? WHERE id = ?", (_iso(end), machine_id))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return self.get_job(job_id)

    # ---- hóa đơn & công nợ --------------------------------------------
    def pay_invoice(self, invoice_id: int, amount: float) -> dict:
        with self.lock:
            if amount <= 0:
                raise DomainError("Số tiền thanh toán phải lớn hơn 0")
            inv = self._one("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
            paid = min(inv["amount"], inv["paid"] + amount)
            status = "PAID" if paid >= inv["amount"] else "PARTIAL"
            self.db.execute("BEGIN")
            try:
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
                            "INSERT INTO job_events (job_id, from_status, to_status, note, at)"
                            " VALUES (?, 'DELIVERED', 'CLOSED', 'Đã thu đủ tiền', ?)",
                            (job["id"], now))
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
            revenue = self._one(
                "SELECT COALESCE(SUM(amount), 0) AS v FROM invoices")["v"]
            low_stock = self._all(
                "SELECT id, name, stock_kg FROM paper_stock WHERE stock_kg < 50 ORDER BY stock_kg")
            return {
                "jobs_by_status": counts,
                "revenue_invoiced": revenue,
                "receivable": receivable,
                "low_stock_papers": low_stock,
                "machines": self.list_machines(),
            }
