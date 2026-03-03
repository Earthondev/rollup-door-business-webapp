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

TAB_HEADERS = {
    "cases_raw": CASES_HEADERS,
    "pricing_reference": PRICING_REFERENCE_HEADERS,
    "knowledge_qna": KNOWLEDGE_HEADERS,
    "calculator_logs": CALCULATOR_LOG_HEADERS,
    "analytics_daily": ANALYTICS_DAILY_HEADERS,
    "lookups": LOOKUPS_HEADERS,
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
