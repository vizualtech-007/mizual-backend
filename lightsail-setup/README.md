# Mizual Lightsail Setup Scripts

This folder contains scripts to set up both development and production Lightsail instances for the Mizual project.

## 📋 Prerequisites

- Fresh Ubuntu 22.04 LTS Lightsail instance (2GB RAM, 2 vCPU)
- SSH access to the instance
- Root/sudo privileges

## 🚀 Quick Setup

### For Development Instance (13.234.238.48)
```bash
# Copy script to server
scp setup-lightsail.sh ubuntu@13.234.238.48:~/

# SSH into server and run
ssh ubuntu@13.234.238.48
chmod +x setup-lightsail.sh
./setup-lightsail.sh dev
```

### For Production Instance (3.110.210.9)
```bash
# Copy script to server
scp setup-lightsail.sh ubuntu@3.110.210.9:~/

# SSH into server and run
ssh ubuntu@3.110.210.9
chmod +x setup-lightsail.sh
./setup-lightsail.sh prod
```

## 🛠️ What the Script Does

### System Setup
- ✅ Updates system packages
- ✅ Installs essential tools (curl, wget, git, htop, nano, ufw)
- ✅ Installs Docker and Docker Compose
- ✅ Adds ubuntu user to docker group
- ✅ Starts and enables Docker service

### Security Configuration
- ✅ Configures UFW firewall (ports 22, 80, 8080)
- ✅ Sets proper file permissions

### Application Setup
- ✅ Creates `/opt/mizual` directory
- ✅ Creates environment-specific `.env` file
- ✅ Sets up proper directory ownership

## 📁 Files Created

### Development Environment
- **File**: `/opt/mizual/.env.preview`
- **Database Schema**: `preview`
- **Storage Path**: `mizual-images/preview/`
- **CORS**: Includes dev frontend URLs

### Production Environment
- **File**: `/opt/mizual/.env.production`
- **Database Schema**: `public`
- **Storage Path**: `mizual-images/production/`
- **CORS**: Production frontend URLs only

## ⚙️ Post-Setup Configuration

### 1. Update Environment Variables
Edit the created `.env` file and replace placeholder values:

```bash
# On the server
sudo nano /opt/mizual/.env.preview    # For dev
sudo nano /opt/mizual/.env.production # For prod
```

**Replace these placeholders:**
- `REPLACE_WITH_YOUR_SUPABASE_CONNECTION_STRING`
- `REPLACE_WITH_YOUR_BACKBLAZE_KEY`
- `REPLACE_WITH_YOUR_BACKBLAZE_SECRET`
- `REPLACE_WITH_YOUR_BFL_API_KEY`
- `REPLACE_WITH_YOUR_GEMINI_API_KEY`

### 2. Configure Cloudflare DNS

**For Development:**
- Type: `A`
- Name: `dev-api`
- Content: `13.234.238.48`
- Proxy: ✅ Enabled (Orange cloud)

**For Production:**
- Type: `A`
- Name: `api`
- Content: `3.110.210.9`
- Proxy: ✅ Enabled (Orange cloud)

### 3. Add GitHub Secrets

Add these secrets to your GitHub repository (Settings > Secrets and variables > Actions):

**Development:**
- `LIGHTSAIL_DEV_HOST` = `13.234.238.48`
- `LIGHTSAIL_DEV_SSH_KEY` = (your SSH private key)

**Production:**
- `LIGHTSAIL_PROD_HOST` = `3.110.210.9`
- `LIGHTSAIL_PROD_SSH_KEY` = (your SSH private key)

### 4. Test Docker Access
```bash
# Logout and login again, or run:
newgrp docker

# Test docker without sudo
docker --version
docker-compose --version
```

## 🔍 Verification

### Check Services
```bash
# Docker status
sudo systemctl status docker

# Firewall status
sudo ufw status

# Directory permissions
ls -la /opt/mizual/
```

### Test Deployment
```bash
# Push to dev branch (deploys to dev server)
git push origin dev

# Push to main branch (deploys to prod server)
git push origin main
```

### Health Checks
```bash
# After deployment
curl https://dev-api.mizual.ai/health    # Dev
curl https://api.mizual.ai/health        # Prod
```

## 🚨 Troubleshooting

### Docker Permission Issues
```bash
# If you get permission denied errors
sudo usermod -aG docker ubuntu
newgrp docker
# Or logout and login again
```

### Firewall Issues
```bash
# Check firewall status
sudo ufw status verbose

# Reset firewall if needed
sudo ufw --force reset
sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 8080
sudo ufw --force enable
```

### Environment File Issues
```bash
# Check file exists and permissions
ls -la /opt/mizual/.env.*
cat /opt/mizual/.env.preview    # or .env.production
```

## 📊 Monitoring

After deployment, access monitoring dashboards:
- **Dev Logs**: `http://dev-logs.mizual.ai:8080`
- **Prod Logs**: `http://logs.mizual.ai:8080`

## 🔄 Updates

To update the setup script or configuration:
1. Update the script in this repository
2. Copy the updated script to servers
3. Re-run if needed (script is idempotent)

## 📞 Support

If you encounter issues:
1. Check the script output for error messages
2. Verify all prerequisites are met
3. Ensure proper network connectivity
4. Check GitHub Actions logs for deployment issues