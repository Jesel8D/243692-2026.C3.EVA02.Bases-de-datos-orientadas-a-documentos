# MongoDB frente a PostgreSQL JSONB bajo contención de CPU y memoria

Universidad Politécnica de Chiapas
Bases de Datos en la Nube — Ingeniería en Tecnologías de la Información e Innovación Digital

**INFORME PARCIAL — RESULTADOS PRELIMINARES**

Estudiante: [Por completar]
Grupo: [Por completar]
Docente: [Por completar]
Fecha: 2026-11-01
Estado: PARTIAL

Índice:
1. Especificaciones del host y entorno Docker
2. Método de medición y baseline
3. Resultados consolidados
4. Análisis gráfico
5. Planes de ejecución
6. Interpretación de los resultados
7. Recomendaciones técnicas

## 1 — Especificaciones del host y entorno Docker


Plataforma objetivo declarada por el usuario: Kubuntu Linux nativo x86_64, Ryzen 7 5700X, 32 GB RAM. La versión exacta de Kubuntu no se presume. Los valores observados abajo provienen de manifiestos/evidencias, no del equipo que genera el reporte.


No hay condiciones de ejecución verificadas disponibles. El hardware declarado no constituye medición.


| Perfil | CPU | Memoria configurada | Estado |
| --- | --- | --- | --- |
| PROFILE_A_BASELINE | 4 | 4096 MiB Docker | Solicitado; ver snapshots efectivos por repetición |
| PROFILE_B_MEDIUM | 2 | 2048 MiB Docker | Solicitado; ver snapshots efectivos por repetición |
| PROFILE_C_SEVERE | 1 | 1024 MiB Docker | Solicitado; ver snapshots efectivos por repetición |


## 2 — Método de medición y baseline


Objetivo: comparar agregaciones JSON equivalentes bajo contención controlada. Fuentes: playbook.pdf pp.1–4 §§1–8 y playbook_sesion.pdf pp.3–11. M1: cambios en P95/P99 al limitar CPU/memoria. M2: gestión de buffers antes de spill/OOM. M3: huella CPU/memoria por 1000 documentos; operacionalización pendiente, no se calcula con throttling como CPU consumida.


Contrato: 500000 órdenes JSON anidadas, media objetivo de tres ítems; Q1 desanida, filtra price>50 y agrupa qty×price por país/categoría; Q2 completed y timestamp>=2026-01-01 UTC, total descendente, Top-1000. Alias de pagos/tipos/índice temporal y adaptación swap siguen documentados como provisionales; no se declaran aprobados por este generador.


Protocolo original: limpieza de caché, warmup 60s, medición 300s, cooldown 60s; concurrencias 1/10/50; tres repeticiones. Se registran variantes Q2 por manifiesto, sin modificar el CSV. La constancia manual de caché es declaración del operador, no prueba automática del estado del kernel.


Runner: sesiones independientes, consumo completo de resultados y reloj monotónico. QPS=éxitos íntegramente dentro de ventana/duración fija; cruces de borde, errores, warmup/cooldown excluidos. Percentiles de cada repetición: Hyndman–Fan R7 exacto en disco. Las medias/medianas de esos P99 NO son P99 combinado de latencias individuales.


Telemetría: Prometheus/cAdvisor/Node Exporter con scrape 1s; throttling=last−first de muestras interiores (subintervalo observado, bordes omitidos), RSS máximo observado/1000000. Spill y OOM requieren evidencia específica. Los OOM de estado Docker posterior pueden acreditar solo el intento, no la ventana de 300s; los conteos agrupan repeticiones afectadas y debe revisarse su alcance en evidencia. Un máximo RSS no permite fabricar curva temporal. Instrumentación y análisis añaden carga al host: este análisis no consulta motores ni adquiere locks del runner; ejecutar fuera de ventanas sensibles/en otro equipo si se quiere evitar interferencia CPU/IO.


Tiempo disponible declarado: 13h. Base 108×420s=12h36, deja SOLO 24min para toda preparación, flush, drenaje, fallos y reporte. Extendida 162×420s=18h54, excede el presupuesto aun sin sobrecostes y continúa pendiente de aprobación. No se reduce el protocolo para ajustarlo.


## 3 — Resultados consolidados


Resúmenes descriptivos exclusivamente de repeticiones válidas dentro de cada cohorte/motor/perfil/consulta/variante/concurrencia. Media, mediana, mínimo y máximo son de KPIs por repetición; no se mezclan muestras crudas ni modalidades. En pilotos, “válida” significa solo diagnóstico técnico, nunca elegibilidad académica. Presentación con hasta siete cifras significativas; statistics.json conserva los decimales de cálculo.


| Cohorte | Esperadas | Terminadas | Válidas | Fallidas | Pendientes | Avance % | ETA aproximada s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| no-measurements | 108 | 0 | 0 | 0 | 108 | 0 | 45360 |


| Cohorte | Motor | Perfil | Q | Variante | Clientes | Válidas/3 | Spill confirmado | OOM confirmado | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no-measurements | mongo | baseline | Q1 | default | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | baseline | Q1 | default | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | baseline | Q1 | default | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | baseline | Q2 | allow_disk_false | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | baseline | Q2 | allow_disk_false | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | baseline | Q2 | allow_disk_false | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | medium | Q1 | default | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | medium | Q1 | default | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | medium | Q1 | default | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | medium | Q2 | allow_disk_false | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | medium | Q2 | allow_disk_false | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | medium | Q2 | allow_disk_false | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | severe | Q1 | default | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | severe | Q1 | default | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | severe | Q1 | default | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | severe | Q2 | allow_disk_false | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | severe | Q2 | allow_disk_false | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | mongo | severe | Q2 | allow_disk_false | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | baseline | Q1 | default | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | baseline | Q1 | default | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | baseline | Q1 | default | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | baseline | Q2 | work_mem_4mb | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | baseline | Q2 | work_mem_4mb | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | baseline | Q2 | work_mem_4mb | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | medium | Q1 | default | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | medium | Q1 | default | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | medium | Q1 | default | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | medium | Q2 | work_mem_4mb | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | medium | Q2 | work_mem_4mb | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | medium | Q2 | work_mem_4mb | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | severe | Q1 | default | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | severe | Q1 | default | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | severe | Q1 | default | 50 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | severe | Q2 | work_mem_4mb | 1 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | severe | Q2 | work_mem_4mb | 10 | 0/3 | 0 | 0 | incomplete/preliminary |
| no-measurements | postgres | severe | Q2 | work_mem_4mb | 50 | 0/3 | 0 | 0 | incomplete/preliminary |


### throughput_qps (consultas/s) — entre repeticiones


| Cohorte / motor / perfil / consulta / variante / clientes | n | Media | Mediana | Mínimo | Máximo |
| --- | --- | --- | --- | --- | --- |
| Sin observaciones | — | — | — | — | — |


### latency_p50_ms (ms) — entre repeticiones


| Cohorte / motor / perfil / consulta / variante / clientes | n | Media | Mediana | Mínimo | Máximo |
| --- | --- | --- | --- | --- | --- |
| Sin observaciones | — | — | — | — | — |


### latency_p95_ms (ms) — entre repeticiones


| Cohorte / motor / perfil / consulta / variante / clientes | n | Media | Mediana | Mínimo | Máximo |
| --- | --- | --- | --- | --- | --- |
| Sin observaciones | — | — | — | — | — |


### latency_p99_ms (ms) — entre repeticiones


| Cohorte / motor / perfil / consulta / variante / clientes | n | Media | Mediana | Mínimo | Máximo |
| --- | --- | --- | --- | --- | --- |
| Sin observaciones | — | — | — | — | — |


### cpu_throttled_seconds (s observados) — entre repeticiones


| Cohorte / motor / perfil / consulta / variante / clientes | n | Media | Mediana | Mínimo | Máximo |
| --- | --- | --- | --- | --- | --- |
| Sin observaciones | — | — | — | — | — |


### max_rss_mb (MB decimales) — entre repeticiones


| Cohorte / motor / perfil / consulta / variante / clientes | n | Media | Mediana | Mínimo | Máximo |
| --- | --- | --- | --- | --- | --- |
| Sin observaciones | — | — | — | — | — |


| Cohorte | Q/perfil/clientes | Pareja de modalidades | Comparación | Razón |
| --- | --- | --- | --- | --- |
| no-measurements | Q1/baseline/1 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q1/baseline/10 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q1/baseline/50 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q2/baseline/1 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |
| no-measurements | Q2/baseline/10 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |
| no-measurements | Q2/baseline/50 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |
| no-measurements | Q1/medium/1 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q1/medium/10 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q1/medium/50 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q2/medium/1 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |
| no-measurements | Q2/medium/10 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |
| no-measurements | Q2/medium/50 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |
| no-measurements | Q1/severe/1 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q1/severe/10 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q1/severe/50 | default : default | NOT_COMPARABLE | Both engines require three valid repetitions under the same cohort/profile/workload/concurrency |
| no-measurements | Q2/severe/1 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |
| no-measurements | Q2/severe/10 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |
| no-measurements | Q2/severe/50 | allow_disk_false : sin pareja | NOT_COMPARABLE | No explicit Q2 modality pair; buffer settings are not intrinsically equivalent |


## 4 — Análisis gráfico


P99 frente a concurrencia usa mediana del P99 de repeticiones válidas. Throttling/QPS usa puntos por repetición. RSS usa muestras temporales originales verificadas, con tiempo relativo al inicio y huecos explícitos. Cohortes/modalidades se separan; las comparaciones entre motores requieren pareja equivalente y tres repeticiones por cada motor.


No hay mediciones válidas para gráficas. No se dibujan valores cero ni curvas inventadas.


## 5 — Planes de ejecución


PENDIENTE: no se proporcionaron planes reales. No se ejecuta EXPLAIN ni se inventan operaciones/índices/tiempos.


Campos ausentes permanecen desconocidos. Actual Rows/Actual Loops se muestran separadamente, no se suman como documentos procesados M3. EXPLAIN ANALYZE y executionStats ejecutan una consulta diagnóstica; su tiempo no sustituye latencia del runner ni acredita spill de otra ejecución. Planes sin dataset/variante vinculados se presentan como auxiliares, no equivalentes al escenario medido.


## 6 — Interpretación de los resultados


### Conclusiones e interpretación


M3 NO CALCULABLE: faltan metodología aprobada para documentos procesados y consumo de CPU usado/normalización de memoria. El conteo del archivo fuente no equivale a documentos procesados por cada consulta; throttling no es CPU usada.


PENDIENTE: no hay comparaciones entre motores con tres repeticiones válidas equivalentes. Los resultados disponibles solo describen las filas observadas; no permiten declarar un motor superior ni efectos causales de recursos/concurrencia.


Limitaciones: repeticiones incompletas indicadas, muestreo 1s no captura todos los picos, bordes de throttling omitidos, cambios de host/código segregados, instrumentación/runner compiten por recursos del host y constancias de caché no prueban buffers internos. Una asociación throughput/throttling o incremento de percentiles no identifica por sí sola una causa. La extensión 162 no se aprueba por poder generar este documento.


## 7 — Recomendaciones técnicas


Recomendaciones generales (no derivadas de un ganador experimental): verificar límites reales/ancestros y salud; dimensionar memoria por operación y número de clientes; vigilar throttling, RSS, temporales y OOM; conservar datos originales/versiones; realizar piloto antes de la matriz; no asumir equivalencia de cachés/buffers internos ni de permisos de observabilidad. Son criterios operativos, no conclusiones comparativas de este estudio.


Recomendaciones específicas: PENDIENTES de comparaciones válidas. No se recomienda MongoDB o PostgreSQL JSONB como superior en rendimiento/estabilidad sin evidencia equivalente.


## Anexos


Estado solicitado/efectivo: PARTIAL. Cobertura se calcula por cohorte, no sumando datasets o versiones incompatibles.


Validación para informe final: ["Se requiere auditoría completa de hashes para informe final","no-measurements: repeticiones pendientes/fallidas/no válidas","Hay escenarios sin tres repeticiones válidas","No hay experimentos medidos"]


Integridad: selected; selected verifica hashes de JSON/CSV usados y existencia del resto; all verifica también journals binarios, sin copiarlos masivamente al reporte. Un commit nuevo posterior al corte se verá en la siguiente generación.


| Experimento | Escenario | Estado | Causa de exclusión |
| --- | --- | --- | --- |
| Sin observaciones | — | — | — |


Intentos no confirmados (pueden estar activos o interrumpidos; no se infiere actividad por existencia del lock): []


Fuentes preservadas por hash en snapshot/index.json; request.json/statistics.json/coverage.json/analysis-manifest.json permiten auditar entradas y cálculos. No contienen credenciales ni copias del dataset.

