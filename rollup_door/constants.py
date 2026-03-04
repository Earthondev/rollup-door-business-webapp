from __future__ import annotations

CASES_HEADERS = [
    "case_id",
    "created_at",
    "creator_name",
    "district",
    "job_type",
    "site_type",
    "width_mm",
    "height_mm",
    "usage_per_day",
    "motor_type",
    "urgent_flag",
    "risk_level",
    "target_margin_pct",
    "material_cost",
    "labor_cost",
    "travel_cost",
    "risk_buffer_cost",
    "warranty_buffer_cost",
    "direct_cost",
    "suggested_price",
    "final_price",
    "gross_profit",
    "gross_margin_pct",
    "status",
    "notes",
]

PRICING_REFERENCE_HEADERS = [
    "item_code",
    "item_name",
    "unit",
    "cost_per_unit",
    "updated_at",
    "source_note",
]

KNOWLEDGE_HEADERS = [
    "topic",
    "question",
    "answer",
    "tags",
    "severity",
    "last_reviewed_at",
]

CALCULATOR_LOG_HEADERS = [
    "calc_id",
    "case_id",
    "input_json",
    "output_json",
    "created_at",
]

ANALYTICS_DAILY_HEADERS = [
    "date",
    "cases_count",
    "avg_margin_pct",
    "low_margin_cases",
    "urgent_cases",
    "win_signal_score",
]

LOOKUPS_HEADERS = [
    "lookup_type",
    "lookup_value",
    "active",
    "sort_order",
]

STUDY_DAILY_HEADERS = [
    "daily_id",
    "log_date",
    "owner_name",
    "mentor_name",
    "shop_or_site_name",
    "district",
    "start_time",
    "end_time",
    "today_goal",
    "job_types_seen",
    "customer_types_seen",
    "safety_briefing_done",
    "tools_prepared",
    "questions_to_ask",
    "lesson_summary",
    "mistakes_or_risks_observed",
    "next_day_focus",
    "photo_drive_links",
    "created_at",
]

STUDY_TASK_HEADERS = [
    "task_id",
    "daily_id",
    "task_time",
    "task_category",
    "job_mode",
    "site_type",
    "symptom_or_requirement",
    "suspected_cause",
    "materials_used",
    "tools_used",
    "step_notes",
    "quality_check_points",
    "safety_risks",
    "mentor_tip",
    "my_role",
    "difficulty_score",
    "confidence_after_task",
    "open_question",
    "photo_drive_link",
    "created_at",
]

STUDY_WEEKLY_REVIEW_HEADERS = [
    "review_id",
    "week_no",
    "from_date",
    "to_date",
    "top_lessons",
    "repeated_problems",
    "skills_improved",
    "skills_need_practice",
    "next_week_plan",
    "created_at",
]

STUDY_LOOKUPS_HEADERS = LOOKUPS_HEADERS.copy()

STUDY_EVENTS_HEADERS = [
    "event_id",
    "event_name",
    "page",
    "metadata_json",
    "created_at",
]

TAB_HEADERS = {
    "cases_raw": CASES_HEADERS,
    "pricing_reference": PRICING_REFERENCE_HEADERS,
    "knowledge_qna": KNOWLEDGE_HEADERS,
    "calculator_logs": CALCULATOR_LOG_HEADERS,
    "analytics_daily": ANALYTICS_DAILY_HEADERS,
    "lookups": LOOKUPS_HEADERS,
    "study_daily": STUDY_DAILY_HEADERS,
    "study_tasks": STUDY_TASK_HEADERS,
    "study_weekly_review": STUDY_WEEKLY_REVIEW_HEADERS,
    "study_lookups": STUDY_LOOKUPS_HEADERS,
    "study_events": STUDY_EVENTS_HEADERS,
}

DEFAULT_LOOKUPS = [
    ["district", "เมือง", "TRUE", "1"],
    ["district", "บางพลี", "TRUE", "2"],
    ["district", "บางปะอิน", "TRUE", "3"],
    ["job_type", "ติดตั้งใหม่", "TRUE", "1"],
    ["job_type", "ซ่อม", "TRUE", "2"],
    ["site_type", "อาคารพาณิชย์", "TRUE", "1"],
    ["site_type", "โกดัง", "TRUE", "2"],
    ["site_type", "โรงงาน", "TRUE", "3"],
    ["status", "New Lead", "TRUE", "1"],
    ["status", "Qualified", "TRUE", "2"],
    ["status", "Survey Booked", "TRUE", "3"],
    ["status", "Quoted", "TRUE", "4"],
    ["status", "Won", "TRUE", "5"],
    ["status", "Lost", "TRUE", "6"],
    ["motor_type", "Manual", "TRUE", "1"],
    ["motor_type", "Chain Hoist", "TRUE", "2"],
    ["motor_type", "Electric", "TRUE", "3"],
]

DEFAULT_PRICING_REFERENCE = [
    ["SLAT-075", "เหล็กแผ่นม้วน 0.75", "ตร.ม.", "950", "", "ราคากลางเริ่มต้น"],
    ["MOTOR-600", "มอเตอร์ 600kg", "ชุด", "14500", "", "ราคากลางเริ่มต้น"],
    ["MOTOR-800", "มอเตอร์ 800kg", "ชุด", "18800", "", "ราคากลางเริ่มต้น"],
    ["GUIDE-STD", "รางมาตรฐาน", "เมตร", "280", "", "ราคากลางเริ่มต้น"],
    ["SERVICE-EM", "ค่าบริการฉุกเฉิน", "ครั้ง", "1500", "", "นอกเวลางาน"],
]

DEFAULT_KNOWLEDGE = [
    [
        "การเลือกมอเตอร์",
        "โกดังขนาดใหญ่ควรใช้มอเตอร์แบบไหน",
        "ให้เลือกตามน้ำหนักบานและรอบการใช้งานต่อวัน โดยงานใช้งานหนักควรเผื่อสเปก 20%",
        "motor,โกดัง,สเปก",
        "medium",
        "",
    ],
    [
        "งานซ่อม",
        "ประตูฝืดและมีเสียงดังควรเช็กอะไรเป็นอันดับแรก",
        "ตรวจราง, ลูกล้อ, จุดยึด และการหล่อลื่นก่อนเสมอ แล้วค่อยประเมินมอเตอร์",
        "ซ่อม,เสียงดัง,บำรุงรักษา",
        "high",
        "",
    ],
]

DEFAULT_STATUS = "New Lead"

DEFAULT_STUDY_LOOKUPS = [
    ["task_category", "สำรวจ", "TRUE", "1"],
    ["task_category", "ติดตั้ง", "TRUE", "2"],
    ["task_category", "ซ่อม", "TRUE", "3"],
    ["task_category", "ทดสอบ", "TRUE", "4"],
    ["task_category", "ส่งมอบ", "TRUE", "5"],
    ["job_mode", "ติดตั้งใหม่", "TRUE", "1"],
    ["job_mode", "ซ่อม", "TRUE", "2"],
    ["job_mode", "บำรุง", "TRUE", "3"],
    ["site_type", "อาคารพาณิชย์", "TRUE", "1"],
    ["site_type", "โกดัง", "TRUE", "2"],
    ["site_type", "โรงงาน", "TRUE", "3"],
    ["my_role", "ดูงาน", "TRUE", "1"],
    ["my_role", "ช่วยจับงาน", "TRUE", "2"],
    ["my_role", "ลงมือเอง", "TRUE", "3"],
]
