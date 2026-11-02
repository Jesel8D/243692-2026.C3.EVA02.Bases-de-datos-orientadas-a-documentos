# MongoDB vs. PostgreSQL JSONB bajo contención

Proyecto académico de Bases de Datos en la Nube de la Universidad Politécnica de Chiapas. Su objetivo es comparar rendimiento, uso de recursos y estabilidad de ambos motores mediante un experimento reproducible.

Se contemplan 500,000 documentos JSON, Q1 y Q2, tres perfiles de CPU/memoria, concurrencias de 1, 10 y 50 y tres repeticiones. Las variantes Q2 están especificadas; su cruce completo daría 162 ejecuciones y requiere confirmar el alcance frente a las 108 base declaradas. Tecnologías previstas: Python, MongoDB, PostgreSQL JSONB, Docker Compose, cgroups v2, Bash, Prometheus, cAdvisor y Node Exporter.

## Estado

Fase 0 COMPLETED (2026-11-01): los dos manuales se incorporaron y reconciliaron con la documentación. Persisten decisiones de implementación identificadas en el registro; no bloquean el cierre documental. Git/GitHub no está configurado ni fue necesario. La infraestructura de Fase 1 está implementada; su cierre permanece BLOCKED por validación real de contenedores y Kubuntu físico. Las validaciones Bash/Compose pasaron; la prueba conjunta de contenedores falló por disco lleno en Cloud. Una prueba aislada posterior confirmó salud, JSONB, persistencia y límites de hoja severe de PostgreSQL en Cloud; MongoDB y la validación física/integral siguen pendientes. El dataset pasó posteriormente a implementación en Fase 2 (sección final); consultas se implementaron posteriormente en Fase 3; el runner se implementó después en Fase 4 con piloto real reducido PG. La telemetría se implementó posteriormente en Fase 5 con validación parcial; análisis/reporte se implementaron en Fase 6 con validación de software y evidencia parcial. No hay mediciones académicas definitivas.

## Documentación

- [Reglas persistentes](AGENTS.md).
- [Hoja de ruta de fases 0–7](PLANS.md).
- [Requisitos y fuentes](docs/01-requisitos-y-trazabilidad.md).
- [Diseño experimental](docs/02-diseno-experimental.md).
- [Dataset y consultas](docs/03-dataset-y-consultas.md).
- [Arquitectura propuesta](docs/04-arquitectura.md).
- [Métricas y evidencia](docs/05-metricas-y-evidencia.md).
- [Validación y aceptación](docs/06-validacion-y-aceptacion.md).
- [Decisiones y pendientes](docs/07-decisiones-y-pendientes.md).
- [Continuidad](docs/08-handoff.md).

## Estructura

Actualmente existen los tres Markdown raíz, docs/01…14, infraestructura, generador, importadores, scripts y pruebas; docs/reference/ conserva [playbook.pdf](docs/reference/playbook.pdf) y [playbook_sesion.pdf](docs/reference/playbook_sesion.pdf). La arquitectura distingue lo implementado los componentes implementados y las validaciones físicas pendientes.

Las fases previstas son: 0 documentación; 1 infraestructura; 2 dataset; 3 consultas; 4 runner; 5 telemetría; 6 integración y reporte; 7 validación local final. Fase 0 completada; Fase 1 BLOCKED con validación estática completada; Fase 2 implementada con validación parcial (IN_PROGRESS); Fase 3 implementada con validación PG parcial (IN_PROGRESS); Fase 4 implementada y parcialmente validada (IN_PROGRESS); Fase 5 implementada/parcialmente validada (IN_PROGRESS); Fase 6 implementada y parcialmente validada (IN_PROGRESS); Fase 7 pendiente. Cada fase necesita su autorización de inicio; no se avanza automáticamente. El respaldo fase0-documentacion.zip conserva los 11 Markdown y ambos PDF con sus rutas relativas.

## Infraestructura de Fase 1

Plataforma objetivo vigente: Kubuntu nativo, Docker Engine y Compose Plugin; sustituye Windows/WSL2 por decisión del usuario. Host declarado: Ryzen 7 5700X y 32 GB RAM; versión Kubuntu pendiente. MongoDB y PostgreSQL con volúmenes persistentes, red interna y healthchecks; imágenes patch/digest fijadas como selección propuesta. Perfiles baseline (4 CPU/4096m), medium (2/2048m), severe (1/1024m). La adaptación sin swap es explícita, documentada y requiere opt-in; no se afirma swappiness literal aplicada.

Leer [instalación Kubuntu](docs/09-instalacion-kubuntu.md) antes de iniciar. Las instrucciones de instalación/ejecución local aún requieren validación física. La suite estática ejecutada es `./tests/test_infrastructure.sh`; la prueba de integración `./tests/test_containers.sh --run` crea un proyecto aislado, sin eliminar volúmenes. Scripts de gestión en scripts/, perfiles en config/profiles/ y puertos opcionales loopback en config/ports.local.yml. No ejecutar benchmarks definitivos; los pilotos autorizados de Fase 4 se documentan al final.

Respaldo histórico de Fase 1: fase1-infraestructura-kubuntu.zip (sin .env reales, credenciales ni volúmenes). El ZIP anterior de Fase 0 se conserva como historial, sin incorporarlo recursivamente al nuevo respaldo.

## Dataset de Fase 2

Generador en streaming y herramientas de carga/integridad implementados, sin esperar validación física de Fase 1 (U4). Estado IN_PROGRESS: 19 unitarias y PostgreSQL real con 100 órdenes aprobados; MongoDB real, equivalencia entre ambos motores y generación/carga de 500,000 en Kubuntu pendientes. No se ejecutaron benchmarks ni Q1/Q2.

[Guía de generación y carga](docs/10-generacion-y-carga-datos.md): JSONL común, semilla configurable, manifiesto/hash, decimales exactos, fechas UTC, importación insert-only por lotes y comparación completa o muestreada. Se conserva payment.totals; el alias payment.final_total y demás concreciones no definidas por el manual son provisionales y reversibles, no decisiones aprobadas. Infraestructura de Fase 1 sin cambios.

Pruebas independientes de Docker: `python3 -m unittest discover -s tests -p 'test_dataset*.py' -v` (integración se omite sin opt-in). Preparación y ejecución local se detallan en la guía; 500,000 es el valor predeterminado preparado, no una carga validada. El respaldo de Fase 2 es fase2-dataset-kubuntu.zip; los ZIP anteriores se conservan aparte. Ese cierre histórico no autorizó Fase 3; U5 la autorizó posteriormente.

## Consultas de Fase 3

Q1/Q2 originales disponibles en queries/mongodb/ y queries/postgresql/, variantes explícitas, API Python, validación independiente y planes. [Guía de consultas](docs/11-consultas-y-validacion.md). Scripts no cambian dataset, imágenes ni límites; durante Fase 3 no había runner ni benchmarking. Los índices se inspeccionan y solo se agregan con --apply; B-Tree textual PG es propuesta con opt-in y comparabilidad pendiente.

Pruebas: 17 unitarias y nueve casos de integración PostgreSQL aprobados (incluyen vacíos, fronteras de fecha, promedios periódicos, variantes, planes, índice y Top-1000 empatado). MongoDB real no disponible; equivalencia real entre motores BLOCKED. Estado Fase 3 IN_PROGRESS por validación parcial, sin depender del equipo físico para terminar código. [Evidencia real PG](docs/evidence/phase3/README.md). Una política explícita compara promedios contra fracciones exactas; empates se validan sin cambiar el sort original.

Ejecutar unitarias/discovery: `python3 -m unittest discover -s tests -p 'test_queries*.py' -v`; integración requiere opt-in según la guía. Respaldo actual: fase3-consultas-kubuntu.zip, con proyecto/evidencia y sin secretos, datasets masivos ni cachés. Descargarlo antes de abandonar la sesión: /workspace no se asume persistente. Esa restricción histórica fue reemplazada por U6, que autoriza exclusivamente Fase 4.


## Automatización de Fase 4

Runner disponible en benchmark/, benchmark_runner y scripts/run_benchmarks.sh. [Guía de automatización](docs/12-automatizacion-benchmarks.md): matriz base 36/108 con selección explícita de Q2, extendida 54/162 sin aprobación académica inferida, filtros y piloto de una repetición. Sesiones nativas persistentes por cliente reutilizan las consultas originales; sin cambios de infraestructura/dataset/SQL.

20 unitarias del runner verifican 1/10/50 clientes simulados, ventanas, percentiles exactos, CSV, fallos, cancelación y reanudación. Un caso de integración real PG verifica sesiones Q1/Q2 y variantes, errores reales y piloto reducido de 100 documentos con reanudación; [evidencia](docs/evidence/phase4/README.md). No acredita Mongo ni rendimiento comparable. Las métricas de recursos ausentes quedan vacías y status=error; la ejecución definitiva se bloquea antes de empezar por telemetría obligatoria pendiente. No había resultados académicos definitivos ni infraestructura Prometheus implementada al cierre histórico de Fase 4; la siguiente sección registra su implementación posterior.

Preparar el venv según la guía. Planificar sin iniciar servicios: `./scripts/run_benchmarks.sh plan --matrix extended`. Los comandos run requieren selección y confirmación explícitas; no hay matriz por omisión. Fase 4 IN_PROGRESS (implementada y parcialmente validada); U7 autorizó posteriormente Fase 5. Respaldo vigente: fase4-benchmark-runner-kubuntu.zip; descargar antes de salir, porque /workspace no se supone persistente. ZIP anteriores conservados aparte.


## Observabilidad de Fase 5

Prometheus 3.15.1, cAdvisor 0.60.6 y Node Exporter 1.12.1 con imágenes/digests verificados en config/monitoring/, proyecto/red separados y TSDB persistente. Scrape 1s, timeout 800ms, retención 7d, acceso Prometheus solo loopback. scripts/monitoring.sh administra/verifica/exporta sin detener motores ni borrar series. Leer permisos de montajes/socket y activación explícita de instrumentación en [guía de telemetría](docs/13-observabilidad-y-telemetria.md).

El runner único incorpora series de contenedor identificado por ID completo, delta observado de throttling, máximo RSS en MB decimales, eventos OOM y evidencia de spill por sesión/operación. CSV de 14 columnas intacto, errores/ausencias explícitos y pilotos separados de definitivos. Fuente/documentación/metodología siguen trazadas y provisionales; no se resolvieron automáticamente las decisiones abiertas.

Cloud verificó scraping real y un piloto PG reducido con 100 órdenes, métricas completas y reanudación sin duplicados. Prometheus se ejecutó como binario oficial de la misma versión debido a falta de disco para su imagen; los dos exportadores sí corrieron en Docker. Pila completa Compose/TSDB local, Kubuntu, Mongo real y carga 500000 siguen pendientes. [Evidencia real](docs/evidence/phase5/README.md). Fase 5 IN_PROGRESS, implementada/parcialmente validada; U8 autorizó posteriormente Fase 6; no hay matriz definitiva. Respaldo vigente: fase5-telemetria-kubuntu.zip; descargar antes de abandonar la sesión.


## Análisis y reporte de Fase 6

Sistema offline en reporting/: lee commits/CSV/manifiestos/evidencia existentes sin bloquear ni modificar al runner. Produce reportes progresivos Markdown y HTML imprimible con las siete secciones de P p.4 §8.3, PDF opcional, tablas estadísticas y gráficas P99/concurrencia, throttling/QPS y RSS temporal real. Variantes/cohortes/pilotos permanecen separados; los requisitos de informe FINAL impiden ocultar faltantes.

[Guía operativa y referencia rápida Kubuntu](docs/14-analisis-y-reporte.md). Instalar requirements-reporting.txt en un venv; requirements-reporting-pdf.txt añade PDF opcional. Scripts aceptan rutas configurables y no consultan motores durante el análisis:

```bash
./scripts/benchmark_progress.sh --inputs /ruta/experimento --scope definitive
./scripts/generate_report.sh generate --inputs /ruta/experimento --scope definitive --mode partial --output /ruta/informes
./scripts/generate_report.sh generate --inputs /ruta/experimento --scope definitive --mode final --allow-partial --audit-all --plans /ruta/planes --output /ruta/informes --pdf
```

Fase 6 implementada y parcialmente validada: 33 pruebas nuevas aprobadas; suite general 126 casos, 114 aprobados y 12 integraciones omitidas. No se iniciaron servicios ni consultas/benchmarks nuevos. [Reportes disponibles](reports/README.md): un informe académico vacío expresa 0/108 mediciones, y un informe separado analiza exclusivamente un piloto PG real histórico con aviso no definitivo. Sin resultados académicos, no hay conclusiones comparativas. Estado IN_PROGRESS conserva la validación con resultados definitivos para Fase 7.

Presupuesto: 108 × 420s = 12h36 de protocolo; solo 24min de margen dentro de 13h, sin contar preparación, caché, drenaje, fallos o exportación. Las 162 repeticiones demandan 18h54 y siguen pendientes de aprobación. No se modifica el protocolo para ajustarlo al tiempo. Respaldo de entrega: fase6-reporte-kubuntu.zip, con originales y reportes reales identificados; descargar antes de abandonar esta sesión. No se inicia Fase 7.
