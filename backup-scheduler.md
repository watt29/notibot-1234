# 📅 Backup Scheduler Options

หาก GitHub Actions ไม่ทำงาน สามารถใช้วิธีเหล่านี้:

## 1️⃣ Cron-job.org (แนะนำ - ฟรี)

1. ไปที่ https://cron-job.org
2. สร้าง account
3. เพิ่ม job ใหม่:
   - **URL:** `https://notibot-1234.onrender.com/send-notifications`
   - **Schedule:** `0 23 * * *` (06:00 Thai)
   - **Schedule:** `0 11 * * *` (18:00 Thai)

## 2️⃣ Manual Test via Admin

ใช้ bot เพื่อทดสอบ:
1. ส่งข้อความ: `/admin`
2. กด "📢 ส่งแจ้งเตือน"
3. กด "🤖 ทดสอบแจ้งเตือนอัตโนมัติ"

## 3️⃣ Direct API Call

```bash
curl https://notibot-1234.onrender.com/send-notifications
```

## 4️⃣ Render Cron Jobs

ใน Render Dashboard (เสียเงิน):
1. เข้า Service Settings
2. เพิ่ม Cron Job:
   - Command: `curl https://notibot-1234.onrender.com/send-notifications`
   - Schedule: `0 23,11 * * *`