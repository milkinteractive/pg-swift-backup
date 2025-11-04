# PostgreSQL Backup to OpenStack Swift (Infomaniak)

Docker-based backup solution that automatically backs up PostgreSQL databases and uploads them to Infomaniak via the OpenStack Swift protocol.

## Features

- Automatic PostgreSQL schema and data backup
- Backup file compression (gzip)
- Upload to Infomaniak via OpenStack Swift
- Automatic cleanup of old backups
- Lightweight Alpine/Debian-based container
- Built-in cron scheduler
- Log rotation to prevent disk space issues
- Configurable via environment variables

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

- `INCLUDED_SCHEMAS`: Which schemas to backup (default: `public`)
- `RETENTION_DAYS`: How long to keep backups (default: 30 days)
- `TZ`: Timezone for timestamps (default: `Europe/Zurich`)
- `CRON_SCHEDULE`: When to run backups (default: `"0 2 * * *"` - daily at 2 AM)
- `RUN_ON_STARTUP`: Run backup on container start (default: `"false"`)

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

### Manual Backup

For one-time backup without cron:

```bash
# Manual backup
docker compose run --rm pg-backup python3 /usr/local/bin/backup.py
```

## Backup Structure

Backups are stored in the following format:

```
backups/
  YYYYMMDD_HHMMSS_db_schema.sql.gz  # Schema backup
  YYYYMMDD_HHMMSS_db_backup.sql.gz  # Data backup
```

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
# 1. Download backup from Swift
swift download CONTAINER_NAME backups/YYYYMMDD_HHMMSS_db_schema.sql.gz
swift download CONTAINER_NAME backups/YYYYMMDD_HHMMSS_db_backup.sql.gz

# 2. Decompress
gunzip *_db_schema.sql.gz
gunzip *_db_backup.sql.gz

# 3. Restore to database
psql -h HOST -p PORT -U USER -d DATABASE < *_db_schema.sql
psql -h HOST -p PORT -U USER -d DATABASE < *_db_backup.sql
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

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DB_HOST` | PostgreSQL host | - | Yes |
| `DB_PORT` | PostgreSQL port | - | Yes |
| `DB_NAME` | Database name | - | Yes |
| `DB_USER` | Database user | - | Yes |
| `DB_PASSWORD` | Database password | - | Yes |
| `SWIFT_AUTH_URL` | Swift authentication URL | - | Yes |
| `SWIFT_USERNAME` | Swift username | - | Yes |
| `SWIFT_PASSWORD` | Swift password | - | Yes |
| `SWIFT_CONTAINER` | Swift container name | - | Yes |
| `SWIFT_TENANT_NAME` | Swift tenant/project name | - | Yes |
| `SWIFT_REGION` | Swift region | - | Yes |
| `INCLUDED_SCHEMAS` | Schemas to backup | `public` | No |
| `BACKUP_DIR` | Local backup directory | `/backups` | No |
| `RETENTION_DAYS` | Days to keep backups | `30` | No |
| `TZ` | Timezone | `Europe/Zurich` | No |
| `CRON_SCHEDULE` | Cron schedule | `"0 2 * * *"` | No |
| `RUN_ON_STARTUP` | Run on container start | `"false"` | No |

## License

This script is for internal use.
