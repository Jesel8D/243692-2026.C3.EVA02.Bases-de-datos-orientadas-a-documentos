"""Limited direct cgroups v2 adapter. RSS/spill absent until Phase 5, never substituted."""
from pathlib import Path
import time


class MissingTelemetry:
    def capabilities(self): return {k:False for k in ('cpu_throttled_seconds','max_rss_mb','disk_spill','oom_killed')}
    def start(self):pass
    def sample(self):pass
    def unavailable(self,reason):
        return {'cpu_throttled_seconds':None,'max_rss_mb':None,'disk_spill':None,'oom_killed':None,'reason':reason}
    def stop(self):return self.unavailable('Phase 5 providers required for exact RSS/spill')


class CgroupTelemetry(MissingTelemetry):
    def __init__(self,path):
        self.path=Path(path) if path else None;self.samples=[];self.before=None;self.failure=None
    def capabilities(self):
        usable=self.path is not None and (self.path/'cpu.stat').is_file()
        return {'cpu_throttled_seconds':usable,'max_rss_mb':False,'disk_spill':False,
                'oom_killed':usable and (self.path/'memory.events').is_file()}
    def read(self):
        if self.path is None:raise OSError('cgroup path unavailable')
        def fields(name):
            return {k:int(v) for k,v in (line.split() for line in (self.path/name).read_text().splitlines())}
        return {'monotonic_ns':time.monotonic_ns(),'cpu':fields('cpu.stat'),'memory_events':fields('memory.events')}
    def start(self):
        try:self.before=self.read()
        except OSError:self.failure='No direct cgroup path/read permission'
    def sample(self):
        # Two boundary snapshots only; no fake RSS from memory.current/anon/working set.
        pass
    def stop(self):
        result=self.unavailable(self.failure or 'Exact RSS and spill not implemented; Phase 5 pending')
        if self.before is None:return result
        try:
            after=self.read();delta=after['cpu']['throttled_usec']-self.before['cpu']['throttled_usec']
            oom=after['memory_events']['oom_kill']-self.before['memory_events']['oom_kill']
            if delta<0 or oom<0:raise ValueError('counter reset')
            from decimal import Decimal
            result.update(cpu_throttled_seconds=Decimal(delta)/1000000,oom_killed=oom>0,
                          snapshots=[self.before,after],source='cgroups v2 throttled_usec delta / 1e6; memory.events oom_kill delta')
        except (OSError,KeyError,ValueError): result['reason']='Counter reset/missing: no valid delta'
        return result


def make_telemetry(cgroup_path=None,context=None):
    """Single provider wiring point for Phase 5; no optional metrics invented today."""
    import os
    from observability.config import ROOT,settings
    if context is not None and (os.environ.get('MONITORING_PROMETHEUS_URL') or Path(os.environ.get('MONITORING_ENV_FILE',ROOT/'.env.monitoring')).exists()):
        from observability.provider import ExperimentalTelemetry
        return ExperimentalTelemetry(cgroup_path,context,settings())
    return CgroupTelemetry(cgroup_path)
