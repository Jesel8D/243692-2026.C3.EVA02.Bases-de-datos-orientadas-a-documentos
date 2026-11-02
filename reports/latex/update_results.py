#!/usr/bin/env python3
"""Extrae SOLO las dos mediciones designadas. No modifica resultados originales."""
import argparse,csv,hashlib,json
from pathlib import Path

CANDIDATES=[
 ('postgres','definitivo-pg-q1-a-c1-20261101-v2','bc0a8de32c1719c76fca6946'),
 ('mongo','definitivo-q1-perfil-a-optimizado-20261101','4f537e29c5c322d57cebb3b9'),
]
COLS=['timestamp_epoch','engine','profile','query_id','concurrency','run_number','throughput_qps','latency_p50_ms','latency_p95_ms','latency_p99_ms','cpu_throttled_seconds','max_rss_mb','disk_spill','status']

def fail(s):raise SystemExit('ERROR: '+str(s))
def read_valid(root,engine,experiment,scenario):
    branch=root/'results'/'definitive'/experiment/scenario
    attempts=sorted(p for p in branch.glob('attempt-*') if (p/'commit.json').is_file())
    if len(attempts)!=1:fail(f'{engine}: se esperaban exactamente 1 intento confirmado, hay {len(attempts)} en {branch}')
    attempt=attempts[0]
    commit=json.loads((attempt/'commit.json').read_text(encoding='utf8'))
    for name,expected in commit.get('files',{}).items():
        if '/' in name or name.startswith('.'):fail(f'{engine}: ruta insegura de evidencia: {name}')
        file=attempt/name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=expected:
            fail(f'{engine}: hash de commit incorrecto para {name}')
    if not {'started.json','results.csv','result.json'}<=set(commit.get('files',{})):
        fail(f'{engine}: commit incompleto')
    result=json.loads((attempt/'result.json').read_text(encoding='utf8'))
    if result.get('eligible_for_final_analysis') is not True:fail(f'{engine}: no elegible para análisis final')
    with (attempt/'results.csv').open(newline='',encoding='utf8') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=COLS:fail(f'{engine}: esquema CSV no coincide')
        rows=list(reader)
    if len(rows)!=1:fail(f'{engine}: se esperaba 1 fila por escenario')
    row=rows[0]
    expected={'engine':engine,'profile':'PROFILE_A_BASELINE','query_id':'Q1','concurrency':'1','run_number':'1'}
    if any(row[k]!=v for k,v in expected.items()):fail(f'{engine}: escenario no coincide')
    if row['status'] not in ('ok','spill'):fail(f'{engine}: estado no elegible {row["status"]}')
    return row,result

def texnumbers(rows,results):
    vals={}
    for tag,engine in [('Mongo','mongo'),('PG','postgres')]:
        row=rows[engine]
        for macro,key,digits in [('QPS','throughput_qps',4),('Pmedian','latency_p50_ms',2),('Pnintyfive','latency_p95_ms',2),('Pnintynine','latency_p99_ms',2),('RSS','max_rss_mb',2),('Throttle','cpu_throttled_seconds',6)]:
            vals[tag+macro]=f'{float(row[key]):.{digits}f}'
        vals[tag+'Samples']=str(results[engine].get('metrics',{}).get('samples','ND'))
    vals['DeltaQPS']=f'{(float(rows["mongo"]["throughput_qps"])/float(rows["postgres"]["throughput_qps"])-1)*100:.1f}'
    vals['RatioRSS']=f'{float(rows["mongo"]["max_rss_mb"])/float(rows["postgres"]["max_rss_mb"]):.2f}'
    return '% Generado automáticamente a partir de commits válidos\n'+''.join(f'\\newcommand{{\\{key}}}{{{value}}}\n' for key,value in vals.items())

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project-root',type=Path,required=True,help='Raíz del proyecto que contiene results/definitive')
    args=ap.parse_args()
    root=args.project_root.expanduser().resolve()
    if not (root/'results'/'definitive').is_dir():fail('No existe results/definitive en la raíz especificada')
    rows={};results={}
    for engine,experiment,scenario in CANDIDATES:
        rows[engine],results[engine]=read_valid(root,engine,experiment,scenario)
        print(f'CONFIRMADO {engine}: {experiment}/{scenario} estado={rows[engine]["status"]}')
    target=Path(__file__).resolve().parent/'generated';target.mkdir(exist_ok=True)
    with (target/'measurements_partial.csv').open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=COLS)
        writer.writeheader();writer.writerows([rows['postgres'],rows['mongo']])
    (target/'metrics.tex').write_text(texnumbers(rows,results),encoding='utf8')
    print('Actualizados generated/measurements_partial.csv y generated/metrics.tex. No se modificaron resultados originales.')
if __name__=='__main__':main()
