# PostgreSQL to OpenStack Swift Backup System

## Overview

This project provides an automated PostgreSQL backup solution that uploads backups to Infomaniak's Swift object storage. The system runs in a Docker container with a built-in cron scheduler.

## Project Structure

```
backup-pg-to-swift/
├── backup.py           # Main Python backup script
├── entrypoint.sh       # Container entrypoint with cron setup
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker Compose configuration
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (not in git)
├── .env.example        # Environment template
├── .gitignore          # Git ignore rules
├── README.md           # User documentation
└── CLAUDE.md           # This file - technical documentation
```

## Components

### 1. backup.py

**Purpose**: Main backup script that handles PostgreSQL dumps and Swift uploads

**Key Features**:
- Object-oriented design with `PostgreSQLBackup` class
- Connects to PostgreSQL and exports schema + data separately
- Applies SQL transformations (CREATE IF NOT EXISTS, etc.)
- Compresses backups with gzip
- Uploads to Swift using python-swiftclient
- Implements retention policy (deletes old backups)
- Comprehensive logging

**Key Methods**:
- `export_schema()`: Exports database schema with transformations
- `export_data()`: Exports database data
- `compress_file()`: Compresses SQL files with gzip
- `upload_to_swift()`: Uploads files to Swift storage
- `cleanup_old_backups()`: Removes backups older than RETENTION_DAYS

### 2. entrypoint.sh

**Purpose**: Container initialization script

**Responsibilities**:
- Creates cron job from `CRON_SCHEDULE` environment variable
- Generates `run-backup.sh` wrapper that exports all env vars for cron
- Sets up log rotation with logrotate
- Optionally runs backup on startup if `RUN_ON_STARTUP=true`
- Starts cron daemon and tails log file to keep container running

**Why needed**: Cron doesn't inherit environment variables, so we need the wrapper script to export them.

### 3. Dockerfile

**Base Image**: python:3.12-slim (Debian-based)

**Installed Packages**:
- `postgresql-client`: For pg_dump command
- `cron`: For scheduled backups
- `logrotate`: For log file rotation
- Python packages: python-swiftclient, python-keystoneclient

**Build Process**:
1. Install system dependencies
2. Install Python dependencies from requirements.txt
3. Copy backup.py and entrypoint.sh
4. Set default environment variables

### 4. docker-compose.yml

**Purpose**: Simplified deployment configuration

**Key Features**:
- Loads environment from `.env` file
- Mounts `./backups` for local backup storage (optional)
- Sets `restart: unless-stopped` for automatic restart
- Allows override of `CRON_SCHEDULE` and `RUN_ON_STARTUP`

## Workflow

### Startup Sequence

```
1. Docker starts container
2. entrypoint.sh executes
3. Creates cron job with CRON_SCHEDULE
4. Creates run-backup.sh wrapper
5. Sets up logrotate configuration
6. Starts cron daemon
7. (Optional) Runs backup if RUN_ON_STARTUP=true
8. Tails /var/log/pg-backup.log (keeps container running)
```

### Backup Execution

```
1. Cron triggers at scheduled time
2. Runs /usr/local/bin/run-backup.sh
3. run-backup.sh exports all environment variables
4. run-backup.sh calls backup.py
5. backup.py:
   a. Exports schema → db_schema_YYYYMMDD_HHMMSS.sql
   b. Exports data → db_backup_YYYYMMDD_HHMMSS.sql
   c. Compresses both files with gzip
   d. Uploads to Swift storage
   e. Cleans up old backups (older than RETENTION_DAYS)
   f. Removes local compressed files
6. Logs output to /var/log/pg-backup.log
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL hostname | `db.example.com` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `mydb` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `secret123` |
| `SWIFT_AUTH_URL` | Swift auth endpoint | `https://swiss-backup04.infomaniak.com/identity/v3` |
| `SWIFT_USERNAME` | Swift username | `SBI-XXXXXXX` |
| `SWIFT_PASSWORD` | Swift password | `your-password` |
| `SWIFT_CONTAINER` | Swift container name | `postgres-backups` |
| `SWIFT_TENANT_NAME` | Swift project name | `sb_project_SBI-XXXXXXX` |
| `SWIFT_REGION` | Swift region | `RegionOne` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `INCLUDED_SCHEMAS` | Schemas to backup | `public` |
| `BACKUP_DIR` | Local backup directory | `/backups` |
| `RETENTION_DAYS` | Days to keep backups | `30` |
| `TZ` | Timezone | `Europe/Zurich` |
| `CRON_SCHEDULE` | Cron expression | `0 2 * * *` |
| `RUN_ON_STARTUP` | Run on start | `false` |
| `EXTRA_FLAGS` | Extra pg_dump flags | `--column-inserts --rows-per-insert 8000` |

## pg_dump Transformations

The backup script applies several SQL transformations to make the dumps more flexible:

```sql
CREATE SCHEMA "foo"              → CREATE SCHEMA IF NOT EXISTS "foo"
CREATE TABLE "bar"               → CREATE TABLE IF NOT EXISTS "bar"
CREATE SEQUENCE "seq"            → CREATE SEQUENCE IF NOT EXISTS "seq"
CREATE VIEW "v"                  → CREATE OR REPLACE VIEW "v"
CREATE FUNCTION "f"              → CREATE OR REPLACE FUNCTION "f"
CREATE TRIGGER "t"               → CREATE OR REPLACE TRIGGER "t"
```

Additionally:
- Comments Supabase-specific statements
- Removes comment lines matching `SED_REMOVE_COMMENTS` pattern
- Wraps dumps with `SET session_replication_role = replica;` and `RESET ALL;`

## Swift Storage Structure

```
swift-container/
└── backups/
    ├── db_schema_20251104_020000.sql.gz
    ├── db_backup_20251104_020000.sql.gz
    ├── db_schema_20251105_020000.sql.gz
    ├── db_backup_20251105_020000.sql.gz
    └── ...
```

## Log Management

- Logs written to `/var/log/pg-backup.log`
- Automatically rotated by logrotate:
  - Daily rotation
  - Keep 7 days of logs
  - Compress after rotation
  - Rotate when > 10 MB
  - Delete logs older than 30 days

## Cron Schedule Examples

```
"0 2 * * *"      # Daily at 2 AM
"0 */6 * * *"    # Every 6 hours
"0 0 * * 0"      # Every Sunday at midnight
"*/30 * * * *"   # Every 30 minutes
"0 3 * * 1-5"    # Weekdays at 3 AM
```

## Deployment

### Development/Testing

```bash
# Build and run once
docker compose build
docker compose run --rm pg-backup python3 /usr/local/bin/backup.py

# Run with startup backup
docker compose run --rm -e RUN_ON_STARTUP=true pg-backup
```

### Production

```bash
# Start with automatic scheduling
docker compose up -d

# View logs
docker compose logs -f

# Restart
docker compose restart

# Stop
docker compose down
```

## Security Considerations

1. **Credentials**: Never commit `.env` file - use `.env.example` as template
2. **Database Access**: Ensure DB_USER has appropriate permissions (SELECT on schemas)
3. **Swift Access**: Use dedicated Swift credentials with minimal required permissions
4. **Container Security**: Runs as root (required for cron), consider security context
5. **Network**: Container needs outbound access to DB host and Swift endpoint

## Troubleshooting

### Container exits immediately

Check logs:
```bash
docker compose logs
```

Common causes:
- Missing required environment variables
- Invalid cron schedule syntax
- Permissions issues

### Backup fails

Check backup.py logs in container:
```bash
docker compose logs | grep ERROR
```

Common causes:
- Invalid DB credentials
- Network connectivity to DB or Swift
- Insufficient disk space
- Invalid Swift credentials

### Cron not running

Verify cron is running:
```bash
docker compose exec pg-backup ps aux | grep cron
```

Check cron job is installed:
```bash
docker compose exec pg-backup crontab -l
```

## Maintenance

### Update Python Dependencies

Edit `requirements.txt` and rebuild:
```bash
docker compose build --no-cache
```

### Change Schedule

Edit `CRON_SCHEDULE` in `.env` and restart:
```bash
docker compose restart
```

### Manual Cleanup

Remove backups older than X days:
```python
# Modify RETENTION_DAYS in .env or run manually:
docker compose exec pg-backup python3 -c "
from backup import PostgreSQLBackup
backup = PostgreSQLBackup()
backup.cleanup_old_backups()
"
```

## Future Enhancements

Potential improvements:
- [ ] Add backup encryption
- [ ] Implement backup verification
- [ ] Add Slack/email notifications
- [ ] Support for multiple databases
- [ ] Incremental backups
- [ ] Backup to multiple Swift containers
- [ ] Prometheus metrics export
- [ ] Health check endpoint

## Dependencies

### Python Packages

- `python-swiftclient==4.6.0`: Swift API client
- `python-keystoneclient==5.4.0`: OpenStack authentication

### System Packages

- `postgresql-client`: pg_dump tool
- `cron`: Task scheduler
- `logrotate`: Log file rotation

## Version History

- **v1.0**: Initial version with manual execution
- **v2.0**: Added Docker support
- **v3.0**: Added built-in cron scheduler
- **v3.1**: Added log rotation
- **v3.2**: Improved error handling and logging

## References

- [PostgreSQL pg_dump Documentation](https://www.postgresql.org/docs/current/app-pgdump.html)
- [OpenStack Swift API](https://docs.openstack.org/swift/latest/api/object_api_v1_overview.html)
- [Python swiftclient](https://docs.openstack.org/python-swiftclient/latest/)
- [Infomaniak Public Cloud](https://www.infomaniak.com/en/hosting/public-cloud)

## Support

For issues or questions:
1. Check the README.md for common solutions
2. Review logs with `docker compose logs`
3. Verify environment variables in `.env`
4. Check network connectivity to DB and Swift

## License

This project is for internal use.
