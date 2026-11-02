"""Offline CLI; no experiment execution, no database queries, no synthetic CLI backend."""
import argparse,hashlib,json,time
from pathlib import Path
from datetime import datetime,timezone
from benchmark.config import plain,digest
from benchmark.results import read_csv,write_json
from src.dataset.model import json_text,parse_json,DataError
from queries.definitions import QueryBlocked
from .loader import load,Snapshot
from .progress import expected_plan,progress,terminal
from .plans import load_plans
from .generator import generate,readiness
from .statistics import groups

def parser():
    p=argparse.ArgumentParser(description='Offline reports/progress from immutable benchmark commits. Does not run queries or benchmarks.')
    p.add_argument('action',choices=('progress','validate','generate','charts','capture-environment'))
    p.add_argument('--inputs',nargs='*',type=Path,default=[])
    p.add_argument('--scope',choices=('definitive','pilot'),default='definitive')
    p.add_argument('--matrix',choices=('auto','base','extended'),default='auto')
    p.add_argument('--plan',type=Path)
    p.add_argument('--base-mongo-variant',choices=('allow_disk_false','allow_disk_true'))
    p.add_argument('--base-postgres-variant',choices=('work_mem_4mb','work_mem_64mb'))
    p.add_argument('--mode',choices=('partial','final'),default='partial')
    p.add_argument('--allow-partial',action='store_true')
    p.add_argument('--audit-all',action='store_true',help='also hash potentially large operation journals; final generation enables this automatically')
    p.add_argument('--q2-pair',action='append',default=[],help='Explicit mongo_variant:postgres_variant descriptive comparison; no automatic buffer equivalence')
    p.add_argument('--plans',type=Path,nargs='*',default=[])
    p.add_argument('--csv',type=Path,help='validate action: standalone official schema only, no academic provenance claim')
    p.add_argument('--output',type=Path)
    p.add_argument('--pdf',action='store_true')
    p.add_argument('--environment',type=Path)
    p.add_argument('--student');p.add_argument('--group');p.add_argument('--teacher')
    p.add_argument('--json',action='store_true',help='progress: machine-readable JSON instead of human terminal summary')
    p.add_argument('--watch',action='store_true',help='progress or partial generation only; does not acquire runner lock')
    p.add_argument('--interval',type=float,default=30)
    p.add_argument('--iterations',type=int,default=0,help='0 watches until Ctrl-C')
    return p

def capture(path):
    if not path:raise QueryBlocked('capture-environment requires --output new JSON file; run outside measurement windows')
    from benchmark.environment import host_info,docker
    value={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'host':host_info(),
       'scope':'independent current observation, not retrospective proof of the benchmark environment'}
    for key,args in [('docker_engine',('info','--format','{{.ServerVersion}}')),('docker_compose',('compose','version','--short')),('docker_cgroups',('info','--format','{{.CgroupVersion}}'))]:
        try:value[key]=docker(*args)
        except (OSError,QueryBlocked):value[key]=None
    path.parent.mkdir(parents=True,exist_ok=True);write_json(path,value)
    return {'status':'PASS','output':str(path),'environment':value}

def main(argv=None):
    a=parser().parse_args(argv)
    try:
        if a.action=='capture-environment':print(json_text(plain(capture(a.output))));return 0
        if a.csv:
            if a.action!='validate' or a.inputs:raise QueryBlocked('--csv is standalone schema validation only')
            rows=read_csv(a.csv);print(json_text({'status':'SCHEMA_ONLY','rows':len(rows),'provenance':'not established; variants/final validity require experiment sidecars'}));return 0
        if a.watch and (a.action not in ('progress','generate','charts') or a.mode=='final'):raise QueryBlocked('Watch is for progress/partial generation, never final export')
        if a.interval<1 or a.iterations<0:raise QueryBlocked('Watch interval >=1 second; iterations >=0')
        previous=None;iteration=0
        while True:
            snapshot=load(a.inputs,a.scope,a.audit_all or a.mode=='final') if a.inputs else Snapshot(scope=a.scope,integrity='all' if a.audit_all or a.mode=='final' else 'selected')
            base={'mongo':a.base_mongo_variant,'postgres':a.base_postgres_variant} if a.matrix=='base' else None
            plan=expected_plan(snapshot,a.matrix,base,a.plan)
            plans=load_plans(a.plans,snapshot)
            fingerprint=digest({'files':{k:v['sha256'] for k,v in snapshot.files.items()},'invalid':snapshot.invalid,'unfinished':snapshot.unfinished,'plan':[s.id for s in plan['scenarios']],'matrix':plan['matrix'],'environment_hash':hashlib.sha256(a.environment.read_bytes()).hexdigest() if a.environment else None})
            if a.action=='progress':result=progress(snapshot,plan)
            elif a.action=='validate':
                result={'status':'NO_MEASUREMENTS' if not snapshot.records and not snapshot.invalid else 'PASS' if not snapshot.invalid and all(r.valid for r in snapshot.records) else 'PARTIAL_OR_INVALID','scope':snapshot.scope,'academic_eligible_rows':sum(r.valid for r in snapshot.records) if snapshot.scope=='definitive' else 0,
                    'integrity':snapshot.integrity,'corrupt':snapshot.invalid,'excluded':[{'scenario':r.scenario.id,'reasons':r.reasons} for r in snapshot.records if not r.valid],
                    'readiness':readiness(snapshot,plan,groups(snapshot,plan),plans)}
            elif previous!=fingerprint:
                if not a.output:raise QueryBlocked('generate/charts requires --output directory outside original experiments')
                env=parse_json(a.environment.read_text()) if a.environment else None
                folder=generate(snapshot,plan,a.output,mode=a.mode,allow_partial=a.allow_partial,plans=plans,
                    q2_pairs=getattr(a,'q2_pair',[]) or [],personal={'student':a.student,'group':a.group,'teacher':a.teacher},pdf=a.pdf,environment=env)
                result={'status':'GENERATED','directory':str(folder),'html':str(folder/'reporte.html'),'markdown':str(folder/'reporte.md'),'complete_manifest':str(folder/'analysis-manifest.json')}
            else:result={'status':'UNCHANGED','new_report_written':False}
            print(terminal(result) if a.action=='progress' and not a.json else json_text(plain(result)),flush=True);previous=fingerprint;iteration+=1
            if not a.watch or a.iterations and iteration>=a.iterations:return 0
            time.sleep(a.interval)
    except (QueryBlocked,DataError,OSError,ValueError,KeyError,TypeError,ImportError) as exc:
        print(json_text({'status':'BLOCKED','reason':str(exc) if isinstance(exc,(QueryBlocked,DataError)) else type(exc).__name__,'measurements_invented':False}));return 2
    except KeyboardInterrupt:return 130

if __name__=='__main__':raise SystemExit(main())
