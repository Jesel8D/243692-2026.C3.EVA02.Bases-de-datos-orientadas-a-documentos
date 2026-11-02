"""Exact decimal summaries OF repetition-level KPIs, never pooled latency P99."""
from decimal import Decimal
from statistics import median
from collections import defaultdict
from queries.definitions import QuerySpec,QueryBlocked
METRICS=('throughput_qps','latency_p50_ms','latency_p95_ms','latency_p99_ms','cpu_throttled_seconds','max_rss_mb')

def summarize(values):
    values=[Decimal(str(v)) for v in values if v is not None]
    if not values:return {'n':0,'mean':None,'median':None,'min':None,'max':None}
    return {'n':len(values),'mean':sum(values)/len(values),'median':median(values),'min':min(values),'max':max(values)}

def difference(reference,other):
    if reference is None or other is None:return {'absolute':None,'percent':None,'reason':'missing comparison measurement'}
    return {'absolute':other-reference,'percent':(other-reference)*100/reference if reference!=0 else None,
            'reason':'zero reference: percentage undefined' if reference==0 else 'PostgreSQL minus MongoDB; percent relative to MongoDB'}

def groups(snapshot,plan):
    expected=defaultdict(list)
    for cohort in {e['cohort'] for e in snapshot.experiments} or {'no-measurements'}:
        for s in plan['scenarios']:expected[(cohort,s.engine,s.profile,s.query,s.variant,s.concurrency)].append(s)
    output=[]
    for key,scenarios in sorted(expected.items()):
        cohort,engine,profile,query,variant,c=key
        rows=[r for r in snapshot.records if (r.cohort,r.scenario.engine,r.scenario.profile,r.scenario.query,r.scenario.variant,r.scenario.concurrency)==key]
        valid=[r for r in rows if r.valid];runs={r.scenario.run_number for r in valid}
        output.append({'cohort':cohort,'engine':engine,'profile':profile,'query':query,'variant':variant,'concurrency':c,
            'n_valid':len(valid),'expected_in_plan':len(scenarios),'triplicate_complete':runs=={1,2,3} and len(valid)==3,
            'status':'complete triplicate' if runs=={1,2,3} and len(valid)==3 else 'incomplete/preliminary',
            'statistics':{m:summarize([Decimal(r.row[m]) for r in valid]) for m in METRICS},
            'spill_confirmed':sum(r.meta.get('telemetry',{}).get('disk_spill') is True for r in rows),
            'oom_confirmed':sum(r.meta.get('telemetry',{}).get('oom_killed') is True for r in rows),
            'failed_observed':sum(not r.valid for r in rows),
            'records':valid})
    return output

def comparisons(groups,pairs=()):
    mapping={}
    for pair in pairs:
        try:m,p=pair.split(':');QuerySpec('mongo','Q2',m);QuerySpec('postgres','Q2',p)
        except (ValueError,QueryBlocked):raise QueryBlocked('Q2 pair must explicitly name mongo_variant:postgres_variant')
        if m in mapping:raise QueryBlocked('Duplicate/ambiguous Mongo Q2 comparison pair')
        mapping[m]=p
    output=[];paired_pg=set()
    for a in groups:
        if a['engine']!='mongo':continue
        wanted='default' if a['query']=='Q1' else mapping.get(a['variant'])
        if wanted is None:
            output.append({'cohort':a['cohort'],'query':'Q2','profile':a['profile'],'concurrency':a['concurrency'],'mongo_variant':a['variant'],'status':'NOT_COMPARABLE','reason':'No explicit Q2 modality pair; buffer settings are not intrinsically equivalent'});continue
        b=next((b for b in groups if b['engine']=='postgres' and b['cohort']==a['cohort'] and b['profile']==a['profile'] and b['query']==a['query'] and b['variant']==wanted and b['concurrency']==a['concurrency']),None)
        if b is not None:paired_pg.add((b['cohort'],b['profile'],b['query'],b['variant'],b['concurrency']))
        item={'cohort':a['cohort'],'query':a['query'],'profile':a['profile'],'concurrency':a['concurrency'],'mongo_variant':a['variant'],'postgres_variant':wanted}
        if b is None or not a['triplicate_complete'] or not b['triplicate_complete']:
            output.append({**item,'status':'NOT_COMPARABLE','reason':'Both engines require three valid repetitions under the same cohort/profile/workload/concurrency'});continue
        output.append({**item,'status':'COMPARABLE','caution':'Descriptive contrast; no causal/superiority claim or implicit buffer equivalence',
            'metric_statistic':'median of repetition-level KPIs',
            'differences':{m:difference(a['statistics'][m]['median'],b['statistics'][m]['median']) for m in METRICS}})
    for b in groups:
        if b['engine']=='postgres' and (b['cohort'],b['profile'],b['query'],b['variant'],b['concurrency']) not in paired_pg:
            output.append({'cohort':b['cohort'],'query':b['query'],'profile':b['profile'],'concurrency':b['concurrency'],'postgres_variant':b['variant'],
                'status':'NOT_COMPARABLE','reason':'No matching MongoDB scenario or no explicit Q2 modality pair'})
    return output
