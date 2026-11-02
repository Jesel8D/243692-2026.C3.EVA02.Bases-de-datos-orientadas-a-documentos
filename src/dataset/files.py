"""Streaming JSONL and manifest validation. UUID uniqueness uses disk SQLite."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import platform
import sqlite3
import tempfile

from .model import (DataError, GENERATOR_VERSION, SCHEMA_VERSION, documents,
                    json_text, parse_json, timestamp, validate_order)

MAX_LINE_BYTES = 1024 * 1024


def manifest_path(path):
    return Path(str(path) + ".manifest.json")


def configuration(seed=42, count=500000, start="2025-07-01T00:00:00Z",
                  end="2026-10-01T00:00:00Z", payment_layout="totals-and-alias"):
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise DataError("Seed must be an integer in [0, 2**64)")
    if type(count) is not int or not 1 <= count <= 10000000:
        raise DataError("Count must be 1..10000000")
    if payment_layout not in ("totals-only", "totals-and-alias"):
        raise DataError("Invalid payment layout")
    seconds = int((timestamp(end) - timestamp(start)).total_seconds())
    if not 0 < seconds <= 2**32:
        raise DataError("Invalid date interval (end exclusive)")
    return {"seed": seed, "count": count, "start": start, "end": end,
            "payment_layout": payment_layout, "distribution": "academic-provisional-v1",
            "prng": "sha256-counter-u32-rejection-v1", "uuid": "uuid5-seed-entity-index-v1"}


def _config_from_manifest(manifest):
    try:
        if manifest["schema_version"] != SCHEMA_VERSION or manifest["generator_version"] != GENERATOR_VERSION:
            raise DataError("Unsupported schema/generator version")
        config = manifest["configuration"]
        expected = configuration(**{k: config[k] for k in ("seed", "count", "start", "end", "payment_layout")})
        if config != expected:
            raise DataError("Manifest configuration differs from versioned contract")
        return expected
    except (KeyError, TypeError) as exc:
        raise DataError("Incomplete manifest") from exc


def generate(path, config, progress_every=10000):
    path = Path(path)
    target_manifest = manifest_path(path)
    if path.exists() or target_manifest.exists():
        raise DataError("Output or manifest already exists; choose new paths (no overwrite)")
    # Validate the complete config before reserving output files.
    expected = configuration(**{k: config[k] for k in ("seed", "count", "start", "end", "payment_layout")})
    if expected != config:
        raise DataError("Unexpected configuration")
    digest = hashlib.sha256()
    logical = hashlib.sha256()
    items = 0
    states = Counter()
    import sys
    # Exclusive creation. Interrupted files are left for inspection; no silent deletion.
    with target_manifest.open("x", encoding="utf8") as mf, path.open("xb") as out:
        for index, doc in enumerate(documents(config["seed"], config["count"], config["start"], config["end"], config["payment_layout"]), 1):
            validate_order(doc, config["payment_layout"])
            raw = (json_text(doc) + "\n").encode("utf8")
            out.write(raw)
            digest.update(raw)
            logical.update((json_text(doc, canonical=True) + "\n").encode("utf8"))
            items += len(doc["items"])
            states[doc["payment"]["status"]] += 1
            if progress_every and index % progress_every == 0:
                print(f"generated={index}/{config['count']}", file=sys.stderr)
        manifest = {"schema_version": SCHEMA_VERSION, "generator_version": GENERATOR_VERSION,
                    "configuration": config, "sha256": digest.hexdigest(),
                    "logical_sha256_in_file_order": logical.hexdigest(), "count": config["count"],
                    "item_count": items, "payment_states": dict(states),
                    "metadata": {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
                                 "python": platform.python_version()}}
        mf.write(json_text(manifest) + "\n")
    return manifest


def iter_file(path):
    with Path(path).open("rb") as stream:
        number = 0
        while True:
            raw = stream.readline(MAX_LINE_BYTES + 1)
            if not raw:
                return
            number += 1
            if len(raw) > MAX_LINE_BYTES:
                raise DataError(f"Line {number} exceeds size limit")
            try:
                doc = parse_json(raw.decode("utf8"))
            except (DataError, UnicodeError) as exc:
                raise DataError(f"Line {number}: invalid UTF8/JSON") from exc
            yield number, raw, doc


def validate_file(path, manifest=None):
    path = Path(path)
    try:
        info = parse_json(Path(manifest or manifest_path(path)).read_text(encoding="utf8"))
        config = _config_from_manifest(info)
    except (OSError, DataError) as exc:
        raise DataError(f"Manifest unavailable/invalid: {exc}") from exc
    digest = hashlib.sha256()
    logical = hashlib.sha256()
    count = total_items = q1_items = q2_orders = 0
    states = Counter()
    # Not an O(N) Python set: disk index grows, RAM cache is capped to ~2 MiB.
    with tempfile.TemporaryDirectory(prefix="orders-validation-") as directory:
        with sqlite3.connect(str(Path(directory) / "ids.sqlite")) as ids:
            ids.execute("PRAGMA cache_size=-2048")
            ids.execute("PRAGMA journal_mode=OFF")
            ids.execute("CREATE TABLE ids (id TEXT PRIMARY KEY)")
            for line, raw, doc in iter_file(path):
                try:
                    validate_order(doc, config["payment_layout"])
                    if not config["start"] <= doc["timestamp"] < config["end"]:
                        raise DataError("Timestamp outside configured interval")
                    ids.execute("INSERT INTO ids VALUES (?)", (doc["order_id"],))
                except (DataError, sqlite3.IntegrityError) as exc:
                    raise DataError(f"Line {line}: schema/date/duplicate UUID failure: {exc}") from exc
                digest.update(raw)
                logical.update((json_text(doc, canonical=True) + "\n").encode("utf8"))
                count += 1
                total_items += len(doc["items"])
                q1_items += sum(item["price"] > 50 for item in doc["items"])
                q2_orders += doc["payment"]["status"] == "completed" and doc["timestamp"] >= "2026-01-01T00:00:00Z"
                states[doc["payment"]["status"]] += 1
    checks = {"count": count, "sha256": digest.hexdigest(),
              "logical_sha256_in_file_order": logical.hexdigest(),
              "item_count": total_items, "payment_states": dict(states)}
    if any(info.get(key) != value for key, value in checks.items()) or count != config["count"]:
        raise DataError("Manifest hash/count/statistics mismatch; no import permitted")
    return {**checks, "configuration": config, "mean_items": Decimal(total_items) / count,
            "eligible_items_price_gt_50": q1_items, "eligible_orders_for_q2": q2_orders}


def batches(path, size):
    if not 1 <= size <= 1000:
        raise DataError("Batch size must be 1..1000")
    chunk = []
    for _, _, doc in iter_file(path):
        chunk.append(doc)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
