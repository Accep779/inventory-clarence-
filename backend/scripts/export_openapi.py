"""
Export OpenAPI Schema
=====================

Exports the FastAPI OpenAPI schema to a JSON file for TypeScript generation.

Usage:
    python scripts/export_openapi.py
    python scripts/export_openapi.py --output ../frontend/lib/api/schema.json
    python scripts/export_openapi.py --check  # Check if schema is up to date
"""

import json
import argparse
import sys
import hashlib
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app


def export_openapi_schema(output_path: str = None) -> dict:
    """
    Export the FastAPI OpenAPI schema to a JSON file.

    Args:
        output_path: Path to write the schema JSON file. If None, returns the schema dict.

    Returns:
        The OpenAPI schema dictionary
    """
    # Get the OpenAPI schema from FastAPI
    schema = app.openapi()

    # Add additional metadata
    schema["info"]["x-logo"] = {
        "url": "https://cephly.com/logo.png",
        "altText": "Cephly Logo"
    }

    # Ensure all Pydantic models are properly exported as OpenAPI components
    # FastAPI does this automatically, but we can enhance the schema here

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(schema, f, indent=2, default=str)

        # Calculate hash for change detection
        schema_hash = hashlib.md5(
            json.dumps(schema, sort_keys=True, default=str).encode()
        ).hexdigest()

        # Write hash file for change detection
        hash_file = output_file.with_suffix('.hash')
        with open(hash_file, 'w') as f:
            f.write(schema_hash)

        print(f"OpenAPI schema exported to: {output_file}")
        print(f"  - Endpoints: {len(schema.get('paths', {}))}")
        print(f"  - Schemas: {len(schema.get('components', {}).get('schemas', {}))}")
        print(f"  - Hash: {schema_hash[:8]}...")

    return schema


def check_schema_freshness(schema_path: str) -> bool:
    """
    Check if the exported schema is up to date with current code.

    Returns:
        True if schema is up to date, False if it needs regeneration
    """
    schema_file = Path(schema_path)
    hash_file = schema_file.with_suffix('.hash')

    if not schema_file.exists() or not hash_file.exists():
        return False

    # Get current schema hash
    current_schema = app.openapi()
    current_hash = hashlib.md5(
        json.dumps(current_schema, sort_keys=True, default=str).encode()
    ).hexdigest()

    # Read stored hash
    with open(hash_file) as f:
        stored_hash = f.read().strip()

    return current_hash == stored_hash


def main():
    parser = argparse.ArgumentParser(
        description="Export FastAPI OpenAPI schema to JSON"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="../frontend/lib/api/schema.json",
        help="Output path for the schema JSON file (default: ../frontend/lib/api/schema.json)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if schema is up to date (exit 1 if stale)"
    )
    parser.add_argument(
        "--silent",
        "-s",
        action="store_true",
        help="Silent mode - no output"
    )

    args = parser.parse_args()

    if args.check:
        is_fresh = check_schema_freshness(args.output)
        if not args.silent:
            if is_fresh:
                print("OpenAPI schema is up to date")
            else:
                print("OpenAPI schema is stale - run with --output to regenerate")
        sys.exit(0 if is_fresh else 1)

    # Export the schema
    export_openapi_schema(args.output)


if __name__ == "__main__":
    main()
