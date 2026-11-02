"""Opt-in real PostgreSQL pilot; never final metrics. New database/role retained."""
import json,os,secrets,subprocess,sys,tempfile,unittest,uuid
from pathlib import Path
from src.dataset.model import parse_json,json_text
from src.dataset.database import PostgresAdapter
from src.dataset.files import configuration,generate,iter_file
from src.dataset.operations import import_dataset
from queries.definitions import QuerySpec
from queries.execution import QueryExecutor
from queries.native import Connection
from queries.validation import source_reference
from benchmark.results import read_csv,file_hash


@unittest.skipUnless(os.environ.get('RUN_BENCHMARK_INTEGRATION')=='1','explicit opt-in, native drivers and real PG required')
class NativePilotTests(unittest.TestCase):
    def test_native_sessions_failures_pilot_csv_and_resume(self):
        root=Path(__file__).resolve().parents[1]
        cid=os.environ['DATA_PG_CONTAINER'];admin_db=os.environ['DATA_DATABASE_NAME']
        token=uuid.uuid4().hex
        role='phase4user_'+token;database='phase4pilot_'+token
        password=secrets.token_hex(24)
        admin=PostgresAdapter()
        # Trusted generated identifiers/password contain only a-z0-9/underscore/hex.
        admin.sql("CREATE ROLE "+role+" LOGIN PASSWORD '"+password+"';\nCREATE DATABASE "+database+" OWNER "+role+";\n")
        try:
            with tempfile.TemporaryDirectory(prefix='phase4-real-pilot-') as folder:
                work=Path(folder);source=work/'small.jsonl'
                generate(source,configuration(count=100),0)
                os.environ['DATA_DATABASE_NAME']=database
                admin=PostgresAdapter();import_dataset(admin,source,batch_size=50)
                admin.sql('GRANT SELECT ON public.orders TO '+role+';\n')
                def info(fmt):
                    return subprocess.check_output(['docker','--host=unix:///var/run/docker.sock','inspect','--format',fmt,cid],text=True).strip()
                project=info('{{index .Config.Labels "com.docker.compose.project"}}')
                networks=json.loads(info('{{json .NetworkSettings.Networks}}'))
                ip=next(v['IPAddress'] for v in networks.values() if v['IPAddress'])
                conn=Connection(ip,5432,database,role,password)
                docs=[d for _,_,d in iter_file(source)]
                for query,variant in [('Q1','default'),('Q2','work_mem_4mb'),('Q2','work_mem_64mb')]:
                    spec=QuerySpec('postgres',query,variant,2000)
                    with_session=QueryExecutor('postgres',2000).open_session(spec,conn)
                    try:
                        self.assertEqual(with_session.validate_once(source_reference(docs,query))['status'],'PASS')
                        self.assertGreater(with_session.execute(),0)
                        self.assertEqual(with_session.verify()['work_mem'],spec.options.get('work_mem','4MB'))
                        if query=='Q1':
                            old=with_session.statement;with_session.statement='SELECT invalid_phase4_column FROM public.orders'
                            with self.assertRaises(Exception):with_session.execute()
                            with_session.statement=old
                        else:
                            with_session.client.execute("SELECT set_config('statement_timeout','20',false)").fetchone()
                            with_session.statement='SELECT pg_sleep(0.1)'
                            with self.assertRaises(Exception) as caught:with_session.execute()
                            self.assertEqual(getattr(caught.exception,'sqlstate',None),'57014')
                    finally:with_session.close()
                # Real connection-refused test, no retries or state changes on any other service.
                bad=Connection('127.0.0.1',1,database,role,password)
                with self.assertRaises(Exception):QueryExecutor('postgres',100).open_session(QuerySpec('postgres','Q1','default',100),bad)
                envfile=work/'pilot.env'
                text=(root/'.env.example').read_text().replace('PROJECT_NAME=jsonbench','PROJECT_NAME='+project).replace('RESOURCE_PROFILE=baseline','RESOURCE_PROFILE=severe')
                text=text.replace('MONGO_PASSWORD=\n','MONGO_PASSWORD=unused_pg_only_fixture\n').replace('POSTGRES_USER=labadmin','POSTGRES_USER='+role).replace('POSTGRES_PASSWORD=\n','POSTGRES_PASSWORD='+password+'\n').replace('POSTGRES_DB=jsonbench','POSTGRES_DB='+database)
                envfile.write_text(text);envfile.chmod(0o600)
                env=os.environ.copy();env.update(ENV_FILE=str(envfile),BENCHMARK_PYTHON=sys.executable)
                command=[str(root/'scripts/run_benchmarks.sh'),'run','--matrix','single','--mode','pilot','--engine','postgres','--profile','severe',
                    '--query','Q1','--concurrency','1','--run-number','1','--file',str(source),'--output',str(work/'results'),'--experiment','real-small-pilot',
                    '--warmup','.05','--measurement','.25','--cooldown','.05','--timeout-ms','2000','--cache','skip','--use-existing-services','--execute-selected']
                first=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=60)
                self.assertEqual(first.returncode,1,first.stdout+first.stderr) # error is mandatory telemetry absence, not fake ok.
                experiment=work/'results/pilots/real-small-pilot'
                csvs=list(experiment.glob('*/attempt-*/results.csv'));self.assertEqual(len(csvs),1)
                row=read_csv(csvs[0])[0]
                meta=parse_json((csvs[0].parent/'result.json').read_text())
                self.assertTrue(meta['window_complete']);self.assertEqual(meta['clients_connected'],1)
                self.assertEqual(meta['evidence_kind'],'real_native_driver')
                self.assertFalse(meta['eligible_for_final_analysis']);self.assertGreater(meta['metrics']['samples'],0)
                self.assertGreater(float(row['throughput_qps']),0)
                for k in ('max_rss_mb','disk_spill'):self.assertEqual(row[k],'')
                self.assertEqual(row['status'],'error')
                sha=file_hash(csvs[0])
                resumed=subprocess.run(command+['--resume'],cwd=root,env=env,capture_output=True,text=True,timeout=60)
                self.assertEqual(resumed.returncode,1,resumed.stdout+resumed.stderr)
                self.assertEqual(len(list(experiment.glob('*/attempt-*/commit.json'))),1)
                self.assertEqual(file_hash(csvs[0]),sha)
                # Full-protocol request blocked BEFORE any multi-hour matrix or privileged cache action.
                definitive=[sys.executable,str(root/'benchmark_runner'),'run','--matrix','single','--mode','definitive','--engine','postgres','--profile','severe',
                    '--query','Q1','--concurrency','1','--run-number','1','--file',str(source),'--output',str(work/'results'),'--experiment','definitely-blocked',
                    '--cache','manual','--execute-selected']
                blocked=subprocess.run(definitive,cwd=root,env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(blocked.returncode,2)
                self.assertFalse(list((work/'results').glob('definitive/**/results.csv')))
                evidence=os.environ.get('BENCHMARK_EVIDENCE_DIR')
                if evidence:
                    dest=Path(evidence);dest.mkdir(parents=True,exist_ok=True)
                    # Only real pilot metadata/CSV; no credentials, dataset or SQLite raw journals in backup.
                    (dest/('pilot-'+token+'.csv')).write_bytes(csvs[0].read_bytes())
                    meta['purpose']='REAL PILOT ONLY: reduced durations, cache skipped, missing mandatory telemetry; NOT academic performance results'
                    meta['source_csv_sha256']=sha
                    (dest/('pilot-'+token+'.json')).write_text(json_text(meta)+'\n')
                    (dest/('blocked-'+token+'.json')).write_text(blocked.stdout)
                    (dest/('experiment-'+token+'.json')).write_bytes((experiment/'experiment.json').read_bytes())
                    (dest/('preflight-'+token+'.json')).write_bytes((csvs[0].parent/'preflight.json').read_bytes())
                print('Real native PG pilot verified; reduced window, missing telemetry, not final. Database/role retained:',database)
        finally:os.environ['DATA_DATABASE_NAME']=admin_db
