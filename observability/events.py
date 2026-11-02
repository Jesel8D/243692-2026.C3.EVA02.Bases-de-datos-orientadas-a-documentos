"""Continuous local Docker evidence streams into bounded-memory SQLite journals."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,re,sqlite3,subprocess,threading,time
from queries.definitions import QueryBlocked

def epoch_ns(stamp):
    match=re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z',stamp)
    if not match:raise ValueError('timestamp must be UTC RFC3339')
    whole=int(datetime.fromisoformat(match[1]).replace(tzinfo=timezone.utc).timestamp())
    return whole*10**9+int((match[2] or '').ljust(9,'0'))

def pg_log(line):
    # Supported PostgreSQL log_line_prefix: '%m [%p] ', log_timezone UTC, stderr.
    parts=line.split(' ',1)
    if len(parts)!=2:return None
    docker_stamp=epoch_ns(parts[0])
    m=re.search(r'(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d\.\d+) (?:UTC|GMT) \[(\d+)\].*temporary file:.*size (\d+)',parts[1])
    if m:return {'stamp_ns':epoch_ns(m[1]+'T'+m[2]+'Z'),'docker_stamp_ns':docker_stamp,'pid':int(m[3]),'size_bytes':int(m[4])}
    if 'temporary file:' in parts[1]:return {'unparsed':True,'stamp_ns':docker_stamp}
    return None

class DockerStream:
    def __init__(self,cid,path,kind):
        if not re.fullmatch('[a-f0-9]{64}',cid):raise QueryBlocked('Full container ID required for evidence stream')
        self.cid=cid;self.path=Path(path);self.kind=kind;self.failure=None;self.count=0;self.process=None
    def start(self):
        self.start_epoch_ns=time.time_ns()
        since=str(self.start_epoch_ns//10**9)+'.'+str(self.start_epoch_ns%10**9).zfill(9)
        args=['events','--filter','container='+self.cid,'--filter','type=container','--since',since,'--format','{{json .}}'] if self.kind=='events' else ['logs','--timestamps','--follow','--since',since,self.cid]
        env=os.environ.copy()
        for k in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(k,None)
        self.process=subprocess.Popen(['docker','--host=unix:///var/run/docker.sock',*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
        self.thread=threading.Thread(target=self._read,daemon=True);self.thread.start()
        time.sleep(.1)
        if self.process.poll() is not None:self.failure='Docker evidence stream exited before window'
    def _read(self):
        try:
            db=sqlite3.connect(self.path);db.execute('PRAGMA cache_size=-1024')
            db.execute('CREATE TABLE evidence(stamp_ns INTEGER,payload TEXT)');db.commit()
            for line in self.process.stdout:
                if self.kind=='events':
                    try:
                        raw=json.loads(line);cid=raw.get('Actor',{}).get('ID',raw.get('id'))
                        if cid!=self.cid:continue
                        value={'action':raw.get('Action',raw.get('status')),'stamp_ns':int(raw['timeNano']),'id':cid}
                    except (KeyError,ValueError,TypeError):self.failure='Malformed Docker event';continue
                else:
                    try:value=pg_log(line.strip())
                    except ValueError:self.failure='Invalid Docker log timestamp';continue
                if value:
                    db.execute('INSERT INTO evidence VALUES (?,?)',(value['stamp_ns'],json.dumps(value)));self.count+=1
                    db.commit()
            db.close()
        except Exception as exc:self.failure='Evidence journal failure: '+type(exc).__name__
    def stop(self):
        alive=self.process is not None and self.process.poll() is None
        if alive:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5);self.failure='Evidence stream forced termination'
        if self.process is not None:
            self.thread.join(5)
            if self.thread.is_alive():self.failure='Evidence stream did not flush'
        self.end_epoch_ns=time.time_ns()
        return {'started_epoch_ns':self.start_epoch_ns,'ended_epoch_ns':self.end_epoch_ns,'continuous':alive and self.failure is None,'failure':self.failure,'records':self.count,'file':self.path.name}
    def rows(self):
        if not self.path.exists():return
        with sqlite3.connect(self.path) as db:
            for row in db.execute('SELECT payload FROM evidence ORDER BY stamp_ns'):yield json.loads(row[0])

def classify_oom(events,start_ns,end_ns,coverage,identity_stable=True):
    positive=[e for e in events if e['action']=='oom' and start_ns<=e['stamp_ns']<=end_ns]
    invalid=[e for e in events if e['action'] in ('die','start','restart','destroy') and start_ns<=e['stamp_ns']<=end_ns]
    if positive:return True,{'source':'Docker oom event in exact mapped epoch window','events':positive[:100]}
    if invalid or not coverage or not identity_stable:return None,{'reason':'OOM source gap or container lifecycle/identity changed','events':invalid[:100]}
    return False,{'source':'continuous Docker event stream for exact container and window','events':[]}
