"""Validated, insert-only loads and deterministic full/sample comparison."""
import hashlib
import heapq
from pathlib import Path
import sys

from .files import batches, iter_file, validate_file
from .model import DataError, json_text, validate_order


def _same(expected, actual):
    return json_text(expected, canonical=True) == json_text(actual, canonical=True)


def import_dataset(adapter, path, *, manifest=None, batch_size=250, resume=False):
    if not 1 <= batch_size <= 1000:
        raise DataError("Batch size must be 1..1000")
    signature = _signature(path)
    stats = validate_file(path, manifest)  # Entire source validation before target writes.
    if _signature(path) != signature:
        raise DataError("Source changed during preflight validation; no writes performed")
    adapter.ensure()
    before = adapter.count()
    if before and not resume:
        raise DataError("orders is not empty. No writes performed. --resume accepts identical rows only; never deletes/replaces")
    if before > stats["count"]:
        raise DataError("Target contains more rows than source; no writes performed")
    inserted = matched = 0
    for chunk in batches(path, batch_size):
        existing = adapter.fetch([d["order_id"] for d in chunk])
        missing = []
        for doc in chunk:
            current = existing.get(doc["order_id"])
            if current is None:
                missing.append(doc)
            elif not resume or not _same(doc, current):
                raise DataError("Existing UUID differs or concurrent import detected; refusing overwrite")
            else:
                validate_order(current, stats["configuration"]["payment_layout"])
                matched += 1
        if missing:
            adapter.insert(missing)
            inserted += len(missing)
        # Read every committed batch back: count alone cannot establish precision/structure.
        observed = adapter.fetch([d["order_id"] for d in chunk])
        for doc in chunk:
            actual = observed.get(doc["order_id"])
            if actual is None or not _same(doc, actual):
                raise DataError("Read-after-write differs; load is partial, no automatic cleanup")
            validate_order(actual, stats["configuration"]["payment_layout"])
        print(f"{adapter.engine}: verified={inserted + matched}/{stats['count']}", file=sys.stderr)
    if _signature(path) != signature:
        raise DataError("Source file changed during load; retain partial state for inspection")
    after = adapter.count()
    if after != stats["count"]:
        raise DataError("Target count differs; possible foreign/concurrent records")
    return {"engine": adapter.engine, "source_sha256": stats["sha256"], "expected_count": stats["count"],
            "before": before, "inserted": inserted, "already_identical": matched, "after": after,
            "verification": "full read-after-write", "status": "ok"}


def _signature(path):
    s = Path(path).stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def select_sample(path, size, seed):
    """Smallest keyed SHA-256 ranks; memory O(size), independent of Python random."""
    if not 1 <= size <= 10000:
        raise DataError("Sample size must be 1..10000")
    heap = []
    for _, _, doc in iter_file(path):
        rank = int.from_bytes(hashlib.sha256(f"{seed}:{doc['order_id']}".encode()).digest(), "big")
        entry = (-rank, doc["order_id"], doc)
        if len(heap) < size:
            heapq.heappush(heap, entry)
        elif entry[:2] > heap[0][:2]:
            heapq.heapreplace(heap, entry)
    return [entry[2] for entry in sorted(heap, key=lambda e: (-e[0], e[1]))]


def compare_dataset(adapters, path, *, manifest=None, batch_size=250, sample_size=None, sample_seed=42):
    if not adapters or not 1 <= batch_size <= 1000:
        raise DataError("At least one adapter and batch size 1..1000 are required")
    signature = _signature(path)
    stats = validate_file(path, manifest)
    if _signature(path) != signature:
        raise DataError("Source changed during preflight comparison")
    counts = {a.engine: a.count() for a in adapters}
    if any(n != stats["count"] for n in counts.values()):
        raise DataError("Engine count differs from source")
    if sample_size is None:
        groups = batches(path, batch_size)
    else:
        chosen = select_sample(path, sample_size, sample_seed)
        groups = (chosen[i:i+batch_size] for i in range(0, len(chosen), batch_size))
    checked = 0
    logical = hashlib.sha256()
    for group in groups:
        all_rows = [a.fetch([d["order_id"] for d in group]) for a in adapters]
        for doc in group:
            uid = doc["order_id"]
            for rows in all_rows:
                current = rows.get(uid)
                if current is None:
                    raise DataError("Missing expected UUID")
                validate_order(current, stats["configuration"]["payment_layout"])
                if not _same(doc, current):
                    raise DataError("Logical content differs from source (field/type/precision)")
            logical.update((json_text(doc, canonical=True) + "\n").encode("utf8"))
            checked += 1
    if _signature(path) != signature:
        raise DataError("Source file changed during comparison")
    if any(a.count() != counts[a.engine] for a in adapters):
        raise DataError("Target count changed during comparison; concurrent writers not permitted")
    return {"status": "ok", "mode": "sample" if sample_size is not None else "full", "checked": checked,
            "count_by_engine": counts, "source_sha256": stats["sha256"],
            "checked_logical_sha256": logical.hexdigest(), "sample_seed": sample_seed if sample_size else None,
            "scope": "sample content + total count (not full equality)" if sample_size else "all IDs and complete logical content vs source"}
