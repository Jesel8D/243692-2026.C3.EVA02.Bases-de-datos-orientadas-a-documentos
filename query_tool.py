#!/usr/bin/env python3
"""Run/validate/explain original Q1/Q2 and safely inspect/prepare indexes."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from decimal import DecimalException

from src.dataset.files import iter_file, validate_file
from src.dataset.model import DataError, json_text
from src.dataset.operations import compare_dataset
from queries.definitions import QuerySpec, QueryBlocked, VARIANTS
from queries.execution import QueryExecutor
from queries.indexes import inspect_indexes
from queries.plans import summarize_plan
from queries.validation import source_reference, compare_results


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('run','validate','explain','indexes'))
    p.add_argument('--engine', choices=('mongo','postgres','both'), default='both')
    p.add_argument('--query', choices=('Q1','Q2'), default='Q1')
    p.add_argument('--variant', help='run/explain: explicit Q2 variant; Q1 uses default')
    p.add_argument('--timeout-ms', type=int, default=120000)
    p.add_argument('--file', help='validate requires source JSONL + manifest; explain optionally verifies and binds the source dataset')
    p.add_argument('--report', help='exclusive-create JSON (not benchmark CSV)')
    p.add_argument('--apply', action='store_true', help='indexes: add required missing indexes; never drop')
    p.add_argument('--accept-text-index-proposal', action='store_true')
    args = p.parse_args(argv)
    try:
        if args.report and Path(args.report).exists():
            raise QueryBlocked('Report exists: refusing overwrite before query execution')
        if args.action not in ('indexes',) and (args.apply or args.accept_text_index_proposal):
            raise QueryBlocked('Index flags only valid for indexes action')
        if args.action in ('run','explain') and args.engine=='both':
            raise QueryBlocked('run/explain require one explicit engine')
        if args.action=='validate' and args.variant:
            raise QueryBlocked('validate checks every configured variant automatically')
        engines = ['mongo','postgres'] if args.engine=='both' else [args.engine]
        executors = {e: QueryExecutor(e,args.timeout_ms) for e in engines}
        if args.action=='indexes':
            reports = {e:inspect_indexes(x,apply=args.apply,accept_text_proposal=args.accept_text_index_proposal) for e,x in executors.items()}
            result = {'status':'PASS' if all(r['status']=='PASS' for r in reports.values()) else 'BLOCKED','index_checks':reports}
        elif args.action=='validate':
            if not args.file:
                raise QueryBlocked('validate requires --file and its manifest')
            stats = validate_file(args.file)
            if args.query=='Q2' and stats['configuration']['payment_layout']!='totals-and-alias':
                raise QueryBlocked('Q2 incompatible with totals-only; original query is not rewritten')
            source_match = compare_dataset([x.adapter for x in executors.values()], args.file)
            reference = source_reference((doc for _,_,doc in iter_file(args.file)),args.query)
            outputs = {}
            checks = []
            for engine, executor in executors.items():
                outputs[engine] = []
                for variant in VARIANTS[engine][args.query]:
                    answer = executor.execute(QuerySpec(engine,args.query,variant,args.timeout_ms))
                    outputs[engine].append((variant, answer['rows']))
                    one = compare_results(reference,{engine:answer['rows']})
                    checks.append({'engine':engine,'variant':variant,'oracle':one['checks'][engine],
                                   'effective':answer['effective'],'preflight':answer['preflight']})
            comparisons = []
            if len(engines)==2:
                for mv, mr in outputs['mongo']:
                    for pv, pr in outputs['postgres']:
                        comparisons.append({'variants':{'mongo':mv,'postgres':pv}, **compare_results(reference,{'mongo':mr,'postgres':pr})})
            failed = any(c['oracle']['status']=='FAIL' for c in checks) or any(c['status']=='FAIL' for c in comparisons)
            result = {'status':'FAIL' if failed else 'PASS' if len(engines)==2 else 'BLOCKED',
                      'query':args.query,'source_sha256':stats['sha256'],'source_match':source_match,
                      'variant_checks':checks,'cross_engine_comparisons':comparisons,
                      'scope':'both engines' if len(engines)==2 else 'single-engine correctness; cross-engine equivalence BLOCKED'}
        else:
            variant = args.variant or ('default' if args.query=='Q1' else '')
            binding = None
            if args.action=='explain' and args.file:
                stats = validate_file(args.file)
                source_match = compare_dataset([executors[args.engine].adapter], args.file)
                binding = {'dataset_sha256':stats['sha256'],'dataset_binding':source_match}
            answer = executors[args.engine].execute(QuerySpec(args.engine,args.query,variant,args.timeout_ms),explain=args.action=='explain')
            result = {'status':'PASS','scope':'execution only, not equivalence/performance', **answer}
            if args.action=='explain':
                result['plan_summary'] = summarize_plan(answer['plan'],args.engine)
                if binding:result.update(binding)
        result['captured_at_utc'] = datetime.now(timezone.utc).isoformat()
    except (DataError, QueryBlocked, OSError, DecimalException, KeyError, TypeError) as exc:
        result = {'status':'BLOCKED','query':args.query,'engine':args.engine,'field':'prerequisites/execution',
                  'expected':'compatible data/configuration and successful real engine execution',
                  'obtained':str(exc),'possible_cause':'missing final_total/types/date/schema/connection/privileges/timeout; no query was rewritten'}
    encoded = json_text(result) + '\n'
    if args.report and not Path(args.report).exists():
        try:
            with Path(args.report).open('x',encoding='utf8') as f:
                f.write(encoded)
        except OSError as exc:
            print('Report write failed: '+str(exc),file=sys.stderr)
            return 2
    print(encoded,end='')
    return {'PASS':0,'FAIL':1,'BLOCKED':2}[result['status']]


if __name__=='__main__':
    sys.exit(main())
