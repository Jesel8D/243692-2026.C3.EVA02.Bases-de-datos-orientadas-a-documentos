"""Immutable per-attempt CSV + JSON commit markers; lock protects resume/consolidation."""
from contextlib import contextmanager
from pathlib import Path
import csv,fcntl,hashlib,io,json,os,uuid
from src.dataset.model import json_text,parse_json
from queries.definitions import QueryBlocked
from .config import digest,plain

COLUMNS='timestamp_epoch,engine,profile,query_id,concurrency,run_number,throughput_qps,latency_p50_ms,latency_p95_ms,latency_p99_ms,cpu_throttled_seconds,max_rss_mb,disk_spill,status'.split(',')


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def immutable_write(path,text):
    path=Path(path)
    temp=path.parent/('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x',encoding='utf8',newline='') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.link(temp,path) # Atomic exclusive install; never replace an existing result.
        fd=os.open(path.parent,os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if temp.exists():temp.unlink() # Only this function's own temporary file.


def write_json(path,data):immutable_write(path,json_text(plain(data))+'\n')


def csv_text(row):
    if set(row)!=set(COLUMNS):raise QueryBlocked('Official CSV must have exactly 14 columns')
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=COLUMNS,lineterminator='\n')
    writer.writeheader();writer.writerow({k:'' if row[k] is None else int(row[k]) if type(row[k]) is bool else row[k] for k in COLUMNS})
    return out.getvalue()


def read_csv(path):
    text=Path(path).read_text()
    if not text.endswith('\n'):raise QueryBlocked('Partial/corrupt CSV: missing final newline')
    try:rows=list(csv.reader(io.StringIO(text),strict=True))
    except csv.Error as exc:raise QueryBlocked('CSV parse corruption') from exc
    if not rows or rows[0]!=COLUMNS or any(len(r)!=14 for r in rows[1:]):raise QueryBlocked('CSV header/row corruption')
    result=[]
    for r in rows[1:]:
        row=dict(zip(COLUMNS,r))
        if row['status'] not in ('ok','spill','oom','error'):raise QueryBlocked('Unknown official status')
        from decimal import Decimal,InvalidOperation
        try:
            for k in ('timestamp_epoch','throughput_qps','latency_p50_ms','latency_p95_ms','latency_p99_ms','cpu_throttled_seconds','max_rss_mb'):
                if row[k] and (not Decimal(row[k]).is_finite() or Decimal(row[k])<0):raise ValueError()
            if row['engine'] not in ('mongo','postgres') or row['query_id'] not in ('Q1','Q2'):raise ValueError()
            if int(row['concurrency']) not in (1,10,50) or int(row['run_number']) not in (1,2,3):raise ValueError()
            if not row['timestamp_epoch']:raise ValueError()
            from .matrix import PROFILES
            if row['profile'] not in {v[0] for v in PROFILES.values()} or row['disk_spill'] not in ('','0','1'):raise ValueError()
            if row['status'] in ('ok','spill'):
                if any(not row[k] for k in COLUMNS[6:13]):raise ValueError()
                if row['disk_spill']!=('1' if row['status']=='spill' else '0'):raise ValueError()
            values=[row[k] for k in ('latency_p50_ms','latency_p95_ms','latency_p99_ms')]
            if any(values) and (not all(values) or list(map(Decimal,values))!=sorted(map(Decimal,values))):raise ValueError()
        except (ValueError,InvalidOperation):raise QueryBlocked('Invalid CSV types/identifiers')
        result.append(row)
    return result


@contextmanager
def experiment_lock(path):
    path=Path(path);path.mkdir(parents=True,exist_ok=True)
    with (path/'.lock').open('a') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise QueryBlocked('Experiment already locked by another process') from exc
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)


class Store:
    def __init__(self,path,configuration,resume=False):
        self.path=Path(path);self.configuration=configuration;self.resumed=resume
        self.path.mkdir(parents=True,exist_ok=True)
        manifest=self.path/'experiment.json'
        if manifest.exists():
            if not resume:raise QueryBlocked('Experiment exists; use --resume, never overwrite')
            old=parse_json(manifest.read_text())
            if digest(old['configuration'])!=digest(configuration):raise QueryBlocked('Resume configuration/dataset/version/host/identity changed')
            self.experiment=old
        else:
            if resume:raise QueryBlocked('No experiment to resume')
            if any(p.name!='.lock' for p in self.path.iterdir()):raise QueryBlocked('Output directory not empty')
            from datetime import datetime,timezone
            self.experiment={'experiment_id':uuid.uuid4().hex,'started_at_utc':datetime.now(timezone.utc).isoformat(),'configuration':configuration}
            write_json(manifest,self.experiment)
        self.finished={};self.incomplete=[];self.incomplete_details=[]
        for started in sorted(self.path.glob('*/attempt-*/started.json')):
            directory=started.parent;commit=directory/'commit.json'
            if not commit.exists():
                rel=str(directory.relative_to(self.path));self.incomplete.append(rel)
                csv_state='absent'
                if (directory/'results.csv').exists():
                    try:read_csv(directory/'results.csv');csv_state='uncommitted_valid'
                    except QueryBlocked:csv_state='corrupt_uncommitted'
                self.incomplete_details.append({'path':rel,'scenario_id':parse_json(started.read_text())['scenario_id'],'csv_state':csv_state,'recovery':'preserve, do not repair; new attempt required'})
                continue
            marker=parse_json(commit.read_text())
            if not {'started.json','results.csv','result.json'}<=set(marker.get('files',{})):raise QueryBlocked('Commit marker missing mandatory evidence hashes')
            for name,sha in marker['files'].items():
                if '/' in name or name.startswith('.') or not (directory/name).is_file() or file_hash(directory/name)!=sha:
                    raise QueryBlocked('Committed evidence/CSV corrupt; refusing silent repair')
            rows=read_csv(directory/'results.csv')
            meta=parse_json((directory/'result.json').read_text())
            expected=parse_json(started.read_text())
            key=expected['scenario_id']
            from .matrix import Scenario,PROFILES
            if Scenario(**expected['scenario']).id!=key:raise QueryBlocked('Scenario ID/config mismatch')
            row=rows[0] if len(rows)==1 else {}
            want=expected['scenario']
            if row and (row['engine']!=want['engine'] or row['profile']!=PROFILES[want['profile']][0] or row['query_id']!=want['query'] or int(row['concurrency'])!=want['concurrency'] or int(row['run_number'])!=want['run_number'] or meta['variant']!=want['variant']):raise QueryBlocked('CSV/scenario/variant mismatch')
            if len(rows)!=1 or marker['scenario_id']!=key or meta['scenario']!=expected['scenario'] or key in self.finished:
                raise QueryBlocked('Duplicate or inconsistent committed repetition')
            self.finished[key]=directory
        self.unresolved_incomplete=[d for d in self.incomplete_details if d['scenario_id'] not in self.finished]

    def begin(self,scenario):
        if scenario.id in self.finished:raise QueryBlocked('Repetition already finalized (errors are not silently retried)')
        directory=self.path/scenario.id/('attempt-'+uuid.uuid4().hex)
        directory.mkdir(parents=True)
        write_json(directory/'started.json',{'scenario_id':scenario.id,'scenario':__import__('dataclasses').asdict(scenario),
                    'experiment_id':self.experiment['experiment_id'],'prior_incomplete_attempts':self.incomplete})
        return directory

    def commit(self,scenario,directory,result):
        if scenario.id in self.finished:raise QueryBlocked('Duplicate finalized repetition; no overwrite')
        from .matrix import PROFILES
        stamp=next((s['timestamp_epoch'] for s in result['stages'] if s['stage']=='measurement'),None)
        # When preparation fails, wall time is an attempt timestamp, not a claimed measurement start.
        if stamp is None:
            from decimal import Decimal
            import time
            stamp=str(Decimal(time.time_ns())/1000000000)
            result['timestamp_scope']='attempt finalization; measurement never started'
        else:result['timestamp_scope']='measurement boundary'
        row={'timestamp_epoch':stamp,'engine':scenario.engine,'profile':PROFILES[scenario.profile][0],
             'query_id':scenario.query,'concurrency':scenario.concurrency,'run_number':scenario.run_number,
             **{k:result['metrics'].get(k) for k in COLUMNS[6:10]},
             **{k:result['telemetry'].get(k) for k in COLUMNS[10:13]},'status':result['status']}
        result.update(experiment_id=self.experiment['experiment_id'],scenario_id=scenario.id,
                      variant=scenario.variant,csv_row_sha256=hashlib.sha256(csv_text(row).split('\n',1)[1].encode()).hexdigest())
        write_json(directory/'result.json',result);immutable_write(directory/'results.csv',csv_text(row))
        read_csv(directory/'results.csv')
        hashes={p.name:file_hash(p) for p in directory.iterdir() if p.is_file() and p.name!='commit.json'}
        write_json(directory/'commit.json',{'scenario_id':scenario.id,'files':hashes})
        self.finished[scenario.id]=directory
        return row


def consolidate(experiments,output,*,allow_nonfinal=False):
    """Consolidation requires all sidecars and preserves explicit variant-to-row mapping."""
    rows=[];mapping=[];seen=set();contexts=set();engine_identities={}
    for root in experiments:
        root=Path(root)
        with experiment_lock(root):
            config=parse_json((root/'experiment.json').read_text())['configuration']
            store=Store(root,config,resume=True)
            if store.unresolved_incomplete:raise QueryBlocked('Unresolved incomplete attempts present; no consolidation')
            expected={s['id'] for s in config.get('selection',{}).get('plan',[])}
            if expected and expected!=set(store.finished):raise QueryBlocked('Experiment plan is not fully finalized')
            contexts.add(digest({'dataset':config['dataset'],'sources':config['sources'],'protocol':config['protocol'],'evidence_kind':config['evidence_kind']}))
            for engine,identity in config['identities'].items():
                if engine in engine_identities and digest(identity)!=digest(engine_identities[engine]):raise QueryBlocked('Different versions/images for the same engine')
                engine_identities[engine]=identity
            for key,directory in sorted(store.finished.items()):
                meta=parse_json((directory/'result.json').read_text())
                if not meta['eligible_for_final_analysis'] and not allow_nonfinal:raise QueryBlocked('Pilot/test/incomplete telemetry rows are not final academic results')
                row=read_csv(directory/'results.csv')[0]
                canonical=csv_text(row).split('\n',1)[1];fingerprint=hashlib.sha256(canonical.encode()).hexdigest()
                if fingerprint in seen:raise QueryBlocked('Duplicate/ambiguous official CSV row: do not concatenate')
                seen.add(fingerprint);rows.append(row)
                mapping.append({'row':len(rows),'row_sha256':fingerprint,'variant':meta['variant'],
                    'scenario_id':key,'experiment_id':meta['experiment_id'],'eligible_for_final_analysis':meta['eligible_for_final_analysis']})
    if len(contexts)>1:raise QueryBlocked('Different datasets/protocols/query sources or pilot/definitive/test modes cannot be mixed')
    text=','.join(COLUMNS)+'\n'+''.join(csv_text(row).split('\n',1)[1] for row in rows)
    output=Path(output)
    if output.exists() or Path(str(output)+'.manifest.json').exists():raise QueryBlocked('Consolidation output exists')
    immutable_write(output,text)
    write_json(str(output)+'.manifest.json',{'row_mapping':mapping,'csv_sha256':file_hash(output),'nonfinal_allowed':allow_nonfinal,'identities':engine_identities})
