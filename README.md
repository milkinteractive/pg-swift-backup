# PostgreSQL Backup to OpenStack Swift (Infomaniak)

Docker-based backup solution that automatically backs up PostgreSQL databases and uploads them to Infomaniak via the OpenStack Swift protocol.

## Features

- **Supabase-Optimized**: Uses official Supabase CLI dump scripts for production-ready backups
- **Three-Part Backups**: Separate exports for roles, schema, and data
- **Auto-Sync**: Dump scripts automatically synchronized with Supabase CLI during Docker build
- Automatic PostgreSQL schema, data, and role backup
- Backup file compression (gzip)
- Upload to Infomaniak via OpenStack Swift
- Automatic cleanup of old backups
- Lightweight Debian-based container
- Built-in cron scheduler
- Log rotation to prevent disk space issues
- Fully configurable via environment variables

## Prerequisites

- Docker and Docker Compose installed
- Access to PostgreSQL database
- Infomaniak OpenStack Swift credentials

## Installation

1. Clone or download this repository

2. Copy the environment template:
```bash
cp .env.example .env
```

3. Edit `.env` and configure:
   - PostgreSQL credentials
   - OpenStack Swift credentials from Infomaniak
   - Backup schedule and retention settings

## Configuration

### PostgreSQL Settings

```env
DB_HOST=your-database-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=your-username
DB_PASSWORD=your-password
```

### OpenStack Swift Settings (Infomaniak)

These values are provided by Infomaniak:

```env
SWIFT_AUTH_URL=https://swiss-backup04.infomaniak.com/identity/v3
SWIFT_USERNAME=SBI-XXXXXXX
SWIFT_PASSWORD=your-generated-password
SWIFT_CONTAINER=your-container-name
SWIFT_TENANT_NAME=sb_project_SBI-XXXXXXX
SWIFT_REGION=RegionOne
```

### Backup Configuration

- `DB_DUMP_INCLUDED_SCHEMAS`: Which schemas to backup (default: `public`)
- `DB_TMP_BACKUP_DIR`: Local directory for temporary backup files (default: `/backups`)
- `SWIFT_PREFIX`: Path prefix within Swift container (default: `backups`). Leave empty for root of container.
  - Example: `SWIFT_PREFIX=backups` stores files at `container/backups/filename.sql.gz`
  - Example: `SWIFT_PREFIX=` stores files at `container/filename.sql.gz`
- `SWIFT_RETENTION_DAYS`: How long to keep backups (default: 30 days). Set to `0` to disable cleanup (keep all backups indefinitely).
- `TZ`: Timezone for timestamps (default: `Europe/Zurich`)
- `CRON_SCHEDULE`: When to run backups (default: `"0 2 * * *"` - daily at 2 AM). Set to `none` for one-shot mode (see below).
- `RUN_ON_STARTUP`: Run backup on container start (default: `"false"`). Only relevant in cron mode; ignored when `CRON_SCHEDULE=none`.

### Backup Options

- `DB_DUMP_ROLES`: Export database roles (default: `true`)
- `DB_DUMP_KEEP_COMMENTS`: Keep SQL comments in dumps (default: `false`)
- `DB_DUMP_USE_COPY`: Use COPY instead of INSERT syntax for data (default: `false`)

### Table Filtering

You can limit the backup to specific tables or exclude certain tables. These options are mutually exclusive — only set one at a time.

- `DB_DUMP_INCLUDE_TABLES`: Comma-separated list of tables to backup (e.g., `public.users,public.orders`). Only these tables will be included in schema and data dumps.
- `DB_DUMP_EXCLUDE_TABLES`: Comma-separated list of tables to exclude (e.g., `public.logs,public.sessions`). All tables except these will be backed up.

### Supabase Configuration (Advanced)

These settings allow you to override the default Supabase schema/role patterns. If not set, the values are automatically extracted from the Supabase CLI at Docker build time.

- `DB_DUMP_INTERNAL_SCHEMAS`: Pipe-separated list of schemas to exclude (e.g., `"auth|extensions|pgbouncer|..."`)
- `DB_DUMP_RESERVED_ROLES`: Pipe-separated list of reserved roles (e.g., `"anon|authenticated|..."`)
- `DB_DUMP_ALLOWED_CONFIGS`: Pipe-separated list of allowed role configurations (e.g., `"pgaudit.*|pgrst.*|..."`)

**Note**: These are automatically set to match the Supabase CLI defaults. Only override if you have specific requirements.

## Usage

### Using Pre-built Image from GitHub Container Registry (Recommended)

The easiest way to use this backup system is with the pre-built Docker image:

```bash
# Pull the latest image
docker pull ghcr.io/milkinteractive/backup-pg-to-swift:latest

# Update docker-compose.yml to use the pre-built image
# Replace 'build: .' with:
# image: ghcr.io/milkinteractive/backup-pg-to-swift:latest

# Start the container
docker compose up -d

# View logs
docker compose logs -f

# Stop the container
docker compose down
```

### Building from Source

Alternatively, build the image yourself:

```bash
# Build and start the container
docker compose build
docker compose up -d

# View logs
docker compose logs -f

# Stop the container
docker compose down
```

The backup schedule can be configured in `docker-compose.yml` or `.env`:

```yaml
environment:
  CRON_SCHEDULE: "0 2 * * *"  # Daily at 2 AM
  RUN_ON_STARTUP: "false"     # Run backup on startup
```

#### Cron Schedule Examples

```bash
"0 2 * * *"      # Daily at 2 AM
"0 */6 * * *"    # Every 6 hours
"0 0 * * 0"      # Every Sunday at midnight
"*/30 * * * *"   # Every 30 minutes
"0 3 * * 1-5"    # Monday to Friday at 3 AM
```

### One-Shot Mode (Kubernetes)

Set `CRON_SCHEDULE=none` to run the backup exactly once and exit. No cron daemon is started, logs go directly to stdout, and the backup's exit code becomes the container's exit code. This is intended for environments where scheduling is handled externally, e.g. a Kubernetes `CronJob`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pg-backup
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: pg-backup
              image: ghcr.io/milkinteractive/backup-pg-to-swift:latest
              env:
                - name: CRON_SCHEDULE
                  value: "none"
                # ... DB_* and SWIFT_* variables (or _FILE variants with mounted secrets)
```

Since the container exits with a non-zero code on failure, Kubernetes correctly reports failed backups (`backoffLimit`, alerting, etc.).

**Note**: With Docker Compose, use `docker compose run --rm -e CRON_SCHEDULE=none pg-backup` for one-shot mode — not `docker compose up`, because `restart: unless-stopped` would restart the container after every run.

### Manual Backup

For one-time backup without cron:

```bash
# One-shot mode via entrypoint (includes _FILE resolution and env validation)
docker compose run --rm -e CRON_SCHEDULE=none pg-backup

# Or run the backup script directly
docker compose run --rm pg-backup python3 /usr/local/bin/backup.py
```

## Backup Structure

Backups are stored in Swift with the following format:

```
{SWIFT_PREFIX}/
  YYYYMMDD_HHMMSS_db_roles.sql.gz   # Role definitions (if DUMP_ROLES=true)
  YYYYMMDD_HHMMSS_db_schema.sql.gz  # Schema definitions
  YYYYMMDD_HHMMSS_db_data.sql.gz    # Table data
```

By default, `SWIFT_PREFIX` is `backups`, so files are stored under `backups/` in your Swift container.

### Three-Part Backup System

1. **Roles** (`*_db_roles.sql.gz`): Database roles, users, and permissions
2. **Schema** (`*_db_schema.sql.gz`): Tables, sequences, views, functions, triggers
3. **Data** (`*_db_data.sql.gz`): Actual table data

This separation allows for flexible restore scenarios:
- Restore only schema to create a new empty database
- Restore roles separately to set up permissions
- Restore data without recreating existing schema

## Logs and Monitoring

To view backup logs:

```bash
# View logs
docker compose logs

# Follow logs in real-time
docker compose logs -f

# View only last 100 lines
docker compose logs --tail=100
```

Log files are automatically rotated to prevent disk space issues:
- Maximum log size: 10 MB
- Logs kept for: 7 days
- Compressed after rotation

## Restore

To restore a backup:

```bash
# 1. Download backups from Swift
swift download CONTAINER_NAME backups/YYYYMMDD_HHMMSS_db_roles.sql.gz
swift download CONTAINER_NAME backups/YYYYMMDD_HHMMSS_db_schema.sql.gz
swift download CONTAINER_NAME backups/YYYYMMDD_HHMMSS_db_data.sql.gz

# 2. Decompress
gunzip *_db_roles.sql.gz
gunzip *_db_schema.sql.gz
gunzip *_db_data.sql.gz

# 3. Restore to database (in order)
psql -h HOST -p PORT -U USER -d postgres < *_db_roles.sql     # Restore roles (to postgres db)
psql -h HOST -p PORT -U USER -d DATABASE < *_db_schema.sql    # Restore schema
psql -h HOST -p PORT -U USER -d DATABASE < *_db_data.sql      # Restore data
```

### Partial Restore

You can also restore only specific parts:

```bash
# Only restore schema (create empty database)
psql -h HOST -p PORT -U USER -d DATABASE < *_db_schema.sql

# Only restore roles
psql -h HOST -p PORT -U USER -d postgres < *_db_roles.sql

# Only restore data (assumes schema already exists)
psql -h HOST -p PORT -U USER -d DATABASE < *_db_data.sql
```

## Troubleshooting

### Database connection fails
- Check DB credentials in `.env` file
- Ensure database is accessible from the container

### Swift upload fails
- Verify Swift credentials
- Test connection manually with `swift` CLI tool
- Ensure the container exists or has permission to create it

### Backup is very large
- Consider reducing `RETENTION_DAYS`
- Check if all schemas are actually needed

### Container exits immediately
- Check logs with `docker compose logs`
- Verify `.env` file exists and is properly formatted
- Ensure all required environment variables are set

## Security

- The `.env` file contains sensitive data and should NOT be committed to Git
- Ensure only authorized persons have access to backup files
- Use strong passwords for PostgreSQL and Swift

### Docker Secrets Support

All environment variables support the `_FILE` suffix pattern for Docker Secrets and Kubernetes Secrets:

```yaml
# docker-compose.yml with Docker Secrets
services:
  pg-backup:
    image: ghcr.io/milkinteractive/backup-pg-to-swift:latest
    environment:
      DB_HOST: db.example.com
      DB_PORT: 5432
      DB_NAME: postgres
      DB_USER: postgres
      DB_PASSWORD_FILE: /run/secrets/db_password
      SWIFT_PASSWORD_FILE: /run/secrets/swift_password
      # ... other variables
    secrets:
      - db_password
      - swift_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
  swift_password:
    file: ./secrets/swift_password.txt
```

When a `_FILE` variant is set, the value is read from the specified file path. This is more secure than passing secrets directly as environment variables.

## Architecture

```
┌─────────────────┐
│  Docker         │
│  Container      │
│                 │
│  ┌───────────┐ │
│  │   Cron    │ │  Schedule: 0 2 * * *
│  └─────┬─────┘ │
│        │       │
│  ┌─────▼─────┐ │
│  │  Backup   │ │  Python Script
│  │  Script   │ │
│  └─────┬─────┘ │
│        │       │
│        ├──────────► PostgreSQL Database
│        │       │
│        └──────────► Swift Storage (Infomaniak)
│                 │
└─────────────────┘
```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL host | `db.example.com` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `postgres` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `secret` |
| `SWIFT_AUTH_URL` | Swift authentication URL | `https://swiss-backup04.infomaniak.com/identity/v3` |
| `SWIFT_USERNAME` | Swift username | `SBI-XXXXXXX` |
| `SWIFT_PASSWORD` | Swift password | `your-password` |
| `SWIFT_CONTAINER` | Swift container name | `my-backups` |
| `SWIFT_TENANT_NAME` | Swift tenant/project name | `sb_project_SBI-XXXXXXX` |
| `SWIFT_REGION` | Swift region | `RegionOne` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_DUMP_INCLUDED_SCHEMAS` | Schemas to backup | `public` |
| `DB_TMP_BACKUP_DIR` | Local backup directory | `/backups` |
| `SWIFT_PREFIX` | Swift path prefix | `backups` |
| `SWIFT_RETENTION_DAYS` | Days to keep backups (`0` = keep all) | `30` |
| `TZ` | Timezone | `Europe/Zurich` |
| `CRON_SCHEDULE` | Cron schedule (`none` = one-shot mode: run once, then exit) | `"0 2 * * *"` |
| `RUN_ON_STARTUP` | Run on container start (cron mode only) | `"false"` |
| `DB_DUMP_ROLES` | Export database roles | `true` |
| `DB_DUMP_KEEP_COMMENTS` | Keep SQL comments | `false` |
| `DB_DUMP_USE_COPY` | Use COPY syntax | `false` |
| `DB_DUMP_INCLUDE_TABLES` | Only backup these tables (comma-separated) | _(none)_ |
| `DB_DUMP_EXCLUDE_TABLES` | Exclude these tables (comma-separated) | _(none)_ |

### Advanced Supabase Overrides

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_DUMP_INTERNAL_SCHEMAS` | Internal schemas to exclude | Auto-detected from Supabase CLI |
| `DB_DUMP_RESERVED_ROLES` | Reserved roles | Auto-detected from Supabase CLI |
| `DB_DUMP_ALLOWED_CONFIGS` | Allowed configurations | Auto-detected from Supabase CLI |

## Supabase CLI Integration

This backup solution uses the official dump scripts from the [Supabase CLI](https://github.com/supabase/cli) for production-grade database exports.

### Automatic Synchronization

During Docker build, the latest dump scripts are automatically downloaded from the Supabase CLI repository:

- `dump_schema.sh` - Schema export with proper transformations
- `dump_data.sh` - Data export excluding migration tables
- `dump_role.sh` - Role export with reserved role handling

Schema and role definitions are also extracted from `cli/internal/utils/misc.go` to ensure compatibility with Supabase's managed platform.

### Fallback Templates

Local template files are included as fallback if GitHub is unreachable during build. These are stored in the `templates/` directory and are kept in sync with the Supabase CLI.

### Manual Synchronization

To manually update the templates to the latest Supabase CLI version:

```bash
cd backup-pg-to-swift
python3 scripts/extract_supabase_definitions.py --output supabase_defaults.py
docker compose build --no-cache
```

This ensures your backup solution always uses the latest Supabase-compatible dump logic.

## Contributing

Enable the pre-commit hook once per clone. It rejects plaintext `.env` files,
key files and tokens before they are committed and needs
[betterleaks](https://github.com/betterleaks/betterleaks) (`brew bundle`):

```bash
git config core.hooksPath .githooks
```

A betterleaks job in GitHub Actions scans the whole history on every push and
pull request.

## License

[MIT](LICENSE) © Milk Interactive AG

The dump scripts and Supabase defaults come from the
[Supabase CLI](https://github.com/supabase/cli) (MIT), see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
