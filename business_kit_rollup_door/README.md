# Roll-Up Door Business Kit (TH)

ชุดเครื่องมือเริ่มธุรกิจประตูเหล็กม้วนแบบ `รับติดตั้ง+ซ่อม` สำหรับตลาด `อาคารพาณิชย์/โกดัง` โดยเน้นการตลาดต้นทุนต่ำผ่าน TikTok และระบบหลังบ้านที่คุมงานได้จริง

## โครงสร้างไฟล์

- `OPERATIONS_PLAYBOOK_TH.md` แผนปฏิบัติการ 90 วัน + เป้าหมาย
- `SOP_SITE_SURVEY_CHECKLIST.md` เช็กลิสต์สำรวจหน้างาน 1 หน้า
- `SALES_SCRIPTS_TH.md` สคริปต์คัดกรองลีด/นัดสำรวจ/ปิดงาน/ติดตามรีวิว
- `TIKTOK_CONTENT_SYSTEM_TH.md` ระบบคอนเทนต์ 5 คลิป/สัปดาห์ + CTA เดียว
- `LEGAL_FINANCE_CHECKLIST_TH.md` เช็กลิสต์กฎหมายและการเงินพื้นฐาน
- `PARTNER_OUTREACH_SCRIPT_TH.md` สคริปต์หาพาร์ทเนอร์ท้องถิ่น
- `RISK_AND_SCENARIO_TESTS_TH.md` เคสทดสอบระบบก่อนขยาย
- `WEBAPP_SETUP_TH.md` คู่มือเริ่มใช้ Google Sheets + Mobile Web App
- `RENDER_DEPLOY_TH.md` คู่มือ deploy production บน Render

## ระบบ Web App + Google Sheets (เวอร์ชันใช้งานจริง)

สคริปต์หลัก:

- `scripts/rollup_create_sheet.py` สร้างชีต schema ทั้งระบบ
- `scripts/rollup_webapp.py` รันเว็บแอปมือถือ
- `scripts/rollup_refresh_analytics.py` สรุป analytics_daily
- `scripts/rollup_export_csv.py` สำรองข้อมูลเป็น CSV
- `scripts/rollup_data_quality_check.py` ตรวจคุณภาพข้อมูลก่อนตัดสินใจขยาย

## วิธีเริ่มต้นเร็ว

```bash
python3 scripts/rollup_create_sheet.py --save_to_config
python3 scripts/rollup_webapp.py
```

## KPI หลัก 90 วัน

- ลีดคุณภาพเฉลี่ย >= 20 ลีด/เดือน
- อัตรานัดสำรวจจากลีด >= 40%
- อัตราปิดงานจากใบเสนอราคา >= 25%
- กำไรขั้นต้นหน้างาน >= 20-30%
- รีวิวลูกค้าจริง >= 10 รีวิว
