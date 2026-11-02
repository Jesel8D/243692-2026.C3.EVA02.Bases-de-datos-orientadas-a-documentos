"""SYNTHETIC SOFTWARE FIXTURES ONLY. All generated artifacts must remain temporary.
They are rejected by the public reporting CLI; they are not database measurements.
"""
from dataclasses import asdict
from decimal import Decimal as D
from pathlib import Path
from benchmark.results import Store,write_json
from benchmark.matrix import matrix,Scenario,PROFILES

DATA_HASH='f'*64

def make_store(root,plan,scope='definitive',suffix=''):
    protocol={'mode':scope,'warmup':60,'measurement':300,'cooldown':60,'timeout_ms':120000,'cache':'manual'}
    if scope=='pilot':protocol.update(warmup=1,measurement=4,cooldown=1,cache='skip')
    cfg={'evidence_kind':'simulated_reporting_test','fixture_warning':'SYNTHETIC TEST DATA ONLY, NEVER ACADEMIC RESULTS',
       'protocol':protocol,'dataset':{'count':500000 if scope=='definitive' else 100,'sha256':DATA_HASH,'configuration':{'fixture':True}},
       'runner_version':'unit-fixture','sources':{'fixture':'0'*64},'drivers':{'fixture':'unit'},'monitoring_configuration':{'fixture':True},'host':{'boot_id':'unit-fixture','os':{'ID':'unit'},'kernel':'unit'},
       'identities':{e:{'server_version':'SYNTHETIC','image':'SYNTHETIC','image_id':'SYNTHETIC'} for e in ('mongo','postgres')},
       'selection':{'matrix':'base' if len(plan)==108 else 'extended' if len(plan)==162 else 'single','base_Q2_selection':{'mongo':'allow_disk_false','postgres':'work_mem_4mb'},'plan':[{'id':s.id,**asdict(s)} for s in plan]}}
    return Store(Path(root)/('SYNTHETIC-UNIT-'+suffix),cfg)

def emit(store,s,*,bad=False,series=True):
    d=store.begin(s);profile,cpu,mem=PROFILES[s.profile];cfg=store.configuration;p=cfg['protocol'];count=cfg['dataset']['count']
    cid=('a' if s.engine=='mongo' else 'b')*64;start=61000000000;end=start+p['measurement']*10**9
    pre={'dataset':{'sha256':DATA_HASH},'deviations':[],'data_check':{'status':'ok','mode':'full','source_sha256':DATA_HASH,'count_by_engine':{'mongo':count,'postgres':count}},
      'query_check':{'status':'PASS'},'index_check':{'status':'PASS'},'telemetry_preflight':{'status':'PASS'},'resources_observed':{'id':cid,'label':profile,'cpu_max':f'{cpu*100000} 100000','memory_max':str(mem*1024**2),'swap_max':'0','health':'healthy'}}
    write_json(d/'preflight.json',pre)
    r=D(s.run_number);metric={'samples':int(p['measurement'])*s.run_number,'throughput_qps':r,'latency_p50_ms':r,'latency_p95_ms':r*2,'latency_p99_ms':r*3}
    telemetry={'cpu_throttled_seconds':r,'max_rss_mb':r,'disk_spill':False,'oom_killed':False}
    if bad:telemetry['max_rss_mb']=None
    effective={str(i):{'server_version':'SYNTHETIC','work_mem':'4MB' if s.variant=='work_mem_4mb' else '64MB','options':{'allowDiskUse':s.variant=='allow_disk_true'}} for i in range(s.concurrency)}
    result={'scenario':asdict(s),'protocol':p,'window_complete':True,'metrics':metric,'telemetry':telemetry,'missing_telemetry':['max_rss_mb'] if bad else [],'status':'error' if bad else 'ok',
      'evidence_kind':'simulated_reporting_test','eligible_for_final_analysis':p['mode']=='definitive' and not bad,'errors':[],'deviations':[],
      'clients_requested':s.concurrency,'clients_connected':s.concurrency,'clients_effective':effective,
      'cache':{'attested':True,'policy':p['cache']},'stages':[{'stage':'warmup','start_ns':start-p['warmup']*10**9,'end_ns':start},{'stage':'measurement','start_ns':start,'end_ns':end,'timestamp_epoch':'1000'},{'stage':'cooldown','start_ns':end,'end_ns':end+p['cooldown']*10**9}]}
    if series and not bad:
        points=[[D(1000+i),r*1000000] for i in range(int(p['measurement'])+1)]
        evidence={'window':{'start_epoch':D(1000),'end_epoch':D(1000+p['measurement']),'clock_invalid':False},
         'max_rss_mb':{'series':{'id':'/docker/'+cid},'samples':points},
         'cpu_throttled_seconds':{'series':{'id':'/docker/'+cid},'samples':[[D(1000),D(0)],[D(1000+p['measurement']),r]]}}
        # The raw counter also requires <=2.5s gaps.
        evidence['cpu_throttled_seconds']['samples']=[[D(1000+i),r*D(i)/p['measurement']] for i in range(int(p['measurement'])+1)]
        write_json(d/'telemetry-evidence.json',evidence)
    store.commit(s,d,result)
    return d

def plans(root):
    result=[]
    for engine,query,variant in [('mongo','Q1','default'),('mongo','Q2','allow_disk_false'),('postgres','Q1','default'),('postgres','Q2','work_mem_4mb')]:
        path=Path(root)/(engine+'-'+query+'-SYNTHETIC.json')
        plan=[{'Plan':{'Node Type':'Seq Scan','Actual Rows':1,'Temp Written Blocks':0}}] if engine=='postgres' else {'executionStats':{'stage':'COLLSCAN','totalDocsExamined':1}}
        write_json(path,{'evidence_kind':'simulated_reporting_test','engine':engine,'query':query,'variant':variant,'dataset_sha256':DATA_HASH,'dataset_binding':{'status':'ok','mode':'full','source_sha256':DATA_HASH},'preflight':{'count':500000},'effective':{'server_version':'SYNTHETIC'},'plan':plan,'source':'SYNTHETIC UNIT TEST ONLY'})
        result.append(path)
    return result
