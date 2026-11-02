"""Identity matching and sampled-window calculations. Unknown is never zero."""
from decimal import Decimal
import json,re
from queries.definitions import QueryBlocked

CPU='container_cpu_cfs_throttled_seconds_total'
RSS='container_memory_rss'
CATALOG=(CPU,RSS,'container_cpu_usage_seconds_total','container_cpu_cfs_throttled_periods_total',
 'container_memory_usage_bytes','container_memory_working_set_bytes','container_memory_failcnt')

def has_id(cgroup_id,cid):
    if not re.fullmatch('[a-f0-9]{64}',cid):raise QueryBlocked('Full 64-character container ID required')
    return bool(re.search(r'(?:/|-)'+re.escape(cid)+r'(?:\.scope)?$',cgroup_id))

def select_container(results,identity,now=None):
    found=[r for r in results if has_id(r.get('metric',{}).get('id',''),identity['id'])]
    if now is not None:
        try:found=[r for r in found if -Decimal('.1')<=Decimal(str(now))-Decimal(r['value'][1])<=Decimal('2.5')]
        except (KeyError,ValueError,ArithmeticError):raise QueryBlocked('Invalid container freshness evidence')
    if len(found)!=1:raise QueryBlocked('Container series missing/ambiguous for exact Docker ID (fresh series required)')
    labels=found[0]['metric']
    for label,key in [('container_label_com_docker_compose_project','project'),('container_label_com_docker_compose_service','service'),('container_label_academic_profile','profile')]:
        if labels.get(label)!=identity[key]:raise QueryBlocked('Container series label does not match verified '+key)
    return labels

def selector(metric,labels):
    if not re.fullmatch('[a-zA-Z_:][a-zA-Z0-9_:]*',metric):raise QueryBlocked('Invalid metric name')
    return metric+'{job="cadvisor",id='+json.dumps(labels['id'])+'}'

def window_samples(samples,start,end,gap=Decimal('2.5')):
    start,end=Decimal(str(start)),Decimal(str(end))
    inside=[(t,v) for t,v in samples if start<=t<=end]
    if len(inside)<2:raise QueryBlocked('Insufficient samples inside measurement window')
    if inside[0][0]-start>gap or end-inside[-1][0]>gap or any(b[0]-a[0]>gap for a,b in zip(inside,inside[1:])):
        raise QueryBlocked('Telemetry gap/insufficient boundary coverage')
    return inside

def counter_delta(samples,start,end):
    selected=window_samples(samples,start,end)
    if any(b[1]<a[1] for a,b in zip(samples,samples[1:])) or any(v<0 for _,v in samples):
        raise QueryBlocked('Counter reset or negative value: no valid delta')
    return selected[-1][1]-selected[0][1],{'first':selected[0][0],'last':selected[-1][0],
       'covered_seconds':selected[-1][0]-selected[0][0],'samples':len(selected),
       'method':'raw last-first inside measurement; no extrapolation; edges omitted'}

def rss_max(samples,start,end):
    selected=window_samples(samples,start,end)
    if any(v<0 for _,v in selected):raise QueryBlocked('Negative RSS')
    return max(v for _,v in selected)/Decimal(1000000),{'samples':len(selected),'divisor_bytes_per_MB':1000000,
          'scope':'maximum observed RSS samples inside window, not absolute instantaneous peak'}
