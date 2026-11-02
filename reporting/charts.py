"""Static scientific plots; Decimal converts to float only for plotting coordinates."""
from pathlib import Path
import math

def segments(points,max_gap=2.5):
    output=[]
    for x,y in points:
        x,y=float(x),float(y)
        if output and x-output[-1][0]>max_gap:output.append((math.nan,math.nan))
        output.append((x,y))
    return output

def create_charts(groups,directory,scope,test_only=False,comparisons=()):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    images=[];missing=[];banner='SIMULADO / SOLO PRUEBAS' if test_only else 'PILOTO REAL / NO DEFINITIVO' if scope=='pilot' else 'RESULTADOS DISPONIBLES / COBERTURA EN REPORTE'
    facets=sorted({(g['cohort'],g['query'],g['variant'],g['engine']) for g in groups})
    for index,(cohort,query,variant,engine) in enumerate(facets):
        subset=[g for g in groups if (g['cohort'],g['query'],g['variant'],g['engine'])==(cohort,query,variant,engine)]
        observed=[g for g in subset if g['n_valid']]
        if not observed:continue
        fig,ax=plt.subplots(figsize=(8.5,4.6),layout='constrained')
        for profile in ('baseline','medium','severe'):
            vals={g['concurrency']:g['statistics']['latency_p99_ms']['median'] for g in observed if g['profile']==profile}
            if vals:ax.plot([1,10,50],[float(vals[c]) if c in vals else math.nan for c in (1,10,50)],marker='o',label=engine+' / '+profile+' / '+variant)
        ax.set(xticks=[1,10,50],xlabel='Clientes concurrentes',ylabel='Mediana del P99 por repetición (ms)',title=f'{banner}\nP99 vs concurrencia — {query} / {variant} / cohorte {cohort[:8]}')
        ax.grid(alpha=.25);ax.legend(fontsize=8)
        filename=f'p99-{index:03}.png';fig.savefig(directory/filename,dpi=160);plt.close(fig)
        images.append({'file':'figures/'+filename,'caption':f'P99 {engine}/{query}/{variant}; mediana de P99 de repeticiones válidas, no P99 combinado. Huecos no conectados.'})
        fig,ax=plt.subplots(figsize=(8.5,4.6),layout='constrained')
        for profile in ('baseline','medium','severe'):
            rows=[r for g in observed if g['profile']==profile for r in g['records']]
            if rows:ax.scatter([float(r.row['throughput_qps']) for r in rows],[float(r.row['cpu_throttled_seconds']) for r in rows],label=engine+' / '+profile+' / '+variant,alpha=.8)
        ax.set(xlabel='Throughput (consultas/s)',ylabel='Throttling observado (s)',title=f'{banner}\nThrottling vs QPS — {query} / {variant} / cohorte {cohort[:8]}')
        ax.grid(alpha=.25);ax.legend(fontsize=8)
        filename=f'throttling-{index:03}.png';fig.savefig(directory/filename,dpi=160);plt.close(fig)
        images.append({'file':'figures/'+filename,'caption':f'Throttling frente a QPS {engine}/{query}/{variant}: un punto por repetición válida; sin inferencia causal.'})
    cross={}
    for c in comparisons:
        if c['status']=='COMPARABLE':cross.setdefault((c['cohort'],c['profile'],c['query'],c['mongo_variant'],c['postgres_variant']),set()).add(c['concurrency'])
    for index,(key,clients) in enumerate(sorted(cross.items())):
        cohort,profile,query,mongo_variant,postgres_variant=key
        fig,ax=plt.subplots(figsize=(8.5,4.6),layout='constrained')
        for engine,variant in [('mongo',mongo_variant),('postgres',postgres_variant)]:
            vals={g['concurrency']:g['statistics']['latency_p99_ms']['median'] for g in groups if g['cohort']==cohort and g['engine']==engine and g['profile']==profile and g['query']==query and g['variant']==variant and g['concurrency'] in clients}
            ax.plot([1,10,50],[float(vals[c]) if c in vals else math.nan for c in (1,10,50)],marker='o',label=engine+' / '+profile+' / '+variant)
        ax.set(xticks=[1,10,50],xlabel='Clientes concurrentes',ylabel='Mediana del P99 por repetición (ms)',title=banner+'\nContraste '+query+' / '+profile+' / cohorte '+cohort[:8])
        ax.grid(alpha=.25);ax.legend(fontsize=8)
        filename=f'comparison-{index:03}.png';fig.savefig(directory/filename,dpi=160);plt.close(fig)
        images.append({'file':'figures/'+filename,'caption':'Contraste descriptivo solo donde ambos motores tienen 3/3 repeticiones válidas. Pareja Q2 explícita no implica buffers equivalentes.'})
    for index,g in enumerate(groups):
        curves=[r for r in g['records'] if r.rss]
        label=f"{g['engine']} / {g['profile']} / {g['query']} / {g['variant']} / c={g['concurrency']} / {g['cohort'][:8]}"
        if not curves:
            if g['n_valid']:missing.append('RSS temporal ausente: '+label+'; no se fabrica curva con max_rss_mb.')
            continue
        fig,ax=plt.subplots(figsize=(8.5,4.6),layout='constrained')
        for r in curves:
            points=segments(r.rss);ax.plot([p[0] for p in points],[p[1] for p in points],marker='.',label=f'{g["engine"]} / run {r.scenario.run_number}')
        ax.set(xlabel='Tiempo desde inicio de medición (s)',ylabel='RSS observado (MB decimales)',title=banner+'\nRSS — '+label)
        ax.grid(alpha=.25);ax.legend(fontsize=8)
        filename=f'rss-{index:03}.png';fig.savefig(directory/filename,dpi=160);plt.close(fig)
        images.append({'file':'figures/'+filename,'caption':'Serie RSS real de '+label+'. Picos entre muestras no observables; gaps mayores a 2.5s no conectados.'})
    if not images:missing.append('No hay mediciones válidas para gráficas. No se dibujan valores cero ni curvas inventadas.')
    return images,missing
