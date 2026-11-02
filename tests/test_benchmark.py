"""Runner logic tests only. Simulated executors/telemetry are NOT DB measurements."""
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
import sqlite3,tempfile,threading,time,unittest
from benchmark.matrix import matrix,Scenario
from benchmark.config import Protocol
from benchmark.metrics import percentiles,stage
from benchmark.runner import run_repetition
from benchmark.results import Store,read_csv,write_json,consolidate,COLUMNS,experiment_lock
from benchmark.telemetry import MissingTelemetry,CgroupTelemetry
from queries.definitions import QueryBlocked


class FakeSession:
    def __init__(self,factory,i):self.factory=factory;self.i=i;self.effective={'test_only':True,'client_id':i}
    def execute(self):
        with self.factory.lock:
            self.factory.active+=1;self.factory.maximum=max(self.factory.maximum,self.factory.active)
            self.factory.calls+=1;n=self.factory.calls
        try:
            time.sleep(.002)
            if self.factory.fail and n>=self.factory.fail:raise TimeoutError('unit controlled failure')
            return 1
        finally:
            with self.factory.lock:self.factory.active-=1
    def verify(self):return self.effective
    def close(self):
        with self.factory.lock:self.factory.closed.add(self.i)


class FakeFactory:
    evidence_kind='simulated_runner_test'
    def __init__(self,fail=None):self.lock=threading.Lock();self.active=0;self.maximum=0;self.calls=0;self.closed=set();self.fail=fail
    def __call__(self,spec,i):return FakeSession(self,i)


class FakeTelemetry(MissingTelemetry):
    def stop(self):return {'cpu_throttled_seconds':Decimal('0.1'),'max_rss_mb':Decimal('10'),'disk_spill':False,'oom_killed':False,'source':'SIMULATED UNIT TEST ONLY'}


def configuration(scenario):
    return {'dataset':{'sha256':'unit-fixture'},'identities':{'postgres':{'server_version':'unit-only'}},'sources':{'queries':'unit-only'},
            'protocol':asdict(Protocol('test',0,.08,0)),'evidence_kind':'simulated_runner_test',
            'selection':{'plan':[{'id':scenario.id,**asdict(scenario)}]}}


class BenchmarkTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def scenario(self,c=1,r=1):return Scenario('postgres','severe','Q1','default',c,r)
    def run_test(self,*,c=1,factory=None,telemetry=None,external=None):
        d=self.root/('raw-'+str(time.monotonic_ns()));d.mkdir()
        s=self.scenario(c);factory=factory or FakeFactory()
        result=run_repetition(s,Protocol('test',.02,.12,0,timeout_ms=500),d,factory,telemetry or FakeTelemetry(),external_cancel=external)
        return d,s,result,factory

    def test_base_and_extended_matrix_counts(self):
        a=matrix('base',base_variants={'mongo':'allow_disk_false','postgres':'work_mem_4mb'})
        b=matrix('extended')
        self.assertEqual(len(a),108);self.assertEqual(len(b),162)
        self.assertEqual(len({(s.engine,s.profile,s.query,s.variant,s.concurrency) for s in a}),36)
        self.assertEqual(len({(s.engine,s.profile,s.query,s.variant,s.concurrency) for s in b}),54)
        self.assertEqual(len({s.id for s in b}),162)
        with self.assertRaises(QueryBlocked):matrix('base')

    def test_filters_ids_invalid_variants_and_protocol(self):
        self.assertEqual(len(matrix('extended',engine='postgres',profile='severe',query='Q2',variant='work_mem_4mb',concurrency=10,run_number=2)),1)
        self.assertEqual(self.scenario().id,self.scenario().id)
        for kw in [dict(profile='wrong'),dict(variant='work_mem_2mb')]:
            with self.assertRaises(QueryBlocked):matrix('extended',**kw)
        with self.assertRaises(QueryBlocked):matrix('single',engine='mongo')
        with self.assertRaises(QueryBlocked):Protocol('definitive',1,2,3,cache='manual')
        with self.assertRaises(QueryBlocked):Protocol('definitive',cache='skip')

    def test_exact_percentiles_type7(self):
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE latencies(ns INTEGER)')
        self.assertIsNone(percentiles(db)['latency_p99_ms'])
        db.executemany('INSERT INTO latencies VALUES (?)',[(x*1000000,) for x in (4,1,3,2)])
        p=percentiles(db)
        self.assertEqual(p['latency_p50_ms'],Decimal('2.5'))
        self.assertEqual(p['latency_p95_ms'],Decimal('3.85'))
        self.assertEqual(p['latency_p99_ms'],Decimal('3.97'))
        db.close()

    def test_boundary_classification(self):
        self.assertEqual(stage(100,200,100,200),'measurement')
        self.assertEqual(stage(99,150,100,200),'excluded_boundary')
        self.assertEqual(stage(100,201,100,200),'excluded_boundary')
        self.assertEqual(stage(200,200,100,200),'excluded_boundary')

    def test_concurrency_one_ten_fifty_no_reduction(self):
        for c in (1,10,50):
            d,s,result,factory=self.run_test(c=c)
            self.assertEqual(result['clients_connected'],c)
            self.assertEqual(len(factory.closed),c)
            self.assertTrue(result['window_complete'])
            self.assertGreater(result['metrics']['samples'],0)
            duration=Decimal('.12')
            self.assertEqual(result['metrics']['throughput_qps'],Decimal(result['metrics']['samples'])/duration)
            self.assertFalse(result['eligible_for_final_analysis'])
            if c>1:self.assertGreater(factory.maximum,1)
            self.assertEqual(len(list(d.glob('client-*.sqlite'))),c)

    def test_missing_telemetry_not_zero_or_ok(self):
        _,_,r,_=self.run_test(telemetry=MissingTelemetry())
        self.assertEqual(r['status'],'error')
        self.assertIsNone(r['telemetry']['cpu_throttled_seconds'])
        self.assertIsNone(r['telemetry']['max_rss_mb'])
        self.assertIsNone(r['telemetry']['disk_spill'])
        self.assertFalse(r['eligible_for_final_analysis'])

    def test_connection_failure_no_fake_throughput(self):
        class Refused(FakeFactory):
            def __call__(self,spec,i):raise ConnectionRefusedError('unit only')
        _,_,r,_=self.run_test(factory=Refused())
        self.assertEqual(r['clients_connected'],0)
        self.assertEqual(r['errors'][0]['category'],'connection')
        self.assertIsNone(r['metrics']['throughput_qps'])
        from benchmark.workers import error_info
        for name in ('OperationalError','InterfaceError','AutoReconnect','ConnectionFailure'):
            self.assertEqual(error_info(type(name,(Exception,),{})(),'measurement')['category'],'connection')

    def test_midwindow_cancel_not_finalized(self):
        cancel=threading.Event();d=self.root/'mid-cancel';d.mkdir();f=FakeFactory()
        timer=threading.Timer(.12,cancel.set);timer.start()
        try:
            with self.assertRaises(InterruptedError):
                run_repetition(self.scenario(),Protocol('test',0,.4,0,timeout_ms=500),d,f,FakeTelemetry(),external_cancel=cancel)
        finally:timer.join()
        self.assertEqual(f.closed,{0})
        self.assertFalse((d/'results.csv').exists())

    def test_query_error_not_success_or_retry(self):
        _,_,r,f=self.run_test(factory=FakeFactory(fail=1))
        self.assertEqual(r['status'],'error')
        self.assertFalse(r['window_complete'])
        self.assertIsNone(r['metrics']['throughput_qps'])
        self.assertTrue(r['errors']);self.assertEqual(f.calls,1)
        self.assertEqual(f.closed,{0})

    def test_simulator_never_runs_as_pilot(self):
        d=self.root/'reject';d.mkdir()
        with self.assertRaises(QueryBlocked):run_repetition(self.scenario(),Protocol('pilot',0,.1,0),d,FakeFactory(),FakeTelemetry())

    def test_cancellation_incomplete_and_connections_close(self):
        cancel=threading.Event();cancel.set();d=self.root/'cancel';d.mkdir();f=FakeFactory()
        with self.assertRaises(InterruptedError):run_repetition(self.scenario(),Protocol('test',0,.1,0,timeout_ms=100),d,f,FakeTelemetry(),external_cancel=cancel)
        self.assertEqual(f.closed,{0})

    def test_direct_cgroup_delta_units_and_unknown_rss(self):
        p=self.root/'cgroup';p.mkdir()
        (p/'cpu.stat').write_text('throttled_usec 1000000\nnr_throttled 999\n')
        (p/'memory.events').write_text('oom_kill 0\n')
        t=CgroupTelemetry(p);t.start()
        (p/'cpu.stat').write_text('throttled_usec 1250000\nnr_throttled 1999\n')
        r=t.stop()
        self.assertEqual(r['cpu_throttled_seconds'],Decimal('.25'))
        self.assertIsNone(r['max_rss_mb']);self.assertIsNone(r['disk_spill'])
        (p/'cpu.stat').write_text('throttled_usec 1\n')
        self.assertIsNone(t.stop()['cpu_throttled_seconds'])

    def store_case(self):
        s=self.scenario();root=self.root/'store';store=Store(root,configuration(s))
        d=store.begin(s)
        result=run_repetition(s,Protocol('test',0,.08,0,timeout_ms=500),d,FakeFactory(),FakeTelemetry())
        return store,s,d,result

    def test_csv_header_single_row_commit_resume_no_duplicate(self):
        store,s,d,result=self.store_case();store.commit(s,d,result)
        rows=read_csv(d/'results.csv');self.assertEqual(len(rows),1)
        self.assertEqual((d/'results.csv').read_text().splitlines()[0],','.join(COLUMNS))
        self.assertNotIn('variant',COLUMNS)
        self.assertEqual(rows[0]['disk_spill'],'0')
        resumed=Store(store.path,configuration(s),resume=True)
        self.assertIn(s.id,resumed.finished)
        with self.assertRaises(QueryBlocked):resumed.begin(s)
        with self.assertRaises(QueryBlocked):store.commit(s,d,result)

    def test_corrupt_committed_csv_and_changed_dataset_rejected(self):
        store,s,d,result=self.store_case();store.commit(s,d,result)
        (d/'results.csv').write_text('timestamp_epoch,engine\npartial')
        with self.assertRaises(QueryBlocked):Store(store.path,configuration(s),resume=True)
        other=configuration(s);other['dataset']['sha256']='different'
        with self.assertRaises(QueryBlocked):Store(store.path,other,resume=True)

    def test_incomplete_corrupt_csv_preserved_new_attempt(self):
        s=self.scenario();root=self.root/'partial';store=Store(root,configuration(s));d=store.begin(s)
        (d/'results.csv').write_text('partial')
        resumed=Store(root,configuration(s),resume=True)
        self.assertFalse(resumed.finished)
        self.assertEqual(resumed.incomplete_details[0]['csv_state'],'corrupt_uncommitted')
        new=resumed.begin(s);self.assertNotEqual(new,d)
        self.assertEqual((d/'results.csv').read_text(),'partial')
        result=run_repetition(s,Protocol('test',0,.05,0,timeout_ms=500),new,FakeFactory(),FakeTelemetry())
        resumed.commit(s,new,result)
        again=Store(root,configuration(s),resume=True)
        self.assertEqual(len(again.finished),1)
        self.assertEqual(again.unresolved_incomplete,[])
        consolidate([root],self.root/'recovered.csv',allow_nonfinal=True)

    def test_consolidation_requires_sidecars_and_rejects_nonfinal(self):
        store,s,d,result=self.store_case();store.commit(s,d,result)
        with self.assertRaises(QueryBlocked):consolidate([store.path],self.root/'forbidden.csv')
        out=self.root/'diagnostic.csv'
        consolidate([store.path],out,allow_nonfinal=True)
        self.assertEqual(len(read_csv(out)),1)
        self.assertTrue(Path(str(out)+'.manifest.json').exists())
        with self.assertRaises(QueryBlocked):consolidate([store.path,store.path],self.root/'duplicate.csv',allow_nonfinal=True)

    def test_experiment_lock(self):
        path=self.root/'locked'
        with experiment_lock(path):
            with self.assertRaises(QueryBlocked):
                with experiment_lock(path):pass

    def test_resume_rejects_protocol_sources_and_engine_changes(self):
        store,s,d,result=self.store_case();store.commit(s,d,result)
        import copy
        for field in ('protocol','sources','identities'):
            changed=copy.deepcopy(configuration(s));changed[field]['changed']='unit-only'
            with self.assertRaises(QueryBlocked):Store(store.path,changed,resume=True)

    def test_modes_never_mix_even_for_diagnostic_consolidation(self):
        store,s,d,result=self.store_case();store.commit(s,d,result)
        other=configuration(s);other['protocol']['mode']='pilot'
        second=Store(self.root/'second-mode',other);attempt=second.begin(s)
        r=run_repetition(s,Protocol('test',0,.08,0,timeout_ms=500),attempt,FakeFactory(),FakeTelemetry())
        second.commit(s,attempt,r)
        with self.assertRaises(QueryBlocked):consolidate([store.path,second.path],self.root/'mixed.csv',allow_nonfinal=True)

    def test_native_mongo_options_consumption_and_close_unit_only(self):
        from unittest.mock import patch
        from queries.native import NativeSession,Connection
        from queries.definitions import QuerySpec
        class Cursor:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def __iter__(self):
                for i in range(7):
                    observed['consumed']+=1
                    yield {'unit_only':i}
        class Client:
            def __init__(self,**kw):observed['connection']=kw;self.admin=self
            def command(self,name):return {'ok':1}
            def server_info(self):return {'version':'unit-mongo-only'}
            def __getitem__(self,name):return self
            def aggregate(self,pipeline,**kw):observed['pipeline']=pipeline;observed['options']=kw;return Cursor()
            def close(self):observed['closed']=True
        for variant,allowed in [('allow_disk_false',False),('allow_disk_true',True)]:
            observed={'consumed':0}
            spec=QuerySpec('mongo','Q2',variant,500)
            with patch('pymongo.MongoClient',Client):
                session=NativeSession(spec,Connection('unit-only',27017,'unit','fixture','fixture'))
                self.assertEqual(session.execute(),7);session.close()
            self.assertEqual(observed['pipeline'],spec.pipeline)
            self.assertEqual(observed['options'],{'maxTimeMS':500,'allowDiskUse':allowed})
            self.assertEqual(observed['connection']['maxPoolSize'],1)
            self.assertFalse(observed['connection']['retryReads'])
            self.assertEqual(observed['consumed'],7);self.assertTrue(observed['closed'])
