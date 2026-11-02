"""Seven-section report model and versioned, immutable output bundles."""
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal
import hashlib,uuid,importlib.metadata,sys
from benchmark.results import write_json,immutable_write,file_hash
from benchmark.config import plain,digest
from benchmark.matrix import PROFILES
from queries.definitions import QueryBlocked
from . import REPORTING_VERSION
from .progress import progress
from .statistics import groups,comparisons,METRICS
from .charts import create_charts
TITLES=[
 'Especificaciones del host y entorno Docker','Método de medición y baseline','Resultados consolidados',
 'Análisis gráfico','Planes de ejecución','Interpretación de los resultados','Recomendaciones técnicas']
UNITS={'throughput_qps':'consultas/s','latency_p50_ms':'ms','latency_p95_ms':'ms','latency_p99_ms':'ms','cpu_throttled_seconds':'s observados','max_rss_mb':'MB decimales'}

def fmt(v):
    if v is None:return 'No disponible'
    if isinstance(v,Decimal):return format(v,'.7g')
    if isinstance(v,bool):return 'Sí' if v else 'No'
    if isinstance(v,(dict,list,tuple)):
        from src.dataset.model import json_text
        return json_text(plain(v))
    return str(v)

def readiness(snapshot,plan,grouped,plans):
    p=progress(snapshot,plan)
    reasons=[]
    if snapshot.integrity!='all':reasons.append('Se requiere auditoría completa de hashes para informe final')
    if plan['matrix']=='extended':reasons.append('P-02: matriz extendida pendiente de aprobación académica, no se declara experimento final aprobado')
    if snapshot.scope!='definitive':reasons.append('Pilotos: excluidos del experimento académico definitivo')
    if not plan['full_matrix']:reasons.append('La selección no constituye una matriz base/extendida completa')
    if len(p['cohorts'])!=1:reasons.append('Varias cohortes incompatibles: no se suman para completar una matriz')
    for cohort,c in p['cohorts'].items():
        if c['pending'] or c['failed'] or c['valid']!=c['expected']:reasons.append(cohort+': repeticiones pendientes/fallidas/no válidas')
    if not all(g['triplicate_complete'] for g in grouped):reasons.append('Hay escenarios sin tres repeticiones válidas')
    if any(not r.rss for r in snapshot.records if r.valid):reasons.append('Faltan series RSS verificables para algunas repeticiones')
    for experiment in snapshot.experiments:
        data=experiment['manifest']['configuration'].get('dataset',{})
        required={(s.engine,s.query,s.variant) for s in plan['scenarios']}
        linked={(p['engine'],p['query'],p['variant']) for p in plans if p.get('dataset_sha256')==data.get('sha256') and p.get('dataset_count')==data.get('count') and p.get('dataset_binding',{}).get('status')=='ok' and p.get('dataset_binding',{}).get('mode')=='full' and p.get('dataset_binding',{}).get('source_sha256')==data.get('sha256') and p.get('effective',{}).get('server_version')==experiment['manifest']['configuration'].get('identities',{}).get(p['engine'],{}).get('server_version') and p['summary']['nodes']}
        if not required<=linked:reasons.append('Faltan planes diagnósticos vinculados explícitamente al hash del dataset/consulta/variante')
    if not snapshot.experiments:reasons.append('No hay experimentos medidos')
    return {'ready':not reasons,'reasons':list(dict.fromkeys(reasons)),'progress':p,'extended_approval':'PENDING' if plan['matrix']=='extended' else 'not inferred'}

def paragraph(text):return {'type':'p','text':text}
def table(headers,rows):return {'type':'table','headers':headers,'rows':[[fmt(x) for x in row] for row in rows]}

def model(snapshot,plan,grouped,compared,plans,images,missing,state,ready,personal=None,environment=None):
    personal=personal or {};sections=[{'number':i+1,'title':t,'blocks':[]} for i,t in enumerate(TITLES)]
    def add(n,*blocks):sections[n-1]['blocks'].extend(blocks)
    add(1,paragraph('Plataforma objetivo declarada por el usuario: Kubuntu Linux nativo x86_64, Ryzen 7 5700X, 32 GB RAM. La versión exacta de Kubuntu no se presume. Los valores observados abajo provienen de manifiestos/evidencias, no del equipo que genera el reporte.'))
    host_rows=[]
    for exp in snapshot.experiments:
        c=exp['manifest']['configuration'];h=c.get('host',{});cid=exp['cohort']
        for k,label in [('os','Sistema operativo registrado'),('kernel','Kernel'),('cpu_model','Procesador'),('memory_total_kib','RAM registrada (KiB)'),('architecture','Arquitectura'),('cgroup_v2_visible','cgroups v2 visibles'),('boot_id','Boot ID')]:host_rows.append([cid,label,h.get(k),'manifiesto de ejecución'])
        host_rows.extend([[cid,'Versión Kubuntu','No verificada como Kubuntu' if h.get('os',{}).get('ID')!='kubuntu' else h['os'].get('VERSION_ID'),'no sustituir versión Ubuntu por prueba del sabor Kubuntu'],[cid,'Docker Engine/Compose','No registrados en este manifiesto','captura independiente opcional, no inferidos desde imagen']])
        for engine,identity in c.get('identities',{}).items():host_rows.append([cid,engine,identity,'versión/imagen observadas por runner'])
        probes=[r.evidence.get('probe',{}) for r in snapshot.records if r.experiment_id==exp['id'] and r.evidence]
        if probes:
            for field,label in [('prometheus_build','Prometheus observado'),('exporter_builds','Exportadores observados')]:host_rows.append([cid,label,probes[-1].get(field),'evidencia de telemetría'])
    add(1,table(['Cohorte','Dato','Valor','Procedencia'],host_rows) if host_rows else paragraph('No hay condiciones de ejecución verificadas disponibles. El hardware declarado no constituye medición.'))
    if environment:add(1,paragraph('Captura ambiental independiente aportada: '+fmt(environment)+'. Su fecha y boot_id no prueban retrospectivamente las versiones durante cada medición.'))
    add(1,table(['Perfil','CPU','Memoria configurada','Estado'],[[v[0],v[1],str(v[2])+' MiB Docker','Solicitado; ver snapshots efectivos por repetición'] for v in PROFILES.values()]))
    add(2,paragraph('Objetivo: comparar agregaciones JSON equivalentes bajo contención controlada. Fuentes: playbook.pdf pp.1–4 §§1–8 y playbook_sesion.pdf pp.3–11. M1: cambios en P95/P99 al limitar CPU/memoria. M2: gestión de buffers antes de spill/OOM. M3: huella CPU/memoria por 1000 documentos; operacionalización pendiente, no se calcula con throttling como CPU consumida.'),
        paragraph('Contrato: 500000 órdenes JSON anidadas, media objetivo de tres ítems; Q1 desanida, filtra price>50 y agrupa qty×price por país/categoría; Q2 completed y timestamp>=2026-01-01 UTC, total descendente, Top-1000. Alias de pagos/tipos/índice temporal y adaptación swap siguen documentados como provisionales; no se declaran aprobados por este generador.'),
        paragraph('Protocolo original: limpieza de caché, warmup 60s, medición 300s, cooldown 60s; concurrencias 1/10/50; tres repeticiones. Se registran variantes Q2 por manifiesto, sin modificar el CSV. La constancia manual de caché es declaración del operador, no prueba automática del estado del kernel.'),
        paragraph('Runner: sesiones independientes, consumo completo de resultados y reloj monotónico. QPS=éxitos íntegramente dentro de ventana/duración fija; cruces de borde, errores, warmup/cooldown excluidos. Percentiles de cada repetición: Hyndman–Fan R7 exacto en disco. Las medias/medianas de esos P99 NO son P99 combinado de latencias individuales.'),
        paragraph('Telemetría: Prometheus/cAdvisor/Node Exporter con scrape 1s; throttling=last−first de muestras interiores (subintervalo observado, bordes omitidos), RSS máximo observado/1000000. Spill y OOM requieren evidencia específica. Los OOM de estado Docker posterior pueden acreditar solo el intento, no la ventana de 300s; los conteos agrupan repeticiones afectadas y debe revisarse su alcance en evidencia. Un máximo RSS no permite fabricar curva temporal. Instrumentación y análisis añaden carga al host: este análisis no consulta motores ni adquiere locks del runner; ejecutar fuera de ventanas sensibles/en otro equipo si se quiere evitar interferencia CPU/IO.'),
        paragraph('Tiempo disponible declarado: 13h. Base 108×420s=12h36, deja SOLO 24min para toda preparación, flush, drenaje, fallos y reporte. Extendida 162×420s=18h54, excede el presupuesto aun sin sobrecostes y continúa pendiente de aprobación. No se reduce el protocolo para ajustarlo.'))
    for exp in snapshot.experiments:add(2,paragraph('Configuración observada '+exp['id']+': dataset '+fmt(exp['manifest']['configuration'].get('dataset'))+'; protocolo '+fmt(exp['manifest']['configuration'].get('protocol'))+'; versión runner '+fmt(exp['manifest']['configuration'].get('runner_version'))+'.'))
    add(3,paragraph('Resúmenes descriptivos exclusivamente de repeticiones válidas dentro de cada cohorte/motor/perfil/consulta/variante/concurrencia. Media, mediana, mínimo y máximo son de KPIs por repetición; no se mezclan muestras crudas ni modalidades. En pilotos, “válida” significa solo diagnóstico técnico, nunca elegibilidad académica. Presentación con hasta siete cifras significativas; statistics.json conserva los decimales de cálculo.'))
    progress_rows=[]
    for cohort,c in ready['progress']['cohorts'].items():progress_rows.append([cohort,c['expected'],c['completed'],c['valid'],c['failed'],c['pending'],c['progress_pct'],c['eta_seconds_approx']])
    add(3,table(['Cohorte','Esperadas','Terminadas','Válidas','Fallidas','Pendientes','Avance %','ETA aproximada s'],progress_rows))
    add(3,table(['Cohorte','Motor','Perfil','Q','Variante','Clientes','Válidas/3','Spill confirmado','OOM confirmado','Estado'],[[g['cohort'],g['engine'],g['profile'],g['query'],g['variant'],g['concurrency'],str(g['n_valid'])+'/3',g['spill_confirmed'],g['oom_confirmed'],g['status']] for g in grouped]))
    for metric in METRICS:
        add(3,{'type':'sub','text':metric+' ('+UNITS[metric]+') — entre repeticiones'},table(['Cohorte / motor / perfil / consulta / variante / clientes','n','Media','Mediana','Mínimo','Máximo'],[[f"{g['cohort']} / {g['engine']} / {g['profile']} / {g['query']} / {g['variant']} / {g['concurrency']}",g['statistics'][metric]['n'],*[g['statistics'][metric][k] for k in ('mean','median','min','max')]] for g in grouped if g['n_valid']]))
    add(3,table(['Cohorte','Q/perfil/clientes','Pareja de modalidades','Comparación','Razón'],[[c['cohort'],str(c['query'])+'/'+c['profile']+'/'+str(c['concurrency']),str(c.get('mongo_variant'))+' : '+str(c.get('postgres_variant','sin pareja')),c['status'],c.get('reason',c.get('caution'))] for c in compared]))
    good=[c for c in compared if c['status']=='COMPARABLE']
    for c in good:add(3,paragraph('Contraste descriptivo '+fmt({k:v for k,v in c.items() if k!='differences'})),table(['KPI de mediana','Diferencia PG−Mongo','Diferencia % respecto a Mongo','Nota'],[[m,v['absolute'],v['percent'],v['reason']] for m,v in c['differences'].items()]))
    add(4,paragraph('P99 frente a concurrencia usa mediana del P99 de repeticiones válidas. Throttling/QPS usa puntos por repetición. RSS usa muestras temporales originales verificadas, con tiempo relativo al inicio y huecos explícitos. Cohortes/modalidades se separan; las comparaciones entre motores requieren pareja equivalente y tres repeticiones por cada motor.'))
    for image in images:add(4,{'type':'image',**image})
    for text in missing:add(4,paragraph(text))
    if not plans:add(5,paragraph('PENDIENTE: no se proporcionaron planes reales. No se ejecuta EXPLAIN ni se inventan operaciones/índices/tiempos.'))
    for p in plans:
        add(5,paragraph('Plan diagnóstico '+p['path']+' — '+str(p['engine'])+'/'+str(p['query'])+'/'+str(p['variant'])+'; dataset registrado='+fmt(p['dataset_count'])+'; hash vinculado='+fmt(p.get('dataset_sha256'))+'. '+p['note']),table(['Ruta nodo','Operaciones/índices/sort/grupos/filas/buffers/temporales (campos disponibles)'],[[n.get('path'),{k:v for k,v in n.items() if k!='path' and v is not None}] for n in p['summary']['nodes']]))
    add(5,paragraph('Campos ausentes permanecen desconocidos. Actual Rows/Actual Loops se muestran separadamente, no se suman como documentos procesados M3. EXPLAIN ANALYZE y executionStats ejecutan una consulta diagnóstica; su tiempo no sustituye latencia del runner ni acredita spill de otra ejecución. Planes sin dataset/variante vinculados se presentan como auxiliares, no equivalentes al escenario medido.'))
    add(6,{'type':'sub','text':'Conclusiones e interpretación'},paragraph('M3 NO CALCULABLE: faltan metodología aprobada para documentos procesados y consumo de CPU usado/normalización de memoria. El conteo del archivo fuente no equivale a documentos procesados por cada consulta; throttling no es CPU usada.'))
    if not good:add(6,paragraph('PENDIENTE: no hay comparaciones entre motores con tres repeticiones válidas equivalentes. Los resultados disponibles solo describen las filas observadas; no permiten declarar un motor superior ni efectos causales de recursos/concurrencia.'))
    for c in good:
        d=c['differences'];add(6,paragraph('Bajo las condiciones registradas en cohorte '+c['cohort']+' / '+c['query']+' / '+c['profile']+' / clientes '+str(c['concurrency'])+', la diferencia descriptiva PG−Mongo de mediana de QPS es '+fmt(d['throughput_qps']['absolute'])+' consultas/s y de mediana del P99 es '+fmt(d['latency_p99_ms']['absolute'])+' ms. No demuestra causalidad, significancia estadística ni superioridad global; n=3 por motor.'))
    add(6,paragraph('Limitaciones: repeticiones incompletas indicadas, muestreo 1s no captura todos los picos, bordes de throttling omitidos, cambios de host/código segregados, instrumentación/runner compiten por recursos del host y constancias de caché no prueban buffers internos. Una asociación throughput/throttling o incremento de percentiles no identifica por sí sola una causa. La extensión 162 no se aprueba por poder generar este documento.'))
    deviations=sorted({str(d) for r in snapshot.records for d in r.meta.get('deviations',[])})
    for d in deviations:add(6,paragraph('Desviación registrada: '+d))
    add(7,paragraph('Recomendaciones generales (no derivadas de un ganador experimental): verificar límites reales/ancestros y salud; dimensionar memoria por operación y número de clientes; vigilar throttling, RSS, temporales y OOM; conservar datos originales/versiones; realizar piloto antes de la matriz; no asumir equivalencia de cachés/buffers internos ni de permisos de observabilidad. Son criterios operativos, no conclusiones comparativas de este estudio.'),paragraph('Recomendaciones específicas: '+('Las diferencias de la sección 3 sirven para priorizar validaciones en esos escenarios, con alcance limitado al dataset/host/modalidades observados. Repetir y revisar planes antes de generalizar a despliegues en nube.' if good else 'PENDIENTES de comparaciones válidas. No se recomienda MongoDB o PostgreSQL JSONB como superior en rendimiento/estabilidad sin evidencia equivalente.')))
    annex=[paragraph('Estado solicitado/efectivo: '+state+'. Cobertura se calcula por cohorte, no sumando datasets o versiones incompatibles.'),paragraph('Validación para informe final: '+fmt(ready['reasons'])),paragraph('Integridad: '+snapshot.integrity+'; selected verifica hashes de JSON/CSV usados y existencia del resto; all verifica también journals binarios, sin copiarlos masivamente al reporte. Un commit nuevo posterior al corte se verá en la siguiente generación.')]
    failures=[[r.experiment_id,r.scenario.id,r.row['status'],'; '.join(r.reasons)] for r in snapshot.records if not r.valid]
    failures += [[v['experiment_id'],v['scenario_id'],'CORRUPTO',v['reason']] for v in snapshot.invalid]
    annex.append(table(['Experimento','Escenario','Estado','Causa de exclusión'],failures))
    annex.append(paragraph('Intentos no confirmados (pueden estar activos o interrumpidos; no se infiere actividad por existencia del lock): '+fmt(snapshot.unfinished)))
    annex.append(paragraph('Fuentes preservadas por hash en snapshot/index.json; request.json/statistics.json/coverage.json/analysis-manifest.json permiten auditar entradas y cálculos. No contienen credenciales ni copias del dataset.'))
    return {'title':'MongoDB frente a PostgreSQL JSONB bajo contención de CPU y memoria','university':'Universidad Politécnica de Chiapas','course':'Bases de Datos en la Nube — Ingeniería en Tecnologías de la Información e Innovación Digital',
            'date':datetime.now(timezone.utc).date().isoformat(),'student':personal.get('student') or '[Por completar]','group':personal.get('group') or '[Por completar]','teacher':personal.get('teacher') or '[Por completar]',
            'state':state,'banner':'SIMULADO: SOLO PRUEBAS DE SOFTWARE' if snapshot.test_only else 'PILOTO REAL — NO RESULTADOS ACADÉMICOS DEFINITIVOS' if snapshot.scope=='pilot' else 'INFORME PARCIAL — RESULTADOS PRELIMINARES' if state!='FINAL' else 'INFORME FINAL — MEDICIONES VALIDADAS Y COBERTURA DOCUMENTADA',
            'sections':sections,'annex':annex}

def generate(snapshot,plan,output,*,mode='partial',allow_partial=False,plans=(),q2_pairs=(),personal=None,pdf=False,environment=None):
    grouped=groups(snapshot,plan);compared=comparisons(grouped,q2_pairs);ready=readiness(snapshot,plan,grouped,plans)
    if mode=='final' and not ready['ready'] and not allow_partial:raise QueryBlocked('Final report BLOCKED: '+'; '.join(ready['reasons'])+'. Use --mode partial or --allow-partial to label honestly.')
    state='FINAL' if mode=='final' and ready['ready'] else 'PARTIAL'
    if snapshot.test_only:state='TEST_'+state
    if snapshot.scope=='pilot':state='DIAGNOSTIC_PARTIAL'
    output=Path(output).resolve()
    if any(output.is_relative_to(Path(e['root'])) for e in snapshot.experiments):raise QueryBlocked('Report output must be outside original experiment directories')
    output.mkdir(parents=True,exist_ok=True)
    folder=output/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:10]);folder.mkdir()
    write_json(folder/'build-started.json',{'reporting_version':REPORTING_VERSION,'scope':snapshot.scope,'requested_mode':mode,'state':state})
    snapdir=folder/'snapshot';snapdir.mkdir();index=[]
    for source,entry in sorted(snapshot.files.items()):
        suffix=Path(source).suffix;name=entry['sha256']+suffix;target=snapdir/name
        if not target.exists():target.write_bytes(entry['bytes'])
        index.append({'source':source,'sha256':entry['sha256'],'snapshot_file':'snapshot/'+name})
    write_json(snapdir/'index.json',index)
    images,missing=create_charts(grouped,folder/'figures',snapshot.scope,snapshot.test_only,compared)
    doc=model(snapshot,plan,grouped,compared,plans,images,missing,state,ready,personal,environment)
    from .exporters import markdown,html,pdf_document
    immutable_write(folder/'reporte.md',markdown(doc));immutable_write(folder/'reporte.html',html(doc))
    write_json(folder/'coverage.json',ready)
    write_json(folder/'statistics.json',{'groups':[{k:v for k,v in g.items() if k!='records'} for g in grouped],'comparisons':compared,
        'note':'Statistics of repetition-level KPIs, not pooled sample percentiles; Decimal calculations retained'})
    write_json(folder/'request.json',{'mode':mode,'scope':snapshot.scope,'plan':{'matrix':plan['matrix'],'full_matrix':plan['full_matrix'],'scenarios':[asdict(s) for s in plan['scenarios']]},'q2_pairs':list(q2_pairs),'captured_at':snapshot.captured_at})
    warnings=list(missing)
    if pdf:
        try:
            draft=folder/'.pdf-building.tmp';pdf_document(doc,folder,draft);draft.rename(folder/'reporte.pdf')
        except ImportError:warnings.append('PDF unavailable: install optional requirements-reporting-pdf.txt; HTML remains printable')
        except Exception as exc:warnings.append('PDF export failed: '+type(exc).__name__+'; HTML/Markdown remain available, partial temporary PDF is not published')
    versions={p:importlib.metadata.version(p) for p in ('matplotlib','numpy')}
    for package in ('pillow','reportlab'):
        try:versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:pass
    versions['python']=sys.version
    hashes={str(p.relative_to(folder)):file_hash(p) for p in folder.rglob('*') if p.is_file()}
    write_json(folder/'analysis-manifest.json',{'reporting_version':REPORTING_VERSION,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'state':state,'ready':ready['ready'],'test_only':snapshot.test_only,'versions':versions,'warnings':warnings,'files':hashes,
         'reporter_sources':{str(p.relative_to(Path(__file__).resolve().parents[1])):file_hash(p) for p in sorted(Path(__file__).parent.rglob('*')) if p.is_file() and '__pycache__' not in p.parts},'source_fingerprint':digest({k:v['sha256'] for k,v in snapshot.files.items()}),'official_csv_unchanged':True})
    return folder
