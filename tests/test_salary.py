import unittest

from job_tracker.salary import meets_salary_floor, parse_salary_text


class SalaryParserTests(unittest.TestCase):
    def test_range_thai(self):
        parsed = parse_salary_text("30,000-45,000 บาท")
        self.assertEqual(parsed.min_thb, 30000)
        self.assertEqual(parsed.max_thb, 45000)
        self.assertTrue(parsed.verified)

    def test_range_english(self):
        parsed = parse_salary_text("THB 50,000 - 65,000")
        self.assertEqual(parsed.min_thb, 50000)
        self.assertEqual(parsed.max_thb, 65000)
        self.assertTrue(parsed.verified)

    def test_unknown(self):
        parsed = parse_salary_text("ตามตกลง")
        self.assertIsNone(parsed.min_thb)
        self.assertIsNone(parsed.max_thb)
        self.assertFalse(parsed.verified)

    def test_meets_floor(self):
        self.assertTrue(meets_salary_floor(30000, 40000, 30000))
        self.assertTrue(meets_salary_floor(None, 32000, 30000))
        self.assertFalse(meets_salary_floor(25000, 28000, 30000))


if __name__ == "__main__":
    unittest.main()
