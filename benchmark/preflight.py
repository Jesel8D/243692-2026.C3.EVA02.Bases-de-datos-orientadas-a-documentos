"""Strict gates; pilot relaxations are visible deviations, not study validation."""
from dataclasses import asdict
from pathlib import Path
import importlib.metadata,os,shutil,time
from queries.definitions import QuerySpec,QueryBlocked
from queries.execution import QueryExecutor
from queries.indexes import inspect_indexes
from queries.validation import source_reference,validate_q1,validate_q2
from queries.native import Connection
from src.dataset.files import validate_file,iter_file
from src.dataset.operations import compare_dataset
from . import RUNNER_VERSION
from .config import source_hashes
from .environment import docker,snapshot,host_info


class NativeFactory:
    evidence_kind='real_native_driver'
    def __init__(self,connection,reference,version):
        self.connection=connection;self.reference=reference;self.version=version
    def __call__(self,spec,client_id):
        session=QueryExecutor(spec.engine,spec.timeout_ms).open_session(spec,self.connection)
        try:
            if session.effective['server_version']!=self.version:raise QueryBlocked('Engine version changed before client preparation')
            session.validate_once(self.reference)
            return session
        except BaseException:session.close();raise


def inspect_identity(engine,query='Q1',variant='default',timeout_ms=120000):
    executor=QueryExecutor(engine,timeout_ms)
    result=executor.execute(QuerySpec(engine,query,variant,timeout_ms))
    return executor,result


# Operator acknowledgement of a physical-index-only interpretation of the
# main playbook. This does NOT assert compatibility with Q2's timestamptz cast
# and does NOT represent approval by the course instructor.
PG_INDEX_ACK_ENV = 'BENCHMARK_PG_TEXT_INDEX_ACK'
PG_INDEX_ACK_EXACT = 'I_ACCEPT_PHYSICAL_TEXT_INDEX_ONLY_Q2_CAST_MISMATCH_NO_TEACHER_APPROVAL'


def index_policy_decision(engine, audit, acknowledgement=None):
    """Read-only gate: physical inventory plus explicit operator acknowledgement."""
    if engine == 'mongo':
        valid = audit.get('engine') == 'mongo' and audit.get('status') == 'PASS'
        return {'status': 'PASS' if valid else 'BLOCKED',
                'engine': engine, 'physical_index_ok': valid,
                'basis': 'Mongo required indexes audited; no methodology exception'}
    if engine != 'postgres':
        raise QueryBlocked('Unsupported engine in index policy')
    physical = (audit.get('engine') == 'postgres'
                and audit.get('physical_index_status') == 'PASS'
                and audit.get('primary_key_ok') is True
                and audit.get('timestamp_text_index_present') is True
                and audit.get('unexpected') == [] )
    accepted = acknowledgement == PG_INDEX_ACK_EXACT
    return {
        'status': 'PASS' if physical and accepted else 'BLOCKED',
        'engine': engine,
        'physical_index_ok': physical,
        'operator_acknowledged': accepted,
        'operator_acknowledgement_source': PG_INDEX_ACK_ENV if accepted else None,
        'operator_acknowledgement_text': PG_INDEX_ACK_EXACT if accepted else None,
        'teacher_approval': 'not_asserted',
        'original_q2_cast_matches_text_index': False,
        'q2_index_usage_from_explain': 'not_verified_by_this_gate',
        'reason': ('Physical B-Tree on data->>timestamp accepted by operator only; '
                   'Q2 casts to timestamptz, so no assertion of predicate/index '
                   'compatibility, index usage, or instructor approval'),
    }


def preflight(scenario,protocol,dataset,output,resource_snapshot,telemetry,global_validation=None):
    preflight_started=time.monotonic()
    if not Path('/sys/fs/cgroup/cgroup.controllers').exists() or docker('info','--format','{{.CgroupVersion}}')!='2':raise QueryBlocked('cgroups v2 required')
    if shutil.disk_usage(output).free<256*1024*1024:raise QueryBlocked('Less than 256 MiB free; no runner starts')
    reuse = global_validation is not None and global_validation.ready and protocol.mode == 'definitive'
    stats=global_validation.stats if reuse else validate_file(dataset)
    strict=protocol.mode=='definitive'
    deviations=[]
    if strict and stats['count']!=500000:raise QueryBlocked('Definitive dataset count must be exactly 500000')
    if not strict and stats['count']!=500000:deviations.append('small dataset, not definitive')
    selected,result=inspect_identity(scenario.engine,scenario.query,scenario.variant,protocol.timeout_ms)
    engines=['mongo','postgres'] if strict else [scenario.engine]
    # Fail fast on index policy before repeating the expensive 500,000-row
    # comparison. Inspect both engines in definitive mode, not merely the
    # selected engine. Never replace the raw academic audit with a false PASS.
    index_checks = {}
    index_decisions = {}
    index_acknowledgement = os.environ.get(PG_INDEX_ACK_ENV)
    for e in engines:
        ex = selected if e == scenario.engine else QueryExecutor(e,protocol.timeout_ms)
        audit = inspect_indexes(ex)
        decision = index_policy_decision(e, audit, index_acknowledgement)
        index_checks[e] = audit
        index_decisions[e] = decision
        if strict and decision['status'] != 'PASS':
            raise QueryBlocked('Index policy BLOCKED for ' + e +
                               ': requires physically valid indexes and explicit '
                               'operator acknowledgement for PostgreSQL text-index limitation')
        if not strict and decision['status'] != 'PASS':
            deviations.append('index conformity/interpretation pending; pilot only')
    index_evidence = index_checks[scenario.engine]
    shared_evidence = None
    if reuse:
        shared_evidence = global_validation.validate(protocol.timeout_ms)
        data_evidence = global_validation.data_evidence
        references = global_validation.references
    else:
        adapters=[QueryExecutor(e,protocol.timeout_ms).adapter for e in engines]
        data_evidence=compare_dataset(adapters,dataset)
        references={scenario.query:source_reference((doc for _,_,doc in iter_file(dataset)),scenario.query)}
    reference=references[scenario.query]
    check=(validate_q1 if scenario.query=='Q1' else validate_q2)(reference,result['rows'],scenario.engine)
    if check['status']!='PASS':raise QueryBlocked('Selected query failed independent source oracle')
    if strict and not reuse:
        # Full query and variant validation is performed ONCE per invocation.
        # Every later scenario still executes and checks its selected query.
        for query in ('Q1','Q2'):
            if query not in references:
                references[query] = source_reference((doc for _,_,doc in iter_file(dataset)),query)
            ref=references[query]
            from queries.definitions import VARIANTS
            for e in engines:
                ex=QueryExecutor(e,protocol.timeout_ms)
                repeated_audit = inspect_indexes(ex)
                repeated_policy = index_policy_decision(e, repeated_audit, index_acknowledgement)
                if repeated_policy['status'] != 'PASS':
                    raise QueryBlocked('Both real index policies must pass; failed: ' + e)
                for variant in VARIANTS[e][query]:
                    answer=ex.execute(QuerySpec(e,query,variant,protocol.timeout_ms))
                    c=(validate_q1 if query=='Q1' else validate_q2)(ref,answer['rows'],e)
                    if c['status']!='PASS':raise QueryBlocked('Definitive real query/variant correctness failed')
    # Capture proof only after full validation of both engines and every variant.
    # Never persist this as a cross-process receipt or use it in pilot mode.
    if strict and global_validation is not None and not reuse:
        global_validation.save(stats,data_evidence,references,scenario.id,protocol.timeout_ms)
    telemetry_check=telemetry.probe() if hasattr(telemetry,'probe') else {'status':'BLOCKED','errors':['Prometheus monitoring not configured']}
    if strict and telemetry_check['status']!='PASS':raise QueryBlocked('Telemetry preflight BLOCKED: '+'; '.join(telemetry_check['errors']))
    if not strict and telemetry_check['status']!='PASS':deviations.append('telemetry preflight incomplete; pilot only')
    required=('cpu_throttled_seconds','max_rss_mb','disk_spill','oom_killed')
    missing=[k for k in required if not telemetry.capabilities().get(k)]
    if strict and missing:raise QueryBlocked('Mandatory telemetry unavailable; inspect monitoring targets/series/spill preparation: '+','.join(missing))
    if missing:deviations.append('mandatory telemetry absent: '+','.join(missing))
    if protocol.cache=='skip':deviations.append('cache flush skipped, not protocol-equivalent')
    networks=resource_snapshot['networks']
    preferred=[v.get('IPAddress') for name,v in networks.items() if name.endswith('_host_access') and v.get('IPAddress')]
    fallback=[v.get('IPAddress') for v in networks.values() if v.get('IPAddress')]
    if len(preferred)==1:
        endpoint_ip=preferred[0]
    elif not preferred and len(fallback)==1:
        endpoint_ip=fallback[0]
    else:
        raise QueryBlocked('Ambiguous/missing local Docker bridge endpoint')
    prefix='MONGO' if scenario.engine=='mongo' else 'POSTGRES'
    username=os.environ.get(prefix+'_USERNAME' if prefix=='MONGO' else prefix+'_USER','')
    password=os.environ.get(prefix+'_PASSWORD','')
    if not username or not password:raise QueryBlocked('Native credentials missing from local configuration')
    conn=Connection(endpoint_ip,27017 if scenario.engine=='mongo' else 5432,os.environ['DATA_DATABASE_NAME'],username,password)
    identity={'server_version':result['effective']['server_version'],'image':resource_snapshot['image'],
              'image_id':resource_snapshot['image_id']}
    return {'dataset':{'sha256':stats['sha256'],'logical_sha256':stats['logical_sha256_in_file_order'],
                         'count':stats['count'],'configuration':stats['configuration']},
            'identity':identity,'resources_observed':resource_snapshot,'query_check':check,'data_check':data_evidence,
            'index_check':index_evidence,'index_checks_by_engine':index_checks,
            'index_policy_by_engine':index_decisions,
            'index_policy_scope':{'teacher_approval':'not_asserted',
                                  'q2_text_index_cast_compatible':False,
                                  'effective_interpretation':'operator-acknowledged physical-only when accepted'},
            'telemetry_preflight':telemetry_check,'telemetry_capabilities':telemetry.capabilities(),'deviations':deviations,
            'global_validation':shared_evidence or {'status':'FULL','scope':'all engines and variants freshly checked',
                           'method':'no evidence reused'},
            'preflight_elapsed_seconds':round(time.monotonic()-preflight_started,3)}, NativeFactory(conn,reference,identity['server_version'])


def driver_versions():
    try:return {p:importlib.metadata.version(p) for p in ('psycopg','psycopg-binary','pymongo','dnspython','typing_extensions')}
    except importlib.metadata.PackageNotFoundError as exc:raise QueryBlocked('Install pinned requirements-benchmark.txt in a local venv') from exc
