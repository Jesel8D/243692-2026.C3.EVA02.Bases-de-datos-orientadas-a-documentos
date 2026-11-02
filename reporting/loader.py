"""Read a consistent cut of immutable commits without taking the runner's lock."""
from dataclasses import dataclass,field
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
import hashlib,re
from benchmark.results import file_hash,read_csv,COLUMNS,csv_text
from benchmark.matrix import Scenario,PROFILES
from benchmark.config import digest
from src.dataset.model import parse_json
from queries.definitions import QueryBlocked

@dataclass
class Record:
    experiment_id:str
    cohort:str
    scenario:Scenario
    row:dict
    meta:dict
    preflight:dict
    evidence:dict
    path:str
    valid:bool=False
    reasons:list=field(default_factory=list)
    rss:list=field(default_factory=list)

@dataclass
class Snapshot:
    scope:str
    experiments:list=field(default_factory=list)
    records:list=field(default_factory=list)
    invalid:list=field(default_factory=list)
    unfinished:list=field(default_factory=list)
    files:dict=field(default_factory=dict)
    captured_at:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
    test_only:bool=False
    integrity:str='selected'

    def remember(self,path,data):
        key=str(Path(path).resolve());sha=hashlib.sha256(data).hexdigest()
        if key in self.files and self.files[key]['sha256']!=sha:raise QueryBlocked('Input changed during snapshot: '+key)
        self.files[key]={'sha256':sha,'bytes':data}
        return data


def resolve_roots(inputs):
    roots=[]
    for name in inputs:
        p=Path(name).resolve()
        if p.is_file() and p.suffix=='.csv':
            p=next((x for x in p.parents if (x/'experiment.json').is_file()),None)
            if p is None:raise QueryBlocked('CSV lacks experimental provenance. Use its complete experiment directory; validate --csv checks schema only.')
        if p is None or not p.is_dir():raise QueryBlocked('Missing experiment input: '+str(name))
        found=[p] if (p/'experiment.json').is_file() else sorted(x for x in p.iterdir() if x.is_dir() and (x/'experiment.json').is_file())
        if not found:raise QueryBlocked('No experiment.json in input/direct children: '+str(name))
        roots.extend(found)
    if len(roots)!=len(set(roots)):raise QueryBlocked('Duplicate experiment directory/CSV input')
    return roots


def cohort_key(config):
    # Engine-specific image identities are checked separately. Never average different sources/hosts/datasets.
    keys=('dataset','protocol','sources','drivers','monitoring_configuration','host','runner_version','evidence_kind')
    values={k:config.get(k) for k in keys}
    selection=config.get('selection',{})
    values['matrix_policy']={'family':selection.get('matrix'),'base_q2':selection.get('base_Q2_selection') if selection.get('matrix')=='base' else None}
    return digest(values)[:16]


def read_stable(snapshot,path,expected=None):
    path=Path(path)
    if path.is_symlink():raise QueryBlocked('Symlink evidence is not accepted')
    before=path.stat();data=path.read_bytes();after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise QueryBlocked('Evidence changed during read')
    if expected and hashlib.sha256(data).hexdigest()!=expected:raise QueryBlocked('Evidence hash mismatch: '+path.name)
    return snapshot.remember(path,data)


def load(inputs,scope='definitive',verify_all=False,_testing=False):
    if scope not in ('definitive','pilot'):raise QueryBlocked('Reporting scope must be definitive or pilot')
    snapshot=Snapshot(scope=scope,integrity='all' if verify_all else 'selected')
    experiment_ids=set();keys=set();identities={}
    for root in resolve_roots(inputs):
        manifest=parse_json(read_stable(snapshot,root/'experiment.json').decode())
        config=manifest['configuration'];eid=manifest['experiment_id']
        dataset=config.get('dataset',{})
        if not re.fullmatch('[a-f0-9]{64}',str(dataset.get('sha256',''))) or type(dataset.get('count')) is not int or dataset['count']<=0:raise QueryBlocked('Dataset identity/count missing or invalid; cannot establish comparison provenance')
        if eid in experiment_ids:raise QueryBlocked('Duplicate experiment UUID, including copied results')
        experiment_ids.add(eid)
        kind=config.get('evidence_kind')
        synthetic=kind=='simulated_reporting_test'
        if synthetic and not _testing:raise QueryBlocked('Synthetic reporting fixtures forbidden in public CLI')
        if kind not in ('real_native_driver','simulated_reporting_test'):raise QueryBlocked('Unknown/unverified measurement provenance')
        if config.get('protocol',{}).get('mode')!=scope:raise QueryBlocked('Pilot/definitive scope mismatch; choose inputs explicitly, never mix')
        snapshot.test_only|=synthetic
        cohort=cohort_key(config)
        for engine,identity in config.get('identities',{}).items():
            key=(cohort,engine)
            if key in identities and identities[key]!=identity:raise QueryBlocked('Different engine versions/images in same comparison cohort; generate separate reports')
            identities[key]=identity
        plan={}
        for item in config['selection']['plan']:
            scenario=Scenario(**{k:item[k] for k in ('engine','profile','query','variant','concurrency','run_number')})
            if item['id']!=scenario.id or scenario.id in plan:raise QueryBlocked('Corrupt/duplicate planned scenario ID')
            plan[scenario.id]=scenario
        snapshot.experiments.append({'id':eid,'root':str(root),'cohort':cohort,'manifest':manifest,'plan':plan})
        # Freeze the commit list BEFORE reading started markers; concurrent new commits appear next time.
        commits=sorted(root.glob('*/attempt-*/commit.json'))
        finalized=set()
        for commit in commits:
            directory=commit.parent;sid=directory.parent.name
            key=(cohort,sid)
            if key in keys:raise QueryBlocked('Duplicate scenario/repetition across attempts or experiments; select the authoritative input explicitly')
            keys.add(key);finalized.add(sid)
            if sid not in plan:raise QueryBlocked('Committed scenario not in experiment plan')
            try:
                marker=parse_json(read_stable(snapshot,commit).decode())
                hashes=marker.get('files',{})
                if marker.get('scenario_id')!=sid or not {'started.json','result.json','results.csv'}<=set(hashes):raise QueryBlocked('Incomplete commit marker')
                for name,sha in hashes.items():
                    if Path(name).name!=name or name.startswith('.') or not re.fullmatch('[a-f0-9]{64}',sha):raise QueryBlocked('Invalid commit path/hash')
                    file=directory/name
                    if not file.is_file() or file.is_symlink():raise QueryBlocked('Missing/unsafe committed artifact: '+name)
                    if verify_all:
                        if file_hash(file)!=sha:raise QueryBlocked('Full audit hash mismatch: '+name)
                    # Report needs metadata/evidence, not unbounded operation SQLite files.
                    if file.suffix in ('.json','.csv'):read_stable(snapshot,file,sha)
                def obj(name):return parse_json(snapshot.files[str((directory/name).resolve())]['bytes'].decode())
                meta=obj('result.json');started=obj('started.json')
                rows=read_csv(directory/'results.csv')
                if len(rows)!=1:raise QueryBlocked('One CSV row per committed repetition required')
                # read_csv reuses official parser; compare a second read with frozen bytes for a race.
                if (directory/'results.csv').read_bytes()!=snapshot.files[str((directory/'results.csv').resolve())]['bytes']:raise QueryBlocked('CSV changed during official parsing')
                from .validation import validate_record
                record=Record(eid,cohort,plan[sid],rows[0],meta,obj('preflight.json') if 'preflight.json' in hashes else {},obj('telemetry-evidence.json') if 'telemetry-evidence.json' in hashes else {},str(directory))
                validate_record(record,started,config,scope,synthetic)
                snapshot.records.append(record)
            except (QueryBlocked,OSError,ValueError,TypeError,KeyError) as exc:
                snapshot.invalid.append({'experiment_id':eid,'cohort':cohort,'scenario_id':sid,'path':str(directory),'reason':str(exc) if isinstance(exc,QueryBlocked) else type(exc).__name__})
        for started in sorted(root.glob('*/attempt-*/started.json')):
            sid=started.parent.parent.name
            if sid not in finalized:
                # Started metadata is immutable; never touch a partial CSV or take .lock.
                try:
                    item=parse_json(read_stable(snapshot,started).decode())
                    if sid not in plan or item.get('scenario_id')!=sid:raise QueryBlocked('Unconfirmed attempt has inconsistent identity')
                    snapshot.unfinished.append({'experiment_id':eid,'cohort':cohort,'scenario_id':sid,'scenario':item['scenario'],'path':str(started.parent),'started_epoch':Decimal(str(started.stat().st_mtime)),
                        'state':'started without commit at snapshot cut: active OR interrupted, not established'})
                except (OSError,ValueError,KeyError,QueryBlocked) as exc:
                    snapshot.unfinished.append({'experiment_id':eid,'cohort':cohort,'scenario_id':sid,'path':str(started.parent),'state':'unconfirmed/corrupt started marker: '+type(exc).__name__})
        # Detect illicit mutation of the experiment metadata; no read lock needed for immutable protocol.
        if (root/'experiment.json').read_bytes()!=snapshot.files[str((root/'experiment.json').resolve())]['bytes']:raise QueryBlocked('Experiment manifest mutated during snapshot')
    return snapshot
