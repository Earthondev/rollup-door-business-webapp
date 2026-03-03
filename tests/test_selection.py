import unittest

from job_tracker.selection import select_daily_jobs


class SelectionTests(unittest.TestCase):
    def test_fallback_when_known_insufficient(self):
        rows = [
            {
                "job_uid": "A",
                "role_title": "R&D Chemist",
                "keywords_matched": "chemist, data analysis",
                "location": "Bangkok",
                "freshness_days": 1,
                "salary_verified": True,
                "salary_min_thb": 35000,
                "salary_max_thb": 45000,
                "fit_score": 90,
                "data_analysis_exposure": 70,
            },
            {
                "job_uid": "B",
                "role_title": "Laboratory Data Analyst",
                "keywords_matched": "laboratory, data",
                "location": "Bangkok",
                "freshness_days": 2,
                "salary_verified": False,
                "salary_min_thb": None,
                "salary_max_thb": None,
                "fit_score": 88,
                "data_analysis_exposure": 80,
                "notes": "",
            },
        ]

        selected = select_daily_jobs(
            rows,
            target_count=2,
            freshness_days=14,
            salary_floor=30000,
            allow_salary_unknown_fallback=True,
            allowed_locations=["bangkok"],
        )

        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0]["job_uid"], "A")
        self.assertEqual(selected[1]["job_uid"], "B")
        self.assertIn("Fallback", selected[1]["notes"])

    def test_location_filter(self):
        rows = [
            {
                "job_uid": "A",
                "role_title": "R&D Chemist",
                "keywords_matched": "chemist",
                "location": "Chiang Mai",
                "freshness_days": 1,
                "salary_verified": True,
                "salary_min_thb": 35000,
                "salary_max_thb": 45000,
                "fit_score": 90,
                "data_analysis_exposure": 70,
            }
        ]
        selected = select_daily_jobs(
            rows,
            target_count=10,
            freshness_days=14,
            salary_floor=30000,
            allow_salary_unknown_fallback=True,
            allowed_locations=["bangkok"],
        )
        self.assertEqual(selected, [])


if __name__ == "__main__":
    unittest.main()
