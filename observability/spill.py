"""Spill is true, false through a valid complete mechanism, or unknown (None)."""
from pathlib import Path
import sqlite3
from queries.definitions import QueryBlocked

def eligible_count(directory,start,end):
    total=0
    for p in Path(directory).glob('client-*.sqlite'):
        with sqlite3.connect(p) as db:
            total+=db.execute("SELECT count(*) FROM operations WHERE phase='measurement' AND outcome='ok' AND start_ns>=? AND end_ns<=?",(start,end)).fetchone()[0]
    return total

def postgres_spill(events,directory,clients,window,offset_ns,coverage):
    if not clients or any(not c.get('spill_capture') for c in clients.values()):return None,{'state':'insufficient','reason':'log_temp_files=0 not verified for every session'}
    pids={c['backend_pid']:i for i,c in clients.items()};matched=0;unmatched=0;examples=[]
    for event in events:
        at=event['stamp_ns']-offset_ns
        if not window[0]<=at<=window[1]:continue
        if event.get('unparsed'):unmatched+=1;continue
        if event['pid'] not in pids:continue # Other backends/global temp files are not evidence for this repetition.
        if event.get('size_bytes',0)<=0:unmatched+=1;continue
        path=Path(directory)/('client-'+str(pids[event['pid']]).zfill(3)+'.sqlite')
        with sqlite3.connect(path) as db:
            # PostgreSQL %m has millisecond precision; explicitly allow only that timestamp quantum.
            count=db.execute("SELECT count(*) FROM operations WHERE phase='measurement' AND outcome='ok' AND start_ns>=? AND end_ns<=? AND start_ns<=? AND end_ns>=?",(*window,at+1000000,at-1000000)).fetchone()[0]
        if count:
            matched+=1
            if len(examples)<100:examples.append(event)
        else:unmatched+=1
    if matched:return True,{'state':'confirmed','source':'session log_temp_files=0; PID + actual included operation interval','events':examples,'files':matched}
    if coverage and not unmatched and eligible_count(directory,*window)>0:
        return False,{'state':'not_detected','source':'complete blocking stderr log stream with log_temp_files=0 on every measured backend','files':0}
    return None,{'state':'insufficient','reason':'log stream incomplete, unparsed/unattributed file, or no included operations','unmatched':unmatched}

class MongoProfiler:
    def __init__(self,connection,token):self.connection=connection;self.token=token;self.client=None;self.previous=None;self.active=False
    def prepare(self,directory):
        from pymongo import MongoClient
        from benchmark.results import write_json
        c=self.connection
        self.client=MongoClient(host=c.host,port=c.port,username=c.username,password=c.password,authSource='admin',serverSelectionTimeoutMS=5000,retryReads=False,retryWrites=False)
        self.db=self.client[c.database];self.previous=self.db.command({'profile':-1})
        if self.previous.get('was')!=0:raise QueryBlocked('Existing Mongo profiling active: left unchanged; explicit isolation needed')
        write_json(Path(directory)/'mongo-profile-restore.json',{'database':c.database,'token':self.token,'previous':{k:self.previous[k] for k in ('was','filter') if k in self.previous},'requires_restoration_if_interrupted':True})
        self.filter={'command.comment.benchmark_token':self.token}
        self.active=True # A lost response may still mean the server applied the command; cleanup must inspect it.
        self.db.command({'profile':1,'filter':self.filter})
    def collect(self,directory,window):
        matched=0;missing=0;explicit_false=0;true_count=0
        db=sqlite3.connect(Path(directory)/'mongo-profile-evidence.sqlite')
        db.execute('CREATE TABLE evidence(tag TEXT PRIMARY KEY,used_disk INTEGER)')
        for row in self.db['system.profile'].find({'command.comment.benchmark_token':self.token,'command.comment.phase':'measurement','command.aggregate':'orders'},{'command.comment':1,'usedDisk':1,'_id':0}):
            comment=row.get('command',{}).get('comment',{});tag=comment.get('tag')
            if tag is None:continue
            value=row.get('usedDisk',False);value=int(value) if type(value) is bool else None
            db.execute('INSERT OR REPLACE INTO evidence VALUES (?,?)',(tag,value))
        db.commit()
        for p in Path(directory).glob('client-*.sqlite'):
            with sqlite3.connect(p) as ops:
                for (tag,) in ops.execute("SELECT tag FROM operations WHERE phase='measurement' AND outcome='ok' AND start_ns>=? AND end_ns<=?",window):
                    value=db.execute('SELECT used_disk FROM evidence WHERE tag=?',(tag,)).fetchone()
                    if value is None or value[0] is None:missing+=1
                    else:matched+=1;true_count+=value[0]==1;explicit_false+=value[0]==0
        db.close()
        details={'source':'system.profile records of the actual tagged operations, never a rerun of explain','matched':matched,'missing_or_no_usedDisk':missing,'explicit_false':explicit_false,'confirmed_spill':true_count}
        if true_count:return True,{'state':'confirmed',**details}
        if matched and not missing:return False,{'state':'not_detected',**details}
        return None,{'state':'insufficient',**details}
    def close(self):
        try:
            if self.active:
                current=self.db.command({'profile':-1})
                if current.get('filter')==self.filter or current.get('filter')=={k:{'$eq':v} for k,v in self.filter.items()}:
                    self.db.command({'profile':self.previous['was'],'filter':self.previous.get('filter','unset')})
                elif current.get('was')!=self.previous['was'] or current.get('filter')!=self.previous.get('filter'):
                    raise QueryBlocked('Mongo profiler changed externally: refusing to overwrite; manual restoration required')
                self.active=False
        finally:
            if self.client is not None:self.client.close()
