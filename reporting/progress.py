"""Coverage of a declared matrix, never inferred from CSV row count alone."""
from dataclasses import asdict
from decimal import Decimal
from datetime import datetime,timezone
from statistics import median
from benchmark.matrix import matrix,Scenario
from src.dataset.model import parse_json
from queries.definitions import QueryBlocked


def expected_plan(snapshot,mode='auto',base_variants=None,plan_file=None):
    if plan_file:
        from pathlib import Path
        data=parse_json(Path(plan_file).read_text());items=data['plan'];selection=data.get('matrix','selection')
        expected=[]
        for v in items:
            s=Scenario(**{k:v[k] for k in ('engine','profile','query','variant','concurrency','run_number')})
            if v.get('id')!=s.id:raise QueryBlocked('Plan scenario ID mismatch')
            expected.append(s)
        if len({s.id for s in expected})!=len(expected):raise QueryBlocked('Duplicate plan repetition')
        if not expected:raise QueryBlocked('Explicit plan is empty')
    elif mode in ('base','extended'):
        expected=matrix(mode,base_variants=base_variants);selection=mode
    elif mode=='auto':
        configs=[e['manifest']['configuration'] for e in snapshot.experiments]
        declared={c['selection']['matrix'] for c in configs}
        if declared=={'base'}:
            variants=[c['selection'].get('base_Q2_selection') for c in configs]
            if any(v!=variants[0] for v in variants):raise QueryBlocked('Different base Q2 selections cannot be mixed')
            expected=matrix('base',base_variants=variants[0]);selection='base'
        elif declared=={'extended'}:expected=matrix('extended');selection='extended'
        else:
            expected=list({s.id:s for e in snapshot.experiments for s in e['plan'].values()}.values());selection='selection'
    else:raise QueryBlocked('Unknown reporting matrix')
    full=False
    if selection=='extended':full={s.id for s in expected}=={s.id for s in matrix('extended')}
    elif selection=='base':
        variants={s.engine:s.variant for s in expected if s.query=='Q2'}
        if set(variants)=={'mongo','postgres'}:full={s.id for s in expected}=={s.id for s in matrix('base',base_variants=variants)}
    if not expected:raise QueryBlocked('With no results, provide an explicit matrix or plan')
    return {'matrix':selection,'full_matrix':full,'extended_approval':'PENDING' if selection=='extended' else 'not inferred',
            'scenarios':expected,'cells':len({(s.engine,s.profile,s.query,s.variant,s.concurrency) for s in expected})}


def progress(snapshot,plan,now=None):
    expected={s.id for s in plan['scenarios']};cohorts={e['cohort'] for e in snapshot.experiments} or {'no-measurements'}
    by_cohort={}
    for cohort in sorted(cohorts):
        rows=[r for r in snapshot.records if r.cohort==cohort]
        invalid=[r for r in snapshot.invalid if r['cohort']==cohort]
        if any(r.scenario.id not in expected for r in rows) or any(r['scenario_id'] not in expected for r in invalid):raise QueryBlocked('Observed repetition is outside chosen reporting matrix; select correct plan')
        done={r.scenario.id for r in rows}|{r['scenario_id'] for r in invalid}
        valid=sum(r.valid for r in rows)
        nominal=Decimal(420)
        configs=[e['manifest']['configuration'] for e in snapshot.experiments if e['cohort']==cohort]
        if configs:
            p=configs[0]['protocol'];nominal=sum(Decimal(str(p[k])) for k in ('warmup','measurement','cooldown'))
        observed=[]
        for r in rows:
            stages=r.meta.get('stages',[])
            starts=[s['start_ns'] for s in stages if 'start_ns' in s];ends=[s['end_ns'] for s in stages if 'end_ns' in s]
            if starts and ends and r.meta.get('window_complete'):observed.append(Decimal(max(ends)-min(starts))/10**9)
        unit=max(nominal,median(observed)) if observed else nominal
        pending=len(expected)-len(done)
        active=[a for a in snapshot.unfinished if a['cohort']==cohort and a['scenario_id'] not in done]
        times=[]
        for e in snapshot.experiments:
            if e['cohort']!=cohort:continue
            stamp=e['manifest'].get('started_at_utc')
            if stamp:
                try:times.append(Decimal(str(datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp())))
                except ValueError:pass
        current=Decimal(str(datetime.now(timezone.utc).timestamp() if now is None else now))
        by_cohort[cohort]={'expected':len(expected),'completed':len(done),'valid':valid,'failed':len(done)-valid,'corrupt':len(invalid),'pending':pending,
            'progress_pct':Decimal(len(done))*100/len(expected),'valid_pct':Decimal(valid)*100/len(expected),
            'elapsed_calendar_seconds':max(Decimal(0),current-min(times)) if times else None,
            'eta_seconds_approx':unit*pending,'eta_nominal_lower_bound_seconds':nominal*pending,'observed_repetition_seconds_median':median(observed) if observed else None,
            'eta_warning':'Approximate; preparation, host cache attestation, failures and interruptions may add time. Calendar includes pauses.',
            'current_unconfirmed':sorted(active,key=lambda a:a.get('started_epoch',Decimal(0)))[-1:] ,
            'latest':[{'scenario_id':r.scenario.id,'engine':r.scenario.engine,'query':r.scenario.query,'variant':r.scenario.variant,'status':r.row['status'],'valid':r.valid,'timestamp_epoch':r.row['timestamp_epoch']} for r in sorted(rows,key=lambda r:Decimal(r.row['timestamp_epoch']))[-5:]]}
    return {'scope':snapshot.scope,'validity_label':'Válidas solo para diagnóstico piloto; válidas académicas=0' if snapshot.scope=='pilot' else 'Validez según protocolo declarado y evidencia confirmada; revisar alcance de auditoría','counts_are_per_cohort':True,'cohorts':by_cohort,'matrix':plan['matrix'],'full_matrix':plan['full_matrix'],
            'nominal_base_seconds':108*420,'nominal_extended_seconds':162*420,'time_budget_seconds':13*3600,
            'budget_note':'La base requiere 12h36 y deja solo 24min para TODOS los sobrecostes/reporte; la extendida requiere 18h54 y excede 13h. El protocolo no cambia.'}


def terminal(value):
    def duration(seconds):
        if seconds is None:return 'No registrado'
        seconds=int(seconds);return f'{seconds//3600:02}:{seconds%3600//60:02}:{seconds%60:02}'
    lines=[f"Matriz: {value['matrix']} | Alcance: {value['scope']} | conteos independientes por cohorte",value['validity_label']]
    for cohort,c in value['cohorts'].items():
        lines += ['',f'Cohorte {cohort}',
          f"Esperadas {c['expected']} | Terminadas {c['completed']} | Válidas {c['valid']} | Fallidas {c['failed']} | Pendientes {c['pending']}",
          f"Avance {c['progress_pct']:.2f}% | válidas {c['valid_pct']:.2f}% | corruptas {c['corrupt']}",
          'Transcurrido calendario '+duration(c['elapsed_calendar_seconds'])+' | ETA aproximada '+duration(c['eta_seconds_approx'])+' | mínimo nominal '+duration(c['eta_nominal_lower_bound_seconds'])]
        active=c['current_unconfirmed']
        lines.append('Último escenario sin commit: '+str(active[-1].get('scenario',active[-1]['scenario_id']))+' (activo o interrumpido, no confirmado)' if active else 'Escenario actual: sin inicio no confirmado disponible')
        for row in c['latest']:lines.append(f"Último: {row['engine']} {row['query']} {row['variant']} {row['scenario_id']} status={row['status']} válido={row['valid']}")
    lines += ['',value['budget_note'],'ETA orientativa: preparación, caché, drenaje, errores y pausas pueden aumentar el tiempo.']
    return '\n'.join(lines)
