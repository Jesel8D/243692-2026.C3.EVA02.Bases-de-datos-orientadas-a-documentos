"""Unit tests for original definitions, exact oracles, ties, sessions and indexes."""
from copy import deepcopy
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from queries.definitions import ROOT, QuerySpec, QueryBlocked, VARIANTS
from queries.execution import QueryExecutor
from queries.validation import source_reference, validate_q1, validate_q2, compare_results
from queries.indexes import audit_mongo, audit_postgres
from queries.plans import summarize_plan
from query_fixtures import controlled, boundary_ties


def q1_rows(ref, engine):
    # Synthetic unit-validator input, never claimed as real database output.
    rows=[]
    for (country,category),(cents,count) in ref['groups'].items():
        exact=Fraction(cents,100*count)
        with localcontext() as ctx:
            ctx.prec=34 if engine=='mongo' else 80
            ctx.rounding=ROUND_HALF_EVEN
            average=Decimal(exact.numerator)/Decimal(exact.denominator)
            if engine=='postgres': average=average.quantize(Decimal('0.0000000000000001'))
        row={'total_revenue':Decimal(cents).scaleb(-2),'avg_revenue':average,'count':count}
        row.update({'_id':{'country':country,'category':category}} if engine=='mongo' else {'country':country,'category':category})
        rows.append(row)
    return rows


def q2_rows(ref, engine, reverse_ties=False):
    rows=sorted(ref['eligible'].values(),key=lambda r:(-r['final_total'],r['order_id'] if not reverse_ties else ''.join(chr(255-ord(c)) for c in r['order_id'])))[:ref['k']]
    if engine=='postgres': return deepcopy(rows)
    return [{'order_id':r['order_id'],'customer':{'id':r['customer_id']},'payment':{'final_total':r['final_total']},'_id':r['order_id']} for r in rows]


class QueryTests(unittest.TestCase):
    def test_original_pipeline_shapes_and_options(self):
        q=QuerySpec('mongo','Q1','default')
        self.assertEqual([next(iter(s)) for s in q.pipeline],['$unwind','$match','$group'])
        self.assertEqual(q.pipeline[1]['$match']['items.price'],{'$gt':50})
        self.assertEqual(q.pipeline[2]['$group']['total_revenue'],{'$sum':{'$multiply':['$items.qty','$items.price']}})
        q=QuerySpec('mongo','Q2','allow_disk_false')
        self.assertEqual([next(iter(s)) for s in q.pipeline],['$match','$sort','$limit','$project'])
        self.assertEqual(q.pipeline[0]['$match']['timestamp']['$gte'],'2026-01-01T00:00:00Z')
        self.assertEqual(q.pipeline[1],{'$sort':{'payment.final_total':-1}})
        self.assertEqual(q.pipeline[2],{'$limit':1000})
        self.assertNotIn('allowDiskUse',str(q.pipeline))
        self.assertIs(q.options['allowDiskUse'],False)
        self.assertIs(QuerySpec('mongo','Q2','allow_disk_true').options['allowDiskUse'],True)

    def test_sql_structure_and_no_secondary_sort(self):
        q1=QuerySpec('postgres','Q1','default').sql
        for token in ('jsonb_array_elements', '::numeric > 50','SUM(', 'AVG(', 'COUNT(*)','GROUP BY 1, 2'):
            self.assertIn(token,q1)
        q2=QuerySpec('postgres','Q2','work_mem_4mb').sql
        self.assertIn("::timestamptz >= '2026-01-01 00:00:00Z'",q2)
        self.assertEqual(q2.split('ORDER BY')[1].strip(),"(data->'payment'->>'final_total')::numeric DESC\nLIMIT 1000")
        self.assertEqual(QuerySpec('postgres','Q2','work_mem_64mb').options,{'work_mem':'64MB'})

    def test_invalid_specs(self):
        for args in [('mongo','Q2','default'),('postgres','Q2','allow_disk_true'),('unknown','Q1','default'),('mongo','Q1','default',0)]:
            with self.assertRaises(QueryBlocked): QuerySpec(*args)

    def test_q1_hand_computed_groups_counts_and_filter(self):
        ref=source_reference(controlled(),'Q1')
        self.assertEqual(ref['groups'],{('MX','electronics'):(20006,3),('MX','books'):(18030,1),('US','electronics'):(32100,1)})
        for engine in ('mongo','postgres'):
            rows=q1_rows(ref,engine)[::-1]
            self.assertEqual(validate_q1(ref,rows,engine)['status'],'PASS')

    def test_invalid_oracle_and_failure_are_json_serializable(self):
        from src.dataset.model import json_text
        with self.assertRaises(QueryBlocked): source_reference([], 'unknown')
        ref=source_reference(controlled(),'Q1')
        result=validate_q1(ref,[],'postgres')
        self.assertIn('"status":"FAIL"',json_text(result))

    def test_empty_groups(self):
        docs=controlled()[4:6] # price == 50, excluded
        ref=source_reference(docs,'Q1')
        self.assertEqual(ref['groups'],{})
        self.assertEqual(validate_q1(ref,[],'postgres')['status'],'PASS')
        self.assertEqual(source_reference([],'Q2')['k'],0)
        self.assertEqual(validate_q2(source_reference([],'Q2'),[],'mongo')['status'],'PASS')

    def test_average_policy_allows_only_engine_quantization(self):
        ref=source_reference(controlled(),'Q1')
        left=q1_rows(ref,'mongo');right=q1_rows(ref,'postgres')
        report=compare_results(ref,{'mongo':left,'postgres':right})
        self.assertEqual(report['status'],'PASS')
        self.assertTrue(report['checks']['postgres']['average_precision_notes'])
        right[0]['avg_revenue']=Decimal('66.687')
        self.assertEqual(validate_q1(ref,right,'postgres')['status'],'FAIL')

    def test_q1_detects_total_count_keys_float_and_strings(self):
        ref=source_reference(controlled(),'Q1');base=q1_rows(ref,'postgres')
        for field,value in [('count',4),('total_revenue',Decimal('200.07')),('total_revenue','200.06'),('avg_revenue',66.68666666666667)]:
            rows=deepcopy(base);rows[0][field]=value
            self.assertEqual(validate_q1(ref,rows,'postgres')['status'],'FAIL')
        self.assertEqual(validate_q1(ref,base[:-1],'postgres')['status'],'FAIL')
        self.assertEqual(validate_q1(ref,base+[base[0]],'postgres')['status'],'FAIL')

    def test_dates_states_and_topk_small(self):
        docs=controlled();ref=source_reference(docs,'Q2')
        self.assertEqual(ref['k'],5)
        self.assertNotIn(docs[0]['order_id'],ref['eligible'])
        self.assertIn(docs[1]['order_id'],ref['eligible'])
        self.assertIn(docs[3]['order_id'],ref['eligible'])
        self.assertNotIn(docs[2]['order_id'],ref['eligible'])
        self.assertNotIn(docs[6]['order_id'],ref['eligible'])
        self.assertNotIn(docs[7]['order_id'],ref['eligible'])
        for e in ('mongo','postgres'):
            self.assertEqual(validate_q2(ref,q2_rows(ref,e),e)['status'],'PASS')

    def test_top1000_legitimate_different_boundary_subsets(self):
        ref=source_reference(boundary_ties(),'Q2')
        self.assertEqual(ref['k'],1000)
        self.assertTrue(ref['boundary_tie'])
        self.assertEqual(len(ref['mandatory']),2)
        self.assertEqual(len(ref['ties']),1002)
        report=compare_results(ref,{'mongo':q2_rows(ref,'mongo'),'postgres':q2_rows(ref,'postgres',True)})
        self.assertEqual(report['status'],'PASS')
        self.assertGreater(report['different_UUIDs_due_to_boundary_tie'],0)

    def test_wrong_topk_missing_high_duplicate_and_order_fail(self):
        ref=source_reference(boundary_ties(),'Q2');rows=q2_rows(ref,'postgres')
        for modified in (rows[::-1],rows[:-1],rows+[rows[0]], [rows[0]]*1000):
            self.assertEqual(validate_q2(ref,modified,'postgres')['status'],'FAIL')
        bad=deepcopy(rows)
        lowest=min(ref['eligible'].values(),key=lambda r:r['final_total'])
        bad[-1]=lowest
        self.assertEqual(validate_q2(ref,bad,'postgres')['status'],'FAIL')
        used={r['order_id'] for r in rows}
        extra=next(r for r in ref['eligible'].values() if r['order_id'] not in used and r['final_total']==ref['cutoff'])
        missing_high=deepcopy(rows[1:])+[extra]
        result=validate_q2(ref,missing_high,'postgres')
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['field'],'mandatory_UUIDs')
        bad=deepcopy(rows);bad[0]['final_total']='200.00'
        self.assertEqual(validate_q2(ref,bad,'postgres')['status'],'FAIL')

    def test_missing_alias_inconsistent_alias_and_timestamps_blocked(self):
        for mode in ('missing','wrong','offset','invalid_date'):
            docs=controlled()
            if mode=='missing': del docs[0]['payment']['final_total']
            elif mode=='wrong': docs[0]['payment']['final_total']=Decimal('1')
            elif mode=='offset': docs[0]['timestamp']='2026-01-01T00:00:00+00:00'
            else: docs[0]['timestamp']='2026-02-30T00:00:00Z'
            with self.assertRaises(QueryBlocked): source_reference(docs,'Q2')

    @patch.dict(os.environ,{'DATA_PG_CONTAINER':'a'*64,'DATA_DATABASE_NAME':'testdb'})
    def test_workmem_and_timeout_local_in_same_session(self):
        executor=QueryExecutor('postgres',1000)
        outputs=['{"work_mem":"4MB"}\n{"x":1}','{"work_mem":"64MB"}\n{"x":1}']
        with patch.object(executor.adapter,'sql',side_effect=outputs) as sql:
            executor.pg_session('SELECT 1;',{'work_mem':'4MB'})
            executor.pg_session('SELECT 1;',{'work_mem':'64MB'})
            for call,value in zip(sql.call_args_list,('4MB','64MB')):
                script=call.args[0]
                self.assertIn(f"SET LOCAL work_mem='{value}'",script)
                self.assertIn("SET LOCAL statement_timeout='1000ms'",script)
                self.assertTrue(script.startswith('BEGIN READ ONLY;'))
                self.assertTrue(script.endswith('ROLLBACK;\n'))
                self.assertIn("current_setting('work_mem')",script)

    @patch.dict(os.environ,{'DATA_MONGO_CONTAINER':'a'*64,'DATA_DATABASE_NAME':'testdb'})
    def test_aggregate_option_not_pipeline_stage(self):
        executor=QueryExecutor('mongo')
        for name,expected in [('allow_disk_false',False),('allow_disk_true',True)]:
            with patch.object(executor,'mongo_action',return_value={'effective':{},'rows':[]}) as call:
                executor.execute(QuerySpec('mongo','Q2',name),preflight=False)
                self.assertIs(call.call_args.kwargs['options']['allowDiskUse'],expected)
                self.assertEqual(call.call_args.kwargs['pipeline'],QuerySpec('mongo','Q2',name).pipeline)

    def test_missing_real_engine_results_are_blocked(self):
        ref=source_reference(controlled(),'Q1')
        result=compare_results(ref,{'postgres':q1_rows(ref,'postgres')})
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['checks']['postgres']['status'],'PASS')

    def test_mongo_index_audit(self):
        rows=[{'key':{'_id':1},'unique':True},{'key':{'timestamp':1}},{'key':{'order_id':1}}]
        self.assertEqual(audit_mongo(rows)['status'],'PASS')
        implicit=deepcopy(rows); del implicit[0]['unique']
        self.assertEqual(audit_mongo(implicit)['status'],'PASS')
        self.assertEqual(audit_mongo(rows+[{'key':{'payment.final_total':-1}}])['status'],'BLOCKED')
        self.assertEqual(audit_mongo(rows[:1])['status'],'BLOCKED')
        self.assertEqual(audit_mongo(rows+[rows[1]])['status'],'BLOCKED')

    def test_plan_missing_metrics_stay_none_and_zero_stays_zero(self):
        summary=summarize_plan([{'Plan':{'Node Type':'Seq Scan','Actual Rows':0}}],'postgres')
        self.assertIsNone(summary['nodes'][0]['Temp Written Blocks'])
        self.assertEqual(summary['nodes'][0]['Actual Rows'],0)
        summary=summarize_plan({'stage':'SORT','usedDisk':False},'mongo')
        self.assertIsNone(summary['nodes'][0]['spills'])
        self.assertIs(summary['nodes'][0]['usedDisk'],False)


if __name__=='__main__': unittest.main()
