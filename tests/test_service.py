import unittest

from offset_mes.service import DomainError, Service
from offset_mes.server import dispatch
from offset_mes.workflow import can_transition


def seed(svc: Service):
    customer = svc.add_customer("Công ty ABC", "0900000000", "0312345678")
    paper = svc.add_paper("Couche 300gsm", 300, 640, 900, 28000, stock_kg=500)
    machine = svc.add_machine("Heidelberg SM74", 6000, 450000, max_colors=4)
    return customer, paper, machine


def quote_params(customer, paper, machine, **over):
    p = {
        "customer_id": customer["id"], "paper_id": paper["id"], "machine_id": machine["id"],
        "piece_w": 90, "piece_h": 54, "quantity": 1000,
        "colors_front": 4, "colors_back": 4, "margin_pct": 25,
    }
    p.update(over)
    return p


class WorkflowRules(unittest.TestCase):
    def test_cannot_skip_stages(self):
        self.assertTrue(can_transition("NEW", "PREPRESS"))
        self.assertFalse(can_transition("NEW", "PRINTING"))
        self.assertTrue(can_transition("QC", "FINISHING"))  # làm lại


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.svc = Service(":memory:")
        self.customer, self.paper, self.machine = seed(self.svc)

    def _job_through_to_delivery(self, quote):
        job = self.svc.accept_quote(quote["id"])
        jid = job["id"]
        self.svc.transition(jid, "PREPRESS")
        self.svc.schedule(jid, self.machine["id"])
        self.svc.transition(jid, "PLATE")
        self.svc.transition(jid, "PRINTING")
        self.svc.transition(jid, "FINISHING")
        self.svc.transition(jid, "QC")
        self.svc.transition(jid, "READY")
        return self.svc.transition(jid, "DELIVERED")

    def test_full_flow_issues_paper_and_invoice_then_closes_on_payment(self):
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        stock_before = self.svc.list_papers()[0]["stock_kg"]
        job = self._job_through_to_delivery(quote)

        kg = job["result"]["paper_kg"]
        stock_after = self.svc.list_papers()[0]["stock_kg"]
        self.assertAlmostEqual(stock_before - stock_after, kg, places=3)
        self.assertEqual(job["status"], "DELIVERED")
        self.assertIsNotNone(job["invoice"])
        self.assertEqual(job["invoice"]["amount"], job["result"]["total"])

        inv = job["invoice"]
        self.svc.pay_invoice(inv["id"], inv["amount"] / 2)
        self.assertEqual(self.svc.get_job(job["id"])["status"], "DELIVERED")
        self.svc.pay_invoice(inv["id"], inv["amount"])
        closed = self.svc.get_job(job["id"])
        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(self.svc.list_invoices()[0]["status"], "PAID")

    def test_paper_is_issued_only_once_per_job(self):
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        job = self.svc.accept_quote(quote["id"])
        self.svc.transition(job["id"], "PREPRESS")
        self.svc.schedule(job["id"], self.machine["id"])
        self.svc.transition(job["id"], "PLATE")
        self.svc.transition(job["id"], "PRINTING")
        self.svc.transition(job["id"], "FINISHING")
        self.svc.transition(job["id"], "QC")
        self.svc.transition(job["id"], "FINISHING")  # làm lại sau QC
        self.svc.transition(job["id"], "QC")
        self.assertTrue(self.svc.get_job(job["id"])["paper_issued"])

    def test_printing_blocked_without_enough_paper(self):
        small = self.svc.add_paper("Giấy ít", 300, 640, 900, 28000, stock_kg=0.1)
        quote = self.svc.create_quote(quote_params(self.customer, small, self.machine))
        job = self.svc.accept_quote(quote["id"])
        self.svc.transition(job["id"], "PREPRESS")
        self.svc.schedule(job["id"], self.machine["id"])
        self.svc.transition(job["id"], "PLATE")
        with self.assertRaises(DomainError) as ctx:
            self.svc.transition(job["id"], "PRINTING")
        self.assertEqual(ctx.exception.code, 409)
        # trạng thái không đổi khi lỗi
        self.assertEqual(self.svc.get_job(job["id"])["status"], "PLATE")

    def test_plate_requires_schedule(self):
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        job = self.svc.accept_quote(quote["id"])
        self.svc.transition(job["id"], "PREPRESS")
        with self.assertRaises(DomainError):
            self.svc.transition(job["id"], "PLATE")

    def test_quote_cannot_be_accepted_twice(self):
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        self.svc.accept_quote(quote["id"])
        with self.assertRaises(DomainError) as ctx:
            self.svc.accept_quote(quote["id"])
        self.assertEqual(ctx.exception.code, 409)

    def test_machine_color_limit(self):
        quote_params_ok = quote_params(self.customer, self.paper, self.machine)
        with self.assertRaises(DomainError):
            self.svc.estimate({**quote_params_ok, "colors_front": 5, "colors_back": 0})

    def test_schedule_queues_jobs_on_same_machine(self):
        q1 = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        q2 = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        j1 = self.svc.accept_quote(q1["id"])
        j2 = self.svc.accept_quote(q2["id"])
        s1 = self.svc.schedule(j1["id"], self.machine["id"])
        s2 = self.svc.schedule(j2["id"], self.machine["id"])
        self.assertEqual(s2["scheduled_start"], s1["scheduled_end"])


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.svc = Service(":memory:")

    def test_end_to_end_over_api(self):
        status, cust = dispatch(self.svc, "POST", "/api/customers", {"name": "Nhà sách X"})
        self.assertEqual(status, 200)
        status, paper = dispatch(self.svc, "POST", "/api/papers", {
            "name": "Ivory 250", "gsm": 250, "sheet_w": 640, "sheet_h": 900,
            "price_per_kg": 30000, "stock_kg": 300})
        self.assertEqual(status, 200)
        status, machine = dispatch(self.svc, "POST", "/api/machines", {
            "name": "Ryobi 524", "sheets_per_hour": 5000, "hour_rate": 400000})
        self.assertEqual(status, 200)

        params = {"customer_id": cust["id"], "paper_id": paper["id"], "machine_id": machine["id"],
                  "piece_w": 210, "piece_h": 297, "quantity": 2000, "colors_front": 4}
        status, est = dispatch(self.svc, "POST", "/api/quotes/estimate", params)
        self.assertEqual(status, 200)
        self.assertGreater(est["total"], 0)

        status, quote = dispatch(self.svc, "POST", "/api/quotes", params)
        self.assertEqual(status, 200)
        status, job = dispatch(self.svc, "POST", f"/api/quotes/{quote['id']}/accept")
        self.assertEqual(status, 200)
        jid = job["id"]
        self.assertEqual(job["allowed_next"], ["CANCELLED", "PREPRESS"])

        self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{jid}/transition", {"to": "PREPRESS"})[0], 200)
        self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{jid}/schedule", {"machine_id": machine["id"]})[0], 200)
        self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{jid}/transition", {"to": "PRINTING"})[0], 409)

        status, listed = dispatch(self.svc, "GET", "/api/jobs?status=PREPRESS")
        self.assertEqual(status, 200)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["status"], "PREPRESS")

    def test_errors_are_mapped(self):
        self.assertEqual(dispatch(self.svc, "GET", "/api/nope")[0], 404)
        self.assertEqual(dispatch(self.svc, "DELETE", "/api/jobs")[0], 405)
        self.assertEqual(dispatch(self.svc, "POST", "/api/customers", {})[0], 400)
        self.assertEqual(dispatch(self.svc, "GET", "/api/jobs/999")[0], 404)


if __name__ == "__main__":
    unittest.main()
