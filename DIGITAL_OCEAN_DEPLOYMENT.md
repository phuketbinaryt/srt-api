# Digital Ocean Deployment Guide

Complete guide to deploy the Audio Transcription API on a Digital Ocean droplet.

## 🚀 Quick Overview

This guide covers:
- Server setup and security
- Docker deployment (recommended)
- Manual installation
- SSL certificate setup
- Domain configuration
- Performance optimization

## 📋 Prerequisites

- Digital Ocean account
- Domain name (optional but recommended)
- SSH key pair
- Basic Linux command knowledge

## 🖥️ Server Requirements

### Minimum Specifications:
- **CPU**: 2 vCPUs
- **RAM**: 4GB (for base Whisper model)
- **Storage**: 25GB SSD
- **OS**: Ubuntu 22.04 LTS

### Recommended Specifications:
- **CPU**: 4 vCPUs
- **RAM**: 8GB (for better performance)
- **Storage**: 50GB SSD
- **OS**: Ubuntu 22.04 LTS

## 🔧 Method 1: Docker Deployment (Recommended)

### Step 1: Create Digital Ocean Droplet

1. **Create Droplet**:
   ```bash
   # Via Digital Ocean CLI (optional)
   doctl compute droplet create audio-transcription-api \
     --image ubuntu-22-04-x64 \
     --size s-2vcpu-4gb \
     --region nyc1 \
     --ssh-keys your-ssh-key-id
   ```

2. **Or use the web interface**:
   - Go to Digital Ocean dashboard
   - Click "Create" → "Droplets"
   - Choose Ubuntu 22.04 LTS
   - Select 4GB/2vCPU plan ($24/month)
   - Add your SSH key
   - Create droplet

### Step 2: Initial Server Setup

```bash
# Connect to your server
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install essential packages
apt install -y curl wget git ufw fail2ban

# Create non-root user
adduser apiuser
usermod -aG sudo apiuser

# Setup SSH for new user
mkdir -p /home/apiuser/.ssh
cp ~/.ssh/authorized_keys /home/apiuser/.ssh/
chown -R apiuser:apiuser /home/apiuser/.ssh
chmod 700 /home/apiuser/.ssh
chmod 600 /home/apiuser/.ssh/authorized_keys

# Configure firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80
ufw allow 443
ufw --force enable

# Switch to new user
su - apiuser
```

### Step 3: Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login again for group changes
exit
ssh apiuser@your-server-ip
```

### Step 4: Deploy the Application

```bash
# Clone the repository
git clone https://github.com/phuketbinaryt/srt-api.git
cd srt-api

# Create production environment file
cp .env.example .env

# Edit environment variables
nano .env
```

**Edit `.env` file**:
```env
# Server Configuration
PORT=8000
HOST=0.0.0.0

# Whisper Model (base recommended for 4GB RAM)
WHISPER_MODEL=base

# File Upload Configuration
MAX_FILE_SIZE_MB=100

# CORS Configuration (replace with your domain)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**Create `docker-compose.prod.yml`**:
```yaml
version: '3.8'

services:
  audio-transcription-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PORT=8000
      - HOST=0.0.0.0
      - WHISPER_MODEL=base
      - MAX_FILE_SIZE_MB=100
      - CORS_ORIGINS=*
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 3G
        reservations:
          memory: 1G

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - audio-transcription-api
    restart: unless-stopped
```

**Create `nginx.conf`**:
```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server audio-transcription-api:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/m;

    server {
        listen 80;
        server_name your-domain.com www.your-domain.com;

        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com www.your-domain.com;

        # SSL Configuration (add your certificates)
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        # File upload size limit
        client_max_body_size 100M;

        # API endpoints
        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeout settings for large file uploads
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }
    }
}
```

### Step 5: Deploy with Docker

```bash
# Build and start the application
docker-compose -f docker-compose.prod.yml up -d

# Check if containers are running
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

## 🔒 Method 2: SSL Certificate Setup

### Option A: Let's Encrypt (Free SSL)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Stop nginx temporarily
docker-compose -f docker-compose.prod.yml stop nginx

# Get SSL certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certificates to project directory
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/
sudo chown -R apiuser:apiuser ssl/

# Restart nginx
docker-compose -f docker-compose.prod.yml up -d nginx

# Setup auto-renewal
sudo crontab -e
# Add this line:
# 0 12 * * * /usr/bin/certbot renew --quiet && docker-compose -f /home/apiuser/srt-api/docker-compose.prod.yml restart nginx
```

### Option B: Cloudflare SSL (Alternative)

If using Cloudflare, you can use their SSL certificates and proxy features.

## 🛠️ Method 3: Manual Installation (Without Docker)

### Step 1: Install Dependencies

```bash
# Install Python and system dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg nginx

# Install Node.js (for process management)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install PM2 for process management
sudo npm install -g pm2
```

### Step 2: Setup Application

```bash
# Clone repository
git clone https://github.com/phuketbinaryt/srt-api.git
cd srt-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
nano .env
```

### Step 3: Configure PM2

**Create `ecosystem.config.js`**:
```javascript
module.exports = {
  apps: [{
    name: 'audio-transcription-api',
    script: 'python',
    args: 'start.py',
    cwd: '/home/apiuser/srt-api',
    interpreter: '/home/apiuser/srt-api/venv/bin/python',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '2G',
    env: {
      PORT: 8000,
      HOST: '0.0.0.0',
      WHISPER_MODEL: 'base',
      MAX_FILE_SIZE_MB: 100
    }
  }]
};
```

### Step 4: Start Application

```bash
# Start with PM2
pm2 start ecosystem.config.js

# Save PM2 configuration
pm2 save

# Setup PM2 to start on boot
pm2 startup
# Follow the instructions provided by the command

# Check status
pm2 status
pm2 logs audio-transcription-api
```

### Step 5: Configure Nginx

```bash
# Create nginx configuration
sudo nano /etc/nginx/sites-available/audio-transcription-api
```

**Nginx configuration**:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/audio-transcription-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 🔍 Testing Your Deployment

### Health Check
```bash
# Test API health
curl http://your-server-ip/health

# Test with domain (if configured)
curl https://yourdomain.com/health
```

### Upload Test
```bash
# Test file upload
curl -X POST "https://yourdomain.com/upload" \
     -F "file=@test-audio.mp3" \
     --output test-subtitles.srt
```

### Web Interface
Visit: `https://yourdomain.com/frontend.html`

## 📊 Monitoring and Maintenance

### Log Management
```bash
# Docker logs
docker-compose -f docker-compose.prod.yml logs -f

# PM2 logs (manual installation)
pm2 logs audio-transcription-api

# System logs
sudo journalctl -u nginx -f
```

### Performance Monitoring
```bash
# Install monitoring tools
sudo apt install -y htop iotop

# Monitor resources
htop
docker stats  # For Docker deployment
pm2 monit     # For manual deployment
```

### Backup Strategy
```bash
# Create backup script
nano backup.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/apiuser/backups"

mkdir -p $BACKUP_DIR

# Backup application
tar -czf $BACKUP_DIR/srt-api-$DATE.tar.gz /home/apiuser/srt-api

# Backup SSL certificates (if using Let's Encrypt)
sudo tar -czf $BACKUP_DIR/ssl-$DATE.tar.gz /etc/letsencrypt

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

```bash
# Make executable and schedule
chmod +x backup.sh
crontab -e
# Add: 0 2 * * * /home/apiuser/backup.sh
```

## 🚨 Security Considerations

### Firewall Rules
```bash
# Restrict SSH access (optional)
sudo ufw limit ssh

# Allow only specific IPs for SSH (optional)
sudo ufw allow from YOUR_IP_ADDRESS to any port 22
```

### Fail2Ban Configuration
```bash
# Configure fail2ban for nginx
sudo nano /etc/fail2ban/jail.local
```

```ini
[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
```

### Regular Updates
```bash
# Create update script
nano update.sh
```

```bash
#!/bin/bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Docker images (if using Docker)
cd /home/apiuser/srt-api
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# Update application code
git pull origin main

# Restart services
docker-compose -f docker-compose.prod.yml restart
# OR for manual installation:
# pm2 restart audio-transcription-api
```

## 💰 Cost Optimization

### Digital Ocean Droplet Sizes:
- **Basic (2GB RAM)**: $12/month - For testing only
- **Standard (4GB RAM)**: $24/month - Recommended minimum
- **Performance (8GB RAM)**: $48/month - For high traffic

### Additional Costs:
- **Domain**: $10-15/year
- **Load Balancer**: $12/month (for high availability)
- **Backup Storage**: $5/month for 250GB

## 🎯 Performance Tuning

### For High Traffic:
1. **Use multiple instances** with load balancer
2. **Implement Redis caching** for frequent requests
3. **Use CDN** for static files
4. **Optimize Whisper model** based on accuracy needs

### Memory Optimization:
```bash
# Add swap file for better memory management
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 🎉 Your API is Now Live!

After following this guide, your Audio Transcription API will be:
- ✅ **Deployed on Digital Ocean**
- ✅ **Secured with SSL**
- ✅ **Protected by firewall**
- ✅ **Monitored and logged**
- ✅ **Automatically backed up**
- ✅ **Production ready**

### Access Your API:
- **Web Interface**: `https://yourdomain.com/frontend.html`
- **API Documentation**: `https://yourdomain.com/docs`
- **Health Check**: `https://yourdomain.com/health`

**Your Audio Transcription API is now running on Digital Ocean!** 🚀