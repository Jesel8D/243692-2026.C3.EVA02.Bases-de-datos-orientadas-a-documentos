"""Reporting software tests. Synthetic artifacts are temporary, labelled and CLI-forbidden."""
import unittest,tempfile,math,hashlib,json,subprocess,sys,os,threading
from pathlib import Path
from decimal import Decimal as D
from unittest.mock import patch
from dataclasses import asdict
from reporting.loader import load,Snapshot
from reporting.progress import expected_plan,progress
from reporting.statistics import summarize,difference,groups,comparisons
from reporting.generator import readiness,generate,model
from reporting.plans import load_plans
from reporting.charts import segments,create_charts
from reporting.exporters import html,markdown
from benchmark.matrix import matrix,Scenario
from benchmark.results import read_csv,file_hash,write_json
from queries.definitions import QueryBlocked
from reporting_fixtures import make_store,emit,plans

class ReportingTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-report-tests-');self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def one(self,scope='definitive',series=True):
        s=Scenario('postgres','severe','Q2','work_mem_4mb',1,1);store=make_store(self.root,[s],scope);d=emit(store,s,series=series)
        return store,s,d
    def snapshot(self,store,scope='definitive',all=False):return load([store.path],scope,all,_testing=True)
    def test_official_csv_and_variant_sidecar(self):
        store,s,d=self.one();snap=self.snapshot(store)
        self.assertEqual(len(read_csv(d/'results.csv')),1);self.assertEqual(snap.records[0].scenario.variant,'work_mem_4mb')
        self.assertTrue(snap.test_only);self.assertTrue(snap.records[0].valid,snap.records[0].reasons)
    def test_public_loader_rejects_synthetic_fixtures(self):
        store,_,_=self.one()
        with self.assertRaises(QueryBlocked):load([store.path])
    def test_scope_separates_pilot_and_definitive(self):
        store,_,_=self.one('pilot')
        with self.assertRaises(QueryBlocked):self.snapshot(store)
        self.assertTrue(self.snapshot(store,'pilot').records[0].valid)
    def test_bad_header_is_quarantined_not_repaired(self):
        store,s,d=self.one();(d/'results.csv').write_text('bad,header\n')
        snap=self.snapshot(store);self.assertEqual(len(snap.invalid),1);self.assertFalse(snap.records)
        self.assertEqual((d/'results.csv').read_text(),'bad,header\n')
    def test_missing_committed_file_quarantines(self):
        store,s,d=self.one();(d/'result.json').rename(d/'result.json.removed-by-test')
        self.assertEqual(len(self.snapshot(store).invalid),1)
    def test_uncommitted_partial_csv_is_pending(self):
        s=Scenario('postgres','severe','Q1','default',1,1);store=make_store(self.root,[s]);d=store.begin(s);(d/'results.csv').write_text('partial')
        snap=self.snapshot(store);p=progress(snap,expected_plan(snap))
        self.assertEqual(next(iter(p['cohorts'].values()))['pending'],1)
        self.assertFalse(snap.records);self.assertTrue(snap.unfinished)
    def test_new_commit_is_seen_without_runner_lock(self):
        from benchmark.results import experiment_lock
        s=Scenario('postgres','severe','Q1','default',1,1);store=make_store(self.root,[s])
        with experiment_lock(store.path):
            first=self.snapshot(store);self.assertFalse(first.records)
            emit(store,s);second=self.snapshot(store);self.assertEqual(len(second.records),1)
    def test_resolved_incomplete_attempt_not_counted_twice(self):
        s=Scenario('postgres','severe','Q1','default',1,1);store=make_store(self.root,[s]);d=store.begin(s);(d/'results.csv').write_text('partial')
        emit(store,s);snap=self.snapshot(store)
        self.assertEqual(len(snap.records),1);self.assertFalse(snap.unfinished)
    def test_duplicate_experiment_and_duplicate_repetition_rejected(self):
        store,s,d=self.one()
        with self.assertRaises(QueryBlocked):load([store.path,store.path],_testing=True)
        another=make_store(self.root,[s],suffix='duplicate');emit(another,s)
        with self.assertRaises(QueryBlocked):load([store.path,another.path],_testing=True)
    def test_cohorts_separate_changed_dataset(self):
        store,s,d=self.one();other=make_store(self.root,[s],suffix='different')
        # New manifest created independently to represent another dataset; no changes to real artifacts.
        obj=json.loads((other.path/'experiment.json').read_text());obj['configuration']['dataset']['sha256']='e'*64
        (other.path/'experiment.json').write_text(json.dumps(obj));other.configuration['dataset']['sha256']='e'*64
        emit(other,s);snap=load([store.path,other.path],_testing=True)
        self.assertEqual(len({e['cohort'] for e in snap.experiments}),2)
        from reporting.loader import cohort_key
        import copy
        cfg=copy.deepcopy(store.configuration);base_key=cohort_key(cfg);cfg['selection']['matrix']='extended'
        self.assertNotEqual(base_key,cohort_key(cfg))
    def test_decimal_statistics_and_percentage_zero(self):
        stat=summarize([D('1.1'),D('2.2'),D('3.3')])
        self.assertEqual(stat,{'n':3,'mean':D('2.2'),'median':D('2.2'),'min':D('1.1'),'max':D('3.3')})
        self.assertIsNone(summarize([])['mean']);self.assertEqual(difference(D(10),D(12))['percent'],20)
        self.assertIsNone(difference(D(0),D(12))['percent'])
    def test_matrix_108_162_and_13h_budget(self):
        a=expected_plan(Snapshot('definitive'),'base',{'mongo':'allow_disk_false','postgres':'work_mem_4mb'})
        b=expected_plan(Snapshot('definitive'),'extended')
        self.assertEqual((a['cells'],len(a['scenarios'])),(36,108));self.assertEqual((b['cells'],len(b['scenarios'])),(54,162))
        p=progress(Snapshot('definitive'),a);c=next(iter(p['cohorts'].values()))
        self.assertEqual(c['eta_seconds_approx'],45360);self.assertEqual(c['pending'],108)
        self.assertGreater(p['nominal_extended_seconds'],p['time_budget_seconds'])
    def test_partial_repetitions_have_descriptive_stats_not_comparison(self):
        plan=[Scenario(e,'severe','Q1','default',1,r) for e in ('mongo','postgres') for r in (1,2,3)]
        store=make_store(self.root,plan);emit(store,plan[0]);emit(store,plan[3]);snap=self.snapshot(store)
        g=groups(snap,expected_plan(snap));self.assertEqual(g[0]['n_valid'],1)
        self.assertEqual(comparisons(g)[0]['status'],'NOT_COMPARABLE')
    def test_q2_pairs_explicit_and_complete_triplicate(self):
        plan=[Scenario(e,'severe','Q2',v,1,r) for e,v in [('mongo','allow_disk_false'),('postgres','work_mem_4mb')] for r in (1,2,3)]
        store=make_store(self.root,plan)
        for s in plan:emit(store,s)
        snap=self.snapshot(store);g=groups(snap,expected_plan(snap))
        self.assertEqual(comparisons(g)[0]['status'],'NOT_COMPARABLE')
        self.assertEqual(comparisons(g,['allow_disk_false:work_mem_4mb'])[0]['status'],'COMPARABLE')
        with self.assertRaises(QueryBlocked):comparisons(g,['allow_disk_false:bad'])
    def test_failed_and_missing_values_excluded_from_means(self):
        plan=[Scenario('postgres','severe','Q1','default',1,r) for r in (1,2,3)];store=make_store(self.root,plan)
        emit(store,plan[0]);emit(store,plan[1],bad=True)
        snap=self.snapshot(store);g=groups(snap,expected_plan(snap))[0]
        self.assertEqual(g['statistics']['throughput_qps']['mean'],1)
        c=next(iter(progress(snap,expected_plan(snap))['cohorts'].values()))
        self.assertEqual((c['completed'],c['valid'],c['failed'],c['pending']),(2,1,1,1))
    def test_final_incomplete_blocks_or_explicit_partial(self):
        store,s,d=self.one();snap=self.snapshot(store,all=True);plan=expected_plan(snap)
        with self.assertRaises(QueryBlocked):generate(snap,plan,self.root/'reports',mode='final')
        with patch('reporting.generator.create_charts',return_value=([],['SYNTHETIC test: charts omitted'])):
            out=generate(snap,plan,self.root/'reports',mode='final',allow_partial=True)
        self.assertIn('TEST_PARTIAL',(out/'reporte.md').read_text());self.assertIn('SIMULADO',(out/'reporte.html').read_text())
    def test_complete_final_gate_requires_all_108_and_linked_plans(self):
        plan=matrix('base',base_variants={'mongo':'allow_disk_false','postgres':'work_mem_4mb'});store=make_store(self.root,plan)
        for s in plan:emit(store,s)
        snap=self.snapshot(store,all=True);expected=expected_plan(snap);g=groups(snap,expected)
        diagnostics=load_plans(plans(self.root),snap)
        ready=readiness(snap,expected,g,diagnostics)
        self.assertTrue(ready['ready'],ready['reasons'])
        with patch('reporting.generator.create_charts',return_value=([],['SYNTHETIC unit render only'])):
            out=generate(snap,expected,self.root/'reports',mode='final',plans=diagnostics)
        self.assertEqual(json.loads((out/'analysis-manifest.json').read_text())['state'],'TEST_FINAL')
        self.assertIn('SIMULADO',(out/'reporte.html').read_text())
        for d in diagnostics:d['dataset_sha256']=None
        self.assertFalse(readiness(snap,expected,g,diagnostics)['ready'])
    def test_rss_is_not_fabricated_from_maximum(self):
        store,s,d=self.one(series=False);snap=self.snapshot(store);self.assertTrue(snap.records[0].valid);self.assertEqual(snap.records[0].rss,[])
        self.assertFalse(readiness(snap,expected_plan(snap),groups(snap,expected_plan(snap)),[])['ready'])
    def test_rss_gap_inserts_nan_and_no_missing_client_line(self):
        out=segments([(0,1),(1,2),(5,3)])
        self.assertTrue(math.isnan(out[2][0]));self.assertEqual(out[-1],(5.0,3.0))
    def test_charts_are_png_and_source_hashes_unchanged(self):
        store,s,d=self.one();before=file_hash(d/'results.csv');snap=self.snapshot(store);plan=expected_plan(snap)
        images,missing=create_charts(groups(snap,plan),self.root/'figures','definitive',True)
        self.assertEqual(len(images),3)
        for p in (self.root/'figures').glob('*.png'):self.assertEqual(p.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
        self.assertEqual(before,file_hash(d/'results.csv'))
    def test_seven_sections_escaping_and_missing_personal_data(self):
        snap=Snapshot('definitive');plan=expected_plan(snap,'base',{'mongo':'allow_disk_false','postgres':'work_mem_4mb'});g=groups(snap,plan)
        doc=model(snap,plan,g,[],[],[],['Sin evidencia'],'PARTIAL',readiness(snap,plan,g,[]),{'student':'<script>alert(1)</script>'})
        self.assertEqual(len(doc['sections']),7)
        rendered=html(doc);self.assertNotIn('<script>',rendered);self.assertIn('&lt;script&gt;',rendered)
        self.assertEqual(len([l for l in markdown(doc).splitlines() if l.startswith('## ') and l[3:4].isdigit()]),7)
        self.assertIn('[Por completar]',rendered)
    def test_snapshot_source_bytes_and_previous_reports_preserved(self):
        store,s,d=self.one();snap=self.snapshot(store);plan=expected_plan(snap)
        with patch('reporting.generator.create_charts',return_value=([],[])):
            first=generate(snap,plan,self.root/'reports');second=generate(snap,plan,self.root/'reports')
        self.assertNotEqual(first,second);self.assertTrue((first/'analysis-manifest.json').exists())
        for item in json.loads((second/'snapshot/index.json').read_text()):self.assertEqual(file_hash(second/item['snapshot_file']),item['sha256'])
    def test_standalone_csv_schema_cli_does_not_certify_results(self):
        store,s,d=self.one()
        result=subprocess.run([sys.executable,'-m','reporting','validate','--csv',str(d/'results.csv')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0);self.assertEqual(json.loads(result.stdout)['status'],'SCHEMA_ONLY')
    def test_raw_journal_corruption_detected_by_full_audit(self):
        store,s,d=self.one();commit=json.loads((d/'commit.json').read_text())
        (d/'raw.sqlite').write_bytes(b'SYNTHETIC UNIT JOURNAL');commit['files']['raw.sqlite']=file_hash(d/'raw.sqlite');(d/'commit.json').write_text(json.dumps(commit))
        (d/'raw.sqlite').write_bytes(b'corrupt fixture')
        self.assertEqual(len(self.snapshot(store,all=True).invalid),1)
    def test_output_cannot_be_inside_experiment(self):
        store,s,d=self.one();snap=self.snapshot(store)
        with self.assertRaises(QueryBlocked):generate(snap,expected_plan(snap),store.path/'reports')
    def test_plans_are_diagnostic_and_never_execute_db(self):
        snap=Snapshot('definitive',test_only=True);loaded=load_plans(plans(self.root),snap)
        self.assertEqual(len(loaded),4);self.assertTrue(all('not evidence of spill' in p['note'] for p in loaded))
    def test_public_cli_cannot_publish_fixture_report(self):
        store,s,d=self.one()
        proc=subprocess.run([sys.executable,'-m','reporting','generate','--inputs',str(store.path),'--output',str(self.root/'blocked')],capture_output=True,text=True)
        self.assertEqual(proc.returncode,2);self.assertFalse((self.root/'blocked').exists())
    def test_effective_variant_and_qps_are_independently_checked(self):
        store,s,d=self.one();snap=self.snapshot(store);r=snap.records[0]
        from reporting.validation import validate_record
        started=json.loads((d/'started.json').read_text())
        r.meta['clients_effective']['0']['work_mem']='64MB'
        validate_record(r,started,store.configuration,'definitive',True)
        self.assertFalse(r.valid);self.assertTrue(any('work_mem' in x for x in r.reasons))
        r.meta['clients_effective']['0']['work_mem']='4MB';r.meta['metrics']['samples']=301
        validate_record(r,started,store.configuration,'definitive',True)
        self.assertFalse(r.valid);self.assertTrue(any('QPS inconsistent' in x for x in r.reasons))
    def test_extended_approval_is_not_inferred(self):
        plan=expected_plan(Snapshot('definitive',integrity='all'),'extended')
        ready=readiness(Snapshot('definitive',integrity='all'),plan,groups(Snapshot('definitive'),plan),[])
        self.assertFalse(ready['ready']);self.assertTrue(any('P-02' in x for x in ready['reasons']))
    def test_progress_watch_reads_real_pilot_without_writes(self):
        source=Path(__file__).resolve().parents[1]/'docs/evidence/phase5/real-pilot-09a82cb8b52d47a9a4ae60e5268d7ff6'
        if not source.exists():self.skipTest('archived real pilot not present')
        before={str(p):file_hash(p) for p in source.rglob('*') if p.is_file()}
        proc=subprocess.run([sys.executable,'-m','reporting','progress','--scope','pilot','--inputs',str(source),'--watch','--iterations','2','--interval','1','--json'],capture_output=True,text=True,timeout=15)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        frames=[json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(len(frames),2);self.assertEqual(next(iter(frames[-1]['cohorts'].values()))['completed'],1)
        self.assertEqual(before,{str(p):file_hash(p) for p in source.rglob('*') if p.is_file()})
    def test_relative_paths_work_outside_repository(self):
        source=Path(__file__).resolve().parents[1]/'scripts/generate_report.sh'
        proc=subprocess.run([str(source),'--matrix','extended'],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(proc.returncode,2) # Must use the explicit action interface; no matrix execution.
        proc=subprocess.run([str(source),'progress','--matrix','extended'],cwd=self.root,capture_output=True,text=True)
        # CLI supports progress; expected count 162, no files in this working directory.
        self.assertEqual(proc.returncode,0,proc.stdout)
