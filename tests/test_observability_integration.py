"""Opt-in real monitoring + PG pilot; no complete academic matrix or induced spill/OOM."""
import json,os,secrets,shutil,subprocess,sys,tempfile,unittest,uuid
from pathlib import Path
from benchmark.results import read_csv,file_hash
from observability.identity import inspect_container
from observability.provider import ExperimentalTelemetry
from observability.config import settings
from benchmark.config import Protocol
from src.dataset.database import PostgresAdapter
from src.dataset.files import generate,configuration

@unittest.skipUnless(os.environ.get('RUN_MONITORING_INTEGRATION')=='1','requires explicit opt-in, real exporters/Prometheus and PostgreSQL')
class RealMonitoringTests(unittest.TestCase):
    def test_real_scraping_native_pilot_and_resume(self):
        self.assertEqual(settings()['MONITORING_SPILL_CAPTURE'],'true','instrumentation must be explicitly enabled for this test')
        root=Path(__file__).resolve().parents[1];cid=os.environ['DATA_PG_CONTAINER'];before_database=os.environ['DATA_DATABASE_NAME']
        identity=inspect_container(cid)
        probe=ExperimentalTelemetry(None,{'snapshot':{'id':cid,'label':identity['profile'],'image_id':identity['image_id']},'protocol':Protocol('pilot')}).probe()
        self.assertEqual(probe['status'],'PASS',probe.get('errors'))
        token=uuid.uuid4().hex;database='phase5pilot_'+token;role='phase5user_'+token;password=secrets.token_hex(24)
        adapter=PostgresAdapter()
        adapter.sql("CREATE ROLE "+role+" LOGIN PASSWORD '"+password+"';\nCREATE DATABASE "+database+" OWNER "+role+";\nGRANT SET ON PARAMETER log_temp_files TO "+role+";\n")
        try:
            with tempfile.TemporaryDirectory(prefix='phase5-real-pilot-') as folder:
                work=Path(folder);source=work/'orders.jsonl';generate(source,configuration(count=100),0)
                os.environ['DATA_DATABASE_NAME']=database;adapter=PostgresAdapter()
                from src.dataset.operations import import_dataset
                import_dataset(adapter,source,batch_size=50);adapter.sql('GRANT SELECT ON public.orders TO '+role+';\n')
                envfile=work/'db.env'
                text=(root/'.env.example').read_text().replace('PROJECT_NAME=jsonbench','PROJECT_NAME='+identity['project']).replace('RESOURCE_PROFILE=baseline','RESOURCE_PROFILE=severe')
                text=text.replace('MONGO_PASSWORD=\n','MONGO_PASSWORD=unused_pg_fixture\n').replace('POSTGRES_USER=labadmin','POSTGRES_USER='+role).replace('POSTGRES_PASSWORD=\n','POSTGRES_PASSWORD='+password+'\n').replace('POSTGRES_DB=jsonbench','POSTGRES_DB='+database)
                envfile.write_text(text);envfile.chmod(0o600)
                env=os.environ.copy();env.update(ENV_FILE=str(envfile),BENCHMARK_PYTHON=sys.executable)
                command=[str(root/'scripts/run_benchmarks.sh'),'run','--matrix','single','--mode','pilot','--engine','postgres','--profile','severe','--query','Q2','--variant','work_mem_4mb','--concurrency','1','--run-number','1','--file',str(source),'--output',str(work/'results'),'--experiment','real-monitoring','--warmup','1','--measurement','4','--cooldown','1','--timeout-ms','3000','--cache','skip','--use-existing-services','--execute-selected']
                first=subprocess.run(command,env=env,cwd=root,capture_output=True,text=True,timeout=90)
                experiment=work/'results/pilots/real-monitoring'
                rows=list(experiment.glob('*/attempt-*/results.csv'))
                self.assertEqual(len(rows),1,first.stdout+first.stderr)
                meta=json.loads((rows[0].parent/'result.json').read_text());row=read_csv(rows[0])[0]
                evidence=json.loads((rows[0].parent/'telemetry-evidence.json').read_text())
                # Preserve actual evidence even when assertions reveal a collection incompatibility.
                if os.environ.get('MONITORING_EVIDENCE_DIR'):
                    dest=Path(os.environ['MONITORING_EVIDENCE_DIR'])/('real-pilot-'+token)
                    shutil.copytree(experiment,dest,ignore=shutil.ignore_patterns('.lock'))
                    (dest/'purpose.txt').write_text('REAL CLOUD FUNCTIONAL PILOT ONLY. 100 orders, 1/4/1 seconds, skipped cache. Not final academic measurements.\n')
                    (dest/'test-invocation.txt').write_text('First return code: '+str(first.returncode)+'\n'+first.stdout+'\n')
                    self.assertNotIn(password,''.join(p.read_text(errors='ignore') for p in dest.rglob('*.json')))
                self.assertEqual(first.returncode,0,first.stdout+first.stderr+str(evidence.get('errors')))
                self.assertEqual(row['status'],'ok');self.assertFalse(meta['eligible_for_final_analysis'])
                self.assertGreater(meta['metrics']['samples'],0)
                self.assertNotEqual(row['cpu_throttled_seconds'],'');self.assertGreaterEqual(float(row['cpu_throttled_seconds']),0)
                self.assertGreater(float(row['max_rss_mb']),0)
                self.assertEqual(row['disk_spill'],'0');self.assertIs(meta['telemetry']['oom_killed'],False)
                self.assertEqual(evidence['spill']['state'],'not_detected')
                self.assertEqual(evidence['probe']['identity']['id'],cid)
                self.assertEqual(meta['clients_effective']['0']['work_mem'],'4MB')
                self.assertTrue(meta['clients_effective']['0']['spill_capture'])
                sha=file_hash(rows[0]);resumed=subprocess.run(command+['--resume'],env=env,cwd=root,capture_output=True,text=True,timeout=90)
                self.assertEqual(resumed.returncode,0,resumed.stdout+resumed.stderr)
                self.assertEqual(len(list(experiment.glob('*/attempt-*/commit.json'))),1);self.assertEqual(file_hash(rows[0]),sha)
                if os.environ.get('MONITORING_EVIDENCE_DIR'):
                    for p in experiment.glob('invocation-*.json'):
                        target=dest/p.name
                        if not target.exists():shutil.copy2(p,target)
                print('PASS real monitoring pilot and resume; new database/role retained:',database,role)
        finally:os.environ['DATA_DATABASE_NAME']=before_database
