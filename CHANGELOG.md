# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.2] - 2026-11-09

### Security
- Rebuilt on the `python:3.12-slim` of 2026-11-05: Python 3.12.16 and the
  Debian 13 security updates since 2026-10-21 (tested with `1.5.2-rc.1` on a
  plain PostgreSQL and a Supabase database; identical dump sizes).

## [1.5.1] - 2026-11-06

### Changed
- `python-swiftclient` 4.11.0 and `python-keystoneclient` 6.0.0 (Keystone v3
  auth and uploads tested against Infomaniak Swift with `1.5.1-rc.1`).

### Security
- `certifi>=2026.10.23`.

### Fixed
- `latest`, `X` and `X.Y` image tags follow stable release tags only; a
  pre-release tag (`vX.Y.Z-rc.N`) publishes just its own image tag. The
  release notes pull the image tag without the `v` prefix.

## [1.5.0] - 2026-11-05

### Changed
- Repository and image renamed to `pg-swift-backup`, now public: pull
  `ghcr.io/milkinteractive/pg-swift-backup`. The license files ship under
  `/usr/share/doc/pg-swift-backup/`.

## [1.4.2] - 2026-11-05

### Added
- MIT license (`LICENSE`). The Supabase CLI notice for the bundled dump
  scripts and defaults is in `THIRD_PARTY_NOTICES.md`; both ship in the image
  under `/usr/share/doc/backup-pg-to-swift/`.

## [1.4.1] - 2026-10-23

### Security
- Rebuilt on the current `python:3.12-slim` (Debian 13 security updates,
  among them perl and libunbound with Critical CVEs); the base image is now
  pinned by digest in both stages.
- `certifi>=2026.10.19` (no longer trusts the compromised eMudhra/emSign
  intermediate CA) and `urllib3>=2.8.0`.

### Added
- Dependabot version updates (`.github/dependabot.yml`) for the base image
  digest, pip and GitHub Actions.

## [1.4.0] - 2026-08-05

### Changed
- PostgreSQL client 18 from the PGDG apt repository (Debian 13 ships 17):
  `pg_dumpall` refuses servers newer than itself, so dumping a PostgreSQL 18
  server failed with "server version mismatch". pg_dump 18 still dumps
  all older servers, so existing users (Supabase 15/17) are unaffected.

## [1.3.0] - 2026-07-02

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

[Unreleased]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.5.2...HEAD
[1.5.2]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.4.2...v1.5.0
[1.4.2]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.1.2...v1.2.0
[1.1.2]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/milkinteractive/pg-swift-backup/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/milkinteractive/pg-swift-backup/releases/tag/v1.0.0
