#!/usr/bin/env python3
"""
PostgreSQL Backup to OpenStack Swift
Backs up PostgreSQL database and uploads to Infomaniak Swift storage
Uses Supabase CLI dump scripts for production-ready database exports
"""

import os
import sys
import subprocess
import gzip
import shutil
import re
from datetime import datetime, timedelta
from pathlib import Path
import logging

from swiftclient.service import SwiftService, SwiftUploadObject
from swiftclient import ClientException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import Supabase defaults (can be overridden via environment variables)
try:
    sys.path.insert(0, '/usr/local/bin')
    from supabase_defaults import (
        DEFAULT_INTERNAL_SCHEMAS,
        DEFAULT_RESERVED_ROLES,
        DEFAULT_ALLOWED_CONFIGS
    )
except ImportError:
    # Fallback if import fails
    logger.warning("Could not import supabase_defaults, using hardcoded fallbacks")
    DEFAULT_INTERNAL_SCHEMAS = "auth|extensions|pgbouncer|realtime|_realtime|storage|_analytics|supabase_functions|supabase_migrations|information_schema|pg_*|cron|graphql|graphql_public|net|pgsodium|pgsodium_masks|pgtle|repack|tiger|tiger_data|timescaledb_*|_timescaledb_*|topology|vault"
    DEFAULT_RESERVED_ROLES = "anon|authenticated|authenticator|dashboard_user|pgbouncer|postgres|service_role|supabase_admin|supabase_auth_admin|supabase_functions_admin|supabase_read_only_user|supabase_replication_admin|supabase_storage_admin|pgsodium_keyholder|pgsodium_keyiduser|pgsodium_keymaker|pgtle_admin"
    DEFAULT_ALLOWED_CONFIGS = "pgaudit.*|pgrst.*|session_replication_role|statement_timeout|track_io_timing"


class PostgreSQLBackup:
    """Handles PostgreSQL backup and Swift upload"""

    def __init__(self):
        """Initialize backup configuration from environment variables"""
        # PostgreSQL settings
        self.db_host = self.get_env('DB_HOST')
        self.db_port = self.get_env('DB_PORT')
        self.db_name = self.get_env('DB_NAME')
        self.db_user = self.get_env('DB_USER')
        self.db_password = self.get_env('DB_PASSWORD')

        # Swift settings
        self.swift_auth_url = self.get_env('SWIFT_AUTH_URL')
        self.swift_username = self.get_env('SWIFT_USERNAME')
        self.swift_password = self.get_env('SWIFT_PASSWORD')
        self.swift_container = self.get_env('SWIFT_CONTAINER')
        self.swift_region = self.get_env('SWIFT_REGION')
        self.swift_tenant_name = self.get_env('SWIFT_TENANT_NAME')

        # Backup settings
        self.backup_dir = Path(os.getenv('DB_TMP_BACKUP_DIR', '/backups'))
        self.swift_prefix = os.getenv('SWIFT_PREFIX', 'backups')
        self.included_schemas = os.getenv('DB_DUMP_INCLUDED_SCHEMAS', 'public')
        self.retention_days = int(os.getenv('SWIFT_RETENTION_DAYS', '30'))

        # Supabase dump configuration (override via environment or use defaults)
        self.internal_schemas = os.getenv('DB_DUMP_INTERNAL_SCHEMAS', DEFAULT_INTERNAL_SCHEMAS)
        self.reserved_roles = os.getenv('DB_DUMP_RESERVED_ROLES', DEFAULT_RESERVED_ROLES)
        self.allowed_configs = os.getenv('DB_DUMP_ALLOWED_CONFIGS', DEFAULT_ALLOWED_CONFIGS)

        # Dump options
        self.dump_roles = os.getenv('DB_DUMP_ROLES', 'true').lower() == 'true'
        self.keep_comments = os.getenv('DB_DUMP_KEEP_COMMENTS', 'false').lower() == 'true'
        self.use_copy = os.getenv('DB_DUMP_USE_COPY', 'false').lower() == 'true'

        # Shell script paths
        self.dump_schema_script = '/usr/local/bin/dump_schema.sh'
        self.dump_data_script = '/usr/local/bin/dump_data.sh'
        self.dump_role_script = '/usr/local/bin/dump_role.sh'

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    @staticmethod
    def get_env(key):
        """Get required environment variable or raise error"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value

    def run_dump_script(self, script_path, additional_env=None):
        """Execute dump shell script with proper environment"""
        try:
            # Base environment for PostgreSQL connection
            env = {
                **os.environ,
                'PGHOST': self.db_host,
                'PGPORT': self.db_port,
                'PGUSER': self.db_user,
                'PGPASSWORD': self.db_password,
                'PGDATABASE': self.db_name,
            }

            # Add additional environment variables
            if additional_env:
                env.update(additional_env)

            logger.debug(f"Running dump script: {script_path}")
            result = subprocess.run(
                ['bash', script_path],
                check=True,
                capture_output=True,
                text=True,
                env=env
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Dump script failed: {e.stderr}")
            raise

    def export_roles(self):
        """Export database roles using dump_role.sh"""
        logger.info("Exporting database roles...")

        role_file = self.backup_dir / f"{self.timestamp}_db_roles.sql"

        # Prepare environment for dump script
        env = {
            'RESERVED_ROLES': self.reserved_roles,
            'ALLOWED_CONFIGS': self.allowed_configs,
        }

        # Add comment removal if needed
        if not self.keep_comments:
            env['EXTRA_SED'] = '/^--/d'

        # Run dump script
        output = self.run_dump_script(self.dump_role_script, env)

        # Write to file
        with open(role_file, 'w') as f:
            f.write(output)

        file_size = role_file.stat().st_size
        logger.info(f"Role export completed: {file_size / 1024:.2f} KB")

        return role_file

    def export_schema(self):
        """Export database schema using dump_schema.sh"""
        logger.info("Exporting database schema...")

        schema_file = self.backup_dir / f"{self.timestamp}_db_schema.sql"

        # Prepare environment for dump script
        env = {
            'EXCLUDED_SCHEMAS': self.internal_schemas,
            'INCLUDED_SCHEMAS': self.included_schemas,
        }

        # Add extension flag if dumping all schemas
        if self.included_schemas == '*':
            env['EXTRA_FLAGS'] = '--extension=*'

        # Add comment removal if needed
        if not self.keep_comments:
            env['EXTRA_SED'] = '/^--/d'

        # Run dump script
        output = self.run_dump_script(self.dump_schema_script, env)

        # Write to file
        with open(schema_file, 'w') as f:
            f.write(output)

        file_size = schema_file.stat().st_size
        logger.info(f"Schema export completed: {file_size / 1024 / 1024:.2f} MB")

        return schema_file

    def export_data(self):
        """Export database data using dump_data.sh"""
        logger.info("Exporting database data...")

        data_file = self.backup_dir / f"{self.timestamp}_db_data.sql"

        # Prepare environment for dump script
        env = {
            'EXCLUDED_SCHEMAS': self.internal_schemas,
            'INCLUDED_SCHEMAS': self.included_schemas,
        }

        # Configure data export format
        extra_flags = []
        if not self.use_copy:
            # Use INSERT statements instead of COPY
            extra_flags.extend(['--column-inserts', '--rows-per-insert 8000'])

        if extra_flags:
            env['EXTRA_FLAGS'] = ' '.join(extra_flags)

        # Run dump script
        output = self.run_dump_script(self.dump_data_script, env)

        # Write to file
        with open(data_file, 'w') as f:
            f.write(output)

        file_size = data_file.stat().st_size
        logger.info(f"Data export completed: {file_size / 1024 / 1024:.2f} MB")

        return data_file

    def compress_file(self, file_path):
        """Compress file with gzip"""
        logger.info(f"Compressing {file_path.name}...")

        gz_file = Path(str(file_path) + '.gz')

        with open(file_path, 'rb') as f_in:
            with gzip.open(gz_file, 'wb', compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove original file
        file_path.unlink()

        file_size = gz_file.stat().st_size
        logger.info(f"Compression completed: {file_size / 1024 / 1024:.2f} MB")

        return gz_file

    def get_swift_options(self):
        """Get Swift authentication options"""
        options = {
            'auth_version': '3',
            'os_auth_url': self.swift_auth_url,
            'os_username': self.swift_username,
            'os_password': self.swift_password,
        }

        if self.swift_tenant_name:
            options['os_tenant_name'] = self.swift_tenant_name

        if self.swift_region:
            options['os_region_name'] = self.swift_region

        return options

    def upload_to_swift(self, file_path):
        """Upload file to Swift storage"""
        logger.info(f"Uploading {file_path.name} to Swift...")

        options = self.get_swift_options()
        swift_service = SwiftService(options=options)

        object_name = f"{self.swift_prefix}/{file_path.name}"

        upload_object = SwiftUploadObject(
            source=str(file_path),
            object_name=object_name
        )

        try:
            for result in swift_service.upload(
                container=self.swift_container,
                objects=[upload_object]
            ):
                if not result['success']:
                    raise ClientException(f"Upload failed: {result.get('error')}")

            logger.info(f"Upload completed: {object_name}")
        except ClientException as e:
            logger.error(f"Swift error: {e}")
            raise

    def cleanup_old_backups(self):
        """Remove old backups from Swift"""
        if self.retention_days <= 0:
            return

        logger.info(f"Cleaning up backups older than {self.retention_days} days...")

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        cutoff_str = cutoff_date.strftime('%Y%m%d')

        options = self.get_swift_options()
        swift_service = SwiftService(options=options)

        try:
            # List objects in container
            list_options = {'prefix': f'{self.swift_prefix}/'}
            for result in swift_service.list(
                container=self.swift_container,
                options=list_options
            ):
                if not result['success']:
                    logger.error(f"Failed to list objects: {result.get('error')}")
                    continue

                for item in result.get('listing', []):
                    object_name = item['name']

                    # Extract date from filename (format: {prefix}/YYYYMMDD_HHMMSS_db_schema.sql.gz)
                    match = re.search(r'(\d{8})_\d{6}_db_', object_name)
                    if match:
                        file_date = match.group(1)

                        if file_date < cutoff_str:
                            logger.info(f"Deleting old backup: {object_name}")

                            delete_result = list(swift_service.delete(
                                container=self.swift_container,
                                objects=[object_name]
                            ))

                            if delete_result and not delete_result[0]['success']:
                                logger.warning(f"Failed to delete {object_name}")

        except ClientException as e:
            logger.error(f"Error during cleanup: {e}")

    def cleanup_local_files(self, *files):
        """Remove local backup files"""
        logger.info("Cleaning up local backup files...")

        for file_path in files:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Removed {file_path}")

    def run(self):
        """Execute complete backup process"""
        try:
            logger.info("Starting PostgreSQL backup process")
            logger.info(f"Timestamp: {self.timestamp}")

            files_to_upload = []

            # Export roles (if enabled)
            if self.dump_roles:
                role_file = self.export_roles()
                role_gz = self.compress_file(role_file)
                files_to_upload.append(role_gz)

            # Export schema and data
            schema_file = self.export_schema()
            data_file = self.export_data()

            # Compress files
            schema_gz = self.compress_file(schema_file)
            data_gz = self.compress_file(data_file)
            files_to_upload.extend([schema_gz, data_gz])

            # Upload to Swift
            for file_path in files_to_upload:
                self.upload_to_swift(file_path)

            # Cleanup old backups
            self.cleanup_old_backups()

            # Cleanup local files
            self.cleanup_local_files(*files_to_upload)

            logger.info("Backup process completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Backup process failed: {e}", exc_info=True)
            return 1


def main():
    """Main entry point"""
    backup = PostgreSQLBackup()
    sys.exit(backup.run())


if __name__ == '__main__':
    main()
