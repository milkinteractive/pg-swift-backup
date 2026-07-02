# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- One-shot mode via `CRON_SCHEDULE=none`: run the backup once and exit, for external schedulers like Kubernetes Jobs/CronJobs
  - Entrypoint execs backup.py directly so its exit code propagates to the container
  - Logs go to stdout; no cron, logrotate or log tailing in this mode
  - `RUN_ON_STARTUP` is ignored in one-shot mode

## [1.2.0] - 2026-02-23

### Added
- Table-level filtering with `DB_DUMP_INCLUDE_TABLES` and `DB_DUMP_EXCLUDE_TABLES` environment variables
- Log message when `SWIFT_RETENTION_DAYS=0` skips cleanup

### Fixed
- Git ignore rules for `.DS_Store` and local Claude settings

## [1.1.2] - 2024-12-16

### Added
- `_FILE` suffix support for all environment variables (Docker secrets pattern)
- Documentation for Docker Secrets and Kubernetes Secrets integration

## [1.1.1] - 2024-12-16

### Fixed
- Environment variable export in `run-backup.sh` wrapper script for cron jobs

## [1.1.0] - 2024-12-15

### Added
- Supabase CLI integration with automatic synchronization of dump scripts
- Three-part backup system: roles, schema, and data exported separately
- Multi-stage Docker build for automatic Supabase CLI script updates
- GitHub Release creation in CI/CD workflow
- New backup options: `DB_DUMP_ROLES`, `DB_DUMP_KEEP_COMMENTS`, `DB_DUMP_USE_COPY`
- Supabase configuration overrides: `DB_DUMP_INTERNAL_SCHEMAS`, `DB_DUMP_RESERVED_ROLES`, `DB_DUMP_ALLOWED_CONFIGS`

### Changed
- Renamed environment variables for better organization:
  - `BACKUP_DIR` → `DB_TMP_BACKUP_DIR`
  - `INCLUDED_SCHEMAS` → `DB_DUMP_INCLUDED_SCHEMAS`
  - `RETENTION_DAYS` → `SWIFT_RETENTION_DAYS`
- Replaced Python SQL transformations with official Supabase CLI shell scripts
- Improved SWIFT_PREFIX documentation to prevent path duplication

### Fixed
- Missing environment variables in entrypoint.sh validation

## [1.0.1] - 2024-12-14

### Fixed
- Cron job format and environment variable expansion issues

## [1.0.0] - 2024-12-14

### Added
- Initial release
- PostgreSQL backup with pg_dump
- Gzip compression for backup files
- Upload to OpenStack Swift (Infomaniak)
- Automatic cleanup of old backups based on retention policy
- Built-in cron scheduler with configurable schedule
- Log rotation to prevent disk space issues
- Docker and Docker Compose support
- GitHub Actions workflow for Docker image publishing
- Configurable `SWIFT_PREFIX` for object storage paths
- Environment variable validation on startup
- `RUN_ON_STARTUP` option for immediate backup on container start

[Unreleased]: https://github.com/milkinteractive/backup-pg-to-swift/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/milkinteractive/backup-pg-to-swift/compare/v1.1.2...v1.2.0
[1.1.2]: https://github.com/milkinteractive/backup-pg-to-swift/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/milkinteractive/backup-pg-to-swift/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/milkinteractive/backup-pg-to-swift/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/milkinteractive/backup-pg-to-swift/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/milkinteractive/backup-pg-to-swift/releases/tag/v1.0.0
