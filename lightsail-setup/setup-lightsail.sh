#!/bin/bash

# Mizual US-East-2 Lightsail Instance Setup Script
# Simplified setup for new us-east-2 instance
# Usage: ./setup-lightsail.sh

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_status "Setting up Mizual Lightsail instance in us-east-2"
print_status "=================================================="

# 1. Update system
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y
print_success "System updated"

# 2. Install essential packages (minimal set)
print_status "Installing essential packages..."
sudo apt install -y curl git htop ufw
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
sudo ufw --force enable
print_success "Firewall configured"

# 8. Create application directory
print_status "Creating application directory..."
sudo mkdir -p /opt/mizual
sudo chown ubuntu:ubuntu /opt/mizual
print_success "Application directory created"

# 9. Setup directory structure
print_status "Setting up directory structure..."
cd /opt/mizual
print_success "Directory setup complete"

# 10. Display system information
print_status "System Information:"
echo "=================="
echo "OS: $(lsb_release -d | cut -f2)"
echo "Docker: $(docker --version)"
echo "Docker Compose: $(docker-compose --version)"
echo "Memory: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "CPU Cores: $(nproc)"
echo "Public IP: $(curl -s ifconfig.me)"

print_success "=================================================="
print_success "Lightsail us-east-2 instance setup completed!"
print_success "=================================================="

print_status "Next steps:"
echo "1. Your environment files are managed by GitHub Actions"
echo "2. Update GitHub secrets with this server IP: $(curl -s ifconfig.me)"
echo "3. Logout and login again to apply docker group membership"
echo "4. Test deployment by pushing to dev/main branch"

print_status "Run 'newgrp docker' or logout/login to use docker without sudo"