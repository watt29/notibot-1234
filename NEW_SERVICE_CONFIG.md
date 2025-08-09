# 🚨 NEW RENDER SERVICE CONFIG - **ACTIVATED 2025-08-09T14:18**

## 🚨 EMERGENCY PRODUCTION OUTAGE - CREATE NEW SERVICE NOW

### Critical Steps:
1. **Go to Render Dashboard:** https://dashboard.render.com/
2. **Create New Web Service**
3. **Connect to GitHub:** watt29/notibot-1234
4. **Configure Service:**

## Service Settings
- **Name:** `notibot-1234-emergency` 
- **Branch:** `main`
- **Build Command:** (empty)
- **Start Command:** `gunicorn app:app`
- **Environment:** `Python 3`

## Environment Variables (COPY FROM OLD SERVICE!)
```
LINE_CHANNEL_ACCESS_TOKEN=copy_from_old_service
LINE_CHANNEL_SECRET=copy_from_old_service  
SUPABASE_URL=copy_from_old_service
SUPABASE_KEY=copy_from_old_service
SUPABASE_SERVICE_KEY=copy_from_old_service
ADMIN_IDS=Uc88eb3896b0e4bcc5fbaa9b78ac1294e,U3f09510286687007931c42eb8d10fa1d
```

## Emergency Recovery Steps
1. ✅ Create new service: `notibot-1234-emergency`
2. ✅ Deploy clean version (no cache)
3. ✅ Get new URL: `https://notibot-1234-emergency.onrender.com`
4. ✅ Update LINE Webhook URL to new service
5. ✅ Test LINE Bot functionality
6. ✅ Delete corrupted service `notibot-1234`

---
**🚨 PRODUCTION DOWN - CACHE CORRUPTION - IMMEDIATE ACTION REQUIRED**