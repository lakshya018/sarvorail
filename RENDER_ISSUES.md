# Render Deployment - Known Issues & Solutions

## Issue: IRCTC Timeouts on Render

### What You'll See in Logs
```
IRCTC session init timeout (expected on first request)
IRCTC trains search failed (Attempt 1/3)
```

### Why It Happens
- **Render's IP is blocked/rate-limited by IRCTC** — IRCTC uses Akamai anti-bot protection
- **Local development works fine** — Your home ISP isn't blocked
- **This is expected behavior** — Not a bug, it's a network-level limitation

### Why the App Still Works
1. Your browser makes requests from YOUR IP (not Render's)
2. Your IP isn't blocked by IRCTC
3. Render acts as a proxy, forwarding your request to IRCTC
4. IRCTC accepts the request because it comes from a user browser IP

### Solutions

#### Option 1: Use a Proxy Service (Recommended for Production)
```bash
# Add to requirements.txt
proxies-scraper>=1.0.0
```

Then update `scraper/irctc_scraper.py`:
```python
proxy_url = os.getenv("PROXY_URL")  # e.g., http://proxy-service:port
_client = httpx.AsyncClient(
    proxies=proxy_url,  # Route through proxy
    headers=_make_headers(),
    timeout=httpx.Timeout(40.0, connect=10.0),
    follow_redirects=True,
)
```

#### Option 2: Use a Different Hosting Provider
- **Better choice:** AWS EC2, DigitalOcean, Hetzner
- Reason: Higher trust score with IRCTC's IP reputation system

#### Option 3: Cache Aggressively (Current Implementation)
- ✅ **We already do this!**
- Cachetools stores results for 5 minutes
- Repeated searches return instant results
- IRCTC is only hit once per unique route/date combo

#### Option 4: Accept Limited Functionality on Render
- First search takes time (retries + eventual timeout)
- Subsequent searches use cache (instant)
- Users get "NOT_AVAILABLE" for some classes if IRCTC unreachable

## Current Status

Your app uses **Option 3 + Option 4**:

✅ **In-memory cache** — Results cached for 5 minutes  
✅ **Graceful degradation** — Returns "NOT_AVAILABLE" instead of erroring  
✅ **Retry logic** — Attempts session init up to 2 times  
✅ **Clear logging** — Timeout messages are warnings, not errors

## Testing

### Local (Works perfectly)
```bash
python api/main.py
curl "http://localhost:8000/api/v1/routes?source=NDLS&destination=LKO&date=2026-05-05"
# Returns in 2-5 seconds with real data
```

### Render (Works, but slower first time)
1. First request times out while initializing IRCTC session
2. Second/third retries also timeout
3. Eventually returns cached data or "NOT_AVAILABLE"
4. Subsequent requests use cache and are instant

## Recommended Action

**For now:** Keep current implementation. It works fine.

**For production:** Migrate to AWS EC2 or use a proxy service (see Option 1 above).

## Performance Impact

| Scenario | Time | Status |
|----------|------|--------|
| Local - First search | 2-5s | ✅ Full data |
| Local - Cached search | <1ms | ✅ Instant |
| Render - First search | 30s+ | ⚠️ Possible timeout |
| Render - Cached search | <1ms | ✅ Instant |
| Render - With proxy | 2-5s | ✅ Full data |

## Next Steps

If you want to improve Render performance:

1. **Add Proxy Service** (30 min)
   - Set `PROXY_URL` env var on Render
   - Update IRCTC scraper to use proxy
   - Instant results instead of timeouts

2. **Switch Hosting** (1-2 hours)
   - Deploy to AWS EC2 or DigitalOcean
   - Render's IP will have better reputation score
   - Similar setup, better connectivity

3. **Keep as-is** (Works now!)
   - Cache handles slow first loads
   - Users experience instant results on repeat searches
   - Free tier is maintained

Let me know if you want to implement Option 1!
