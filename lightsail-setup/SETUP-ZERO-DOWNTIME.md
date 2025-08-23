# Zero-Downtime Deployment Setup Instructions

## Overview
This setup enables zero-downtime deployments using a local Docker registry and Watchtower for automatic rolling updates.

## Prerequisites
- SSH access to your Lightsail servers (dev and prod)
- GitHub repository with appropriate secrets configured
- Docker and Docker Compose installed on servers

## Server Setup (Run on BOTH dev and prod servers)

### 1. Initial Setup
```bash
# SSH into your server
ssh user@your-server

# Create necessary directories
mkdir -p ~/registry-data
cd ~/

# Copy the new docker-compose file
# You'll need to upload docker-compose.zero-downtime.yml to the server
```

### 2. Create Environment File
```bash
# Copy your existing .env file
cp .env.dev .env  # or .env.prod for production

# Add registry secret (generate a strong secret)
echo "REGISTRY_SECRET=$(openssl rand -base64 32)" >> .env
```

### 3. Initial Registry and Watchtower Start
```bash
# Start registry and watchtower first
docker-compose -f docker-compose.zero-downtime.yml up -d registry watchtower

# Verify they're running
docker ps | grep -E "registry|watchtower"

# Test registry is accessible
curl http://localhost:5000/v2/_catalog
```

### 4. Initial Image Push (One-time setup)
```bash
# Build your current image
docker-compose -f docker-compose.zero-downtime.yml build backend

# Tag for registry
docker tag mizual-backend:latest localhost:5000/mizual-backend:latest

# Push to local registry
docker push localhost:5000/mizual-backend:latest

# Start all services
docker-compose -f docker-compose.zero-downtime.yml up -d
```

## GitHub Secrets Configuration

Add the following secrets to your GitHub repository (mizual-backend):

### Development Server Secrets
- `DEV_HOST` - Your dev server IP or hostname (e.g., dev-api.mizual.ai)
- `DEV_USER` - SSH username for dev server (e.g., ubuntu)
- `DEV_SSH_KEY` - Private SSH key for dev server (full key including BEGIN/END lines)
- `ENV_FILE_DEV` - Complete .env file contents for dev environment

### Production Server Secrets
- `PROD_HOST` - Your prod server IP or hostname (e.g., api.mizual.ai)
- `PROD_USER` - SSH username for prod server (e.g., ubuntu)
- `PROD_SSH_KEY` - Private SSH key for prod server (full key including BEGIN/END lines)
- `ENV_FILE_PROD` - Complete .env file contents for prod environment

### How to Add SSH Key as Secret
```bash
# On your local machine, copy your SSH private key
cat ~/.ssh/your-lightsail-key.pem

# In GitHub:
# 1. Go to Settings → Secrets and variables → Actions
# 2. Click "New repository secret"
# 3. Name: DEV_SSH_KEY (or PROD_SSH_KEY)
# 4. Value: Paste the entire private key including:
#    -----BEGIN RSA PRIVATE KEY-----
#    [key content]
#    -----END RSA PRIVATE KEY-----
```

## Testing the Setup

### 1. Manual Test (Before using GitHub Actions)
```bash
# On your local machine
cd mizual-backend

# Build with ultra-slim Dockerfile
docker build -f Dockerfile.ultra-slim -t mizual-backend:test .

# Save as tar
docker save mizual-backend:test | gzip > test-image.tar.gz

# Transfer to server
scp test-image.tar.gz user@your-server:~/

# On server
docker load < ~/test-image.tar.gz
docker tag mizual-backend:test localhost:5000/mizual-backend:test
docker push localhost:5000/mizual-backend:test

# Check if Watchtower detects it (wait up to 5 minutes)
docker logs mizual-watchtower --tail 50
```

### 2. GitHub Actions Test
```bash
# Make a small change and push to dev branch
git checkout dev
echo "# Test deployment" >> README.md
git add README.md
git commit -m "Test zero-downtime deployment"
git push origin dev

# Monitor GitHub Actions tab for workflow execution
# SSH to dev server and check logs
docker logs mizual-watchtower --tail 50 -f
```

## Monitoring Deployment

### Check Watchtower Logs
```bash
# See what Watchtower is doing
docker logs mizual-watchtower --tail 100 -f
```

### Check Container Updates
```bash
# See when containers were last updated
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
```

### Verify Zero Downtime
```bash
# During deployment, continuously check health
while true; do 
  curl -s http://localhost/health && echo " - OK" || echo " - DOWN"
  sleep 1
done
```

## Rollback Procedure

If something goes wrong:

### Quick Rollback
```bash
# Stop watchtower temporarily
docker stop mizual-watchtower

# Pull previous image from registry
docker pull localhost:5000/mizual-backend:previous-tag

# Manually update containers
docker-compose -f docker-compose.zero-downtime.yml up -d backend celery

# Restart watchtower
docker start mizual-watchtower
```

### Emergency Fallback
```bash
# Switch back to old docker-compose if needed
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Registry Connection Issues
```bash
# Check registry is running
docker ps | grep registry

# Test registry endpoint
curl http://localhost:5000/v2/_catalog

# Check registry logs
docker logs mizual-registry --tail 50
```

### Watchtower Not Updating
```bash
# Check Watchtower logs
docker logs mizual-watchtower --tail 100

# Manually trigger update
docker restart mizual-watchtower

# Verify labels on containers
docker inspect mizual-backend | grep -A 2 Labels
```

### Image Not Found
```bash
# List images in registry
curl http://localhost:5000/v2/mizual-backend/tags/list

# Check if image was pushed
docker images | grep localhost:5000
```

## Important Notes

1. **First Deployment**: The very first deployment after setup might take up to 5 minutes for Watchtower to detect
2. **Manual Override**: You can always manually update by running `docker-compose -f docker-compose.zero-downtime.yml pull && docker-compose -f docker-compose.zero-downtime.yml up -d`
3. **Registry Cleanup**: Old images are automatically cleaned up by Watchtower with `WATCHTOWER_CLEANUP=true`
4. **Security**: Registry is only accessible from localhost (127.0.0.1:5000)
5. **Monitoring**: Keep Dozzle (port 8080) and cAdvisor (port 8081) for monitoring

## Workflow Summary

1. Developer pushes code to `dev` or `main` branch
2. GitHub Actions builds ultra-slim Docker image (433MB)
3. Image is transferred to appropriate server via SSH
4. Image is pushed to local registry on server
5. Watchtower detects new image within 5 minutes
6. Watchtower performs rolling update with zero downtime
7. Old containers are replaced with new ones
8. Health checks ensure service availability

## Benefits
- Zero downtime during deployments
- Automatic rollout within 5 minutes
- No manual intervention required
- Minimal resource overhead (14.7MB total)
- Secure (registry not exposed externally)
- Easy rollback if needed