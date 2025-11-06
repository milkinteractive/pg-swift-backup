#!/usr/bin/env python3
"""
Extract Supabase schema/role definitions from cli/internal/utils/misc.go
Generates Python file with default values that can be overridden via environment variables
"""
import re
import sys
import argparse
from pathlib import Path


def download_misc_go(url):
    """Download misc.go from GitHub or use local file"""
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Warning: Could not download from {url}: {e}", file=sys.stderr)
        return None


def read_local_file(file_path):
    """Read from local file as fallback"""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading local file {file_path}: {e}", file=sys.stderr)
        return None


def extract_go_string_array(content, array_name):
    """Extract Go string array and convert to pipe-separated list"""

    # Special handling for InternalSchemas (uses append with SystemSchemas)
    if array_name == "InternalSchemas":
        # Pattern: InternalSchemas = append([]string{"val1", "val2"}, SystemSchemas...)
        # Match until the closing brace and comma before SystemSchemas
        pattern = rf'{array_name}\s*=\s*append\(\s*\[\]string\s*\{{(.+?)\}}\s*,\s*SystemSchemas'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            array_content = match.group(1)
            values = re.findall(r'"([^"]+)"', array_content)

            # Also extract SystemSchemas and append
            system_values = extract_go_string_array(content, "SystemSchemas")
            if system_values:
                values.extend(system_values.split('|'))

            return '|'.join(values)

    # Normal array pattern: ArrayName = []string{"val1", "val2", ...}
    # Match until we find a closing brace followed by newline or other terminator
    pattern = rf'{array_name}\s*=\s*\[\]string\s*\{{(.+?)\}}'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return None

    array_content = match.group(1)
    # Extract all quoted strings, ignoring comments
    values = re.findall(r'"([^"]+)"', array_content)

    return '|'.join(values)


def generate_python_defaults(internal_schemas, reserved_roles, allowed_configs):
    """Generate Python file with default constants"""
    return f'''"""
Auto-generated Supabase default configurations
Extracted from: https://github.com/supabase/cli/blob/main/internal/utils/misc.go

These are the default values. They can be overridden via environment variables:
- DB_DUMP_INTERNAL_SCHEMAS
- DB_DUMP_RESERVED_ROLES
- DB_DUMP_ALLOWED_CONFIGS
"""

# Default schemas to exclude (Supabase internal + system schemas)
DEFAULT_INTERNAL_SCHEMAS = "{internal_schemas}"

# Default reserved roles that should not be created/altered
DEFAULT_RESERVED_ROLES = "{reserved_roles}"

# Default allowed role configurations
DEFAULT_ALLOWED_CONFIGS = "{allowed_configs}"
'''


def main():
    parser = argparse.ArgumentParser(
        description='Extract Supabase definitions from misc.go'
    )
    parser.add_argument(
        '--url',
        default='https://raw.githubusercontent.com/supabase/cli/main/internal/utils/misc.go',
        help='URL to misc.go file'
    )
    parser.add_argument(
        '--local',
        help='Path to local misc.go file (fallback if URL fails)'
    )
    parser.add_argument(
        '--output',
        default='supabase_defaults.py',
        help='Output Python file (default: supabase_defaults.py)'
    )
    args = parser.parse_args()

    try:
        content = None

        # Try local file first if specified
        if args.local:
            print(f"Using local file {args.local}...", file=sys.stderr)
            content = read_local_file(args.local)

        # Fallback to URL download
        if not content and args.url:
            print(f"Downloading from {args.url}...", file=sys.stderr)
            content = download_misc_go(args.url)

        if not content:
            print("Error: Could not load misc.go content", file=sys.stderr)
            return 1

        # Extract values
        print("Extracting InternalSchemas...", file=sys.stderr)
        internal_schemas = extract_go_string_array(content, "InternalSchemas")

        print("Extracting ReservedRoles...", file=sys.stderr)
        reserved_roles = extract_go_string_array(content, "ReservedRoles")

        print("Extracting AllowedConfigs...", file=sys.stderr)
        allowed_configs = extract_go_string_array(content, "AllowedConfigs")

        if not all([internal_schemas, reserved_roles, allowed_configs]):
            print("Error: Failed to extract all required values", file=sys.stderr)
            return 1

        # Generate Python file
        output_content = generate_python_defaults(
            internal_schemas,
            reserved_roles,
            allowed_configs
        )

        # Write to file
        output_path = Path(args.output)
        output_path.write_text(output_content)

        print(f"Successfully generated {output_path}", file=sys.stderr)
        print(f"  - InternalSchemas: {len(internal_schemas.split('|'))} items", file=sys.stderr)
        print(f"  - ReservedRoles: {len(reserved_roles.split('|'))} items", file=sys.stderr)
        print(f"  - AllowedConfigs: {len(allowed_configs.split('|'))} items", file=sys.stderr)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
