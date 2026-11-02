"""Exact percentiles on disk; no unbounded response/latency list in RAM."""
from decimal import Decimal
import sqlite3


def stage(start,end,window_start,window_end):
    return 'measurement' if window_start<=start<window_end and start<=end<=window_end else 'excluded_boundary'


def percentiles(database):
    n=database.execute('SELECT count(*) FROM latencies').fetchone()[0]
    if not n: return {'samples':0,'latency_p50_ms':None,'latency_p95_ms':None,'latency_p99_ms':None}
    result={'samples':n}
    for label,p in [('50',50),('95',95),('99',99)]:
        # Hyndman-Fan type 7: h=(n-1)*p, exact linear interpolation in nanoseconds.
        h=Decimal(n-1)*Decimal(p)/100
        i=int(h);fraction=h-i
        a=database.execute('SELECT ns FROM latencies ORDER BY ns LIMIT 1 OFFSET ?',(i,)).fetchone()[0]
        b=database.execute('SELECT ns FROM latencies ORDER BY ns LIMIT 1 OFFSET ?',(min(i+1,n-1),)).fetchone()[0]
        result[f'latency_p{label}_ms']=(Decimal(a)+(Decimal(b)-a)*fraction)/1000000
    return result


def aggregate(directory,window,completed):
    path=directory/'metrics.sqlite'
    db=sqlite3.connect(path)
    db.execute('PRAGMA cache_size=-2048');db.execute('PRAGMA temp_store=FILE')
    db.execute('CREATE TABLE latencies(ns INTEGER NOT NULL)')
    counts={'successful_inside':0,'errors':0,'excluded_boundary':0,'warmup':0}
    for p in sorted(directory.glob('client-*.sqlite')):
        with sqlite3.connect(p) as raw:
            for phase,start,end,outcome,_ in raw.execute('SELECT phase,start_ns,end_ns,outcome,error_class FROM operations ORDER BY sequence'):
                if phase=='warmup': counts['warmup']+=1;continue
                if outcome!='ok': counts['errors']+=1;continue
                if window is None or stage(start,end,*window)!='measurement': counts['excluded_boundary']+=1;continue
                db.execute('INSERT INTO latencies VALUES (?)',(end-start,));counts['successful_inside']+=1
    db.execute('CREATE INDEX latency_order ON latencies(ns)');db.commit()
    result=percentiles(db)
    result['throughput_qps']=(Decimal(counts['successful_inside'])*1000000000/Decimal(window[1]-window[0])) if completed and window else None
    if not completed:
        for k in ('latency_p50_ms','latency_p95_ms','latency_p99_ms'): result[k]=None
    result.update(counts)
    db.close()
    return result
