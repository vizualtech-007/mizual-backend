#!/bin/bash

# Setup monitoring and log persistence for Mizual on AWS Lightsail
# This script sets up CloudWatch monitoring and Backblaze B2 log shipping

set -e

echo "================================================"
echo "Setting up Monitoring & Log Persistence"
echo "================================================"

# 1. Install CloudWatch Agent (OS detection)
echo "Installing CloudWatch Agent..."

# Detect OS
if command -v yum &> /dev/null; then
    OS="amazon-linux"
elif command -v apt &> /dev/null; then
    OS="ubuntu"
else
    echo "Unsupported OS. This script supports Amazon Linux and Ubuntu."
    exit 1
fi

if ! command -v amazon-cloudwatch-agent &> /dev/null; then
    if [ "$OS" = "amazon-linux" ]; then
        echo "Installing on Amazon Linux..."
        sudo yum install -y amazon-cloudwatch-agent
    elif [ "$OS" = "ubuntu" ]; then
        echo "Installing on Ubuntu..."
        wget -q https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
        sudo dpkg -i amazon-cloudwatch-agent.deb
        rm -f amazon-cloudwatch-agent.deb
    fi
    echo "CloudWatch Agent installed successfully"
else
    echo "CloudWatch Agent already installed"
fi

# 2. Create CloudWatch configuration
echo "Creating CloudWatch configuration..."
sudo tee /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json > /dev/null <<'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "root"
  },
  "metrics": {
    "namespace": "Mizual",
    "metrics_collected": {
      "cpu": {
        "measurement": [
          {
            "name": "cpu_usage_idle",
            "rename": "CPU_IDLE",
            "unit": "Percent"
          },
          "cpu_usage_iowait"
        ],
        "metrics_collection_interval": 60,
        "cpu_per_core": false,
        "totalcpu": true
      },
      "disk": {
        "measurement": [
          {
            "name": "disk_used_percent",
            "rename": "DISK_USED",
            "unit": "Percent"
          },
          "disk_free"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "/"
        ]
      },
      "mem": {
        "measurement": [
          {
            "name": "mem_used_percent",
            "rename": "MEM_USED",
            "unit": "Percent"
          },
          "mem_available"
        ],
        "metrics_collection_interval": 60
      },
      "netstat": {
        "measurement": [
          {
            "name": "tcp_established",
            "rename": "TCP_CONN",
            "unit": "Count"
          }
        ],
        "metrics_collection_interval": 60
      }
    }
  }
}
EOF

# 3. Start CloudWatch Agent
echo "Starting CloudWatch Agent..."
sudo systemctl start amazon-cloudwatch-agent
sudo systemctl enable amazon-cloudwatch-agent
echo "CloudWatch Agent started and enabled"

# 4. Install AWS CLI if not present (for log shipping)
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI..."
    if [ "$OS" = "amazon-linux" ]; then
        sudo yum install -y aws-cli
    elif [ "$OS" = "ubuntu" ]; then
        sudo apt update
        sudo apt install -y awscli
    fi
    echo "AWS CLI installed successfully"
else
    echo "AWS CLI already installed"
fi

# 5. Create monitoring scripts directory (outside Git repo)
echo "Creating monitoring scripts directory..."
sudo mkdir -p /opt/mizual-monitoring

# Create log shipping script
echo "Creating log shipping script..."
sudo tee /opt/mizual-monitoring/ship-logs.sh > /dev/null <<'EOF'
#!/bin/bash

# Ship Docker logs to Backblaze B2
# Run this via cron every 30 minutes

# Load environment variables if available
if [ -f /opt/mizual/.env ]; then
    export $(grep -E '^(S3_|STORAGE_PATH_PREFIX)' /opt/mizual/.env | xargs)
fi

LOG_DIR="/opt/mizual/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_DIR=$(date +%Y-%m-%d)
ARCHIVE_NAME="logs-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="/tmp/${ARCHIVE_NAME}"
HOSTNAME=$(hostname)

# Determine environment from STORAGE_PATH_PREFIX
if [ "$STORAGE_PATH_PREFIX" = "production" ]; then
    ENV_DIR="prod"
else
    ENV_DIR="dev"
fi

# Build S3 path: logs/{env}/{hostname}/{date}/
S3_PATH="logs/${ENV_DIR}/${HOSTNAME}/${DATE_DIR}/"

# Create log directory if it doesn't exist
mkdir -p ${LOG_DIR}

# Export logs from Docker containers (last 30 minutes)
docker logs mizual-backend --since 30m > ${LOG_DIR}/backend-${TIMESTAMP}.log 2>&1
docker logs mizual-celery --since 30m > ${LOG_DIR}/celery-${TIMESTAMP}.log 2>&1
docker logs mizual-registry --since 30m > ${LOG_DIR}/registry-${TIMESTAMP}.log 2>&1
docker logs mizual-watchtower --since 30m > ${LOG_DIR}/watchtower-${TIMESTAMP}.log 2>&1

# Export system alerts log (if it exists)
if [ -f /var/log/mizual-alerts.log ]; then
    # Copy recent alerts (last 30 minutes) based on timestamp
    awk -v cutoff="$(date -d '30 minutes ago' '+%Y-%m-%d %H:%M')" '$0 >= "["cutoff {print}' /var/log/mizual-alerts.log > ${LOG_DIR}/alerts-${TIMESTAMP}.log 2>/dev/null || \
    # Fallback: copy entire alert log if timestamp parsing fails
    cp /var/log/mizual-alerts.log ${LOG_DIR}/alerts-${TIMESTAMP}.log 2>/dev/null || \
    # Create empty file if copy fails
    touch ${LOG_DIR}/alerts-${TIMESTAMP}.log
else
    # Create empty alerts file if no alerts log exists yet
    touch ${LOG_DIR}/alerts-${TIMESTAMP}.log
fi

# Create archive
tar -czf ${ARCHIVE_PATH} -C ${LOG_DIR} .

# Upload to Backblaze B2 (using existing S3 credentials)
aws s3 cp ${ARCHIVE_PATH} s3://${S3_BUCKET_NAME}/${S3_PATH} \
    --endpoint-url ${S3_ENDPOINT_URL} \
    --quiet || echo "Failed to upload logs to ${S3_PATH}"

# Clean up
rm -f ${ARCHIVE_PATH}
rm -f ${LOG_DIR}/*.log

# Clean up old local logs (keep only last 90 days)
find ${LOG_DIR} -name "*.log" -mtime +90 -delete

# Clean up old S3 logs (keep only last 90 days) - run once daily at midnight
if [ $(date +%H) -eq 0 ]; then
    # Calculate date 90 days ago
    OLD_DATE=$(date -d '90 days ago' +%Y-%m-%d)
    
    # List and delete old date directories
    aws s3 ls s3://${S3_BUCKET_NAME}/logs/${ENV_DIR}/${HOSTNAME}/ \
        --endpoint-url ${S3_ENDPOINT_URL} | \
        awk '{print $2}' | \
        while read dir; do
            dir_date=${dir%/}
            if [[ "$dir_date" < "$OLD_DATE" ]]; then
                echo "Removing old logs: ${dir_date}"
                aws s3 rm s3://${S3_BUCKET_NAME}/logs/${ENV_DIR}/${HOSTNAME}/${dir_date}/ \
                    --recursive \
                    --endpoint-url ${S3_ENDPOINT_URL} \
                    --quiet
            fi
        done
fi
EOF

sudo chmod +x /opt/mizual-monitoring/ship-logs.sh

# 6. Add cron job for log shipping (every 30 minutes)
echo "Setting up cron job for log shipping..."
(crontab -l 2>/dev/null || echo "") | grep -v ship-logs | (cat; echo "*/30 * * * * /opt/mizual-monitoring/ship-logs.sh >> /var/log/mizual-log-shipping.log 2>&1") | crontab -

# 7. Setup AWS credentials for log shipping (root user)
echo "Configuring AWS credentials for root user..."

# Extract S3 credentials from .env file
if [ -f /opt/mizual/.env ]; then
    S3_ACCESS_KEY=$(grep "^S3_ACCESS_KEY_ID=" /opt/mizual/.env | cut -d'=' -f2)
    S3_SECRET_KEY=$(grep "^S3_SECRET_ACCESS_KEY=" /opt/mizual/.env | cut -d'=' -f2)
    
    if [ ! -z "$S3_ACCESS_KEY" ] && [ ! -z "$S3_SECRET_KEY" ]; then
        # Create AWS credentials directory for root
        sudo mkdir -p /root/.aws
        
        # Create credentials file
        sudo tee /root/.aws/credentials > /dev/null <<EOF
[default]
aws_access_key_id = $S3_ACCESS_KEY
aws_secret_access_key = $S3_SECRET_KEY
EOF
        
        # Create config file
        sudo tee /root/.aws/config > /dev/null <<EOF
[default]
region = us-east-1
EOF
        
        # Set proper permissions
        sudo chmod 600 /root/.aws/credentials
        sudo chmod 600 /root/.aws/config
        
        echo "AWS credentials configured for root user"
        
        # Test S3 connection
        if [ ! -z "$(grep "^S3_ENDPOINT_URL=" /opt/mizual/.env)" ]; then
            S3_ENDPOINT=$(grep "^S3_ENDPOINT_URL=" /opt/mizual/.env | cut -d'=' -f2)
            S3_BUCKET=$(grep "^S3_BUCKET_NAME=" /opt/mizual/.env | cut -d'=' -f2)
            
            echo "Testing S3 connection..."
            if sudo aws s3 ls s3://$S3_BUCKET/ --endpoint-url $S3_ENDPOINT >/dev/null 2>&1; then
                echo "S3 connection successful"
            else
                echo "WARNING: S3 connection failed - check credentials and endpoint"
            fi
        fi
    else
        echo "WARNING: S3 credentials not found in .env file"
        echo "Log shipping will fail until credentials are configured"
    fi
else
    echo "WARNING: .env file not found at /opt/mizual/.env"
    echo "Log shipping requires S3 credentials in .env file"
fi

# 8. Create monitoring dashboard script
echo "Creating monitoring dashboard script..."
sudo tee /opt/mizual-monitoring/check-metrics.sh > /dev/null <<'EOF'
#!/bin/bash

echo "================================================"
echo "Mizual System Metrics Dashboard"
echo "================================================"
echo ""

# CPU Usage
CPU_IDLE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
echo "CPU Usage: ${CPU_IDLE}%"

# Memory Usage
MEM_INFO=$(free -m | awk 'NR==2{printf "%.1f", $3*100/$2}')
echo "Memory Usage: ${MEM_INFO}%"

# Disk Usage
DISK_USAGE=$(df -h / | awk 'NR==2{print $5}')
echo "Disk Usage: ${DISK_USAGE}"

# Docker Container Status
echo ""
echo "Container Status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Size}}" | grep -E "mizual|registry|watchtower"

# Redis Memory
echo ""
echo "Redis Memory:"
docker exec $(docker ps -qf "name=redis") redis-cli INFO memory | grep used_memory_human || echo "Redis not running"

# Recent Logs
echo ""
echo "Recent Error Logs (last 5):"
docker logs mizual-backend --tail 5 2>&1 | grep -E "ERROR|CRITICAL" || echo "No recent errors"

echo ""
echo "================================================"
echo "For detailed logs: docker logs [container-name]"
echo "For live metrics: watch -n 5 /opt/mizual-monitoring/check-metrics.sh"
echo "CloudWatch metrics available in AWS Lightsail console"
echo "================================================"
EOF

sudo chmod +x /opt/mizual-monitoring/check-metrics.sh

# 9. Set up alert thresholds notification script
echo "Creating alert notification script..."
sudo tee /opt/mizual-monitoring/check-alerts.sh > /dev/null <<'EOF'
#!/bin/bash

# Check system thresholds and log warnings
# This can be extended to send emails or webhooks

ALERT_LOG="/var/log/mizual-alerts.log"

# CPU Alert (>80% for 2 checks)
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print int(100 - $1)}')
if [ $CPU_USAGE -gt 80 ]; then
    echo "[$(date)] WARNING: High CPU usage: ${CPU_USAGE}%" >> $ALERT_LOG
fi

# Memory Alert (>85%)
MEM_USAGE=$(free -m | awk 'NR==2{printf "%d", $3*100/$2}')
if [ $MEM_USAGE -gt 85 ]; then
    echo "[$(date)] WARNING: High memory usage: ${MEM_USAGE}%" >> $ALERT_LOG
fi

# Disk Alert (>90%)
DISK_USAGE=$(df / | awk 'NR==2{print int($5)}')
if [ $DISK_USAGE -gt 90 ]; then
    echo "[$(date)] CRITICAL: High disk usage: ${DISK_USAGE}%" >> $ALERT_LOG
fi

# Container Health Check
for container in mizual-backend mizual-celery mizual-registry mizual-watchtower; do
    if ! docker ps | grep -q $container; then
        echo "[$(date)] CRITICAL: Container $container is not running" >> $ALERT_LOG
    fi
done

# Rotate alert log if it gets too large (>10MB)
if [ -f $ALERT_LOG ] && [ $(stat -c%s "$ALERT_LOG") -gt 10485760 ]; then
    mv $ALERT_LOG ${ALERT_LOG}.old
    touch $ALERT_LOG
fi
EOF

sudo chmod +x /opt/mizual-monitoring/check-alerts.sh

# Add cron job for alert checking (every 5 minutes)
(crontab -l 2>/dev/null || echo "") | grep -v check-alerts | (cat; echo "*/5 * * * * /opt/mizual-monitoring/check-alerts.sh") | crontab -

# 10. Install systemd service for monitoring persistence
echo "Installing systemd service for monitoring..."
if [ -f /opt/mizual/lightsail-setup/mizual-monitoring.service ]; then
    sudo cp /opt/mizual/lightsail-setup/mizual-monitoring.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable mizual-monitoring.service
    sudo systemctl start mizual-monitoring.service
    echo "Monitoring service installed and started"
fi

echo ""
echo "================================================"
echo "Monitoring Setup Complete!"
echo "================================================"
echo ""
echo "Available monitoring tools:"
echo "1. CloudWatch metrics: View in AWS Lightsail console"
echo "2. Live metrics: /opt/mizual-monitoring/check-metrics.sh"
echo "3. Container logs: docker logs [container-name]"
echo "4. Dozzle web UI: http://[server-ip]:8080"
echo "5. cAdvisor web UI: http://[server-ip]:8081"
echo "6. Alert log: /var/log/mizual-alerts.log"
echo ""
echo "Log shipping to Backblaze B2:"
echo "- Runs every 30 minutes via cron"
echo "- Stores in s3://mizual-images/logs/[env]/[hostname]/[date]/"
echo "- Container-specific logs (backend, celery, registry, watchtower)"
echo "- Retains logs for 90 days in B2"
echo ""
echo "To configure CloudWatch alarms:"
echo "Go to AWS Lightsail > Your Instance > Monitoring > Create Alarm"
echo ""
echo "IMPORTANT: Log shipping uses existing S3 credentials from .env:"
echo "- S3_BUCKET_NAME (same bucket as images)"
echo "- S3_ENDPOINT_URL"  
echo "- S3_ACCESS_KEY_ID"
echo "- S3_SECRET_ACCESS_KEY"
echo "- STORAGE_PATH_PREFIX (determines dev/prod log folder)"
echo "================================================"