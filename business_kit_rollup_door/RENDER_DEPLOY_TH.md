# Deploy ขึ้น Render (TH)

เอกสารนี้สำหรับ production โดยใช้ `Service Account` เชื่อม Google Sheets

## 1) เตรียม Google Service Account

1. ไป Google Cloud Console แล้วสร้าง Service Account
2. เปิด API: `Google Sheets API` และ `Google Drive API`
3. สร้าง key แบบ JSON และคัดลอกเนื้อหา JSON ทั้งก้อน
4. แชร์ Google Sheet ให้ email ของ Service Account เป็น `Editor`

## 2) เตรียม GitHub

1. push โปรเจกต์ไป repo: `rollup-door-business-webapp`
2. ยืนยันว่าไฟล์ `render.yaml` อยู่ที่ root ของ repo

## 3) สร้าง Render Service ด้วย Blueprint

1. Login Render แล้วเลือก `New +` -> `Blueprint`
2. เลือก repo `rollup-door-business-webapp`
3. Render จะอ่านค่าจาก `render.yaml` และสร้าง service ชื่อ `rollup-door-webapp`

## 4) ใส่ Environment Variables บน Render

ต้องใส่ค่าเหล่านี้:
- `GOOGLE_SERVICE_ACCOUNT_JSON` หรือ `GOOGLE_OAUTH_TOKEN_JSON` ที่ยังใช้งานได้
- ถ้าใช้ OAuth และ token ต้อง refresh ได้ ให้ใส่ `GOOGLE_CLIENT_SECRETS_JSON` คู่กันด้วย
- `ROLLUP_ACCESS_KEY_ID`
- `ROLLUP_ACCESS_KEY_SECRET`

ค่าที่มี default ใน render.yaml อยู่แล้ว:
- `ROLLUP_SPREADSHEET_ID=10D5NNHTMFqiwnwlhRZrFkO0pjDXbpA0BgFGNJ7y0ebQ`
- `ROLLUP_ENV=production`
- `ROLLUP_DEBUG=false`
- `ROLLUP_MARGIN_THRESHOLD_PCT=20`
- `ROLLUP_RATE_LIMIT_PER_MINUTE=180`

## 5) Verify หลัง deploy

1. เปิด `/api/v1/health` ต้องได้ `ok: true`
2. ทดสอบหน้าเว็บว่าเรียก API ได้เมื่อกรอก Access key/secret
3. ทดสอบบันทึกเคส 1 รายการและตรวจในแท็บ `cases_raw`

## 6) Troubleshooting

- ถ้า API ตอบ `503` และ health มี `missing_google_credentials`:
  ตัว web service จะบูตได้ แต่ API ที่ต้องใช้ Google Sheets จะยังใช้งานไม่ได้
  ให้ใส่ `GOOGLE_SERVICE_ACCOUNT_JSON` หรือชุด OAuth (`GOOGLE_OAUTH_TOKEN_JSON` และถ้าจำเป็น `GOOGLE_CLIENT_SECRETS_JSON`) ให้ครบ
- ถ้าเขียนชีตไม่ได้:
  ตรวจว่าแชร์ชีตให้ Service Account แล้ว
- ถ้า health เป็น `ok: false`:
  ตรวจ fields ใน `errors` ที่ `/api/v1/health`
