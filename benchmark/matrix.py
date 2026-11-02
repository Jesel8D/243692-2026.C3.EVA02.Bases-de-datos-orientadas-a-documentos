from dataclasses import dataclass, asdict
import hashlib
import json
from queries.definitions import VARIANTS, QuerySpec, QueryBlocked

PROFILES = {'baseline':('PROFILE_A_BASELINE',4,4096),'medium':('PROFILE_B_MEDIUM',2,2048),'severe':('PROFILE_C_SEVERE',1,1024)}


@dataclass(frozen=True)
class Scenario:
    engine: str
    profile: str
    query: str
    variant: str
    concurrency: int
    run_number: int

    def __post_init__(self):
        QuerySpec(self.engine,self.query,self.variant)
        if self.profile not in PROFILES or type(self.concurrency) is not int or self.concurrency not in (1,10,50) or type(self.run_number) is not int or not 1<=self.run_number<=3:
            raise QueryBlocked('Invalid official profile/concurrency/repetition')

    @property
    def id(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()[:24]


def matrix(mode, *, base_variants=None, engine=None, profile=None, query=None, variant=None, concurrency=None, run_number=None):
    if mode not in ('base','extended','single'): raise QueryBlocked('Select base/extended/single explicitly')
    for value,allowed in [(engine,VARIANTS),(profile,PROFILES),(query,('Q1','Q2')),(concurrency,(1,10,50)),(run_number,(1,2,3))]:
        if value is not None and value not in allowed: raise QueryBlocked('Invalid scenario filter')
    if mode=='single':
        if any(v is None for v in (engine,profile,query,concurrency,run_number)):
            raise QueryBlocked('single requires engine/profile/query/concurrency/run-number')
        return [Scenario(engine,profile,query,variant or ('default' if query=='Q1' else ''),concurrency,run_number)]
    if mode=='base':
        if not base_variants or set(base_variants)!=set(VARIANTS):
            raise QueryBlocked('Base requires explicit Q2 variant for BOTH engines; omitted alternatives are recorded')
        for e,v in base_variants.items(): QuerySpec(e,'Q2',v)
    selected=[]
    for e in VARIANTS:
        for p in PROFILES:
            for q in ('Q1','Q2'):
                choices = [base_variants[e]] if mode=='base' and q=='Q2' else list(VARIANTS[e][q])
                for v in choices:
                    for c in (1,10,50):
                        for r in (1,2,3):
                            s=Scenario(e,p,q,v,c,r)
                            if all(w is None or got==w for got,w in [(e,engine),(p,profile),(q,query),(v,variant),(c,concurrency),(r,run_number)]): selected.append(s)
    if not selected: raise QueryBlocked('Filters select no scenarios')
    return selected
