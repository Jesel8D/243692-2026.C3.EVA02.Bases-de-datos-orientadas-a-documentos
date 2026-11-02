#!/usr/bin/env python3
"""Validate JSONL, load orders and compare data (not a benchmark runner)."""
import argparse
from decimal import DecimalException
from pathlib import Path
import sys

from src.dataset.database import MongoAdapter, PostgresAdapter
from src.dataset.files import validate_file
from src.dataset.model import DataError, json_text
from src.dataset.operations import compare_dataset, import_dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("validate", "import-mongo", "import-postgres", "counts", "compare"))
    parser.add_argument("--file")
    parser.add_argument("--manifest")
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--resume", action="store_true", help="accept identical existing rows; never overwrite")
    parser.add_argument("--engine", choices=("mongo", "postgres", "both"), default="both")
    parser.add_argument("--sample-size", type=int)
    parser.add_argument("--sample-seed", type=int, default=42)
    parser.add_argument("--timeout", type=int, default=120, help="per batch Docker exec timeout (s)")
    parser.add_argument("--report", help="exclusive-create JSON evidence, never official benchmark CSV")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.batch_size <= 1000 or not 1 <= args.timeout <= 3600:
            raise DataError("Invalid batch-size/timeout")
        if args.operation != "counts" and not args.file:
            raise DataError("--file is required")
        if args.sample_size is not None and (args.operation != "compare" or not 1 <= args.sample_size <= 10000):
            raise DataError("--sample-size 1..10000 is for compare only")
        if args.resume and not args.operation.startswith("import-"):
            raise DataError("--resume is for import only")
        if args.report and Path(args.report).exists():
            raise DataError("Report exists; refusing overwrite before any database operation")
        if args.operation == "validate":
            result = validate_file(args.file, args.manifest)
        elif args.operation.startswith("import-"):
            adapter = MongoAdapter(args.timeout) if args.operation == "import-mongo" else PostgresAdapter(args.timeout)
            result = import_dataset(adapter, args.file, manifest=args.manifest, batch_size=args.batch_size, resume=args.resume)
        else:
            adapters = []
            if args.engine in ("mongo", "both"):
                adapters.append(MongoAdapter(args.timeout))
            if args.engine in ("postgres", "both"):
                adapters.append(PostgresAdapter(args.timeout))
            if args.operation == "counts":
                result = {a.engine: a.count() for a in adapters}
            else:
                result = compare_dataset(adapters, args.file, manifest=args.manifest, batch_size=args.batch_size,
                                         sample_size=args.sample_size, sample_seed=args.sample_seed)
        encoded = json_text(result) + "\n"
        if args.report:
            with Path(args.report).open("x", encoding="utf8") as report:
                report.write(encoded)
        print(encoded, end="")
        return 0
    except (DataError, OSError, DecimalException, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
