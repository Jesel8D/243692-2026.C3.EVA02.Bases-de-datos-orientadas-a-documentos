# Arquitectura propuesta

El diseño general permanece PROPOSED; U3 autorizó la infraestructura de Fase 1, ya implementada; U4 autoriza generación/carga/validación de Fase 2, también implementadas con estado de validación parcial. U5 extiende la implementación a consultas/validadores/planes de Fase 3; U6 autoriza runner/matrices/pilotos de Fase 4, con validación parcial. U7 autorizó telemetría Fase 5; U8 autorizó análisis/reportes Fase 6. Las implementaciones actuales y validaciones pendientes se describen al final; no se inicia Fase 7 por su inclusión aquí. Fuentes: U §4.7; P pp.1,3–4 §§2,7,8.1; S p.10; REQ-002, 015–019, 025–026, 032, 035. Los componentes exigidos por las fuentes son requisitos; su organización e interacciones siguientes son propuestas. Sin interfaz web: no hay requisito que la justifique.

## Componentes y flujos

1. Configuración y manifiesto: semilla, perfiles, parámetros, versiones aprobadas e identificación de ejecución.
2. Generador Python → archivo JSON fuente y manifiesto → adaptadores de importación → MongoDB y PostgreSQL JSONB en Docker Compose.
3. Validador de equivalencia → habilitación del piloto → runner Python con clientes concurrentes y ciclo experimental; Bash solo como apoyo parametrizable.
4. Docker/cgroups v2 → cAdvisor (contenedores), Node Exporter (host Linux/VM) → Prometheus (scrape_interval: 1s, P p.3 §7) → recolector de evidencia. Lecturas de cgroups y registros de motores completan spill/OOM cuando haga falta.
5. Runner y recolector → evidencia original por ejecución → agregador → CSV oficial de 14 columnas → análisis Python, gráficas y reporte con enlaces a originales.

Dependencias: contratos de dataset/consultas antes del runner; infraestructura compatible antes de perfiles; semántica de métricas antes de exportación; pilotos y equivalencia antes de benchmarks definitivos. Prometheus no reemplaza por sí solo las latencias por solicitud ni identifica necesariamente spill.

## Carpetas propuestas en Fase 0 (antecedente; implementación vigente debajo)

| Ruta | Responsabilidad |
| --- | --- |
| docs/reference/ | Manuales originales |
| infra/ | Compose y perfiles parametrizados |
| config/ | Configuración no sensible y manifiestos |
| src/dataset/ | Generación/importación |
| src/queries/ | Adaptadores Q1/Q2 |
| src/benchmark/ | Runner y recolección |
| src/analysis/ | Agregación y gráficas |
| observability/ | Configuraciones de telemetría |
| tests/ | Pruebas unitarias/integración |
| scripts/ | Orquestación auxiliar |
| data/ | Dataset derivado, política de versionado pendiente |
| results/ | Originales, CSV y metadatos separados |
| reports/ | Reporte y evidencias seleccionadas |

## Antecedente de Fase 0: Windows, Docker Desktop y WSL2 (reemplazado)

Este párrafo conserva el diseño histórico de Fase 0; no es instrucción vigente de instalación. En ese diseño se contemplaba validar versiones, kernel, modo cgroups v2, presupuesto de CPU/RAM de la VM, almacenamiento, visibilidad de métricas y soporte de cada flag. mem_swappiness: 0 no puede declararse satisfecho solo porque figure en YAML: confirmar soporte real. No sustituirlo por otro límite sin documentar la diferencia y obtener aprobación. Node Exporter podría observar la VM Linux y no Windows; identificar alcance real. Los montajes de cAdvisor y permisos necesitan revisión antes de aplicarlos. No se ejecutan acciones privilegiadas en Fase 0.

P p.1 §2 indica latest-stable para ambos motores. U exige versiones explícitas una vez aprobadas: proponer seleccionar estables en una fecha registrada y fijar versión/digest antes de medir (P-11), sin inventar números de versión en Fase 0. MongoDB usará WiredTiger sin sharding; PostgreSQL la tabla orders con JSONB descrita en docs/03.

## Compatibilidad con entregables originales

P p.4 §8.1 exige en la entrega docker-compose.yml, synthetic_data_generator.py, benchmark_runner, queries/ y run_benchmarks.sh. Se conservarán esos nombres/rutas públicas; los módulos internos propuestos bajo src/ podrán ser llamados por esos puntos de entrada, sin duplicar lógica. El runner será preferentemente Python multiproceso (opción permitida por P y preferida por U), decisión de organización todavía provisional. El directorio infra/ contendría fragmentos auxiliares, no sustituiría docker-compose.yml raíz. queries/ será la ruta de consultas entregable, no una sustitución exclusiva por src/queries/.

## Plataforma y componentes implementados en Fase 1

U3 §2 aprueba Kubuntu nativo sobre Ryzen 7 5700X/32 GB x86_64. No usar Docker Desktop, WSL2 ni dependencias Windows. Docker Engine local por socket Unix y Compose Plugin. La distribución exacta está pendiente. Los exportadores futuros observarán el host Linux físico, sujeto a validación; no hay VM WSL2 en el diseño vigente.

Implementados: docker-compose.yml con mongodb y postgres, red database interna, tres volúmenes nombrados (db/configdb de MongoDB y /var/lib/postgresql para PG18), healthchecks autenticados, cuotas CFS/perfiles parametrizados, mem_limit y alternativa explícita memswap_limit=mem_limit. No auto-restart para evitar ocultar fallos. WiredTiger sin sharding; PG con JSONB nativo sin crear todavía esquema orders. Selecciones propuestas MongoDB 9.0.4-resolute y PG 18.6-bookworm, con digest; no se supone igualdad de cachés internas. Índices/identidad siguen pendientes de Fases 2–3.

Scripts de gestión y diagnóstico locales, .env no ejecutable por shell, credenciales no versionadas y override de puertos solo en loopback. La interpretación binaria de memoria y la adaptación de swap se explican en [instalación](09-instalacion-kubuntu.md). CPU y memoria deben verificarse en la hoja y ancestros: la configuración no demuestra recursos disponibles. Estado BLOCKED para cierre de Fase 1; la arquitectura general no implica que existan runner, dataset ni servicios de telemetría.

## Conexión de Fase 2 implementada

synthetic_data_generator.py y src/dataset/ generan/validan JSONL por streaming con manifiesto. dataset_tool.py y scripts/data.sh reutilizan common.sh, IDs de contenedor y clientes existentes, sin alterar Compose, puertos o versiones. La comparación lee todos los IDs o una muestra determinista. No se implementan consultas ni telemetría; ver [guía de datos](10-generacion-y-carga-datos.md) para contrato provisional y evidencia.

## Fase 3 implementada y límites de integración futura

U5 autoriza queries/: definiciones originales separadas de variantes/ejecución, oráculo y normalizadores independientes, inventario/preparación de índices y capturador de planes. QueryExecutor reutiliza DockerAdapter de Fase 2: mongosh API aggregate con opciones y psql con SET LOCAL en transacción dedicada. Durante Fase 3 los procesos cierran conexiones y no hay pool ni concurrencia; Fase 4 añade el camino nativo descrito debajo. El transporte de CLI/preflight/JSON sirve para corrección y no debe convertirse sin diseño adicional en medición de latencia del motor.

Los planes reales PG se preservan en docs/evidence/phase3/; métricas ausentes permanecen null. La infraestructura y el generador permanecen intactos. Dataset total/alias/precisión/índice temporal siguen provisionales; no se implementa una consulta alternativa para hacer pasar el índice textual. [Guía](11-consultas-y-validacion.md) documenta API, comandos, pendientes Mongo/Kubuntu y fuentes técnicas.

## Fase 4 implementada por U6

benchmark/ organiza planificación, protocolo, workers, métricas, telemetría limitada y evidencia. benchmark_runner/scripts/run_benchmarks.sh exponen plan/run/consolidate; la organización real sustituye la carpeta propuesta src/benchmark/. No hay servicio adicional ni interfaz gráfica. El único cambio de código previo, QueryExecutor.open_session en queries/execution.py, delega a queries/native.py sin modificar las consultas. CLI de corrección/preflight conserva transporte anterior; ventana medida usa sesiones persistentes psycopg/PyMongo con resultados consumidos y parámetros efectivos verificados. U6 §6 permite hilos por I/O; la mención anterior de multiproceso se conserva como antecedente del manual, con justificación operativa en [docs/12](12-automatizacion-benchmarks.md).

Configuración/archivo fuente → plan/manifiesto → scripts Fase 1 y verificación real → validación Fases 2/3 → sesiones independientes → caché explícita → warmup/medición/cooldown → diarios SQLite → cuantiles/QPS → CSV inmutable/JSON/commit → consolidación con mapa fila-variante. telemetry.py es punto de extensión para Fase 5; hoy RSS/spill faltan y la ejecución definitiva está bloqueada. No se implementa Prometheus/cAdvisor/Node Exporter. Piloto PG real, pruebas simuladas del runner y validaciones físicas pendientes se distinguen en handoff.

## Fase 5 implementada por U7

config/monitoring/compose.monitoring.yml mantiene proyecto/red/volumen propios; Prometheus scrapea cAdvisor/Node Exporter a 1s y el runner existente consulta los datos de su ventana. observability/ separa configuración/API/series/identidad/eventos/spill/proveedor/diagnósticos; scripts/monitoring.sh gestiona solo monitoreo. No se reconstruyeron results.py, metrics.py, generador, importadores, SQL/pipelines ni infraestructura de motores.

Flujo: snapshot verificado → targets/versiones/series/host/capacidad → evidencia OOM/logs/profiler y sesiones → hook de ventana monotónica/epoch del runner → muestras y operaciones reales → finalización después de cooldown/restauración → CSV existente + evidencia con hashes. Privilegios y montajes explícitos, socket ro con autoridad API no restringida, y carga adicional fuera de cgroups del motor descritos en [docs/13](13-observabilidad-y-telemetria.md). Cloud validó exportadores Docker + Prometheus binario oficial exacto por disco limitado; la pila Docker completa/Kubuntu permanece pendiente. Arquitectura desarrollada no equivale a aceptación experimental definitiva.


## Fase 6 implementada por U8

reporting/ sustituye la ruta inicial propuesta src/analysis/: loader/validation leen commits/CSV/JSON de fuentes existentes, progress calcula cobertura/ETA, statistics resume KPIs por cohorte/variante, charts genera PNG estáticos, plans resume diagnósticos y generator/exporters construyen siete secciones Markdown/HTML/PDF opcional. Scripts de terminal en scripts/ no crean servicios ni otro benchmark. Dependencias de figuras/PDF separadas del runner.

Flujo: fuentes inmutables completas → lectura estable/hashes → selección piloto/definitivo/cohortes → validación de filas/variantes → cobertura 108/162 → estadísticas y muestras RSS → figuras/tablas/planes → nueva versión de reports/ con snapshots y analysis-manifest.json. No locks del runner, consultas de motores ni procesamiento añadido a workers. El análisis puede ejecutarse en otro equipo; localmente consume CPU/IO fuera de los límites del motor y debe considerarse como carga adicional. Única adaptación previa: query_tool.py explain --file opcional vincula diagnóstico al dataset verificado fuera de medición. [Guía](14-analisis-y-reporte.md). Software preparado, cierre con resultados definitivos pendiente de Fase 7.
