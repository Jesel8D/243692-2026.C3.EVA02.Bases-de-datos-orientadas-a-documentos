# Hoja de ruta

Estados: PENDING, IN_PROGRESS, BLOCKED, COMPLETED. No se avanza automáticamente ni se declara COMPLETED sin evidencia. Los IDs abreviados siguientes llevan prefijo REQ-; véase [trazabilidad](docs/01-requisitos-y-trazabilidad.md). Fase 0 COMPLETED al 2026-11-01: ambos manuales incorporados, 40 requisitos trazados y pendientes documentados. Fase 1 BLOCKED (configuración validada; ejecución/validación local pendientes); Fase 2 IN_PROGRESS (implementada, validación parcial); Fase 3 IN_PROGRESS (consultas implementadas, validación PG parcial); Fase 4 IN_PROGRESS (implementada y parcialmente validada); Fase 5 IN_PROGRESS (implementada/parcialmente validada); Fase 6 IN_PROGRESS (implementada, validación de software realizada y validación definitiva pendiente); Fase 7 PENDING. U4 autoriza continuar Fase 2 sin bloquear por pruebas locales pendientes de Fase 1. Git/GitHub no es condición para este cierre (U2).

## Fase 0. Fundamentación y documentación — COMPLETED

- **Objetivo:** Extraer fuentes y preparar documentación verificable.
- **Alcance:** Solo análisis, arquitectura propuesta, trazabilidad y criterios.
- **Requisitos:** 020–024, 040
- **Dependencias:** Manuales originales disponibles; /workspace es la raíz documental, sin necesidad de Git.
- **Archivos esperados:** AGENTS.md, README.md, PLANS.md, docs/01–08.
- **Actividades:** Inspeccionar fuentes, registrar faltantes y redactar documentos.
- **Validaciones:** Inventario, enlaces, coherencia y alcance.
- **Criterios de aceptación:** Fuentes revisadas con páginas; decisiones explícitas; handoff fiel.
- **Riesgos:** Ambigüedades de implementación registradas en docs/07; Git no bloquea documentación.
- **Condición de cierre:** Satisfecha: lectura completa P/S, reconciliación, revisión documental y respaldo verificado; evidencia en docs/08-handoff.md. La autorización de Fase 1 llegó por U3; U4 autorizó posteriormente Fase 2, sin avance automático a Fase 3.

## Fase 1. Infraestructura y Docker — BLOCKED

- **Objetivo:** Preparar ambos motores y perfiles controlados.
- **Alcance:** Docker Engine nativo, Compose Plugin y compatibilidad en Kubuntu (U3 reemplaza WSL2).
- **Requisitos:** 001–002, 007, 017, 019, 025–026, 028, 041–047
- **Dependencias:** Fase 0 cerrada y Fase 1 autorizada por U3. Versiones propuestas verificadas por manifiesto/pull; aceptación definitiva de selección/adaptación y pruebas locales pendientes.
- **Archivos esperados:** docker-compose.yml, .env.example, .gitignore, config/, scripts/, tests/ y docs/09; ya creados. No se necesita infra/ vacía.
- **Actividades:** Fijar versiones aprobadas, preparar salud y límites.
- **Validaciones:** Bash y Compose aprobados para 3 perfiles; controles negativos y loopback aprobados. Pull de imágenes confirmado. Prueba conjunta abortó por disco lleno; salud, persistencia y límites de ambos motores aún no validados. Véase handoff para pruebas aisladas adicionales.
- **Criterios de aceptación:** Ambos motores operativos y perfiles efectivos demostrados.
- **Riesgos:** Versión Kubuntu desconocida, swappiness no representable literalmente en v2, ancestros CPU/RAM y disco insuficiente en Cloud.
- **Condición de cierre:** Pendiente: salud/persistencia de ambos motores, límites/ancestros/swap de A/B/C y aceptación documentada de adaptación en Kubuntu físico; no marcar COMPLETED antes de ello.

## Fase 2. Dataset sintético — IN_PROGRESS

- **Objetivo:** Generar e importar contenido reproducible.
- **Alcance:** 500,000 documentos en ambos motores.
- **Requisitos:** 003–005, 015, 019, 023, 025, 027–028 (compatibilidad), 048–054
- **Dependencias:** Infraestructura implementada; U4 permite desarrollo sin cierre físico de Fase 1. Contrato provisional explícito y reversible; aceptación definitiva pendiente.
- **Archivos esperados:** synthetic_data_generator.py, dataset_tool.py, src/dataset/, siete scripts de datos, pruebas unitarias/integración y docs/10; implementados.
- **Actividades:** Generar con semilla, importar y comparar.
- **Validaciones:** 19 unitarias aprobadas; generación CLI de 100 repetida con bytes/hash idénticos; PostgreSQL real 100, lectura completa/muestra, resume y rollback aprobados. MongoDB real, equivalencia real entre ambos y carga local de 500,000 pendientes.
- **Criterios de aceptación:** Contenido equivalente completo y generación repetible.
- **Riesgos:** Tipos, fórmulas, alias, distribución e identidad son adaptaciones provisionales; Mongo y carga completa sin validar físicamente; no extrapolar prueba pequeña a 500,000.
- **Condición de cierre:** Desarrollo disponible sin bloqueo por Fase 1; no se marca COMPLETED mientras falten integración Mongo/ambos y validación de la carga objetivo. Estado IN_PROGRESS refleja alcance implementado y pruebas disponibles ejecutadas, con pendientes explícitos.

## Fase 3. Consultas equivalentes — IN_PROGRESS

- **Objetivo:** Validar Q1/Q2 y variantes.
- **Alcance:** Adaptadores e índices exigidos.
- **Requisitos:** 006, 011, 023, 028–031, 036, 055–063
- **Dependencias:** U5 autoriza desarrollo sin equipo físico. Manuales y código Fase 2 inspeccionados; contrato/índice temporal siguen provisionales y condicionan validación final.
- **Archivos esperados:** queries/ con SQL/pipelines/variantes/API/oráculo/índices/planes, query_tool.py, scripts/queries.sh, pruebas y docs/11; implementados. Evidencia real pequeña en docs/evidence/phase3/.
- **Actividades:** Implementar consultas originales y parámetros de variantes.
- **Validaciones:** 17 unitarias; 9 casos reales PG con 10/100/1000, controlado, vacío y Top-1000 con 1005; variantes/sesiones/planes/índices comprobados. Mongo real y equivalencia entre ambos BLOCKED por disponibilidad Cloud; no se sustituyen por unitarias.
- **Criterios de aceptación:** Consultas fieles y validador independiente; cada carga/variante contra fuente, equivalencia real ambos motores y política temporal/numérica/índices documentada y aceptada.
- **Riesgos:** Campos, fechas, precisión, empates y alcance de variantes pendientes (P-02–06, P-15).
- **Condición de cierre:** Desarrollo disponible; no declarar COMPLETED mientras falten Mongo real, equivalencia cruzada y decisión de índice/precisión/alias. Matriz definitiva de benchmarking sigue pendiente y no se ejecuta en esta fase.

## Fase 4. Automatización de benchmarks — IN_PROGRESS

- **Objetivo:** Orquestar ciclo y exportar CSV.
- **Alcance:** Runner Python, concurrencias y repeticiones.
- **Requisitos:** 008–012, 014–015, 031, 034–035, 038–039, 064–074
- **Dependencias:** U6 autoriza desarrollo sin equipo físico. Consultas Fase 3 reutilizadas; Mongo/equivalencia/índice y contrato metodológico siguen pendientes para ejecución definitiva.
- **Archivos esperados:** benchmark_runner, benchmark/, queries/native.py, scripts/run_benchmarks.sh y benchmark_environment.sh, requirements-benchmark.txt, tests/test_benchmark*.py, docs/12 y evidencia; implementados.
- **Actividades:** Matrices 108/162 y filtros, clientes independientes, 60/300/60, piloto, R7/QPS, telemetría modular, CSV/manifiestos y reanudación segura.
- **Validaciones:** 20 unitarias de runner, conteos 36/108 y 54/162, clientes simulados 1/10/50, CSV/reanudación/cancelación. Integración PG real de sesiones y piloto reducido con 100 documentos aprobada. Regresión y comprobaciones estáticas en handoff.
- **Criterios de aceptación:** Una fila por repetición finalizada, trazabilidad de variante sin columna extra, fallos/ausencias explícitos y bloqueo definitivo sin preflight completo.
- **Riesgos:** Caché manual no prueba limpieza; GIL/diarios/capacidad del runner, CPU cgroup con bordes aproximados, RSS/spill ausentes y Mongo no integrado.
- **Condición de cierre:** Desarrollo y piloto PG disponibles. Validación parcial: integración Mongo, 1/10/50 reales en ambos, Kubuntu y telemetría obligatoria pendientes; no declarar COMPLETED ni habilitar mediciones definitivas por pruebas simuladas.

## Fase 5. Observabilidad y telemetría — IN_PROGRESS

- **Objetivo:** Capturar recursos y estabilidad.
- **Alcance:** Prometheus con scrape_interval 1s, cAdvisor, Node Exporter y evidencia lateral.
- **Requisitos:** 012–013, 019, 032–034, 039, 075–085
- **Dependencias:** U7 autoriza desarrollo sin equipo físico; infraestructura/runner existentes. Contratos/índices/Mongo y aceptación de método siguen pendientes para definitivo.
- **Archivos esperados:** observability/, config/monitoring/, scripts/monitoring.sh, tests/test_observability*.py y docs/13; implementados.
- **Actividades:** Stack fijado/scrape 1s, identidad exacta, series/ventanas/clock bridge, journales OOM/spill y hooks en runner único.
- **Validaciones:** Unitarias de muestreo/errores/spill/OOM/CSV/recuperación y regresión; scraping real con exportadores Docker y Prometheus binario oficial 3.15.1, piloto PG reducido 100 con todos los campos/reanudación. Evidencia y conteos vigentes en handoff.
- **Criterios de aceptación:** Telemetría integrada/identificada; ausencias/gaps no válidos para estudio final; CSV intacto/evidencia por intento y límites de atribución explícitos.
- **Riesgos:** Socket Docker poderoso aun ro, instrumentación/CPU/IO, picos/bordes omitidos, clock drift, profiler capped/restore tras muerte abrupta, disco VFS y entorno anidado.
- **Condición de cierre:** Desarrollo y pruebas disponibles realizados; validación parcial. No COMPLETED hasta pila Docker/TSDB persistente y ambos motores con fuentes reales en Kubuntu, decisiones metodológicas y sobrecarga verificadas.

## Fase 6. Integración, análisis y reporte — IN_PROGRESS

- **Objetivo:** Generar informes académicos incrementales reproducibles desde resultados reales disponibles.
- **Alcance:** Análisis offline, progreso, estadísticas descriptivas, gráficas exigidas y siete secciones HTML/Markdown; PDF opcional. No generar nuevas mediciones.
- **Requisitos:** 014, 016, 019, 036–039, 086–095; P p.4 §8.3 y U8.
- **Dependencias:** U8 autoriza desarrollo sin equipo físico; commits/manifiestos del runner único, CSV exacto y evidencia de Fases 3–5. Faltantes finales no se transforman en datos.
- **Archivos esperados:** reporting/, scripts/generate_report.sh y benchmark_progress.sh, requirements-reporting*.txt, tests/test_reporting*.py, reports/, docs/14 y evidencia de revisión; implementados.
- **Actividades:** Snapshots sin locks, coherencia/hashes/cohortes, cobertura 108/162, estadísticas/contrastes por variante, curvas de muestras reales, planes vinculados, exportación y continuidad.
- **Validaciones:** 33 pruebas nuevas aprobadas; regresión 126 descubiertas/114 aprobadas/12 omitidas. Análisis offline del piloto PG histórico real y reporte académico vacío; no consultas nuevas. Sintaxis/Compose/enlaces/archivo final documentados en handoff.
- **Criterios de aceptación:** CSV intacto y fuentes inmutables; reportes parciales explícitos, series ausentes visibles, matrices/cohortes separadas y FINAL bloqueado sin todas las repeticiones/evidencias verificadas.
- **Riesgos:** Confundir P99 promedio con combinado; comparación Q2 no equivalente; snapshots no sustituyen diarios completos; 13h insuficientes si overhead excede 24min; evidencia masiva/física ausente.
- **Condición de cierre:** Implementación y verificaciones disponibles terminadas. IN_PROGRESS expresa validación parcial: no hay mediciones definitivas para demostrar informe FINAL real. Fase 7 debe validar pipeline con resultados locales auténticos y conservar diagnósticos vinculados al mismo dataset; no se inicia automáticamente.

## Fase 7. Validación local final — PENDING

- **Objetivo:** Obtener mediciones definitivas locales.
- **Alcance:** Matriz aprobada en Kubuntu nativo y cierre del reporte; plataforma histórica Windows/WSL2 reemplazada por U3.
- **Requisitos:** 001–019, 025–039
- **Dependencias:** Fases técnicas verificadas, equipo validado y autorización de fase.
- **Archivos esperados:** results/, evidencia local, reports/ final y handoff.
- **Actividades:** Ejecutar matriz, auditar fallos y completar reporte con datos reales.
- **Validaciones:** Cobertura, equivalencia, integridad CSV y repetibilidad.
- **Criterios de aceptación:** Todas las ejecuciones/evidencias explicadas y reporte trazable.
- **Riesgos:** Tiempo, recursos, OOM y carga externa.
- **Condición de cierre:** Validación local completa, limitaciones registradas y reporte final revisado.

Las rutas de fases posteriores siguen propuestas; infraestructura y módulos de dataset/carga ya están implementados con validaciones pendientes indicadas. La telemetría y el contrato del runner se diseñan coordinadamente; Fase 4 ofreció lecturas cgroup limitadas; Fase 5 integra fuentes reales de RSS/spill y ventanas con validación parcial, sin cerrar la aceptación física/experimental. Cada cierre actualiza docs/08-handoff.md.

## Puertas de implementación

Historial: U3 autorizó exclusivamente Fase 1. U4 autorizó Fase 2 sin cerrar ficticiamente Fase 1; U5 autorizó Fase 3; U6 autorizó Fase 4; U7 autorizó Fase 5; U8 autoriza exclusivamente Fase 6 y prohíbe Fase 7/benchmarks definitivos. La infraestructura está preparada con validación estática, pero el cierre está BLOCKED. Confirmar versiones propuestas y validar Kubuntu nativo/cgroups; la ausencia de GitHub no es bloqueo. Las consultas y el dataset requieren resolver payment, fechas, tipos, índices e identidad. La propuesta de 162 ejecuciones no está aprobada. La arquitectura modular y los métodos de medición siguen propuestos, con nombres públicos exigidos conservados. Fase 6 prepara el reporte de siete secciones; Fase 7 lo cierra con evidencia definitiva local.
