"""Opt-in real engines; new databases only, no removal of existing data."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
import uuid

from src.dataset.database import MongoAdapter, PostgresAdapter
from src.dataset.files import generate, configuration, iter_file
from src.dataset.model import DataError, json_text
from queries.definitions import QuerySpec, QueryBlocked, VARIANTS
from queries.execution import QueryExecutor
from queries.validation import source_reference, compare_results
from queries.indexes import inspect_indexes
from queries.plans import summarize_plan
from query_fixtures import controlled, boundary_ties


@unittest.skipUnless(os.environ.get('RUN_QUERY_INTEGRATION')=='1','requires explicit opt-in and real running containers')
class RealQueryTests(unittest.TestCase):
    def setUp(self):
        engine=os.environ.get('DATA_TEST_ENGINE','both')
        self.engines=['mongo','postgres'] if engine=='both' else [engine]
        self.database='phase3test_'+uuid.uuid4().hex
        self.previous_database=os.environ['DATA_DATABASE_NAME']
        if 'postgres' in self.engines:
            PostgresAdapter().sql('CREATE DATABASE '+self.database+';\n')
        os.environ['DATA_DATABASE_NAME']=self.database
        self.executors={e:QueryExecutor(e) for e in self.engines}
        self.temp=tempfile.TemporaryDirectory(prefix='phase3-query-tests-')
        print('Real correctness database retained:',self.database)

    def tearDown(self):
        os.environ['DATA_DATABASE_NAME']=self.previous_database
        self.temp.cleanup()

    def load(self,docs):
        for executor in self.executors.values():
            adapter=executor.adapter
            adapter.ensure()
            self.assertEqual(adapter.count(),0)
            for i in range(0,len(docs),250): adapter.insert(docs[i:i+250])
            self.assertEqual(adapter.count(),len(docs))

    def evidence(self,label,value):
        folder=os.environ.get('QUERY_EVIDENCE_DIR')
        if folder:
            path=Path(folder)
            path.mkdir(parents=True,exist_ok=True)
            with (path/(self.database+'_'+label+'.json')).open('x') as stream:
                stream.write(json_text({**value, 'evidence_written_at_utc':datetime.now(timezone.utc).isoformat(), 'timestamp_source':'artifact write time, not benchmark timestamp'})+'\n')

    def check_queries(self,docs,plans=False):
        for query in ('Q1','Q2'):
            reference=source_reference(docs,query)
            results={}
            checks=[]
            for engine,executor in self.executors.items():
                results[engine]=[]
                for variant in VARIANTS[engine][query]:
                    spec=QuerySpec(engine,query,variant)
                    answer=executor.execute(spec)
                    check=compare_results(reference,{engine:answer['rows']})
                    self.assertEqual(check['checks'][engine]['status'],'PASS',check)
                    checks.append({'query':query,'engine':engine,'variant':variant,'check':check,
                                   'effective':answer['effective'],'preflight':answer['preflight']})
                    results[engine].append(answer['rows'])
                    if plans:
                        plan=executor.execute(spec,explain=True)
                        summary=summarize_plan(plan['plan'],engine)
                        self.assertTrue(summary['nodes'])
                        self.evidence(query+'_'+variant+'_plan',{'source':'real explain, correctness only',**plan,'summary':summary})
            if len(results)==2:
                for mongo in results['mongo']:
                    for pg in results['postgres']:
                        cross=compare_results(reference,{'mongo':mongo,'postgres':pg})
                        self.assertEqual(cross['status'],'PASS',cross)
            else:
                cross=compare_results(reference,{self.engines[0]:results[self.engines[0]][0]})
                self.assertEqual(cross['status'],'BLOCKED')
            if plans: self.evidence(query+'_validation',{'cross_engine_status':'compared' if len(results)==2 else 'BLOCKED','checks':checks})

    def test_controlled_expected_results_variants_and_plans(self):
        docs=controlled();self.load(docs)
        self.check_queries(docs,plans=True)
        if 'postgres' in self.executors:
            executor=self.executors['postgres']
            baseline=executor.adapter.sql('SHOW work_mem;\n')
            for v,value in [('work_mem_4mb','4MB'),('work_mem_64mb','64MB')]:
                result=executor.execute(QuerySpec('postgres','Q2',v))
                self.assertEqual(result['effective']['work_mem'],value)
                self.assertEqual(executor.adapter.sql('SHOW work_mem;\n'),baseline)

    def test_empty_group_and_empty_topk(self):
        docs=controlled()[4:6]
        for doc in docs: doc['payment']['status']='pending'
        self.load(docs)
        self.check_queries(docs)

    def test_generated_ten(self):
        path=Path(self.temp.name)/'10.jsonl';generate(path,configuration(count=10),0)
        docs=[d for _,_,d in iter_file(path)];self.load(docs);self.check_queries(docs)
        if 'postgres' in self.engines:
            root=Path(__file__).resolve().parents[1]
            proc=subprocess.run([sys.executable,str(root/'query_tool.py'),'validate','--engine','postgres','--query','Q1','--file',str(path)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,2,proc.stdout+proc.stderr)
            self.assertIn('"oracle":{"average_precision_notes"',proc.stdout)
            self.assertIn('"status":"PASS"',proc.stdout)
            self.assertIn('"status":"BLOCKED"',proc.stdout)

    def test_generated_hundred(self):
        path=Path(self.temp.name)/'100.jsonl';generate(path,configuration(count=100),0)
        docs=[d for _,_,d in iter_file(path)];self.load(docs);self.check_queries(docs)

    def test_generated_thousand(self):
        path=Path(self.temp.name)/'1000.jsonl';generate(path,configuration(count=1000),0)
        docs=[d for _,_,d in iter_file(path)];self.load(docs);self.check_queries(docs)

    def test_top1000_boundary_ties(self):
        docs=boundary_ties();self.load(docs)
        ref=source_reference(docs,'Q2')
        self.assertTrue(ref['boundary_tie'])
        for engine,executor in self.executors.items():
            for variant in VARIANTS[engine]['Q2']:
                answer=executor.execute(QuerySpec(engine,'Q2',variant))
                check=compare_results(ref,{engine:answer['rows']})
                self.assertEqual(check['checks'][engine]['status'],'PASS',check)
                self.assertEqual(len(answer['rows']),1000)
                self.evidence(engine+'_'+variant+'_boundary_tie',check)

    def test_totals_only_blocks_original_q2(self):
        docs=controlled()
        for d in docs: del d['payment']['final_total']
        self.load(docs)
        for engine,executor in self.executors.items():
            executor.execute(QuerySpec(engine,'Q1','default'))
            for variant in VARIANTS[engine]['Q2']:
                with self.assertRaises(QueryBlocked): executor.execute(QuerySpec(engine,'Q2',variant))

    def test_invalid_calendar_blocks_before_workload(self):
        docs=controlled();docs[0]['timestamp']='2026-02-30T00:00:00Z'
        self.load(docs)
        for engine,executor in self.executors.items():
            with self.assertRaises(QueryBlocked): executor.execute(QuerySpec(engine,'Q1','default'))

    def test_indexes_inspect_safe_prepare_and_original_cast_incompatible(self):
        self.load(controlled())
        for engine,executor in self.executors.items():
            before=inspect_indexes(executor)
            if engine=='mongo':
                after=inspect_indexes(executor,apply=True)
                self.assertEqual(after['status'],'PASS')
                self.assertEqual(inspect_indexes(executor,apply=True)['status'],'PASS')
            else:
                self.assertTrue(before['primary_key_ok'])
                self.assertEqual(before['timestamptz_input_volatility'],'s')
                # Prove the original cast expression cannot be indexed as is.
                with self.assertRaises(DataError):
                    executor.adapter.sql("CREATE INDEX original_cast_probe ON public.orders (((data->>'timestamp')::timestamptz));\n")
                blocked=inspect_indexes(executor,apply=True)
                self.assertEqual(blocked['status'],'BLOCKED')
                self.assertFalse(blocked['timestamp_text_index_present'])
                # Explicit acceptance in this isolated test, not academic approval.
                after=inspect_indexes(executor,apply=True,accept_text_proposal=True)
                self.assertEqual(after['physical_index_status'],'PASS')
                self.assertEqual(after['status'],'BLOCKED')
                repeated=inspect_indexes(executor,apply=True,accept_text_proposal=True)
                self.assertEqual(len(after['indexes']),len(repeated['indexes']))
                plan=executor.execute(QuerySpec(engine,'Q2','work_mem_4mb'),explain=True)
                self.evidence('after_text_proposal_plan',{'source':'real original Q2, text index proposal only',**plan,'summary':summarize_plan(plan['plan'],engine)})
            self.evidence(engine+'_indexes',after)


if __name__=='__main__': unittest.main()
