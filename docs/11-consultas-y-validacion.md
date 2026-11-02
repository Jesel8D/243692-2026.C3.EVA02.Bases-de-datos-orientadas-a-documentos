# Consultas originales y validación de corrección — Fase 3

## Estado, fuentes y alcance

Consultas e interfaces implementadas; Fase 3 IN_PROGRESS por validación parcial. Se ejecutaron 17 unitarias y nueve casos de integración PostgreSQL, más una comprobación dirigida del índice tras incorporar timeouts. MongoDB real y equivalencia real entre ambos motores siguen BLOCKED por disponibilidad/espacio de Cloud; Kubuntu físico no está accesible. Fases 1/2 conservan sus pendientes. No se ejecutaron benchmarks, clientes concurrentes, percentiles ni Prometheus.

Fuentes: P = playbook.pdf, p.1 §2 (motores/índices), p.2 §5.1 (Q1), pp.2–3 §5.2 (Q2/variantes), p.4 §8.3 (planes); S = playbook_sesion.pdf, pp.6–7 (cargas), pp.10–11 (evidencias). U5 es la solicitud de Fase 3, §§3–21. Los originales permanecen en docs/reference/. No se modificó el generador, importadores, imágenes, límites ni configuración de infraestructura. El ajuste mínimo de AGENTS conserva la nueva autorización de Fase 3 y la prohibición de Fase 4.

## Organización e interfaz reutilizable

- queries/mongodb/q1.json y q2.json: pipelines originales, sin etapas auxiliares.
- queries/postgresql/q1.sql y q2.sql: consultas SQL explícitas del manual.
- queries/variants.json y definitions.py: combinaciones válidas y QuerySpec inmutable.
- queries/execution.py: QueryExecutor, preflight de tipos/fechas/alias, sesiones y timeouts.
- queries/validation.py: referencia independiente desde fuente y validadores de resultados.
- queries/indexes.py: inventario y adición segura explícita; sin eliminación/reemplazo.
- queries/plans.py: planes completos y resumen por nodo, sin inventar métricas ausentes.
- query_tool.py y scripts/queries.sh: interfaz operativa, informe JSON y códigos 0 PASS, 1 FAIL, 2 BLOCKED.

Se reutilizan los adaptadores stdlib de Fase 2 y el socket Docker local. Mongo utiliza la API de colección de mongosh (`aggregate(pipeline, options)`); no se añade PyMongo, framework ni servicio. PostgreSQL usa psql. Son backends de corrección: procesos de cliente, preflight y serialización no son una base válida para medir latencia de motor. Un runner futuro podrá reutilizar definiciones, variantes, oráculos y normalización, sustituyendo el transporte por sesiones persistentes si se aprueba. No hay runner implementado.

Ejemplo de API (requiere las variables DATA_* configuradas como en los scripts):

```python
from queries.definitions import QuerySpec
from queries.execution import QueryExecutor

spec = QuerySpec('postgres', 'Q2', 'work_mem_4mb', timeout_ms=120000)
answer = QueryExecutor('postgres', timeout_ms=120000).execute(spec)
rows = answer['rows']
```

preflight=True es el predeterminado. preflight=False existe solo para reutilización controlada tras una validación independiente y en unitarias; la CLI no ofrece omitirlo. El backend no mantiene sesiones compartidas entre llamadas. Cada proceso se cierra, PG termina con ROLLBACK; ante error ON_ERROR_STOP cierra conexión/revierte. Mongo materializa y consume el cursor; su proceso finaliza. maxTimeMS y statement_timeout acotan consultas, más timeout de cliente con margen de 15 s. Un timeout de cliente no garantiza cancelación instantánea de docker exec: revisar procesos/operaciones locales antes de reintentar; el timeout del motor sigue aplicándose. No se modifica configuración global.

## Q1: desanidar, filtrar y agrupar

Objetivo: carga de agregación de ítems, conforme a P p.2 §5.1/S p.6. Mongo: unwind items → match items.price > 50 → group por customer.geo.country/items.category. Calcula suma y promedio de qty × price, además de count de ítems filtrados. SQL usa jsonb_array_elements, casts numeric, WHERE estricto > 50 y GROUP BY país/categoría con SUM/AVG/COUNT.

No se añaden filtros temporales, impuestos, descuentos ni un orden final. Un price exactamente 50 se excluye; count cuenta artículos, no órdenes. Los archivos originales se leen en cada especificación; la envoltura row_to_json del transporte PG únicamente serializa resultados, sin modificar expresiones del manual. Los planes PG se obtienen sobre la consulta original sin esa envoltura.

Normalización: Mongo devuelve claves dentro de _id; PG devuelve country/category planos. Se comparan conjuntos de claves y resultados por grupo, independientemente del orden. Claves duplicadas, grupos faltantes, count incorrecto o suma diferente producen FAIL con consulta, motor, campo, esperado, obtenido y causa posible.

### Precisión de totales y promedios

Se inspeccionó código real de Fase 2: qty entero; price y payment.final_total son Decimal con centavos; alias igual a payment.totals.final_total. JSONL conserva tokens numéricos. Adaptador Mongo usa Extended JSON para Decimal128, mientras PG COPY conserva números JSONB. El generador y su contrato provisional no se cambian ni se consideran aprobados por implementar consultas.

La referencia independiente recorre la fuente y acumula centavos enteros; avg esperado es la fracción exacta suma/count. Sumas y count deben coincidir exactamente, sin epsilon. No se convierte dinero a float ni se aceptan strings numéricos. El preflight de Mongo exige price decimal y qty int/long; el PG verifica jsonb_typeof=number y qty entero del contrato. Un tipo incompatible bloquea antes de ejecutar la carga original.

Una fracción periódica no tiene representación decimal finita: numeric y Decimal128 pueden devolver distintas longitudes. Política técnica propuesta P-24: si avg coincide racionalmente, aceptar exactitud; si no, exigir redondeo de la fracción al quantum realmente devuelto, con al menos 16 cifras significativas PG y 34 Mongo. Se usa ROUND_HALF_UP para numeric positivo y ROUND_HALF_EVEN para Decimal128. No es una tolerancia libre: el redondeo debe coincidir exactamente y cada diferencia se informa como average_precision_notes. Esta política permanece PROPOSED y debe revisarse al validar Mongo real.

Se observó realmente en PG el promedio del grupo controlado MX/electronics, suma 200.06 y count 3: 66.6866666666666667. Es redondeo de 10003/150; no se declara que Mongo haya producido una cifra concreta. Los casos de Decimal128 del test unitario son entradas de prueba del validador, no resultados del motor.

Soporte técnico consultado el 2026-11-01: [BSON decimal128 (34 cifras)](https://www.mongodb.com/docs/manual/reference/bson-types/#decimal128), [numeric.c, select_div_scale](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/utils/adt/numeric.c), [numeric.h, NUMERIC_MIN_SIG_DIGITS=16](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/include/utils/numeric.h). La política concreta del comparador no está definida por el profesor ni sustituye pruebas de las versiones fijadas.

## Q2: completadas, fecha, sort descendente y Top-1000

P pp.2–3 §5.2/S p.7: payment.status=completed, timestamp >= 2026-01-01T00:00:00Z, ordenar únicamente payment.final_total descendente, límite 1000 y proyección order_id/customer.id/final_total. No se añade un límite superior de fecha ni un segundo orden. Mongo conserva incluso la inclusión implícita de _id del pipeline original; el comparador separa solo ese metadato técnico y los alias de presentación de PG.

Variantes explícitas:

| Motor | QuerySpec.variant | Aplicación |
| --- | --- | --- |
| Mongo Q1 | default | Opciones originales; no imponer variante Q2 |
| Mongo Q2 | allow_disk_false | aggregate(pipeline, {allowDiskUse:false, maxTimeMS:...}) |
| Mongo Q2 | allow_disk_true | aggregate(pipeline, {allowDiskUse:true, maxTimeMS:...}) |
| PG Q1 | default | work_mem heredado, registrado |
| PG Q2 | work_mem_4mb | SET LOCAL work_mem='4MB' |
| PG Q2 | work_mem_64mb | SET LOCAL work_mem='64MB' |

allowDiskUse es opción de comando, nunca una etapa. PG ejecuta BEGIN READ ONLY, SET LOCAL, lectura current_setting y consulta en una misma sesión; ROLLBACK/cierre evita contaminación posterior. Se comprobó realmente work_mem 4MB/64MB y que una conexión independiente conserva el valor previo. El PG backend_pid/effective y versión quedan en evidencias; Mongo real aún no se comprobó.

### Alias y timestamps

Un dataset totals-only se bloquea explícitamente para Q2, tanto por manifiesto en validate como por tipos efectivos del motor en run/explain. Alias ausente, string en vez de número o importe distinto de totals bloquea. No se utiliza COALESCE ni se cambia el pipeline para ocultar incompatibilidad. totals siempre se conserva.

UTC canónico de Fase 2: YYYY-MM-DDTHH:MM:SSZ, homogéneo en longitud/precisión y zona. Solo bajo esa precondición su comparación lexicográfica coincide con la temporal. Mongo preflight comprueba formato y fecha calendario mediante recorrido; PG comprueba formato y roundtrip temporal en UTC (un calendario inválido puede hacer fallar el cast y bloquear). Se inspeccionan tipos reales, no solo el manifiesto. Fechas antes, iguales y posteriores a la frontera se probaron; igualdad se incluye. No se convierte a BSON Date ni se aceptan offsets/formatos mezclados por conveniencia.

### Empates: validez sin modificar el sort

La referencia filtra la fuente por status y fecha con datetime UTC, cuenta elegibles y determina K=min(1000,N), cutoff, UUID estrictamente superiores y conjunto empatado en la frontera. Cada resultado debe tener K UUID únicos, estar ordenado por importe descendente, ser elegible y conservar customer_id/importe de la fuente. Todos los superiores al cutoff son obligatorios; los lugares restantes pueden ser cualquier subconjunto de los empatados. También se detectan importes repetidos fuera de la frontera.

No se presupone estabilidad del orden entre importes iguales. Selecciones distintas en el cutoff solo son legítimas si ambas cumplen íntegramente esas condiciones. La comparación lo explica y registra cantidad de UUID distintos; no declara iguales listas que contengan filas incorrectas. P-15/P-25 siguen pendientes de aceptación académica de la estrategia; no se implementó un sort secundario auxiliar porque no era necesario.

Caso controlado realmente probado en PG: 1005 elegibles, dos superiores, 1002 empatados y uno inferior; cada variante devolvió 1000 cumpliendo la regla. La comparación cruzada con selecciones distintas se probó unitariamente, sin presentarla como integración Mongo.

## Índices: inspección, preparación y límites

```bash
# Solo inventario:
./scripts/queries.sh indexes --engine mongo
./scripts/queries.sh indexes --engine postgres
# Adiciones requeridas Mongo, sin borrar índices previos:
./scripts/queries.sh indexes --engine mongo --apply
# PG: deja BLOCKED si se exige la expresión temporal original.
./scripts/queries.sh indexes --engine postgres --apply
# Propuesta textual explícita, para preparación/piloto autorizado:
./scripts/queries.sh indexes --engine postgres --apply --accept-text-index-proposal
```

Mongo requiere _id nativo más timestamp:1 y order_id:1 simples, sin unique extra, TTL, parcial, sparse, collation ni índice del total. El _id es único implícitamente aunque getIndexes no muestre unique. Índices extra/duplicados se notifican y no se eliminan. La preparación crea solo los dos faltantes e inspecciona después; está implementada y probada unitariamente, pendiente de Mongo real.

PG inspecciona catálogo, PK id, método B-Tree, columnas/expresión, validez y predicado. En PostgreSQL real se comprobó timestamptz_in con volatilidad s (STABLE), y se rechazó CREATE INDEX sobre ((data->>'timestamp')::timestamptz). No se crea una función falsamente IMMUTABLE ni se altera el servidor para conseguirlo. [CREATE INDEX exige funciones inmutables](https://www.postgresql.org/docs/18/sql-createindex.html).

La alternativa implementada es B-Tree textual sobre data->>'timestamp', únicamente con opt-in de propuesta. Se probó en una base aislada, se inspeccionó su definición, PK y ausencia de índice del total; repetir preparación no duplica índices. El predicado original sigue casteando a timestamptz: no se afirma que utilice ese índice. El informe conserva status=BLOCKED para comparabilidad académica aunque physical_index_status=PASS. En el pequeño plan PG posterior se observó Seq Scan → Sort → Limit.

Alternativas pendientes P-06/P-26: aceptar índice textual manteniendo consulta original y registrar su efecto real, o aprobar un experimento separado con columna temporal/materialización y consulta adaptada. Ninguna reemplaza automáticamente la original. Incluso un índice compatible no garantiza uso: EXPLAIN debe comprobarlo. Preparación puede tomar locks; tiene timeout y no debe ejecutarse con otras cargas. Un fallo puede dejar alguna adición Mongo realizada; nunca se borra para revertir automáticamente.

## Ejecución, validación y planes

Servicios y .env de Fases 1–2 deben estar disponibles. No se inician ni cambian perfiles desde estos comandos:

```bash
./scripts/queries.sh run --engine mongo --query Q1
./scripts/queries.sh run --engine mongo --query Q2 --variant allow_disk_false
./scripts/queries.sh run --engine mongo --query Q2 --variant allow_disk_true
./scripts/queries.sh run --engine postgres --query Q1
./scripts/queries.sh run --engine postgres --query Q2 --variant work_mem_4mb
./scripts/queries.sh run --engine postgres --query Q2 --variant work_mem_64mb

./scripts/queries.sh validate --engine both --query Q1 --file data/orders-42.jsonl --report data/q1-validation.json
./scripts/queries.sh validate --engine both --query Q2 --file data/orders-42.jsonl --report data/q2-validation.json
# Diagnóstico parcial (status global BLOCKED si falta el otro motor):
./scripts/queries.sh validate --engine postgres --query Q1 --file data/orders-42.jsonl

./scripts/queries.sh explain --engine postgres --query Q1 --report data/pg-q1-plan.json
./scripts/queries.sh explain --engine postgres --query Q2 --variant work_mem_64mb --report data/pg-q2-plan.json
./scripts/queries.sh explain --engine mongo --query Q2 --variant allow_disk_true --report data/mongo-q2-plan.json
```

validate exige JSONL/manifiesto válido y verifica todo el contenido almacenado con el comparador de Fase 2 antes de comparar resultados. Ejecuta todas las variantes configuradas del query; si hay ambos motores, compara todas las combinaciones. PASS=ambos resultados correctos contra fuente; FAIL=discrepancia; BLOCKED=datos/configuración/motor/evidencia faltantes. Una comprobación individual puede ser PASS y la equivalencia cruzada BLOCKED. run/explain PASS solo afirma ejecución, no equivalencia ni rendimiento. Reportes se crean de forma exclusiva, sin sobrescribir existentes; no contienen credenciales ni modifican el CSV oficial.

La fuente debe permanecer inmutable y sin escritores concurrentes, como en Fase 2. El oráculo mantiene un conjunto de UUID de fuente para detectar duplicados (memoria O(N)); Q1 acumula grupos y Q2 también retiene proyecciones elegibles para validar empates: se ejecuta fuera de mediciones y no se ha perfilado con 500000. No se llama al oráculo/preflight/CLI dentro de una ventana de benchmarking futura sin diseñar antes ese runner.

Mongo explica con c.explain('executionStats').aggregate(pipeline, options); PG con EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) sobre SQL original y misma variante. Se guardan plan crudo, opciones/versión efectiva, fecha UTC y resumen por ruta de nodo. Se identifican lecturas/índices/sort/aggregate, filas/loops, memoria y temporales cuando el motor los expone; ausente es null, no cero. No sumar ciegamente contadores de padres/hijos. Mongo conserva Extended JSON diagnóstico, separado de la decodificación estricta de importes.

Evidencia real pequeña PG en docs/evidence/phase3/: planes Q1 y Q2 4/64MB, plan tras índice textual, inventario y validaciones/control de empate. Q1 mostró Aggregate/Nested Loop/Seq Scan/Function Scan; Q2 Limit/Sort/Seq Scan. Esto identifica ejecución, no un ganador ni un cuello de botella a escala. No usar tiempos de EXPLAIN como P50/P95/P99 del runner.

## Memoria y ausencia de spill

Mongo puede coalescer $sort seguido de $limit y conservar solo los mejores K; proyección/otras optimizaciones pueden reducir memoria. Permitir disco no obliga a derramar, y prohibirlo no demuestra fallo en un Top-1000 pequeño. [Optimización del pipeline](https://www.mongodb.com/docs/manual/core/aggregation-pipeline-optimization/) y [límites de agregación](https://www.mongodb.com/docs/manual/core/aggregation-pipeline-limits/) explican límites por operación/etapa y control de allowDiskUse. El límite de contenedor también sigue vigente.

En PG work_mem no es un presupuesto global del servidor: varias operaciones, workers y sesiones pueden acumular consumos. Una hipótesis de 50 clientes con una operación usando 64 MiB cada uno suma 3200 MiB antes de otros consumos; no es una medición ni una predicción de OOM. El consumo real depende del plan/Top-K; [documentación de recursos](https://www.postgresql.org/docs/18/runtime-config-resource.html). No se simula concurrencia en esta fase ni se modifica dataset, K, cuotas o memoria para inducir spill/OOM. Las métricas disponibles se conservan en planes; falta observación de carga definitiva. Experimentos alternativos requieren aprobación y nunca sustituyen Q2.

## Pruebas, errores y continuidad

```bash
python3 -m unittest discover -s tests -p 'test_queries*.py' -v
./tests/test_infrastructure.sh
# Acción explícita con servicios en marcha: nuevas bases de pruebas, sin borrado.
./tests/test_queries_integration.sh --run both
./tests/test_queries_integration.sh --run postgres
```

Sin opt-in, las nueve integraciones se omiten (skip); no contarlas como pruebas del motor. En Cloud se ejecutaron nueve casos reales PG con 10/100/1000, control de frontera temporal, grupos exactos, precisión periódica, variantes/aislamiento, planes, índices, empates Top-1000 con 1005, calendario inválido y totals-only. La preparación de índice con timeout se revalidó de forma dirigida. Bases auxiliares se conservan, sin DROP/DELETE/TRUNCATE. Mongo solo tiene pruebas de construcción/interfaz, oráculo y planes sintéticos de unidad; no hay equivalencia real entre ambos.

Errores comunes: alias ausente/importe string, timestamps mixtos o calendario inválido, variantes cruzadas entre motores, datos almacenados distintos de fuente, índices extra, permisos/timeouts o servicios ausentes. Detener con diagnóstico; no redondear arbitrariamente, corregir consulta o borrar datos para hacer pasar validación. Los errores de servidor se resumen sin volcar credenciales ni filas; revisar logs localmente si es necesario.

Pendiente en Kubuntu: comprobar ambos motores/versiones/tipos, construir índices autorizados, confirmar la decisión temporal/numérica/alias, ejecutar integración both y validación de fuente completa, planes en condiciones controladas y conjunto definitivo. Nuevos informes no resuelven P-02 (matriz), P-03 (alias), P-06 (índice) ni P-24/25/26 automáticamente. Requiere nueva instrucción para Fase 4 y diseño aprobado de sesiones/mediciones; no implementar runner ahora.

El respaldo fase3-consultas-kubuntu.zip conserva todo el proyecto y evidencia real de corrección, excluyendo secretos, .env reales, datasets masivos, volúmenes, cachés, temporales y ZIP previos. /workspace no se asume persistente: descargar/recuperar el ZIP desde el explorador del entorno antes de terminar la sesión si el enlace local no permite descarga directa.


## Continuidad tras autorización U6

Las afirmaciones de ausencia/prohibición de runner anteriores describen el cierre histórico de Fase 3. U6 autorizó Fase 4: QueryExecutor.open_session añade sesiones nativas persistentes mediante queries/native.py, conservando la CLI, SQL/pipelines y validadores aquí documentados. [Automatización](12-automatizacion-benchmarks.md) define clientes/tiempos/CSV y sus pruebas. Mongo real y equivalencia cruzada siguen pendientes; no se convirtió el tiempo de EXPLAIN en percentiles ni se aprobó el índice temporal.
