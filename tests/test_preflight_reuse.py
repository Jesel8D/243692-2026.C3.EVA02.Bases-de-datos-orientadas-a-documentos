"""Offline guard tests. No DB connections or benchmark execution."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from queries.definitions import QueryBlocked
from benchmark.preflight_reuse import InvocationValidation, file_fingerprint


class ReuseProofTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / 'orders.jsonl'
        self.file.write_text('{"order_id":"demo"}\n')
        Path(str(self.file) + '.manifest.json').write_text('{}')
        self.stats = {'sha256':file_fingerprint(self.file)['data_sha256']}
        self.evidence = {'status':'ok', 'mode':'full', 'checked':500000}
        self.refs = {'Q1':object(), 'Q2':object()}
        self.db_rev = {'mongo':{'count':500000,'insert':7}, 'postgres':{'row_count':500000, 'tup_inserted':10}}

    def test_full_current_invocation_proof_can_be_reused(self):
        with patch('benchmark.preflight_reuse.database_write_guards',return_value=self.db_rev):
            proof=InvocationValidation(self.file)
            proof.save(self.stats,self.evidence,self.refs,'scenario-1',120000)
            self.assertEqual(proof.validate(120000)['status'],'PASS')
            self.assertEqual(proof.original_scenario_id,'scenario-1')
            with self.assertRaises(QueryBlocked):proof.save(self.stats,self.evidence,self.refs,'scenario-2',120000)

    def test_changed_source_or_manifest_fails_closed(self):
        with patch('benchmark.preflight_reuse.database_write_guards',return_value=self.db_rev):
            proof=InvocationValidation(self.file)
            proof.save(self.stats,self.evidence,self.refs,'scenario-1',120000)
            Path(str(self.file)+'.manifest.json').write_text('{"changed":1}')
            with self.assertRaises(QueryBlocked):proof.validate(120000)

    def test_changed_write_counters_fails_closed(self):
        with patch('benchmark.preflight_reuse.database_write_guards',side_effect=[self.db_rev,{'mongo':{'count':500000,'insert':8},'postgres':{'row_count':500000,'tup_inserted':10}}]):
            proof=InvocationValidation(self.file)
            proof.save(self.stats,self.evidence,self.refs,'scenario-1',120000)
            with self.assertRaises(QueryBlocked):proof.validate(120000)

    def test_incomplete_or_missing_proof_refused(self):
        proof=InvocationValidation(self.file)
        with self.assertRaises(QueryBlocked):proof.validate(120000)
        with self.assertRaises(QueryBlocked):proof.save(self.stats,{'status':'ok','mode':'sample','checked':500000},self.refs,'s',120000)
        with self.assertRaises(QueryBlocked):proof.save(self.stats,self.evidence,{'Q1':object()},'s',120000)

    def test_source_replaced_content_same_size_but_new_hash_is_rejected(self):
        with patch('benchmark.preflight_reuse.database_write_guards',return_value=self.db_rev):
            proof=InvocationValidation(self.file)
            proof.save(self.stats,self.evidence,self.refs,'scenario-1',120000)
            self.file.write_text('{"order_id":"xemo"}\n')
            with self.assertRaises(QueryBlocked):proof.validate(120000)
