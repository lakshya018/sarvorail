# Deployment Updates — Redis to In-Memory Cache

## 🚀 For Render Deployment

### Step 1: Update Environment Variables
**Remove these** from Render dashboard:
- `REDIS_URL`

No new env vars needed — in-memory cache requires no external connection.

### Step 2: Delete Old Cache Module
```bash
rm -rf cache/
```

The `cache/redis_client.py` file is now obsolete.

### Step 3: Deploy
```bash
git add .
git commit -m "Refactor: Replace Redis with in-memory cachetools"
git push origin main
```

Render will automatically:
1. Install new `requirements.txt` (adds `cachetools`, removes `redis`)
2. Start the app (no Redis connection needed)
3. App will log: `"App started — using in-memory cache (cachetools)"`

### Step 4: Verify
```bash
# Check health endpoint
curl https://your-app.onrender.com/api/v1/health

# Response should show:
{
  "status": "ok",
  "redis_connected": false,  ✓ Now false
  "active_sessions": 0,
  "total_sessions": 0,
  "uptime_seconds": 0.0
}
```

## 💾 In-Memory Cache Behavior

| Action | Behavior |
|--------|----------|
| First request | Normal speed (~2–5s for IRCTC scraping) |
| Repeated request (within 5 min) | <1ms cache hit ✨ |
| 5 minutes pass | Availability cache expires, re-fetches |
| App restarts | Cache clears (expected) |

## 📊 Memory Impact

Max cache size: **1000 routes** × ~100KB = **~100MB worst case**
Render free tier: **512MB available** = **plenty of headroom**

## ✅ What Got Better

1. **No more "Too many connections" errors** ← Main goal
2. **Faster cache hits** ← <1ms vs 20–50ms with Redis
3. **No network latency** ← All lookups are in-process
4. **Simpler deployment** ← No Redis service to manage
5. **Lower bandwidth** ← No Redis replication overhead

## ❌ What's Different

- **Cache resets on app restart** (was already true with free Redis tier expiry)
- **Single-worker only** (Render free tier = 1 worker anyway)
- **In-memory only** (no persistence; expected for free tier)

## 🔧 Local Development

No changes needed:
```bash
# Still works the same
python api/main.py
```

Logs will show:
```
App started — using in-memory cache (cachetools)
```

## Troubleshooting

**Q: Cache not working?**
- Check logs: `grep -i "cache" *.log`
- Cache operations are instant (silent)
- If seeing repeated IRCTC calls, cache might be cleared (app restarted)

**Q: Memory usage high?**
- Check cache size: `len(cache.cache)` in Python REPL
- Max is 1000 entries by design
- Check Render dashboard under "Metrics"

**Q: How to clear cache manually?**
```python
from core.cache import clear
clear()  # Clears all cached data
```

## 🚨 Do NOT Do This

- ❌ Don't try to connect to Redis (it's not installed)
- ❌ Don't set `REDIS_URL` env var (won't be used)
- ❌ Don't import `cache.redis_client` (file is gone)
- ❌ Don't use `await cache.get()` (cache is sync now)
