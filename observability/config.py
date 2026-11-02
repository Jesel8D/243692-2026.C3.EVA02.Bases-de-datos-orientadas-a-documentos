"""Non-secret, strictly parsed local settings; no shell evaluation."""
from pathlib import Path
from urllib.parse import urlsplit
import os,re,ipaddress
from queries.definitions import QueryBlocked
ROOT=Path(__file__).resolve().parents[1]
DEFAULTS={'MONITORING_PROJECT_NAME':'jsonbench-monitoring','MONITORING_PROMETHEUS_URL':'http://127.0.0.1:19090',
 'MONITORING_PORT':'19090','MONITORING_RETENTION':'7d','MONITORING_RETENTION_SIZE':'0B',
 'MONITORING_MIN_FREE_MB':'1024','MONITORING_ACCEPT_HOST_ACCESS':'false','MONITORING_SPILL_CAPTURE':'false',
 'MONITORING_DOCKER_ROOT':'/var/lib/docker'}
IMAGES={
 'prometheus':'prom/prometheus:v3.15.1@sha256:fa3302279710be2f21a8301ec17a8b4f2301fd829bd113839b3b6b02b6f191a2',
 'node-exporter':'prom/node-exporter:v1.12.1@sha256:1b4e4438faca4dd7e001dd445d161a4a2091b0fededa84093b3a8dfeae1f1be0',
 'cadvisor':'ghcr.io/google/cadvisor:0.60.6@sha256:b8e7d1093144fd088f425ff003d75a4aa405de075db78dae3bc563730b1bd07a'}

def local_url(url):
    p=urlsplit(url)
    if p.scheme!='http' or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
        raise QueryBlocked('Prometheus URL must be local HTTP without credentials/path/query')
    try:
        ip=ipaddress.ip_address(p.hostname)
        if not (ip.is_loopback or ip.is_private) or ip.is_unspecified:raise ValueError()
        if not p.port or not 1<=p.port<=65535:raise ValueError()
    except (ValueError,TypeError):raise QueryBlocked('Use an explicit loopback/private IP and port for local Prometheus')
    return url.rstrip('/')

def duration_seconds(value):
    parts=re.findall(r'([0-9]+)(ms|s|m|h|d|w|y)',value)
    if not parts or ''.join(n+u for n,u in parts)!=value:raise QueryBlocked('Invalid Prometheus duration')
    factors={'ms':0.001,'s':1,'m':60,'h':3600,'d':86400,'w':604800,'y':31536000}
    return sum(int(n)*factors[u] for n,u in parts)

def settings():
    values=dict(DEFAULTS)
    file=Path(os.environ.get('MONITORING_ENV_FILE',ROOT/'.env.monitoring'))
    if file.exists():
        for line in file.read_text().splitlines():
            if not line or line.startswith('#'):continue
            key,sep,value=line.partition('=')
            if sep!='=' or key not in DEFAULTS or not re.fullmatch(r'[a-zA-Z0-9_./:@%+=,!~-]*',value):
                raise QueryBlocked('Invalid monitoring configuration; use KEY=value without shell expressions')
            values[key]=value
    values.update({k:os.environ[k] for k in DEFAULTS if k in os.environ})
    for key in ('MONITORING_ACCEPT_HOST_ACCESS','MONITORING_SPILL_CAPTURE'):
        if values[key] not in ('true','false'):raise QueryBlocked('Monitoring boolean must be true/false')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',values['MONITORING_PROJECT_NAME']):raise QueryBlocked('Invalid monitoring project')
    for key in ('MONITORING_PORT','MONITORING_MIN_FREE_MB'):
        if not re.fullmatch('[1-9][0-9]*',values[key]):raise QueryBlocked('Invalid monitoring numeric setting')
    if int(values['MONITORING_PORT'])>65535:raise QueryBlocked('Invalid monitoring port')
    m=re.fullmatch(r'([1-9][0-9]*)(h|d)',values['MONITORING_RETENTION'])
    if not m or int(m[1])*(24 if m[2]=='d' else 1)<24:raise QueryBlocked('Retention must be at least 24h (experiment may exceed 18h54)')
    if not re.fullmatch(r'0B|[1-9][0-9]*(MB|GB)',values['MONITORING_RETENTION_SIZE']):raise QueryBlocked('Invalid retention size')
    if not re.fullmatch(r'/[a-zA-Z0-9_./-]+',values['MONITORING_DOCKER_ROOT']):raise QueryBlocked('Invalid Docker root path')
    if '..' in Path(values['MONITORING_DOCKER_ROOT']).parts:raise QueryBlocked('Docker root cannot contain traversal')
    local_url(values['MONITORING_PROMETHEUS_URL'])
    return values

if __name__=='__main__':
    for k,v in settings().items():print(k+'='+v)
