import unittest

from offset_mes.server import dispatch
from offset_mes.service import DomainError, Service
from tests.test_service import advance, quote_params, seed


class ProductionLogTests(unittest.TestCase):
    def setUp(self):
        self.svc = Service(":memory:")
        self.customer, self.paper, self.machine = seed(self.svc)
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine,
                                                   quantity=1000))
        self.job = self.svc.accept_quote(quote["id"])
        self.jid = self.job["id"]

    def test_empty_output_summary(self):
        out = self.svc.get_job(self.jid)["output"]
        self.assertEqual(out["planned_qty"], 1000)
        self.assertEqual(out["good_qty"], 0)
        self.assertEqual(out["remaining_qty"], 1000)
        self.assertEqual(out["percent"], 0)

    def test_logs_accumulate_and_track_scrap(self):
        advance(self.svc, self.jid, "PREPRESS")
        self.svc.schedule(self.jid, self.machine["id"])
        advance(self.svc, self.jid, "PLATE")
        self.svc.log_production(self.jid, "PRINTING", 600, scrap_qty=20, downtime_min=15,
                                machine_id=self.machine["id"], actor="Thợ 1")
        job = self.svc.log_production(self.jid, "PRINTING", 300, scrap_qty=10, actor="Thợ 2")
        out = job["output"]
        self.assertEqual(out["good_qty"], 900)
        self.assertEqual(out["scrap_qty"], 30)
        self.assertEqual(out["remaining_qty"], 100)
        self.assertEqual(out["percent"], 90)
        self.assertEqual(out["downtime_min"], 15)
        self.assertAlmostEqual(out["scrap_pct"], round(100 * 30 / 930, 2))
        logs = self.svc.production_logs(self.jid)
        self.assertEqual([l["actor"] for l in logs], ["Thợ 1", "Thợ 2"])
        self.assertEqual(logs[0]["machine_name"], self.machine["name"])

    def test_remaining_never_negative_and_percent_capped(self):
        job = self.svc.log_production(self.jid, "PRINTING", 1200)
        self.assertEqual(job["output"]["remaining_qty"], 0)
        self.assertEqual(job["output"]["percent"], 100)

    def test_invalid_input_rejected(self):
        with self.assertRaises(DomainError):
            self.svc.log_production(self.jid, "PRINTING", -1)
        with self.assertRaises(DomainError):
            self.svc.log_production(self.jid, "PRINTING", 0, 0, 0)
        with self.assertRaises(DomainError):
            self.svc.log_production(self.jid, "PRINTING", "abc")
        with self.assertRaises(DomainError):
            self.svc.log_production(self.jid, "NOPE", 10)

    def test_closed_job_rejects_logs(self):
        self.svc.transition(self.jid, "CANCELLED")
        with self.assertRaises(DomainError):
            self.svc.log_production(self.jid, "PRINTING", 10)

    def test_api_route_and_permission(self):
        status, operator = dispatch(self.svc, "POST", "/api/users",
                                    {"username": "tho1", "password": "matkhau123",
                                     "role": "OPERATOR"}, None)
        self.assertEqual(status, 401)  # chưa đăng nhập
        self.svc.setup_admin("admin", "matkhau123")
        admin = self.svc.login("admin", "matkhau123")["token"]
        self.svc.create_user("tho1", "matkhau123", "Thợ 1", "OPERATOR")
        op = self.svc.login("tho1", "matkhau123")["token"]
        self.svc.create_user("ketoan", "matkhau123", "", "ACCOUNTANT")
        acc = self.svc.login("ketoan", "matkhau123")["token"]

        body = {"stage": "PRINTING", "good_qty": 50, "scrap_qty": 2}
        status, res = dispatch(self.svc, "POST", f"/api/jobs/{self.jid}/production", body, op)
        self.assertEqual(status, 200)
        self.assertEqual(res["output"]["good_qty"], 50)
        self.assertEqual(res["output"]["scrap_qty"], 2)
        self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{self.jid}/production",
                                  body, acc)[0], 403)
        status, logs = dispatch(self.svc, "GET", f"/api/jobs/{self.jid}/production", None, admin)
        self.assertEqual(status, 200)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["actor"], "Thợ 1")


if __name__ == "__main__":
    unittest.main()
