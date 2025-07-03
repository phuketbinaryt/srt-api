#!/bin/bash

# Audio Transcription API - Digital Ocean One-Click Deployment Script
# This script automates the entire deployment process on a fresh Ubuntu 22.04 server

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_USER="apiuser"
APP_DIR="/home/$APP_USER/srt-api"
DOMAIN=""
EMAIL=""

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_status "Running as root - this is correct for initial setup"
    else
        print_error "This script must be run as root for initial setup"
        exit 1
    fi
}

# Function to get user input
get_user_input() {
    echo -e "${BLUE}=== Audio Transcription API Deployment ===${NC}"
    echo ""
    
    read -p "Enter your domain name (optional, press Enter to skip): " DOMAIN
    if [[ -n "$DOMAIN" ]]; then
        read -p "Enter your email for SSL certificate: " EMAIL
    fi
    
    echo ""
    print_status "Starting deployment..."
}

# Function to update system
update_system() {
    print_status "Updating system packages..."
    apt update && apt upgrade -y
    print_success "System updated"
}

# Function to install essential packages
install_essentials() {
    print_status "Installing essential packages..."
    apt install -y curl wget git ufw fail2ban htop unzip
    print_success "Essential packages installed"
}

# Function to create application user
create_app_user() {
    print_status "Creating application user: $APP_USER"
    
    if id "$APP_USER" &>/dev/null; then
        print_warning "User $APP_USER already exists"
    else
        adduser --disabled-password --gecos "" $APP_USER
        usermod -aG sudo $APP_USER
        print_success "User $APP_USER created"
    fi
    
    # Setup SSH keys
    if [[ -f ~/.ssh/authorized_keys ]]; then
        mkdir -p /home/$APP_USER/.ssh
        cp ~/.ssh/authorized_keys /home/$APP_USER/.ssh/
        chown -R $APP_USER:$APP_USER /home/$APP_USER/.ssh
        chmod 700 /home/$APP_USER/.ssh
        chmod 600 /home/$APP_USER/.ssh/authorized_keys
        print_success "SSH keys copied to $APP_USER"
    fi
}

# Function to configure firewall
configure_firewall() {
    print_status "Configuring firewall..."
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 80
    ufw allow 443
    ufw --force enable
    print_success "Firewall configured"
}

# Function to install Docker
install_docker() {
    print_status "Installing Docker..."
    
    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    
    # Add user to docker group
    usermod -aG docker $APP_USER
    
    # Install Docker Compose
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    
    print_success "Docker installed"
}

# Function to clone and setup application
setup_application() {
    print_status "Setting up application..."
    
    # Switch to app user for application setup
    sudo -u $APP_USER bash << EOF
cd /home/$APP_USER
git clone https://github.com/phuketbinaryt/srt-api.git
cd srt-api

# Create environment file
cp .env.example .env

# Create production docker-compose file
cat > docker-compose.prod.yml << 'DOCKER_EOF'
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
DOCKER_EOF

# Create nginx configuration
cat > nginx.conf << 'NGINX_EOF'
events {
    worker_connections 1024;
}

http {
    upstream api {
        server audio-transcription-api:8000;
    }

    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/m;

    server {
        listen 80;
        server_name _;

        client_max_body_size 100M;

        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://api;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }
    }
}
NGINX_EOF

# Create directories
mkdir -p uploads logs ssl

EOF

    print_success "Application setup completed"
}

# Function to setup SSL if domain is provided
setup_ssl() {
    if [[ -n "$DOMAIN" && -n "$EMAIL" ]]; then
        print_status "Setting up SSL certificate for $DOMAIN..."
        
        # Install certbot
        apt install -y certbot
        
        # Update nginx config for domain
        sudo -u $APP_USER bash << EOF
cd $APP_DIR
cat > nginx.conf << 'NGINX_EOF'
events {
    worker_connections 1024;
}

http {
    upstream api {
        server audio-transcription-api:8000;
    }

    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/m;

    server {
        listen 80;
        server_name $DOMAIN www.$DOMAIN;
        return 301 https://\$server_name\$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name $DOMAIN www.$DOMAIN;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        client_max_body_size 100M;

        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://api;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }
    }
}
NGINX_EOF
EOF

        # Get SSL certificate
        certbot certonly --standalone -d $DOMAIN -d www.$DOMAIN --email $EMAIL --agree-tos --non-interactive
        
        # Copy certificates
        sudo -u $APP_USER mkdir -p $APP_DIR/ssl
        cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $APP_DIR/ssl/
        cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $APP_DIR/ssl/
        chown -R $APP_USER:$APP_USER $APP_DIR/ssl
        
        # Setup auto-renewal
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet && cd $APP_DIR && docker-compose -f docker-compose.prod.yml restart nginx") | crontab -
        
        print_success "SSL certificate configured for $DOMAIN"
    else
        print_warning "No domain provided, skipping SSL setup"
    fi
}

# Function to start application
start_application() {
    print_status "Starting application..."
    
    sudo -u $APP_USER bash << EOF
cd $APP_DIR
docker-compose -f docker-compose.prod.yml up -d --build
EOF

    print_success "Application started"
}

# Function to setup monitoring
setup_monitoring() {
    print_status "Setting up monitoring and maintenance scripts..."
    
    sudo -u $APP_USER bash << EOF
cd $APP_DIR

# Create backup script
cat > backup.sh << 'BACKUP_EOF'
#!/bin/bash
DATE=\$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/$APP_USER/backups"

mkdir -p \$BACKUP_DIR

# Backup application
tar -czf \$BACKUP_DIR/srt-api-\$DATE.tar.gz $APP_DIR

# Keep only last 7 days of backups
find \$BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: \$DATE"
BACKUP_EOF

chmod +x backup.sh

# Create update script
cat > update.sh << 'UPDATE_EOF'
#!/bin/bash
cd $APP_DIR

# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build

echo "Application updated: \$(date)"
UPDATE_EOF

chmod +x update.sh

# Create status check script
cat > status.sh << 'STATUS_EOF'
#!/bin/bash
cd $APP_DIR

echo "=== Docker Containers ==="
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "=== Application Health ==="
curl -s http://localhost:8000/health | python3 -m json.tool

echo ""
echo "=== System Resources ==="
free -h
df -h /
STATUS_EOF

chmod +x status.sh

EOF

    # Schedule daily backup
    sudo -u $APP_USER bash << EOF
(crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh") | crontab -
EOF

    print_success "Monitoring and maintenance scripts created"
}

# Function to display final information
display_final_info() {
    echo ""
    echo -e "${GREEN}=== Deployment Complete! ===${NC}"
    echo ""
    
    if [[ -n "$DOMAIN" ]]; then
        echo -e "${BLUE}Your API is available at:${NC}"
        echo "  🌐 Web Interface: https://$DOMAIN/frontend.html"
        echo "  📚 API Documentation: https://$DOMAIN/docs"
        echo "  ❤️  Health Check: https://$DOMAIN/health"
    else
        SERVER_IP=$(curl -s ifconfig.me)
        echo -e "${BLUE}Your API is available at:${NC}"
        echo "  🌐 Web Interface: http://$SERVER_IP/frontend.html"
        echo "  📚 API Documentation: http://$SERVER_IP/docs"
        echo "  ❤️  Health Check: http://$SERVER_IP/health"
    fi
    
    echo ""
    echo -e "${BLUE}Useful commands:${NC}"
    echo "  📊 Check status: sudo -u $APP_USER $APP_DIR/status.sh"
    echo "  🔄 Update app: sudo -u $APP_USER $APP_DIR/update.sh"
    echo "  💾 Manual backup: sudo -u $APP_USER $APP_DIR/backup.sh"
    echo "  📋 View logs: sudo -u $APP_USER docker-compose -f $APP_DIR/docker-compose.prod.yml logs -f"
    echo "  🔧 Restart app: sudo -u $APP_USER docker-compose -f $APP_DIR/docker-compose.prod.yml restart"
    
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Test your API by uploading an audio file"
    echo "  2. Configure your domain's DNS to point to this server"
    echo "  3. Monitor the application logs for any issues"
    echo "  4. Set up additional monitoring if needed"
    
    echo ""
    print_success "Audio Transcription API is now running on Digital Ocean!"
}

# Main deployment function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           Audio Transcription API Deployment Script         ║"
    echo "║                    Digital Ocean Edition                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_root
    get_user_input
    
    print_status "Starting deployment process..."
    
    update_system
    install_essentials
    create_app_user
    configure_firewall
    install_docker
    setup_application
    setup_ssl
    start_application
    setup_monitoring
    
    # Wait a moment for services to start
    print_status "Waiting for services to start..."
    sleep 30
    
    display_final_info
}

# Run main function
main "$@"