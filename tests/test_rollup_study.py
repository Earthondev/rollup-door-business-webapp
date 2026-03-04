import unittest
from unittest.mock import patch

from rollup_door.sheets import build_weekly_review_id, list_study_tasks_by_daily_id, search_study_notes


class RollupStudyTests(unittest.TestCase):
    def test_build_weekly_review_id(self):
        from datetime import date

        self.assertEqual(build_weekly_review_id(date(2026, 3, 4), 9), "WEEK-2026-09")

    @patch("rollup_door.sheets.read_table_rows")
    def test_list_study_tasks_by_daily_id(self, mock_read_table_rows):
        mock_read_table_rows.return_value = [
            {"task_id": "TASK-202603-0001", "daily_id": "DAY-20260304-001"},
            {"task_id": "TASK-202603-0002", "daily_id": "DAY-20260305-001"},
        ]

        items = list_study_tasks_by_daily_id(service=None, spreadsheet_id="sheet", daily_id="DAY-20260304-001")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["task_id"], "TASK-202603-0001")

    @patch("rollup_door.sheets.read_table_rows")
    def test_search_study_notes(self, mock_read_table_rows):
        mock_read_table_rows.side_effect = [
            [
                {
                    "daily_id": "DAY-20260304-001",
                    "log_date": "2026-03-04",
                    "lesson_summary": "วันนี้เจอเคสมอเตอร์ค้าง",
                    "mistakes_or_risks_observed": "ต่อสายช้า",
                    "questions_to_ask": "มอเตอร์ค้างควรเช็กอะไร",
                    "today_goal": "ดูงานซ่อม",
                }
            ],
            [
                {
                    "task_id": "TASK-202603-0001",
                    "daily_id": "DAY-20260304-001",
                    "symptom_or_requirement": "ลูกค้าบอกมอเตอร์ค้าง",
                    "mentor_tip": "ไล่เช็กไฟก่อน",
                    "open_question": "ค่าอะไหล่เท่าไร",
                    "step_notes": "เช็กรีเลย์",
                }
            ],
        ]

        out = search_study_notes(service=None, spreadsheet_id="sheet", query="มอเตอร์ค้าง")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["source"], "study_daily")
        self.assertEqual(out[1]["source"], "study_tasks")


if __name__ == "__main__":
    unittest.main()
