"""Reusable correctness execution backend. CLI startup/preflight are NOT benchmark latency."""
import json
from math import ceil

from src.dataset.database import MongoAdapter, PostgresAdapter, from_ejson
from src.dataset.model import DataError, parse_json
from .definitions import ROOT, QueryBlocked, QuerySpec


class QueryExecutor:
    def __init__(self, engine, timeout_ms=120000):
        if engine not in ('mongo', 'postgres') or type(timeout_ms) is not int or not 1 <= timeout_ms <= 3600000:
            raise QueryBlocked('Invalid executor engine/timeout')
        self.engine = engine
        self.timeout_ms = timeout_ms
        wall_seconds = ceil(timeout_ms/1000) + 15
        self.adapter = MongoAdapter(wall_seconds) if engine == 'mongo' else PostgresAdapter(wall_seconds)

    def open_session(self, spec, connection):
        """Phase 4 adaptation: same definitions, one native connection per client."""
        if spec.engine != self.engine or spec.timeout_ms != self.timeout_ms:
            raise QueryBlocked('Executor/spec mismatch')
        from .native import NativeSession
        return NativeSession(spec, connection)

    def mongo_action(self, action, **kwargs):
        payload = {'action': action, 'timeout_ms': self.timeout_ms, **kwargs}
        output = self.adapter.execute(['mongosh', '--quiet', '--norc', '--eval', (ROOT/'mongodb/execute.js').read_text()], json.dumps(payload))
        return parse_json(output)

    def pg_session(self, body, options=None, raw_plan=False):
        options = options or {}
        script = "BEGIN READ ONLY;\nSET LOCAL search_path=public,pg_catalog;\nSET LOCAL TimeZone='UTC';\n"
        script += f"SET LOCAL statement_timeout='{self.timeout_ms}ms';\nSET LOCAL lock_timeout='{self.timeout_ms}ms';\n"
        if options:
            value = options.get('work_mem')
            if value not in ('4MB', '64MB') or set(options) != {'work_mem'}:
                raise QueryBlocked('Unsupported PostgreSQL variant')
            script += f"SET LOCAL work_mem='{value}';\n"
        script += "SELECT json_build_object('work_mem',current_setting('work_mem'),'statement_timeout',current_setting('statement_timeout'),'server_version',current_setting('server_version'),'backend_pid',pg_backend_pid());\n"
        script += body + "\nROLLBACK;\n"
        output = self.adapter.sql(script)
        first, _, rest = output.partition('\n')
        effective = parse_json(first)
        if options and effective['work_mem'] != options['work_mem']:
            raise QueryBlocked('Effective work_mem differs in the query session')
        result = parse_json(rest) if raw_plan else [parse_json(line) for line in rest.splitlines() if line]
        return effective, result

    def preflight(self, query):
        try:
            if self.engine == 'mongo':
                info = from_ejson(self.mongo_action('preflight'))
                strings, numeric = 'string', 'decimal'
                for row in info['item_types']:
                    if row['qty'] not in ('int', 'long') or row['price'] != 'decimal':
                        raise QueryBlocked('Mongo requires integer qty and Decimal128 price')
            else:
                _, rows = self.pg_session((ROOT/'postgresql/preflight.sql').read_text())
                info = rows[0]
                strings, numeric = 'string', 'number'
                for row in info['item_types']:
                    if row['qty'] != 'number' or row['price'] != 'number':
                        raise QueryBlocked('JSONB qty/price must be numeric tokens, never strings')
            for row in info['order_types']:
                if any(row[k] != strings for k in ('timestamp','status','order_id','customer_id')):
                    raise QueryBlocked('Stored timestamps/IDs/status are not canonical strings')
                if query == 'Q2' and any(row[k] != numeric for k in ('final_total','totals_final_total')):
                    raise QueryBlocked('Q2 incompatible: final_total missing or not numeric (totals-only is blocked)')
            if info['invalid_timestamps'] or info['invalid_qty'] or (query == 'Q2' and info['invalid_alias']):
                raise QueryBlocked('Invalid UTC dates, qty or final_total/totals alias')
            return info
        except DataError as exc:
            raise QueryBlocked('Preflight failed: schema/calendar/engine/authentication must be checked locally') from exc

    def execute(self, spec, *, explain=False, preflight=True):
        if not isinstance(spec, QuerySpec) or spec.engine != self.engine or spec.timeout_ms != self.timeout_ms:
            raise QueryBlocked('Executor/spec mismatch')
        try:
            observed = self.preflight(spec.query) if preflight else None
            if self.engine == 'mongo':
                raw = self.mongo_action('explain' if explain else 'run', pipeline=spec.pipeline, options=spec.options)
                if explain:
                    # Preserve Extended JSON diagnostic doubles instead of treating them as query amounts.
                    result = {'effective': from_ejson(raw['effective']), 'plan': raw['plan']}
                else:
                    result = from_ejson(raw)
            else:
                body = 'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + spec.sql + ';' if explain else 'SELECT row_to_json(q) FROM (' + spec.sql + ') q;'
                effective, data = self.pg_session(body, spec.options, raw_plan=explain)
                result = {'effective': effective, 'plan' if explain else 'rows': data}
            return {'engine': self.engine, 'query': spec.query, 'variant': spec.variant,
                    'preflight': observed, **result}
        except DataError as exc:
            raise QueryBlocked('Query/explain command failed; inspect engine, schema, privileges and timeout locally') from exc
