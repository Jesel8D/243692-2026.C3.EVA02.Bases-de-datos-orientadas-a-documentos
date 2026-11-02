"""Opt-in real data integration in new databases; no collection/table/database deletion."""
from pathlib import Path
import os
import tempfile
import unittest
import uuid

from src.dataset.database import MongoAdapter, PostgresAdapter
from src.dataset.files import configuration, generate
from src.dataset.model import DataError, documents
from src.dataset.operations import compare_dataset, import_dataset


@unittest.skipUnless(os.environ.get('RUN_DATA_INTEGRATION') == '1', 'requires explicit RUN_DATA_INTEGRATION=1 and running containers')
class RealDataIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine = os.environ.get('DATA_TEST_ENGINE', 'both')
        if engine not in ('mongo', 'postgres', 'both'):
            raise DataError('DATA_TEST_ENGINE must be mongo/postgres/both')
        cls.directory = tempfile.TemporaryDirectory(prefix='phase2-integration-')
        cls.path = Path(cls.directory.name) / 'small.jsonl'
        cls.info = generate(cls.path, configuration(count=100), 0)
        database = 'phase2test_' + uuid.uuid4().hex
        cls.adapters = []
        if engine in ('postgres', 'both'):
            admin = PostgresAdapter()
            # Fresh database only. Never DROP/TRUNCATE existing data.
            admin.sql('CREATE DATABASE ' + database + ';\n')
        os.environ['DATA_DATABASE_NAME'] = database
        if engine in ('mongo', 'both'):
            cls.adapters.append(MongoAdapter())
        if engine in ('postgres', 'both'):
            cls.adapters.append(PostgresAdapter())
        print('Real integration database (retained):', database)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()  # Own temporary file only; database remains.

    def test_real_import_resume_and_readback(self):
        for adapter in self.adapters:
            with self.subTest(engine=adapter.engine):
                report = import_dataset(adapter, self.path, batch_size=17)
                self.assertEqual(report['after'], 100)
                with self.assertRaises(DataError):
                    import_dataset(adapter, self.path)
                report = import_dataset(adapter, self.path, batch_size=29, resume=True)
                self.assertEqual(report['already_identical'], 100)
                if adapter.engine == 'postgres':
                    # A fresh row followed by duplicate PK must roll back the entire COPY batch.
                    fresh = next(documents(43, 1, '2025-07-01T00:00:00Z', '2026-10-01T00:00:00Z', 'totals-and-alias'))
                    duplicate = next(documents(42, 1, '2025-07-01T00:00:00Z', '2026-10-01T00:00:00Z', 'totals-and-alias'))
                    with self.assertRaises(DataError):
                        adapter.insert([fresh, duplicate])
                    self.assertEqual(adapter.count(), 100)
                    self.assertEqual(adapter.fetch([fresh['order_id']]), {})

        result = compare_dataset(self.adapters, self.path, batch_size=19)
        self.assertEqual(result['checked'], 100)
        self.assertEqual(result['mode'], 'full')
        self.assertEqual(result['source_sha256'], self.info['sha256'])
        self.assertEqual(compare_dataset(self.adapters, self.path, sample_size=10, sample_seed=7)['checked'], 10)
        print('REAL DATA INTEGRATION OK:', ','.join(a.engine for a in self.adapters), self.info['sha256'])


if __name__ == '__main__':
    unittest.main()
