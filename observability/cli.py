"""Local diagnostics and evidence export, not a second benchmark runner."""
from pathlib import Path
from decimal import Decimal
import argparse,json,shutil,time
from benchmark.config import Protocol,plain
from benchmark.results import write_json
from src.dataset.model import json_text
from queries.definitions import QueryBlocked
from .config import settings,ROOT,duration_seconds
from .prometheus import Prometheus
from .identity import inspect_container
from .provider import ExperimentalTelemetry
from .series import CPU,RSS,selector,counter_delta,rss_max

def main(argv=None):
    p=argparse.ArgumentParser(description='Local monitoring: health, targets, storage, diagnose, query, export. No database queries or privileged commands.')
    p.add_argument('action',choices=('health','targets','storage','diagnose','query','export'))
    p.add_argument('--container-id',help='full 64-character ID of the evaluated engine')
    p.add_argument('--seconds',type=int,default=10)
    p.add_argument('--output',type=Path)
    a=p.parse_args(argv)
    try:
        cfg=settings();api=Prometheus(cfg['MONITORING_PROMETHEUS_URL'])
        if a.action=='storage':
            usage=shutil.disk_usage(ROOT)
            report={'status':'PASS' if usage.free>=int(cfg['MONITORING_MIN_FREE_MB'])*1024**2 else 'BLOCKED',
                    'filesystem_observed':str(ROOT),'free_bytes':usage.free,'minimum_MiB':int(cfg['MONITORING_MIN_FREE_MB']),
                    'retention':cfg['MONITORING_RETENTION'],'size_retention':cfg['MONITORING_RETENTION_SIZE'],
                    'warning':'Check Docker TSDB volume filesystem too; this path may differ. Minimum is not a capacity guarantee.'}
        else:
            report={'status':'PASS','targets':api.targets()}
            report['build']=api.get('/api/v1/status/buildinfo')
            if report['build'].get('version')!='3.15.1':raise QueryBlocked('Prometheus version differs from pinned configuration')
            report['flags']=api.get('/api/v1/status/flags')
            for k,v in [('storage.tsdb.retention.time',cfg['MONITORING_RETENTION']),('storage.tsdb.retention.size',cfg['MONITORING_RETENTION_SIZE'])]:
                observed=report['flags'].get(k,'')
                same=duration_seconds(observed)==duration_seconds(v) if k.endswith('.time') else observed==v
                if not same:raise QueryBlocked('Effective Prometheus retention differs from requested configuration: '+k)
            if a.action in ('diagnose','query','export'):
                if not a.container_id:raise QueryBlocked('Container-specific diagnostics require --container-id (full ID)')
                identity=inspect_container(a.container_id)
                context={'snapshot':{'id':identity['id'],'label':identity['profile'],'image_id':identity['image_id']},'protocol':Protocol('pilot')}
                telemetry=ExperimentalTelemetry(None,context,cfg,api)
                report['probe']=telemetry.probe()
                if report['probe']['status']!='PASS':report['status']='BLOCKED'
                if a.action in ('query','export'):
                    if not 2<=a.seconds<=3600:raise QueryBlocked('Diagnostic duration must be 2..3600 seconds')
                    if not hasattr(telemetry,'labels'):raise QueryBlocked('No verified container series')
                    end=Decimal(time.time_ns())/10**9;start=end-a.seconds;report['window']={'start_epoch':start,'end_epoch':end,'diagnostic_only':True}
                    for metric,key,compute in [(CPU,'cpu_throttled_seconds',counter_delta),(RSS,'max_rss_mb',rss_max)]:
                        try:
                            labels,samples=api.raw(selector(metric,telemetry.labels),a.seconds+4,end)
                            value,method=compute(samples,start,end)
                            report[key]={'value':value,'method':method,'labels':labels,'samples':samples}
                        except QueryBlocked as exc:report[key]={'value':None,'reason':str(exc)};report['status']='BLOCKED'
            report['api_evidence']=api.requests
        if a.action=='export' and not a.output:raise QueryBlocked('export requires --output new JSON file')
        if a.output:
            a.output.parent.mkdir(parents=True,exist_ok=True);write_json(a.output,report)
        print(json_text(plain(report)));return 0 if report['status']=='PASS' else 2
    except (QueryBlocked,OSError,ValueError,KeyError) as exc:
        print(json_text({'status':'BLOCKED','reason':str(exc) if isinstance(exc,QueryBlocked) else type(exc).__name__,'metrics_invented':False}));return 2

if __name__=='__main__':raise SystemExit(main())
