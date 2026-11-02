"""Simulated telemetry fixtures test software only, never real database measurements."""
from pathlib import Path
from decimal import Decimal as D
from unittest.mock import patch
import json,sqlite3,tempfile,time,unittest,io,urllib.error
from observability.config import settings,local_url,duration_seconds
from observability.series import select_container,selector,has_id,counter_delta,rss_max,window_samples
from observability.prometheus import Prometheus
from observability.events import epoch_ns,pg_log,classify_oom
from observability.spill import postgres_spill,MongoProfiler
from observability.provider import ExperimentalTelemetry
from benchmark.config import Protocol
from benchmark.matrix import Scenario
from benchmark.results import Store,read_csv
from benchmark.runner import run_repetition
from benchmark.telemetry import MissingTelemetry
from test_benchmark import FakeFactory,configuration
from queries.definitions import QueryBlocked
CID='a'*64
LABELS={'id':'/system.slice/docker-'+CID+'.scope','container_label_com_docker_compose_project':'unit','container_label_com_docker_compose_service':'postgres','container_label_academic_profile':'PROFILE_C_SEVERE'}
IDENTITY={'id':CID,'project':'unit','service':'postgres','profile':'PROFILE_C_SEVERE'}

class ObservabilityTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def raw(self,rows):
        db=sqlite3.connect(self.root/'client-000.sqlite')
        db.execute('CREATE TABLE operations(phase TEXT,start_ns INTEGER,end_ns INTEGER,outcome TEXT,tag TEXT)')
        db.executemany('INSERT INTO operations VALUES (?,?,?,?,?)',rows);db.commit();db.close()
    def test_exact_id_and_compose_labels(self):
        self.assertTrue(has_id(LABELS['id'],CID));self.assertTrue(has_id('/docker/'+CID,CID))
        self.assertFalse(has_id('/docker/'+CID+'f',CID))
        self.assertEqual(select_container([{'metric':LABELS}],IDENTITY),LABELS)
        with self.assertRaises(QueryBlocked):select_container([{'metric':LABELS}]*2,IDENTITY)
        with self.assertRaises(QueryBlocked):has_id('/docker/'+CID,CID[:12])
        records=[{'metric':LABELS,'value':[100,'50']},{'metric':LABELS,'value':[100,'100']}]
        self.assertEqual(select_container(records,IDENTITY,now=100),LABELS)
        records[0]['value'][1]='100'
        with self.assertRaises(QueryBlocked):select_container(records,IDENTITY,now=100)
    def test_wrong_profile_or_project_rejected(self):
        for key in ('project','service','profile'):
            bad=dict(IDENTITY);bad[key]='wrong'
            with self.assertRaises(QueryBlocked):select_container([{'metric':LABELS}],bad)
    def test_promql_uses_exact_label_and_valid_metric(self):
        q=selector('container_memory_rss',LABELS)
        self.assertIn('id="'+LABELS['id']+'"',q)
        with self.assertRaises(QueryBlocked):selector('metric} or up',LABELS)
    def test_observed_counter_delta_and_valid_zero(self):
        rows=[(D(1),D(8)),(D(2),D(9)),(D(3),D(9))]
        value,meta=counter_delta(rows,D('.5'),D('3.5'))
        self.assertEqual(value,1);self.assertEqual(meta['covered_seconds'],2)
        self.assertEqual(counter_delta([(D(1),D(8)),(D(2),D(8))],1,2)[0],0)
    def test_counter_reset_is_unknown(self):
        with self.assertRaises(QueryBlocked):counter_delta([(D(1),D(8)),(D(2),D(1))],1,2)
    def test_rss_decimal_mb_not_working_set(self):
        self.assertEqual(rss_max([(D(1),D(1000000)),(D(2),D(2500000))],1,2)[0],D('2.5'))
    def test_no_samples_gaps_and_missing_boundary(self):
        for rows,start,end in [([],1,5),([(D(1),D(8))],1,5),([(D(1),D(8)),(D(9),D(8))],1,9),([(D(4),D(8)),(D(5),D(8))],0,5)]:
            with self.assertRaises(QueryBlocked):window_samples(rows,start,end)
    def test_rfc3339_nanoseconds_exact(self):
        self.assertEqual(epoch_ns('2026-01-01T00:00:00.123456789Z')%10**9,123456789)
        with self.assertRaises(ValueError):epoch_ns('2026-01-01T00:00:00+01:00')
    def test_pg_log_extracts_only_tempfile_evidence(self):
        row=pg_log('2026-01-01T00:00:00.123456789Z 2026-01-01 00:00:00.123 UTC [42] LOG:  temporary file: path "base/pgsql_tmp/x", size 2048')
        self.assertEqual(row['pid'],42);self.assertEqual(row['size_bytes'],2048)
        self.assertNotIn('path',row)
        self.assertIsNone(pg_log('2026-01-01T00:00:00Z ordinary non-temp log'))
    def test_pg_positive_is_attributed_to_measured_backend_and_query(self):
        self.raw([('measurement',10**9,2*10**9,'ok','x')])
        rows=[{'pid':42,'stamp_ns':1500000000,'size_bytes':2048}]
        value,detail=postgres_spill(rows,self.root,{'0':{'backend_pid':42,'spill_capture':True}},(10**9,2*10**9),0,True)
        self.assertTrue(value);self.assertEqual(detail['state'],'confirmed')
    def test_pg_global_or_warmup_files_not_attributed(self):
        self.raw([('measurement',10**9,2*10**9,'ok','x')])
        for rows in ([{'pid':99,'stamp_ns':1500000000,'size_bytes':2048}],[{'pid':42,'stamp_ns':100,'size_bytes':2048}]):
            value,_=postgres_spill(rows,self.root,{'0':{'backend_pid':42,'spill_capture':True}},(10**9,2*10**9),0,True)
            self.assertFalse(value)
    def test_pg_absence_requires_complete_valid_mechanism(self):
        self.raw([('measurement',10**9,2*10**9,'ok','x')])
        clients={'0':{'backend_pid':42,'spill_capture':True}}
        self.assertFalse(postgres_spill([],self.root,clients,(10**9,2*10**9),0,True)[0])
        self.assertIsNone(postgres_spill([],self.root,clients,(10**9,2*10**9),0,False)[0])
        clients['0']['spill_capture']=False
        self.assertIsNone(postgres_spill([],self.root,clients,(10**9,2*10**9),0,True)[0])
    def test_unparsed_engine_log_never_means_no_spill(self):
        self.raw([('measurement',10**9,2*10**9,'ok','x')])
        self.assertIsNone(postgres_spill([{'unparsed':True,'stamp_ns':1500000000}],self.root,{'0':{'backend_pid':42,'spill_capture':True}},(10**9,2*10**9),0,True)[0])
    def mongo_case(self,records):
        folder=self.root/str(time.monotonic_ns());folder.mkdir()
        db=sqlite3.connect(folder/'client-000.sqlite');db.execute('CREATE TABLE operations(phase TEXT,start_ns INTEGER,end_ns INTEGER,outcome TEXT,tag TEXT)');db.execute("INSERT INTO operations VALUES ('measurement',1,2,'ok','0:measurement:1')");db.commit();db.close()
        class Collection:
            def find(self,*args):
                if args[0].get('command.aggregate')!='orders':raise AssertionError('getMore must not overwrite aggregate spill evidence')
                return records
        profiler=MongoProfiler(None,'unit');profiler.db={'system.profile':Collection()}
        return profiler.collect(folder,(1,2))
    def test_mongo_profile_true_false_and_insufficient(self):
        for flag in (True,False):
            value,_=self.mongo_case([{'command':{'comment':{'tag':'0:measurement:1'}},'usedDisk':flag}]);self.assertIs(value,flag)
        self.assertIsNone(self.mongo_case([])[0])
        self.assertFalse(self.mongo_case([{'command':{'comment':{'tag':'0:measurement:1'}}}])[0])
        self.assertIsNone(self.mongo_case([])[0])
    def test_oom_confirmed_no_exit137_inference(self):
        self.assertTrue(classify_oom([{'action':'oom','stamp_ns':5}],1,9,False)[0])
        self.assertIsNone(classify_oom([{'action':'die','stamp_ns':5}],1,9,True)[0])
        self.assertIsNone(classify_oom([],1,9,False)[0])
        self.assertFalse(classify_oom([],1,9,True)[0])
    def test_outside_window_oom_not_assigned(self):self.assertFalse(classify_oom([{'action':'oom','stamp_ns':10}],1,9,True)[0])
    def test_monitoring_config_no_eval_or_public_url(self):
        file=self.root/'config';file.write_text('MONITORING_RETENTION=1h\n')
        with patch.dict('os.environ',{'MONITORING_ENV_FILE':str(file)},clear=True):
            with self.assertRaises(QueryBlocked):settings()
        for url in ('http://8.8.8.8:9090','http://user:pass@127.0.0.1:9090','https://127.0.0.1:9090','http://0.0.0.0:9090'):
            with self.assertRaises(QueryBlocked):local_url(url)
        self.assertEqual(duration_seconds('1w'),duration_seconds('7d'))
        file.write_text('MONITORING_PORT=$(touch_bad)\n')
        with patch.dict('os.environ',{'MONITORING_ENV_FILE':str(file)},clear=True):
            with self.assertRaises(QueryBlocked):settings()
    def test_http_error_and_empty_success(self):
        api=Prometheus('http://127.0.0.1:19090')
        with patch.object(api.opener,'open',side_effect=urllib.error.URLError('unit')):
            with self.assertRaises(QueryBlocked):api.get('/api/v1/query')
        with patch.object(api,'query',return_value={'resultType':'matrix','result':[]}) as request:
            with self.assertRaises(QueryBlocked):api.raw('unit_metric',seconds=10.0)
            self.assertEqual(request.call_args.args[0],'unit_metric[10000ms]')
    def test_nonfinite_metric_and_duplicate_timestamps(self):
        api=Prometheus('http://127.0.0.1:19090')
        for values in ([[1,'NaN'],[2,'1']],[[1,'0'],[1,'1']]):
            with patch.object(api,'query',return_value={'resultType':'matrix','result':[{'metric':{},'values':values}]}):
                with self.assertRaises(QueryBlocked):api.raw('unit_metric')
    def test_targets_down_stale_and_wrong_interval(self):
        api=Prometheus('http://127.0.0.1:19090')
        targets=[{'labels':{'job':job},'health':'up','lastError':'','lastScrape':'2026-01-01T00:00:00Z','scrapeInterval':'1s'} for job in ('cadvisor','node','prometheus')]
        now=D(epoch_ns('2026-01-01T00:00:01Z'))/10**9
        with patch.object(api,'get',return_value={'activeTargets':targets}):
            self.assertEqual(len(api.targets(now)),3)
            targets[0]['health']='down'
            with self.assertRaises(QueryBlocked):api.targets(now)
            targets[0]['health']='up';targets[0]['scrapeInterval']='5s'
            with self.assertRaises(QueryBlocked):api.targets(now)
            targets[0]['scrapeInterval']='1s'
            with self.assertRaises(QueryBlocked):api.targets(now+10)
    def test_clock_drift_invalidates_mapping(self):
        telemetry=ExperimentalTelemetry(None,{},config={'MONITORING_PROMETHEUS_URL':'http://127.0.0.1:19090','MONITORING_SPILL_CAPTURE':'false'})
        telemetry.set_window(100,200,1000)
        with patch('observability.provider.time.monotonic_ns',side_effect=[150,160]),patch('observability.provider.time.time_ns',return_value=2000000000):telemetry.sample()
        self.assertTrue(telemetry.clock_bad)
        # A vanished/unverified container must return unknown telemetry, not crash finalization.
        result=telemetry.finish(self.root,(100,200),{})
        self.assertIsNone(result['max_rss_mb']);self.assertTrue(result['integrity_error'])
    def test_runner_lifecycle_csv_evidence_and_resume(self):
        class Observer(MissingTelemetry):
            def prepare(self,directory,factory):self.directory=directory;self.called=['prepare']
            def clients_ready(self,effective):self.called.append('clients')
            def set_window(self,start,end,epoch):self.window=(start,end);self.called.append('window')
            def finish(self,directory,window,effective):
                self.called.append('finish');self.observed=window
                from benchmark.results import write_json
                write_json(directory/'telemetry-evidence.json',{'kind':'SIMULATED UNIT FIXTURE ONLY'})
                return self.unavailable('unit intentional missing data')
        s=Scenario('postgres','severe','Q1','default',1,1);cfg=configuration(s);cfg['monitoring_configuration']={'unit':'original'}
        store=Store(self.root/'experiment',cfg);d=store.begin(s);telemetry=Observer()
        result=run_repetition(s,Protocol('test',0,.05,0,timeout_ms=500),d,FakeFactory(),telemetry)
        self.assertEqual(telemetry.called,['prepare','clients','window','finish']);self.assertEqual(telemetry.window,telemetry.observed)
        store.commit(s,d,result);row=read_csv(d/'results.csv')[0]
        self.assertEqual(row['max_rss_mb'],'');self.assertEqual(row['status'],'error')
        self.assertIn('telemetry-evidence.json',json.loads((d/'commit.json').read_text())['files'])
        resumed=Store(store.path,cfg,resume=True);self.assertIn(s.id,resumed.finished)
        cfg['monitoring_configuration']['unit']='changed'
        with self.assertRaises(QueryBlocked):Store(store.path,cfg,resume=True)
    def test_cancel_restores_instrumentation(self):
        import threading
        class Observer(MissingTelemetry):
            def prepare(self,d,f):self.closed=False
            def cleanup(self):self.closed=True
        s=Scenario('postgres','severe','Q1','default',1,1);o=Observer();event=threading.Event();event.set();folder=self.root/'cancel';folder.mkdir()
        with self.assertRaises(InterruptedError):run_repetition(s,Protocol('test',0,.05,0,timeout_ms=500),folder,FakeFactory(),o,external_cancel=event)
        self.assertTrue(o.closed)
    def test_mongo_profiling_bounded_filter_and_restore(self):
        class Database:
            def __init__(self):self.status={'was':0,'filter':{'existing':'inactive'}};self.commands=[]
            def command(self,cmd):
                self.commands.append(cmd)
                if cmd['profile']==-1:return dict(self.status)
                self.status={'was':cmd['profile'],'filter':cmd['filter']};return {'ok':1}
        database=Database()
        class Client:
            def __init__(self,**kwargs):pass
            def __getitem__(self,key):return database
            def close(self):pass
        from queries.native import Connection
        profiler=MongoProfiler(Connection('unit',1,'fixture','fixture','fixture'),'unit-token')
        with patch('pymongo.MongoClient',Client):
            profiler.prepare(self.root);self.assertEqual(database.status['was'],1)
            self.assertEqual(database.status['filter'],{'command.comment.benchmark_token':'unit-token'})
            profiler.close()
        self.assertEqual(database.status,{'was':0,'filter':{'existing':'inactive'}})
        self.assertTrue((self.root/'mongo-profile-restore.json').exists())
        self.assertTrue(all('slowms' not in c and 'sampleRate' not in c for c in database.commands))
    def test_mongo_external_profiling_change_not_overwritten(self):
        profiler=MongoProfiler(None,'unit');profiler.active=True;profiler.previous={'was':0};profiler.filter={'unit':True}
        class Database:
            def command(self,cmd):
                if cmd['profile']!=-1:raise AssertionError('must not overwrite external configuration')
                return {'was':1,'filter':{'someone_else':True}}
        profiler.db=Database()
        with self.assertRaises(QueryBlocked):profiler.close()
