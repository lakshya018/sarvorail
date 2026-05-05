# Azure App Service Deployment Guide

## Prerequisites
- Azure Account (free tier eligible)
- GitHub repo (public or private)
- Azure CLI installed (optional, but helpful)

## Step 1: Create Azure Account

1. Go to https://azure.microsoft.com/en-us/free/
2. Click "Start free"
3. Sign in with Microsoft account or create new one
4. Add payment method (won't be charged for free tier)
5. Verify phone number
6. Done! You get $200 free credits + always-free services

## Step 2: Create App Service

1. Go to [Azure Portal](https://portal.azure.com)
2. Click "Create a resource"
3. Search for "App Service"
4. Click "App Service" → "Create"

**Fill in details:**
- **Subscription**: Free Trial (or your account)
- **Resource Group**: Click "Create new" → name: `sarvorail-rg`
- **Name**: `sarvorail-api` (must be unique, Azure adds `.azurewebsites.net`)
- **Publish**: Code
- **Runtime stack**: Python 3.11
- **Operating System**: Linux
- **Region**: Select closest to you (e.g., East US)
- **App Service Plan**: Click "Create new"
  - Name: `sarvorail-plan`
  - SKU: **Free (F1)** ← Important! Select this
  - Click "OK"

Click "Review + create" → "Create"

Wait 2-3 minutes for deployment.

## Step 3: Configure Deployment

Once deployed:

1. Go to your App Service
2. Left sidebar → "Deployment center"
3. **Source**: GitHub
4. Click "Authorize" (sign in to GitHub)
5. **Organization**: Your GitHub username
6. **Repository**: `sarvorail`
7. **Branch**: `Main`
8. Click "Save"

Azure will automatically deploy whenever you push to Main! ✨

## Step 4: Configure App Settings

In your App Service:

1. Left sidebar → "Configuration"
2. Click "New application setting"
3. Add these settings:

```
Name: LOG_LEVEL
Value: INFO

Name: PORT
Value: 8000
```

Click "Save"

## Step 5: Add Startup Command

In App Service → "Configuration":

1. Click "General settings" tab
2. **Startup Command**:
```
gunicorn --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 api.main:app
```
3. Click "Save"

## Step 6: Update requirements.txt

Your requirements.txt needs gunicorn. Check if it's there:

```bash
cat requirements.txt | grep gunicorn
```

If not, add it:

```bash
echo "gunicorn" >> requirements.txt
git add requirements.txt
git commit -m "Add gunicorn for Azure deployment"
git push origin Main
```

## Step 7: Monitor Deployment

1. Go to your App Service
2. Left sidebar → "Deployment slots" (or "Deployments")
3. Wait for "In progress" → "Success"

First deployment takes ~3-5 minutes.

View logs:
1. Left sidebar → "Log stream"
2. You'll see real-time logs as the app starts

## Step 8: Test It Works

Your app is now live at: `https://sarvorail-api.azurewebsites.net`

Test endpoints:

```bash
# Health check
curl https://sarvorail-api.azurewebsites.net/api/v1/health

# Station search
curl "https://sarvorail-api.azurewebsites.net/api/v1/stations/search?query=delhi"

# Routes (THIS SHOULD WORK NOW!)
curl "https://sarvorail-api.azurewebsites.net/api/v1/routes?source=NDLS&destination=LKO&date=2026-05-05"
```

Should return actual train data! 🎉

## Step 9: Update Frontend

Update your frontend API URL:

In `frontend/.env` or `frontend/.env.local`:
```
VITE_API_BASE=https://sarvorail-api.azurewebsites.net/api/v1
```

Or in your code:
```javascript
const API_BASE = 'https://sarvorail-api.azurewebsites.net/api/v1';
```

Push to deploy frontend (Vercel, Netlify, or wherever).

## Troubleshooting

### App shows error page
Check logs in "Log stream":
```
Error in Python startup
ModuleNotFoundError: No module named 'fastapi'
```

**Fix**: Make sure all dependencies are in requirements.txt

### 502 Bad Gateway
**Fix**: Check startup command and gunicorn is installed

### Logs not showing
1. Left sidebar → "App Service logs"
2. Toggle "Application logging" ON
3. Level: Information
4. Click "Save"
5. Go back to "Log stream"

### Still can't reach IRCTC
Azure IPs should NOT be blocked. If still timing out:
1. Check logs for actual error message
2. Verify IRCTC is reachable: `curl https://www.irctc.co.in/nget/train-search`

## Auto-Deployment

Every time you push to GitHub Main branch:
1. Azure detects change
2. Pulls latest code
3. Installs requirements
4. Runs startup command
5. Your app is live (1-2 minutes)

No manual steps needed! Just `git push`.

## Cost (Monthly)

- App Service (Free tier): **$0/month**
  - 1 GB memory
  - 60 minutes compute/day (generous free tier)
  - Shared infrastructure
  - No SLA

After free tier expires:
- Basic (B1): ~$13/month
- Standard (S1): ~$60+/month

**Recommendation**: Free tier is plenty. Upgrade only if needed.

## Monitoring

1. Left sidebar → "Metrics"
2. See CPU, memory, requests in real-time
3. Set up alerts if needed

## Custom Domain (Optional)

1. Left sidebar → "Custom domains"
2. Add your domain
3. Follow DNS setup instructions
4. Takes ~5 minutes to activate

## Restart App

If anything goes wrong:
1. App Service page → "Restart"
2. App will be down for ~10 seconds
3. Redeploy latest code from GitHub

## Backup/Rollback

If deployment breaks:
1. Go to "Deployment slots"
2. See previous deployments
3. Can swap to previous version

## Comparison: Azure vs AWS vs Render

| Feature | Azure | AWS | Render |
|---------|-------|-----|--------|
| Free tier | Yes (always free) | Yes (1 year) | Yes (limited) |
| Setup time | 10 min | 30 min | 5 min |
| IRCTC connectivity | ✅ Works | ✅ Works | ❌ Blocked |
| Auto-deploy | ✅ Yes | ❌ Manual | ✅ Yes |
| Scale up | Easy | Medium | Easy |
| Cost after free | $13+/month | $5+/month | $5+/month |

**Best for you**: Azure (free, simple, works with IRCTC)

## Next Steps

1. Create Azure account
2. Follow steps 2-6 above
3. Push code to GitHub (auto-deploys)
4. Test endpoints
5. Update frontend URL
6. Done! 🚀

Need help with any step? Let me know!
