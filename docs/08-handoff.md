# Continuidad vigente — Fase 6

## Estado real y autorización

U8 autorizó exclusivamente análisis estadístico/reportes offline. Implementación terminada y verificaciones disponibles realizadas; Fase 6 IN_PROGRESS indica validación parcial, porque falta demostrar un informe FINAL con resultados definitivos auténticos. Fase 0 COMPLETED; Fase 1 BLOCKED para cierre integral/físico; Fases 2–5 IN_PROGRESS con código implementado y validaciones pendientes; Fase 7 PENDING, no iniciada. Última fase completamente cerrada en todos sus criterios: Fase 0. Git/GitHub no es requisito y no se configuró. Los handoffs inferiores son históricos, con sus autorizaciones/evidencias originales.

Plataforma definitiva declarada: Kubuntu nativo/Engine/Compose Plugin/cgroups v2, Ryzen 7 5700X y 32GB. Versión Kubuntu y validaciones físicas siguen pendientes. No se iniciaron contenedores, no se hicieron nuevas consultas ni benchmarks durante Fase 6. No se cambiaron límites, imágenes, índices, dataset, SQL/pipelines, CSV ni protocolo 60/300/60.

## Implementación reutilizable

reporting/ contiene loader/validation/progress/statistics/charts/plans/generator/exporters/CLI y CSS de impresión. scripts/generate_report.sh y benchmark_progress.sh son entradas Bash ejecutables. requirements-reporting.txt fija herramientas/transitivas; requirements-reporting-pdf.txt añade ReportLab opcional. Guía [docs/14](14-analisis-y-reporte.md) describe instalación, comandos completos, semántica y referencia breve de Fases 1–5 para Kubuntu.

Loader observa commits completos con lectura estable/hashes sin tomar lock, copiar datasets ni consultar motores. Integridad selected usa metadatos/CSV/series necesarios; all verifica además todos los diarios y es obligatoria para FINAL. Snapshots compactos permiten auditar tablas, pero para reauditar diarios se conservan los experimentos completos. Nunca editar fuentes para pasar validación. Intentos incompletos quedan pendientes y cambios se observan en próxima actualización.

Cohortes separan dataset/hash/configuración, host/boot, fuentes/drivers/runner, protocolo/monitoreo y política de matriz/variantes. No sumar cohortes para completar 108/162. Estadística Decimal por KPI de repetición (media/mediana/min/max), no P99 combinado. Q2 requiere pareja explícita para contraste descriptivo; no equivalencia de buffers inferida. RSS temporal solo de series verificadas; no se fabrica curva desde máximo. M3 no calculable por falta de insumos/metodología de CPU/documentos atribuibles. Cero solo si medido.

Reportes tienen siete secciones P p.4 §8.3, portada editable sin identidad inventada, índice, tablas, figuras/conclusiones/anexos; Markdown/HTML imprimible/PDF opcional. Versiones inmutables UUID con analysis-manifest.json al final, hashes, fuentes/dependencias y snapshot/index.json. Progreso terminal/JSON, watcher y ETA aproximada no ejecutan benchmarks. FINAL bloquea incompletos/inválidos; --allow-partial conserva PARCIAL.

## Único cambio de código de fases anteriores

query_tool.py: --file opcional para explain valida archivo/contenido completo con interfaces existentes antes del diagnóstico original y guarda dataset_sha256/dataset_binding. Necesario para vincular planes al mismo dataset; sin archivo comportamiento previo intacto. Dos pruebas mock y regresión pasaron. La nueva rama NO se ejecutó contra motores reales en Fase 6; validar en Kubuntu fuera de medición. No cambia consultas ni prueba el spill de una ejecución anterior. Runner/Fase 5 restante intactos respecto al ZIP anterior; evidencia de conservación final en [validación](evidence/phase6/validation-summary.json).

## Evidencias y entregables reales

- Informe académico [HTML](../reports/academico-parcial/20261101T180843Z-e7abcd9f5b/reporte.html), [PDF](../reports/academico-parcial/20261101T180843Z-e7abcd9f5b/reporte.pdf): PARCIAL, 0/108 mediciones, sin valores/curvas inventados. Selección base Q2 false/4MB explícita para plantilla, no aceptación del profesor.
- Diagnóstico [HTML](../reports/piloto-real/20261101T180841Z-1e2a201164/reporte.html), [PDF](../reports/piloto-real/20261101T180841Z-1e2a201164/reporte.pdf): piloto PG real histórico de 100 órdenes/1 cliente/1–4–1s/severe/4MB; no definitivo. Tres figuras reales y planes PG históricos auxiliares sobre 10 órdenes. Piloto no incorpora mediciones nuevas.
- [Catálogo y versiones anteriores](../reports/README.md); captura Cloud independiente reports/entorno-cloud-fase6.json no prueba retrospectiva ni entorno Kubuntu.
- [Evidencia de revisión](evidence/phase6/README.md): logs unitarios/regresión/Compose/promtool, fuentes sin cambios, gates y artefactos. PDF revisado con pdfinfo/pdftotext y vista de portada/figura; siete secciones verificadas.

## Verificaciones efectivamente ejecutadas

33 pruebas nuevas aprobadas. Regresión total: 126 descubiertas, 114 aprobadas, 12 integraciones omitidas sin opt-in; no contarlas como aprobadas. Cloud usó Python 3.12.14/Matplotlib 3.10.8/NumPy 2.3.5/ReportLab 4.4.9 y drivers previos vía PYTHONPATH=/tmp/phase4-venv/lib/python3.12/site-packages. Instalación normal local en venv documentada, sin depender de /tmp Cloud.

Sintaxis AST de 61 Python y bash -n de 24 scripts aprobadas. tests/test_infrastructure.sh aprobó Compose A/B/C y controles negativos; monitoring.sh config y promtool 3.15.1 aprobaron configuración existente 1s/800ms. No es prueba de contenedores. Análisis offline del piloto real, watcher, hashes completos, exportaciones y rechazo FINAL sin datos pasaron. Los fixtures de pruebas fueron temporales y etiquetados; no se incluyen sus resultados en informes/ZIP. No se validaron nuevas conexiones de Mongo/PG ni integración física/masiva/final. Comprobaciones documentales/ZIP se conservan en evidence/phase6/ al cierre.

## Decisiones y bloqueos que deben conservarse

95 requisitos trazados (U8 añade 086–095) y 50 asuntos (P-44–50 nuevos). Ninguna propuesta se marcó aprobada por inferencia. Siguen P-02 matriz, P-03 alias, P-04/05 fechas/tipos, P-06/P-26 índice temporal, P-07 caché, P-08 orden/fallos, P-10/P-38 unidades/bordes, P-11/P-36 versiones finales, P-14 M3, P-19 swap, P-24/25 precisión/empates, P-37 permisos, P-40/41 sobrecarga/spill/restore, P-42/43 telemetría/validación y nuevos riesgos/metodologías de reporte.

Mongo real/equivalencia cruzada, Kubuntu físico, generación/carga 500000, 1/10/50 reales de ambos, pila Prometheus Docker/TSDB/retención/sobrecarga siguen pendientes. Node Exporter exit2 al stop histórico sin OOM sigue sin causa confirmada; comprobar cierre local. El nuevo vínculo de planes requiere prueba real. No hay informe FINAL académico ni justificación para declarar experimento completo.

Tiempo: base 108 × 420s = 12h36, solo 24min de margen dentro de 13h para TODOS los costes adicionales. Extendida 162 = 18h54 y sigue no aprobada. No ajustar protocolo ni ocultar incompletos: priorizar reporte parcial verificable si el tiempo no alcanza.

## Respaldo y continuidad

fase6-reporte-kubuntu.zip conserva código/documentación/configuración/manuales/evidencia real y reportes, estructura y permisos; excluye secretos/.env reales/cachés/volúmenes/datasets masivos/resultados simulados/ZIP anteriores. Verificación CRC/bytes/permisos/inventario y conservación de Fase 5 en evidence/phase6/archive-verification.json; SHA256 en fase6-reporte-kubuntu.zip.sha256. No se presupone persistencia de /workspace: descargar antes de terminar sesión. ZIPs históricos quedan separados.

Próximo objetivo sujeto a nueva instrucción: Fase 7, validar equipo y decisiones académicas, datos/motores/consultas/telemetría, preparar planes vinculados/captura ambiental, piloto local real y solo después preflight definitivo. [Referencia rápida Kubuntu](14-analisis-y-reporte.md) enlaza comandos de las guías 09–13 sin duplicarlas. Reportes pueden actualizarse en paralelo desde otro equipo usando commits completos; conservar originales. Esta entrega se detiene en Fase 6.

---

## Archivo histórico — cierre de Fase 5 y anteriores

# Continuidad vigente — Fase 5

## Estado y autorización

U7 autoriza exclusivamente observabilidad/telemetría de Fase 5; no Fase 6 ni benchmarks definitivos. Fase 0 COMPLETED; Fase 1 BLOCKED para cierre integral/físico; Fases 2–5 IN_PROGRESS con implementación y validación parcial. Fases 6–7 PENDING. Última fase completamente cerrada: Fase 0. La ausencia de equipo Kubuntu/Mongo no bloqueó desarrollo ni se transformó en evidencia ficticia. Los handoffs debajo son históricos.

Objetivo definitivo: Kubuntu Linux nativo x86_64, Ryzen 7 5700X/32 GB; versión exacta pendiente. Cloud observado: Debian 13/kernel 6.18.57, Engine 28.4.0/Compose 2.40.3/cgroups v2, cuota padre 2 CPU/8 GiB, filesystem pequeño y driver VFS. No se cambiaron límites/imágenes/Compose/volúmenes de motores, generador/importadores ni SQL/pipelines. Git/GitHub siguen sin configurarse y no bloquean entrega.

## Implementación y archivos

config/monitoring/compose.monitoring.yml y prometheus.yml: tres servicios, proyecto/red internos separados, TSDB nombrado persistente, puerto Prometheus solo 127.0.0.1:19090, scrape/evaluation 1s y timeout 800ms, retención 7d/size=0B configurable. config/monitoring/monitoring.env.example se copia opcionalmente a .env.monitoring local (no se creó un .env real en el proyecto). scripts/monitoring.sh config/validate/start/stop/health/targets/storage/diagnose/query/export gestiona solo monitoreo. No Grafana, interfaz adicional, instalación global ni cambios privilegiados.

Versiones/digests verificados: Prometheus 3.15.1/fa3302279710…, cAdvisor 0.60.6/b8e7d1093144…, Node Exporter 1.12.1/1b4e4438faca…; valores completos en config/monitoring y docs/evidence/phase5/versions.json. Las tres referencias/amd64/pulls se comprobaron. Prometheus Docker recién descargado llenó VFS: solo esa imagen nueva se retiró. Integración Cloud usó binario oficial **misma versión**, tar SHA256 6a726885328ad9efebbf36e876ce2fb6225468a71fd1e7ce3ba666d5f4d97a84 verificado contra release oficial, TSDB temporal y targets por IP Docker. Los exportadores sí fueron contenedores fijados. No afirmar pila completa Compose/TSDB persistente/healthcheck Prometheus Docker probados aquí.

observability/ implementa cliente HTTP local, selectores/series, identidad, eventos, spill, proveedor, configuración y CLI. make_telemetry de Fase 4 sigue como fábrica única; con URL/.env.monitoring añade ExperimentalTelemetry y sin ello mantiene fallback incompleto. Hooks prepare/configure_client/clients_ready/set_window/finish/cleanup se integran al runner, conservando protocolo y escritura/recuperación CSV. No hay un segundo runner.

Modificaciones de código previo acotadas: benchmark/__init__.py (1.1.0-provisional), cli.py, config.py, preflight.py, runner.py, telemetry.py y workers.py; queries/native.py añade instrumentación por sesión/comentario. Motivo: fuentes/evidencia, tags de operación, clock bridge, preflight y fingerprint de monitoreo. metrics.py, results.py y queries/execution.py no cambiaron respecto al ZIP de Fase 4. Source hashes incluyen observability/ y config/monitoring; no mezclar resume 1.0/1.1, datasets/config/versiones diferentes. Regresión de código anterior ejecutada.

## Método y seguridad

Series por ID completo, etiquetas project/service/profile e identidad/imagen/límites reales, versiones/targets/host/kernel/boot/frescura. Cambio de ID/StartedAt/RestartCount invalida asociación. Raw samples dentro de ventana: throttling último−primero en segundos con subintervalo cubierto explícito (no extrapolación ni equivalencia exacta a todos los bordes); RSS máximo observado/1000000, MB decimal provisional, no pico absoluto ni working set. Relojes unidos por offset epoch−monotonic, salto >100ms/lectura >10ms invalida. Cuantiles/QPS y CSV de 14 columnas permanecen como Fase 4.

OOM: eventos Docker continuos por ID/timeNano, cgroup/estado como evidencia separada; no exit137/memoria al límite como prueba. Nuevo State.OOMKilled posterior solo acredita intento, no instante de medición. Spill PG: log_temp_files=0 en cada sesión, permiso explícito, prefijo/timezone/locale/destino verificados y stream json-file bloqueante; PID/tiempo cruzados con operaciones realmente incluidas. Cero requiere mecanismo/cobertura válidos; eventos de otros backends no son atribución. Mongo: profiler filtrado por token/aggregate comment, canario/usedDisk explícito, cobertura de tags, restauración/CAS/estado previo; getMore no reemplaza evidencia aggregate. Sin señal suficiente, null y exclusión, nunca EXPLAIN posterior como sustituto.

MONITORING_SPILL_CAPTURE=false por defecto; instrumentación requiere opt-in y añade trabajo al motor, sin modificar consulta lógica/GUC global. Perfil Mongo previo activo se respeta/rechaza; no cambia slowms/sampleRate global. SIGKILL puede impedir restore: conservar mongo-profile-restore.json y verificar estado/filtro/token antes de intervención explícita; no borrar system.profile ni apagar perfil ajeno. Mongo real no disponible: esta ruta es unitaria, no integración.

Start requiere MONITORING_ACCEPT_HOST_ACCESS=true: raíz/proc/sys/UTS/cgroup del host y socket Docker son accesos sensibles documentados. **Socket :ro conserva poder de API Docker**. Sin privileged ni cap_add; etiquetas exportadas whitelist. cAdvisor distroless no tiene wget: se corrigió el healthcheck inicial inválido y se verifica por targets/series reales, no por --version. Errores de filesystem VFS auxiliares quedan registrados sin ampliar privilegios. Monitoreo fuera de cgroups del motor puede consumir CPU/RAM/IO del mismo host.

## Pruebas efectivamente realizadas

- Discovery final: **93 casos, 81 aprobados y 12 integraciones omitidas** sin opt-in. Incluye 25 unitarias nuevas de observabilidad y 56 de fases anteriores. Simulaciones solo prueban lógica y viven en temporales; no se empaquetan resultados simulados.
- Integración monitoreo opt-in real: un caso PG con 100 órdenes en base/rol nuevos, Q2 4MB, 1 cliente y 1/4/1s, caché omitida. Scraping real, siete métricas cAdvisor, host/kernel/boot y targets/versiones verificados. CPU/RSS obtenidos de muestras, negativos OOM/spill por mecanismos válidos, CSV íntegro y resume con un único commit/hash aprobados. Piloto no definitivo aun con status=ok. Se conservaron intentos independientes; primer rango PromQL inválido quedó con nulos/error y se corrigió a ms enteros, sin sobrescribirlo. Bajo carga Cloud un preflight rechazó métrica no fresca; bloqueo real documentado, no se relajó el gate.
- Regresión real adicional PG: **1 caso de datos**, **9 casos de consultas** y **1 caso de runner nativo Fase 4**, todos aprobados. Generación/importación/readback/resume/rollback, Q1/Q2/variantes/planes/índices en bases nuevas de prueba, conexiones/errores/timeout y CSV/cgroups fallback comprobados sin atribuir Mongo. Son las 12 integraciones de discovery ejecutadas por separado en el alcance disponible PG/monitoreo, no integración both.
- Python compileall, sintaxis Bash individual, tests/test_infrastructure.sh (Compose A/B/C y negativos) y Compose complementario/promtool 3.15.1 reales aprobados. Health/targets/diagnose/export/storage y stop ejercitados; stop dejó PostgreSQL corriendo antes de restaurarlo a detenido. No se probó start de la pila completa Prometheus Docker por disco.

Evidencia original en docs/evidence/phase5/: manifiestos/config/fuentes de cada piloto, CSV, commit/hashes, telemetry-evidence.json con PromQL/respuestas/samples/ventana y journals SQLite crudos, versiones y logs. Todas las filas son mode=pilot, eligible_for_final_analysis=false. Los hashes conservan código del momento de captura; cambios conservadores posteriores (como el guard de identidad ausente) se validaron unitariamente, no reescribiendo evidencia. Ningún positivo real de spill/OOM se provocó: positivos solo fixtures unitarios.

PG de pruebas jsonbenchpgsmoke1793495-postgres-1, cAdvisor/Node Exporter jsonbench-monitoring-* quedaron detenidos; PG exit0/cAdvisor exit0. Node Exporter terminó con exit2, OOMKilled=false y error vacío tras stop: causa no confirmada, pendiente revisar cierre en Kubuntu; no se presenta como OOM ni apagado limpio demostrado. El binario Prometheus temporal propio se detuvo por su PID verificado, TSDB temporal se conservó fuera del respaldo. Bases/roles/volúmenes/series/resultados previos se conservaron, sin prune/down -v/drop_caches. Roles auxiliares nuevos recibieron únicamente permisos necesarios; sus contraseñas aleatorias temporales no se registraron ni empaquetaron. No se generaron/cargaron 500000 ni se ejecutó matriz 108/162.

## Pendientes y continuidad

85 requisitos (U7 añade 075–085) y 43 asuntos (P-36–43 añadidos). Ninguna propuesta metodológica se marcó aprobada automáticamente. Siguen P-02 matriz, P-03 alias, P-04/05 tipos/fechas, P-06/P-26 índice temporal, P-07 caché, P-08 orden/fallos, P-10/P-38 métricas/MB/bordes, P-11/P-36 versiones definitivas, P-14 M3, P-19 swap, P-24/25 precisión/empates, P-37 permisos, P-40/41 sobrecarga/atribución/restore y P-42/43 fuentes/validación parcial.

En Kubuntu: identificar versión, iniciar stack completo con aceptación de montajes; comprobar DockerRootDir/cgroups2/recursos A/B/C/ancestros de ambos; salud/persistencia TSDB y retención/capacidad real; scraping/frescura/offset y carga de instrumentación 1/10/50; Mongo real/profiler/usedDisk/Decimal128/equivalencia; 500000 idénticos, índices/alias/tipos/caché aprobados, M3 definido. No presentar este piloto como rendimiento ni equivalencia definitiva. El preflight conserva todos los gates previos y añade stack Docker identificado, métricas/fuentes/sesiones/relojes/capacidad; no hay bypass para definitivo.

Leer AGENTS/PLANS, docs/01–07, docs/09–13 y los PDF originales. Próximo objetivo potencial: Fase 6 de integración/análisis/reporte, **solo tras nueva instrucción** y con pendientes visibles; no producir gráficas o conclusiones académicas con pilotos. [Guía operativa](13-observabilidad-y-telemetria.md) detalla instalación, comandos, permisos y errores.

Respaldo vigente: /workspace/fase5-telemetria-kubuntu.zip, proyecto completo/manuales/fuentes/pruebas/config y evidencia real etiquetada, sin .env reales/secretos/datasets generados/volúmenes/TSDB/cachés/binarios temporales/resultados simulados/ZIP anteriores. Los ZIP anteriores se conservan aparte. Los SQLite en docs/evidence/phase5 son **journales reales preservados**, no cachés ni resultados ficticios. Descargar antes de abandonar sesión; /workspace no se supone persistente. Enlace local o explorador del entorno; no se despliega servidor ni se dispone de publicación general HTTP de archivos.

La verificación final de documentación/respaldo se añade debajo tras ejecutarla. No se afirma git diff --check por ausencia de repositorio; espacios/conflictos se revisan independientemente.

## Verificación final de cierre

Revisión ejecutada: 19 Markdown, 103 enlaces locales existentes, 85 REQ y 43 P únicos/consecutivos, tablas/cercas y ausencia de conflictos/espacios finales; PDF originales con hashes intactos. Sintaxis Python/Bash y Compose/promtool verificadas; prometheus.yml no secreto tiene modo 0644 para USER nobody, scripts mantienen ejecutabilidad. No hay repositorio Git ni afirmación de git diff --check.

Auditoría de cuatro experimentos reales preservados (tres ok, uno error; todos piloto/no elegibles): Store verificó cabeceras/commits/hashes/recuperación; QPS y R7 se recalcularon desde sus SQLite crudos en un directorio temporal independiente, y throttling/RSS disponibles desde las muestras originales de su ventana. Coincidieron con CSV/JSON sin modificar originales. El intento fallido no fue sustituido por ceros ni sobrescrito. La regresión final pasó 93 casos (81 aprobados/12 skips), y las 12 integraciones disponibles PG/monitoreo se ejecutaron aparte con éxito dentro de su alcance descrito.

Comparación con ZIP Fase 4: sus 121 archivos permanecen, incluidos todos los resultados/manuales previos. Solo se cambiaron documentación y los ocho archivos de código previo enumerados arriba (siete benchmark/ y queries/native.py); docker-compose.yml, perfiles, imágenes de motores, generador/importadores, SQL/pipelines, metrics.py y results.py están intactos. No hay Fase 6, matriz definitiva, datos de rendimiento ficticios ni dataset masivo.

fase5-telemetria-kubuntu.zip contiene 213 archivos y 30 directorios, incluidos manuales y journals reales auditables. Verificación CRC, lectura completa/bytes contra fuentes finales, rutas relativas sin duplicados/escapes, permisos originales/ejecutables y exclusión de secretos/.env reales/datasets/TSDB/volúmenes/cachés/binarios temporales/resultados simulados/ZIP anteriores. Los respaldos anteriores se conservan aparte. La validez del ZIP no cierra Mongo/Kubuntu, shutdown Node exit2 ni las decisiones metodológicas. Detenerse al entregar.

---

# Archivo histórico: handoff de Fase 4

# Continuidad vigente — Fase 4

## Estado real y autorización

U6 autoriza exclusivamente automatización de Fase 4, sin Fase 5 ni benchmarks definitivos. Fase 0 COMPLETED; Fase 1 BLOCKED para cierre integral/físico; Fases 2 y 3 IN_PROGRESS parcialmente validadas; Fase 4 IN_PROGRESS, implementación terminada y validación parcial; Fases 5–7 PENDING. Última fase completamente cerrada: Fase 0. La ausencia de Mongo/Kubuntu no bloqueó desarrollo ni se convirtió en validación ficticia. Los handoffs siguientes son históricos.

Plataforma objetivo sigue Kubuntu nativo x86_64, Ryzen 7 5700X/32 GB; versión Kubuntu desconocida. Cloud Debian 13/kernel 6.18.57, Engine 28.4.0/Compose 2.40.3/cgroups v2, cuota padre 2 CPU/8 GiB y espacio insuficiente para Mongo conjunto. No se cambiaron imágenes, Compose, perfiles, generador, importadores, SQL/pipelines, variantes, índices ni datos anteriores. Git/GitHub no se configuró y no condiciona entrega.

## Implementación disponible

benchmark_runner y scripts/run_benchmarks.sh exponen plan/run/consolidate; módulos en benchmark/ gestionan matrices, protocolo, clientes, métricas, preflight, telemetría limitada y resultados/manifiestos/reanudación. Base 36 celdas/108 repeticiones exige ambas elecciones Q2 explícitas; extendida 54/162 conserva P-02 OPEN. Escenario individual/filtros/piloto disponibles; no hay ejecución por omisión y múltiples repeticiones requieren --confirm-matrix. No se ejecutó matriz completa.

Sesiones nativas por cliente con requirements-benchmark.txt fijado (psycopg/psycopg-binary 3.3.6, pymongo 4.19.0, dnspython 2.9.1, typing_extensions 4.16.0), instaladas solo en /tmp/phase4-venv para pruebas Cloud. Crear otro venv local según docs/12; ese venv temporal no está en ZIP ni se supone persistente. Único cambio de código previo: queries/execution.py añade open_session delegando a queries/native.py; conserva execute() anterior. Motivo: no medir arranque docker exec/cliente por consulta. Regresión unitarias Fases 2/3 y sesiones PG reales ejecutadas; transporte de importación y CLI de corrección no cambia.

Un hilo por cliente independiente (1/10/50), conexión preparada/validada antes de caché, warmup drenado, ventana común monotónica, resultados completos consumidos, cierre y cooldown. Ajustes PG en sesión exclusiva fuera de medición, verify work_mem y descarte; Mongo opciones aggregate, pool máximo 1 sin retries. R7 exacto y QPS sobre mismos éxitos íntegramente dentro de ventana, diarios SQLite en disco, sin retener respuestas. Métodos siguen provisionales, no aprobaciones académicas inferidas.

CSV oficial intacto de 14 columnas por intento confirmado, variante externa en result.json/hash de fila y manifiesto de consolidación. Estado error cuando faltan métricas; null/celda vacía, jamás cero inventado. Locks/hashes/commit exclusivo protegen originales; incompleto conserva historial y permite nuevo intento, error ya confirmado se omite en resume sin retry automático. Configuración/dataset/fuentes/drivers/imagen/host/protocolo distintos bloquean resume. Consolidación exige sidecars, plan completo y elegibilidad, rechaza duplicados y mezcla piloto/definitivo/test.

## Evidencia ejecutada y límites

- Suite general con drivers: 67 casos, 56 aprobados y 11 integraciones omitidas sin opt-in; incluye 20 unitarias de runner y regresión de datos/consultas. Tests simulados prueban lógica, no bases. Casos: matrices, filtros, variantes, tiempos/bordes/R7/QPS, 1/10/50 clientes, errores, cancelación y cierre, telemetría ausente/deltas, CSV/locks, recuperación/corrupción/duplicados y separación de modos. Logs en docs/evidence/phase4/.
- Integración real nativa PostgreSQL: un caso opt-in aprobado con base/rol nuevos, 100 órdenes de Fase 2, Q1 y Q2 4MB/64MB contra oráculo, conexión rechazada, SQL inválido y timeout 57014. Piloto de un cliente Q1 0.05/0.25/0.05 s produjo muestras reales y CSV con status=error por métricas faltantes; resume dejó un solo commit/CSV/hash. Solicitud definitiva bloqueó antes de ejecución/cache y no creó CSV definitivo.
- Se conservaron cuatro pilotos funcionales independientes, con advertencia no académica, en docs/evidence/phase4/README.md; el último añade configuración/preflight exactos. Son pruebas pequeñas de software, no tres repeticiones oficiales ni rendimiento comparable. Bases/roles auxiliares phase4pilot_<token>/phase4user_<token> se conservan; credenciales temporales fuera del proyecto no se incluyen. Contenedor PG de pruebas jsonbenchpgsmoke1793495-postgres-1 restaurado detenido, exit 0; no se detuvieron servicios ajenos ni borraron volúmenes/datos.
- Bash -n, compileall, tests/test_infrastructure.sh (Compose A/B/C y controles negativos), planes CLI 36/108 y 54/162 y rechazo de interfaces inválidas ejecutados. La validación Compose es configuración, no operación conjunta. No se repitieron benchmarks masivos ni se generaron 500000.

La telemetría solo ofrece interfaz y lectura directa cgroups opcional de throttled_usec/oom_kill con snapshots; bordes aproximados deben sincronizarse/validarse. En este Cloud no hubo ruta directa disponible en el piloto. RSS exacto/spill no disponibles: no se reemplazaron por memory.current/anon/working set/RSS del runner. State.OOMKilled positivo sería evidencia de intento, no inferencia por exit137 ni prueba de causalidad. No se provocó OOM/spill. **Definitivo bloqueado intencionalmente** antes de activar servicios/caché por métricas obligatorias faltantes; Fase 5 deberá integrar proveedor verificado, no eliminar la puerta para hacer pasar un test.

## Pendientes y decisiones vigentes

74 requisitos trazados (REQ-064–074 añadidos U6), 35 asuntos (P-29–35 añadidos sin aprobación académica). Se preservan P-02 matriz, P-03 alias, P-04/05 tipos/fechas, P-06/P-26 índice temporal PG, P-07 caché, P-08 orden/fallos, P-10 métricas, P-11 versiones definitivas, P-14 M3, P-19 swap y P-24/25 precisión/empates. Propuestas del runner documentadas: hilos/sesión propia, cuantiles/bordes, codificación CSV/manifiestos; no se marcaron APPROVED.

Pendiente real: Mongo y equivalencia ambos, 500000 idénticos, Kubuntu/versión/salud/persistencia/límites A/B/C y ancestros, aceptación swap/índice/alias/tipos/método, 1/10/50 conexiones reales/capacidad del runner/disco, caché autorizada con evidencia, telemetría RSS/spill/OOM y sincronización. No confundir core probado con aceptación experimental definitiva.

## Continuación y respaldo

Leer AGENTS.md, PLANS.md, docs/01–07, docs/09–12 y manuales. [Guía de runner](12-automatizacion-benchmarks.md) incluye arquitectura, CLI, piloto/resume/consolidación, errores y evidencias. Próximo objetivo potencial: Fase 5, solamente tras nueva instrucción; diseñar proveedores reales y evidencia sin sustituir RSS/spill ni resolver M3 por inferencia. No arrancar automáticamente otra fase ni una matriz real.

Respaldo vigente /workspace/fase4-benchmark-runner-kubuntu.zip: fuentes/configuraciones/pruebas/documentación/manuales de todas las fases y evidencia real etiquetada; ZIP previos se conservan aparte. Excluye credenciales, .env reales, datasets generados, resultados temporales/simulados, venv/cachés, volúmenes y ZIP previos. Recuperar mediante enlace local/explorador y descargar antes de salir; /workspace no se presume persistente. El entorno no ofrece publicación HTTP de archivos generales y no se desplegó servicio para distribuirlo.

La verificación final documental/ZIP se registra debajo una vez ejecutada. No se afirmó git diff --check: no hay repositorio Git; se revisan espacios/conflictos independientemente.

## Verificación final de cierre

Se ejecutaron 67 tests de discovery: 56 aprobados, 11 omitidos por falta de opt-in; 20 son unitarias del runner. El caso nativo PG se ejecutó aparte y pasó, incluyendo errores reales, variantes, piloto y resume; último log en docs/evidence/phase4/native-tests.txt. Compilación Python, sintaxis Bash individual de scripts/pruebas y Compose A/B/C con controles negativos pasaron. Planes CLI confirmaron 36/108 y 54/162, sin empezar matrices. La inspección documental verificó 17 Markdown, 87 enlaces relativos existentes, 74 REQ y 35 P consecutivos, tablas/cercas/espacios/conflictos, CSV exacto y hashes de ambos PDF. Los cuatro pilotos son reales y no definitivos; sus CSV/hashes/ausencias/elegibilidad se comprobaron, y el manifiesto del último coincide con hashes del código final.

Comparación con respaldo Fase 3: sus 80 archivos fuente permanecen; las únicas modificaciones previas son Markdown y queries/execution.py (puente documentado, sin cambiar execute/consultas). No se modificaron Compose/perfiles/imágenes/generador/importadores/índices anteriores. Docker de prueba final: Running=false, ExitCode=0. No se ejecutó git diff --check por ausencia de repositorio; se revisaron conflictos/espacios independientemente.

fase4-benchmark-runner-kubuntu.zip contiene 121 archivos y 15 directorios. Se verifican CRC, lectura/comparación byte a byte con fuentes finales, rutas relativas sin duplicados/escapes y permisos originales, incluidos ejecutables. Se incluye este handoff y se excluyen secretos/.env reales, datasets generados, resultados temporales/simulados, venv/cachés, volúmenes y ZIP anteriores. El respaldo no certifica Mongo/Kubuntu ni telemetría ausente. Detenerse al entregar; no iniciar Fase 5.

---

# Archivo histórico: handoff de Fase 3

# Continuidad vigente — Fase 3

## Estado real y alcance autorizado

Fase 0 COMPLETED; Fase 1 BLOCKED para cierre físico/integral; Fase 2 IN_PROGRESS con implementación y validación parcial; Fase 3 IN_PROGRESS con desarrollo terminado y validación PG real disponible. Fases 4–7 PENDING. U5 autoriza implementar consultas/índices seguros/validadores/planes sin equipo físico, pero prohíbe Fase 4 y benchmarks. No se generaron 108/162 mediciones, clientes concurrentes, percentiles ni telemetría. Se conservan debajo los handoffs históricos, que no describen el estado actual.

Kubuntu nativo sigue siendo objetivo (Ryzen 7 5700X/32 GB x86_64; versión de sistema pendiente). Cloud observado: Debian 13, kernel 6.18.57, Docker Engine 28.4.0 y Compose 2.40.3, cgroups v2, cuota padre restrictiva/espacio limitado. No se cambió Compose, perfiles, imágenes, generador ni importadores de Fases 1/2. AGENTS se ajustó mínimamente para conservar autorización U5 y prohibición de Fase 4. Git/GitHub siguen ausentes y no bloquean entrega.

## Implementación y continuidad técnica

queries/ contiene JSON Mongo y SQL PG originales, variantes explícitas, QuerySpec/QueryExecutor, preflight, oráculo independiente, índices y planes; query_tool.py/scripts/queries.sh exponen run/validate/explain/indexes. Reutiliza clientes mongosh/psql de contenedores, sin dependencias Python externas, puertos ni servicios nuevos. Mongo pasa allowDiskUse a aggregate como opción; PG usa SET LOCAL y lectura efectiva dentro de la misma transacción/sesión. No hay configuración global ni transporte de credenciales en argv/informes.

Q1 conserva unwind/match/group y qty*price, agrupación por país/categoría, suma/promedio/count. Q2 conserva completed, fecha >= 2026-01-01, único sort final_total DESC, Top-1000 y proyección original. No se eliminó totals ni se cambió alias/tipo para hacer pasar pruebas. Totals-only se bloquea para Q2, calendario/formatos inválidos y tipos incompatibles se bloquean en preflight antes de la consulta original.

Validación: fuente completa vs bases (Fase 2), oráculo independiente desde documentos, grupos sin dependencia del orden, suma/count exactos. Promedios periódicos deben ser cuantización de la fracción exacta al quantum del motor, con mínimos justificados 16 cifras PG/34 Mongo; se informa cada diferencia, sin floats/epsilon libre. Empates se validan por cutoff/UUID: todos los superiores obligatorios y selección libre solo en el empate de frontera; no hay segundo sort ni se ocultan resultados incorrectos. Estas políticas siguen propuestas P-24/25, no aprobaciones académicas.

Índices: Mongo preparación segura timestamp/order_id implementada, sin índice de total y sin borrado, pendiente de motor real. PG inventario/PK verificados, timestamptz_in STABLE y cast no indexable directamente comprobados. Solo con opt-in se preparó B-Tree textual en base nueva; physical_index_status PASS, status académico BLOCKED. Q2 original no se reescribió y plan pequeño observado Seq Scan/Sort/Limit. P-06/P-26 siguen pendientes; no hay funciones falsas IMMUTABLE.

## Evidencia realmente ejecutada

- 17 unitarias de Fase 3 aprobadas: fidelidad de definiciones/variantes, umbral estricto 50, cantidades/grupos, suma/avg exacto o cuantizado, vacíos, fechas/status, alias, tipos, Top-1000/empates, errores/diagnósticos, sesiones e índices/planes. Inputs sintéticos del validador son unitarios, no evidencia Mongo real.
- 9 casos reales PG: ocho en suite inicial y un caso vacío dirigido posterior. Tamaños generados 10/100/1000, controlado de 10 y empate con 1005; Q1/Q2 y ambas work_mem pasaron oráculo. Totals-only y calendario inválido bloquearon. Se repitió de forma dirigida el caso índice tras añadir timeout a DDL; pasó.
- PG work_mem efectivo 4MB/64MB confirmado en la sesión de cada consulta; conexión independiente mantuvo su configuración previa. Predicado temporal incluyó igualdad y excluyó fecha anterior/no completadas. JSONB mantuvo qty/price/final_total numéricos y timestamp string según preflight.
- Controlado MX/electronics: suma 200.06/count3, avg PG 66.6866666666666667 validado contra 10003/150. No se declara un valor real Mongo. Q1 ignoró descuentos/impuestos del dato controlado conforme al manual.
- Top-K controlado: 1005 elegibles, dos superiores, 1002 en empate de frontera y uno inferior. PG devolvió 1000 válidos en ambas variantes. Selecciones distintas entre motores fueron probadas solo como entradas unitarias del validador.
- Nueve JSON reales preservados en docs/evidence/phase3/ y su README: planes Q1/Q2 4/64MB, plan posterior al índice textual, inventario y validaciones. Q1 mostró Aggregate/Nested Loop/Seq Scan/Function Scan; Q2 Limit/Sort/Seq Scan. Ausentes se mantienen null; valores de planes no son benchmarks. Procedencia temporal de archivos históricos se registra como mtime original, no inicio de consulta.
- Python compileall, Bash, JSON/pipelines, SQL mediante ejecución real, interfaz --help y Node --check del cliente JS aprobados. tests/test_infrastructure.sh sigue pasando sin cambios. Discovery global: 46 tests, 36 unitarios aprobados y 10 integraciones omitidas sin opt-in (9 consultas + 1 datos); no confundir esos skip con integraciones reales. PG se ejecutó por separado con opt-in.

## Límites y pendientes

MongoDB no está disponible en Cloud: su imagen fue retirada durante Fase 1 por disco lleno y el espacio restante no permite ambos motores razonablemente. No se descargaron otras versiones ni se borraron datos para forzarlo. Construcción de pipelines/API/preflight/índices Mongo está comprobada estática/unitariamente; tipos Decimal128, resultados, variantes, índices y executionStats reales todavía pendientes. Equivalencia real Mongo-PG permanece BLOCKED aunque checks PG sean PASS.

63 requisitos y 28 asuntos registrados. P-02/matriz, P-03/alias, P-05/precisión, P-06/índice, P-09/P-19/recursos y políticas de medición no se marcan resueltos. P-24/25/26 son propuestas; P-27/28 registran memoria/evidencia pendiente. El Top-K puede no generar spill; no se cambia consulta/dataset/límites para provocarlo. No hay conclusiones de rendimiento.

Bases nuevas phase3test_* se conservaron en el contenedor PG de prueba preexistente, sin DROP/DELETE/TRUNCATE. No se tocaron bases de usuario previas; solo se añadieron datos/índices en bases aisladas de esta fase. Al finalizar se devuelve ese contenedor a detenido como estaba al inicio; no se eliminan datos. Los JSON de evidencia no incluyen credenciales ni datasets masivos.

Para cerrar validación: ejecutar integración both cuando haya Mongo, confirmar tipos/alias/UTC/precisión y empates, inventariar/preparar índices autorizados, decidir alternativa temporal y políticas de promedio, obtener planes de ambos, y validar Kubuntu físico. Las pruebas de 10/1000 no demuestran carga de 500000 ni comportamiento bajo 50 clientes. Fase 4 exige nueva instrucción y diseño de sesiones persistentes/mediciones; no usar tiempos de procesos CLI/preflight o EXPLAIN como latencia de motor.

## Archivos y recuperación

Leer [reglas](../AGENTS.md), [plan](../PLANS.md), [requisitos](01-requisitos-y-trazabilidad.md), [decisiones](07-decisiones-y-pendientes.md), [guía de consultas](11-consultas-y-validacion.md) y [evidencia real](evidence/phase3/README.md). El código del generador sigue 1.0.0/orders-v1-provisional sin alteraciones. Guías 09/10 siguen necesarias para preparar servicios/dataset.

Respaldo final: fase3-consultas-kubuntu.zip, proyecto completo y evidencia, sin .env reales/secretos/volúmenes/datasets masivos/cachés/temporales ni ZIP previos. Los respaldos anteriores se conservan aparte. Recuperar desde /workspace/fase3-consultas-kubuntu.zip por enlace local/explorador antes de abandonar sesión: no se supone persistencia de /workspace y no hay publicador HTTP de archivos disponible. No desplegar un servicio para exponer el ZIP.

## Verificación final

Verificado: 15 Markdown, 72 enlaces locales existentes, 63 requisitos y 28 asuntos únicos/consecutivos, estados coherentes y tablas/cercas correctas, sin espacios finales/conflictos. Dos PDF originales y CSV oficial de 14 columnas intactos. 34 archivos anteriores de implementación/configuración/pruebas comparados byte a byte con ZIP Fase 2, sin cambios. Bash/Compose, compileall e interfaces aprobados; Node --check valida sintaxis JS, no ejecución Mongo. Discovery final: 46 tests, 36 unitarias aprobadas y 10 integraciones omitidas sin opt-in; las 9 de consultas PG reales se ejecutaron por separado, con un caso de índice además revalidado. Contenedor de prueba PG restaurado a Exited (0).

ZIP final fase3-consultas-kubuntu.zip: 80 archivos y 13 directorios, CRC íntegro, lectura/comparación byte a byte con fuentes finales, rutas relativas sin escapes/duplicados y permisos ejecutables de Bash/entradas Python preservados. Incluye nueve JSON reales de evidencia y su guía. Excluye .env reales, credenciales, datasets masivos/generados, informes temporales, volúmenes, cachés y ZIP anteriores. /workspace no se considera persistente: recuperar el ZIP antes de abandonar sesión. No hay publicador HTTP de archivos disponible; usar enlace local o explorador. No hay Git, por lo que no se afirmó git diff --check; espacios/conflictos se verificaron independientemente. El respaldo íntegro no resuelve pruebas Mongo/Kubuntu pendientes.

---

# Archivo histórico: handoff de Fase 2

## Estado y autorización

Fase 0 COMPLETED. Fase 1 sigue BLOCKED para cierre por pruebas integrales/físicas pendientes; U4 autoriza desarrollar Fase 2 sin esperar esas pruebas. Fase 2 IN_PROGRESS: implementación terminada y validación disponible ejecutada, con integración Mongo/ambos y carga objetivo pendientes. Fases 3–7 PENDING. No comenzar Fase 3 ni ejecutar Q1/Q2/benchmarks. Las secciones históricas de Fases 1/0 al final no describen el estado vigente.

Plataforma: Kubuntu nativo x86_64, Docker Engine/Compose Plugin/cgroups v2; hardware declarado Ryzen 7 5700X y 32 GB, versión Kubuntu no identificada y equipo no accesible. Git/GitHub no configurados. No se modificó la infraestructura de Fase 1: 14 archivos Docker/env/config/scripts comparados byte a byte contra su ZIP anterior.

## Implementación disponible

synthetic_data_generator.py, dataset_tool.py y módulos src/dataset/ implementan generación streaming, validación, importación insert-only y equivalencia. Solo biblioteca estándar Python, comprobada 3.12.14. JSONL común UTF-8, semilla predeterminada 42/count 500000, manifiesto adyacente con versiones/configuración/hash y metadata temporal separada. Generador 1.0.0, schema orders-v1-provisional. UUIDv5/PRNG SHA-256 deterministas; el validador verifica unicidad en SQLite temporal para no retener todos los UUID en RAM.

Scripts nuevos: generate_data, validate_data, import_mongodb, import_postgresql, count_records, compare_data y data.sh compartido. Generación/validación no requieren .env/Docker. Carga reutiliza common.sh y clientes mongosh/psql de contenedores existentes por socket local; sin puertos adicionales ni paquetes. PG COPY por transacción/lote y Mongo insertMany ordered; validación completa de fuente antes de escribir y lectura completa posterior por lote. Destino vacío por defecto; --resume solo acepta registros idénticos. Sin eliminación de datos ni sobrescritura. Detalles en docs/10.

54 requisitos (7 añadidos por U4) y 23 asuntos. Campos del manual conservados. Propuestas implementadas y NO aprobadas: totals objeto y alias payment.final_total (reversible mediante layout totals-only al generar archivo nuevo); fechas UTC de segundos; importes exactos Decimal128/JSONB numérico; PK id=order_id, _id técnico Mongo=order_id; distribuciones y campos secundarios de model.py. P-03/04/05/06/13 y P-21/P-22 siguen provisionales/abiertos. No se crean índices experimentales ni se decide expresión B-Tree temporal; puerta de Fase 3. P-02/P-10/P-14/P-15 y variantes de consultas no se resolvieron aquí.

## Evidencia efectivamente ejecutada

- 19 unitarias aprobadas: determinismo, UUID/fechas/estructura/tipos, importes y redondeo, enum, duplicados, hashes, layouts, argumentos, memoria de generación pequeña, interfaces y casos de fallos/reanudación. El adaptador de memoria verifica software, no resultados de motores.
- Generaciones CLI repetidas de 100/seed42: cmp iguales y SHA-256 4654466a1e399e3ed332a5d044b1b8478ef6dfe55509f8dbf1249fca66db0587; validación completa de manifiesto/esquema/cálculos correcta. 282 ítems (media 2.82), 119 ítems price>50 y 47 órdenes elegibles para el filtro de Q2; son estadísticas del dataset sintético, no mediciones de consultas.
- Golden 1000/seed42: SHA-256 20c4e83b3694a07c80da80a681639df4b5931490d283c0ac37b638225aaec20a; media items 2.873, verificada. Nunca se generaron 500000 en Cloud.
- Integración PostgreSQL real: 100 órdenes, batch 17, lectura posterior/UUID/JSONB exactos; destino no vacío rechazado; resume batch29 sin duplicar; comparación completa batch19 y muestra10/seed7 aprobadas. COPY con nueva fila seguida de duplicado revirtió todo el lote; contador quedó100 y UUID nuevo ausente.
- Integración final en base nueva phase2test_18f9d2fd39204549aeee0a3acd2ac2af; también se conserva una base anterior de prueba phase2test_a61dc71206274b7eafb16d5eb78bc13b. Ambas en el contenedor PG de prueba preexistente jsonbenchpgsmoke1793495-postgres-1, sin alterar datos previos ni eliminar bases. No se leyeron credenciales del host: autenticación con entorno de inicialización del contenedor. Son bases de pruebas, no carga definitiva.
- tests/test_infrastructure.sh sigue pasando; Python compileall, Bash y --help de las interfaces de datos correctos. El test de integración predeterminado informa skip sin opt-in; no presentarlo como ejecutado para MongoDB.

## Limitaciones y siguientes puertas

Cloud conserva Debian 13/kernel 6.18.57, Engine 28.4.0/Compose 2.40.3 con cgroups v2; no es Kubuntu físico. MongoDB no está disponible y se mantiene la limitación de disco de Fase 1. No se descargó otra versión, modificó perfiles, eliminó datos ni forzó ejecución conjunta. Mongo solo se comprobó unitariamente (EJSON/Decimal128/interfaz), no como motor real. No hay equivalencia real comprobada entre ambos ni carga masiva 500000 validada en ningún host.

Pendientes: iniciar/validar ambos motores cuando haya espacio/equipo, ejecutar tests/test_data_integration.sh --run both, generar/cargar 500000 localmente y comparar todos los IDs/contenido contra fuente/manifiesto; registrar distribución y condiciones. Aceptar/revisar contrato provisional antes de consultas, índices y tipos, con nueva instrucción para Fase 3. Las muestras no sustituyen comparación completa. Para comparar, detener escritores y conservar archivo/manifiesto inmutables: el procedimiento no es un snapshot distribuido concurrente.

## Reanudación y archivos

Leer [reglas](../AGENTS.md), [plan](../PLANS.md), [datos](03-dataset-y-consultas.md), [pendientes](07-decisiones-y-pendientes.md) y [guía operativa](10-generacion-y-carga-datos.md). El cambio mínimo en AGENTS elimina la prohibición de Fase 2 superada por U4 y preserva alcance/historia. No contiene credenciales. La guía incluye comandos de reproducción con seed/count/start/end/layout y los hashes de referencia. Mantener versiones del generador/esquema; cambios requieren nueva versión y nuevo dataset, no mutación de anteriores.

Respaldo: /workspace/fase2-dataset-kubuntu.zip, con infraestructura/documentación/manuales previos y código/pruebas nuevos. No incluye .env reales, credenciales, datos generados, informes operativos, cachés, temporales, volúmenes ni ZIP anteriores. Recuperar por enlace local o explorador del entorno; no hay publicación HTTP de archivos disponible. Los ZIP de Fases 0/1 se conservan aparte.

## Verificación final y entrega

Comprobaciones finales ejecutadas: 13 Markdown, 49 enlaces locales válidos, 54 requisitos y 23 asuntos consecutivos, estados coherentes, tablas/cercas correctas, sin conflictos ni espacios finales. Los hashes PDF y la cabecera CSV oficial siguen intactos. Infraestructura comparada byte a byte con ZIP Fase 1 (14 archivos, sin cambios). Bash/Compose, compileall e interfaces --help aprobados; última ejecución unitaria: 19 aprobadas y 1 integración omitida por falta de opt-in en ese comando. La integración real PG se ejecutó por separado y pasó, incluida prueba de rollback. Se restauró el contenedor de prueba PG a su estado detenido (exit 0); bases auxiliares conservadas, sin eliminación de datos.

Respaldo final fase2-dataset-kubuntu.zip: 49 archivos y 8 directorios; CRC íntegro, todos los bytes comparados con fuentes finales, rutas relativas sin duplicados/escapes y permisos ejecutables preservados para scripts Bash y entradas Python. Excluidos .env reales/credenciales, datasets/informes generados, cachés, temporales, volúmenes y ZIP previos. Se conserva el handoff final dentro del respaldo. No hay repositorio Git; no se afirmó git diff --check, se revisaron espacios/conflictos independientemente. El respaldo no convierte los pendientes físicos/Mongo en pruebas superadas.

---

# Archivo histórico: handoff de Fase 1

## Estado real

Fase 0 COMPLETED. Fase 1 BLOCKED para cierre, con implementación y validación estática/configuración terminadas. Fases 2–7 PENDING. U3 autoriza solo infraestructura; no generar dataset ni iniciar Fase 2. La sección histórica de Fase 0 se conserva íntegra debajo y no describe el estado actual.

Plataforma aprobada por usuario (P-18): Kubuntu Linux nativo, Ryzen 7 5700X, RAM DDR4 32 GB, x86_64. Versión Kubuntu pendiente. Windows/Docker Desktop/WSL2 ya no son dependencias. Git/GitHub siguen sin configurarse y no bloquean entrega.

## Implementación y requisitos

47 requisitos vigentes: 40 previos con REQ-017 actualizado por U3 y 7 añadidos. Dos servicios en docker-compose.yml con red interna, volúmenes persistentes, salud autenticada, CPU quota/period y memoria; perfiles en config/profiles/, .env.example y .gitignore. Selecciones propuestas: mongo:9.0.4-resolute y postgres:18.6-bookworm con digest; manifiestos oficiales y pull de ambos confirmados. Mongo WiredTiger/sin sharding, PG JSONB nativo; no se crean orders/índices del experimento. P-11 sigue PROPOSED.

Scripts: check_environment, setup_kubuntu (solo imprime pasos), start_services, stop_services (stop sin borrar), verify_resources, healthcheck y common compartido. Los scripts fijan daemon local por socket Unix y no ejecutan .env como shell. Puertos no publicados por defecto, override opcional solo 127.0.0.1. No hay instalaciones, cambios de kernel/arranque/particiones, dataset, consultas Q1/Q2, runner ni servicios de telemetría.

El literal mem_swappiness:0 se solicita, pero cgroups v2/Moby consultado no ofrece ese ajuste. Alternativa P-19: memswap_limit igual a memoria, verificación swap.max=0 y opt-in explícito para inicio. Sigue PROPOSED para uso experimental definitivo; no se considera cumplimiento literal ni aceptación del usuario por los tests.

## Evidencia de validación ejecutada

- Bash -n: los 7 scripts y 2 scripts de pruebas pasan.
- tests/test_infrastructure.sh: pasa Compose config en A/B/C, variables requeridas, perfiles/recursos incompatibles, puertos loopback, etiquetas flotantes, sintaxis .env sin ejecución y rechazo de inicio sin aceptación. Sin crear contenedores.
- setup_kubuntu.sh: detectó instalación existente y no la modificó.
- check_environment.sh: devolvió error correctamente por CPU insuficiente para baseline en Cloud; controladores cpu/memory y cgroups2 visibles.
- Cloud observado: Debian 13, kernel 6.18.57, x86_64; Engine 28.4.0, Compose 2.40.3, driver cgroupfs, cuota padre 200000/100000 us y memoria padre 8589934592 bytes. No es el host del usuario.
- Pull de ambas imágenes/digests correcto. tests/test_containers.sh --run intentó arrancar ambos motores severe en proyecto jsonbenchtest17934953304603 y falló al crear contenedores con no space left on device. No alcanzó salud, persistencia ni verificación integral. No se repitió esa suite como si hubiese pasado.
- Se retiró únicamente la imagen MongoDB recién descargada por esta tarea para recuperar espacio documental. No se retiraron imágenes previas ni datos/volúmenes. No se ejecutaron prune ni cambios privilegiados.
- Prueba aislada adicional PostgreSQL (proyecto jsonbenchpgsmoke1793495): healthcheck healthy con autenticación, tabla auxiliar infra_probe con JSONB y una fila; se detuvo/recreó sobre el mismo volumen. Tras arrancar el contenedor recreado, count(*) devolvió 1. Contenedor final detenido con exit 0. No son datos ni mediciones experimentales.
- PG severe observado: cpu.max = 100000 100000; memory.max = 1073741824; memory.swap.max = 0. Inspect: cuota 100000, periodo 100000, Memory/MemorySwap 1073741824 y MemorySwappiness=null. Esto confirma solo hoja PG severe en Cloud; no demuestra ancestros completos ni perfiles A/B ni MongoDB ni compatibilidad Kubuntu.
- Docker conserva los recursos de prueba creados (redes/volúmenes y contenedor PG detenido). Los scripts no eliminan datos. Credenciales de prueba eran aleatorias/temporales, no se guardaron en documentación ni ZIP; los volúmenes auxiliares no son volúmenes del proyecto definitivo.

## Pendientes para completar Fase 1

Identificar versión Kubuntu/Ubuntu base y kernel, instalación y acceso Engine/Plugin, controles v2 y espacio suficiente. Ejecutar suites y salud de ambos motores, persistencia y verificación inspect/cgroup/ancestros en baseline/medium/severe. Confirmar selección de versiones y aceptación documentada de la alternativa sin swap; registrar incompatibilidades en P-09/P-19. Verificar acceso por loopback solo si se habilitan puertos. Las diferencias de cachés internas y shm_size se documentan en docs/09; no asumir igualdad entre motores.

No marcar Fase 1 COMPLETED hasta satisfacer estas puertas. P-02–06, P-08/P-10/P-13–17 siguen pendientes de sus fases; no se resolvieron aquí. Antes de Fase 2 se necesitará nueva instrucción y resolver contrato payment/tipos/fechas/identidad/distribución; no generar 500,000 registros ahora.

## Archivos de continuidad y respaldo

Leer [AGENTS](../AGENTS.md), [PLANS](../PLANS.md), [requisitos](01-requisitos-y-trazabilidad.md), [decisiones](07-decisiones-y-pendientes.md) e [instalación Kubuntu](09-instalacion-kubuntu.md). docs/04/06 detallan arquitectura y aceptación; manuales originales permanecen en docs/reference/ con hashes históricos.

Entrega fase1-infraestructura-kubuntu.zip: documentación actual e histórica, configuraciones, scripts, pruebas y dos PDF; excluye .env reales, credenciales, datos, volúmenes, temporales/cachés y ZIP previos. El ZIP de Fase 0 se conserva aparte. Ruta de recuperación: /workspace/fase1-infraestructura-kubuntu.zip mediante explorador de archivos del entorno si el enlace no permite descargar. No hay herramienta disponible para publicar un enlace HTTP de descarga; no se despliega ningún servicio para ello.

## Comprobaciones documentales y ZIP

Revisión final ejecutada: 12 Markdown, 37 enlaces locales existentes, 47 requisitos y 20 asuntos únicos/consecutivos; tablas uniformes, cercas balanceadas, ausencia de espacios finales/conflictos, CSV oficial intacto, fases coherentes y hashes de los dos PDF originales coincidentes. tests/test_infrastructure.sh pasó tras los ajustes finales. La inspección de scripts no encontró comandos sudo, prune, drop_caches, down -v, rm -rf, sysctl ni cambios de GRUB/apt ejecutables. No se usa git diff --check por ausencia de repositorio; espacios/conflictos se verificaron independientemente.

ZIP final verificado con CRC (ZipFile.testzip), lectura y comparación byte a byte de todos los archivos incluidos, rutas relativas sin escapes/duplicados y permisos ejecutables preservados para Bash. Se empaquetan 30 archivos (12 Markdown, 2 PDF, 9 Bash, 4 archivos de config/, docker-compose.yml, .env.example y .gitignore), más entradas de directorios. Se comprobó la exclusión de .env reales, credenciales, datos, cachés, temporales, recursos Docker y ZIP previos. El handoff final está incluido. El entorno no ofrece publicación de archivos ni /mnt/data escribible; recuperar /workspace/fase1-infraestructura-kubuntu.zip por enlace local/explorador. La validez del respaldo no cambia el estado BLOCKED de Fase 1.

---

# Archivo histórico: handoff de Fase 0

## Estado general al 2026-11-01

Última fase completada: Fase 0 (COMPLETED). Se incorporaron los dos manuales y se reconciliaron los 11 Markdown. Fases 1–7 PENDING; no existe autorización de inicio de Fase 1. Solo documentación y originales PDF: ningún generador, consulta ejecutable, servicio Docker, runner ni resultado experimental implementado.

La primera entrega estaba BLOCKED por falta de fuentes. U2 aportó los archivos y aclaró que no existe GitHub y que no debe configurarse Git para esta tarea. /workspace es la raíz documental; ausencia de Git no bloquea el cierre.

## Fuentes y evidencia de incorporación

P = docs/reference/playbook.pdf (4 páginas); S = docs/reference/playbook_sesion.pdf (13 páginas). Se extrajo y leyó el texto de todas las páginas con pdftotext -layout y se comprobaron sus conteos con pdfinfo. S5/S9/S12 se inspeccionaron además como imágenes: sus espacios vacíos no ocultaban tablas de requisitos. Archivos copiados de adjuntos; verificación byte a byte y hashes SHA-256:

- playbook.pdf: `d3f7d23fb6fd18dc59916290063588f4c98b20649c2f230145fd353d50900ef6`
- playbook_sesion.pdf: `e8d8c2cfc6b5f3fd5f0fe5f4b613082c5174aefefc24d1f3316a4fe480a3cdcd`

Autoridad: usuario > P > S > decisiones aprobadas > propuestas. Referencias completas en docs/01. Hay 40 requisitos: 24 IDs conservados/reconciliados y 16 añadidos. Registro de 17 asuntos: P-01 RESOLVED, P-12 APPROVED por restricción expresa del usuario, 10 OPEN y 5 PROPOSED. No se aprobó solución técnica por inferencia.

## Decisiones vigentes y bloqueos para implementación

El CSV conserva 14 columnas exactas; una fila por repetición y nota ok/spill/oom/error (S8). Recursos y ciclo 60/300/60 confirmados. Variantes Q2 confirmadas: allowDiskUse false/true; work_mem 4MB/64MB. 36 celdas/108 ejecuciones son la base declarada; el cruce completo de variantes daría 54/162 y sigue pendiente P-02.

No hay bloqueo de lectura/documentación. Antes de infraestructura: autorización nueva, versiones fijas y compatibilidad de límites en WSL2 (P-09/P-11). Antes de datos/consultas: payment.totals frente a final_total, timestamps cadena/cast, precisión, índices/identidad, empates y distribución (P-03–06, P-13/P-15). Antes de automatización: caché privilegiada, política de fallos, codificación de métricas y definición de M3 (P-07–08/P-10/P-14). Spill/OOM no se presume por el ejemplo ficticio de S7 (P-17).

## Validación y límites

Verificación documental final y ZIP: resultado registrado al final tras ejecutarla. No se han probado Docker, motores, índices, WSL2, límites, queries ni telemetría. No hay mediciones ni reporte de resultados. No se ejecutaron acciones privilegiadas ni se configuró Git; git diff --check no es aplicable sin repositorio. La ausencia de mediciones es correcta para esta fase.

## Archivos de continuidad

[Reglas](../AGENTS.md), [introducción](../README.md), [fases](../PLANS.md), [requisitos](01-requisitos-y-trazabilidad.md), [diseño](02-diseno-experimental.md), [datos/consultas](03-dataset-y-consultas.md), [arquitectura](04-arquitectura.md), [métricas](05-metricas-y-evidencia.md), [aceptación](06-validacion-y-aceptacion.md), [pendientes](07-decisiones-y-pendientes.md), [P](reference/playbook.pdf) y [S](reference/playbook_sesion.pdf).

## Próximo objetivo y reanudación

Detenerse después de entregar fase0-documentacion.zip. Esperar nueva instrucción para Fase 1. Al reanudar leer AGENTS, PLANS, este handoff y asuntos de la fase; proponer versiones concretas, contrastar latest-stable y diseñar prueba de límites locales. Arquitectura modular y métodos de recolección siguen PROPOSED. No solicitar credenciales; benchmarks definitivos únicamente en Windows/Docker Desktop/WSL2 validado. Conservar nombres de entregables de P §8.1 aunque se organicen módulos internos. La documentación permite continuar sin historial de conversación, con las puertas de decisión explícitas.

## Respaldo

fase0-documentacion.zip contendrá exactamente los 11 Markdown y los dos PDF, con docs/ y docs/reference/ conservados. Excluye carpetas auxiliares vacías del entorno (library-files, scratch, shared), que no pertenecen al proyecto, y no se incluye a sí mismo. Puede recuperarse desde /workspace/fase0-documentacion.zip; se facilita también una copia descargable cuando el entorno lo permite. La verificación se efectúa sobre los archivos finales, incluida esta versión del handoff.

## Resultado final de verificaciones

Se verificaron 11 Markdown, 30 enlaces relativos existentes, 40 IDs de requisitos únicos/consecutivos con fuente y criterio, 17 asuntos con estados consistentes, ocho fases (solo Fase 0 COMPLETED), tablas con columnas uniformes, cercas balanceadas, ausencia de conflictos y espacios finales, y cabecera CSV exacta de 14 columnas. Revisión de coherencia y trazabilidad realizada contra P/S; las incógnitas técnicas permanecen explícitas. Los dos PDF copiados son idénticos byte a byte a los adjuntos. El inventario de proyecto no contiene implementaciones ni mediciones. No se ejecutó git diff --check porque no existe repositorio Git; la revisión de espacios fue independiente.

El respaldo final se verificó mediante ZipFile.testzip (CRC), lectura de todas sus entradas y comparación byte a byte con los 13 archivos del proyecto: 11 Markdown y dos PDF. Se conservaron entradas docs/ y docs/reference/, sin rutas absolutas, duplicadas ni segmentos de escape. El ZIP queda en /workspace/fase0-documentacion.zip. No se pudo preparar una copia en /mnt/data: el entorno denegó crear ese directorio. No se elevaron permisos. Si el enlace local no permite descargarlo, recuperarlo desde el explorador de archivos del entorno en esa ruta; no hay herramienta de publicación/descarga de archivos generales disponible en esta sesión. Ninguna validación documental sustituye pruebas técnicas o benchmarks definitivos.
