"""Persistent, thread-owned native sessions over the original QuerySpec definitions."""
from dataclasses import dataclass, field
from .definitions import QueryBlocked


@dataclass(frozen=True)
class Connection:
    host: str
    port: int
    database: str
    username: str = field(repr=False)
    password: str = field(repr=False)


class NativeSession:
    evidence_kind = 'real_native_driver'

    def __init__(self, spec, connection):
        self.spec = spec
        self.client = None
        self.connection = connection
        self.observation = None
        self.observation_token = None
        try:
            if spec.engine == 'postgres':
                import psycopg
                from psycopg.rows import dict_row
                self.client = psycopg.connect(host=connection.host, port=connection.port,
                    dbname=connection.database, user=connection.username, password=connection.password,
                    connect_timeout=max(1,(spec.timeout_ms+999)//1000), autocommit=True,
                    prepare_threshold=None, application_name='academic_benchmark',row_factory=dict_row)
                for name,value in [('statement_timeout',str(spec.timeout_ms)),('TimeZone','UTC'),('search_path','public,pg_catalog'),('default_transaction_read_only','on')]:
                    self.client.execute('SELECT set_config(%s,%s,false)',(name,value)).fetchone()
                if 'work_mem' in spec.options:
                    self.client.execute('SELECT set_config(%s,%s,false)',('work_mem',spec.options['work_mem'])).fetchone()
                self.effective = self._pg_effective()
                if spec.options and self.effective['work_mem'] != spec.options['work_mem']:
                    raise QueryBlocked('Native session work_mem mismatch')
                self.statement = spec.sql
            else:
                from pymongo import MongoClient
                self.client = MongoClient(host=connection.host,port=connection.port,
                    username=connection.username,password=connection.password,authSource='admin',
                    maxPoolSize=1,minPoolSize=0,maxConnecting=1,retryReads=False,retryWrites=False,
                    serverSelectionTimeoutMS=spec.timeout_ms,connectTimeoutMS=spec.timeout_ms,
                    socketTimeoutMS=spec.timeout_ms+1000,waitQueueTimeoutMS=spec.timeout_ms)
                self.client.admin.command('ping')
                self.collection = self.client[connection.database]['orders']
                self.pipeline = spec.pipeline
                self.effective = {'server_version':self.client.server_info()['version'],
                    'options':spec.options,'maxPoolSize':1,'retryReads':False}
        except BaseException:
            self.close()
            raise

    def _pg_effective(self):
        row = self.client.execute("SELECT current_setting('server_version') AS version,current_setting('work_mem') AS work_mem,pg_backend_pid() AS pid").fetchone()
        return {'server_version':row['version'],'work_mem':row['work_mem'],'backend_pid':row['pid'],'prepare_threshold':None}

    def execute(self):
        # No connections, SET or SHOW here. Fully consume result batches before returning.
        count = 0
        if self.spec.engine == 'postgres':
            with self.client.cursor() as cursor:
                cursor.execute(self.statement)
                while True:
                    rows = cursor.fetchmany(128)
                    if not rows: break
                    count += len(rows)
        else:
            with self.collection.aggregate(self.pipeline, maxTimeMS=self.spec.timeout_ms, **self.spec.options, **({'comment':self.observation} if self.observation else {})) as cursor:
                for _ in cursor: count += 1
        return count

    def enable_spill_capture(self, token, client_id):
        """Explicit instrumentation only, configured outside the measured query."""
        self.observation_token=token;self.observation_client=client_id
        if self.spec.engine=='postgres':
            try:
                self.client.execute("SELECT set_config('log_temp_files','0',false)").fetchone()
                row=self.client.execute("SELECT current_setting('log_temp_files') AS temp,current_setting('log_line_prefix') AS prefix,current_setting('log_timezone') AS timezone,current_setting('logging_collector') AS collector,current_setting('log_destination') AS destination,current_setting('lc_messages') AS lc_messages").fetchone()
                valid=row['temp']=='0' and row['prefix']=='%m [%p] ' and row['timezone'] in ('UTC','Etc/UTC','GMT') and row['collector']=='off' and row['destination']=='stderr' and row['lc_messages'] in ('C','POSIX','C.UTF-8','en_US.utf8','en_US.UTF-8','en_US')
                self.effective.update(spill_capture=valid,spill_settings=row)
            except Exception as exc:
                self.effective.update(spill_capture=False,spill_error_class=type(exc).__name__)
        else:
            self.effective.update(spill_capture=True,spill_source='filtered system.profile, actual operation tags; explicit usedDisk required')

    def set_observation(self, phase, sequence):
        if self.observation_token is None:return None
        tag=str(self.observation_client)+':'+phase+':'+str(sequence)
        if self.spec.engine=='mongo':
            self.observation={'benchmark_token':self.observation_token,'phase':phase,'tag':tag}
        return tag

    def validate_once(self, reference):
        """Untimed startup correctness check, before cache stage and warmup."""
        if self.spec.engine == 'postgres':
            with self.client.cursor() as cursor:
                cursor.execute(self.statement)
                rows=cursor.fetchall()
        else:
            from bson.decimal128 import Decimal128
            def decode(v):
                if isinstance(v,Decimal128): return v.to_decimal()
                if isinstance(v,dict):return {k:decode(x) for k,x in v.items()}
                if isinstance(v,list):return [decode(x) for x in v]
                return v
            with self.collection.aggregate(self.pipeline,maxTimeMS=self.spec.timeout_ms,**self.spec.options) as cursor:
                rows=[decode(r) for r in cursor]
        from .validation import validate_q1,validate_q2
        result=(validate_q1 if self.spec.query=='Q1' else validate_q2)(reference,rows,self.spec.engine)
        if result['status']!='PASS':raise QueryBlocked('Native client startup result failed independent oracle')
        return result

    def verify(self):
        if self.spec.engine == 'postgres':
            observed = self._pg_effective()
            if observed['work_mem'] != self.effective['work_mem']:
                raise QueryBlocked('Session work_mem changed during repetition')
        return self.effective

    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None
