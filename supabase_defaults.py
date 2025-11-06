"""
Auto-generated Supabase default configurations
Extracted from: https://github.com/supabase/cli/blob/main/internal/utils/misc.go

These are the default values. They can be overridden via environment variables:
- DB_DUMP_INTERNAL_SCHEMAS
- DB_DUMP_RESERVED_ROLES
- DB_DUMP_ALLOWED_CONFIGS
"""

# Default schemas to exclude (Supabase internal + system schemas)
DEFAULT_INTERNAL_SCHEMAS = "auth|extensions|pgbouncer|realtime|_realtime|storage|_analytics|supabase_functions|supabase_migrations|information_schema|pg_*|cron|graphql|graphql_public|net|pgsodium|pgsodium_masks|pgtle|repack|tiger|tiger_data|timescaledb_*|_timescaledb_*|topology|vault"

# Default reserved roles that should not be created/altered
DEFAULT_RESERVED_ROLES = "anon|authenticated|authenticator|dashboard_user|pgbouncer|postgres|service_role|supabase_admin|supabase_auth_admin|supabase_functions_admin|supabase_read_only_user|supabase_replication_admin|supabase_storage_admin|pgsodium_keyholder|pgsodium_keyiduser|pgsodium_keymaker|pgtle_admin"

# Default allowed role configurations
DEFAULT_ALLOWED_CONFIGS = "pgaudit.*|pgrst.*|session_replication_role|statement_timeout|track_io_timing"
