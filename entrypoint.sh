#!/bin/bash
set -e

# Validate required environment variables
REQUIRED_VARS=(
    "DB_HOST"
    "DB_PORT"
    "DB_NAME"
    "DB_USER"
    "DB_PASSWORD"
    "SWIFT_AUTH_URL"
    "SWIFT_USERNAME"
    "SWIFT_PASSWORD"
    "SWIFT_CONTAINER"
    "SWIFT_TENANT_NAME"
    "SWIFT_REGION"
)

echo "Validating required environment variables..."
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "ERROR: The following required environment variables are not set:"
    printf '  - %s\n' "${MISSING_VARS[@]}"
    echo ""
    echo "Please set these variables in your .env file or docker-compose.yml"
    exit 1
fi

echo "All required environment variables are set."
echo ""

# Create cron job from environment variable
# Default: daily at 2 AM
# Remove quotes from CRON_SCHEDULE and RUN_ON_STARTUP if present
CRON_SCHEDULE="${CRON_SCHEDULE:-0 2 * * *}"
CRON_SCHEDULE="${CRON_SCHEDULE//\"/}"  # Remove all quotes
RUN_ON_STARTUP="${RUN_ON_STARTUP//\"/}"  # Remove all quotes

echo "Setting up cron job with schedule: $CRON_SCHEDULE"

# Create cron job file with proper PATH
cat > /etc/cron.d/pg-backup << 'CRON_EOF'
# PostgreSQL Backup Cron Job
PATH=/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin
CRON_EOF

echo "$CRON_SCHEDULE root /usr/local/bin/run-backup.sh >> /var/log/pg-backup.log 2>&1" >> /etc/cron.d/pg-backup
echo "" >> /etc/cron.d/pg-backup

# Give execution rights on the cron job
chmod 0644 /etc/cron.d/pg-backup

# Create the wrapper script that sets up the environment
cat > /usr/local/bin/run-backup.sh << EOF
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
export SWIFT_PREFIX="${SWIFT_PREFIX}"
export RETENTION_DAYS="${RETENTION_DAYS}"
export TZ="${TZ}"

# Backup options
export DUMP_ROLES="${DUMP_ROLES}"
export KEEP_COMMENTS="${KEEP_COMMENTS}"
export USE_COPY="${USE_COPY}"

# Supabase configuration overrides (optional)
export DB_DUMP_INTERNAL_SCHEMAS="${DB_DUMP_INTERNAL_SCHEMAS}"
export DB_DUMP_RESERVED_ROLES="${DB_DUMP_RESERVED_ROLES}"
export DB_DUMP_ALLOWED_CONFIGS="${DB_DUMP_ALLOWED_CONFIGS}"

# Run backup
echo "=== Backup started at \$(date) ==="
/usr/local/bin/python3 /usr/local/bin/backup.py
echo "=== Backup finished at \$(date) ==="
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
