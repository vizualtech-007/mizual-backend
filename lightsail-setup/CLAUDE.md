# CLAUDE.md - Lightsail Setup & Deployment

This file provides guidance to Claude Code when working with Lightsail deployment and monitoring scripts.

**Last Updated**: August 24, 2025
**Purpose**: AWS Lightsail instance setup, zero-downtime deployment, and monitoring configuration
**Status**: FULLY OPERATIONAL - Zero-downtime deployment working for both fresh instances and updates

## Overview

This directory contains scripts for setting up and managing Mizual backend deployments on AWS Lightsail instances. The deployment uses Docker with a local registry and Watchtower for zero-downtime updates.

## Infrastructure Architecture

### Zero-Downtime Deployment Components
- **Local Docker Registry** (`localhost:5000`) - Stores Docker images on the server
- **Watchtower** - Monitors registry and performs rolling updates (1-minute polling)
- **Docker Compose** - Orchestrates all services
- **GitHub Actions** - Builds and deploys images automatically

### Deployment Flow
1. GitHub Actions builds Docker image on push to `dev` or `main` branch
2. Image is transferred to Lightsail instance via SCP
3. Image is pushed to local registry at `localhost:5000`
4. Watchtower detects new image and performs rolling update
5. No downtime during the entire process

## Scripts in this Directory

### 1. setup-lightsail.sh
**Purpose**: Initial setup for new Lightsail instances
**Usage**: `bash setup-lightsail.sh`

**What it does**:
- Installs Docker and Docker Compose
- Configures firewall (ports 22, 80)
- Creates `/opt/mizual` directory structure
- Creates `/opt/mizual/registry-data` for Docker registry persistence
- Adds ubuntu user to docker group
- Completely non-interactive (no prompts)

**Important Notes**:
- Skip system upgrade to avoid SSH configuration conflicts
- Uses DEBIAN_FRONTEND=noninteractive for package installation
- Creates needrestart config to suppress restart prompts

### 2. setup-monitoring.sh
**Purpose**: Sets up monitoring and log shipping (NO CloudWatch)
**Usage**: `bash setup-monitoring.sh`

**What it does**:
- Installs AWS CLI for S3/Backblaze B2 access
- Creates monitoring scripts in `/opt/mizual-monitoring/`:
  - `ship-logs.sh` - Ships Docker logs to Backblaze B2 every 30 minutes
  - `check-alerts.sh` - Checks system health every 5 minutes
  - `check-metrics.sh` - Manual dashboard for system metrics
- Sets up cron jobs for automated monitoring
- Configures AWS credentials for root user (needed for cron)

**Log Shipping Details**:
- Destination: `s3://mizual-images/logs/{env}/{hostname}/{date}/`
- Includes: backend, celery, registry, watchtower logs
- Retention: 90 days (automatic cleanup)
- Frequency: Every 30 minutes via cron

**Alert Monitoring**:
- CPU > 80% = WARNING
- Memory > 85% = WARNING
- Disk > 90% = CRITICAL
- Container health checks
- Logs to `/var/log/mizual-alerts.log`

### 3. verify-deployment.sh
**Purpose**: Comprehensive deployment verification
**Usage**: `bash verify-deployment.sh`

**What it checks**:
1. Docker installation and service status
2. Registry and Watchtower containers
3. Application containers (backend, celery, redis)
4. API endpoints (/health, /version, /health/celery)
5. Files and directories (.env, CURRENT_VERSION, git repo)
6. Monitoring setup (scripts, cron jobs, credentials)
7. Network ports (80, 22, 5000)
8. System resources (CPU, memory, disk)
9. Recent error logs

**Output**:
- Color-coded results (green=success, yellow=warning, red=error)
- Summary with total errors and warnings
- Exit code 1 if errors found (useful for CI/CD)

## Directory Structure

```
/opt/mizual/                      # Main application directory
├── .env                          # Environment variables (from Parameter Store)
├── .git/                         # Git repository
├── CURRENT_VERSION               # Deployment version tracking
├── registry-data/                # Docker registry persistent storage
├── logs/                         # Temporary log storage (before shipping)
├── docker-compose.zero-downtime.yml
└── lightsail-setup/
    ├── setup-lightsail.sh
    ├── setup-monitoring.sh
    └── verify-deployment.sh

/opt/mizual-monitoring/           # Monitoring scripts (outside git)
├── ship-logs.sh                 # Log shipping to B2
├── check-alerts.sh              # System alert checking
└── check-metrics.sh             # Manual metrics dashboard
```

## Environment Configuration

### Source of Truth: AWS Parameter Store
All environment variables come from AWS Systems Manager Parameter Store at path `/mizual/*`

**DO NOT**:
- Hardcode environment variables in GitHub Actions
- Override Parameter Store values in deployment scripts
- Store sensitive values in GitHub Secrets (except AWS keys for deployment)

**GitHub Actions Behavior**:
- Fetches all parameters from `/mizual/*` path
- Only adds `DATABASE_SCHEMA` and `STORAGE_PATH_PREFIX` if missing
- Never overwrites existing values from Parameter Store

### Critical Environment Variables
```bash
# These MUST be in Parameter Store:
CELERY_BROKER_URL=redis://redis:6379/0  # NOT localhost!
CELERY_RESULT_BACKEND=redis://redis:6379/0
DATABASE_URL=postgresql://...
BFL_API_KEY=...
GEMINI_API_KEY=...
S3_BUCKET_NAME=mizual-images
S3_ENDPOINT_URL=https://...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...

# These are set by deployment based on branch:
DATABASE_SCHEMA=preview|public
STORAGE_PATH_PREFIX=preview|production
```

## Docker Containers

### Infrastructure Containers
- **mizual-registry**: Local Docker registry (7.4MB RAM)
- **mizual-watchtower**: Auto-updater (7.3MB RAM)
- **dozzle**: Web UI for logs on port 8080

### Application Containers  
- **mizual-backend**: FastAPI application (400MB RAM limit)
- **mizual-celery**: Async worker (600MB RAM limit)
- **redis**: Cache and message broker (200MB RAM limit)

### Container Health Checks
All containers have health checks configured:
- Backend: `curl -f http://localhost:8000/health`
- Celery: `celery inspect ping`
- Redis: `redis-cli ping`
- Registry: `wget http://localhost:5000/v2/`
- Watchtower: `/watchtower --health-check`

## Deployment Process

### First Deployment on New Instance
1. Run `setup-lightsail.sh` to install Docker
2. GitHub Actions will:
   - Clone repository to `/opt/mizual`
   - Create `.env` from Parameter Store
   - Start registry and watchtower
   - Deploy all containers

### Subsequent Deployments
1. Push to `dev` or `main` branch
2. GitHub Actions builds and transfers image
3. Image pushed to local registry
4. Watchtower detects and updates containers
5. Zero downtime throughout

### Manual Deployment Commands
```bash
# Check deployment status
./verify-deployment.sh

# View container status
docker ps

# Check version
curl http://localhost/version

# View logs
docker logs mizual-backend --tail 100

# Restart a container
docker-compose -f docker-compose.zero-downtime.yml restart backend
```

## Monitoring Without CloudWatch

### Data Flow
1. **Collection**: Cron jobs run monitoring scripts
2. **Storage**: Logs shipped to Backblaze B2
3. **Alerts**: Written to `/var/log/mizual-alerts.log`
4. **Access**: Dozzle web UI or direct log access

### No CloudWatch Agent
- CloudWatch is NOT used (cost savings)
- All metrics saved to Backblaze B2
- Local monitoring scripts handle everything

### Monitoring Access Points
- **Dozzle Web UI**: `http://[server-ip]:8080`
- **Live Metrics**: `/opt/mizual-monitoring/check-metrics.sh`
- **Alert Log**: `/var/log/mizual-alerts.log`
- **Backblaze B2**: Long-term storage for all logs

## Common Issues & Solutions

### SOLVED: .env file missing on fresh instance deployment
**Cause**: Multiple issues in deployment workflow:
1. Directory `/opt/mizual` doesn't exist when SCP tries to copy .env
2. Git clone operations were deleting the .env file after it was copied
3. Deployment scenario detection was checking for ANY mizual container instead of APPLICATION containers
4. Syntax error in bash arithmetic causing incorrect scenario detection

**Root Problem**: On fresh instances, the workflow would:
- Create .env from Parameter Store on GitHub runner
- Try to SCP to `/opt/mizual/.env` (might fail if directory doesn't exist)
- Clone git repo which would delete the .env file
- Registry/watchtower start but no application containers could run without .env
- Bash syntax error with `grep -c` output causing deployment to fail

**Solution (IMPLEMENTED & VERIFIED)**: 
1. Ensure `/opt/mizual` exists before SCP with error handling
2. Preserve .env file during git operations (no longer delete it)
3. Check specifically for backend/celery containers, not registry/watchtower
4. Fixed bash syntax error in container detection logic
5. Add verification that .env exists before Docker operations

**Final Working Implementation**:
```bash
# Before SCP, ensure directory exists
ssh "sudo mkdir -p /opt/mizual && sudo chown ubuntu:ubuntu /opt/mizual" || exit 1
scp .env user@host:/opt/mizual/.env || exit 1

# During git clone, preserve .env
if [ -f /opt/mizual/.env ]; then
  cp /opt/mizual/.env /tmp/.env.backup
fi
# ... git clone ...
if [ -f /tmp/.env.backup ]; then
  cp /tmp/.env.backup /opt/mizual/.env
fi

# Fixed detection logic - check APPLICATION containers only (no syntax errors)
BACKEND_EXISTS=$(docker ps -a --format "{{.Names}}" | grep -c "^mizual-backend$" || true)
CELERY_EXISTS=$(docker ps -a --format "{{.Names}}" | grep -c "^mizual-celery$" || true)
BACKEND_EXISTS=${BACKEND_EXISTS:-0}
CELERY_EXISTS=${CELERY_EXISTS:-0}
APP_CONTAINERS_EXIST=$((BACKEND_EXISTS + CELERY_EXISTS))
```

**Verification**: Successfully tested on both:
- Fresh Lightsail instance (first deployment)
- Existing instance (zero-downtime update)

### Issue: CURRENT_VERSION exists as directory
**Cause**: Docker creates it as directory if file doesn't exist
**Solution**: GitHub Actions now creates file before Docker starts

### Issue: Celery can't connect to Redis
**Cause**: Wrong Redis URL (localhost instead of redis)
**Solution**: Ensure Parameter Store has `redis://redis:6379/0`

### Issue: Deployment verification shows port warnings
**Cause**: Using netstat which isn't installed
**Solution**: Script now uses `ss` command instead

### Issue: Interactive prompts during setup
**Cause**: Package installation prompts
**Solution**: DEBIAN_FRONTEND=noninteractive and needrestart config

### Issue: Watchtower not updating containers
**Check**:
1. Registry has `:latest` tags: `curl http://localhost:5000/v2/mizual-backend/tags/list`
2. Containers labeled for monitoring: `com.centurylinklabs.watchtower.enable=true`
3. Watchtower logs: `docker logs mizual-watchtower --tail 20`

## Security Considerations

### Registry Security
- Only accessible on localhost:5000
- Not exposed to internet
- Persistent storage in `/opt/mizual/registry-data`

### Credentials Management
- AWS keys only in GitHub Secrets (for deployment)
- All other secrets in Parameter Store
- Root AWS credentials for cron jobs (auto-configured)

### Network Security
- Port 80: HTTP (API)
- Port 22: SSH
- Port 5000: Registry (localhost only)
- Port 8080: Dozzle (consider restricting in production)

## Resource Usage

### Total Infrastructure Overhead
- Registry: 7.4MB RAM
- Watchtower: 7.3MB RAM
- Monitoring scripts: ~5MB during execution
- **Total**: ~20MB overhead for zero-downtime capability

### Lightsail Instance Requirements
- Minimum: 2GB RAM, 2 vCPU
- Recommended: 4GB RAM for production
- Storage: 40GB minimum (for Docker images and logs)

## Maintenance Tasks

### Regular Maintenance
```bash
# Clean up old Docker images
docker system prune -af

# Check disk usage
df -h /opt/mizual/registry-data

# View recent alerts
tail -f /var/log/mizual-alerts.log

# Check cron job execution
grep mizual /var/log/syslog
```

### Log Rotation
- Backblaze B2: Automatic 90-day retention
- Local logs: Cleaned after shipping
- Alert log: Rotated at 10MB

## GitHub Actions Integration

### Workflow: deploy-zero-downtime.yml
**Triggers**: Push to `dev` or `main` branches

**Key Steps**:
1. Build ultra-slim Docker image (433MB)
2. Transfer image via SCP
3. Push to local registry
4. Wait for Watchtower update
5. Verify deployment via /version endpoint

**Important Configuration**:
- Uses Parameter Store for environment variables
- Never overwrites existing Parameter Store values
- Handles existing `/opt/mizual` directory
- Creates CURRENT_VERSION file before Docker

### GitHub Secrets Required
```
LIGHTSAIL_DEV_HOST     # Dev server IP
LIGHTSAIL_DEV_SSH_KEY  # Dev server SSH private key
LIGHTSAIL_PROD_HOST    # Prod server IP
LIGHTSAIL_PROD_SSH_KEY # Prod server SSH private key
DEV_AWS_ACCESS_KEY_ID  # For Parameter Store access
DEV_AWS_SECRET_ACCESS_KEY
PROD_AWS_ACCESS_KEY_ID
PROD_AWS_SECRET_ACCESS_KEY
```

## Testing Zero-Downtime Updates

### Verification Steps
1. Note current version: `curl http://[server-ip]/version`
2. Make a code change and push
3. Watch GitHub Actions progress
4. Monitor Watchtower: `docker logs mizual-watchtower --tail -f`
5. Verify no downtime: Keep polling `/health` endpoint
6. Confirm new version: `curl http://[server-ip]/version`

### Success Indicators
- No failed health checks during update
- Watchtower logs show "Updated" message
- New version reflected in API
- All containers healthy after update

## Important Notes

1. **Never run `apt-get upgrade`** in setup scripts - causes SSH conflicts
2. **Always use Parameter Store** for configuration - single source of truth
3. **Don't create unnecessary files** - keep scripts minimal and focused
4. **Registry data is persistent** - survives container restarts
5. **Monitoring is functional without CloudWatch** - saves costs
6. **Watchtower polls every 1 minute** - configurable in docker-compose
7. **CURRENT_VERSION must be a file** - created before Docker starts
8. **Redis URL must use hostname** - `redis://redis:6379/0` not localhost

## Support Commands

```bash
# Full system check
bash /opt/mizual/lightsail-setup/verify-deployment.sh

# Quick health check
curl http://localhost/health

# Container status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"

# Recent deployments
docker logs mizual-watchtower --tail 50 | grep Updated

# System resources
free -h && df -h && uptime
```