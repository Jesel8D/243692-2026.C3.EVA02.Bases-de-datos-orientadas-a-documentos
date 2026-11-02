# Requisitos y trazabilidad

## Fuentes verificadas y autoridad

- U: instrucciones del usuario «FASE 0 — FUNDAMENTACIÓN Y PLANIFICACIÓN DEL PROYECTO», secciones numeradas, sin páginas.
- U8: solicitud «FASE 6 — ANÁLISIS ESTADÍSTICO, GRÁFICAS Y REPORTE ACADÉMICO AUTOMÁTICO», secciones numeradas, sin páginas.
- U7: solicitud «FASE 5 — OBSERVABILIDAD, TELEMETRÍA Y CAPTURA DE MÉTRICAS EXPERIMENTALES», secciones numeradas, sin páginas.
- U6: solicitud «FASE 4 — AUTOMATIZACIÓN DE BENCHMARKS Y MATRIZ EXPERIMENTAL», secciones numeradas, sin páginas.
- U5: solicitud «FASE 3 — IMPLEMENTACIÓN Y VALIDACIÓN DE CONSULTAS EQUIVALENTES», secciones numeradas, sin páginas.
- U4: solicitud «FASE 2 — DATASET SINTÉTICO REPRODUCIBLE Y CARGA EN MONGODB / POSTGRESQL», secciones numeradas, sin páginas.
- U3: solicitud «FASE 1 — INFRAESTRUCTURA DOCKER REPRODUCIBLE PARA KUBUNTU», secciones numeradas, sin páginas.
- U2: solicitud «Incorporación de manuales y reconciliación documental», instrucciones 1–8 y respaldo obligatorio, sin páginas.
- P: [playbook.pdf](reference/playbook.pdf), 4 páginas, especificación técnica principal.
- S: [playbook_sesion.pdf](reference/playbook_sesion.pdf), 13 páginas/diapositivas, complemento académico.

Fecha de revisión: 2026-11-01. Se leyó el texto completo de las 17 páginas; las páginas S5, S9 y S12 se revisaron además visualmente por sus espacios vacíos en la extracción (no contienen tablas adicionales). Páginas referidas son las posiciones del PDF, coincidentes con sus folios. Jerarquía: usuario > P > S > decisiones aprobadas > propuestas.

Los 24 IDs iniciales se conservan y se reconciliaron individualmente. Se añaden REQ-025–040: 40 requisitos al cierre de Fase 0; U3 añade REQ-041–047; U4 añade REQ-048–054; U5 añade REQ-055–063; U6 añade REQ-064–074; U7 añade REQ-075–085; U8 añade REQ-086–095 (95 en total). Las exigencias de manuales son normativas para este proyecto; sus indeterminaciones se registran sin inventar soluciones. Obligatorio (usuario) distingue restricciones adicionales a los PDF. Propuestas de método figuran en los documentos de diseño, no como requisitos del profesor.

| ID | Categoría | Descripción | Fuente/sección | Carácter | Fase | Verificación |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-001 | funcional | Comparar MongoDB y PostgreSQL JSONB bajo contención controlada. | U §1, 3; P p.1, objetivo; S p.3 | Obligatorio (usuario y manual; límites en pendientes) | 1–7 | Ambos motores ejecutan cargas equivalentes con condiciones registradas. |
| REQ-002 | técnico | Usar Docker, Docker Compose y cgroups v2. | U §3, 4.1; P p.1, objetivo; p.4 §8.1 | Obligatorio (usuario y manual; límites en pendientes) | 1 | Inspección de servicios y límites efectivos. |
| REQ-003 | datos | Generar 500,000 registros JSON sintéticos. | U §3; P p.1 §4; S p.3 | Obligatorio (usuario y manual; límites en pendientes) | 2 | Conteo exacto e importación completa. |
| REQ-004 | datos | Estructuras anidadas de aproximadamente tres niveles. | U §3; P p.1 §4 (3 niveles); S p.3 (~3) | Obligatorio (usuario y manual; límites en pendientes) | 2 | Validación estructural sobre dataset. |
| REQ-005 | datos | Promedio de tres ítems por registro. | U §3; P p.1 §4 | Obligatorio (usuario y manual; límites en pendientes) | 2 | Calcular y registrar promedio; tolerancia pendiente. |
| REQ-006 | funcional | Implementar Q1 y Q2 semánticamente equivalentes. | U §3, 4.6; P pp.2–3 §5; S pp.6–7 | Obligatorio (usuario y manual; límites en pendientes) | 3 | Comparación de resultados sobre el mismo dataset. |
| REQ-007 | experimental | Perfiles baseline: 4 CPU/4096 MB; medium: 2/2048; severe: 1/1024; mem_swappiness: 0 en todos. | U §3; P p.1 §3 | Obligatorio (usuario y manual; límites en pendientes) | 1, 7 | Verificar límites efectivos y compatibilidad; no sustituir swappiness silenciosamente. |
| REQ-008 | experimental | Concurrencias de 1, 10 y 50 clientes. | U §3; P p.3 §6 | Obligatorio (usuario y manual; límites en pendientes) | 4 | Registro de clientes activos y barrera de inicio. |
| REQ-009 | experimental | Tres repeticiones por escenario. | U §3; P p.3 §6; S p.8 | Obligatorio (usuario y manual; límites en pendientes) | 4, 7 | Auditar identificadores y cobertura de matriz. |
| REQ-010 | experimental | Limpieza de caché, warmup 60 s, medición 300 s y cooldown 60 s. | U §3; P p.3 §6 | Obligatorio (usuario y manual; límites en pendientes) | 4, 7 | Tiempos por etapa y evidencia del procedimiento de caché aprobado. |
| REQ-011 | experimental | Analizar 36 escenarios base, 108 ejecuciones y variantes Q2 antes de fijar total. | U §3, 4.5; P p.3 §6; S pp.7–8 (ambigüedad de cruce) | Obligatorio (usuario y manual; límites en pendientes) | 0, 3, 4 | Matriz aprobada sin variantes implícitas. |
| REQ-012 | métricas | Medir QPS, p50/p95/p99, throttling, max RSS, spill y status. | U §4.8; P p.3 §7 y p.4 §8.2 | Obligatorio (usuario y manual; límites en pendientes) | 4, 5 | Evidencia cruda y agregación verificable. |
| REQ-013 | métricas | Documentar telemetría del manual y eventos OOM. | U §4.8; P p.3 §7; S pp.5,10 | Obligatorio (usuario y manual; límites en pendientes) | 0, 5 | Revisar manual y enlazar eventos con ejecuciones. |
| REQ-014 | entrega | Exportar CSV con las 14 columnas exactas de la sección 4.8. | U §4.8; P p.4 §8.2; S p.9 | Obligatorio (usuario y manual; límites en pendientes) | 4 | Validar cabecera, tipos y cobertura. |
| REQ-015 | reproducibilidad | Automatizar tareas mediante scripts; favorecer Python y parametrización. | U §3, 4.1, 5.4; P p.4 §8.1 (k6 o Python); preferencia Python de U | Obligatorio (usuario y manual; límites en pendientes) | 2–6 | Repetición con misma configuración y semilla. |
| REQ-016 | entrega | Entregar reporte técnico reproducible y evidencias. | U §3, 4.9; P p.4 §8.3; S pp.10–11 | Obligatorio (usuario y manual; límites en pendientes) | 6, 7 | Trazabilidad de gráficas a datos originales. |
| REQ-017 | entorno | Ejecutar benchmarks definitivos en Kubuntu nativo sobre hardware físico; reemplaza Windows/Docker Desktop/WSL2 del requisito original. | U3 §2 (reemplaza U §3); P-18 conserva historia | Obligatorio (usuario) | 1, 7 | Inventario local y piloto satisfactorio. |
| REQ-018 | entorno | Usar Codex Cloud para desarrollo y preparación, no mediciones definitivas. | U §3 | Obligatorio (usuario) | 0–7 | Clasificar origen y finalidad de cada evidencia. |
| REQ-019 | reproducibilidad | Fijar versiones una vez aprobadas, conservar configuraciones y resultados originales, usar control de cambios. | U §4.1, 5.4; P p.1 §2 (latest-stable); S p.5 (registrar versión) | Obligatorio (usuario y manual; límites en pendientes) | 1–7 | Manifiesto de versiones/configuraciones y revisión del historial. |
| REQ-020 | reproducibilidad | No inventar requisitos, fuentes, mediciones ni resultados. | U §2, 5 | Obligatorio (usuario) | 0–7 | Auditoría de fuentes y procedencia. |
| REQ-021 | entrega | Crear AGENTS, README, PLANS y docs/01–08 con enlaces y handoff coherentes. | U §4, 7 | Obligatorio (usuario) | 0 | Inventario y revisión documental. |
| REQ-022 | entorno | Limitar Fase 0 a documentación; sin privilegios, borrado, cambios globales, despliegues, credenciales, benchmarks, commits ni pushes. | U §5.5, 6 | Obligatorio (usuario) | 0 | Inspección de archivos y acciones realizadas. |
| REQ-023 | datos | Revisar payment.totals/final_total, timestamps, precisión e índices sin corrección silenciosa. | U §4.6; P p.2 §4 frente a pp.2–3 §5.2 | Obligatorio (usuario y manual; límites en pendientes) | 0, 2, 3 | Resolver cada discrepancia contra PDF y registrar aprobación. |
| REQ-024 | experimental | Documentar preguntas M1, M2 y M3 fielmente a las fuentes. | U §4.5; P p.1 §1; S p.4 | Obligatorio (usuario y manual; límites en pendientes) | 0 | Transcribir con página cuando estén disponibles. |
| REQ-025 | técnico | MongoDB: colección orders sin sharding, WiredTiger; PostgreSQL: orders (id UUID PRIMARY KEY, data JSONB). | P p.1 §2 | Obligatorio (fuente indicada) | 1–3 | Inspección de motor, tabla, colección y configuración. |
| REQ-026 | técnico | Motores latest-stable según manual; seleccionar y congelar versiones concretas para reproducibilidad tras aprobación, sin usar una etiqueta mutable en mediciones. | P p.1 §2; U §4.1 | Obligatorio (fuente indicada) | 1 | Registrar fecha de selección, versión y digest; ver P-11. |
| REQ-027 | datos | Atributos order_id, timestamp, customer, items, payment y metadata con subcampos enumerados. | P pp.1–2 §4 | Obligatorio (fuente indicada) | 2 | Contrato completo en docs/03; validar campos sin inventar tipos no especificados. |
| REQ-028 | técnico | MongoDB: índices simples timestamp y order_id. PostgreSQL: PK id y B-Tree de timestamp extraído. | P p.1 §2 | Obligatorio (fuente indicada) | 1–3 | Inventario de índices; expresión temporal pendiente P-06. |
| REQ-029 | funcional | Q1: desanidar items, price > 50, subtotal qty*price; suma, promedio y conteo por país/categoría. | P p.2 §5.1; S p.6 | Obligatorio (fuente indicada) | 3 | Comparar grupos, conteos y cálculos con manual. |
| REQ-030 | funcional | Q2: completed, timestamp >= 2026-01-01T00:00:00Z, final_total descendente, Top-1000; sin índice previo del total. | P pp.2–3 §5.2; S p.7 | Obligatorio (fuente indicada) | 3 | Validar filtro, proyección, orden y ausencia de índice del total. |
| REQ-031 | experimental | Reportar Q2 allowDiskUse false/true y work_mem 4MB/64MB, sin prometer que ocurra spill. | P p.2 §5.2; S p.7 | Obligatorio (fuente indicada) | 3–7 | Configuración efectiva y resultado/eventos por variante. |
| REQ-032 | métricas | cAdvisor para contenedores, Node Exporter para host (I/O, disco, swap), Prometheus scrape_interval 1s. | P p.3 §7 | Obligatorio (fuente indicada) | 5 | Configuración y series efectivas, con alcance host/VM declarado. |
| REQ-033 | métricas | Conservar container_cpu_cfs_throttled_seconds_total (s), container_memory_rss_bytes (bytes), disk_spill_detected y oom_killed (booleanos). | P p.3 §7 | Obligatorio (fuente indicada) | 5 | Evidencia cruda y conversión documentada al CSV. |
| REQ-034 | entrega | Una fila CSV por repetición y nota de estado ok/spill/oom/error; límites reales, versión y spill/OOM por celda. | S pp.5,8–9 | Obligatorio (fuente indicada) | 4–7 | Auditar filas y evidencia lateral sin columnas nuevas. |
| REQ-035 | entrega | Entregar docker-compose.yml, synthetic_data_generator.py, benchmark_runner (P: k6 o Python multiproceso; U6 §6 admite threading justificado), queries/ y run_benchmarks.sh. | P p.4 §8.1; S p.10; U6 §6 | Obligatorio (fuente indicada) | 1–4 | Inventario de entregables exactos; Python favorecido por U. |
| REQ-036 | entrega | Reporte con siete secciones, gráficas P99/concurrencia, throttling/QPS y RSS; planes explain executionStats y EXPLAIN ANALYZE BUFFERS. | P p.4 §8.3; S pp.10–12 | Obligatorio (fuente indicada) | 6–7 | Checklist de docs/06 y trazabilidad a evidencia real. |
| REQ-037 | experimental | Verificar baseline comparable, reportar repeticiones y resumen media/mediana justificado; responder con tablas, figuras y planes. | S p.11; P p.4 §8.3 | Obligatorio (fuente indicada) | 6–7 | Reporte responde seis preguntas del revisor; estadístico por aprobar. |
| REQ-038 | experimental | Antes de matriz completa: levantar A/B/C, probar una celda piloto y validar CSV. | S p.13 | Obligatorio (fuente indicada) | 1,4–7 | Piloto identificado y CSV válido antes de ejecución definitiva. |
| REQ-039 | experimental | Responder M3: huella CPU y memoria por cada 1,000 documentos procesados; definición operativa pendiente. | P p.1 §1 M3; S p.4 | Obligatorio (fuente indicada) | 4–7 | Denominador y unidades aprobados; evidencia lateral sin alterar CSV. |
| REQ-040 | entrega | Incorporar originales y entregar ZIP con 11 Markdown, dos PDF y estructura de carpetas; verificar integridad. | U2, respaldo obligatorio | Obligatorio (fuente indicada) | 0 | Comparar bytes de originales, contenido ZIP, CRC y rutas. |

## Resultado de reconciliación de los 24 originales

REQ-001–016 y 024 tienen correspondencias en P/S detalladas en la tabla; REQ-015 conserva la preferencia Python del usuario aunque P permite k6. REQ-017–018 y 020–022 son restricciones del usuario, no exigencias atribuidas al profesor. REQ-019 conserva el congelamiento de versiones del usuario frente a latest-stable de P. REQ-023 pasa de advertencia a discrepancia comprobada. Ningún ID se elimina ni se declara satisfecho por implementación inexistente. REQ-004 conserva aproximadamente tres niveles por U/S, documentando que P dice tres. Git/GitHub no es una dependencia de Fase 0 (U2); control de cambios queda planificado para fases posteriores.

## Adiciones y cobertura de infraestructura (U3)

REQ-017 cambia plataforma por instrucción explícita posterior, no por conveniencia técnica. Los requisitos de datos/consultas/medición no cambian. Infraestructura cubre REQ-002/007/017/019/025/026/035 parcialmente: Compose/scripts/configuración disponibles, ejecución local aún pendiente. REQ-028 conserva índices en Fases 2–3 sin crear índices prematuros. Python, automatización y CSV de fases posteriores no se implementan aquí.

| ID | Categoría | Descripción | Fuente/sección | Carácter | Fase | Verificación |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-041 | entorno | Docker Engine nativo y Compose Plugin en Kubuntu x86_64, sin Windows/WSL2/Desktop; identificar versión local. | U3 §§2,6,11 | Obligatorio usuario | 1,7 | check_environment y evidencia física |
| REQ-042 | técnico | Dos servicios oficiales con patch explícito, persistencia, red privada, salud y límites comparables. | U3 §§4–5 | Obligatorio usuario | 1 | Compose + pruebas de conectividad/persistencia |
| REQ-043 | técnico | Verificar quota/period, memoria, swap, cgroups y configuración efectiva; documentar alternativa a swappiness si no soportado. | U3 §6 | Obligatorio usuario | 1 | verify_resources en 3 perfiles y ancestros |
| REQ-044 | reproducibilidad | .env.example, perfiles, imágenes, puertos/credenciales locales/proyecto parametrizados y .gitignore. | U3 §7 | Obligatorio usuario | 1 | Suite estática y exclusión de secretos |
| REQ-045 | entorno | Scripts Bash de diagnóstico, instalación asistida sin cambios privilegiados, inicio/parada y salud; sin eliminación de datos. | U3 §§8–9 | Obligatorio usuario | 1 | Bash, casos negativos, revisión de comandos y pruebas locales |
| REQ-046 | entrega | Pruebas automatizadas y guía Kubuntu; distinguir validación estática/configuración/contenedores/local, sin avanzar a Fase 2. | U3 §§10–13,15 | Obligatorio usuario | 1 | tests/ y docs/09; handoff con pendientes |
| REQ-047 | entrega | ZIP Fase 1 con documentación, scripts, configuraciones, pruebas y manuales, sin .env reales/secretos/datos/cachés/volúmenes. | U3 §14 | Obligatorio usuario | 1 | CRC, rutas y comparación byte a byte |

## Adiciones de dataset y carga (U4)

U4 permite concretar provisionalmente el contrato y continuar sin equipo físico; no convierte propuestas P-03–06/P-13 en decisiones aprobadas. La infraestructura, versiones y límites permanecen intactos. El predeterminado 500,000 está implementado, no validado empíricamente en Cloud ni Kubuntu. REQ-003–005/019/023/025/027 tienen cobertura de software y PG pequeño; integración de ambos/carga objetivo sigue pendiente.

| ID | Categoría | Descripción | Fuente/sección | Carácter | Fase | Verificación |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-048 | funcional | Generador Python, count predeterminado 500000, semilla/configuración, argumentos, streaming, UUID/fechas/números válidos y progreso. | U4 §§3–8,14 | Obligatorio usuario | 2 | Unitarias, CLI pequeña y hash; carga objetivo local pendiente |
| REQ-049 | datos | Conservar todos los campos del manual y totals; adaptación final_total explícita, reversible y provisional; distribuciones propuestas sin atribución al profesor. | U4 §§4–7; P pp.1–2 §4, pp.2–3 §5.2 | Obligatorio fuente indicada | 2 | Validador estricto, cálculos y layouts; docs/03 y docs/10 |
| REQ-050 | reproducibilidad | Manifiesto con semilla/count/esquema/configuración/hash y fecha separada; mismas entradas/versiones producen mismo dataset lógico. | U4 §8 | Obligatorio usuario | 2 | Generación repetida y golden hashes |
| REQ-051 | funcional | Importar orders en ambos motores por lotes, autenticación/configuración, UUID/duplicados/conteos y transacciones PG; sin eliminación automática. | U4 §§9–10 | Obligatorio usuario | 2 | Interfaces unitarias y suite integración por motor/ambos |
| REQ-052 | datos | Verificar IDs, campos/tipos, fechas/importes/items/pagos y equivalencia semántica; selección de muestras determinista. | U4 §11 | Obligatorio usuario | 2 | Comparación completa frente a fuente y muestra etiquetada parcial |
| REQ-053 | entrega | Scripts operativos, unitarias 10/100/1000 e integración disponible; guía y evidencia honesta Cloud/Kubuntu, sin iniciar Fase 3. | U4 §§12–17 | Obligatorio usuario | 2 | tests/, docs/10 y handoff con resultados y pendientes |
| REQ-054 | entrega | ZIP Fase 2 conserva manuales, infraestructura, código/configuración/documentación/pruebas; excluye secretos/datasets/cachés/temporales y verifica permisos. | U4 §18 | Obligatorio usuario | 2 | CRC, bytes, rutas, exclusiones y permisos ejecutables |

## Adiciones de consultas y corrección (U5)

REQ-006/029/030 implementados como consultas originales; validación PG disponible, equivalencia real ambos pendiente. REQ-028 no se declara completamente satisfecho: preparación Mongo pendiente de motor real y decisión temporal PG sigue OPEN. REQ-031 variantes explícitas implementadas, solo PG real verificado. REQ-036 planes PG reales pequeños; no equivalen al reporte final ni a mediciones de latencia.

| ID | Categoría | Descripción | Fuente/sección | Carácter | Fase | Verificación |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-055 | técnico | Organizar consultas originales, variantes, API Python reutilizable, conexiones/timeouts/errores y liberación de recursos. | U5 §§3–4,14; P pp.2–3 §5 | Obligatorio fuente indicada | 3 | Archivos, QuerySpec/QueryExecutor y pruebas de sesiones |
| REQ-056 | funcional | Q1 con normalización independiente de orden/grupos, count/suma/promedio y precisión numérica justificada. | U5 §§5,9,16; P p.2 §5.1 | Obligatorio fuente indicada | 3 | Oráculo racional, unitarias e integración ambos cuando disponible |
| REQ-057 | datos | Verificar tipos almacenados, alias totals/final_total y fechas UTC con frontera inclusiva; bloquear incompatibles sin cambiar consulta. | U5 §§7–9 | Obligatorio usuario | 3 | Preflight real/archivo, totales-only y calendario inválido |
| REQ-058 | funcional | Q2 con opciones allowDiskUse del comando y SET LOCAL work_mem por sesión; validar Top-1000 con empates sin sort secundario silencioso. | U5 §§6,10; P pp.2–3 §5.2 | Obligatorio fuente indicada | 3 | Variantes, ajustes efectivos, oráculo de cutoff/UUID |
| REQ-059 | técnico | Inspeccionar/preparar índices de forma segura, sin total ni inmutabilidad falsa; separar alternativas PG del SQL original. | U5 §11; P p.1 §2 | Obligatorio fuente indicada | 3 | Inventarios, creación explícita, catálogo y planes |
| REQ-060 | entrega | Guardar explain executionStats y EXPLAIN ANALYZE BUFFERS estructurados; ausentes no son cero ni tiempo de benchmark. | U5 §12; P p.4 §8.3; S p.11 | Obligatorio fuente indicada | 3 | Plan crudo/resumen/fecha/variante y evidencias |
| REQ-061 | experimental | Analizar Top-K/memoria/spill/concurrencia futura sin provocar eventos artificialmente ni sustituir cargas originales. | U5 §13 | Obligatorio usuario | 3 | docs/11; límites/consulta/dataset sin modificar |
| REQ-062 | entrega | Unitarias e integración disponible con tamaños pequeños/controlados, PASS/FAIL/BLOCKED y evidencia Cloud/local honesta; no Fase 4. | U5 §§15–20 | Obligatorio usuario | 3 | tests/ y handoff; Mongo no se simula como integración |
| REQ-063 | entrega | ZIP Fase 3 conserva proyecto, manuales, consultas, validadores, pruebas y evidencia; sin secretos/volúmenes/datasets masivos/cachés/temporales. | U5 §21 | Obligatorio usuario | 3 | CRC, bytes, permisos y recuperación fuera de sesión |


## Adición normativa U6 — Fase 4

| ID | Categoría | Descripción | Fuente/sección | Carácter | Fase | Verificación |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-064 | experimental | Admitir base 36/108 con Q2 explícita, extendida 54/162 sin aprobarla, filtros, escenario individual y piloto. | U6 §§4,16; P p.3 §6 y p.2 §5.2; S pp.7–8 | Obligatorio usuario; ambigüedad académica P-02 intacta | 4 | Tests de conteos/variantes y plan visible sin ejecución por omisión |
| REQ-065 | técnico | Clientes 1/10/50 independientes, sincronizados, con timeout/cancelación/cierre y consumo completo de respuestas; reutilizar Q1/Q2. | U6 §§6–7,14 | Obligatorio usuario | 4 | Unitarias de concurrencia y sesiones; integración nativa diferenciada |
| REQ-066 | experimental | 60/300/60 definitivo con reloj monotónico; definir bordes y separar warmup/cooldown. Caché privilegiada nunca automática y skip solo piloto explícito. | U6 §§5,16,21; P p.3 §6 | Obligatorio usuario y manual | 4 | Protocol/config, trazas, tests de bordes y bloqueo estricto |
| REQ-067 | métricas | QPS de éxitos y percentiles verificables, muestra contada, errores aparte, memoria controlada sin guardar respuestas indefinidamente. | U6 §8; P p.3 §7 | Obligatorio usuario y manual | 4 | R7/QPS contra valores conocidos, registros en disco y muestras auditables |
| REQ-068 | métricas | Telemetría modular; delta temporal de throttling, RSS exacto, spill/OOM con evidencia. Ausente no es cero ni fila definitiva válida. | U6 §§9,11; P p.3 §7; S p.8 | Obligatorio usuario y manual | 4–5 | Tests de null/deltas y bloqueo sin proveedor completo |
| REQ-069 | entrega | CSV exacto de 14 columnas y una fila por repetición; variante identificable externamente aun al consolidar. | U6 §10; P p.4 §8.2; S pp.8–9 | Obligatorio usuario y manual | 4 | Cabecera/tipos, sidecar de fila/variante y consolidación sin ambigüedad |
| REQ-070 | reproducibilidad | Reanudación sin sobrescritura/duplicados, rechazar CSV corrupto/cambios de dataset/versiones/perfiles, preservar intentos incompletos. | U6 §14 | Obligatorio usuario | 4 | Locks, hashes/commit y pruebas de recuperación |
| REQ-071 | reproducibilidad | Manifiesto separado con ejecución/fechas, dataset, versiones/imágenes, configuración solicitada/observada, protocolo/caché, errores/evidencia y host; sin credenciales. | U6 §15 | Obligatorio usuario | 4 | Inspección de experiment/preflight/result JSON y hashes |
| REQ-072 | técnico | Preflight definitivo exige 500000 equivalentes, consultas/variantes/índices reales conformes, perfil/salud/cgroups2/clientes, telemetría y espacio. Mantener Mongo pendiente visible. | U6 §§12–13 | Obligatorio usuario | 4–7 | Sin preflight completo no arranca; piloto reducido identificado |
| REQ-073 | entrega | Pruebas unitarias de orquestación y fallos con ejecutores simulados etiquetados, integración real disponible separada, documentación/handoff honestos. | U6 §§17–20,23 | Obligatorio usuario | 4 | Suite de runner/regresión y evidencia real PG, Mongo/Kubuntu pendientes |
| REQ-074 | entrega | Conservar fases anteriores, ZIP íntegro sin secretos/.env/datasets masivos/cachés/resultados ficticios, detenerse antes de Fase 5 y no ejecutar matriz definitiva. | U6 §§21–24,26 | Obligatorio usuario | 4 | Comparación con ZIP previo, inventario/CRC/bytes/permisos y alcance |


## Adición normativa U7 — Fase 5

| ID | Categoría | Descripción | Fuente/sección | Carácter | Fase | Verificación |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-075 | técnico | Prometheus, cAdvisor y Node Exporter en Compose complementario, imágenes/versiones verificadas, permisos explícitos, red privada/local y TSDB persistente. | U7 §§4–6,9; P p.3 §7 | Obligatorio usuario y manual | 5 | Compose/promtool, versiones/digests, montajes y evidencia real diferenciada |
| REQ-076 | experimental | Scrape 1s, timeout compatible, retención suficiente, estimación de espacio/CPU y control de carga del monitoreo fuera de límites del motor. | U7 §§5,17; P p.3 §7 | Obligatorio usuario y manual | 5 | Configuración/flags/targets observados, cardinalidad/capacidad y pendientes físicos |
| REQ-077 | reproducibilidad | Identificar series por contenedor real, proyecto/servicio/perfil/imagen/límites y detectar recreación/reinicio, ambigüedad y datos viejos. | U7 §§6,14,17 | Obligatorio usuario | 5 | ID completo, labels, snapshots y pruebas de frescura/duplicidad |
| REQ-078 | métricas | Throttling temporal en segundos, deltas con muestras/reset/gaps; contrastar cpu.stat sin igualar metodologías distintas. | U7 §7; P p.3 §7 | Obligatorio usuario y manual | 5 | Raw series, intervalo realmente cubierto, delta/zero observado y resets rechazados |
| REQ-079 | métricas | Máximo RSS observado de ventana, conversión explícita y ausencias; no working set/uso total ni garantía de pico absoluto. | U7 §8; P p.3 §7 | Obligatorio usuario y manual | 5 | container_memory_rss real, max/1000000 documentado y tests |
| REQ-080 | métricas | Host CPU/memoria/IO/swap e identidad separadas de métricas del motor/contenedor; Cloud anidado explícito. | U7 §9 | Obligatorio usuario | 5 | node_uname_info/boot/catálogo; sin sustitución de KPIs |
| REQ-081 | métricas | Detectar OOM por fuentes suficientes, conservar evento/contenedor/repetición y no inferirlo por exit137/error/asignación. | U7 §10 | Obligatorio usuario | 5 | Evento Docker/cgroup/estado con scope y fixtures claramente simulados |
| REQ-082 | métricas | Spill específico del motor y de consultas reales; estados confirmado/no detectado válido/insuficiente; EXPLAIN posterior no prueba el pasado. | U7 §11 | Obligatorio usuario | 5 | Sesiones/logs/tags/profile y evidencia de cobertura; null si insuficiente |
| REQ-083 | técnico | Integrar proveedor en runner existente y relojes monotónico/epoch con ventanas, desfases, gaps y evidencia; conservar CSV y bloqueo definitivo incompleto. | U7 §§12–14 | Obligatorio usuario | 5 | Hooks, clock bridge, preflight, 14 columnas y sidecars con hashes |
| REQ-084 | entrega | Scripts de monitoreo/diagnóstico/exportación sin detener motores ni eliminar series/volúmenes, pruebas unitarias/integración/regresión y guía técnica. | U7 §§15–18,20 | Obligatorio usuario | 5 | monitoring.sh, suites/logs/guía y limitaciones efectivamente observadas |
| REQ-085 | entrega | Conservar fases previas, ZIP completo sin secretos/datasets masivos/cachés/resultados simulados; detenerse antes de Fase 6 y matriz definitiva. | U7 §§19,21,23 | Obligatorio usuario | 5 | Comparación con ZIP Fase 4, CRC/bytes/permisos/exclusiones y handoff |


## Adición normativa U8 — Fase 6

Estos requisitos adicionales proceden del usuario. Las propuestas de agregación/aceptación implementadas no se atribuyen al profesor ni aprueban las decisiones académicas abiertas.

| ID | Categoría | Descripción | Fuente/sección | Carácter | Fase | Verificación |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-086 | funcional | Reporte parcial progresivo y final consolidado, sin etiquetar completa una matriz incompleta ni usar pilotos como evidencia académica. | U8 §§3,5,7; P p.4 §8.3 | Obligatorio usuario/manual para estructura | 6 | Gates de cobertura, modo, procedencia y repeticiones; pruebas de final/partial |
| REQ-087 | entrega | Siete secciones: host, método/baseline, resultados, gráficas, planes, interpretación y recomendaciones; datos declarados/verificados separados. | U8 §4; P p.4 §8.3 | Obligatorio usuario y manual | 6 | Siete títulos HTML/Markdown/PDF y ausencia explícita de datos |
| REQ-088 | métricas | Estadística descriptiva por repeticiones válidas; diferencias absolutas/porcentuales solo comparables; no confundir P99 combinado/media de P99; M3 no calculable sin insumos. | U8 §§4,8 | Obligatorio usuario | 6 | Decimal, media/mediana/min/max y contrastes/cohortes/variantes probados |
| REQ-089 | métricas | Gráficas P99/concurrencia, throttling/QPS y curva RSS de muestras temporales reales con unidades/identidad y huecos explícitos. | U8 §4 sección 4; P p.4 §8.3 | Obligatorio usuario y manual | 6 | PNG generados, series reales/rangos y ausencia de curva si solo hay máximo |
| REQ-090 | reproducibilidad | Análisis incremental offline de archivos completos/consistentes, snapshots, fuentes sin cambios, sin detener runner ni consultas adicionales en medición. | U8 §5 | Obligatorio usuario | 6 | Commits/hashes/lecturas estables, watcher y hashes de originales antes/después |
| REQ-091 | funcional | Progreso terminal: esperadas/completadas/válidas/fallidas/pendientes, avance, actual si disponible, últimas filas y tiempo/ETA aproximada. | U8 §6 | Obligatorio usuario | 6 | Comandos progress/watch, detección de intentos incompletos y ETA con protocolo |
| REQ-092 | reproducibilidad | Reconocer 108 base/162 extendida sin mezclas ambiguas, variante por manifiesto y CSV oficial intacto; extendida no aprobada. | U8 §7; P p.3 §6 | Obligatorio usuario y manual | 6 | Reconstrucción de matriz completa, selección Q2 explícita y cohortes separadas |
| REQ-093 | entrega | HTML imprimible y Markdown con portada editable, índice, figuras/anexos; PDF cuando viable sin depender de servicios externos. | U8 §§9–11 | Obligatorio usuario; PDF condicionado | 6 | Render, escape de texto, exportaciones reales y versiones de dependencias |
| REQ-094 | entrega | Pruebas de carga/estadísticas/corrupción/incrementos/reportes/regresión, fixtures etiquetados fuera de informes reales, documentación y guía breve Kubuntu. | U8 §§12–14 | Obligatorio usuario | 6 | Suites/logs, CLI rechaza procedencia simulada y docs/14 |
| REQ-095 | entrega | Preservar fases previas y ZIP íntegro/permisos sin secretos/datasets masivos/cachés/resultados simulados; no iniciar Fase 7, matriz completa ni cambiar protocolo. | U8 §§1,13,15–16 | Obligatorio usuario | 6 | Archivo auditado, comparación con respaldo previo y revisión de alcance |
