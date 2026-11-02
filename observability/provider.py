"""Prometheus plus actual engine evidence integrated into the existing runner lifecycle."""
from pathlib import Path
from decimal import Decimal
import json,os,time,uuid,shutil
from benchmark.telemetry import MissingTelemetry,CgroupTelemetry
from benchmark.environment import docker
from benchmark.results import write_json
from queries.definitions import QueryBlocked
from .config import settings
from .prometheus import Prometheus
from .series import CPU,RSS,CATALOG,select_container,selector,counter_delta,rss_max
from .identity import inspect_container,unchanged,host_identity,monitoring_containers
from .events import DockerStream,classify_oom
from .spill import MongoProfiler,postgres_spill

class ExperimentalTelemetry(MissingTelemetry):
    def __init__(self,path,context,config=None,api=None):
        self.config=config or settings();self.context=context;self.api=api or Prometheus(self.config['MONITORING_PROMETHEUS_URL'])
        self.direct=CgroupTelemetry(path);self.check=None;self.errors=[];self.streams=[];self.profiler=None
        self.token=uuid.uuid4().hex;self.clients={};self.window=None;self.clock_bad=False;self.offset_range=None
        self.enabled=self.config['MONITORING_SPILL_CAPTURE']=='true'
    def fingerprint(self):return {'settings':self.config,'source':'Prometheus raw in-window samples + actual engine instrumentation','rss_divisor':1000000}
    def probe(self):
        if self.check is not None:return self.check
        self.check={'status':'BLOCKED','errors':[],'catalog':{}}
        try:
            shot=self.context['snapshot'];self.identity=inspect_container(shot['id'])
            if self.identity['profile']!=shot['label'] or self.identity['image_id']!=shot['image_id']:raise QueryBlocked('Telemetry Docker identity differs from benchmark snapshot')
            self.check['identity']=self.identity
            self.check['monitoring_containers']=monitoring_containers(self.config['MONITORING_PROJECT_NAME'])
            containers=self.check['monitoring_containers']
            if self.context['protocol'].mode=='definitive':
                if set(containers)!=set(('prometheus','cadvisor','node-exporter')):raise QueryBlocked('Definitive requires the three identified Docker monitoring services; native/alternate test endpoint is pilot-only')
                if any(not c['pinned_image_matches'] or c['privileged'] or c['cap_add'] for c in containers.values()):raise QueryBlocked('Monitoring image/security configuration differs from pinned no-privilege design')
            self.check['targets']=self.api.targets()
            self.check['prometheus_build']=self.api.get('/api/v1/status/buildinfo')
            if self.check['prometheus_build'].get('version')!='3.15.1':raise QueryBlocked('Prometheus version differs from pinned release')
            self.check['exporter_builds']={}
            for metric,label,prefix in [('cadvisor_version_info','cadvisorVersion','v0.60.6'),('node_exporter_build_info','version','1.12.1')]:
                info=self.api.query(metric)
                rows=info.get('result',[])
                if info.get('resultType')!='vector' or len(rows)!=1 or rows[0]['metric'].get(label)!=prefix:raise QueryBlocked('Exporter version missing/different: '+metric)
                self.check['exporter_builds'][metric]=rows[0]['metric']
            flags=self.api.get('/api/v1/status/flags');self.check['retention_flags']={k:flags.get(k) for k in ('storage.tsdb.retention.time','storage.tsdb.retention.size')}
            from .config import duration_seconds,ROOT
            if duration_seconds(flags.get('storage.tsdb.retention.time',''))!=duration_seconds(self.config['MONITORING_RETENTION']) or flags.get('storage.tsdb.retention.size')!=self.config['MONITORING_RETENTION_SIZE']:raise QueryBlocked('Requested/effective Prometheus retention differs')
            if duration_seconds(flags.get('storage.tsdb.retention.time',''))<86400:raise QueryBlocked('Effective Prometheus retention is below 24h')
            if flags.get('storage.tsdb.retention.size')!='0B':self.check['errors'].append('Size retention may evict samples early; disable size cap for definitive study or document a verified capacity policy')
            _,head=self.api.raw('prometheus_tsdb_head_series{job="prometheus"}')
            free=shutil.disk_usage(ROOT).free
            storage_source='runner filesystem only; native test Prometheus, not proof of Docker TSDB capacity'
            if 'prometheus' in containers:
                mounts=containers['prometheus']['mounts']
                if not any(m['Destination']=='/prometheus' and m['Type']=='volume' and m['RW'] for m in mounts):raise QueryBlocked('Prometheus persistent writable TSDB volume not verified')
                disk=docker('exec',containers['prometheus']['id'],'/bin/df','-Pk','/prometheus')
                free=int(disk.splitlines()[-1].split()[3])*1024
                storage_source='df -Pk /prometheus inside identified Prometheus container'
            estimate=int(head[-1][1]*86400*Decimal('4.5'))
            self.check['storage']={'free_bytes':free,'filesystem_source':storage_source,'observed_head_series':head[-1][1],'screening_estimate_24h_bytes':estimate,'method':'1s scrape, 3 bytes/sample plus 50% margin; estimate, not guaranteed compression; verify Docker volume filesystem independently'}
            if self.context['protocol'].mode=='definitive' and free<max(int(self.config['MONITORING_MIN_FREE_MB'])*1024**2,estimate):raise QueryBlocked('Insufficient screening storage for 24h at observed cardinality; verify TSDB filesystem/capacity')
            before=Decimal(time.time_ns())/10**9
            clock=self.api.query('time()')
            after=Decimal(time.time_ns())/10**9
            if clock.get('resultType')!='scalar' or not before-Decimal('.1')<=Decimal(clock['result'][1])<=after+Decimal('.1'):
                raise QueryBlocked('Prometheus and runner epoch clocks disagree')
            data=self.api.query('container_last_seen{job="cadvisor"}')
            if data.get('resultType')!='vector':raise QueryBlocked('Missing cAdvisor container discovery')
            self.labels=select_container(data.get('result',[]),self.identity,now=Decimal(time.time_ns())/10**9)
            _,fresh=self.api.raw(selector('container_last_seen',self.labels))
            now=Decimal(time.time_ns())/10**9
            if not -Decimal('.1')<=now-fresh[-1][0]<=Decimal('2.5') or not -Decimal('.1')<=now-fresh[-1][1]<=Decimal('2.5'):raise QueryBlocked('Stale container discovery')
            for metric in CATALOG:
                try:
                    labels,samples=self.api.raw(selector(metric,self.labels))
                    if not -Decimal('.1')<=Decimal(time.time_ns())/10**9-samples[-1][0]<=Decimal('2.5'):raise QueryBlocked('Metric stale')
                    self.check['catalog'][metric]={'available':True,'labels':labels,'samples':len(samples),'last_epoch':samples[-1][0]}
                except QueryBlocked as exc:
                    self.check['catalog'][metric]={'available':False,'reason':str(exc)}
            for metric in (CPU,RSS):
                if not self.check['catalog'][metric]['available']:raise QueryBlocked('Required metric unavailable: '+metric+'; verify cAdvisor cgroups v2 support/permissions')
            host=host_identity();data=self.api.query('node_uname_info{job="node"}')
            rows=data.get('result',[])
            if data.get('resultType')!='vector' or len(rows)!=1:raise QueryBlocked('Node Exporter host identity missing/ambiguous')
            labels=rows[0]['metric'];self.check['host']={'runner':host,'exporter':labels}
            if labels.get('nodename')!=host['nodename'] or labels.get('release')!=host['kernel']:raise QueryBlocked('Node Exporter observes a different host/kernel/UTS namespace')
            _,boot=self.api.raw('node_boot_time_seconds{job="node"}')
            if abs(boot[-1][1]-host['boot_epoch'])>1:raise QueryBlocked('Host boot identity mismatch')
            for metric in ('node_memory_MemAvailable_bytes','node_vmstat_pswpin','node_vmstat_pswpout'):
                _,values=self.api.raw(metric+'{job="node"}')
                if not -Decimal('.1')<=Decimal(time.time_ns())/10**9-values[-1][0]<=Decimal('2.5'):raise QueryBlocked('Stale host metric: '+metric)
            self.check['host_diagnostics']={metric:self.api.query(metric+'{job="node"}') for metric in ('node_cpu_seconds_total','node_disk_read_bytes_total','node_disk_written_bytes_total','node_disk_reads_completed_total','node_disk_writes_completed_total')}
            logging=self.identity['log_config']
            self.log_compatible=logging.get('Type')=='json-file' and logging.get('Config',{}).get('mode','blocking')=='blocking'
            if not self.enabled:self.check['errors'].append('Engine spill capture disabled; explicitly set MONITORING_SPILL_CAPTURE=true after reading instrumentation overhead')
            elif self.identity['service']=='postgres' and not self.log_compatible:self.check['errors'].append('PG needs blocking json-file stderr logs for attributed spill')
            self.check['status']='PASS' if not self.check['errors'] else 'BLOCKED'
        except (QueryBlocked,OSError,ValueError,KeyError) as exc:
            self.check['errors'].append(str(exc) if isinstance(exc,QueryBlocked) else type(exc).__name__)
        return self.check
    def capabilities(self):
        check=self.probe();catalog=check.get('catalog',{})
        return {'cpu_throttled_seconds':catalog.get(CPU,{}).get('available',False),
                'max_rss_mb':catalog.get(RSS,{}).get('available',False),
                'disk_spill':check['status']=='PASS','oom_killed':'identity' in check and check.get('targets') is not None}
    def prepare(self,directory,factory):
        self.directory=Path(directory);self.probe()
        if not hasattr(self,'identity'):return
        try:
            events=DockerStream(self.identity['id'],self.directory/'docker-events.sqlite','events');events.start();self.streams.append(events);self.events=events
            if self.enabled and self.identity['service']=='postgres' and self.log_compatible:
                logs=DockerStream(self.identity['id'],self.directory/'engine-logs.sqlite','logs');logs.start();self.streams.append(logs);self.logs=logs
            if self.enabled and self.identity['service']=='mongodb':
                self.profiler=MongoProfiler(factory.connection,self.token);self.profiler.prepare(directory)
        except Exception as exc:self.errors.append('Evidence preparation: '+type(exc).__name__)
    def configure_client(self,session,client_id):
        if self.enabled and hasattr(self,'identity'):
            ready=(self.identity['service']=='postgres' and hasattr(self,'logs') and self.logs.failure is None) or (self.profiler and self.profiler.active)
            if ready:
                session.enable_spill_capture(self.token,client_id)
                if self.profiler:
                    # Original query, untimed canary, never attributed to the measurement window.
                    tag=session.set_observation('probe',0);session.execute()
                    time.sleep(.02)
                    record=self.profiler.db['system.profile'].find_one({'command.comment.benchmark_token':self.token,'command.comment.tag':tag,'command.aggregate':'orders'},{'usedDisk':1})
                    if record is None or ('usedDisk' in record and type(record['usedDisk']) is not bool):
                        session.effective.update(spill_capture=False,spill_reason='Profiler canary lacks explicit usedDisk; absence is unknown')
    def clients_ready(self,effective):
        self.clients=effective
        if self.context['protocol'].mode=='definitive':
            if not self.enabled or not effective or any(not v.get('spill_capture') for v in effective.values()) or self.errors or any(s.failure for s in self.streams):
                raise QueryBlocked('Telemetry/spill not ready in actual client sessions; no warmup/measurement starts')
    def start(self):self.direct.start()
    def set_window(self,start,end,epoch_ns):
        self.window=(start,end);self.epoch_start_ns=epoch_ns;self.offset_ns=epoch_ns-start
        self.offset_range=[self.offset_ns,self.offset_ns];self.clock_checks=0
    def sample(self):
        if self.window is None:return
        a=time.monotonic_ns();wall=time.time_ns();b=time.monotonic_ns()
        offset=wall-(a+b)//2;self.clock_checks+=1
        self.offset_range=[min(self.offset_range[0],offset),max(self.offset_range[1],offset)]
        if abs(offset-self.offset_ns)>100000000 or b-a>10000000:self.clock_bad=True
    def stop(self):
        self.sample();self.direct_result=self.direct.stop()
        return self.unavailable('Awaiting raw Prometheus window and engine evidence finalization')
    def finish(self,directory,window,effective):
        result=self.unavailable('Required measurement unavailable');evidence={'probe':self.check,'errors':self.errors}
        try:
            # Allow logs already emitted to drain; this runs after measured work and cooldown.
            time.sleep(.2)
            coverage={}
            for stream in self.streams:coverage[stream.kind]=stream.stop()
            self.streams=[];evidence['streams']=coverage
            if self.window is None or window is None:raise QueryBlocked('Measurement never started')
            self.sample()
            start=Decimal(self.epoch_start_ns)/10**9;end=start+Decimal(window[1]-window[0])/10**9
            evidence['window']={'monotonic_ns':window,'start_epoch':start,'end_epoch':end,'offset_ns':self.offset_ns,'offset_range_ns':self.offset_range,'clock_checks':self.clock_checks,'clock_invalid':self.clock_bad}
            if not hasattr(self,'identity'):raise QueryBlocked('No verified Docker identity; telemetry cannot be attributed')
            after=inspect_container(self.identity['id'],require_running=False);stable=unchanged(self.identity,after);evidence['identity_after']=after
            if hasattr(self,'events'):
                continuous=coverage.get('events',{}).get('continuous',False) and self.events.start_epoch_ns<=self.epoch_start_ns and self.events.end_epoch_ns>=int(end*10**9)
                result['oom_killed'],evidence['oom']=classify_oom(self.events.rows(),int(start*10**9),int(end*10**9),continuous,stable)
            if not stable:raise QueryBlocked('Container restarted/recreated/stopped during attempt')
            if self.clock_bad:raise QueryBlocked('Clock mapping changed or uncertainty exceeded 100ms')
            self.api.targets()
            if not hasattr(self,'labels'):raise QueryBlocked('No verified container series; measurement cannot be attributed')
            for metric,key,compute in ((CPU,'cpu_throttled_seconds',counter_delta),(RSS,'max_rss_mb',rss_max)):
                try:
                    labels,samples=self.api.raw(selector(metric,self.labels),float(end-start+6),end+3)
                    value,details=compute(samples,start,end);result[key]=value
                    evidence[key]={'method':details,'series':labels,'samples':samples}
                except QueryBlocked as exc:self.errors.append(str(exc))
            if hasattr(self,'events'):
                continuous=coverage.get('events',{}).get('continuous',False) and self.events.start_epoch_ns<=self.epoch_start_ns and self.events.end_epoch_ns>=int(end*10**9)
                result['oom_killed'],evidence['oom']=classify_oom(self.events.rows(),int(start*10**9),int(end*10**9),continuous,stable)
            if self.profiler and self.profiler.active:
                result['disk_spill'],evidence['spill']=self.profiler.collect(directory,window)
            elif hasattr(self,'logs'):
                result['disk_spill'],evidence['spill']=postgres_spill(self.logs.rows(),directory,effective,window,self.offset_ns,coverage.get('logs',{}).get('continuous',False))
            else:evidence['spill']={'state':'insufficient','reason':'No enabled, prepared actual-engine spill mechanism'}
            evidence['cgroup_contrast']=getattr(self,'direct_result',None)
            result['source']='Prometheus/cAdvisor raw observed window; actual engine records; Docker events'
        except (QueryBlocked,OSError,ValueError,KeyError) as exc:
            self.errors.append(str(exc) if isinstance(exc,QueryBlocked) else type(exc).__name__)
        finally:
            try:self.cleanup()
            except Exception as exc:self.errors.append('Instrumentation restoration failed: '+type(exc).__name__)
            evidence['errors']=self.errors;evidence['prometheus_api']=self.api.requests
            write_json(Path(directory)/'telemetry-evidence.json',evidence)
        result.update(evidence_file='telemetry-evidence.json',errors=self.errors)
        # A collection/integrity error makes the repetition ineligible even if some fields survived.
        if self.errors:result['integrity_error']=True
        return result
    def cleanup(self):
        for stream in self.streams:stream.stop()
        self.streams=[]
        if self.profiler:self.profiler.close()
