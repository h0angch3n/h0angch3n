"""HTTP API (JSON) + giao diện web tĩnh, chỉ dùng thư viện chuẩn.

`dispatch()` là hàm thuần (method, path, body, token) -> (status, payload) để kiểm thử
mà không cần mở socket. Mỗi route khai báo quyền cần có:
  "public" — không cần đăng nhập; "auth" — chỉ cần đăng nhập; còn lại là tên quyền.
"""
from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import auth
from .service import DomainError, Service
from .workflow import STATUSES

STATIC_DIR = Path(__file__).parent / "static"

Route = tuple[str, re.Pattern, str, str]
ROUTES: list[Route] = []


def route(method: str, pattern: str, name: str, perm: str) -> None:
    ROUTES.append((method, re.compile(f"^{pattern}$"), name, perm))


# Công khai
route("GET", r"/api/setup-status", "setup_status", "public")
route("POST", r"/api/setup", "setup", "public")
route("POST", r"/api/login", "login", "public")
# Phiên hiện tại
route("POST", r"/api/logout", "logout", "auth")
route("GET", r"/api/me", "me", "auth")
route("POST", r"/api/me/password", "change_password", "auth")
route("GET", r"/api/roles", "roles", "auth")
route("GET", r"/api/statuses", "statuses", "auth")
# Tài khoản (quản trị)
route("GET", r"/api/users", "list_users", "users.manage")
route("POST", r"/api/users", "create_user", "users.manage")
route("POST", r"/api/users/(\d+)", "update_user", "users.manage")
# Quy trình tiến trình mẫu
route("GET", r"/api/process-template", "get_template", "read")
route("PUT", r"/api/process-template", "set_template", "process.write")
# Tổng quan & danh mục
route("GET", r"/api/dashboard", "dashboard", "read")
route("GET", r"/api/customers", "list_customers", "read")
route("POST", r"/api/customers", "add_customer", "customer.write")
route("GET", r"/api/papers", "list_papers", "read")
route("POST", r"/api/papers", "add_paper", "stock.write")
route("POST", r"/api/papers/(\d+)/restock", "restock_paper", "stock.write")
route("GET", r"/api/machines", "list_machines", "read")
route("POST", r"/api/machines", "add_machine", "machine.write")
# Báo giá
route("POST", r"/api/quotes/estimate", "estimate", "read")
route("GET", r"/api/quotes", "list_quotes", "read")
route("POST", r"/api/quotes", "create_quote", "quote.write")
route("POST", r"/api/quotes/(\d+)/accept", "accept_quote", "quote.write")
# Đơn hàng & tiến trình
route("GET", r"/api/jobs", "list_jobs", "read")
route("GET", r"/api/jobs/(\d+)", "get_job", "read")
route("POST", r"/api/jobs/(\d+)/transition", "transition", "job.write")
route("POST", r"/api/jobs/(\d+)/schedule", "schedule", "job.write")
route("POST", r"/api/jobs/(\d+)/steps", "add_step", "job.write")
route("POST", r"/api/jobs/(\d+)/steps/(\d+)", "set_step", "job.step")
route("GET", r"/api/jobs/(\d+)/production", "production_logs", "read")
route("POST", r"/api/jobs/(\d+)/production", "log_production", "job.step")
# Hóa đơn
route("GET", r"/api/invoices", "list_invoices", "read")
route("POST", r"/api/invoices/(\d+)/pay", "pay_invoice", "invoice.pay")


def _need(body: dict, key: str):
    if key not in body:
        raise DomainError(f"Thiếu trường '{key}'")
    return body[key]


def _actor(user: dict | None) -> str:
    if not user:
        return "system"
    return user["full_name"] or user["username"]


def _call(service: Service, name: str, args: list, body: dict, query: dict, user: dict | None):
    actor = _actor(user)
    if name == "setup_status":
        return {"has_users": service.has_users()}
    if name == "setup":
        if service.has_users():
            raise DomainError("Hệ thống đã được khởi tạo; hãy đăng nhập", 409)
        username, password = _need(body, "username"), _need(body, "password")
        service.setup_admin(username, password, body.get("full_name", ""))
        return service.login(username, password)
    if name == "login":
        return service.login(_need(body, "username"), _need(body, "password"))
    if name == "logout":
        service.logout(user and user.get("_token"))
        return {"ok": True}
    if name == "me":
        return user
    if name == "change_password":
        service.change_own_password(user["id"], _need(body, "old_password"),
                                    _need(body, "new_password"))
        return {"ok": True}
    if name == "roles":
        return auth.ROLES
    if name == "statuses":
        return STATUSES
    if name == "list_users":
        return service.list_users()
    if name == "create_user":
        return service.create_user(_need(body, "username"), _need(body, "password"),
                                   body.get("full_name", ""), _need(body, "role"))
    if name == "update_user":
        return service.update_user(
            args[0], role=body.get("role"), active=body.get("active"),
            full_name=body.get("full_name"), password=body.get("password") or None)
    if name == "get_template":
        return service.get_process_template()
    if name == "set_template":
        return service.set_process_template(_need(body, "steps"))
    if name == "dashboard":
        return service.dashboard()
    if name == "list_customers":
        return service.list_customers()
    if name == "add_customer":
        return service.add_customer(_need(body, "name"), body.get("phone", ""), body.get("tax_code", ""))
    if name == "list_papers":
        return service.list_papers()
    if name == "add_paper":
        return service.add_paper(
            _need(body, "name"), float(_need(body, "gsm")),
            float(_need(body, "sheet_w")), float(_need(body, "sheet_h")),
            float(_need(body, "price_per_kg")), float(body.get("stock_kg", 0)))
    if name == "restock_paper":
        return service.restock_paper(args[0], float(_need(body, "kg")))
    if name == "list_machines":
        return service.list_machines()
    if name == "add_machine":
        return service.add_machine(
            _need(body, "name"), float(_need(body, "sheets_per_hour")),
            float(_need(body, "hour_rate")), int(body.get("max_colors", 4)),
            float(body.get("makeready_hours", 0.5)))
    if name == "estimate":
        return service.estimate(body)
    if name == "list_quotes":
        return service.list_quotes()
    if name == "create_quote":
        return service.create_quote(body)
    if name == "accept_quote":
        return service.accept_quote(args[0], actor)
    if name == "list_jobs":
        return service.list_jobs(query.get("status", [None])[0])
    if name == "get_job":
        return service.get_job(args[0])
    if name == "transition":
        return service.transition(args[0], _need(body, "to"), body.get("note", ""), actor)
    if name == "schedule":
        return service.schedule(args[0], int(_need(body, "machine_id")), actor)
    if name == "add_step":
        return service.add_step(args[0], _need(body, "stage"), _need(body, "name"), actor)
    if name == "set_step":
        return service.set_step_done(args[0], args[1], bool(_need(body, "done")), actor)
    if name == "production_logs":
        return service.production_logs(args[0])
    if name == "log_production":
        mid = body.get("machine_id")
        return service.log_production(
            args[0], _need(body, "stage"), _need(body, "good_qty"),
            body.get("scrap_qty", 0), body.get("downtime_min", 0),
            int(mid) if mid not in (None, "") else None,
            body.get("note", ""), actor)
    if name == "list_invoices":
        return service.list_invoices()
    if name == "pay_invoice":
        return service.pay_invoice(args[0], float(_need(body, "amount")), actor)
    raise DomainError("Không hỗ trợ", 404)


def dispatch(service: Service, method: str, raw_path: str, body: dict | None = None,
             token: str | None = None) -> tuple[int, object]:
    url = urlparse(raw_path)
    path = url.path
    query = parse_qs(url.query)
    body = body or {}
    matched_path = False
    for m, pattern, name, perm in ROUTES:
        match = pattern.match(path)
        if not match:
            continue
        matched_path = True
        if m != method:
            continue
        args = [int(g) for g in match.groups()]
        try:
            user = None
            if perm != "public":
                user = service.user_for_token(token)
                if user is None:
                    return 401, {"error": "Cần đăng nhập"}
                if perm != "auth" and not auth.allowed(user["role"], perm):
                    return 403, {"error": "Tài khoản không có quyền thực hiện thao tác này"}
                user = {**user, "_token": token}
            with service.lock:
                return 200, _call(service, name, args, body, query, user)
        except DomainError as exc:
            return exc.code, {"error": str(exc)}
        except (ValueError, TypeError) as exc:
            return 400, {"error": f"Dữ liệu không hợp lệ: {exc}"}
    if matched_path:
        return 405, {"error": "Phương thức không được phép"}
    return 404, {"error": "Không tìm thấy"}


def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "OffsetMES/0.2"

        def log_message(self, fmt, *args):  # giữ log gọn
            return

        def _send(self, status: int, payload: object, ctype: str = "application/json; charset=utf-8"):
            data = payload if isinstance(payload, bytes) else json.dumps(
                payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            if length > 1_000_000:
                raise DomainError("Dữ liệu gửi lên quá lớn", 413)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise DomainError("JSON không hợp lệ")
            if not isinstance(data, dict):
                raise DomainError("Body phải là object JSON")
            return data

        def _token(self) -> str | None:
            header = self.headers.get("Authorization", "")
            return header[7:] if header.startswith("Bearer ") else None

        def _handle(self, method: str):
            path = urlparse(self.path).path
            if method == "GET" and not path.startswith("/api/"):
                return self._static(path)
            try:
                body = self._read_body() if method in ("POST", "PUT") else {}
            except DomainError as exc:
                return self._send(exc.code, {"error": str(exc)})
            status, payload = dispatch(service, method, self.path, body, self._token())
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

        def do_PUT(self):
            self._handle("PUT")

    return Handler


def make_server(service: Service, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(service))


def serve(host: str = "127.0.0.1", port: int = 8000, db_path: str = "offset_mes.db") -> None:
    service = Service(db_path)
    httpd = make_server(service, host, port)
    print(f"Offset MES đang chạy tại http://{host}:{port}  (CSDL: {db_path})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
