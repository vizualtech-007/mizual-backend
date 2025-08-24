#!/bin/bash

# Mizual Deployment Verification Script
# This script checks if all components are properly deployed and running
# Usage: ./verify-deployment.sh

# Don't exit on error - we want to check everything
set +e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

print_status() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Track overall status
ERRORS=0
WARNINGS=0

# Start verification
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          MIZUAL DEPLOYMENT VERIFICATION SCRIPT               ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo -e "Started at: $(date)"

# 1. Check Docker Installation
print_header "1. DOCKER INSTALLATION"
print_status "Checking Docker installation..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_success "Docker installed: $DOCKER_VERSION"
else
    print_error "Docker is not installed"
    ((ERRORS++))
fi

print_status "Checking Docker Compose installation..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    print_success "Docker Compose installed: $COMPOSE_VERSION"
else
    print_error "Docker Compose is not installed"
    ((ERRORS++))
fi

print_status "Checking Docker service status..."
if systemctl is-active docker >/dev/null 2>&1; then
    print_success "Docker service is running"
else
    print_error "Docker service is not running"
    ((ERRORS++))
fi

# 2. Check Registry and Watchtower
print_header "2. ZERO-DOWNTIME INFRASTRUCTURE"
print_status "Checking Docker Registry..."
if docker ps | grep -q mizual-registry; then
    REGISTRY_STATUS=$(docker ps --format "table {{.Status}}" --filter "name=mizual-registry" | tail -1)
    print_success "Registry running: $REGISTRY_STATUS"
    
    # Check registry accessibility
    if curl -f -s http://localhost:5000/v2/ > /dev/null; then
        print_success "Registry API accessible at localhost:5000"
    else
        print_error "Registry API not accessible"
        ((ERRORS++))
    fi
    
    # Check registry has images
    BACKEND_TAGS=$(curl -s http://localhost:5000/v2/mizual-backend/tags/list 2>/dev/null | grep -o '"tags":\[[^]]*\]' || echo "")
    if [[ $BACKEND_TAGS == *"latest"* ]]; then
        print_success "Registry has mizual-backend:latest image"
    else
        print_warning "Registry missing mizual-backend:latest image"
        ((WARNINGS++))
    fi
else
    print_error "Registry container not running"
    ((ERRORS++))
fi

print_status "Checking Watchtower..."
if docker ps | grep -q mizual-watchtower; then
    WATCHTOWER_STATUS=$(docker ps --format "table {{.Status}}" --filter "name=mizual-watchtower" | tail -1)
    print_success "Watchtower running: $WATCHTOWER_STATUS"
    
    # Check last Watchtower scan
    LAST_SCAN=$(docker logs mizual-watchtower --tail 100 2>&1 | grep -E "Scanned" | tail -1 || echo "No scan logs found")
    echo "  Last scan: $LAST_SCAN"
else
    print_error "Watchtower container not running"
    ((ERRORS++))
fi

# 3. Check Application Containers
print_header "3. APPLICATION CONTAINERS"
CONTAINERS=("mizual-backend" "mizual-celery" "redis")

for container in "${CONTAINERS[@]}"; do
    print_status "Checking $container..."
    if docker ps 2>/dev/null | grep -q "$container"; then
        STATUS=$(docker ps --format "table {{.Status}}" --filter "name=$container" 2>/dev/null | tail -1)
        IMAGE=$(docker ps --format "table {{.Image}}" --filter "name=$container" 2>/dev/null | tail -1)
        print_success "$container running"
        echo "  Status: $STATUS"
        echo "  Image: $IMAGE"
        
        # Check container health if available - handle redis specially as it may not have container name
        if [[ "$container" == "redis" ]]; then
            # Find redis container by image name
            REDIS_CONTAINER=$(docker ps --format "{{.Names}}" --filter "ancestor=redis" 2>/dev/null | head -1)
            if [ ! -z "$REDIS_CONTAINER" ]; then
                HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$REDIS_CONTAINER" 2>/dev/null || echo "no healthcheck")
            else
                HEALTH="no healthcheck"
            fi
        else
            HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no healthcheck")
        fi
        
        if [ "$HEALTH" = "healthy" ]; then
            print_success "  Health: $HEALTH"
        elif [ "$HEALTH" = "no healthcheck" ]; then
            echo "  Health: No healthcheck configured"
        else
            print_warning "  Health: $HEALTH"
            ((WARNINGS++))
        fi
    else
        print_error "$container not running"
        ((ERRORS++))
    fi
done

# 4. Check API Health
print_header "4. API HEALTH"
print_status "Checking API health endpoint..."
if curl -f -s http://localhost/health > /dev/null; then
    HEALTH_RESPONSE=$(curl -s http://localhost/health)
    print_success "API health endpoint responding"
    echo "  Response: $HEALTH_RESPONSE"
else
    print_error "API health endpoint not responding"
    ((ERRORS++))
fi

print_status "Checking API version endpoint..."
if VERSION_RESPONSE=$(curl -s http://localhost/version 2>/dev/null); then
    if echo "$VERSION_RESPONSE" | grep -q "version_tag"; then
        VERSION_TAG=$(echo "$VERSION_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version_tag','unknown'))" 2>/dev/null || echo "parse error")
        print_success "Version endpoint responding"
        echo "  Deployed version: $VERSION_TAG"
    else
        print_warning "Version endpoint returned unexpected response"
        ((WARNINGS++))
    fi
else
    print_error "Version endpoint not responding"
    ((ERRORS++))
fi

print_status "Checking Celery health..."
if curl -f -s http://localhost/health/celery > /dev/null; then
    CELERY_HEALTH=$(curl -s http://localhost/health/celery)
    print_success "Celery health endpoint responding"
    echo "  Response: $CELERY_HEALTH"
else
    print_warning "Celery health endpoint not responding"
    ((WARNINGS++))
fi

# 5. Check Files and Directories
print_header "5. FILES AND DIRECTORIES"
print_status "Checking /opt/mizual directory..."
if [ -d /opt/mizual ]; then
    print_success "/opt/mizual directory exists"
    
    # Check git repository
    if [ -d /opt/mizual/.git ]; then
        cd /opt/mizual
        BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
        COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
        print_success "Git repository initialized"
        echo "  Branch: $BRANCH"
        echo "  Commit: $COMMIT"
        cd - > /dev/null
    else
        print_error "Git repository not initialized in /opt/mizual"
        ((ERRORS++))
    fi
    
    # Check .env file
    if [ -f /opt/mizual/.env ]; then
        ENV_LINES=$(wc -l < /opt/mizual/.env)
        print_success ".env file exists ($ENV_LINES lines)"
    else
        print_error ".env file not found"
        ((ERRORS++))
    fi
    
    # Check CURRENT_VERSION file
    if [ -f /opt/mizual/CURRENT_VERSION ]; then
        print_success "CURRENT_VERSION file exists"
        echo "  Content:"
        cat /opt/mizual/CURRENT_VERSION | sed 's/^/    /'
    elif [ -d /opt/mizual/CURRENT_VERSION ]; then
        print_error "CURRENT_VERSION exists as directory (should be file)"
        ((ERRORS++))
    else
        print_warning "CURRENT_VERSION file not found"
        ((WARNINGS++))
    fi
    
    # Check registry data directory
    if [ -d /opt/mizual/registry-data ]; then
        REGISTRY_SIZE=$(du -sh /opt/mizual/registry-data 2>/dev/null | cut -f1)
        print_success "Registry data directory exists (Size: $REGISTRY_SIZE)"
    else
        print_warning "Registry data directory not found"
        ((WARNINGS++))
    fi
else
    print_error "/opt/mizual directory not found"
    ((ERRORS++))
fi

# 6. Check Monitoring Setup
print_header "6. MONITORING SETUP"

# Check monitoring directory
print_status "Checking monitoring directory..."
if [ -d /opt/mizual-monitoring ]; then
    print_success "Monitoring directory exists"
    MONITOR_FILES=$(ls -la /opt/mizual-monitoring 2>/dev/null | wc -l)
    echo "  Contains $((MONITOR_FILES-3)) files"
else
    print_warning "Monitoring directory /opt/mizual-monitoring not found"
    ((WARNINGS++))
fi

print_status "Checking monitoring scripts..."
if [ -f /opt/mizual-monitoring/ship-logs.sh ]; then
    print_success "Log shipping script exists"
    if [ -x /opt/mizual-monitoring/ship-logs.sh ]; then
        print_success "  Script is executable"
    else
        print_warning "  Script is not executable"
        ((WARNINGS++))
    fi
else
    print_warning "Log shipping script not found at /opt/mizual-monitoring/ship-logs.sh"
    echo "  Monitoring may not have been set up yet"
    ((WARNINGS++))
fi

if [ -f /opt/mizual-monitoring/check-alerts.sh ]; then
    print_success "Alert checking script exists"
    if [ -x /opt/mizual-monitoring/check-alerts.sh ]; then
        print_success "  Script is executable"
    else
        print_warning "  Script is not executable"
        ((WARNINGS++))
    fi
else
    print_warning "Alert checking script not found at /opt/mizual-monitoring/check-alerts.sh"
    echo "  Monitoring may not have been set up yet"
    ((WARNINGS++))
fi

if [ -f /opt/mizual-monitoring/check-metrics.sh ]; then
    print_success "Metrics dashboard script exists"
else
    print_warning "Metrics dashboard script not found"
    ((WARNINGS++))
fi

print_status "Checking cron jobs for ubuntu user..."
# Check cron jobs as ubuntu user (not root)
CRON_OUTPUT=$(crontab -l 2>/dev/null || echo "")
if echo "$CRON_OUTPUT" | grep -q "ship-logs.sh"; then
    print_success "Log shipping cron job configured"
    CRON_JOBS=$(echo "$CRON_OUTPUT" | grep -c mizual-monitoring)
    echo "  Found $CRON_JOBS monitoring cron jobs:"
    echo "$CRON_OUTPUT" | grep mizual-monitoring | sed 's/^/    /'
else
    print_warning "Log shipping cron job not configured for ubuntu user"
    echo "  Run: bash /opt/mizual/lightsail-setup/setup-monitoring.sh"
    ((WARNINGS++))
fi

# CloudWatch agent removed - using custom monitoring with Backblaze B2

# Check AWS credentials for log shipping
print_status "Checking AWS credentials for log shipping..."
if [ -f /root/.aws/credentials ]; then
    print_success "Root AWS credentials configured (for cron jobs)"
else
    if sudo test -f /root/.aws/credentials; then
        print_success "Root AWS credentials configured (for cron jobs)"
    else
        print_warning "Root AWS credentials not found - log shipping may fail"
        echo "  The setup-monitoring.sh script should configure this from .env file"
        ((WARNINGS++))
    fi
fi

# Check log directories
print_status "Checking log directories..."
if [ -d /opt/mizual/logs ]; then
    LOG_COUNT=$(ls -la /opt/mizual/logs 2>/dev/null | wc -l)
    print_success "Log directory exists with $((LOG_COUNT-3)) files"
else
    echo "  Log directory /opt/mizual/logs not found (will be created on first run)"
fi

# Check for Dozzle (log viewer)
print_status "Checking Dozzle log viewer..."
if docker ps 2>/dev/null | grep -q "dozzle"; then
    print_success "Dozzle container is running (port 8080)"
else
    print_warning "Dozzle container not running - web log viewer unavailable"
    ((WARNINGS++))
fi

# 7. Check Network and Ports
print_header "7. NETWORK AND PORTS"
print_status "Checking exposed ports..."

# Use ss instead of netstat (netstat not installed by default on Ubuntu)
PORTS_TO_CHECK="80 22"
for port in $PORTS_TO_CHECK; do
    if ss -tuln 2>/dev/null | grep -q ":$port " || sudo lsof -i:$port 2>/dev/null | grep -q LISTEN; then
        print_success "Port $port is listening"
    else
        print_warning "Port $port is not listening"
        ((WARNINGS++))
    fi
done

# Check if port 5000 is only on localhost
if ss -tuln 2>/dev/null | grep -q "127.0.0.1:5000" || sudo lsof -i:5000 2>/dev/null | grep -q "localhost"; then
    print_success "Registry port 5000 bound to localhost only (secure)"
else
    print_warning "Registry port 5000 not found or misconfigured"
    ((WARNINGS++))
fi

# 8. Check System Resources
print_header "8. SYSTEM RESOURCES"
print_status "Checking system resources..."
MEMORY_USAGE=$(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2}')
DISK_USAGE=$(df -h / | awk 'NR==2{print $5}')
CPU_LOAD=$(uptime | awk -F'load average:' '{print $2}')

echo "  Memory Usage: $MEMORY_USAGE"
echo "  Disk Usage: $DISK_USAGE"
echo "  CPU Load:$CPU_LOAD"

# Check if memory usage is high
MEM_PERCENT=$(free -m | awk 'NR==2{printf "%d", $3*100/$2}')
if [ $MEM_PERCENT -gt 85 ]; then
    print_warning "High memory usage detected (>85%)"
    ((WARNINGS++))
else
    print_success "Memory usage is acceptable"
fi

# Check if disk usage is high
DISK_PERCENT=$(df / | awk 'NR==2{print int($5)}')
if [ $DISK_PERCENT -gt 90 ]; then
    print_error "Critical disk usage (>90%)"
    ((ERRORS++))
elif [ $DISK_PERCENT -gt 80 ]; then
    print_warning "High disk usage (>80%)"
    ((WARNINGS++))
else
    print_success "Disk usage is acceptable"
fi

# 9. Recent Logs Check
print_header "9. RECENT LOGS"
print_status "Checking for recent errors..."
ERROR_COUNT=0
for container in mizual-backend mizual-celery; do
    if docker ps | grep -q $container; then
        RECENT_ERRORS=$(docker logs $container --tail 100 2>&1 | grep -iE "error|critical|exception" | wc -l)
        if [ $RECENT_ERRORS -gt 0 ]; then
            print_warning "$container has $RECENT_ERRORS error messages in last 100 lines"
            ((WARNINGS++))
            ERROR_COUNT=$((ERROR_COUNT + RECENT_ERRORS))
        fi
    fi
done

if [ $ERROR_COUNT -eq 0 ]; then
    print_success "No recent errors in application logs"
fi

# Final Summary
print_header "VERIFICATION SUMMARY"
echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    ALL CHECKS PASSED!                        ║${NC}"
    echo -e "${GREEN}║              Deployment is fully operational                 ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║               DEPLOYMENT OPERATIONAL WITH WARNINGS           ║${NC}"
    echo -e "${YELLOW}║                   $WARNINGS warning(s) found                            ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                  DEPLOYMENT ISSUES DETECTED                  ║${NC}"
    echo -e "${RED}║          $ERRORS error(s) and $WARNINGS warning(s) found                    ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
fi

echo ""
echo "Errors: $ERRORS"
echo "Warnings: $WARNINGS"
echo "Completed at: $(date)"

# Exit with error code if there are errors
if [ $ERRORS -gt 0 ]; then
    exit 1
else
    exit 0
fi