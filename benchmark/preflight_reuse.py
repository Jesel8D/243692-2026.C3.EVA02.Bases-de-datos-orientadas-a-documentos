"""Per-invocation proof reuse. Never trust an old receipt or reuse across processes.

Writer exclusion remains a methodological condition: the database endpoints must be
reserved for the study, with no independent writer or DDL session. Change counters
make ordinary writes observable; they cannot mathematically prove immutability.
"""
import hashlib
import os
from pathlib import Path

from queries.definitions import QueryBlocked
from src.dataset.model import parse_json


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def file_fingerprint(path):
    path = Path(path)
    s = path.stat()
    manifest = Path(str(path) + '.manifest.json')
    return {'data_sha256': file_sha256(path),
            'manifest_sha256': file_sha256(manifest),
            'source_dev': s.st_dev, 'source_ino': s.st_ino,
            'source_size': s.st_size, 'source_mtime_ns': s.st_mtime_ns,
            'source_ctime_ns': s.st_ctime_ns}


def database_write_guards(timeout_ms=120000):
    """Read-only metadata and cumulative writes; fail closed if unavailable/reset."""
    from queries.execution import QueryExecutor
    from pymongo import MongoClient
    # Includes the database OID, reset epoch, original table identity and DML
    # counters. An empty or ambiguous response must not authorize reuse.
    sql = '''
SELECT row_to_json(x) FROM (
 SELECT d.datid::text AS database_oid, d.stats_reset::text AS stats_reset,
        d.tup_inserted, d.tup_updated, d.tup_deleted,
        c.oid::text AS table_oid, c.relfilenode::text AS relfilenode,
        (SELECT count(*) FROM public.orders) AS row_count
 FROM pg_stat_database d, pg_class c
 WHERE d.datname=current_database() AND c.oid='public.orders'::regclass
) x;
'''
    rows = [parse_json(s) for s in QueryExecutor('postgres',timeout_ms).adapter.sql(sql).splitlines() if s.strip()]
    if len(rows) != 1 or rows[0].get('row_count') != 500000:
        raise QueryBlocked('Global validation cache: PostgreSQL revision/count unavailable or changed')
    user = os.environ.get('MONGO_USERNAME')
    pwd = os.environ.get('MONGO_PASSWORD')
    name = os.environ.get('DATA_DATABASE_NAME')
    if not user or not pwd or not name:
        raise QueryBlocked('Global validation cache: Mongo credentials/database unavailable')
    with MongoClient(host='127.0.0.1',port=27017,username=user,password=pwd,
                     authSource='admin',serverSelectionTimeoutMS=5000,
                     retryReads=False,retryWrites=False) as client:
        db = client[name]
        status = client.admin.command('serverStatus')
        operations = status.get('opcounters',{})
        inventory = list(db.list_collections(filter={'name':'orders'}))
        if len(inventory)!=1:
            raise QueryBlocked('Global validation cache: Mongo collection identity unavailable')
        count = db.orders.estimated_document_count()
        if count != 500000:
            raise QueryBlocked('Global validation cache: MongoDB document count changed')
        uuid = inventory[0].get('info',{}).get('uuid')
        if uuid is None or not all(k in operations for k in ('insert','update','delete')):
            raise QueryBlocked('Global validation cache: MongoDB write/identity counters unavailable')
        mongo = {'collection_uuid': str(uuid), 'count': count,
                 'insert': int(operations['insert']),
                 'update': int(operations['update']),
                 'delete': int(operations['delete'])}
    return {'postgres': rows[0], 'mongo': mongo}


class InvocationValidation:
    """Never persisted; first full proof belongs to this one CLI invocation only."""
    def __init__(self, dataset):
        self.dataset = str(Path(dataset).resolve())
        self.ready = False
        self.stats = None
        self.data_evidence = None
        self.references = {}
        self.revision = None
        self.source = None
        self.original_scenario_id = None

    def check_source(self):
        source = file_fingerprint(self.dataset)
        if self.ready and source != self.source:
            raise QueryBlocked('Global preflight reuse blocked: source/manifest changed')
        return source

    def check_revision(self, timeout_ms):
        current = database_write_guards(timeout_ms)
        if self.ready and current != self.revision:
            raise QueryBlocked('Global preflight reuse blocked: DB write counters/identity/count changed')
        return current

    def save(self, stats, data_evidence, references, scenario_id, timeout_ms):
        if self.ready:
            raise QueryBlocked('Global preflight must not be overwritten')
        if data_evidence.get('status') != 'ok' or data_evidence.get('mode') != 'full' or data_evidence.get('checked') != 500000:
            raise QueryBlocked('Only verified full comparison qualifies for global reuse')
        if not {'Q1','Q2'} <= set(references):
            raise QueryBlocked('Both source references required for global reuse')
        source = self.check_source()
        if source['data_sha256'] != stats['sha256']:
            raise QueryBlocked('Global preflight: source hash differs from verified file')
        revision = self.check_revision(timeout_ms)
        self.stats = stats
        self.data_evidence = data_evidence
        self.references = references
        self.source = source
        self.revision = revision
        self.original_scenario_id = scenario_id
        self.ready = True

    def validate(self, timeout_ms):
        if not self.ready:
            raise QueryBlocked('No current invocation full preflight proof')
        self.check_source()
        self.check_revision(timeout_ms)
        return {'status':'PASS','method':'same-process full-preflight evidence reuse',
                'original_scenario_id':self.original_scenario_id,
                'source_sha256':self.source['data_sha256'],
                'change_guard':'source+manifest SHA256, Mongo collection UUID/count/opcounters, PostgreSQL table OID/relfilenode/count/DML statistics',
                'limitations':'requires exclusive/no-external-writers; counters cannot prove immutability against DDL or all privileged changes'}
