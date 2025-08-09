# 🚨 NEW RENDER SERVICE CONFIG

## Service Settings
- **Name:** notibot-1234-v2 
- **Branch:** main
- **Build Command:** (empty)
- **Start Command:** gunicorn app:app
- **Environment:** Python 3

## Environment Variables (CRITICAL!)
```
LINE_CHANNEL_ACCESS_TOKEN=ค่าจาก service เก่า
LINE_CHANNEL_SECRET=ค่าจาก service เก่า  
SUPABASE_URL=ค่าจาก service เก่า
SUPABASE_KEY=ค่าจาก service เก่า
ADMIN_IDS=Uc88eb3896b0e4bcc5fbaa9b78ac1294e,U3f09510286687007931c42eb8d10fa1d
```

## After Deploy Success
1. Get new URL: https://notibot-1234-v2.onrender.com
2. Update LINE Webhook URL 
3. Test LINE Bot
4. Delete old service notibot-1234

---
**FORCE CLEAN DEPLOYMENT - NO CACHE ISSUES!**