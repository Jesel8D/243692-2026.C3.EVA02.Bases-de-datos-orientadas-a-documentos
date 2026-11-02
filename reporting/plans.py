"""Read existing diagnostic plans only; never run EXPLAIN or contact a database."""
from pathlib import Path
from src.dataset.model import parse_json
from queries.plans import summarize_plan
from queries.definitions import QueryBlocked
from .loader import read_stable

def load_plans(paths,snapshot):
    output=[]
    for path in paths:
        p=Path(path).resolve()
        candidates=[p] if p.is_file() else sorted(p.glob('*.json'))
        for candidate in candidates:
            try:
                value=parse_json(read_stable(snapshot,candidate).decode())
                if 'plan' not in value or value.get('engine') not in ('mongo','postgres'):continue
                if value.get('evidence_kind')=='simulated_reporting_test' and not snapshot.test_only:raise QueryBlocked('Synthetic plan forbidden outside internal reporting tests')
                summary=summarize_plan(value['plan'],value['engine'])
                output.append({'path':str(candidate),'engine':value['engine'],'query':value.get('query'),'variant':value.get('variant'),
                    'captured_at':value.get('evidence_written_at_utc',value.get('captured_at_utc')),'effective':value.get('effective',{}),
                    'dataset_binding':value.get('dataset_binding',{}),'dataset_sha256':value.get('dataset_sha256'),'dataset_count':value.get('preflight',{}).get('count'),'source':value.get('source','diagnostic artifact supplied by operator'),
                    'summary':summary,'note':'Diagnostic execution; not evidence of spill of a previous timed query or benchmark latency'})
            except (OSError,ValueError,KeyError,TypeError) as exc:raise QueryBlocked('Invalid diagnostic plan: '+candidate.name+' '+type(exc).__name__) from exc
    return output
