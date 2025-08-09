# 🚨 EMERGENCY PRODUCTION RECOVERY

## Status: PRODUCTION DOWN - CACHE CORRUPTION

### Problem:
- Render service `notibot-1234` has corrupted cache
- Deploys line 2699 SyntaxError despite fixes
- Nuclear rebuild failed
- LINE Bot completely offline

### Solution: NEW SERVICE DEPLOYMENT

#### 1. Create New Render Service
- Name: `notibot-1234-emergency`
- Repo: `watt29/notibot-1234` 
- Branch: `main`

#### 2. Environment Variables (CRITICAL!)
Copy these from old service settings:
```
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
SUPABASE_URL
SUPABASE_KEY
SUPABASE_SERVICE_KEY
ADMIN_IDS=Uc88eb3896b0e4bcc5fbaa9b78ac1294e,U3f09510286687007931c42eb8d10fa1d
```

#### 3. LINE Webhook Update
- Go to LINE Developer Console
- Update Webhook URL to: `https://notibot-1234-emergency.onrender.com/callback`

#### 4. Verification
- Test `/search` command
- Verify event system works
- Confirm contact management works

---
**Time Sensitive: Every minute = lost user interactions**