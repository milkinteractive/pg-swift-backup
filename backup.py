#!/usr/bin/env python3
"""
PostgreSQL Backup to OpenStack Swift
Backs up PostgreSQL database and uploads to Infomaniak Swift storage
"""

import os
import sys
import subprocess
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import re
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
        self.backup_dir = Path(os.getenv('BACKUP_DIR', '/backups'))
        self.included_schemas = os.getenv('INCLUDED_SCHEMAS', 'public')
        self.extra_flags = os.getenv('EXTRA_FLAGS', '--column-inserts --rows-per-insert 8000')
        self.sed_remove_comments = os.getenv('SED_REMOVE_COMMENTS', r'/^--/d')
        self.retention_days = int(os.getenv('RETENTION_DAYS', '30'))

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

    def run_command(self, cmd, env=None):
        """Execute shell command and return output"""
        try:
            logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, **(env or {})}
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.stderr}")
            raise

    def process_sql_output(self, sql_content):
        """Apply sed-like transformations to SQL output"""
        lines = sql_content.split('\n')
        processed_lines = []

        for line in lines:
            # Skip comment lines if configured
            if line.startswith('--'):
                if 'COMMENT ON EXTENSION' in line:
                    line = '-- ' + line
                elif 'CREATE POLICY "cron_job_' in line:
                    line = '-- ' + line
                elif 'ALTER TABLE "cron"' in line:
                    line = '-- ' + line
                elif re.match(self.sed_remove_comments.strip('/d'), line):
                    continue
            else:
                # Apply CREATE transformations
                line = re.sub(r'^CREATE SCHEMA "', 'CREATE SCHEMA IF NOT EXISTS "', line)
                line = re.sub(r'^CREATE TABLE "', 'CREATE TABLE IF NOT EXISTS "', line)
                line = re.sub(r'^CREATE SEQUENCE "', 'CREATE SEQUENCE IF NOT EXISTS "', line)
                line = re.sub(r'^CREATE VIEW "', 'CREATE OR REPLACE VIEW "', line)
                line = re.sub(r'^CREATE FUNCTION "', 'CREATE OR REPLACE FUNCTION "', line)
                line = re.sub(r'^CREATE TRIGGER "', 'CREATE OR REPLACE TRIGGER "', line)

            processed_lines.append(line)

        # Remove consecutive duplicate lines
        result = []
        prev_line = None
        for line in processed_lines:
            if line != prev_line:
                result.append(line)
                prev_line = line

        return '\n'.join(result)

    def export_schema(self):
        """Export database schema"""
        logger.info("Exporting database schema...")

        schema_file = self.backup_dir / f"{self.timestamp}_db_schema.sql"

        # Run pg_dump for schema
        cmd = [
            'pg_dump',
            '-h', self.db_host,
            '-p', self.db_port,
            '-U', self.db_user,
            '--schema-only',
            '--quote-all-identifiers',
            '--extension', '*',
            '--schema', self.included_schemas,
            self.db_name
        ]

        env = {'PGPASSWORD': self.db_password}
        output = self.run_command(cmd, env)

        # Process output
        processed_output = self.process_sql_output(output)

        # Write to file with session role
        with open(schema_file, 'w') as f:
            f.write("SET session_replication_role = replica;\n")
            f.write(processed_output)
            f.write("\nRESET ALL;\n")

        file_size = schema_file.stat().st_size
        logger.info(f"Schema export completed: {file_size / 1024 / 1024:.2f} MB")

        return schema_file

    def export_data(self):
        """Export database data"""
        logger.info("Exporting database data...")

        data_file = self.backup_dir / f"{self.timestamp}_db_backup.sql"

        # Run pg_dump for data
        cmd = [
            'pg_dump',
            '-h', self.db_host,
            '-p', self.db_port,
            '-U', self.db_user,
            '--data-only',
            '--quote-all-identifiers',
            '--schema', self.included_schemas,
            '--no-comments',
            self.db_name
        ]

        # Add extra flags
        if self.extra_flags:
            cmd.extend(self.extra_flags.split())

        env = {'PGPASSWORD': self.db_password}
        output = self.run_command(cmd, env)

        # Write to file with session role
        with open(data_file, 'w') as f:
            f.write("SET session_replication_role = replica;\n")
            f.write(output)
            f.write("\nRESET ALL;\n")

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

        object_name = f"backups/{file_path.name}"

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
            list_options = {'prefix': 'backups/db_'}
            for result in swift_service.list(
                container=self.swift_container,
                options=list_options
            ):
                if not result['success']:
                    logger.error(f"Failed to list objects: {result.get('error')}")
                    continue

                for item in result.get('listing', []):
                    object_name = item['name']

                    # Extract date from filename (format: backups/YYYYMMDD_HHMMSS_db_schema.sql.gz)
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

            # Export schema and data
            schema_file = self.export_schema()
            data_file = self.export_data()

            # Compress files
            schema_gz = self.compress_file(schema_file)
            data_gz = self.compress_file(data_file)

            # Upload to Swift
            self.upload_to_swift(schema_gz)
            self.upload_to_swift(data_gz)

            # Cleanup old backups
            self.cleanup_old_backups()

            # Cleanup local files
            self.cleanup_local_files(schema_gz, data_gz)

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
