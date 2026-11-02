"""Only selected non-sensitive Docker metadata; never inspect.Env."""
import json,re,platform
from benchmark.environment import docker
from benchmark.matrix import PROFILES
from queries.definitions import QueryBlocked

def inspect_container(cid,require_running=True):
    if not re.fullmatch('[a-f0-9]{64}',cid):raise QueryBlocked('Use full Docker container ID')
    fmt='{"id":{{json .Id}},"image":{{json .Config.Image}},"image_id":{{json .Image}},"started_at":{{json .State.StartedAt}},"restart_count":{{.RestartCount}},"running":{{.State.Running}},"oom_killed":{{.State.OOMKilled}},"pid":{{.State.Pid}},"labels":{{json .Config.Labels}},"log_config":{{json .HostConfig.LogConfig}},"quota":{{.HostConfig.CpuQuota}},"period":{{.HostConfig.CpuPeriod}},"memory":{{.HostConfig.Memory}}}'
    data=json.loads(docker('inspect','--format',fmt,cid))
    labels=data.pop('labels') or {}
    data.update(project=labels.get('com.docker.compose.project'),service=labels.get('com.docker.compose.service'),profile=labels.get('academic.profile'))
    if data['service'] not in ('mongodb','postgres') or not data['project'] or data['profile'] not in {v[0] for v in PROFILES.values()}:
        raise QueryBlocked('Container is not an identified experimental Compose engine')
    official=next(v for v in PROFILES.values() if v[0]==data['profile'])
    if (require_running and not data['running']) or data['quota']!=official[1]*100000 or data['period']!=100000 or data['memory']!=official[2]*1024**2:
        raise QueryBlocked('Container is stopped or effective Docker resources differ from profile')
    return data

def unchanged(before,after):
    return all(before[k]==after[k] for k in ('id','image_id','started_at','restart_count','profile','quota','period','memory')) and after['running']

def host_identity():
    from pathlib import Path
    boot=next(int(l.split()[1]) for l in Path('/proc/stat').read_text().splitlines() if l.startswith('btime '))
    return {'nodename':platform.node(),'kernel':platform.release(),'boot_epoch':boot,'scope':'Linux observed by runner; Cloud may be nested'}


def monitoring_containers(project):
    from .config import IMAGES
    found={}
    for service,image in IMAGES.items():
        ids=docker('ps','--no-trunc','--filter','label=com.docker.compose.project='+project,'--filter','label=com.docker.compose.service='+service,'--format','{{.ID}}').splitlines()
        if not ids:continue
        if len(ids)!=1:raise QueryBlocked('Ambiguous monitoring service: '+service)
        fmt='{"id":{{json .Id}},"image":{{json .Config.Image}},"image_id":{{json .Image}},"started_at":{{json .State.StartedAt}},"restart_count":{{.RestartCount}},"privileged":{{.HostConfig.Privileged}},"read_only":{{.HostConfig.ReadonlyRootfs}},"cap_add":{{json .HostConfig.CapAdd}},"cap_drop":{{json .HostConfig.CapDrop}},"cgroup_namespace":{{json .HostConfig.CgroupnsMode}},"uts":{{json .HostConfig.UTSMode}},"mounts":{{json .Mounts}},"ports":{{json .HostConfig.PortBindings}}}'
        data=json.loads(docker('inspect','--format',fmt,ids[0]));data['pinned_image_matches']=data['image']==image
        found[service]=data
    return found
