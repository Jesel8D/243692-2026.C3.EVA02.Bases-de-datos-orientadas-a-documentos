"""Unit/contract tests: no Docker, no fabricated database measurements."""
import copy
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import subprocess
import tracemalloc
import sys
import unittest
from unittest.mock import patch

from src.dataset.database import MongoAdapter, PostgresAdapter, to_ejson, from_ejson
from src.dataset.files import configuration, generate, validate_file, manifest_path, iter_file
from src.dataset.model import (DataError, documents, json_text, parse_json, timestamp,
                               totals, validate_order, valid_uuid)
from src.dataset.operations import compare_dataset, import_dataset, select_sample


class MemoryAdapter:
    engine = "unit-fake"

    def __init__(self):
        self.rows = {}
        self.writes = 0

    def ensure(self):
        pass

    def count(self):
        return len(self.rows)

    def fetch(self, ids):
        return {uid: copy.deepcopy(self.rows[uid]) for uid in ids if uid in self.rows}

    def insert(self, docs):
        for doc in docs:
            if doc["order_id"] in self.rows:
                raise DataError("duplicate")
            self.rows[doc["order_id"]] = copy.deepcopy(doc)
            self.writes += 1


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "orders.jsonl"
        self.config = configuration(count=10)
        self.info = generate(self.path, self.config, 0)
        self.doc = next(iter_file(self.path))[2]

    def tearDown(self):
        self.temp.cleanup()

    def test_deterministic_bytes_and_metadata_separation(self):
        other = self.root / "again.jsonl"
        info = generate(other, self.config, 0)
        self.assertEqual(self.path.read_bytes(), other.read_bytes())
        self.assertEqual(self.info["sha256"], info["sha256"])
        self.assertEqual(self.info["logical_sha256_in_file_order"], info["logical_sha256_in_file_order"])
        self.assertNotIn(b"generated_at", self.path.read_bytes())

    def test_seed_changes_content_and_uuids(self):
        first = next(documents(42, 1, self.config["start"], self.config["end"], "totals-and-alias"))
        other = next(documents(43, 1, self.config["start"], self.config["end"], "totals-and-alias"))
        self.assertNotEqual(first["order_id"], other["order_id"])

    def test_thousand_records_structure_distributions_and_uniqueness(self):
        path = self.root / "thousand.jsonl"
        info = generate(path, configuration(count=1000), 0)
        stats = validate_file(path)
        self.assertEqual(stats["count"], 1000)
        self.assertGreater(stats["mean_items"], Decimal("2.8"))
        self.assertLess(stats["mean_items"], Decimal("3.2"))
        self.assertGreater(stats["eligible_items_price_gt_50"], 0)
        self.assertGreater(stats["eligible_orders_for_q2"], 0)
        self.assertEqual(len(stats["payment_states"]), 4)
        self.assertEqual(stats["sha256"], info["sha256"])
        self.assertEqual(info["sha256"], "20c4e83b3694a07c80da80a681639df4b5931490d283c0ac37b638225aaec20a")
        ids = set()
        for _, _, doc in iter_file(path):
            self.assertEqual(valid_uuid(doc["order_id"]), doc["order_id"])
            self.assertNotIn(doc["order_id"], ids)
            ids.add(doc["order_id"])
            self.assertEqual(timestamp(doc["timestamp"]).utcoffset().total_seconds(), 0)

    def test_validate_manifest_and_hash(self):
        self.assertEqual(validate_file(self.path)["count"], 10)
        with self.path.open("ab") as stream:
            stream.write(b"\n")
        with self.assertRaises(DataError):
            validate_file(self.path)

    def test_duplicate_uuid_detected_before_import(self):
        lines = self.path.read_bytes().splitlines(keepends=True)
        lines[1] = lines[0]
        self.path.write_bytes(b"".join(lines))
        adapter = MemoryAdapter()
        with self.assertRaisesRegex(DataError, "duplicate UUID"):
            import_dataset(adapter, self.path)
        self.assertEqual(adapter.writes, 0)

    def test_decimal_roundtrip_and_amounts(self):
        parsed = parse_json(json_text(self.doc))
        self.assertIsInstance(parsed["items"][0]["price"], Decimal)
        self.assertEqual(parsed["payment"]["totals"], totals(parsed["items"]))
        self.assertEqual(parsed["payment"]["final_total"], parsed["payment"]["totals"]["final_total"])
        self.assertEqual(from_ejson(to_ejson(parsed)), parsed)
        self.assertEqual(json_text(Decimal("1.000"), True), json_text(1, True))

    def test_half_up_tax_rule(self):
        item = {"qty": 1, "price": Decimal("1.01"), "discounts": [], "tax_pct": Decimal("8")}
        self.assertEqual(totals([item])["tax"], Decimal("0.08"))
        item["price"] = Decimal("0.25")
        item["tax_pct"] = Decimal("2")
        self.assertEqual(totals([item])["tax"], Decimal("0.01"))

    def test_schema_mutations_rejected(self):
        cases = []
        for path, value in [(('timestamp',), '2026-02-30T00:00:00Z'), (('order_id',), 'bad'),
                            (('payment', 'status'), 'unknown'), (('payment', 'final_total'), Decimal("0")),
                            (('metadata', 'flags', 'gift'), 1), (('items',), []),
                            (('customer', 'geo', 'coordinates'), [Decimal('300'), Decimal('0')])]:
            d = copy.deepcopy(self.doc)
            obj = d
            for k in path[:-1]:
                obj = obj[k]
            obj[path[-1]] = value
            cases.append(d)
        d = copy.deepcopy(self.doc); d['items'][0]['qty'] = True; cases.append(d)
        d = copy.deepcopy(self.doc); d['items'][0]['price'] = 1.1; cases.append(d)
        d = copy.deepcopy(self.doc); d['items'][0]['price'] = '50.00'; cases.append(d)
        d = copy.deepcopy(self.doc); del d['payment']['totals']; cases.append(d)
        d = copy.deepcopy(self.doc); d['extra'] = 1; cases.append(d)
        for d in cases:
            with self.subTest(doc=d), self.assertRaises(DataError):
                validate_order(d)

    def test_duplicate_fields_nan_and_binary_double_rejected(self):
        for text in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}']:
            with self.assertRaises(DataError):
                parse_json(text)
        with self.assertRaises(DataError):
            from_ejson({"$numberDouble": "1.25"})

    def test_bad_configs_and_no_overwrite(self):
        for kwargs in [dict(count=0), dict(seed=-1), dict(end='2025-01-01T00:00:00Z'), dict(payment_layout='bad')]:
            with self.assertRaises(DataError):
                configuration(**kwargs)
        with self.assertRaises(DataError):
            generate(self.path, self.config)
        for value in ['2026-01-01', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00.000Z']:
            with self.assertRaises(DataError):
                timestamp(value)

    def test_reversible_alias_layout(self):
        path = self.root / 'totals-only.jsonl'
        generate(path, configuration(count=10, payment_layout='totals-only'), 0)
        self.assertEqual(validate_file(path)['count'], 10)
        doc = next(iter_file(path))[2]
        self.assertNotIn('final_total', doc['payment'])
        self.assertIn('totals', doc['payment'])

    def test_insert_only_resume_and_full_equivalence(self):
        a = MemoryAdapter()
        report = import_dataset(a, self.path, batch_size=3)
        self.assertEqual(report['inserted'], 10)
        with self.assertRaises(DataError):
            import_dataset(a, self.path)
        report = import_dataset(a, self.path, batch_size=4, resume=True)
        self.assertEqual(report['already_identical'], 10)
        self.assertEqual(a.writes, 10)
        self.assertEqual(compare_dataset([a], self.path)['checked'], 10)
        a.rows[self.doc['order_id']]['metadata']['user_agent'] = 'changed'
        with self.assertRaises(DataError):
            import_dataset(a, self.path, resume=True)
        with self.assertRaises(DataError):
            compare_dataset([a], self.path)

    def test_deterministic_sample_and_no_full_claim(self):
        self.assertEqual(select_sample(self.path, 3, 7), select_sample(self.path, 3, 7))
        self.assertNotEqual(select_sample(self.path, 3, 7), select_sample(self.path, 3, 8))
        a = MemoryAdapter(); import_dataset(a, self.path)
        report = compare_dataset([a], self.path, sample_size=3, sample_seed=7)
        self.assertEqual(report['checked'], 3)
        self.assertEqual(report['mode'], 'sample')
        self.assertIn('not full equality', report['scope'])

    def test_partial_batch_failure_can_resume_without_replace(self):
        a = MemoryAdapter()
        original = a.insert
        def partial(docs):
            original(docs[:1])
            raise DataError('simulated software failure; not database evidence')
        a.insert = partial
        with self.assertRaises(DataError):
            import_dataset(a, self.path, batch_size=3)
        self.assertEqual(a.count(), 1)
        a.insert = original
        self.assertEqual(import_dataset(a, self.path, resume=True)['after'], 10)
        self.assertEqual(a.writes, 10)

    @patch.dict('os.environ', {'DATA_PG_CONTAINER': 'a'*64, 'DATA_DATABASE_NAME': 'unitdb'})
    def test_postgres_copy_has_numeric_json_and_transaction(self):
        adapter = PostgresAdapter()
        with patch.object(adapter, 'sql') as sql:
            adapter.insert([self.doc])
            script = sql.call_args.args[0]
            self.assertTrue(script.startswith('BEGIN;\nCOPY'))
            self.assertTrue(script.endswith('\\.\nCOMMIT;\n'))
            uid, payload = next(csv.reader(io.StringIO(script.split('\n', 2)[2])))
            self.assertEqual(uid, self.doc['order_id'])
            self.assertEqual(parse_json(payload), self.doc)

    @patch.dict('os.environ', {'DATA_MONGO_CONTAINER': 'a'*64, 'DATA_DATABASE_NAME': 'unitdb'})
    def test_mongo_decimal128_and_deterministic_technical_id(self):
        adapter = MongoAdapter()
        with patch.object(adapter, 'command', return_value=1) as command:
            adapter.insert([self.doc])
            row = command.call_args.kwargs['docs'][0]
            self.assertEqual(row['_id'], row['order_id'])
            self.assertIn('$numberDecimal', to_ejson(row)['items'][0]['price'])

    def test_streaming_memory_bound(self):
        path = self.root / 'streaming.jsonl'
        tracemalloc.start()
        try:
            generate(path, configuration(count=1000), 0)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 8 * 1024 * 1024)

    def test_cli_defaults_and_invalid_arguments(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run([sys.executable, str(root/'synthetic_data_generator.py'), '--output', str(self.root/'bad.jsonl'), '--count', '-1'], capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((self.root/'bad.jsonl').exists())
        self.assertEqual(configuration()['count'], 500000)
        proc = subprocess.run([sys.executable, str(root/'dataset_tool.py'), 'validate'], capture_output=True)
        self.assertNotEqual(proc.returncode, 0)

    def test_batch_bounds_and_missing_interface(self):
        a = MemoryAdapter()
        with self.assertRaises(DataError):
            import_dataset(a, self.path, batch_size=0)
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(DataError):
            MongoAdapter()


if __name__ == '__main__':
    unittest.main()
