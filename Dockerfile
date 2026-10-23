# Base image pinned by digest (both stages): a rebuild then really pulls the
# Debian security fixes instead of a cached layer, and Dependabot (docker
# ecosystem) proposes the digest refreshes.
# Stage 1: Download Supabase CLI dump scripts and generate defaults
FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704 AS builder

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy local templates and defaults as fallback
COPY templates/ /build/templates/
COPY scripts/extract_supabase_definitions.py /build/
COPY supabase_defaults.py /tmp/supabase_defaults.py

# Download latest dump scripts from Supabase CLI
# Fall back to local templates if download fails
RUN curl -fsSL https://raw.githubusercontent.com/supabase/cli/main/internal/db/dump/templates/dump_schema.sh \
    -o /tmp/dump_schema.sh || cp /build/templates/dump_schema.sh /tmp/dump_schema.sh

RUN curl -fsSL https://raw.githubusercontent.com/supabase/cli/main/internal/db/dump/templates/dump_data.sh \
    -o /tmp/dump_data.sh || cp /build/templates/dump_data.sh /tmp/dump_data.sh

RUN curl -fsSL https://raw.githubusercontent.com/supabase/cli/main/internal/db/dump/templates/dump_role.sh \
    -o /tmp/dump_role.sh || cp /build/templates/dump_role.sh /tmp/dump_role.sh

RUN chmod +x /tmp/dump_*.sh

# Try to generate latest Python defaults from Supabase CLI misc.go
# If it fails, the local supabase_defaults.py (copied above) will be used
RUN python3 extract_supabase_definitions.py --output /tmp/supabase_defaults.py || \
    echo "Warning: Could not download latest definitions, using bundled defaults" >&2

# Stage 2: Production image
FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704

# Install system dependencies. postgresql-client comes from the PGDG repo:
# pg_dump/pg_dumpall must be >= the server's major version, and Debian's
# bundled client (17) cannot dump PostgreSQL 18 servers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y \
    postgresql-client-18 \
    cron \
    logrotate \
    && rm -rf /var/lib/apt/lists/*

# Create backup directory
RUN mkdir -p /backups

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Copy dump scripts from builder stage
COPY --from=builder /tmp/dump_*.sh /usr/local/bin/

# Copy supabase defaults (either generated during build, or local fallback)
COPY --from=builder /tmp/supabase_defaults.py /usr/local/bin/supabase_defaults.py

# Copy backup script
COPY backup.py /usr/local/bin/backup.py
RUN chmod +x /usr/local/bin/backup.py

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /backups

# Run entrypoint script
CMD ["/usr/local/bin/entrypoint.sh"]
