import unittest

from offset_mes import auth
from offset_mes.server import dispatch
from offset_mes.service import DomainError, Service


class PasswordTests(unittest.TestCase):
    def test_hash_and_verify(self):
        stored = auth.hash_password("matkhau-dai")
        self.assertTrue(auth.verify_password("matkhau-dai", stored))
        self.assertFalse(auth.verify_password("sai", stored))
        self.assertNotIn("matkhau-dai", stored)

    def test_malformed_hash_is_rejected(self):
        self.assertFalse(auth.verify_password("x", "plaintext"))

    def test_role_permissions(self):
        self.assertTrue(auth.allowed("ADMIN", "users.manage"))
        self.assertTrue(auth.allowed("ADMIN", "process.write"))
        self.assertFalse(auth.allowed("MANAGER", "users.manage"))
        self.assertFalse(auth.allowed("MANAGER", "process.write"))
        self.assertTrue(auth.allowed("ACCOUNTANT", "invoice.pay"))
        self.assertFalse(auth.allowed("SALES", "invoice.pay"))
        self.assertFalse(auth.allowed("OPERATOR", "quote.write"))
        self.assertFalse(auth.allowed("UNKNOWN", "read"))


class SetupAndLoginTests(unittest.TestCase):
    def setUp(self):
        self.svc = Service(":memory:")

    def test_setup_only_once(self):
        self.assertFalse(self.svc.has_users())
        self.svc.setup_admin("admin", "matkhau123")
        self.assertTrue(self.svc.has_users())
        with self.assertRaises(DomainError) as ctx:
            self.svc.setup_admin("admin2", "matkhau123")
        self.assertEqual(ctx.exception.code, 409)

    def test_custom_admin_name_and_login(self):
        self.svc.setup_admin("giamdoc.lan", "matkhau123", "Lan")
        result = self.svc.login("giamdoc.lan", "matkhau123")
        self.assertEqual(result["user"]["role"], "ADMIN")
        self.assertEqual(result["user"]["full_name"], "Lan")
        self.assertIsNotNone(self.svc.user_for_token(result["token"]))

    def test_wrong_password_and_logout(self):
        self.svc.setup_admin("admin", "matkhau123")
        with self.assertRaises(DomainError) as ctx:
            self.svc.login("admin", "sai-mat-khau")
        self.assertEqual(ctx.exception.code, 401)
        token = self.svc.login("admin", "matkhau123")["token"]
        self.svc.logout(token)
        self.assertIsNone(self.svc.user_for_token(token))

    def test_weak_input_rejected(self):
        with self.assertRaises(DomainError):
            self.svc.setup_admin("ab", "matkhau123")
        with self.assertRaises(DomainError):
            self.svc.setup_admin("admin", "123")

    def test_last_admin_cannot_be_demoted_or_locked(self):
        admin = self.svc.setup_admin("admin", "matkhau123")
        with self.assertRaises(DomainError):
            self.svc.update_user(admin["id"], role="MANAGER")
        with self.assertRaises(DomainError):
            self.svc.update_user(admin["id"], active=False)
        second = self.svc.create_user("admin2", "matkhau123", "", "ADMIN")
        self.svc.update_user(admin["id"], role="MANAGER")  # còn admin khác nên được phép
        self.assertEqual(self.svc.get_user(second["id"])["role"], "ADMIN")

    def test_deactivated_user_loses_session(self):
        self.svc.setup_admin("admin", "matkhau123")
        op = self.svc.create_user("tho1", "matkhau123", "Thợ 1", "OPERATOR")
        token = self.svc.login("tho1", "matkhau123")["token"]
        self.assertIsNotNone(self.svc.user_for_token(token))
        self.svc.update_user(op["id"], active=False)
        self.assertIsNone(self.svc.user_for_token(token))
        with self.assertRaises(DomainError):
            self.svc.login("tho1", "matkhau123")

    def test_change_own_password(self):
        admin = self.svc.setup_admin("admin", "matkhau123")
        with self.assertRaises(DomainError):
            self.svc.change_own_password(admin["id"], "sai-mat-khau", "moi-mat-khau")
        self.svc.change_own_password(admin["id"], "matkhau123", "moi-mat-khau")
        self.svc.login("admin", "moi-mat-khau")
        with self.assertRaises(DomainError):
            self.svc.login("admin", "matkhau123")


class ApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.svc = Service(":memory:")
        status, body = dispatch(self.svc, "POST", "/api/setup",
                                {"username": "admin", "password": "matkhau123"})
        self.assertEqual(status, 200)
        self.admin_token = body["token"]

    def _login_as(self, username, role):
        dispatch(self.svc, "POST", "/api/users",
                 {"username": username, "password": "matkhau123", "role": role}, self.admin_token)
        status, body = dispatch(self.svc, "POST", "/api/login",
                                {"username": username, "password": "matkhau123"})
        self.assertEqual(status, 200)
        return body["token"]

    def test_protected_routes_need_token(self):
        self.assertEqual(dispatch(self.svc, "GET", "/api/dashboard")[0], 401)
        self.assertEqual(dispatch(self.svc, "GET", "/api/dashboard", None, "bad-token")[0], 401)
        self.assertEqual(dispatch(self.svc, "GET", "/api/dashboard", None, self.admin_token)[0], 200)

    def test_setup_is_closed_after_first_admin(self):
        status, _ = dispatch(self.svc, "POST", "/api/setup",
                             {"username": "hacker", "password": "matkhau123"})
        self.assertEqual(status, 409)
        self.assertEqual(dispatch(self.svc, "GET", "/api/setup-status")[1], {"has_users": True})

    def test_only_admin_manages_users(self):
        manager = self._login_as("quanly", "MANAGER")
        status, _ = dispatch(self.svc, "GET", "/api/users", None, manager)
        self.assertEqual(status, 403)
        status, body = dispatch(self.svc, "GET", "/api/users", None, self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(len(body), 2)

    def test_manager_cannot_edit_process_template_but_admin_can(self):
        manager = self._login_as("quanly", "MANAGER")
        steps = [{"stage": "PLATE", "name": "Làm bản"}]
        self.assertEqual(dispatch(self.svc, "PUT", "/api/process-template", {"steps": steps}, manager)[0], 403)
        self.assertEqual(dispatch(self.svc, "PUT", "/api/process-template", {"steps": steps},
                                  self.admin_token)[0], 200)

    def test_accountant_pays_but_sales_cannot(self):
        sales = self._login_as("sales1", "SALES")
        accountant = self._login_as("ketoan", "ACCOUNTANT")
        self.assertEqual(dispatch(self.svc, "POST", "/api/invoices/1/pay", {"amount": 1}, sales)[0], 403)
        # kế toán được phép: không có hóa đơn nên trả 404 (đã qua bước kiểm quyền)
        self.assertEqual(dispatch(self.svc, "POST", "/api/invoices/1/pay", {"amount": 1}, accountant)[0], 404)

    def test_user_can_change_password_via_api(self):
        status, _ = dispatch(self.svc, "POST", "/api/me/password",
                             {"old_password": "matkhau123", "new_password": "moi-mat-khau"},
                             self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(dispatch(self.svc, "POST", "/api/login",
                                  {"username": "admin", "password": "moi-mat-khau"})[0], 200)


if __name__ == "__main__":
    unittest.main()
