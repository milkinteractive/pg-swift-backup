# PostgreSQL to OpenStack Swift Backup System

## Overview

This project provides an automated PostgreSQL backup solution that uploads backups to Infomaniak's Swift object storage. The system runs in a Docker container with a built-in cron scheduler.

## Development Notes

**Git Commits**: This project does NOT use "Co-Authored-By: Claude" in commit messages. Keep commits clean and concise without AI attribution.

**Git Tags**: When creating a new git tag, ALWAYS check the remote tags first with `git ls-remote --tags origin` and ensure the new version is higher than the latest remote tag. Use semantic versioning (MAJOR.MINOR.PATCH). After pushing tags to remote, monitor the GitHub workflow with `gh run list --workflow docker-publish.yml --limit 1` and `gh run watch` to ensure the Docker build succeeds. `latest`, `X` and `X.Y` follow stable tags only: a pre-release tag `vX.Y.Z-rc.N` publishes just the image `X.Y.Z-rc.N` and a GitHub pre-release, so dependency updates can be tested in a dev cluster (manual Job with the image overridden) before the final tag.

**Documentation Updates**: When renaming environment variables, functions, classes, or any documented identifiers, ALWAYS update ALL documentation files:
- CLAUDE.md (this file) - Technical documentation
- README.md - User documentation
- .env.example - Environment template
- Any other files that reference the changed names

**Testing**: When testing the backup system, ALWAYS set `RUN_ON_STARTUP=true` in your .env file to verify the backup process runs correctly on container startup. This ensures the backup script executes immediately, allowing you to validate the configuration and troubleshoot any issues.

**Public Repository**: The repo and the GHCR image are public. Examples and templates use placeholders only (`your-database-host`, `SBI-XXXXXXX`); never commit real hosts, ports, account IDs or container names.

**Secret Scanning**: Enable the pre-commit hook once per clone with `git config core.hooksPath .githooks` (needs betterleaks, `brew bundle`). It rejects plaintext `.env` files, key files and tokens. `betterleaks.yml` scans the whole history on every push and PR; reviewed false positives go by fingerprint into `.betterleaksignore`.

## Project Structure

```
pg-swift-backup/
├── backup.py                        # Main Python backup script
├── entrypoint.sh                    # Container entrypoint with cron setup
├── Dockerfile                       # Multi-stage Docker build
├── docker-compose.yml               # Docker Compose configuration (build)
├── docker-compose.ghcr.yml          # Docker Compose configuration (pre-built)
├── requirements.txt                 # Python dependencies
├── supabase_defaults.py             # Auto-generated Supabase defaults
├── scripts/
│   └── extract_supabase_definitions.py  # Extracts schemas/roles from Supabase CLI
├── templates/                       # Fallback dump scripts
│   ├── dump_schema.sh
│   ├── dump_data.sh
│   └── dump_role.sh
├── .github/
│   ├── dependabot.yml               # Weekly docker/pip/actions updates
│   └── workflows/
│       ├── docker-publish.yml       # Image build + GitHub release on v* tags
│       └── betterleaks.yml          # Secret scan of the whole history on push/PR
├── .githooks/
│   └── pre-commit                   # Rejects plaintext .env, key files, tokens
├── .betterleaksignore               # Reviewed betterleaks false positives
├── .claude/settings.json            # Denies Claude reads of .env files
├── Brewfile                         # Dev tools (betterleaks)
├── .env                             # Environment variables (not in git)
├── .env.example                     # Environment template
├── .gitignore                       # Git ignore rules
├── LICENSE                          # MIT
├── THIRD_PARTY_NOTICES.md           # Supabase CLI MIT notice (also in the image)
├── README.md                        # User documentation
└── CLAUDE.md                        # This file - technical documentation
```

## Components

### 1. backup.py

**Purpose**: Main backup script that orchestrates PostgreSQL dumps and Swift uploads

**Key Features**:
- Object-oriented design with `PostgreSQLBackup` class
- Uses Supabase CLI dump scripts for production-ready exports
- Three-part backup: roles, schema, and data exported separately
- Environment variable overrides for Supabase configuration
- Compresses backups with gzip
- Uploads to Swift using python-swiftclient
- Implements retention policy (deletes old backups)
- Comprehensive logging

**Key Methods**:
- `run_dump_script()`: Executes shell dump scripts with proper environment
- `export_roles()`: Exports database roles using dump_role.sh
- `export_schema()`: Exports database schema using dump_schema.sh
- `export_data()`: Exports database data using dump_data.sh
- `compress_file()`: Compresses SQL files with gzip
- `upload_to_swift()`: Uploads files to Swift storage
- `cleanup_old_backups()`: Removes backups older than RETENTION_DAYS

**Architecture Change (v4.0)**:
- Replaced Python SQL transformations with official Supabase CLI shell scripts
- Imports `supabase_defaults.py` with fallback to hardcoded values
- Supports environment variable overrides: `DB_DUMP_INTERNAL_SCHEMAS`, `DB_DUMP_RESERVED_ROLES`, `DB_DUMP_ALLOWED_CONFIGS`

### 2. entrypoint.sh

**Purpose**: Container initialization script

**Responsibilities**:
- Creates cron job from `CRON_SCHEDULE` environment variable
- Generates `run-backup.sh` wrapper that dynamically exports all DB_* and SWIFT_* env vars for cron
- Sets up log rotation with logrotate
- Optionally runs backup on startup if `RUN_ON_STARTUP=true`
- Starts cron daemon and tails log file to keep container running

**Why needed**: Cron doesn't inherit environment variables, so we need the wrapper script to export them.

**One-Shot Mode** (v1.3.0): Setting `CRON_SCHEDULE=none` skips cron/logrotate setup entirely. After _FILE resolution and env validation, the entrypoint `exec`s backup.py directly: logs go to stdout, the backup's exit code becomes the container's exit code, and the container exits when done. Intended for Kubernetes Jobs/CronJobs where scheduling is external. `RUN_ON_STARTUP` is ignored in this mode.

**Dynamic Export** (v1.1.0): The wrapper script uses `compgen -e | grep -E '^(DB_|SWIFT_)'` to automatically export all DB_* and SWIFT_* variables, eliminating the need to manually list each variable.

### 3. Dockerfile

**Architecture**: Multi-stage Docker build

**Stage 1 (builder)**:
- Base: python:3.12-slim
- Downloads latest dump scripts from Supabase CLI GitHub:
  - `dump_schema.sh`
  - `dump_data.sh`
  - `dump_role.sh`
- Runs `extract_supabase_definitions.py` to generate `supabase_defaults.py`
- Falls back to local templates if GitHub is unreachable

**Stage 2 (production)**:
- Base: python:3.12-slim (Debian-based)
- Installed Packages:
  - `postgresql-client`: For pg_dump/pg_dumpall commands
  - `cron`: For scheduled backups
  - `logrotate`: For log file rotation
  - Python packages: python-swiftclient, python-keystoneclient
- Copies dump scripts and defaults from builder stage
- Copies backup.py and entrypoint.sh
- Copies `LICENSE` and `THIRD_PARTY_NOTICES.md` to `/usr/share/doc/pg-swift-backup/` (MIT requires the Supabase notice with the bundled scripts)
- Sets default environment variables

**Build Benefits**:
- Always uses latest Supabase CLI dump logic
- Offline build support with local fallbacks
- Production image stays clean (no curl, no build tools)

### 4. scripts/extract_supabase_definitions.py

**Purpose**: Extracts Supabase schema/role definitions from upstream CLI

**Process**:
1. Downloads `cli/internal/utils/misc.go` from Supabase CLI GitHub
2. Parses Go source code with regex to extract:
   - `InternalSchemas` (includes SystemSchemas)
   - `ReservedRoles`
   - `AllowedConfigs`
3. Generates `supabase_defaults.py` with pipe-separated values
4. Falls back to local file if GitHub unreachable

**Usage**:
```bash
python3 scripts/extract_supabase_definitions.py --output supabase_defaults.py
# Or with local file:
python3 scripts/extract_supabase_definitions.py --local path/to/misc.go
```

### 5. templates/dump_*.sh

**Purpose**: Fallback dump scripts if GitHub is unreachable during build

**Files**:
- `dump_schema.sh`: Schema export with SQL transformations
- `dump_data.sh`: Data export with session replication role
- `dump_role.sh`: Role export with pg_dumpall

**Maintenance**: Keep in sync with Supabase CLI by periodically copying from upstream

### 6. docker-compose.yml

**Purpose**: Simplified deployment configuration for building from source

**Key Features**:
- Builds image locally
- Loads environment from `.env` file
- Mounts `./backups` for local backup storage (optional)
- Sets `restart: unless-stopped` for automatic restart
- Supports backup options: `DB_DUMP_ROLES`, `DB_DUMP_KEEP_COMMENTS`, `DB_DUMP_USE_COPY`
- Allows Supabase configuration overrides

### 7. docker-compose.ghcr.yml

**Purpose**: Uses pre-built image from GitHub Container Registry

**Key Features**:
- Uses `ghcr.io/milkinteractive/pg-swift-backup:latest`
- Identical configuration to docker-compose.yml
- Faster deployment (no build required)

## Workflow

### Startup Sequence

```
1. Docker starts container
2. entrypoint.sh executes
3. Resolves _FILE environment variables (Docker secrets)
4. Validates required environment variables
5. If CRON_SCHEDULE=none: exec backup.py once, then container exits (one-shot mode)
6. Creates cron job with CRON_SCHEDULE
7. Creates run-backup.sh wrapper
8. Sets up logrotate configuration
9. Starts cron daemon
10. (Optional) Runs backup if RUN_ON_STARTUP=true
11. Tails /var/log/pg-backup.log (keeps container running)
```

### Backup Execution

```
1. Cron triggers at scheduled time
2. Runs /usr/local/bin/run-backup.sh
3. run-backup.sh exports all environment variables
4. run-backup.sh calls backup.py
5. backup.py:
   a. Exports roles → YYYYMMDD_HHMMSS_db_roles.sql (if DB_DUMP_ROLES=true)
      - Executes /usr/local/bin/dump_role.sh
      - Uses pg_dumpall --roles-only
      - Comments out reserved roles
   b. Exports schema → YYYYMMDD_HHMMSS_db_schema.sql
      - Executes /usr/local/bin/dump_schema.sh
      - Uses pg_dump --schema-only
      - Applies CREATE IF NOT EXISTS transformations
   c. Exports data → YYYYMMDD_HHMMSS_db_data.sql
      - Executes /usr/local/bin/dump_data.sh
      - Uses pg_dump --data-only
      - Excludes migration tables
   d. Compresses all files with gzip
   e. Uploads to Swift storage
   f. Cleans up old backups (older than SWIFT_RETENTION_DAYS)
   g. Removes local compressed files
6. Logs output to /var/log/pg-backup.log
```

**Three-Part Backup Benefits**:
- Flexible restore options (roles/schema/data independently)
- Faster schema-only copies for testing
- Separate role management across databases

## Environment Variables

All environment variables support the `_FILE` suffix pattern for Docker Secrets and Kubernetes Secrets. When a `VAR_FILE` is set, the value is read from the specified file path instead of from the environment variable directly.

Example: Instead of `DB_PASSWORD=secret`, use `DB_PASSWORD_FILE=/run/secrets/db_password`

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
| `DB_DUMP_INCLUDED_SCHEMAS` | Schemas to backup | `public` |
| `DB_TMP_BACKUP_DIR` | Local backup directory | `/backups` |
| `SWIFT_PREFIX` | Swift path prefix | `backups` |
| `SWIFT_RETENTION_DAYS` | Days to keep backups (`0` = keep all) | `30` |
| `TZ` | Timezone (for cron and timestamps) | `Europe/Zurich` |
| `CRON_SCHEDULE` | Cron expression (`none` = one-shot mode: run once, then exit) | `0 2 * * *` |
| `RUN_ON_STARTUP` | Run on start (cron mode only, ignored in one-shot mode) | `false` |
| `DB_DUMP_ROLES` | Export database roles | `true` |
| `DB_DUMP_KEEP_COMMENTS` | Keep SQL comments | `false` |
| `DB_DUMP_USE_COPY` | Use COPY syntax | `false` |
| `DB_DUMP_INCLUDE_TABLES` | Only backup these tables (comma-separated, mutually exclusive with EXCLUDE) | _(none)_ |
| `DB_DUMP_EXCLUDE_TABLES` | Exclude these tables (comma-separated, mutually exclusive with INCLUDE) | _(none)_ |

### Advanced Supabase Overrides

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_DUMP_INTERNAL_SCHEMAS` | Internal schemas to exclude | Auto-detected from Supabase CLI |
| `DB_DUMP_RESERVED_ROLES` | Reserved roles | Auto-detected from Supabase CLI |
| `DB_DUMP_ALLOWED_CONFIGS` | Allowed role configs | Auto-detected from Supabase CLI |

**Note**: These are automatically extracted during Docker build from Supabase CLI's `misc.go`. Only override if you have specific requirements or are using a non-Supabase PostgreSQL setup.

## Supabase CLI Integration

This project uses official dump scripts from the [Supabase CLI](https://github.com/supabase/cli) for production-ready database exports.

**Automatic Synchronization**:
- During Docker build, the latest dump scripts are downloaded from GitHub
- Schema/role definitions are extracted from `cli/internal/utils/misc.go`
- Local templates serve as fallback if GitHub is unreachable
- Ensures compatibility with Supabase managed databases

**Shell Scripts Used**:
- `dump_schema.sh`: Schema export with SQL transformations
- `dump_data.sh`: Data export excluding migration tables
- `dump_role.sh`: Role export with reserved role handling

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
└── {SWIFT_PREFIX}/
    ├── 20251106_020000_db_roles.sql.gz   # Role definitions
    ├── 20251106_020000_db_schema.sql.gz  # Schema definitions
    ├── 20251106_020000_db_data.sql.gz    # Table data
    ├── 20251107_020000_db_roles.sql.gz
    ├── 20251107_020000_db_schema.sql.gz
    ├── 20251107_020000_db_data.sql.gz
    └── ...
```

By default, `SWIFT_PREFIX` is `backups`, so files are stored under `backups/` in your Swift container. This prefix can be customized via the `SWIFT_PREFIX` environment variable.

**Three-Part Backup System**:
- `*_db_roles.sql.gz`: Database roles, users, and permissions (optional via `DUMP_ROLES`)
- `*_db_schema.sql.gz`: Tables, sequences, views, functions, triggers
- `*_db_data.sql.gz`: Actual table data

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
"none"           # One-shot mode: run once, then exit (no cron)
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

- `python-swiftclient==4.11.0`: Swift API client
- `python-keystoneclient==6.0.0`: OpenStack authentication

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
- **v4.0**: Supabase CLI integration
  - Multi-stage Docker build
  - Automatic sync with upstream Supabase CLI dump scripts
  - Three-part backup system (roles/schema/data)
  - Environment variable overrides for Supabase configuration
  - Replaced Python transformations with official shell scripts
  - Fixed missing `re` import bug
- **v1.3.0**: One-shot mode for external schedulers
  - `CRON_SCHEDULE=none` runs the backup once and exits
  - Exit code of backup.py propagates to the container (Kubernetes Job/CronJob support)
  - Logs to stdout, no cron/logrotate/log tailing in this mode

## References

- [PostgreSQL pg_dump Documentation](https://www.postgresql.org/docs/current/app-pgdump.html)
- [PostgreSQL pg_dumpall Documentation](https://www.postgresql.org/docs/current/app-pg-dumpall.html)
- [Supabase CLI](https://github.com/supabase/cli) - Official Supabase command-line tool
- [Supabase CLI Dump Scripts](https://github.com/supabase/cli/tree/main/internal/db/dump/templates)
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

MIT, see `LICENSE`. The dump scripts in `templates/` and the values in `supabase_defaults.py` come from the Supabase CLI (MIT), see `THIRD_PARTY_NOTICES.md`.

## Applied Learning

- Re-pushing `v*` tags rebuilds old images and `latest`; disable docker-publish first
