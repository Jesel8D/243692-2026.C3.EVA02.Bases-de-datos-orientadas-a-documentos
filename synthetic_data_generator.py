#!/usr/bin/env python3
"""Generate deterministic JSON Lines orders (default 500,000); stdlib only."""
import argparse
import sys
from decimal import DecimalException
from src.dataset.files import configuration, generate
from src.dataset.model import DataError, json_text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=500000)
    parser.add_argument("--start", default="2025-07-01T00:00:00Z")
    parser.add_argument("--end", default="2026-10-01T00:00:00Z", help="exclusive upper bound")
    parser.add_argument("--payment-layout", choices=("totals-and-alias", "totals-only"), default="totals-and-alias")
    parser.add_argument("--progress-every", type=int, default=10000)
    args = parser.parse_args(argv)
    try:
        if args.progress_every < 0:
            raise DataError("progress-every must be non-negative (0 disables)")
        config = configuration(args.seed, args.count, args.start, args.end, args.payment_layout)
        print(json_text(generate(args.output, config, args.progress_every)))
        return 0
    except (DataError, OSError, DecimalException) as exc:
        print(f"ERROR: {exc}. Any partial output is retained; use a new path.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
