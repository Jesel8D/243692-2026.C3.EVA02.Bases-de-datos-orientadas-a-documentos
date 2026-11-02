from dataclasses import dataclass,asdict
import hashlib,json
from decimal import Decimal
from src.dataset.model import json_text
from pathlib import Path
from queries.definitions import QueryBlocked


@dataclass(frozen=True)
class Protocol:
    mode: str
    warmup: float = 60
    measurement: float = 300
    cooldown: float = 60
    timeout_ms: int = 120000
    cache: str = 'skip'

    def __post_init__(self):
        if self.mode not in ('pilot','definitive','test'): raise QueryBlocked('Invalid execution mode')
        if any(type(x) not in (int,float) or not 0<=x<=3600 for x in (self.warmup,self.measurement,self.cooldown)) or self.measurement<=0:
            raise QueryBlocked('Invalid protocol durations')
        if self.mode=='definitive' and (self.warmup,self.measurement,self.cooldown)!=(60,300,60):
            raise QueryBlocked('Definitive protocol is exactly 60/300/60')
        if type(self.timeout_ms) is not int or not 1<=self.timeout_ms<=3600000: raise QueryBlocked('Invalid query timeout')
        if self.cache not in ('skip','manual'): raise QueryBlocked('Cache must be skip or manual; never automatic privileged commands')
        if self.mode=='definitive' and self.cache!='manual': raise QueryBlocked('Cache skip is not definitive-equivalent')


def plain(value):
    if type(value) is float:return Decimal(str(value))
    if isinstance(value,dict):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [plain(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json_text(plain(value),canonical=True).encode()).hexdigest()


def source_hashes():
    root=Path(__file__).resolve().parents[1]
    paths=[root/'queries/variants.json',root/'queries/native.py',root/'queries/execution.py',root/'requirements-benchmark.txt',root/'scripts/run_benchmarks.sh',root/'scripts/benchmark_environment.sh',*sorted((root/'benchmark').glob('*.py')),*sorted((root/'observability').glob('*.py')),*sorted((root/'config/monitoring').glob('*')),*sorted((root/'queries/mongodb').glob('q*.json')),*sorted((root/'queries/postgresql').glob('q*.sql'))]
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
