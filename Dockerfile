FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    cron \
    logrotate \
    && rm -rf /var/lib/apt/lists/*

# Create backup directory
RUN mkdir -p /backups

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Copy backup script
COPY backup.py /usr/local/bin/backup.py
RUN chmod +x /usr/local/bin/backup.py

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set timezone (can be overridden)
ENV TZ=Europe/Zurich

# Cron schedule (can be overridden)
ENV CRON_SCHEDULE="0 2 * * *"

# Run backup on container startup (can be overridden)
ENV RUN_ON_STARTUP="false"

WORKDIR /backups

# Run entrypoint script
CMD ["/usr/local/bin/entrypoint.sh"]
