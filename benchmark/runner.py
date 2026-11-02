"""Window orchestration, with injected factories for labelled runner tests only."""
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
import queue,resource,threading,time

from queries.definitions import QuerySpec, QueryBlocked
from .workers import worker
from .timing import ns,wait_until
from .metrics import aggregate


def run_repetition(scenario,protocol,directory,factory,telemetry,*,external_cancel=None,cache_action=None):
    directory=Path(directory)
    if getattr(factory,'evidence_kind',None)!='real_native_driver' and protocol.mode!='test':
        raise QueryBlocked('Simulated executors are forbidden outside internal runner tests')
    cancel=threading.Event();external_cancel=external_cancel or threading.Event()
    events={p:threading.Event() for p in ('warmup','measurement')};state={'telemetry':telemetry};messages=queue.Queue()
    spec=QuerySpec(scenario.engine,scenario.query,scenario.variant,protocol.timeout_ms)
    threads=[threading.Thread(target=worker,args=(i,factory,spec,directory,state,events,messages,cancel),daemon=True,name=f'client-{i}') for i in range(scenario.concurrency)]
    seen={};errors=[];trace=[];effective={};window=None;complete=False;interrupted=False;telemetry_started=False
    usage=resource.getrusage(resource.RUSAGE_SELF)
    def drain_messages():
        while True:
            try: kind,i,data=messages.get_nowait()
            except queue.Empty: break
            seen.setdefault(kind,set()).add(i)
            if kind=='connected': effective[str(i)]=data
            if kind=='error': errors.append({'client':i,**data})
    def await_clients(kind,seconds):
        deadline=time.monotonic()+seconds
        while len(seen.get(kind,set()))<scenario.concurrency:
            drain_messages()
            if external_cancel.is_set(): cancel.set();return False
            if cancel.is_set(): return False
            if time.monotonic()>deadline:
                errors.append({'category':'runner_timeout','phase':kind});cancel.set();return False
            time.sleep(.005)
        return True
    try:
        if hasattr(telemetry,'prepare'):telemetry.prepare(directory,factory)
        for t in threads:t.start()
        if await_clients('connected',protocol.timeout_ms/1000+20):
            if hasattr(telemetry,'clients_ready'):telemetry.clients_ready(effective)
            cache_info=cache_action() if cache_action else {'policy':'skip','deviation':'not equivalent to manual cache flush'}
            if protocol.cache=='manual' and (not cache_action or not cache_info.get('attested')):
                raise QueryBlocked('Manual cache attestation missing; no privileged commands executed')
            now=time.monotonic_ns();state['warmup']=(now+ns(.02),now+ns(.02)+ns(protocol.warmup))
            trace.append({'stage':'warmup','start_ns':state['warmup'][0],'end_ns':state['warmup'][1]})
            events['warmup'].set()
            if await_clients('warmup_done',protocol.warmup+protocol.timeout_ms/1000+20):
                # Warmup in-flight queries have drained; none can contaminate measurement.
                trace.append({'stage':'warmup_drained','at_ns':time.monotonic_ns()})
                telemetry.start();telemetry_started=True
                start=time.monotonic_ns()+ns(.02);end=start+ns(protocol.measurement)
                epoch_ns=time.time_ns()+(start-time.monotonic_ns())
                state['measurement']=(start,end);window=(start,end)
                if hasattr(telemetry,'set_window'):telemetry.set_window(start,end,epoch_ns)
                trace.append({'stage':'measurement','start_ns':start,'end_ns':end,'timestamp_epoch':str(Decimal(epoch_ns)/1000000000)})
                events['measurement'].set()
                while time.monotonic_ns()<end and not cancel.is_set():
                    if external_cancel.is_set():cancel.set();break
                    telemetry.sample()
                    cancel.wait(min(.05,max(0,(end-time.monotonic_ns())/1e9)))
                telemetry_data=telemetry.stop();telemetry_started=False
                complete=not cancel.is_set() and time.monotonic_ns()>=end
                await_clients('closed',protocol.timeout_ms/1000+20)
                trace.append({'stage':'measurement_drained','at_ns':time.monotonic_ns()})
    except BaseException:
        cancel.set()
        raise
    finally:
        if external_cancel.is_set():cancel.set();interrupted=True
        # Ensure a waiting worker cannot access an undefined window during abort.
        state.setdefault('warmup',(0,0));state.setdefault('measurement',(0,0))
        for event in events.values():event.set()
        join_deadline=time.monotonic()+protocol.timeout_ms/1000+20
        for t in threads:
            if t.ident is not None:t.join(max(0,join_deadline-time.monotonic()))
        if any(t.is_alive() for t in threads):
            if hasattr(telemetry,'cleanup'):telemetry.cleanup()
            raise QueryBlocked('Worker did not close by timeout; attempt remains incomplete, no CSV committed')
        drain_messages()
        if telemetry_started:
            telemetry_data=telemetry.stop()
        import sys
        if (sys.exc_info()[0] is not None or external_cancel.is_set()) and hasattr(telemetry,'cleanup'):telemetry.cleanup()
    if external_cancel.is_set(): interrupted=True
    if interrupted: raise InterruptedError('Controlled cancellation; repetition is incomplete and resumable')
    complete=complete and not errors and len(seen.get('closed',set()))==scenario.concurrency
    if 'telemetry_data' not in locals():telemetry_data=telemetry.unavailable('measurement_not_started')
    if protocol.cooldown and not external_cancel.is_set():
        start=time.monotonic_ns();end=start+ns(protocol.cooldown)
        trace.append({'stage':'cooldown','start_ns':start,'end_ns':end})
        if not wait_until(end,external_cancel):
            if hasattr(telemetry,'cleanup'):telemetry.cleanup()
            raise InterruptedError('Cancelled during cooldown; no completed repetition')
    if hasattr(telemetry,'finish'):telemetry_data=telemetry.finish(directory,window,effective)
    metrics=aggregate(directory,window,complete)
    missing=[k for k in ('cpu_throttled_seconds','max_rss_mb','disk_spill','oom_killed') if telemetry_data.get(k) is None]
    oom=telemetry_data.get('oom_killed') is True
    status='oom' if oom else 'error' if errors or missing or telemetry_data.get('integrity_error') or not complete or not metrics['samples'] else 'spill' if telemetry_data['disk_spill'] else 'ok'
    endusage=resource.getrusage(resource.RUSAGE_SELF)
    return {'scenario':asdict(scenario),'protocol':asdict(protocol),'window_complete':complete,
            'metrics':metrics,'telemetry':telemetry_data,'missing_telemetry':missing,'status':status,
            'cache':locals().get('cache_info',{'policy':protocol.cache,'stage_not_reached':True}),'errors':errors,'stages':trace,'clients_requested':scenario.concurrency,'clients_connected':len(effective),
            'clients_effective':effective,'evidence_kind':factory.evidence_kind,
            'eligible_for_final_analysis':protocol.mode=='definitive' and not missing and complete and not errors and not telemetry_data.get('integrity_error') and metrics['samples']>0 and status in ('ok','spill'),
            'runner_resources':{'user_cpu_seconds':endusage.ru_utime-usage.ru_utime,'system_cpu_seconds':endusage.ru_stime-usage.ru_stime,
              'process_lifetime_maxrss_kib':endusage.ru_maxrss,'scope':'runner process, not database RSS; whole attempt CPU'}}
