# Validación y aceptación

Plan original de Fase 0; las pruebas técnicas ejecutadas durante Fase 1 se registran en la sección final, sin dar por probadas las demás fases. Fuentes: U §4.9 y §7; P pp.1–4 §§2–8; S pp.8,10–13; requisitos de aceptación en [trazabilidad](01-requisitos-y-trazabilidad.md). Toda ejecución debe registrar entorno, versión, configuración, resultado y evidencia.

| Nivel | Criterio | Requisitos | Evidencia y condición de aceptación |
| --- | --- | --- | --- |
| Unitaria | Generación determinista y estructura | 003–005, 019 | Misma semilla produce mismo contenido canónico; tipos/anidamiento y distribución cumplen contrato aprobado |
| Unitaria | Cálculo de métricas | 012, 014 | Casos conocidos para QPS y cuantiles; manejo explícito de errores y ventanas |
| Unitaria | CSV | 014 | 14 nombres/orden exactos, tipos y nulos aprobados; rechazar duplicados |
| Integración | MongoDB y PostgreSQL | 001–002 | Salud, conexión, escritura/lectura de prueba aislada en ambos; sin datos del usuario |
| Integración | Límites CPU/memoria | 007, 017 | Inspección Docker y cgroup efectivo por perfil, incluyendo soporte swappiness; YAML solo no basta |
| Integración | Dataset completo equivalente | 003–005 | 500,000 en ambos, identidad y contenido canónico coincidentes; promedio/tolerancia aprobados |
| Integración | Q1 equivalente | 006, 023 | Resultados completos coinciden con parámetros y tipos controlados |
| Integración | Q2 equivalente | 006, 023 | Igual comparación, arrays, cálculos y orden normalizados bajo contrato aprobado |
| Integración | Variantes de memoria | 011 | Configuración efectiva y resultado equivalente por variante; evidencia de comportamiento esperado según manual |
| Integración | Concurrencia/repeticiones | 008–009 | 1/10/50 clientes y exactamente tres intentos identificados por celda; política de fallos aprobada |
| Integración | Percentiles y QPS | 012 | Recalcular desde observaciones originales y tiempos efectivos |
| Integración | Throttling y memoria | 012 | Correlación de ventana/contadores y fuente RSS verificada; documentar si no se induce throttling |
| Integración | Spill/OOM | 013 | Casos controlados aislados tras autorización de fase; detector respaldado por logs/contadores, no solo salida 137 |
| Piloto | Ciclo experimental | 010, 017 | Caché aprobada, etapas 60/300/60 verificadas y recursos locales observables; piloto reducido etiquetado no definitivo |
| Piloto | Cadena de evidencia | 012–016 | Una ejecución trazable desde solicitudes/telemetría hasta CSV y gráfico, incluso en error |
| Definitivo | Matriz local aprobada | 009–011, 017–018 | Cobertura de todas las celdas/variantes/repeticiones en equipo local con versiones y condiciones registradas |
| Definitivo | Reporte y reproducibilidad | 016, 019 | Gráficas recalculables desde originales, limitaciones y fallos incluidos; repetición documentada de una selección aprobada |

Los números de requisitos de la tabla llevan prefijo REQ-. No usar fixtures, datos sintéticos de pruebas de software o benchmarks simulados como evidencia definitiva. El dataset del experimento sí es sintético por requisito; las mediciones deben ser reales. No ejecutar benchmarks completos en Cloud. Los criterios de tolerancia numérica, estabilidad y umbrales de rendimiento no están definidos: no inventar ganadores ni mínimos de QPS.

## Puertas de avance

Fase 0: inventario, enlaces, coherencia, fuentes, pendientes, fases, handoff y alcance. Ambos PDF están disponibles y revisados; extracción y reconciliación completadas. Los asuntos técnicos abiertos son puertas para sus fases responsables, no ausencia de documentación. Fases técnicas: satisfacer criterios asociados y conservar evidencia antes de declarar COMPLETED. Pilotos no sustituyen pruebas definitivas. Criterios académicos incorporados desde S pp.10–13; su cumplimiento experimental se verificará en Fases 6–7.

## Criterios añadidos tras revisar manuales

- REQ-025–028 (integración, Fases 1–3): verificar WiredTiger/sin sharding, tabla orders con UUID/JSONB, versiones efectivas, todos los campos e inventario de índices, sin índice del total. Revisar compatibilidad del B-Tree temporal (P-06).
- REQ-029–031 (integración, Fase 3): Q1 incluye conteo de ítems, filtro estricto y cálculos sin impuestos/descuentos; Q2 incluye límite inferior exacto y 1000 resultados como máximo. Probar empates en frontera, tipos temporales, precisión, proyección y ambas configuraciones por motor tras resolver P-03–06 y P-15.
- REQ-032–034 (integración, Fases 4–5): verificar scrape a 1 s, nombres de KPIs, RSS real, continuidad y estados ok/spill/oom/error; archivos laterales preservan OOM y variantes. Si no se observa spill/OOM, no inventar el evento. Un fallo debe producir fila y evidencia, no desaparecer.
- REQ-035 (entrega, Fases 1–4): comprobar nombres y rutas públicas de los cinco entregables exactos de P §8.1, aunque deleguen a módulos internos.
- REQ-037–038 (piloto y definitivo): validar una celda y CSV antes de matriz completa; declarar estadístico entre repeticiones y verificar comparabilidad del baseline con datos, consultas, índices y límites efectivos. Piloto reducido requiere autorización/etiquetado y no satisface por sí mismo el protocolo definitivo de 300 s.
- REQ-039 (integración/análisis): aprobar denominador de documentos procesados y fórmula de huella CPU/memoria por 1,000; verificar con conteos independientes, conservar metadatos sin añadir columnas.
- REQ-040 (documental): ZIP con 11 Markdown y ambos PDF; rutas relativas seguras, prueba CRC, lectura completa y comparación byte a byte con archivos finales.

## Checklist del reporte (REQ-036)

P p.4 §8.3 exige estas siete secciones:

1. Especificaciones del host y del entorno Docker.
2. Método de medición y verificación del baseline.
3. Resultados consolidados: throughput, P95/P99 y tiempo de throttling.
4. Análisis gráfico: P99 vs concurrencia, throttling vs QPS y curva RSS.
5. Planes de ejecución: explain executionStats frente a EXPLAIN ANALYZE BUFFERS.
6. Interpretación de límites de memoria, volcado a disco y throttling de cgroups.
7. Recomendaciones técnicas para despliegues documentales en la nube.

S p.11 requiere responder con tablas/figuras a comparabilidad del baseline, percentiles, segundos de CFS throttling, spill/OOM por perfil/concurrencia, repeticiones/resumen y planes que respalden el cuello de botella. Los planes deben conservar versión, configuración y parámetros del escenario. Su captura puede tener sobrecarga: se propone realizarla fuera de la ventana medida y enlazarla con el escenario, pendiente de aprobación. La validación documental no afirma que estas evidencias experimentales ya existan.

## Ejecución de validación de Fase 1

Plataforma definitiva actualizada por U3: Kubuntu nativo; REQ-017/041 reemplazan Windows/WSL2. Bash y Compose config se validan mediante tests/test_infrastructure.sh: tres perfiles exactos, variables requeridas, argumentos inválidos, configuración de recursos incompatible, rechazo de etiquetas flotantes y expansión shell, publicación loopback. Suite ejecutada con Engine 28.4.0/Compose 2.40.3 en Cloud; no equivale a instalar en Kubuntu.

La suite tests/test_containers.sh --run inicia un proyecto aislado severe, intenta salud autenticada, una tabla auxiliar JSONB y un marcador MongoDB (sin dataset/queries experimentales), recreación y persistencia, y verificación de recursos. El intento conjunto en Cloud falló al crear contenedores con disco lleno, antes de realizar esas aserciones. Los marcadores no son resultados experimentales. El informe vigente y cualquier prueba aislada adicional están en docs/08-handoff.md.

Pendiente para cierre: ambos motores saludables, conectividad y persistencia verificadas; inspect y cpu.max/memory.max/memory.swap.max/ancestros concordantes en baseline/medium/severe en Kubuntu físico; versión de sistema identificada y aceptación registrada de adaptación sin swap. No ejecutar pruebas de presión, OOM ni benchmark durante Fase 1. No marcar REQ-025 (esquema orders)/028 (índices) satisfechos por existir contenedores: se completan más adelante. El ZIP de Fase 1 se valida por CRC y bytes finales, excluyendo secretos/datos. Estado de Fase 1 BLOCKED, con validación estática/configuración aprobada.

## Validación de Fase 2 (U4)

Pruebas unitarias reales de software en tests/test_dataset.py: 19 aprobadas con 10/1000 registros; determinismo de bytes/hashes, UUID, fechas, tipos, anidamiento, media de items, estados, cálculos exactos/redondeo, duplicate UUID/JSON fields, layouts reversibles, rechazo de destino ocupado/divergente, resume y muestras reproducibles. La simulación en memoria prueba flujo/error del software, no constituye integración de motores. Ensayo acotado de streaming con 1000 y heap Python <8 MiB: no prueba empíricamente el tamaño final 500,000.

Generación CLI realmente ejecutada dos veces con 100/seed42 y mismo archivo byte a byte (cmp y SHA256); validate_data.sh comprobó manifiesto/esquema/fechas/cálculos. compileall y sintaxis Bash aprobados. tests/test_infrastructure.sh sigue pasando sin cambios de configuración de Fase 1.

Integración real disponible, tests/test_dataset_integration.py (opt-in mediante tests/test_data_integration.sh): PostgreSQL 18.6 con base nueva y 100 órdenes, COPY por lotes 17, lectura posterior exacta, rechazo de destino no vacío, resume por lotes 29, comparación completa por lotes 19 y muestra de 10 aprobados. Se verificó rollback de lote con fila nueva seguida de UUID duplicado; no quedaron inserciones de ese lote. Bases de prueba conservadas, sin DELETE/DROP/TRUNCATE. No es una prueba de consultas ni rendimiento.

MongoDB real no disponible por limitación de espacio registrada; solo interfaces/EJSON verificadas unitariamente. Integración both y carga real 500,000 con verificación completa, distribución y recursos en Kubuntu siguen pendientes; Fase 1 permanece BLOCKED sin impedir trabajo de Fase 2. Fase 2 IN_PROGRESS (implementación terminada, validación parcial), no COMPLETED sin esa evidencia. Para Fase 3: nueva instrucción, aceptación/revisión del contrato provisional e índices/semántica de consultas pendientes. No interpretar hashes de datasets sintéticos como mediciones de motores.

## Validación de Fase 3 (U5)

17 unitarias prueban fidelidad de archivos Mongo/SQL, precios <50/=50/>50, grupos/cantidades/país/categoría, exactitud de suma y promedio racional cuantizado, vacío, fechas antes/igual/después, estados, alias ausente/divergente, Top-1000/empates legítimos/frontera, errores de variantes, sesión SET LOCAL, índices Mongo y métricas ausentes. Inputs de motor construidos en unitarias son datos del validador, nunca evidencia real de Mongo.

Nueve casos reales PostgreSQL aprobados: controlado con resultados esperados y planes; 10/100/1000 generados; resultado vacío; 1005 para Top-1000 empatado; totals-only bloqueado; calendario inválido bloqueado; índice temporal y preparación segura. Sesiones 4MB/64MB confirmadas y valor de conexión independiente intacto. Tras incorporar timeout a DDL se repitió específicamente ese caso. La comparación contra oráculo PG PASS no implica equivalencia real cruzada: esa permanece BLOCKED.

La referencia exige suma/count exactos y avg redondeado desde fracción al quantum devuelto, con precisión mínima justificada de 16 cifras PG/34 Decimal128 (P-24 PROPOSED). No se aprueba automáticamente para resultados definitivos. Índice original timestamptz rechazado, catálogo STABLE observado; B-Tree textual verificado solo en base aislada y con aceptación de propuesta. Auditoría conserva BLOCKED académico aunque índice físico PASS. Planes originales PG conservados; no extrapolar tiempos/memoria/ausencia de spill a datos masivos.

Pruebas de Python/Bash/JSON y construcción de pipeline ejecutadas; sintaxis SQL además comprobada por PG real. Las integraciones se omiten sin opt-in; no contarlas como aprobadas. Pendientes: Mongo real, tipos Decimal128 reales, uso/índices/explain de Mongo, equivalencia entre ambos y validación en Kubuntu. Fase 3 IN_PROGRESS, implementación preparada con evidencia parcial. No hay runner/percentiles/telemetría ni autorización de Fase 4.

## Validación vigente de Fase 4 (U6)

U6 supera la prohibición histórica de Fase 4 al final del apartado anterior. No autoriza Fase 5 ni matriz definitiva. 20 unitarias de runner: 36/108 y 54/162, selección explícita/filtros/IDs/variantes, duraciones/bordes, R7/QPS, clientes simulados independientes 1/10/50 y cierre, errores sin retry, cancelación previa/en ventana, telemetría ausente y contadores, cabecera/tipos/locks, corrupción/reanudación/cambios de configuración, recuperación de intento parcial y consolidación sin mezclar modos. Mongo mock verifica opciones aggregate y consumo completo; no es integración Mongo. Los fixtures/telemetría simulados están prohibidos fuera del modo test interno, sin CSV ficticios entregables.

Integración PG real de tests/test_benchmark_integration.py: base/rol nuevos, 100 documentos importados con código Fase 2, sesiones nativas Q1 y Q2 4MB/64MB contra oráculo, configuración efectiva, conexión rechazada, consulta inválida y timeout SQLSTATE 57014. Un piloto Q1 de 0.05/0.25/0.05 s y un cliente verificó ventana, muestras, CSV de error por recursos ausentes y reanudación sin otra fila/commit. Solicitud definitiva bloqueada antes de empezar y sin CSV definitivo. Es prueba funcional reducida, no validación de rendimiento. Evidencias reales y limitaciones en [phase4](evidence/phase4/README.md).

Suite general del proyecto con drivers instalados: 67 casos descubiertos, 56 aprobados y 11 integraciones omitidas sin opt-in; el caso nativo real se ejecutó aparte y pasó. Las cifras de integración históricas no se suman como pruebas repetidas en este comando. Sintaxis Python/Bash, Compose para A/B/C y regresión estática se registran al cierre en handoff. Pendiente: Mongo real/corrección cruzada, 1/10/50 conexiones reales, Kubuntu, 500000 y telemetría obligatoria/caché autorizada. Estado Fase 4 IN_PROGRESS, implementada y parcialmente validada; no COMPLETED experimental.

## Validación de Fase 5 (U7)

Unitarias nuevas en tests/test_observability.py: 25 casos de lógica simulada, no mediciones: PromQL/ID/labels/frescura, rangos ms, unidades/deltas/zero observado/reset/gaps, HTTP/200 vacío/NaN, targets DOWN/stale/intervalo, timestamps/offset, OOM, spill PG/Mongo, filtro/restauración/CAS de profiler, hooks/cancelación, CSV/evidencia/manifiesto y resume con configuración de monitoreo cambiada. Regresión previa incluida en discovery. Conteos finales y comandos efectivamente ejecutados se registran en handoff.

Integración real disponible y ejecutada: cAdvisor 0.60.6 y Node Exporter 1.12.1 en Docker sin privileged/caps extra; Prometheus 3.15.1 como binario oficial verificado por checksum porque su imagen agotó VFS Cloud. promtool real aprobó configuración 1s/800ms, Compose complementario validó estáticamente. Targets UP, versiones, host/boot y siete métricas de cAdvisor del motor real comprobados. Se corrigió healthcheck inválido basado en wget inexistente en cAdvisor distroless, sustituyéndolo por verificación HTTP/scraping externa; no se simula salud con --version.

Piloto real PG/Q2 4MB: 100 órdenes en base/rol nuevos, sesión con permiso SET log_temp_files solo para ese rol de prueba, 1 cliente y 1/4/1s. Muestras de throttling/RSS reales, negativos OOM/spill con mecanismos válidos, CSV intacto y resume sin duplicado aprobados. Una falla inicial de sintaxis de rango PromQL quedó registrada como error/nulos; se corrigió a rangos enteros ms y se repitió en otra base/experimento conservando ambos. Tras restringir etiquetas y añadir metadatos de seguridad/versiones se repitió integración. No son repeticiones oficiales del estudio ni prueba de rendimiento. Evidencia en [phase5](evidence/phase5/README.md).

Positivos de OOM/spill solo unitarios simulados; no se provocó OOM del host ni se alteraron consultas/datos para forzar temporales. Mongo profiler/usedDisk solo unidad; Mongo real/equivalencia siguen pendientes. No se validaron pila Prometheus Docker/healthcheck/TSDB persistente completa ni retención de días ni sobrecarga/1–10–50 físicos. Fase 5 IN_PROGRESS implementada/parcialmente validada, no COMPLETED. Definitivo conserva gates de datos/índices/recursos/caché y nuevas condiciones de fuentes/identidad/ventana/capacidad; no hay bypass.


## Validación de Fase 6 — U8

33 pruebas nuevas de tests/test_reporting.py y tests/test_reporting_plan_binding.py aprobadas. Cubren CSV oficial/columnas/tipos, manifiestos/variantes, conteos 108/162, matriz completa y seleccionada, estadística Decimal y comparaciones, datos ausentes/fallidos, duplicados, corrupción y commits incompletos, reanudación incremental, cohortes incompatibles, separación piloto/definitivo, gates FINAL, tablas/HTML/escape, gráficos y gaps, rutas desde otro directorio, snapshots y fuentes inmutables. Los casos controlados usan fixtures sintéticos privados en directorios temporales; la CLI pública rechaza esa procedencia. No se incorporaron sus CSV/reportes al entregable.

Regresión ejecutada: 126 casos descubiertos, 114 aprobados y 12 integraciones omitidas sin opt-in. Comando Cloud: PYTHONPATH=/tmp/phase4-venv/lib/python3.12/site-packages python3 -m unittest discover -s tests -v (drivers existentes; dependencias de reportes en Python del sistema). La guía documenta instalación normal en venv. Las pruebas omitidas no se cuentan como aprobadas. Las integraciones PostgreSQL/exportadores de Fases 3–5 son antecedentes, no ejecuciones repetidas en esta fase.

Integración offline real: lectura del piloto PG histórico de Fase 5, validación de commit/CSV/telemetría, RSS temporal, tablas/HTML/Markdown/PDF y watcher; fuente verificada sin cambios. Reporte académico vacío 0/108, sin métricas/curvas inventadas. FINAL sin evidencia es rechazado; --allow-partial conserva etiqueta parcial. PDF revisado mediante extracción de texto y previsualización; portada y figura legibles. Detalles de sintaxis/Compose, hashes y archivo final en evidence/phase6/ y handoff.

Cambio anterior mínimo: query_tool.py añade --file opcional a explain, reutiliza validate_file/compare_dataset completos antes del diagnóstico y registra dataset_sha256/dataset_binding. Dos pruebas unitarias verifican vínculo y bloqueo ante mismatch. Esta nueva rama NO se probó con una conexión real; requiere Kubuntu. Sin --file comportamiento anterior intacto; sin cambios de SQL, pipeline, runner, CSV, infraestructura, generador/importadores ni límites.

No se iniciaron servicios, no se hicieron consultas nuevas a motores y no se ejecutaron benchmarks definitivos. Pendientes: validación física, equivalencia real Mongo/PG, generación/carga objetivo, instrumentación completa y reporte FINAL con mediciones auténticas. Fase 6 IN_PROGRESS expresa implementación terminada y validación disponible realizada, con validación definitiva pendiente de Fase 7.
