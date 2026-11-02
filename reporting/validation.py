"""Independent eligibility and data/metadata consistency checks for reporting."""
from decimal import Decimal
import hashlib
from benchmark.config import digest
from benchmark.results import COLUMNS,csv_text
from benchmark.matrix import PROFILES
from queries.definitions import QueryBlocked
from observability.series import has_id,rss_max,counter_delta


def validate_record(record,started,config,scope,synthetic=False):
    s,row,meta=record.scenario,record.row,record.meta
    expected={'engine':s.engine,'profile':PROFILES[s.profile][0],'query_id':s.query,'concurrency':str(s.concurrency),'run_number':str(s.run_number)}
    if any(row[k]!=v for k,v in expected.items()):raise QueryBlocked('CSV vs scenario mismatch')
    if started.get('experiment_id')!=record.experiment_id or meta.get('experiment_id')!=record.experiment_id or meta.get('scenario_id')!=s.id or started.get('scenario_id')!=s.id:raise QueryBlocked('Experiment/scenario identity mismatch')
    from dataclasses import asdict
    if meta.get('scenario')!=asdict(s) or started.get('scenario')!=asdict(s) or meta.get('variant')!=s.variant:raise QueryBlocked('Variant/scenario metadata mismatch')
    if digest(meta.get('protocol'))!=digest(config['protocol']):raise QueryBlocked('Protocol differs from experiment manifest')
    if meta.get('evidence_kind')!=config.get('evidence_kind') or row['status']!=meta.get('status'):raise QueryBlocked('Status/provenance mismatch')
    fingerprint=hashlib.sha256(csv_text(row).split('\n',1)[1].encode()).hexdigest()
    if meta.get('csv_row_sha256')!=fingerprint:raise QueryBlocked('CSV row fingerprint mismatch')
    for key in COLUMNS[6:10]:
        actual=meta.get('metrics',{}).get(key)
        if (row[key]=='')!=(actual is None) or row[key] and Decimal(row[key])!=actual:raise QueryBlocked('CSV metric differs from result metadata: '+key)
    for key in COLUMNS[10:13]:
        actual=meta.get('telemetry',{}).get(key)
        if (row[key]=='')!=(actual is None) or row[key] and Decimal(row[key])!=actual:raise QueryBlocked('Resource metric differs from result metadata: '+key)
    reasons=[]
    if row['status'] not in ('ok','spill'):reasons.append('failed status: '+row['status'])
    if not meta.get('window_complete') or meta.get('metrics',{}).get('samples',0)<=0:reasons.append('no complete measured window/samples')
    if meta.get('errors') or meta.get('missing_telemetry') or meta.get('telemetry',{}).get('integrity_error') or meta.get('telemetry',{}).get('errors'):reasons.append('measurement/telemetry errors or missing indicators')
    if any(not row[k] for k in COLUMNS[6:13]) or type(meta.get('telemetry',{}).get('oom_killed')) is not bool:reasons.append('mandatory measurement absent')
    if meta.get('telemetry',{}).get('oom_killed') is True:reasons.append('OOM: not a successful performance repetition')
    clients=meta.get('clients_effective',{})
    if meta.get('clients_requested')!=s.concurrency or meta.get('clients_connected')!=s.concurrency or len(clients)!=s.concurrency:reasons.append('requested/effective client count mismatch')
    if s.query=='Q2':
        if s.engine=='postgres' and any(c.get('work_mem')!=('4MB' if s.variant=='work_mem_4mb' else '64MB') for c in clients.values()):reasons.append('effective work_mem differs from selected variant')
        if s.engine=='mongo' and any(c.get('options',{}).get('allowDiskUse') is not (s.variant=='allow_disk_true') for c in clients.values()):reasons.append('aggregate allowDiskUse differs from variant')
    stages=[v for v in meta.get('stages',[]) if v.get('stage')=='measurement']
    if len(stages)!=1:reasons.append('measurement boundary not documented')
    elif stages[0]['end_ns']-stages[0]['start_ns']!=Decimal(str(config['protocol']['measurement']))*10**9:reasons.append('measurement duration does not match configured protocol')
    elif meta.get('window_complete') and row['throughput_qps'] and Decimal(row['throughput_qps'])!=Decimal(meta['metrics']['samples'])*10**9/Decimal(stages[0]['end_ns']-stages[0]['start_ns']):reasons.append('QPS inconsistent with included sample count/window')
    elif Decimal(row['timestamp_epoch'])!=Decimal(stages[0]['timestamp_epoch']):raise QueryBlocked('CSV timestamp vs measurement boundary mismatch')
    if scope=='definitive':
        p=config['protocol'];data=config.get('dataset',{});pre=record.preflight
        for phase in ('warmup','cooldown'):
            traces=[t for t in meta.get('stages',[]) if t.get('stage')==phase]
            if len(traces)!=1 or traces[0].get('end_ns',0)-traces[0].get('start_ns',0)!=Decimal(str(p[phase]))*10**9:reasons.append('actual '+phase+' interval not documented/mismatched')
        if (p.get('warmup'),p.get('measurement'),p.get('cooldown'),p.get('cache'))!=(60,300,60,'manual'):reasons.append('definitive protocol differs from 60/300/60/manual')
        if data.get('count')!=500000:reasons.append('definitive dataset is not 500000')
        if not meta.get('eligible_for_final_analysis') or meta.get('deviations'):reasons.append('runner did not certify final eligibility/deviations exist')
        if not meta.get('cache',{}).get('attested'):reasons.append('cache attestation missing (operator attestation is not kernel proof)')
        if pre.get('deviations') or pre.get('query_check',{}).get('status')!='PASS' or pre.get('index_check',{}).get('status')!='PASS' or pre.get('telemetry_preflight',{}).get('status')!='PASS':reasons.append('preflight correctness/indices/telemetry incomplete')
        check=pre.get('data_check',{})
        if check.get('status')!='ok' or check.get('mode')!='full' or check.get('count_by_engine')!={'mongo':500000,'postgres':500000} or check.get('source_sha256')!=data.get('sha256'):reasons.append('full cross-engine dataset equivalence not certified')
        shot=pre.get('resources_observed',{});_,cpu,mem=PROFILES[s.profile]
        if shot.get('label')!=PROFILES[s.profile][0] or shot.get('cpu_max')!=f'{cpu*100000} 100000' or shot.get('memory_max')!=str(mem*1024**2) or shot.get('swap_max')!='0' or shot.get('health')!='healthy':reasons.append('effective profile not certified')
        if pre.get('dataset',{}).get('sha256')!=data.get('sha256'):reasons.append('preflight dataset hash differs')
    if record.evidence:
        window=record.evidence.get('window',{})
        if window.get('clock_invalid'):reasons.append('telemetry clock mapping invalid')
        for key,compute in [('cpu_throttled_seconds',counter_delta),('max_rss_mb',rss_max)]:
            values=record.evidence.get(key)
            if not values:continue
            try:
                samples=values['samples'];start,end=window['start_epoch'],window['end_epoch']
                cid=record.preflight.get('resources_observed',{}).get('id')
                if cid and not has_id(values['series']['id'],cid):raise QueryBlocked('Series belongs to another container')
                observed,_=compute(samples,start,end)
                if not row[key] or observed!=Decimal(row[key]):raise QueryBlocked('CSV vs original telemetry samples mismatch')
                if key=='max_rss_mb':record.rss=[(t-start,v/Decimal(1000000)) for t,v in samples if start<=t<=end]
            except (QueryBlocked,KeyError,ValueError,TypeError) as exc:reasons.append('unverified '+key+': '+str(exc))
    record.reasons=reasons;record.valid=not reasons
