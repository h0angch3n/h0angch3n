import unittest

from offset_mes import calc
from offset_mes.calc import Rates, Size, Spec


class UpsTests(unittest.TestCase):
    def test_business_card_on_sra3_like_sheet(self):
        # 90x54 mm + bleed 3 mm -> 96x60 ; khổ 640x900 có mép kẹp 10 mm, khe 3 mm
        # chiều gốc 96x60: cols = floor((640-10+3)/(96+3)) = 6, rows = floor(903/63) = 14 -> 84
        # chiều xoay 60x96: cols = floor(633/63) = 10, rows = floor(903/99) = 9 -> 90 (chọn)
        self.assertEqual(calc.ups(Size(640, 900), Size(90, 54)), 90)

    def test_rotation_is_considered(self):
        # khổ 400x200, thành phẩm 190x90 (+bleed 196x96):
        # không xoay: 1 cột x 2 hàng = 2 ; xoay 96x196: 3 cột x 1 hàng = 3
        self.assertEqual(calc.ups(Size(400, 200), Size(190, 90)), 3)

    def test_piece_too_big_raises(self):
        with self.assertRaises(ValueError):
            calc.ups(Size(100, 100), Size(500, 500))


class EstimateTests(unittest.TestCase):
    def setUp(self):
        self.rates = Rates(
            paper_per_kg=28000,
            plate_price=150000,
            press_hour_rate=450000,
            press_sheets_per_hour=6000,
            makeready_hours=0.5,
        )

    def test_sheet_counts_include_waste_and_makeready(self):
        spec = Spec(quantity=1000, piece=Size(90, 54), sheet=Size(640, 900), gsm=300,
                    colors_front=4, colors_back=0, spoilage_pct=3.0)
        r = calc.estimate(spec, self.rates)
        self.assertEqual(r["ups"], 90)
        self.assertEqual(r["run_sheets"], 12)          # ceil(1000/90)
        self.assertEqual(r["waste_sheets"], 1)         # ceil(12*3%)
        self.assertEqual(r["makeready_sheets"], 80)    # 20 * 4 màu
        self.assertEqual(r["total_sheets"], 93)

    def test_total_is_cost_plus_margin_plus_vat(self):
        spec = Spec(quantity=1000, piece=Size(90, 54), sheet=Size(640, 900), gsm=300,
                    colors_front=4, colors_back=4, margin_pct=25)
        r = calc.estimate(spec, self.rates)
        expected_price = r["cost"]["total"] * 1.25
        self.assertAlmostEqual(r["subtotal"], expected_price, delta=1)
        self.assertAlmostEqual(r["total"], expected_price * 1.10, delta=2)
        self.assertEqual(r["unit_price"], round(r["total"] / 1000))

    def test_finishing_scales_with_quantity(self):
        base = Spec(quantity=500, piece=Size(90, 54), sheet=Size(640, 900), gsm=300)
        with_fin = Spec(quantity=500, piece=Size(90, 54), sheet=Size(640, 900), gsm=300,
                        finishing_per_piece=200)
        a = calc.estimate(base, self.rates)["cost"]["finishing"]
        b = calc.estimate(with_fin, self.rates)["cost"]["finishing"]
        self.assertEqual(a, 0)
        self.assertEqual(b, 100000)

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            calc.estimate(Spec(quantity=0, piece=Size(90, 54), sheet=Size(640, 900), gsm=300),
                          self.rates)


if __name__ == "__main__":
    unittest.main()
