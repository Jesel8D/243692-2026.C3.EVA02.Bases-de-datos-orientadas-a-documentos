"""Local Prometheus API with explicit empty/stale/error handling and raw evidence."""
import json,time,urllib.request,urllib.parse,urllib.error
from datetime import datetime
from decimal import Decimal,InvalidOperation,ROUND_CEILING
from .config import local_url
from queries.definitions import QueryBlocked

class Prometheus:
    def __init__(self,url,timeout=5):
        self.url=local_url(url);self.timeout=timeout;self.requests=[]
        # Only an explicitly validated local IP. Internet traffic still uses the session proxy elsewhere.
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(self,path,params=None):
        target=self.url+path+('?' + urllib.parse.urlencode(params) if params else '')
        try:
            with self.opener.open(target,timeout=self.timeout) as response:
                body=response.read(8*1024*1024+1)
                if len(body)>8*1024*1024:raise ValueError('response too large')
            value=json.loads(body,parse_float=Decimal)
        except urllib.error.HTTPError as exc:
            try:message=json.loads(exc.read(4096)).get('error','HTTP error')
            except Exception:message='HTTP error'
            self.requests.append({'path':path,'params':params,'http_status':exc.code,'error':str(message)[:512]})
            raise QueryBlocked('Prometheus HTTP '+str(exc.code)+': '+str(message)[:512]) from exc
        except Exception as exc:raise QueryBlocked('Prometheus local HTTP/JSON failure: '+type(exc).__name__) from exc
        if value.get('status')!='success' or value.get('warnings') or value.get('infos'):
            raise QueryBlocked('Prometheus API failed or reported warnings/partial data')
        self.requests.append({'path':path,'params':params,'response':value,'received_epoch_ns':time.time_ns()})
        return value['data']
    def query(self,expression,at=None):
        params={'query':expression}
        if at is not None:params['time']=str(at)
        return self.get('/api/v1/query',params)
    def raw(self,expression,seconds=5,at=None):
        if not 0<seconds<=7200:raise QueryBlocked('Telemetry raw range must be 0..7200 seconds')
        milliseconds=int((Decimal(str(seconds))*1000).to_integral_value(rounding=ROUND_CEILING))
        data=self.query(expression+'['+str(milliseconds)+'ms]',at)
        if data.get('resultType')!='matrix' or len(data.get('result',[]))!=1:
            raise QueryBlocked('Required metric missing or ambiguous: '+expression)
        result=data['result'][0]
        samples=[]
        try:
            for stamp,value in result['values']:
                stamp,value=Decimal(str(stamp)),Decimal(value)
                if not stamp.is_finite() or not value.is_finite():raise ValueError()
                samples.append((stamp,value))
        except (KeyError,ValueError,InvalidOperation):raise QueryBlocked('Invalid/nonfinite metric samples')
        if not samples or samples!=sorted(samples) or len({t for t,_ in samples})!=len(samples):
            raise QueryBlocked('Empty/unsorted/duplicate metric samples')
        return result['metric'],samples
    def targets(self,now=None):
        now=Decimal(str(time.time() if now is None else now))
        targets=self.get('/api/v1/targets',{'state':'active'}).get('activeTargets',[])
        selected={}
        for job in ('cadvisor','node','prometheus'):
            matches=[t for t in targets if t.get('labels',{}).get('job')==job]
            if len(matches)!=1:raise QueryBlocked('Missing/ambiguous target: '+job)
            t=matches[0]
            try:age=now-Decimal(str(datetime.fromisoformat(t['lastScrape'].replace('Z','+00:00')).timestamp()))
            except (KeyError,ValueError):raise QueryBlocked('Invalid target scrape time: '+job)
            if t.get('health')!='up' or t.get('lastError') or not -Decimal('.1')<=age<=3:
                raise QueryBlocked('Target DOWN or stale: '+job)
            if t.get('scrapeInterval')!='1s':raise QueryBlocked('Target scrape interval is not 1s: '+job)
            selected[job]=t
        return selected
