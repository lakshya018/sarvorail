# AWS EC2 Deployment Guide

## Prerequisites
- AWS Account (you have this ✅)
- GitHub repo access (public or private)
- Terminal/SSH client

## Step 1: Launch EC2 Instance

1. Go to AWS Console → EC2 → Instances
2. Click "Launch instances"
3. **AMI**: Select "Ubuntu Server 24.04 LTS" (free tier eligible)
4. **Instance type**: t2.micro (free tier)
5. **Key pair**: 
   - Click "Create new key pair"
   - Name: `sarvorail-key`
   - Type: RSA
   - Format: .pem (for Mac/Linux) or .ppk (for Windows)
   - Click "Create key pair" (saves to Downloads)
6. **Network settings**:
   - Allow SSH from anywhere (0.0.0.0/0)
   - Allow HTTP (80)
   - Allow HTTPS (443)
7. **Storage**: 30GB (default, free tier)
8. Click "Launch instance"

Wait 2-3 minutes for instance to start.

## Step 2: Connect to Instance

```bash
# Navigate to your Downloads folder
cd ~/Downloads

# Give key permission
chmod 400 sarvorail-key.pem

# Connect (replace IP with your instance public IP)
ssh -i sarvorail-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

You'll see Ubuntu command prompt.

## Step 3: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python & pip
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install git
sudo apt install -y git

# Install nginx (reverse proxy)
sudo apt install -y nginx

# Verify
python3 --version
git --version
```

## Step 4: Clone & Setup App

```bash
# Clone your repo
git clone https://github.com/lakshya018/sarvorail.git
cd sarvorail

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 5: Configure Gunicorn (Production Server)

```bash
# Install gunicorn
pip install gunicorn

# Create systemd service file
sudo nano /etc/systemd/system/sarvorail.service
```

Paste this:
```ini
[Unit]
Description=SarvoRail FastAPI Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/sarvorail
Environment="PATH=/home/ubuntu/sarvorail/venv/bin"
ExecStart=/home/ubuntu/sarvorail/venv/bin/gunicorn \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    api.main:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save: Ctrl+O, Enter, Ctrl+X

## Step 6: Configure Nginx

```bash
# Edit nginx config
sudo nano /etc/nginx/sites-available/default
```

Replace with:
```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 70s;
    }
}
```

Save: Ctrl+O, Enter, Ctrl+X

## Step 7: Start Services

```bash
# Enable and start the app
sudo systemctl daemon-reload
sudo systemctl enable sarvorail
sudo systemctl start sarvorail

# Check status
sudo systemctl status sarvorail

# Enable and restart nginx
sudo systemctl enable nginx
sudo systemctl restart nginx

# Check nginx
sudo systemctl status nginx
```

## Step 8: Test It Works

```bash
# Get your EC2 public IP from AWS Console
# Test health endpoint
curl http://YOUR_EC2_PUBLIC_IP/api/v1/health

# Test station search
curl "http://YOUR_EC2_PUBLIC_IP/api/v1/stations/search?query=delhi"

# Test routes (this should work now!)
curl "http://YOUR_EC2_PUBLIC_IP/api/v1/routes?source=NDLS&destination=LKO&date=2026-05-05"
```

Should return actual train data! 🎉

## Step 9: Update Frontend

If you have a frontend, update the API base URL:

In `frontend/.env` or `frontend/.env.local`:
```
VITE_API_BASE=http://YOUR_EC2_PUBLIC_IP/api/v1
```

Or set it in your frontend code.

## Monitoring & Logs

```bash
# View app logs
sudo journalctl -u sarvorail -f

# View nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Check disk space
df -h

# Check memory/CPU
free -h
top
```

## Restarting the App

```bash
sudo systemctl restart sarvorail
```

## About Redis

AWS ElastiCache has a free tier with:
- 750 hours/month of t2.micro
- But requires VPC setup (more complex)
- Our in-memory cache is fine for now

**Recommendation**: Keep in-memory cache. It's simpler and works great. If you need distributed caching later, ElastiCache is easy to add.

## Troubleshooting

### App won't start
```bash
sudo journalctl -u sarvorail -n 50
```

### Port already in use
```bash
sudo lsof -i :8000
sudo kill -9 <PID>
```

### Permission denied
```bash
sudo chown ubuntu:ubuntu /home/ubuntu/sarvorail -R
```

### Still can't reach IRCTC
That's fixed! AWS EC2 IPs aren't blocked like Render's. Should work now.

## Cost Estimate (Monthly)

- EC2 t2.micro: $0 (free tier, 1 year)
- Data transfer: $0 (within free tier)
- **Total**: $0 for first year, ~$5-10/month after

## Next Steps

1. Launch EC2 instance
2. SSH in and follow steps 3-7
3. Test endpoints in step 8
4. Update frontend URL
5. Done! 🚀

Need help with any step? Let me know!
