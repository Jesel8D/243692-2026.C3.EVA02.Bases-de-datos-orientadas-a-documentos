"""One independent native session and SQLite journal per client thread."""
import sqlite3,time
from pathlib import Path


def error_info(exc,phase):
    sqlstate=getattr(exc,'sqlstate',None)
    name=type(exc).__name__
    kind=('timeout' if sqlstate=='57014' or 'Timeout' in name or 'Canceled' in name else
          'connection' if phase=='connect' or (sqlstate and sqlstate.startswith('08')) or name in ('OperationalError','InterfaceError','AutoReconnect','ConnectionFailure') or 'Connection' in name else
          'query' if phase in ('warmup','measurement') else 'runner')
    return {'category':kind,'error_class':name,'sqlstate':sqlstate,'phase':phase}


def worker(client_id,factory,spec,directory,state,events,queue,cancel):
    session=None;db=None;phase='connect'
    try:
        db=sqlite3.connect(Path(directory)/f'client-{client_id:03}.sqlite')
        db.execute('PRAGMA cache_size=-2048')
        db.execute('CREATE TABLE operations(sequence INTEGER PRIMARY KEY,phase TEXT,start_ns INTEGER,end_ns INTEGER,outcome TEXT,error_class TEXT,tag TEXT)')
        db.commit()
        session=factory(spec,client_id)
        observer=state.get('telemetry')
        if observer is not None and hasattr(observer,'configure_client'):observer.configure_client(session,client_id)
        queue.put(('connected',client_id,dict(session.effective)))
        for phase in ('warmup','measurement'):
            while not events[phase].wait(.05):
                if cancel.is_set(): return
            start,end=state[phase]
            while not cancel.is_set() and time.monotonic_ns()<start:
                cancel.wait(min(.01,(start-time.monotonic_ns())/1e9) if time.monotonic_ns()<start else 0)
            pending=0;sequence=0
            while not cancel.is_set():
                sequence+=1
                tag=session.set_observation(phase,sequence) if hasattr(session,'set_observation') else None
                before=time.monotonic_ns()
                if before>=end: break
                try:
                    session.execute()  # Original query + complete result consumption.
                    after=time.monotonic_ns();outcome='ok';err=None
                except Exception as exc:
                    after=time.monotonic_ns();outcome='error';err=type(exc).__name__
                    queue.put(('error',client_id,error_info(exc,phase)));cancel.set()
                db.execute('INSERT INTO operations(phase,start_ns,end_ns,outcome,error_class,tag) VALUES (?,?,?,?,?,?)',(phase,before,after,outcome,err,tag))
                pending+=1
                if pending>=64 or outcome!='ok': db.commit();pending=0
            db.commit()
            queue.put((phase+'_done',client_id,None))
            if cancel.is_set(): return
        phase='verify'
        session.verify()
    except Exception as exc:
        queue.put(('error',client_id,error_info(exc,phase)));cancel.set()
    finally:
        if db is not None:
            try: db.commit();db.close()
            except Exception as exc: queue.put(('error',client_id,error_info(exc,'journal_flush')));cancel.set()
        if session is not None:
            try: session.close()
            except Exception as exc: queue.put(('error',client_id,error_info(exc,'close')));cancel.set()
        queue.put(('closed',client_id,None))
