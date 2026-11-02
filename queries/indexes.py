"""Read-only inventory, explicit safe additions; never drop/replace indexes."""
import re
from src.dataset.database import from_ejson
from src.dataset.model import parse_json
from .definitions import ROOT, QueryBlocked

PG_INVENTORY = """
SELECT json_build_object('name',ci.relname,'primary',i.indisprimary,'unique',i.indisunique,
'valid',i.indisvalid,'ready',i.indisready,'nkeys',i.indnkeyatts,'natts',i.indnatts,
'access_method',am.amname,'definition',pg_get_indexdef(i.indexrelid),
'expression',pg_get_expr(i.indexprs,i.indrelid),'predicate',pg_get_expr(i.indpred,i.indrelid),
'columns',(SELECT json_agg(a.attname ORDER BY k.ordinality) FROM unnest(i.indkey) WITH ORDINALITY k(attnum,ordinality)
JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum))
FROM pg_index i JOIN pg_class ci ON ci.oid=i.indexrelid JOIN pg_am am ON am.oid=ci.relam
WHERE i.indrelid='public.orders'::regclass ORDER BY ci.relname;
"""


def audit_mongo(rows):
    expected = [({'_id':1}, True), ({'timestamp':1}, False), ({'order_id':1}, False)]
    missing = []
    unexpected = []
    for key, unique in expected:
        if not any(r.get('key') == key and bool(r.get('unique', r.get('key')=={'_id':1})) == unique for r in rows):
            missing.append(key)
    seen = []
    for row in rows:
        duplicate = row.get('key') in seen
        seen.append(row.get('key'))
        if duplicate or not any(row.get('key') == key and bool(row.get('unique', row.get('key')=={'_id':1})) == unique for key, unique in expected) or any(k in row for k in ('sparse','partialFilterExpression','expireAfterSeconds','collation')):
            unexpected.append(row)
    return {'status':'PASS' if not missing and not unexpected else 'BLOCKED',
            'engine':'mongo','missing':missing,'unexpected':unexpected,'indexes':rows}


def audit_postgres(rows):
    pk = []
    text = []
    unexpected = []
    for row in rows:
        expression = re.sub(r'[\s()]', '', row.get('expression') or '')
        simple = row['access_method']=='btree' and row['valid'] and row['ready'] and row['nkeys']==row['natts']==1 and row['predicate'] is None
        if simple and row['primary'] and row['unique'] and row['columns']==['id']:
            pk.append(row)
        elif simple and not row['primary'] and not row['unique'] and expression in ("data->>'timestamp'::text", "data->>'timestamp'"):
            text.append(row)
        else:
            unexpected.append(row)
    return {'status':'BLOCKED','engine':'postgres','indexes':rows,'unexpected':unexpected,
            'primary_key_ok':len(pk)==1,'timestamp_text_index_present':len(text)==1,
            'physical_index_status':'PASS' if len(pk)==len(text)==1 and not unexpected else 'BLOCKED',
            'reason':'text B-Tree is a proposal; original Q2 casts to timestamptz. No claim of matching predicate/index usage or academic approval'}


def inspect_indexes(executor, *, apply=False, accept_text_proposal=False):
    if executor.engine=='mongo':
        rows = from_ejson(executor.mongo_action('indexes'))
        before = audit_mongo(rows)
        if apply:
            if before['unexpected']:
                raise QueryBlocked('Unexpected Mongo indexes: refusing automatic deletion/replacement')
            rows = from_ejson(executor.mongo_action('prepare_indexes'))
        return {**audit_mongo(rows),'applied':apply}
    rows = [parse_json(line) for line in executor.adapter.sql(PG_INVENTORY).splitlines() if line]
    before = audit_postgres(rows)
    volatility = executor.adapter.sql("SELECT provolatile FROM pg_proc WHERE oid='pg_catalog.timestamptz_in(cstring,oid,integer)'::regprocedure;\n")
    if apply and (not before['primary_key_ok'] or before['unexpected']):
        raise QueryBlocked('Unexpected PostgreSQL indexes/PK: no indexes were deleted/replaced')
    if apply and accept_text_proposal and not before['timestamp_text_index_present']:
        executor.adapter.sql(f"BEGIN; SET LOCAL statement_timeout='{executor.timeout_ms}ms'; SET LOCAL lock_timeout='{executor.timeout_ms}ms';\n" + (ROOT/'postgresql/timestamp_text_index.sql').read_text() + '\nCOMMIT;\n')
        rows = [parse_json(line) for line in executor.adapter.sql(PG_INVENTORY).splitlines() if line]
    report = audit_postgres(rows)
    report.update({'applied':bool(apply and accept_text_proposal),'text_proposal_accepted_for_preparation':accept_text_proposal,
                   'timestamptz_input_volatility':volatility,
                   'original_cast_index':'BLOCKED: stable input conversion; cannot declare a false IMMUTABLE wrapper'})
    return report
