"""HTTP API (JSON) + giao diện web tĩnh, chỉ dùng thư viện chuẩn.

`dispatch()` là hàm thuần (method, path, body) -> (status, payload) để kiểm thử
mà không cần mở socket.
"""
from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .service import DomainError, Service
from .workflow import STATUSES

STATIC_DIR = Path(__file__).parent / "static"

Route = tuple[str, re.Pattern, str]
ROUTES: list[Route] = []


def route(method: str, pattern: str, name: str) -> None:
    ROUTES.append((method, re.compile(f"^{pattern}$"), name))


route("GET", r"/api/statuses", "statuses")
route("GET", r"/api/dashboard", "dashboard")
route("GET", r"/api/customers", "list_customers")
route("POST", r"/api/customers", "add_customer")
route("GET", r"/api/papers", "list_papers")
route("POST", r"/api/papers", "add_paper")
route("POST", r"/api/papers/(\d+)/restock", "restock_paper")
route("GET", r"/api/machines", "list_machines")
route("POST", r"/api/machines", "add_machine")
route("POST", r"/api/quotes/estimate", "estimate")
route("GET", r"/api/quotes", "list_quotes")
route("POST", r"/api/quotes", "create_quote")
route("POST", r"/api/quotes/(\d+)/accept", "accept_quote")
route("GET", r"/api/jobs", "list_jobs")
route("GET", r"/api/jobs/(\d+)", "get_job")
route("POST", r"/api/jobs/(\d+)/transition", "transition")
route("POST", r"/api/jobs/(\d+)/schedule", "schedule")
route("GET", r"/api/invoices", "list_invoices")
route("POST", r"/api/invoices/(\d+)/pay", "pay_invoice")


def _body_get(body: dict, key: str):
    if key not in body:
        raise DomainError(f"Thiếu trường '{key}'")
    return body[key]


def _call(service: Service, name: str, args: list, body: dict, query: dict):
    if name == "statuses":
        return STATUSES
    if name == "dashboard":
        return service.dashboard()
    if name == "list_customers":
        return service.list_customers()
    if name == "add_customer":
        return service.add_customer(_body_get(body, "name"), body.get("phone", ""), body.get("tax_code", ""))
    if name == "list_papers":
        return service.list_papers()
    if name == "add_paper":
        return service.add_paper(
            _body_get(body, "name"), float(_body_get(body, "gsm")),
            float(_body_get(body, "sheet_w")), float(_body_get(body, "sheet_h")),
            float(_body_get(body, "price_per_kg")), float(body.get("stock_kg", 0)))
    if name == "restock_paper":
        return service.restock_paper(args[0], float(_body_get(body, "kg")))
    if name == "list_machines":
        return service.list_machines()
    if name == "add_machine":
        return service.add_machine(
            _body_get(body, "name"), float(_body_get(body, "sheets_per_hour")),
            float(_body_get(body, "hour_rate")), int(body.get("max_colors", 4)),
            float(body.get("makeready_hours", 0.5)))
    if name == "estimate":
        return service.estimate(body)
    if name == "list_quotes":
        return service.list_quotes()
    if name == "create_quote":
        return service.create_quote(body)
    if name == "accept_quote":
        return service.accept_quote(args[0])
    if name == "list_jobs":
        status = query.get("status", [None])[0]
        return service.list_jobs(status)
    if name == "get_job":
        return service.get_job(args[0])
    if name == "transition":
        return service.transition(args[0], _body_get(body, "to"), body.get("note", ""))
    if name == "schedule":
        return service.schedule(args[0], int(_body_get(body, "machine_id")))
    if name == "list_invoices":
        return service.list_invoices()
    if name == "pay_invoice":
        return service.pay_invoice(args[0], float(_body_get(body, "amount")))
    raise DomainError("Không hỗ trợ", 404)


def dispatch(service: Service, method: str, raw_path: str, body: dict | None = None) -> tuple[int, object]:
    url = urlparse(raw_path)
    path = url.path
    query = parse_qs(url.query)
    body = body or {}
    matched_path = False
    for m, pattern, name in ROUTES:
        match = pattern.match(path)
        if not match:
            continue
        matched_path = True
        if m != method:
            continue
        args = [int(g) for g in match.groups()]
        try:
            with service.lock:
                return 200, _call(service, name, args, body, query)
        except DomainError as exc:
            return exc.code, {"error": str(exc)}
        except (ValueError, TypeError) as exc:
            return 400, {"error": f"Dữ liệu không hợp lệ: {exc}"}
    if matched_path:
        return 405, {"error": "Phương thức không được phép"}
    return 404, {"error": "Không tìm thấy"}


def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "OffsetMES/0.1"

        def log_message(self, fmt, *args):  # giữ log gọn
            return

        def _send(self, status: int, payload: object, ctype: str = "application/json; charset=utf-8"):
            data = payload if isinstance(payload, bytes) else json.dumps(
                payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise DomainError("JSON không hợp lệ")
            if not isinstance(data, dict):
                raise DomainError("Body phải là object JSON")
            return data

        def _handle(self, method: str):
            path = urlparse(self.path).path
            if method == "GET" and not path.startswith("/api/"):
                return self._static(path)
            try:
                body = self._read_body() if method in ("POST", "PUT") else {}
            except DomainError as exc:
                return self._send(exc.code, {"error": str(exc)})
            status, payload = dispatch(service, method, self.path, body)
            self._send(status, payload)

        def _static(self, path: str):
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            target = (STATIC_DIR / rel).resolve()
            if STATIC_DIR.resolve() not in target.parents or not target.is_file():
                return self._send(404, {"error": "Không tìm thấy"})
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), ctype)

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000, db_path: str = "offset_mes.db") -> None:
    service = Service(db_path)
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    print(f"Offset MES đang chạy tại http://{host}:{port}  (CSDL: {db_path})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
