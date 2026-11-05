import unittest

from offset_mes.service import DEFAULT_TEMPLATE, DomainError, Service
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


def finish_stage(svc: Service, job_id: int, actor: str = "tester"):
    """Đánh dấu xong toàn bộ bước của công đoạn hiện tại."""
    job = svc.get_job(job_id)
    for s in job["steps"]:
        if s["stage"] == job["status"] and not s["done"]:
            svc.set_step_done(job_id, s["id"], True, actor)


def advance(svc: Service, job_id: int, to: str, actor: str = "tester"):
    finish_stage(svc, job_id, actor)
    return svc.transition(job_id, to, actor=actor)


class WorkflowRules(unittest.TestCase):
    def test_cannot_skip_stages(self):
        self.assertTrue(can_transition("NEW", "PREPRESS"))
        self.assertFalse(can_transition("NEW", "PRINTING"))
        self.assertTrue(can_transition("QC", "FINISHING"))  # làm lại


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.svc = Service(":memory:")
        self.customer, self.paper, self.machine = seed(self.svc)

    def _new_job(self, **over):
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine, **over))
        return self.svc.accept_quote(quote["id"])

    def _job_through_to_delivery(self):
        jid = self._new_job()["id"]
        advance(self.svc, jid, "PREPRESS")
        self.svc.schedule(jid, self.machine["id"])
        advance(self.svc, jid, "PLATE")
        advance(self.svc, jid, "PRINTING")
        advance(self.svc, jid, "FINISHING")
        advance(self.svc, jid, "QC")
        advance(self.svc, jid, "READY")
        return advance(self.svc, jid, "DELIVERED")

    def test_full_flow_issues_paper_and_invoice_then_closes_on_payment(self):
        stock_before = self.svc.list_papers()[0]["stock_kg"]
        job = self._job_through_to_delivery()

        kg = job["result"]["paper_kg"]
        stock_after = self.svc.list_papers()[0]["stock_kg"]
        self.assertAlmostEqual(stock_before - stock_after, kg, places=3)
        self.assertEqual(job["status"], "DELIVERED")
        self.assertEqual(job["invoice"]["amount"], job["result"]["total"])

        inv = job["invoice"]
        self.svc.pay_invoice(inv["id"], inv["amount"] / 2)
        self.assertEqual(self.svc.get_job(job["id"])["status"], "DELIVERED")
        self.svc.pay_invoice(inv["id"], inv["amount"])
        self.assertEqual(self.svc.get_job(job["id"])["status"], "CLOSED")
        self.assertEqual(self.svc.list_invoices()[0]["status"], "PAID")

    def test_events_record_actor(self):
        jid = self._new_job()["id"]
        advance(self.svc, jid, "PREPRESS", actor="Nguyễn Văn A")
        events = self.svc.get_job(jid)["events"]
        self.assertEqual(events[-1]["actor"], "Nguyễn Văn A")
        self.assertEqual(events[-1]["to_status"], "PREPRESS")

    def test_paper_is_issued_only_once_per_job(self):
        jid = self._new_job()["id"]
        advance(self.svc, jid, "PREPRESS")
        self.svc.schedule(jid, self.machine["id"])
        advance(self.svc, jid, "PLATE")
        advance(self.svc, jid, "PRINTING")
        advance(self.svc, jid, "FINISHING")
        advance(self.svc, jid, "QC")
        self.svc.transition(jid, "FINISHING")  # làm lại, không bị cổng chặn
        advance(self.svc, jid, "QC")
        self.assertTrue(self.svc.get_job(jid)["paper_issued"])

    def test_printing_blocked_without_enough_paper(self):
        small = self.svc.add_paper("Giấy ít", 300, 640, 900, 28000, stock_kg=0.1)
        quote = self.svc.create_quote(quote_params(self.customer, small, self.machine))
        jid = self.svc.accept_quote(quote["id"])["id"]
        advance(self.svc, jid, "PREPRESS")
        self.svc.schedule(jid, self.machine["id"])
        advance(self.svc, jid, "PLATE")
        with self.assertRaises(DomainError) as ctx:
            advance(self.svc, jid, "PRINTING")
        self.assertEqual(ctx.exception.code, 409)
        self.assertEqual(self.svc.get_job(jid)["status"], "PLATE")

    def test_plate_requires_schedule(self):
        jid = self._new_job()["id"]
        advance(self.svc, jid, "PREPRESS")
        with self.assertRaises(DomainError):
            advance(self.svc, jid, "PLATE")

    def test_quote_cannot_be_accepted_twice(self):
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        self.svc.accept_quote(quote["id"])
        with self.assertRaises(DomainError) as ctx:
            self.svc.accept_quote(quote["id"])
        self.assertEqual(ctx.exception.code, 409)

    def test_machine_color_limit(self):
        with self.assertRaises(DomainError):
            self.svc.estimate(quote_params(self.customer, self.paper, self.machine,
                                           colors_front=5, colors_back=0))

    def test_schedule_queues_jobs_on_same_machine(self):
        j1 = self._new_job()
        j2 = self._new_job()
        s1 = self.svc.schedule(j1["id"], self.machine["id"])
        s2 = self.svc.schedule(j2["id"], self.machine["id"])
        self.assertEqual(s2["scheduled_start"], s1["scheduled_end"])


class ProcessChecklistTests(unittest.TestCase):
    def setUp(self):
        self.svc = Service(":memory:")
        self.customer, self.paper, self.machine = seed(self.svc)
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        self.jid = self.svc.accept_quote(quote["id"])["id"]

    def test_job_gets_steps_from_template(self):
        job = self.svc.get_job(self.jid)
        self.assertEqual(len(job["steps"]), len(DEFAULT_TEMPLATE))
        self.assertEqual(job["progress"], {"done": 0, "total": len(DEFAULT_TEMPLATE), "percent": 0})

    def test_gate_blocks_leaving_stage_until_steps_done(self):
        advance(self.svc, self.jid, "PREPRESS")
        self.svc.schedule(self.jid, self.machine["id"])
        with self.assertRaises(DomainError) as ctx:
            self.svc.transition(self.jid, "PLATE")
        self.assertIn("Chưa hoàn thành", str(ctx.exception))
        steps = [s for s in self.svc.get_job(self.jid)["steps"] if s["stage"] == "PREPRESS"]
        for s in steps[:-1]:
            self.svc.set_step_done(self.jid, s["id"], True)
        with self.assertRaises(DomainError):
            self.svc.transition(self.jid, "PLATE")
        self.svc.set_step_done(self.jid, steps[-1]["id"], True, "Thợ B")
        job = self.svc.transition(self.jid, "PLATE")
        self.assertEqual(job["status"], "PLATE")
        done = [s for s in job["steps"] if s["id"] == steps[-1]["id"]][0]
        self.assertEqual(done["done_by"], "Thợ B")
        self.assertIsNotNone(done["done_at"])

    def test_undo_step_and_progress(self):
        advance(self.svc, self.jid, "PREPRESS")
        step = self.svc.get_job(self.jid)["steps"][0]
        job = self.svc.set_step_done(self.jid, step["id"], True)
        self.assertGreater(job["progress"]["done"], 0)
        job = self.svc.set_step_done(self.jid, step["id"], False)
        self.assertEqual(job["progress"]["done"], 0)

    def test_custom_step_added_to_job_and_gates_stage(self):
        advance(self.svc, self.jid, "PREPRESS")
        self.svc.schedule(self.jid, self.machine["id"])
        self.svc.add_step(self.jid, "PLATE", "Đóng dấu logo khách lên bản")
        finish_stage(self.svc, self.jid)  # xong PREPRESS
        self.svc.transition(self.jid, "PLATE")
        # bước mẫu "Xuất và làm bản kẽm" và bước riêng đều chưa xong
        with self.assertRaises(DomainError) as ctx:
            self.svc.transition(self.jid, "PRINTING")
        self.assertIn("Đóng dấu logo", str(ctx.exception))

    def test_template_change_affects_only_new_jobs(self):
        self.svc.set_process_template([{"stage": "PLATE", "name": "Làm bản"}])
        self.assertEqual(len(self.svc.get_job(self.jid)["steps"]), len(DEFAULT_TEMPLATE))
        quote = self.svc.create_quote(quote_params(self.customer, self.paper, self.machine))
        new = self.svc.accept_quote(quote["id"])
        self.assertEqual([s["name"] for s in new["steps"]], ["Làm bản"])

    def test_template_validation(self):
        with self.assertRaises(DomainError):
            self.svc.set_process_template([{"stage": "NOPE", "name": "x"}])
        with self.assertRaises(DomainError):
            self.svc.set_process_template([{"stage": "PLATE", "name": "  "}])
        with self.assertRaises(DomainError):
            self.svc.set_process_template([])

    def test_cancelled_job_steps_are_locked(self):
        self.svc.transition(self.jid, "CANCELLED")
        with self.assertRaises(DomainError):
            self.svc.add_step(self.jid, "PLATE", "trễ")
        with self.assertRaises(DomainError):
            self.svc.set_step_done(self.jid, self.svc.get_job(self.jid)["steps"][0]["id"], True)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.svc = Service(":memory:")
        status, body = dispatch(self.svc, "POST", "/api/setup",
                                {"username": "admin", "password": "matkhau123"})
        assert status == 200, body
        self.admin = body["token"]

    def test_end_to_end_over_api(self):
        t = self.admin
        _, cust = dispatch(self.svc, "POST", "/api/customers", {"name": "Nhà sách X"}, t)
        _, paper = dispatch(self.svc, "POST", "/api/papers", {
            "name": "Ivory 250", "gsm": 250, "sheet_w": 640, "sheet_h": 900,
            "price_per_kg": 30000, "stock_kg": 300}, t)
        _, machine = dispatch(self.svc, "POST", "/api/machines", {
            "name": "Ryobi 524", "sheets_per_hour": 5000, "hour_rate": 400000}, t)

        params = {"customer_id": cust["id"], "paper_id": paper["id"], "machine_id": machine["id"],
                  "piece_w": 210, "piece_h": 297, "quantity": 2000, "colors_front": 4}
        status, est = dispatch(self.svc, "POST", "/api/quotes/estimate", params, t)
        self.assertEqual(status, 200)
        self.assertGreater(est["total"], 0)

        status, quote = dispatch(self.svc, "POST", "/api/quotes", params, t)
        self.assertEqual(status, 200)
        status, job = dispatch(self.svc, "POST", f"/api/quotes/{quote['id']}/accept", None, t)
        self.assertEqual(status, 200)
        jid = job["id"]
        self.assertEqual(job["allowed_next"], ["CANCELLED", "PREPRESS"])

        self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{jid}/transition",
                                  {"to": "PREPRESS"}, t)[0], 200)
        # Chưa xong tiến trình PREPRESS -> bị chặn
        status, err = dispatch(self.svc, "POST", f"/api/jobs/{jid}/transition", {"to": "PLATE"}, t)
        self.assertEqual(status, 409)
        status, job = dispatch(self.svc, "GET", f"/api/jobs/{jid}", None, t)
        for s in job["steps"]:
            if s["stage"] == "PREPRESS":
                self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{jid}/steps/{s['id']}",
                                          {"done": True}, t)[0], 200)
        self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{jid}/schedule",
                                  {"machine_id": machine["id"]}, t)[0], 200)
        self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{jid}/transition",
                                  {"to": "PLATE"}, t)[0], 200)
        self.assertEqual(dispatch(self.svc, "POST", f"/api/jobs/{jid}/transition",
                                  {"to": "PRINTING"}, t)[0], 409)

        status, listed = dispatch(self.svc, "GET", "/api/jobs?status=PLATE", None, t)
        self.assertEqual(status, 200)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["status"], "PLATE")

    def test_errors_are_mapped(self):
        t = self.admin
        self.assertEqual(dispatch(self.svc, "GET", "/api/nope", None, t)[0], 404)
        self.assertEqual(dispatch(self.svc, "DELETE", "/api/jobs", None, t)[0], 405)
        self.assertEqual(dispatch(self.svc, "POST", "/api/customers", {}, t)[0], 400)
        self.assertEqual(dispatch(self.svc, "GET", "/api/jobs/999", None, t)[0], 404)


if __name__ == "__main__":
    unittest.main()
