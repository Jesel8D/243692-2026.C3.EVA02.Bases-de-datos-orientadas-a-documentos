"""Local Docker metadata and reuse of Phase 1 scripts; no global/privileged changes."""
from pathlib import Path
import json,os,platform,subprocess,sys,sqlite3
from .matrix import PROFILES
from queries.definitions import QueryBlocked

ROOT=Path(__file__).resolve().parents[1]


def docker(*args):
    env=os.environ.copy()
    for k in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(k,None)
    result=subprocess.run(['docker','--host=unix:///var/run/docker.sock',*args],env=env,text=True,capture_output=True,timeout=60)
    if result.returncode:raise QueryBlocked('Local Docker command failed; diagnostic not dumped to avoid credentials')
    return result.stdout.strip()


def helper(action,profile,engine):
    result=subprocess.run(['bash',str(ROOT/'scripts/benchmark_environment.sh'),action,profile,engine],text=True,capture_output=True,timeout=360)
    if result.returncode:raise QueryBlocked('Infrastructure action failed: '+action+'; no volumes deleted')
    return result.stdout.strip()


def snapshot(engine,profile):
    raw=helper('snapshot',profile,engine)
    data=json.loads(raw)
    expected_id,cpus,mem=PROFILES[profile]
    expected={'quota':cpus*100000,'period':100000,'memory':mem*1024*1024,'swap':mem*1024*1024,'label':expected_id}
    if any(data[k]!=v for k,v in expected.items()) or data['cpu_max']!=f'{cpus*100000} 100000' or data['memory_max']!=str(mem*1024*1024) or data['swap_max']!='0':
        raise QueryBlocked('Actual inspect/cgroup resource limits differ from official requested profile')
    if not data['running'] or data['health']!='healthy':raise QueryBlocked('Engine not running/healthy')
    return data


def cgroup_path(pid):
    try:
        rel=next(l.split(':',2)[2] for l in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if l.startswith('0::'))
        p=(Path('/sys/fs/cgroup')/rel.lstrip('/')).resolve()
        if p.is_relative_to('/sys/fs/cgroup') and (p/'cpu.stat').exists():return p
    except (OSError,StopIteration):pass
    return None


def host_info():
    keys=('PRETTY_NAME','VERSION_ID','ID')
    distro={}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            k,v=line.split('=',1)
            if k in keys:distro[k]=v.strip('"')
    return {'os':distro,'kernel':platform.release(),'architecture':platform.machine(),
            'cpu_affinity_count':len(os.sched_getaffinity(0)),'cgroup_v2_visible':Path('/sys/fs/cgroup/cgroup.controllers').exists(),
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'cpu_model':next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),None),
            'memory_total_kib':int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))),
            'python':sys.version,'sqlite':sqlite3.sqlite_version}
