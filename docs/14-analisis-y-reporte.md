# Análisis estadístico y reporte automático — Fase 6

U8 autoriza exclusivamente análisis/reportes, no Fase 7 ni mediciones definitivas. Fuentes: P p.4 §8.3 (siete secciones), P p.3 §§6–7 (matriz/ciclo/KPIs), S pp.8–11 (CSV/estados/evidencia), U8 §§3–16. No se modificaron consultas, dataset, perfiles ni protocolo. La arquitectura usa los archivos del runner existente; no crea otro benchmark ni consulta bases al generar reportes.

## Instalación y dependencias

Python >=3.11 por NumPy fijado; Cloud validado con Python 3.12.14, Matplotlib 3.10.8, NumPy 2.3.5. Dependencias/transitivas explícitas en requirements-reporting.txt. ReportLab 4.4.9 y charset-normalizer 3.5.2 son opcionales para PDF, en requirements-reporting-pdf.txt. No hay servicios nuevos ni dependencias de Windows/WSL2. La versión Python/Kubuntu local sigue pendiente. Crear un venv sin instalación privilegiada:

```bash
python3 -m venv .local/analisis-venv
.local/analisis-venv/bin/python -m pip install -r requirements-reporting.txt
# Opcional PDF:
.local/analisis-venv/bin/python -m pip install -r requirements-reporting-pdf.txt
export REPORTING_PYTHON="$PWD/.local/analisis-venv/bin/python"
./scripts/generate_report.sh --help
```

Para ejecutar toda la regresión del proyecto en ese mismo venv añadir requirements-benchmark.txt; reporting/progress no se conectan a motores. Progreso/validación básica usan stdlib; generación de gráficas requiere Matplotlib. HTML es imprimible aunque falte PDF; no se instala Chromium ni dependencias pesadas automáticamente. PDF usa fuente DejaVu si existe y Helvetica como fallback; verificar representación local. HTML/Markdown y los cálculos no dependen del renderizador PDF.

## Entradas, snapshots e integridad

Entrada preferida: directorio de experimento con experiment.json y subdirectorios escenario/attempt-UUID/commit.json, results.csv, result.json, started.json, preflight.json y evidencia. También se acepta ruta a results.csv si se encuentra su experimento completo entre sus padres. Un directorio padre inmediato puede contener varios experimentos. No se asume ruta fija. Un CSV consolidado sin configuración experimental no basta para inferir dataset/protocolo/variante: usar los experimentos originales; --csv solo comprueba esquema.

El loader congela la lista de commits por experimento, lee archivos estables y verifica hashes de JSON/CSV necesarios, marcador, identidad/variante/protocolo, tipos y concordancia de métricas. Comprueba existencia de todos los artefactos declarados. Un commit nuevo posterior al corte se verá la próxima vez; started sin commit no es terminado. No adquiere .lock, escribe en entradas, repara archivos ni consulta Mongo/PostgreSQL/Prometheus. Un commit corrupto se excluye y cuenta como terminado fallido/corrupto; manifiesto raíz ilegible, duplicados o identidades ambiguas bloquean la selección para evitar adivinar.

Integridad selected (parcial/progreso): hashes de metadatos/CSV/series usados y existencia del resto; no rehash masivo de diarios SQLite. Integridad all (--audit-all, automático con --mode final): hash de todos los artefactos, incluidos diarios. Esta distinción se imprime en anexos. Los archivos no usados no se dan por auditados criptográficamente en selected. El reporte copia metadatos/CSV/planes/series seleccionados a snapshot/ por contenido, con index.json de origen/hash; no copia journals masivos. Para repetir auditoría completa desde otro equipo, copiar los directorios experimentales completos conservando su estructura relativa, no solo HTML/CSV sueltos.

Cada generación crea una carpeta nueva con UUID y conserva versiones anteriores. analysis-manifest.json es el marcador de construcción terminada con hashes, versión/fuentes del generador y versiones de dependencias; una carpeta sin ese marcador quedó incompleta. Los originales nunca se sobrescriben. Las rutas relativas CLI se resuelven desde el directorio del usuario, aunque se invoque el script por ruta absoluta.

## Matrices y cohortes

Base: 36 celdas/108 repeticiones; requiere elegir explícitamente variante Mongo Q2 y PostgreSQL Q2. Extendida: 54/162, ambas modalidades, **P-02 pendiente de aprobación**; esta versión no la etiqueta como experimento académico final aprobado. Selecciones individuales pueden describirse, pero no sustituyen cobertura de la matriz.

Auto reconoce base/extendida desde el manifiesto y reconstruye su matriz completa incluso si el runner seleccionó un bloque filtrado. Si todos los planes son individuales, auto muestra la unión de la selección, que no acredita estudio completo; usar --matrix base con ambas variantes o --plan para medir avance contra 108. El plan JSON puede ser la salida de run_benchmarks.sh plan: valida IDs/duplicados y nunca inicia mediciones.

Cohortes separan dataset/configuración/hash, protocolo, host/boot, fuentes del código, drivers, versión runner, configuración de monitoreo y política de matriz/base Q2. No se suman cohortes incompatibles para completar 108/162. Cambios de imagen/versión de un mismo motor dentro de una cohorte se rechazan. Misma repetición duplicada entre experimentos/intentos también se rechaza; el usuario debe seleccionar entradas autorizadas sin ocultar reintentos fallidos. Un intento incompleto anterior queda como historia cuando el mismo escenario ya tiene commit válido en su experimento.

## Progreso y restricción de 13 horas

```bash
./scripts/benchmark_progress.sh --inputs results/definitive/estudio-base
./scripts/benchmark_progress.sh --inputs results/definitive/estudio-base --watch --interval 30
./scripts/benchmark_progress.sh --inputs /mnt/resultados/estudio-a /mnt/resultados/estudio-b --json
```

Muestra esperadas/terminadas/válidas/fallidas/pendientes, porcentaje de terminación y de validez, últimos resultados, calendario transcurrido y ETA aproximada. Los conteos son por cohorte. Válida en scope=pilot significa solo diagnóstico técnico; académicas=0. Fallida incluye commit corrupto o medición excluida; pendiente no tiene commit, aunque exista CSV parcial. Un estado started sin commit puede estar activo o interrumpido: no se inventa fase actual/heartbeat; su mtime puede cambiar al copiarlo. El calendario incluye pausas. ETA usa pendientes × máximo entre duración nominal configurada y mediana observada de spans de etapas terminadas; preparación, flush, fallos/pausas y carga pueden añadir más tiempo. No promete siete minutos exactos por repetición.

| Plan | Tiempo nominal 60/300/60 | Frente a 13h |
| --- | --- | --- |
| Base 108 | 12h36 | Solo 24min para TODA preparación, verificación, caché, drenaje y reporte |
| Extendida 162 | 18h54 | Excede 13h incluso sin sobrecostes; además no aprobada |

Preparación/importación y preflight completo pueden hacer inviable terminar la base en 13h. **No se acortan warmup/medición/cooldown ni se redefine la matriz para ocultarlo.** Si falta tiempo, entregar parcial con cobertura y limitaciones reales. La herramienta puede analizar desde otro equipo; en el mismo host sus lecturas/CPU/figuras agregan carga fuera del camino de consultas. Ejecutar después de bloques o en otro equipo para evitar contaminación adicional; no se promete impacto cero solo por ser readonly.

## Reporte parcial y actualización incremental

Ejemplo de planificación sin mediciones (las elecciones Q2 son explícitas de este comando, no aprobación del profesor):

```bash
./scripts/generate_report.sh generate --matrix base \
  --base-mongo-variant allow_disk_false --base-postgres-variant work_mem_4mb \
  --mode partial --output reports/avance-inicial --pdf
```

Con resultados reales, sin detener el runner:

```bash
./scripts/generate_report.sh generate --inputs results/definitive/estudio-base \
  --mode partial --plans evidencia/planes --output reports/estudio --pdf
# Actualizar solo al detectar nuevos commits/configuración de entrada:
./scripts/generate_report.sh generate --inputs results/definitive/estudio-base \
  --mode partial --output reports/estudio --watch --interval 60
# Rehacer tablas/gráficas como una nueva versión coherente del reporte:
./scripts/generate_report.sh charts --inputs results/definitive/estudio-base --output reports/estudio
```

--watch no reescribe una versión sin cambios; conserva versiones anteriores y termina con Ctrl-C. Cada versión usa un corte coherente de commits, sin leer CSV en construcción. No hace análisis costoso dentro de workers ni ejecuta EXPLAIN. La generación repetida de figuras puede consumir CPU/IO del host, por lo que se recomienda otro equipo si el benchmark sigue activo.

Diagnóstico explícito de pilotos (nunca se mezclan con definitivos):

```bash
./scripts/generate_report.sh generate --scope pilot --inputs results/pilots/piloto-telemetria \
  --mode partial --output reports/diagnostico-pilotos --pdf
```

Los informes/figuras llevan banner PILOTO REAL / NO DEFINITIVO y todas las filas siguen excluidas del estudio final, aunque tengan status=ok. Los reportes conservados en reports/piloto-real proceden de evidencia real pequeña de Fase 5; reports/academico-parcial tiene 0 mediciones definitivas, no datos simulados rellenados. Las versiones antiguas se conservan y pueden preceder a endurecimientos de validación; usar el último build terminado, cuyos hashes describen su código y entradas.

## Validación y final

```bash
./scripts/generate_report.sh validate --inputs results/definitive/estudio-base --audit-all
./scripts/generate_report.sh validate --csv /mnt/resultados/mediciones.csv
./scripts/generate_report.sh generate --inputs results/definitive/estudio-base \
  --mode final --plans evidencia/planes --output reports/entrega --pdf
# Si no alcanza cobertura/evidencia: generar documento marcado PARCIAL, no completo:
./scripts/generate_report.sh generate --inputs results/definitive/estudio-base \
  --mode final --allow-partial --plans evidencia/planes --output reports/entrega --pdf
```

validate --csv retorna SCHEMA_ONLY: comprueba 14 columnas/nombres/orden/tipos; no certifica variantes, procedencia ni estudio completo. validate con experimentos muestra exclusiones/readiness; PASS de filas no implica por sí solo cierre final. Con cero filas retorna NO_MEASUREMENTS. Código 2 indica selección/configuración/cierre bloqueado; 130 cancelación de watch. Generaciones parciales válidas retornan 0 sin fingir resultados finales.

Final exige: una cohorte definitiva, matriz completa, todas las repeticiones 1/2/3 válidas, auditoría all, protocolo/ventanas reales 60/300/60, dataset de 500000 con equivalencia completa de ambos, preflight/índices/perfil/variantes/clientes certificados, métricas obligatorias y elegibilidad del runner, sin errores/desviaciones, series RSS verificables y planes vinculados a dataset/consulta/variante/versión. Si falla, no etiqueta experimento completo; --allow-partial mantiene PARCIAL y explica cada condición. La versión final de software no sustituye aceptación académica ni validación física Fase 7.

## Planes de ejecución y cambio mínimo anterior

Se reutiliza queries/plans.py para resumir planes, nunca para lanzarlos desde análisis. La única modificación de código previo es query_tool.py: **explain --file** opcional reutiliza validate_file/compare_dataset para verificar íntegramente el archivo y contenido del motor antes del EXPLAIN original, y añade dataset_sha256/dataset_binding al JSON. Sin --file conserva la interfaz anterior. No cambia SQL/pipelines, runner, índices ni límites; unitarias mock de binding/error y regresión verifican el cambio. La rama nueva no se ejecutó contra Mongo/PG aquí: solo se leyeron diagnósticos reales anteriores. Se usa fuera de ventanas cronometradas y puede añadir preparación/lecturas relevantes al presupuesto.

Ejemplos futuros con datos congelados, **no durante la medición ni ejecutados en esta fase**:

```bash
mkdir -p evidencia/planes
./scripts/queries.sh explain --engine mongo --query Q1 --file data/orders.jsonl --report evidencia/planes/mongo-q1.json
./scripts/queries.sh explain --engine postgres --query Q1 --file data/orders.jsonl --report evidencia/planes/pg-q1.json
./scripts/queries.sh explain --engine mongo --query Q2 --variant allow_disk_false --file data/orders.jsonl --report evidencia/planes/mongo-q2-false.json
./scripts/queries.sh explain --engine postgres --query Q2 --variant work_mem_4mb --file data/orders.jsonl --report evidencia/planes/pg-q2-4mb.json
```

Guardar también otras modalidades si se autoriza su alcance; no aprobar 162 por crear planes. En el reporte, un plan sin hash/binding completo/count/versión correspondientes es auxiliar y no cierra evidencia final. La captura presupone ausencia de escritores, como Fases 2–3; no es snapshot distribuido atómico. Un nuevo EXPLAIN nunca demuestra el spill de una consulta cronometrada anterior. Se muestran nodos/índices/sort/grupo/filas/loops/buffers/temporales presentes; campos ausentes no son cero. Los planes de Fase 3 sobre 10 órdenes se incluyen como diagnósticos históricos explícitos, no como planes de 500000.

## Estadística, comparaciones y gráficas

Cada grupo fija cohorte, motor, perfil, consulta, variante y concurrencia. Se calculan media/mediana/min/max con Decimal sobre repeticiones válidas, no fallidas ni censuradas. “Mediana del P99 por repetición” y “media de P99” son estadísticos de KPIs; NO son un P99 combinado de latencias individuales. Se mantienen todos los n y estados; con n<3 se marca preliminar. statistics.json conserva precisión de cálculo; tablas presentan hasta siete cifras significativas, sin alterar CSV original.

Comparaciones requieren tres repeticiones por ambos motores bajo mismas condiciones. Diferencia absoluta=PG−Mongo; porcentaje=(PG−Mongo)/Mongo×100. Denominador cero deja porcentaje no calculable. Un signo positivo no significa automáticamente mejor rendimiento: depende del KPI. Q1 pareja default/default; Q2 nunca empareja automáticamente buffers distintos:

```bash
./scripts/generate_report.sh generate --inputs results/definitive/estudio-base --output reports/estudio \
  --q2-pair allow_disk_false:work_mem_4mb
```

La pareja explícita permite contraste descriptivo, no afirma equivalencia interna ni aprueba metodología pendiente. Variantes incompatibles y cohortes no se promedian. Si faltan escenarios o repeticiones, se muestra NOT_COMPARABLE. No hay prueba de causalidad, significancia estadística ni ganador global automático.

Gráficas Matplotlib/Agg: P99 vs concurrencia con NaN en clientes ausentes; throttling vs QPS por repetición; RSS vs segundos desde inicio usando muestras temporales originales verificadas, sin extender a toda ventana desde un máximo. Gaps >2.5s quedan desconectados. Títulos/leyendas incluyen motor/perfil/Q/variante/cohorte; overlays de motores solo cuando hay comparación 3/3 válida. Sin serie RSS se indica falta de evidencia; sin mediciones no se crea gráfica con ceros. M3 queda **NO CALCULABLE** hasta definir/medir CPU usada, documentos procesados y normalización de memoria; CSV throttling o count del archivo no los sustituyen.

## Formatos y auditoría

Siete secciones numeradas exactamente según P/U8, más portada/índice/anexos. Conclusiones quedan dentro de sección 6. HTML contiene campos editables de estudiante/grupo/docente, vacíos por defecto [Por completar]; no se inventa identidad personal. --student/--group/--teacher permiten rellenarlos explícitamente. HTML escapa texto y no carga scripts/CDN externos. Se imprime desde navegador en A4 horizontal; ReportLab opcional genera PDF del mismo modelo. Un fallo PDF no elimina HTML/Markdown; la advertencia se conserva y el PDF parcial no se publica.

Capture el entorno local en preparación, no durante consultas sensibles:

```bash
./scripts/generate_report.sh capture-environment --output evidencia/entorno-local.json
./scripts/generate_report.sh generate --inputs results/definitive/estudio-base --output reports/estudio --environment evidencia/entorno-local.json
```

Esa captura usa host_info y metadata Docker de solo lectura, sin inspect.Env ni credenciales. Se etiqueta como observación independiente con fecha/boot, no prueba retrospectiva de versiones durante medición. El host del analizador no sustituye silenciosamente al del benchmark. La versión Ubuntu no prueba por sí sola el sabor Kubuntu; lo no registrado queda explícito.

Salidas: reporte.html, reporte.md, reporte.pdf si está disponible, figures/, coverage.json, statistics.json, request.json, snapshot/index.json/entradas seleccionadas y analysis-manifest.json con hashes/dependencias/fuentes. Conservar directorios completos para figuras, aunque PDF sea portable. reports/README.md indica los builds de demostración entregados; solo hay pilotos reales y reporte académico vacío/parcial, nunca fixtures publicados.

## Pruebas y solución de problemas

```bash
.local/analisis-venv/bin/python -m pip install -r requirements-benchmark.txt
.local/analisis-venv/bin/python -m unittest discover -s tests -v
./tests/test_infrastructure.sh
```

Pruebas nuevas cubren CSV/manifiesto/variantes, integridad/corrupción, ventanas/clientes, estadísticas/porcentajes, 108/162, progreso/incremental/concurrencia con lock de runner sostenido sin adquirirlo, no duplicados/resume, cohortes, planes, salida parcial/final, plots/gaps, HTML escaping y fuentes sin cambios. Fixtures sintéticos solo en TemporaryDirectory con evidence_kind=simulated_reporting_test; CLI público los rechaza, API privada de tests fuerza banner SIMULADO/TEST_FINAL. No se incluyen esos outputs en ZIP. El gate completo 108 se prueba así, no como matriz real.

Regresión de Fases 1–5 disponible se ejecuta sin activar integraciones de motores; las 12 omitidas se distinguen de tests aprobados. Integración de análisis real usa CSV/manifiestos/series/planes ya conservados, sin arrancar servicios ni consultar motores. Handoff/evidencias enumeran comandos/conteos ejecutados. No se validó Kubuntu físico ni un reporte final sobre 108/162 mediciones definitivas inexistentes.

Errores comunes: CSV suelto sin sidecars, scope piloto/definitivo mezclado, raíz corrupta, duplicados, matriz elegida incompatible con filas observadas, dataset/versión/host distintos, evidencia sin hash o series faltantes, falta Matplotlib/PDF opcional, --output dentro del experimento, source plan sin vínculo real. Restaurar copia válida o seleccionar explícitamente entradas correctas; nunca editar resultados para hacer pasar un gate ni asumir datos faltantes.

## Referencia rápida para Fase 7 en Kubuntu (no ejecutada/autorizada aquí)

1. [Instalación y perfiles](09-instalacion-kubuntu.md): identificar Kubuntu/kernel/CPU/RAM, Engine/Plugin/cgroups2, espacio y controladores. setup_kubuntu.sh imprime pasos; check_environment.sh/verify_resources.sh/healthcheck.sh deben pasar para ambos motores/A–B–C. Resolver aceptación swap/versiones sin tratar :0 descartado como cumplimiento literal.
2. [Datos](10-generacion-y-carga-datos.md): configurar .env local, generar seed/configuración versionados 500000, importar ambos sin borrar y compare_data.sh completo. Conservar JSONL/manifiesto/hash fuera del respaldo pequeño.
3. [Consultas](11-consultas-y-validacion.md): validar Q1/Q2/variantes de ambos, índices aprobados y equivalencia real. P-03/P-06/P-19/P-24–26 no se resuelven por este reporte; el runner puede seguir bloqueando definitivo mientras estén abiertos.
4. [Telemetría](13-observabilidad-y-telemetria.md): configurar .env.monitoring, aceptar conscientemente montajes/instrumentación, iniciar stack y verificar targets/series por ID, RSS/throttling/OOM/spill, retención/disco/offset. Revisar exit2 de Node Exporter observado al cierre Cloud y sobrecarga local.
5. [Runner](12-automatizacion-benchmarks.md): capturar entorno/planes fuera de medición, ejecutar un piloto real pequeño con CSV/telemetría completos; decidir/documentar matriz y variantes. Solo después de nueva autorización Fase 7 y gates completos iniciar mediciones definitivas con 60/300/60 y caché autorizada. No ejecutar 162 en un presupuesto 13h ni prometer 108 sin margen real.
6. Mantener este progreso/reporte parcial actualizándose desde archivos, preferentemente en otro equipo; al cerrar intentar final con --allow-partial para nunca ocultar pendientes. Descargar/copiar resultados y reportes originales antes de depender de una sesión efímera.

La implementación se detiene en Fase 6. Las decisiones de ejecución/aceptación académica pendientes y los benchmarks definitivos pertenecen a Fase 7.
