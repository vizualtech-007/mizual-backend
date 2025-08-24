# Mizual Monitoring & Log Management (TESTING)

## Overview

**Status: TESTING - Implementation complete, pending verification**

Mizual uses a multi-layered monitoring approach optimized for AWS Lightsail's 2GB RAM constraint:

1. **CloudWatch Integration** - System metrics (FREE, no memory overhead)
2. **Backblaze B2 Log Shipping** - Persistent log storage
3. **Local Monitoring Tools** - Quick diagnostics
4. **Automated Alerting** - Threshold-based warnings

## Components

### 1. AWS CloudWatch Agent
- **Purpose**: Collects system metrics
- **Metrics**: CPU, Memory, Disk, Network
- **Interval**: 60 seconds
- **Cost**: FREE (included with Lightsail)
- **Memory**: ~10MB (external process)

### 2. Log Shipping to Backblaze B2
- **Schedule**: Every 30 minutes via cron  
- **Retention**: 90 days in cloud, 90 days local
- **Storage**: `s3://mizual-images/logs/[env]/[hostname]/[date]/`
- **Compression**: gzip archives with container and system logs

### 3. Local Monitoring Tools

#### Dozzle (Port 8080)
- Web UI for viewing Docker logs
- Real-time log streaming
- No authentication (secure behind firewall)

#### cAdvisor (Port 8081)
- Container resource usage
- Historical metrics (1 minute)
- REST API for metrics

#### Custom Scripts
- `/opt/mizual/check-metrics.sh` - System dashboard
- `/opt/mizual/check-alerts.sh` - Alert monitoring
- `/opt/mizual/ship-logs.sh` - Log shipping

## Setup Instructions

### Initial Setup (New Instance)

```bash
# Run the main setup script (includes monitoring)
bash /opt/mizual/lightsail-setup/setup-lightsail.sh

# Or run monitoring setup separately
bash /opt/mizual/lightsail-setup/setup-monitoring.sh
```

### Required Environment Variables

Log shipping uses existing S3 credentials from your `.env` file:
```env
# Existing S3 configuration (used for both images and logs)
S3_BUCKET_NAME=mizual-images
S3_ENDPOINT_URL=https://s3.us-east-005.backblazeb2.com
S3_ACCESS_KEY_ID=your-b2-key-id
S3_SECRET_ACCESS_KEY=your-b2-secret-key
STORAGE_PATH_PREFIX=preview  # or "production" - determines log folder
```

**Log Storage Structure:**
- Dev logs: `s3://mizual-images/logs/dev/[hostname]/[date]/`
- Prod logs: `s3://mizual-images/logs/prod/[hostname]/[date]/`

### Create Backblaze B2 Bucket

1. Log into Backblaze B2
2. Create bucket named `mizual-logs`
3. Set lifecycle: Delete files after 30 days
4. Generate application key with read/write access

## Monitoring Commands

### View System Metrics
```bash
# Live dashboard
/opt/mizual/check-metrics.sh

# Continuous monitoring
watch -n 5 /opt/mizual/check-metrics.sh

# Check specific container
docker stats mizual-backend
```

### View Logs
```bash
# Recent logs
docker logs mizual-backend --tail 100

# Follow logs
docker logs -f mizual-backend

# Web UI
http://your-server:8080  # Dozzle
```

### Check Alerts
```bash
# View alert log
tail -f /var/log/mizual-alerts.log

# Check cron jobs
crontab -l

# Verify log shipping
tail /var/log/mizual-log-shipping.log
```

### CloudWatch Metrics
```bash
# Check agent status
sudo systemctl status amazon-cloudwatch-agent

# View configuration
cat /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

# Restart agent
sudo systemctl restart amazon-cloudwatch-agent
```

## Alert Thresholds

Default thresholds configured in `/opt/mizual/check-alerts.sh`:

| Metric | Threshold | Severity |
|--------|-----------|----------|
| CPU Usage | >80% | WARNING |
| Memory Usage | >85% | WARNING |
| Disk Usage | >90% | CRITICAL |
| Container Down | Any | CRITICAL |

## CloudWatch Alarms (AWS Console)

1. Go to AWS Lightsail Console
2. Select your instance
3. Click "Monitoring" tab
4. Click "Create alarm"
5. Configure:
   - Metric: CPU utilization
   - Threshold: 80%
   - Duration: 10 minutes
   - Notification: Your email

Recommended alarms:
- CPU > 80% for 10 minutes
- Network In > 1GB/hour
- Network Out > 5GB/hour
- Status check failed

## Log Shipping Details

### Process Flow
1. Cron runs `/opt/mizual/ship-logs.sh` every 30 minutes
2. Script exports last 30 minutes of Docker logs + system alerts
3. Creates compressed archive with timestamp containing:
   - Container logs (backend, celery, registry, watchtower)
   - System alerts and warnings
4. Uploads to `s3://mizual-images/logs/[env]/[hostname]/[date]/`
5. Cleans local logs older than 90 days
6. Cleans B2 logs older than 90 days (daily at midnight)

### Manual Log Retrieval
```bash
# Set your environment and endpoint
ENV="dev"  # or "prod"
HOSTNAME=$(hostname)
ENDPOINT="https://s3.us-east-005.backblazeb2.com"

# List available dates
aws s3 ls s3://mizual-images/logs/${ENV}/${HOSTNAME}/ \
  --endpoint-url ${ENDPOINT}

# List logs for specific date
aws s3 ls s3://mizual-images/logs/${ENV}/${HOSTNAME}/2025-01-23/ \
  --endpoint-url ${ENDPOINT}

# Download specific log
aws s3 cp s3://mizual-images/logs/${ENV}/${HOSTNAME}/2025-01-23/logs-20250123_143000.tar.gz . \
  --endpoint-url ${ENDPOINT}

# Extract and view logs
tar -xzf logs-20250123_143000.tar.gz
cat backend-20250123_143000.log    # FastAPI logs
cat celery-20250123_143000.log     # Celery worker logs
cat registry-20250123_143000.log   # Registry logs
cat watchtower-20250123_143000.log # Watchtower logs
cat alerts-20250123_143000.log     # System alerts and warnings
```

## Troubleshooting

### CloudWatch Agent Not Sending Metrics
```bash
# Check IAM role (should be attached by Lightsail)
aws sts get-caller-identity

# Restart agent
sudo systemctl restart amazon-cloudwatch-agent

# Check logs
sudo tail -f /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log
```

### Log Shipping Failing
```bash
# Test S3 credentials
aws s3 ls --endpoint-url $S3_ENDPOINT_URL

# Check cron logs
grep ship-logs /var/log/cron

# Run manually
/opt/mizual/ship-logs.sh

# Check disk space
df -h
```

### High Memory Usage
```bash
# Check container memory
docker stats --no-stream

# Check Redis memory
docker exec $(docker ps -qf "name=redis") redis-cli INFO memory

# Restart containers
docker-compose -f docker-compose.zero-downtime.yml restart
```

## Monitoring Dashboard URLs

- **Dozzle (Logs)**: http://your-server:8080
- **cAdvisor (Metrics)**: http://your-server:8081
- **CloudWatch**: AWS Lightsail Console → Instance → Monitoring
- **Application Health**: http://your-server/health

## Resource Usage

Total monitoring overhead:
- CloudWatch Agent: ~10MB RAM
- Log shipping: ~5MB during compression
- Cron jobs: Negligible
- **Total**: ~15MB RAM

## Best Practices

1. **Regular Review**: Check alerts log weekly
2. **Capacity Planning**: Monitor trends in CloudWatch
3. **Log Rotation**: Ensure disk doesn't fill up
4. **Cost Control**: Monitor Backblaze B2 usage
5. **Security**: Keep monitoring ports behind firewall

## Integration with CI/CD

The monitoring setup is automatically installed during:
- New instance setup via `setup-lightsail.sh`
- Manual run of `setup-monitoring.sh`
- GitHub Actions doesn't interfere with monitoring

## Future Enhancements

- [ ] Webhook notifications for critical alerts
- [ ] Grafana dashboard integration
- [ ] Application-level metrics (API response times)
- [ ] Database query performance tracking
- [ ] Cost tracking and optimization