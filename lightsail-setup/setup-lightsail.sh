#!/bin/bash

# Mizual Lightsail Instance Setup Script
# This script sets up both dev and production Lightsail instances
# Usage: ./setup-lightsail.sh [dev|prod]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if environment argument is provided
if [ $# -eq 0 ]; then
    print_error "Please specify environment: dev or prod"
    echo "Usage: $0 [dev|prod]"
    exit 1
fi

ENVIRONMENT=$1

if [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
    print_error "Invalid environment. Use 'dev' or 'prod'"
    exit 1
fi

print_status "Setting up Lightsail instance for $ENVIRONMENT environment"
print_status "=================================================="

# 1. Update system
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y
print_success "System updated"

# 2. Install essential packages
print_status "Installing essential packages..."
sudo apt install -y curl wget git htop nano ufw net-tools
print_success "Essential packages installed"

# 3. Install Docker
print_status "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    print_success "Docker installed"
else
    print_warning "Docker already installed"
fi

# 4. Install Docker Compose
print_status "Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    print_success "Docker Compose installed"
else
    print_warning "Docker Compose already installed"
fi

# 5. Add ubuntu user to docker group
print_status "Adding ubuntu user to docker group..."
sudo usermod -aG docker ubuntu
print_success "User added to docker group"

# 6. Start and enable Docker service
print_status "Starting Docker service..."
sudo systemctl enable docker
sudo systemctl start docker
print_success "Docker service started"

# 7. Configure firewall
print_status "Configuring firewall..."
sudo ufw --force reset
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 8080  # Dozzle logs
sudo ufw --force enable
print_success "Firewall configured"

# 8. Create application directory
print_status "Creating application directory..."
sudo mkdir -p /opt/mizual
sudo chown ubuntu:ubuntu /opt/mizual
print_success "Application directory created"

# 9. Create environment-specific .env file
print_status "Creating environment file..."
cd /opt/mizual

if [ "$ENVIRONMENT" = "dev" ]; then
    ENV_FILE=".env.preview"
    DB_SCHEMA="preview"
    STORAGE_PREFIX="preview"
    CORS_ORIGINS="https://dev.mizual.ai,http://localhost:3000"
else
    ENV_FILE=".env.production"
    DB_SCHEMA="public"
    STORAGE_PREFIX="production"
    CORS_ORIGINS="https://mizual.ai"
fi

cat > $ENV_FILE << EOF
# Mizual Backend Environment Variables - ${ENVIRONMENT^^} Environment
# Lightsail 2GB RAM, 2 vCPU

# Environment Configuration
ENVIRONMENT=$DB_SCHEMA
DATABASE_SCHEMA=$DB_SCHEMA

# Resource Configuration (Unified for 2GB RAM, 2 vCPU)
MAX_WORKERS=5
CELERY_WORKER_MEMORY_LIMIT=1GB
CELERY_CONCURRENCY=2

# Database Configuration
DATABASE_URL=postgresql://REPLACE_WITH_YOUR_SUPABASE_CONNECTION_STRING

# Queue Configuration (Local Redis on Lightsail)
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Storage Configuration
S3_ENDPOINT_URL=https://s3.us-west-004.backblazeb2.com
S3_BUCKET_NAME=mizual-images
S3_ACCESS_KEY_ID=REPLACE_WITH_YOUR_BACKBLAZE_KEY
S3_SECRET_ACCESS_KEY=REPLACE_WITH_YOUR_BACKBLAZE_SECRET
S3_REGION=us-west-004
STORAGE_PATH_PREFIX=$STORAGE_PREFIX

# API Configuration
BFL_API_KEY=REPLACE_WITH_YOUR_BFL_API_KEY
GEMINI_API_KEY=REPLACE_WITH_YOUR_GEMINI_API_KEY

# CORS Configuration
ALLOWED_ORIGINS=$CORS_ORIGINS

# Rate Limiting
RATE_LIMIT_ENABLED=true

# Image Processing
UNSUPPORTED_IMAGE_TYPES=heic,gif

# Logging
LOG_LEVEL=INFO
EOF

print_success "Environment file created: $ENV_FILE"

# 10. Set proper permissions
print_status "Setting file permissions..."
chmod 600 $ENV_FILE
chown ubuntu:ubuntu $ENV_FILE
print_success "File permissions set"

# 11. Display system information
print_status "System Information:"
echo "=================="
echo "OS: $(lsb_release -d | cut -f2)"
echo "Kernel: $(uname -r)"
echo "Docker: $(docker --version)"
echo "Docker Compose: $(docker-compose --version)"
echo "Memory: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "CPU Cores: $(nproc)"
echo "Disk Space: $(df -h / | tail -1 | awk '{print $4}' | sed 's/G/ GB/')"

print_success "=================================================="
print_success "Lightsail $ENVIRONMENT instance setup completed!"
print_success "=================================================="

print_warning "IMPORTANT: Next steps required:"
echo "1. Edit $ENV_FILE and replace placeholder values with actual credentials"
echo "2. Add DNS record in Cloudflare:"
if [ "$ENVIRONMENT" = "dev" ]; then
    echo "   - Type: A, Name: dev-api, Content: $(curl -s ifconfig.me), Proxy: Enabled"
else
    echo "   - Type: A, Name: api, Content: $(curl -s ifconfig.me), Proxy: Enabled"
fi
echo "3. Add GitHub secrets for this server:"
echo "   - LIGHTSAIL_${ENVIRONMENT^^}_HOST = $(curl -s ifconfig.me)"
echo "   - LIGHTSAIL_${ENVIRONMENT^^}_SSH_KEY = (your SSH private key)"
echo "4. Logout and login again to apply docker group membership"
echo "5. Test deployment by pushing to the appropriate branch"

print_status "You may need to logout and login again for docker group changes to take effect"
print_status "Run 'newgrp docker' or logout/login to avoid using sudo with docker commands"