"""Kiểm thử máy chủ Projeck: chạy `python -m unittest discover -s tests -v` trong thư mục company-projeck."""
import http.cookiejar
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["PROJECK_QUIET"] = "1"
import server  # noqa: E402


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, content_type="application/json"):
        data = None if method == "GET" else json.dumps(body or {}).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", content_type)
        try:
            with self.opener.open(req) as res:
                raw = res.read()
                return res.status, (json.loads(raw) if raw and path.startswith("/api/") else raw)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, raw

    def ok(self, method, path, body=None, expect=(200, 201)):
        status, data = self.call(method, path, body)
        if status not in expect:
            raise AssertionError(f"{method} {path} -> {status} {data}")
        return data


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        self.srv = server.make_server(self.db, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.admin = Client(self.base)
        self.admin.ok("POST", "/api/setup", {"name": "Tổng GĐ", "username": "Boss", "password": "secret1",
                                             "company": "Công ty Cổ phần Dịch vụ Dev"})
        st = self.admin.ok("GET", "/api/state")
        self.dept = {d["name"]: d["id"] for d in st["departments"]}

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def make_user(self, username, role, dept):
        uid = self.admin.ok("POST", "/api/users", {"username": username, "name": username.upper(), "password": "pass123",
                                                   "role": role, "dept_id": self.dept[dept]})["id"]
        c = Client(self.base)
        c.ok("POST", "/api/login", {"username": username, "password": "pass123"})
        return uid, c

    def project(self):
        return self.admin.ok("POST", "/api/projects", {"name": "Dự án A"})["id"]

    # ------------------------------------------------------------------
    def test_setup_creates_company_structure_and_rollout_plan(self):
        st = self.admin.ok("GET", "/api/state")
        self.assertEqual(st["company"], "Công ty Cổ phần Dịch vụ Dev")
        self.assertEqual(st["me"]["username"], "boss")
        self.assertEqual(st["me"]["role"], "admin")
        for name in ("Hội đồng quản trị", "Ban Kiểm soát", "Ban Tổng Giám đốc", "Pháp chế – Hợp đồng"):
            self.assertIn(name, self.dept)
        self.assertEqual(len(st["departments"]), len(server.DEPARTMENTS))
        self.assertEqual(st["projects"][0]["name"], "Triển khai Projeck tại công ty")
        self.assertEqual(len(st["tasks"]), len(server.ROLLOUT_TASKS))
        status, _ = Client(self.base).call("POST", "/api/setup", {"name": "X", "username": "xx1", "password": "123456"})
        self.assertEqual(status, 403)

    def test_login_errors_and_lockout(self):
        c = Client(self.base)
        self.assertEqual(c.call("GET", "/api/state")[0], 401)
        for _ in range(5):
            self.assertEqual(c.call("POST", "/api/login", {"username": "boss", "password": "sai"})[0], 401)
        self.assertEqual(c.call("POST", "/api/login", {"username": "boss", "password": "secret1"})[0], 429)

    def test_csrf_requires_json(self):
        status, _ = self.admin.call("POST", "/api/departments", {"name": "X"}, content_type="text/plain")
        self.assertEqual(status, 415)

    def test_assignment_permissions_and_review_flow(self):
        pid = self.project()
        lead_id, lead = self.make_user("lead.be", "lead", "Phát triển Backend")
        staff_id, staff = self.make_user("dev.be", "staff", "Phát triển Backend")
        other_id, other = self.make_user("dev.fe", "staff", "Phát triển Frontend")

        # Nhân viên không được tạo dự án; trưởng bộ phận không giao ra ngoài bộ phận.
        self.assertEqual(staff.call("POST", "/api/projects", {"name": "X"})[0], 403)
        self.assertEqual(lead.call("POST", "/api/tasks", {"project_id": pid, "title": "x", "assignee_id": other_id})[0], 403)
        tid = lead.ok("POST", "/api/tasks", {"project_id": pid, "title": "API thanh toán",
                                             "assignee_id": staff_id, "priority": "high", "due": "2030-01-01"})["id"]
        notes = staff.ok("GET", "/api/notifications")["items"]
        self.assertIn("giao cho bạn", notes[0]["body"])

        # Nhân viên tự ghi nhận việc thì tự động giao cho chính mình; không giao cho người khác.
        own = staff.ok("POST", "/api/tasks", {"project_id": pid, "title": "Tự học Docker"})["id"]
        self.assertEqual(next(t for t in staff.ok("GET", "/api/state")["tasks"] if t["id"] == own)["assignee_id"], staff_id)
        self.assertEqual(staff.call("POST", "/api/tasks", {"project_id": pid, "title": "x", "assignee_id": other_id})[0], 403)

        # Nhân viên chỉ đổi trạng thái việc được giao, không tự đánh dấu hoàn thành.
        self.assertEqual(staff.call("PATCH", f"/api/tasks/{tid}", {"title": "đổi"})[0], 403)
        self.assertEqual(staff.call("PATCH", f"/api/tasks/{tid}", {"status": "done"})[0], 403)
        staff.ok("PATCH", f"/api/tasks/{tid}", {"status": "doing"})
        staff.ok("PATCH", f"/api/tasks/{tid}", {"status": "review"})
        self.assertIn("gửi duyệt", lead.ok("GET", "/api/notifications")["items"][0]["body"])
        self.assertEqual(other.call("PATCH", f"/api/tasks/{tid}", {"status": "doing"})[0], 403)

        # Trưởng bộ phận duyệt hoàn thành → nhân viên nhận thông báo.
        lead.ok("PATCH", f"/api/tasks/{tid}", {"status": "done"})
        self.assertIn("duyệt hoàn thành", staff.ok("GET", "/api/notifications")["items"][0]["body"])

        staff.ok("POST", f"/api/tasks/{tid}/comments", {"body": "Đã xong, nhờ anh kiểm tra"})
        acts = staff.ok("GET", f"/api/tasks/{tid}/activity")["items"]
        self.assertEqual([a["kind"] for a in acts].count("comment"), 1)
        self.assertTrue(any("Chờ duyệt → Hoàn thành" in a["body"] for a in acts))

        # Chỉ người giao hoặc quản lý mới xóa được việc.
        self.assertEqual(staff.call("DELETE", f"/api/tasks/{tid}")[0], 403)
        lead.ok("DELETE", f"/api/tasks/{tid}")

    def test_deactivate_user_unassigns_open_tasks(self):
        pid = self.project()
        uid, user = self.make_user("nghi.viec", "staff", "Kiểm thử (QA/QC)")
        tid = self.admin.ok("POST", "/api/tasks", {"project_id": pid, "title": "Test", "assignee_id": uid})["id"]
        self.admin.ok("DELETE", f"/api/users/{uid}")
        st = self.admin.ok("GET", "/api/state")
        self.assertIsNone(next(t for t in st["tasks"] if t["id"] == tid)["assignee_id"])
        self.assertEqual(user.call("GET", "/api/state")[0], 401)
        self.assertEqual(Client(self.base).call("POST", "/api/login", {"username": "nghi.viec", "password": "pass123"})[0], 401)
        self.assertEqual(self.admin.call("POST", "/api/tasks", {"project_id": pid, "title": "x", "assignee_id": uid})[0], 400)

    def test_admin_only_structure_and_company_name(self):
        _, pm = self.make_user("pm1", "pm", "Quản lý dự án (PMO)")
        self.assertEqual(pm.call("POST", "/api/departments", {"name": "X"})[0], 403)
        self.assertEqual(pm.call("PATCH", "/api/settings", {"company": "X"})[0], 403)
        self.admin.ok("PATCH", "/api/settings", {"company": "CTCP Dịch vụ Dev"})
        self.assertEqual(pm.ok("GET", "/api/state")["company"], "CTCP Dịch vụ Dev")
        status, data = self.admin.call("PATCH", "/api/users/1", {"role": "staff"})
        self.assertEqual(status, 400)

    def test_static_files_and_no_path_traversal(self):
        c = Client(self.base)
        status, body = c.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Projeck".encode(), body)
        self.assertEqual(c.call("GET", "/../server.py")[0], 404)
        self.assertEqual(c.call("GET", "/server.py")[0], 404)

    def test_backup_and_demo_seed(self):
        out = server.backup_db(self.db, Path(self.tmp.name) / "bk", keep=2)
        self.assertTrue(out.exists())
        demo_db = Path(self.tmp.name) / "demo.db"
        server.init_db(demo_db)
        with server.closing(server.connect(demo_db)) as conn:
            server.seed_demo(conn)
            conn.commit()
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 10)


if __name__ == "__main__":
    unittest.main()
