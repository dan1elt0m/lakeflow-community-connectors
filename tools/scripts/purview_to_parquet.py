"""Export Microsoft Purview tables to Parquet files.

Usage:
    python tools/scripts/purview_to_parquet.py [--output-dir ./output] [--tables domains,data_products,data_assets]

Requires: azure-identity, pandas, pyarrow
Auth: Uses DefaultAzureCredential (az login).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Add project root to path so we can import the connector
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from databricks.labs.community_connector.sources.purview.purview import (
    PurviewLakeflowConnect,
)


def flatten_record(record: dict, parent_key: str = "", sep: str = "_") -> dict:
    """Flatten nested dicts/lists into a flat dict for Parquet compatibility."""
    items = {}
    for k, v in record.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_record(v, new_key, sep))
        elif isinstance(v, list):
            items[new_key] = json.dumps(v, default=str)
        else:
            items[new_key] = v
    return items


def export_table(connector: PurviewLakeflowConnect, table_name: str, output_dir: Path) -> None:
    """Read a table and write it to Parquet."""
    print(f"\n{'=' * 60}")
    print(f"Reading table: {table_name}")
    print(f"{'=' * 60}")

    records_iter, end_offset = connector.read_table(table_name, {}, {})
    records = [flatten_record(r) for r in records_iter]

    if not records:
        print(f"  No records found for {table_name}, skipping.")
        return

    df = pd.DataFrame(records)

    # Replace all-null columns (Parquet "void" type) with empty strings
    # so Power BI and other tools can read them as STRING.
    for col in df.columns:
        if df[col].isna().all():
            df[col] = df[col].fillna("").astype(str)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{table_name}_{timestamp}.parquet"
    filepath = output_dir / filename

    df.to_parquet(filepath, index=False, engine="pyarrow")
    print(f"  Records: {len(df)}")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Written: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Export Purview tables to Parquet")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./output/purview",
        help="Directory to write Parquet files (default: ./output/purview)",
    )
    parser.add_argument(
        "--tables",
        "-t",
        default="domains,data_products,data_assets",
        help="Comma-separated list of tables to export (default: all)",
    )
    parser.add_argument(
        "--account-name",
        "-a",
        default=None,
        help="Purview account name (default: reads from dev_config.json)",
    )
    args = parser.parse_args()

    # Resolve account name
    account_name = args.account_name
    if not account_name:
        config_path = (
            Path(__file__).resolve().parents[2]
            / "tests/unit/sources/purview/configs/dev_config.json"
        )
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            account_name = config.get("purview_account_name")
        if not account_name:
            print("Error: No account name. Use --account-name or set it in dev_config.json")
            sys.exit(1)

    # Setup
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = [t.strip() for t in args.tables.split(",")]

    print(f"Purview account: {account_name}")
    print(f"Output dir:      {output_dir}")
    print(f"Tables:          {tables}")

    # Initialize connector
    connector = PurviewLakeflowConnect(
        {
            "purview_account_name": account_name,
            "auth_method": "default_credential",
        }
    )

    # Export each table
    for table in tables:
        try:
            export_table(connector, table, output_dir)
        except Exception as e:
            print(f"  ERROR reading {table}: {e}")

    print(f"\nDone! Files in: {output_dir}")


if __name__ == "__main__":
    main()
