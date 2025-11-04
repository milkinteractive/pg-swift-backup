#!/bin/bash
set -e

# Create cron job from environment variable
# Default: täglich um 2 Uhr nachts
# Remove quotes from CRON_SCHEDULE and RUN_ON_STARTUP if present
CRON_SCHEDULE="${CRON_SCHEDULE:-0 2 * * *}"
CRON_SCHEDULE="${CRON_SCHEDULE//\"/}"  # Remove all quotes
RUN_ON_STARTUP="${RUN_ON_STARTUP//\"/}"  # Remove all quotes

echo "Setting up cron job with schedule: $CRON_SCHEDULE"

# Create cron job file
cat > /etc/cron.d/pg-backup << EOF
# PostgreSQL Backup Cron Job
$CRON_SCHEDULE root /usr/local/bin/run-backup.sh >> /var/log/pg-backup.log 2>&1

EOF

# Give execution rights on the cron job
chmod 0644 /etc/cron.d/pg-backup

# Create the wrapper script that sets up the environment
cat > /usr/local/bin/run-backup.sh << 'EOF'
#!/bin/bash
# Export all environment variables for cron
export DB_HOST="${DB_HOST}"
export DB_PORT="${DB_PORT}"
export DB_NAME="${DB_NAME}"
export DB_USER="${DB_USER}"
export DB_PASSWORD="${DB_PASSWORD}"
export SWIFT_AUTH_URL="${SWIFT_AUTH_URL}"
export SWIFT_USERNAME="${SWIFT_USERNAME}"
export SWIFT_PASSWORD="${SWIFT_PASSWORD}"
export SWIFT_CONTAINER="${SWIFT_CONTAINER}"
export SWIFT_TENANT_NAME="${SWIFT_TENANT_NAME}"
export SWIFT_REGION="${SWIFT_REGION}"
export INCLUDED_SCHEMAS="${INCLUDED_SCHEMAS}"
export BACKUP_DIR="${BACKUP_DIR}"
export RETENTION_DAYS="${RETENTION_DAYS}"
export TZ="${TZ}"

# Run backup
echo "=== Backup started at $(date) ==="
python3 /usr/local/bin/backup.py
echo "=== Backup finished at $(date) ==="
echo ""
EOF

chmod +x /usr/local/bin/run-backup.sh

# Create log file with rotation configuration
touch /var/log/pg-backup.log
chmod 0666 /var/log/pg-backup.log

# Setup logrotate for backup log
cat > /etc/logrotate.d/pg-backup << 'LOGROTATE_EOF'
/var/log/pg-backup.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    size 10M
    maxage 30
}
LOGROTATE_EOF

# Add logrotate to daily cron
echo "0 0 * * * root /usr/sbin/logrotate /etc/logrotate.conf" >> /etc/cron.d/pg-backup

# Apply cron job
crontab /etc/cron.d/pg-backup

# Start cron in the background first
cron

echo "Starting cron daemon..."
echo "Backup schedule: $CRON_SCHEDULE"
echo "RUN_ON_STARTUP: $RUN_ON_STARTUP"

# If RUN_ON_STARTUP is set to "true", run backup immediately
if [ "${RUN_ON_STARTUP}" = "true" ]; then
    echo "Running backup on startup..."
    /usr/local/bin/run-backup.sh
fi

echo "Logs will appear below:"
echo "---"

# Tail the log file to keep the container running and show output
tail -f /var/log/pg-backup.log
