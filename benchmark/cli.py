import argparse,os,signal,threading,uuid,subprocess
from dataclasses import asdict
from pathlib import Path
from src.dataset.model import json_text,DataError
from src.dataset.files import validate_file
from queries.definitions import QueryBlocked,QuerySpec
from queries.execution import QueryExecutor
from . import RUNNER_VERSION
from .config import Protocol,plain,digest,source_hashes
from .matrix import matrix
from .environment import helper,snapshot,cgroup_path,host_info,docker
from .telemetry import make_telemetry
from .preflight import preflight,driver_versions
from .preflight_reuse import InvocationValidation
from .results import Store,experiment_lock,write_json,consolidate
from .runner import run_repetition
from .cache import manual_cache


def parser():
    p=argparse.ArgumentParser(description='Phase 4: plan only by default; real execution must be explicitly selected. No fake CLI backend.')
    p.add_argument('action',choices=('plan','run','consolidate'))
    p.add_argument('--matrix',choices=('base','extended','single'))
    p.add_argument('--engine',choices=('mongo','postgres'))
    p.add_argument('--profile',choices=('baseline','medium','severe'))
    p.add_argument('--query',choices=('Q1','Q2'))
    p.add_argument('--variant')
    p.add_argument('--concurrency',type=int,choices=(1,10,50))
    p.add_argument('--run-number',type=int,choices=(1,2,3))
    p.add_argument('--base-mongo-variant',choices=('allow_disk_false','allow_disk_true'))
    p.add_argument('--base-postgres-variant',choices=('work_mem_4mb','work_mem_64mb'))
    p.add_argument('--mode',choices=('pilot','definitive'))
    p.add_argument('--warmup',type=float,default=60)
    p.add_argument('--measurement',type=float,default=300)
    p.add_argument('--cooldown',type=float,default=60)
    p.add_argument('--timeout-ms',type=int,default=120000)
    p.add_argument('--cache',choices=('skip','manual'),default='skip')
    p.add_argument('--file')
    p.add_argument('--output',type=Path)
    p.add_argument('--experiment')
    p.add_argument('--execute-selected',action='store_true')
    p.add_argument('--confirm-matrix',action='store_true')
    p.add_argument('--use-existing-services',action='store_true',help='pilot only; selected leaf limits must still match')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--reuse-global-preflight',action='store_true',help='definitive only; one full check per invocation with guarded in-memory reuse; requires exclusive database writers')
    p.add_argument('--inputs',type=Path,nargs='+',help='consolidate: experiment directories with sidecars')
    p.add_argument('--allow-nonfinal',action='store_true',help='consolidate diagnostic pilot CSV only, never silently final')
    return p


def plan_from_args(a):
    selected=matrix(a.matrix,base_variants={'mongo':a.base_mongo_variant,'postgres':a.base_postgres_variant} if a.matrix=='base' else None,
        engine=a.engine,profile=a.profile,query=a.query,variant=a.variant,concurrency=a.concurrency,run_number=a.run_number)
    return selected,{'matrix':a.matrix,'extended_is_approved':False,'selected_repetitions':len(selected),
       'scenario_cells':len({(s.engine,s.profile,s.query,s.variant,s.concurrency) for s in selected}),
       'base_Q2_selection':{'mongo':a.base_mongo_variant,'postgres':a.base_postgres_variant} if a.matrix=='base' else None,
       'note':'base omits other Q2 modality explicitly; extended is implementation capability, not academic approval',
       'plan':[{'id':s.id,**asdict(s)} for s in selected]}


def execute(a,selected,plan):
    import re
    if not a.mode or not a.execute_selected or not a.output or not a.experiment or not a.file:
        raise QueryBlocked('run requires mode, file, output, experiment and --execute-selected')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',a.experiment):raise QueryBlocked('Experiment name must be a simple slug')
    if len(selected)>1 and not a.confirm_matrix:raise QueryBlocked('Multiple repetitions require --confirm-matrix explicitly')
    if a.mode=='pilot' and len(selected)!=1:raise QueryBlocked('Pilot is exactly one scenario/repetition; select single mode')
    if a.use_existing_services and a.mode!='pilot':raise QueryBlocked('--use-existing-services is pilot-only')
    if a.reuse_global_preflight and a.mode!='definitive':raise QueryBlocked('Global preflight reuse is definitive-only')
    if a.reuse_global_preflight and len(selected)<2:raise QueryBlocked('Global preflight reuse requires multiple scenarios in one invocation')
    if a.reuse_global_preflight and os.environ.get('BENCHMARK_EXCLUSIVE_WRITERS_ACK')!='I_CONFIRM_NO_EXTERNAL_DB_WRITES':
        raise QueryBlocked('Reuse requires BENCHMARK_EXCLUSIVE_WRITERS_ACK=I_CONFIRM_NO_EXTERNAL_DB_WRITES')
    protocol=Protocol(a.mode,a.warmup,a.measurement,a.cooldown,a.timeout_ms,a.cache)
    dataset=validate_file(a.file)
    versions=driver_versions()
    a.output.mkdir(parents=True,exist_ok=True)
    if a.mode=='definitive':
        if dataset['count']!=500000:raise QueryBlocked('Definitive requires 500000 records; no benchmark starts')
        from observability.config import settings
        from observability.prometheus import Prometheus
        Prometheus(settings()['MONITORING_PROMETHEUS_URL']).targets()
        # Full, container-specific telemetry checks still run for EVERY repetition below.
    destination=a.output/('pilots' if a.mode=='pilot' else 'definitive')/a.experiment
    cancel=threading.Event();signals=[]
    def interrupted(signum,_):signals.append(signal.Signals(signum).name);cancel.set()
    old={s:signal.signal(s,interrupted) for s in (signal.SIGINT,signal.SIGTERM)}
    try:
        with experiment_lock(destination):
            if not a.use_existing_services:helper('activate',selected[0].profile,selected[0].engine)
            identities={}
            for e in sorted({s.engine for s in selected}):
                first=next(s for s in selected if s.engine==e)
                shot=snapshot(e,first.profile)
                os.environ['DATA_MONGO_CONTAINER' if e=='mongo' else 'DATA_PG_CONTAINER']=shot['id']
                result=QueryExecutor(e,protocol.timeout_ms).execute(QuerySpec(e,'Q1','default',protocol.timeout_ms))
                identities[e]={'image':shot['image'],'image_id':shot['image_id'],'server_version':result['effective']['server_version']}
            configuration={'runner_version':RUNNER_VERSION,'protocol':asdict(protocol),'selection':plan,'sources':source_hashes(),
                'dataset':{'sha256':dataset['sha256'],'count':dataset['count'],'configuration':dataset['configuration']},
                'identities':identities,'drivers':versions,'host':host_info(),'use_existing_services':a.use_existing_services,
                'evidence_kind':'real_native_driver','row_variant_mapping':'result.json + row SHA256; consolidation sidecar required',
                'monitoring_configuration':__import__('observability.config',fromlist=['settings']).settings(),
                'global_preflight_policy':{'enabled':a.reuse_global_preflight,'scope':'single invocation only',
                  'external_writer_exclusion_acknowledged':a.reuse_global_preflight,
                  'limitations':'metadata/change counters do not constitute a cryptographic DB snapshot'}}
            store=Store(destination,plain(configuration),resume=a.resume)
            from datetime import datetime,timezone
            write_json(destination/('invocation-'+uuid.uuid4().hex+'.json'),{'started_at_utc':datetime.now(timezone.utc).isoformat(),'resume':a.resume,'incomplete_attempts':store.incomplete,'incomplete_details':store.incomplete_details})
            global_validation=InvocationValidation(a.file) if a.reuse_global_preflight else None
            for s in selected:
                if s.id in store.finished:continue
                if cancel.is_set():raise InterruptedError('Cancelled before next repetition')
                if not a.use_existing_services:helper('activate',s.profile,s.engine)
                shot=snapshot(s.engine,s.profile)
                os.environ['DATA_MONGO_CONTAINER' if s.engine=='mongo' else 'DATA_PG_CONTAINER']=shot['id']
                telemetry=make_telemetry(cgroup_path(shot['pid']),context={'snapshot':shot,'scenario':s,'protocol':protocol})
                evidence,factory=preflight(s,protocol,a.file,a.output,shot,telemetry,global_validation=global_validation)
                if evidence['identity']!=identities[s.engine]:raise QueryBlocked('Engine identity changed; start a new experiment')
                if a.use_existing_services:evidence['deviations'].append('pilot: ancestors/other engine isolation not fully validated')
                else:helper('isolate',s.profile,s.engine)
                directory=store.begin(s)
                write_json(directory/'preflight.json',evidence)
                cache_action=(lambda:manual_cache(directory.name,cancel,directory/'cache.json')) if protocol.cache=='manual' else None
                try:
                    result=run_repetition(s,protocol,directory,factory,telemetry,external_cancel=cancel,cache_action=cache_action)
                except (InterruptedError,KeyboardInterrupt):
                    write_json(directory/'interruption.json',{'reason':signals or ['controlled_interruption'],'repetition_complete':False})
                    raise
                import json
                end_state=json.loads(docker('inspect','--format','{"running":{{.State.Running}},"oom_killed":{{.State.OOMKilled}},"exit_code":{{.State.ExitCode}}}',shot['id']))
                result['container_end_state']=end_state
                if end_state['oom_killed'] and not shot.get('oom_killed',False):
                    result['telemetry']['oom_killed']=True
                    result['telemetry']['oom_evidence']='Docker State.OOMKilled true, observed during attempt; not exit 137 inference'
                    result['status']='oom';result['eligible_for_final_analysis']=False
                    result['telemetry']['oom_scope']='attempt-level Docker state; exact measurement attribution not established'
                result['deviations']=evidence['deviations']
                if a.matrix=='extended':result['deviations'].append('extended matrix is not academically approved')
                if evidence['deviations']:result['eligible_for_final_analysis']=False
                row=store.commit(s,directory,result)
                print(json_text(plain({'status':row['status'],'experiment':str(destination),'scenario_id':s.id,
                                      'samples':result['metrics']['samples'],'eligible_for_final_analysis':result['eligible_for_final_analysis']})))
                if row['status'] in ('error','oom'):return 1
            import json
            failed=sum(json.loads((d/'result.json').read_text())['status'] in ('error','oom') for d in store.finished.values())
            if failed:print(json_text({'experiment_state':'finalized_with_errors','failed_repetitions':failed,'automatic_retries':False}))
            return 1 if failed else 0
    finally:
        for s,handler in old.items():signal.signal(s,handler)


def main(argv=None):
    a=parser().parse_args(argv)
    try:
        if a.action=='consolidate':
            if not a.inputs or not a.output:raise QueryBlocked('consolidate requires --inputs experiment directories and --output CSV path')
            consolidate(a.inputs,a.output,allow_nonfinal=a.allow_nonfinal)
            print(json_text({'status':'PASS','output':str(a.output),'allow_nonfinal':a.allow_nonfinal}));return 0
        selected,plan=plan_from_args(a)
        if a.action=='plan':print(json_text(plan));return 0
        return execute(a,selected,plan)
    except (QueryBlocked,DataError,OSError,ValueError,ImportError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        # No native driver error text/dsn/password is printed; only known sanitized prerequisites.
        message=str(exc) if isinstance(exc,(QueryBlocked,DataError)) else type(exc).__name__
        report={'status':'BLOCKED','reason':message,'stage':'preflight/orchestration','measurements_invented':False}
        if a.action=='run' and a.output:
            folder=a.output/'preflight_reports';folder.mkdir(parents=True,exist_ok=True)
            write_json(folder/('blocked-'+uuid.uuid4().hex+'.json'),report)
        print(json_text(report));return 2
    except (InterruptedError,KeyboardInterrupt):
        print(json_text({'status':'BLOCKED','reason':'interrupted; incomplete repetition is resumable, never counted successful'}));return 130
