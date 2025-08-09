# 🤖 LINE Bot Event Notification System

ระบบแจ้งเตือนกิจกรรมผ่าน LINE Bot ที่ผู้ใช้สามารถดูกิจกรรม ค้นหา และสมัครรับแจ้งเตือนอัตโนมัติได้ โดยมี Admin interface สำหรับจัดการกิจกรรม

## 📋 สารบัญ

- [ภาพรวมระบบ](#ภาพรวมระบบ)
- [ฟีเจอร์หลัก](#ฟีเจอร์หลัก)
- [การติดตั้งและตั้งค่า](#การติดตั้งและตั้งค่า)
- [การใช้งาน](#การใช้งาน)
- [ปัญหาที่พบและการแก้ไข](#ปัญหาที่พบและการแก้ไข)
- [ประวัติการพัฒนา](#ประวัติการพัฒนา)
- [API Reference](#api-reference)
- [การ Deploy](#การ-deploy)
- [การบำรุงรักษา](#การบำรุงรักษา)

## 🎯 ภาพรวมระบบ

### Technology Stack
- **Backend**: Flask (Python)
- **Database**: Supabase (PostgreSQL)
- **LINE Bot SDK**: line-bot-sdk v3.17.1
- **Deployment**: Render.com
- **Scheduler**: GitHub Actions
- **Environment Management**: python-dotenv

### Architecture
```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   LINE Users    │◄──►│   LINE Bot   │◄──►│   Supabase DB   │
└─────────────────┘    └──────────────┘    └─────────────────┘
                               │
                       ┌──────────────┐
                       │ GitHub Actions │
                       │  (Scheduler)   │
                       └──────────────┘
```

## ⭐ ฟีเจอร์หลัก

### 👥 สำหรับผู้ใช้ทั่วไป

#### 📅 ดูกิจกรรม
- **กิจกรรมล่าสุด** - ดูกิจกรรมทั้งหมดเรียงตามวันที่
- **กิจกรรมวันนี้** - กิจกรรมที่มีวันนี้
- **กิจกรรมถัดไป** - กิจกรรม 5 รายการถัดไป
- **กิจกรรมเดือนนี้** - กิจกรรมในเดือนปัจจุบัน
- **Pagination** - รองรับกิจกรรมไม่จำกัด (10 รายการต่อหน้า)

#### 🔍 ค้นหากิจกรรม (แบบไม่ต้องพิมพ์)
- **ค้นหาชื่อ/รายละเอียด** - ค้นหาจากคำในชื่อหรือรายละเอียด
- **ค้นหาวันที่** - เลือกวันที่จากปุ่ม (11 วันข้างหน้า + วันอื่น)
- **ค้นหาทั้งหมด** - ค้นหาแบบอิสระ (รองรับ text, Thai keywords และ date)
- **รองรับคีย์เวิร์ดไทย** - "วันนี้", "พรุ่งนี้", "เมื่อวาน" ใช้งานได้
- **ผลลัพธ์ครบถ้วน** - แสดงผล Flex Message + pagination

#### 🔔 ระบบแจ้งเตือน
- **สมัครรับแจ้งเตือน** - กดปุ่มเดียวสมัครเสร็จ
- **แจ้งเตือนอัตโนมัติ** - รับการแจ้งเตือนตามกิจกรรม
  - **06:00 น.** - แจ้งกิจกรรมวันนี้และพรุ่งนี้
  - **18:00 น.** - แจ้งซ้ำเพื่อความแน่ใจ

### 👨‍💼 สำหรับ Admin

#### 📝 จัดการกิจกรรม (แบบไม่ต้องพิมพ์)
- **เพิ่มกิจกรรม** - Guided flow 3 ขั้นตอน
  1. ชื่อกิจกรรม
  2. รายละเอียด
  3. วันที่ (เลือกจากปุ่ม 11 วัน + วันอื่น)
- **แก้ไขกิจกรรม** - เลือกแก้เฉพาะส่วนที่ต้องการ
  - แก้ชื่อ, รายละเอียด, วันที่ แยกส่วน
  - หรือแก้ทั้งหมดแบบ 3 ขั้นตอน
- **ลบกิจกรรม** - ปุ่มใน Flex Message + การยืนยัน

#### 📢 ระบบแจ้งเตือน Admin
- **ข้อความกำหนดเอง** - พิมพ์ข้อความส่งให้ผู้สมัครทุกคน
- **แจ้งกิจกรรมถัดไป** - ส่งข้อมูลกิจกรรมที่กำลังจะมาถึง
- **ทดสอบแจ้งเตือนอัตโนมัติ** - ทดสอบระบบส่งแจ้งเตือนวันนี้/พรุ่งนี้
- **ดูสถิติผู้สมัคร** - สถิติการใช้งานและจำนวนผู้สมัคร

### 🤖 ระบบอัตโนมัติ

#### ⏰ Scheduler (GitHub Actions)
```yaml
# เวลาการทำงาน (UTC)
06:00 Thai = 23:00 UTC (previous day) = 0 23 * * *
18:00 Thai = 11:00 UTC (same day)     = 0 11 * * *
```

#### 📊 API Endpoints
- `GET /` - Health check
- `GET|POST /send-notifications` - ส่งแจ้งเตือนอัตโนมัติ
- `POST /callback` - LINE Bot webhook

## 🚀 การติดตั้งและตั้งค่า

### 1. ข้อกำหนดระบบ
```bash
Python 3.8+
LINE Bot Channel (LINE Developers Console)
Supabase Account
GitHub Account
Render.com Account (optional)
```

### 2. Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables (.env)
```bash
# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
LINE_CHANNEL_SECRET=your_channel_secret
ADMIN_IDS=user_id_1,user_id_2

# Supabase Configuration  
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key

# Optional
Webhook_URL=https://your-app.render.com/callback
PORT=5000
```

### 4. Database Schema (Supabase)

#### Events Table
```sql
CREATE TABLE events (
  id SERIAL PRIMARY KEY,
  event_title VARCHAR NOT NULL,
  event_description TEXT,
  event_date DATE NOT NULL,
  created_by VARCHAR,
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### Subscribers Table  
```sql
CREATE TABLE subscribers (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 5. LINE Bot Setup
1. สร้าง LINE Bot Channel ที่ [LINE Developers Console](https://developers.line.biz/)
2. เปิดใช้งาน Messaging API
3. ตั้งค่า Webhook URL: `https://your-app.com/callback`
4. Copy Channel Access Token และ Channel Secret

## 📱 การใช้งาน

### ผู้ใช้ทั่วไป
1. **Add Bot** - เพิ่มเป็นเพื่อนใน LINE
2. **พิมพ์ "สวัสดี"** - เริ่มใช้งาน
3. **ใช้เมนูปุ่ม** - เลือกฟีเจอร์ที่ต้องการ
4. **สมัครแจ้งเตือน** - กด "🔔 สมัครแจ้งเตือน"

### Admin
1. **ตั้งค่า ADMIN_IDS** - ใส่ LINE User ID ใน environment
2. **พิมพ์ "/admin"** - เข้าสู่โหมด Admin
3. **ใช้ปุ่มเมนู** - จัดการกิจกรรมและแจ้งเตือน

### คำสั่งที่รองรับ
```bash
# ผู้ใช้ทั่วไป
สวัสดี                    # เริ่มใช้งาน
/today                   # กิจกรรมวันนี้
/next                    # กิจกรรมถัดไป
/month                   # กิจกรรมเดือนนี้
/search                  # ค้นหากิจกรรม
/search คำค้น             # ค้นหาโดยตรง
/search วันนี้             # ค้นหาด้วยคีย์เวิร์ดไทย
/search 2025-01-20       # ค้นหาตามวันที่
/subscribe               # สมัครรับแจ้งเตือน

# Admin เท่านั้น
/admin                   # เมนู Admin
/add ชื่อ | รายละเอียด | วันที่  # เพิ่มกิจกรรมแบบเร็ว
/edit ID | ชื่อ | รายละเอียด | วันที่  # แก้ไขกิจกรรม
/delete ID               # ลบกิจกรรม
/list                    # ดูรายการทั้งหมด
/notify ข้อความ           # ส่งแจ้งเตือนด่วน
```

## ⚠️ ปัญหาที่พบและการแก้ไข

### ปัญหาการ Deploy

#### 1. RLS (Row Level Security) Error
**ปัญหา:** ไม่สามารถเพิ่ม/แก้ไข/ลบข้อมูลใน Supabase
```
new row violates row-level security policy
```

**การแก้ไข:**
```python
# เปลี่ยนจาก SUPABASE_KEY เป็น SUPABASE_SERVICE_KEY
supabase_key = os.getenv('SUPABASE_SERVICE_KEY')  # ใช้ service role
```

#### 2. Gunicorn Not Found (Render)
**ปัญหา:** Deployment fail เพราะไม่พบ gunicorn

**การแก้ไข:**
```bash
# requirements.txt
gunicorn==23.0.0

# Procfile  
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

### ปัญหาระบบแจ้งเตือน

#### 3. GitHub Actions ไม่ทำงาน
**ปัญหา:** Workflow มีอยู่แต่ไม่เคยรัน

**การแก้ไข:**
```yaml
# เพิ่ม trigger เพื่อทดสอบ
on:
  push:
    branches: [ main ]
  schedule:
    - cron: '0 23 * * *'
    - cron: '0 11 * * *'
```

**Plan B: ใช้ Cron-job.org**
1. ไปที่ https://cron-job.org
2. สร้าง job: `https://your-app.com/send-notifications`
3. ตั้งเวลา: `0 23 * * *` และ `0 11 * * *`

#### 4. Timezone Issues
**ปัญหา:** เวลาไม่ตรงกับเวลาไทย

**การแก้ไข:**
```
Thai Time = UTC + 7
06:00 Thai = 23:00 UTC (previous day)
18:00 Thai = 11:00 UTC (same day)
```

### ปัญหา LINE Bot

#### 5. Webhook Verification Failed
**ปัญหา:** LINE Bot ไม่ตอบสนอง

**การแก้ไข:**
```python
# ตรวจสอบ Channel Secret และ Access Token
LINE_CHANNEL_ACCESS_TOKEN=correct_token
LINE_CHANNEL_SECRET=correct_secret

# ตรวจสอบ Webhook URL
https://your-app.com/callback
```

#### 6. Quick Reply Limit Exceeded
**ปัญหา:** LINE จำกัด Quick Reply ไม่เกิน 13 items

**การแก้ไข:**
```python
# แบ่งเมนูออกเป็นหลายขั้น และใช้ให้คุ้มค่า
def create_date_quick_reply():
    # ใช้สูงสุด 11 วัน + วันอื่น + ยกเลิก = 13 items
    for i in range(11):  # เพิ่มจาก 7 เป็น 11 วัน
```

#### 7. Thai Date Keywords Not Working
**ปัญหา:** พิมพ์ "วันนี้" แสดงข้อความ "รูปแบบวันที่ไม่ถูกต้อง"

**การแก้ไข:**
```python
# เพิ่มการรองรับคีย์เวิร์ดไทยในทุก search handler
if search_term.lower() in ["วันนี้", "today"]:
    actual_search_term = str(date.today())
elif search_term.lower() in ["พรุ่งนี้", "tomorrow"]:
    actual_search_term = str(date.today() + timedelta(days=1))
elif search_term.lower() in ["เมื่อวาน", "yesterday"]:
    actual_search_term = str(date.today() - timedelta(days=1))
```

## 📜 ประวัติการพัฒนา

### Phase 1: Core System (Initial Release)
- ✅ พื้นฐาน Flask + LINE Bot SDK
- ✅ Supabase database integration  
- ✅ Basic CRUD operations
- ✅ Render deployment

### Phase 2: Admin Interface
- ✅ Admin authentication
- ✅ Event management commands
- ✅ Flex Message การ์ด
- ✅ Admin buttons ใน Flex Messages

### Phase 3: Scalability  
- ✅ Pagination system
- ✅ Search functionality
- ✅ Support unlimited events
- ✅ Performance optimization

### Phase 4: User Experience
- ✅ No-typing interface
- ✅ Guided conversation flows
- ✅ Step-by-step event creation
- ✅ Flexible edit options

### Phase 5: Notification System
- ✅ Manual notifications
- ✅ Push message system
- ✅ Subscriber management
- ✅ Delivery reporting

### Phase 6: Automation
- ✅ Automatic daily notifications
- ✅ GitHub Actions scheduler
- ✅ API endpoints for external scheduling
- ✅ Testing and monitoring tools

### Phase 7: Bug Fixes & UX Improvements (Latest)
- ✅ Fix Thai date keyword support ("วันนี้", "พรุ่งนี้", "เมื่อวาน")
- ✅ Fix "จัดการกิจกรรม" button not responding issue
- ✅ Expand date selection from 7 to 11 days
- ✅ Improve search functionality with proper Thai keyword recognition
- ✅ Add friendly date display in search results

## 📊 API Reference

### Automatic Notifications
```bash
# ส่งแจ้งเตือนอัตโนมัติ
GET/POST https://your-app.com/send-notifications

# Response
{
  "status": "success",
  "notifications_sent": 4,
  "events_today": 1,
  "events_tomorrow": 1,
  "subscribers": 2
}
```

### Health Check
```bash
# ตรวจสอบสถานะระบบ
GET https://your-app.com/

# Response
{
  "status": "ok",
  "service": "LINE Bot Event Notification System"
}
```

### Database Operations (Internal)
```python
# Get events
response = supabase_client.table('events').select('*').execute()

# Add event
response = supabase_client.table('events').insert({
    'event_title': title,
    'event_description': desc,
    'event_date': date,
    'created_by': user_id
}).execute()

# Get subscribers
response = supabase_client.table('subscribers').select('user_id').execute()
```

## 🚀 การ Deploy

### Render.com (แนะนำ)
1. **Connect GitHub** - เชื่อมต่อ repository
2. **Environment Variables** - ตั้งค่าตัวแปรสภาพแวดล้อม
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`

### Heroku
```bash
# Procfile
web: gunicorn app:app --bind 0.0.0.0:$PORT

# Deploy
git push heroku main
```

### Docker (ตัวเลือก)
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
```

### Local Development
```bash
# เริ่มระบบ
python app.py

# หรือใช้ gunicorn
gunicorn app:app --bind 0.0.0.0:5000
```

## 🔧 การบำรุงรักษา

### Monitoring
- **Health Check:** `https://your-app.com/`
- **Notification Test:** Admin > "🤖 ทดสอบแจ้งเตือนอัตโนมัติ"
- **GitHub Actions:** ตรวจสอบ workflow runs
- **Render Logs:** ดู application logs

### Backup Options
1. **GitHub Actions** (primary)
2. **Cron-job.org** (free backup)
3. **Render Cron Jobs** (paid)
4. **Manual Admin Testing**

### Database Maintenance
```sql
-- ทำความสะอาดข้อมูลเก่า
DELETE FROM events WHERE event_date < (CURRENT_DATE - INTERVAL '1 year');

-- ดูสถิติการใช้งาน
SELECT COUNT(*) as total_events FROM events;
SELECT COUNT(*) as total_subscribers FROM subscribers;
```

### Security Best Practices
- ✅ ใช้ Service Role key สำหรับ database operations
- ✅ ซ่อน sensitive data ใน environment variables
- ✅ Validate user input และ admin permissions
- ✅ Use HTTPS สำหรับ webhook URL
- ✅ Monitor logs สำหรับ suspicious activities

## 📞 การติดต่อและสนับสนุน

### Issues และ Bug Reports
- **GitHub Issues:** https://github.com/watt29/notibot-1234/issues
- **Documentation:** README.md และ backup-scheduler.md

### การพัฒนาต่อยอด
- เพิ่มประเภทกิจกรรม (categories)
- Rich menu สำหรับ LINE Bot
- Multi-language support
- Event reminder customization
- Analytics dashboard
- Export/Import ข้อมูล

---

## 📝 หมายเหตุสำคัญ

### การใช้งานครั้งแรก
1. ตั้งค่า environment variables ให้ครบ
2. สร้าง database tables ใน Supabase
3. Test webhook connection
4. เพิ่ม Admin ID
5. ทดสอบการส่งแจ้งเตือน

### ข้อจำกัด
- LINE Bot API มี rate limit
- Quick Reply จำกัด 13 items
- Flex Message Carousel จำกัด 12 items  
- GitHub Actions จำกัด 2,000 minutes/month (free plan)

### Performance Tips
- ใช้ pagination สำหรับข้อมูลจำนวนมาก
- Cache frequently accessed data
- Optimize database queries
- Monitor API usage

**🎉 ระบบพร้อมใช้งานและสามารถปรับขยายได้ตามความต้องการ!**