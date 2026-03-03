# วิธีเริ่มใช้ Google Sheets + Mobile Web App (TH)

## 1) ติดตั้ง dependencies

```bash
cd "/Users/earthondev/Desktop/untitled folder"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) ตั้งค่า local development (Google OAuth)

1. วางไฟล์ OAuth client ที่ `credentials/client_secrets.json`
2. แก้ไฟล์ `config/rollup_door.yaml`
- `security.access_key_id`
- `security.access_key_secret`

## 3) สร้าง Google Sheets schema ทั้ง 6 แท็บ

```bash
source .venv/bin/activate
python scripts/rollup_create_sheet.py --save_to_config
```

คำสั่งนี้จะ:
- สร้าง Spreadsheet ใหม่
- สร้างแท็บ `cases_raw`, `pricing_reference`, `knowledge_qna`, `calculator_logs`, `analytics_daily`, `lookups`
- seed ข้อมูลตั้งต้นบางส่วน
- บันทึก `spreadsheet_id` ลง `config/rollup_door.yaml`

## 4) รัน Mobile Web App

```bash
source .venv/bin/activate
python scripts/rollup_webapp.py
```

เปิดที่: `http://127.0.0.1:8080`

## 5) การใช้งานครั้งแรกบนหน้าเว็บ

1. กรอก Access Key ID/Secret ให้ตรงกับ `config/rollup_door.yaml`
2. เริ่มกรอกเคสที่หน้า `Quick Intake`
3. ใช้หน้า `Calculator` สำหรับคำนวณราคาเร็ว
4. ใช้หน้า `Knowledge` ค้นหา Q&A หน้างาน
5. ใช้หน้า `Analytics` ดูภาพรวมกำไรและ cost drivers

## 6) งานหลังบ้านประจำวัน

รีเฟรชสรุปรายวัน:
```bash
python scripts/rollup_refresh_analytics.py
```

สำรองข้อมูลเป็น CSV:
```bash
python scripts/rollup_export_csv.py
```

ตรวจคุณภาพข้อมูล (ตั้งเป้าฟิลด์ขาดหายไม่เกิน 10%):
```bash
python scripts/rollup_data_quality_check.py --target_missing_pct 10
```

## หมายเหตุด้านความปลอดภัย

V1 ตั้งใจให้ใช้งานเร็วด้วยทีมเล็กและยังไม่บังคับ login
- ใช้ signed request + rate limit ขั้นต้น
- ไม่ควรเปิด endpoint สู่สาธารณะโดยไม่มี reverse proxy/firewall
- Phase ถัดไปแนะนำเพิ่ม Google Login และ role-based access

## Deploy production บน Render

ดูขั้นตอนเต็มที่ `RENDER_DEPLOY_TH.md`
