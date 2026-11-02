"""Manual operator attestation only: no sync/drop_caches/sudo executed here."""
import select,sys,time
from .results import write_json
from queries.definitions import QueryBlocked


def manual_cache(attempt_id,cancel,evidence_path):
    if not sys.stdin.isatty():raise QueryBlocked('Manual cache stage needs an interactive operator, never automatic privilege escalation')
    phrase='CACHE_CLEARED '+attempt_id
    print('Manual cache stage AFTER client preparation. Follow approved host procedure separately; this runner never executes privileged commands.',file=sys.stderr)
    print('If cache flush was actually completed, enter exactly: '+phrase,file=sys.stderr)
    while not cancel.is_set():
        if select.select([sys.stdin],[],[],.1)[0]:
            text=sys.stdin.readline().strip()
            if text!=phrase:raise QueryBlocked('Cache not attested; no equivalent definitive run')
            data={'policy':'manual','attested':True,'verified_by_runner':False,'timestamp_epoch_ns':time.time_ns(),
                  'evidence':'operator attestation, not proof of kernel cache state','attempt_id':attempt_id}
            write_json(evidence_path,data)
            return data
    raise InterruptedError('Cancelled awaiting manual cache attestation')
