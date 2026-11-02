# Dataset y consultas

Reconciliación: P p.1 §§2,4; p.2 §§4,5.1–5.2 y p.3 §5.2; S pp.3,6–7. Ver REQ-003–006, 023, 025, 027–031. Este apartado conserva el análisis original de Fase 0; el generador/importadores implementados por U4 se describen al final y en docs/10. En Fase 2 no se implementaban Q1/Q2; U5 autoriza su implementación en Fase 3 sin cambiar el contrato provisional.

## Contrato original del dataset

500,000 registros JSON; P §4 dice tres niveles de anidamiento y promedio tres ítems por registro; S p.3 dice aproximadamente tres niveles. Distribuciones, nulabilidad, rangos y tolerancia del promedio no están especificados (P-13).

| Campo | Estructura y tipo indicado por P §4 | Información no fijada |
| --- | --- | --- |
| order_id | UUID | Codificación JSON/BSON y relación con PK id |
| timestamp | ISO-8601 | Zona y precisión uniformes para todos los datos |
| customer | Objeto: id, tier, segment, geo | Tipos de subcampos |
| customer.geo | country, state, city, zip, coordinates | Forma y tipo de coordinates |
| items | Arreglo de objetos | Distribución de longitud |
| items[] | sku, category, brand, qty, price, tax_pct, discounts | Tipos y forma de discounts; precisión numérica |
| payment | Objeto: method, status, transaction_id, gateway_latency_ms, totals | Forma/tipo de totals; ausencia de final_total en este listado |
| metadata | Objeto: channel, user_agent, session_id, flags | Tipos y estructura de flags |

No se añade un ejemplo JSON que pudiera fijar por accidente los tipos no definidos.

## Almacenamiento e índices

P p.1 §2: MongoDB, colección orders sin sharding, WiredTiger, índices simples en timestamp y order_id. PostgreSQL, tabla orders (id UUID PRIMARY KEY, data JSONB), PK id y B-Tree sobre timestamp extraído del JSONB. P §5.2 prohíbe índices previos sobre el total para Q2. No se exige índice único de order_id en MongoDB ni se debe inferirlo del índice simple.

La correspondencia orders.id ↔ data.order_id no está explícita: se propone conservar el mismo UUID con aprobación (P-06). Tampoco se define la expresión B-Tree: texto ISO y cast a timestamptz no son equivalentes para el plan; hay que verificar viabilidad de la expresión temporal y no sustituirla silenciosamente. Las asimetrías PK/order_id y timestamp deben figurar en el reporte.

## Q1 — Unwind, Filter & Grouping

P p.2 §5.1: desanidar items, filtrar items.price > 50 (estricto), subtotal = qty × price; agrupar por customer.geo.country y items.category. Salidas: total_revenue (suma), avg_revenue (promedio) y count (ítems que pasan el filtro). MongoDB usa unwind/match/group y PostgreSQL jsonb_array_elements con conversiones numeric. No hay orden de salida exigido: comparar grupos por clave, no por posición. No añadir filtros de fecha ni descuentos/impuestos al cálculo.

## Q2 — Massive Sort & Top-K

P pp.2–3 §5.2: payment.status = completed; timestamp >= 2026-01-01T00:00:00Z; ordenar payment.final_total descendente; límite 1000. El texto dice «rango de fechas», pero ambos ejemplos solo fijan límite inferior: no añadir límite superior (P-15). Proyección MongoDB: order_id, customer.id, payment.final_total; SQL: order_id, customer_id, final_total con cast numeric. El pipeline no excluye explícitamente _id: documentar esta diferencia de presentación en vez de modificarlo sin registro.

Variantes obligatorias: MongoDB allowDiskUse:false y true; PostgreSQL work_mem 4MB y 64MB. No son garantías de spill, OOM ni éxito; dependen del plan, datos y memoria efectiva. S p.7 contiene un ejemplo expresamente ficticio: no es una medición y su frase «false ⇒ spill o fallo» no demuestra spill con disco deshabilitado. Conservar el comportamiento real y la configuración. No aumentar dataset ni cambiar Top-K para forzar eventos (P-17).

## Inconsistencias y equivalencia semántica

- Payment: P p.2 §4 declara totals, pero §5.2 consulta final_total. Propuesta P-03: mantener totals y añadir final_total con relación numérica definida, solo tras aprobación; alternativas: corregir consulta o especificación con autorización. En Fase 0 no se elegía una; U4 autoriza implementar provisionalmente la primera, conservando el estado pendiente de aprobación.
- Tiempo: dataset ISO-8601 y comparación MongoDB contra cadena frente a cast SQL a timestamptz. Propuesta P-04: cadenas UTC de forma/precisión uniformes compatibles con el literal para preservar el orden cronológico; no importar BSON Date sin adaptar y aprobar consulta. Offsets o formatos mixtos invalidarían equivalencia lexicográfica.
- Números: SQL usa numeric; MongoDB hereda tipos almacenados. P-05 debe fijar representación, escala y redondeo; no convertir todo a double ni asumir tolerancia cero. qty/price y final_total deben tener tipos comparables y presentes para evitar diferencias de null/ausente y orden por tipo.
- Top-K: no hay criterio de desempate para totales iguales. Validar orden y frontera del Top-1000 con empates; no exigir listas idénticas ni añadir sort secundario sin acuerdo (P-15).
- Presentación: normalizar _id de agrupación, objetos anidados y alias SQL solo en el comparador; proponer excluir _id técnico del contraste de Q2 sin cambiar silenciosamente el pipeline (P-15).

## Generación e importación propuestas

Python con semilla explícita, algoritmo y dependencias versionadas; guardar configuración, conteo, hash del archivo y resumen de distribución. Antecedente Fase 0: no se habían seleccionado librerías/versiones. En Fase 2 se usa biblioteca estándar, generador 1.0.0 y esquema orders-v1-provisional, comprobados con Python 3.12.14. Conservar un único dataset fuente, importar su contenido a ambos motores mediante lotes parametrizables y validar conteo, identificadores y hashes canónicos. Los adaptadores deben documentar diferencias BSON/JSONB y evitar pérdida de precisión. Son propuestas de reproducibilidad, no parámetros exigidos por P.

Toda solución de esquema, fecha, tipo o índice permanece pendiente según [registro](07-decisiones-y-pendientes.md). La equivalencia se comprobará antes de medir, para Q1 y cada modalidad Q2, con evidencia de cardinalidad y contenido.

## Concreción provisional implementada en Fase 2 (U4)

La especificación original anterior se conserva como fuente; U4 §§4–8 autoriza concretar campos/distribuciones no definidos y una adaptación reversible, sin marcarla aprobada. Modelo normativo del código: src/dataset/model.py; contrato y operaciones en [guía de datos](10-generacion-y-carga-datos.md). P-03/P-04/P-05/P-06/P-13 siguen pendientes de aceptación para el experimento.

Implementado: todos los campos del manual; totals como subtotal/discount/tax/final_total, con alias adicional payment.final_total por defecto. `--payment-layout totals-only` elimina solo el alias al generar un archivo nuevo y conserva totals. Fechas UTC homogéneas de segundos, decimales exactos (Decimal128 en Mongo/numéricos JSONB), qty entero, coordinates [lon,lat], discounts lista de importes y flags gift/priority booleanos. UUIDv5 reproducibles y PK id = order_id; _id técnico Mongo = order_id, separado de la comparación lógica. No se alteran ni eliminan datos existentes para cambiar el contrato.

Distribuciones sintéticas propuestas: items uniforme 1..5 (media poblacional 3); precios en tres bandas alrededor de price > 50; categorías y lugares variados; completed 70% y fechas que cruzan el límite de 2026. No son exigencias atribuidas al profesor. El promedio observado, importes y campos se validan con manifiesto; no se garantiza exactamente tres ítems ni spill/OOM.

Formato común: JSONL UTF-8 con tokens numéricos exactos; Extended JSON solo se usa en el transporte Mongo. Generación y carga por streaming/lotes; SQLite temporal para detectar todos los UUID duplicados en la fuente sin mantener un set de 500,000 elementos. Validación completa de origen antes de insertar, lectura posterior por lote, comparación completa o muestra determinista expresamente identificada como parcial. PostgreSQL importa por COPY CSV con transacción por lote; Mongo insertMany ordered puede conservar inserciones parciales si falla. Sin sobrescritura, drop ni borrado; resume solo acepta contenido ya idéntico.

Indexación: Fase 2 deja _id nativo de Mongo y PK id de PG; no construye índices del total. Los campos siguen compatibles con índices simples del manual, pero la creación/verificación de timestamp/order_id y la expresión B-Tree temporal quedan como puerta de Fase 3. No se afirma equivalencia de planes ni resultados Q1/Q2 hasta esa fase.

## Consultas implementadas por U5 — Fase 3

Pipelines y SQL originales en queries/; no se cambió generador/importadores ni tipos. El preflight lee tipos reales de timestamps/qty/price/final_total, confirma UTC canónico/calendario y alias; totals-only se bloquea explícitamente para Q2. Q1 usa bruto qty*price, ignorando impuestos/descuentos. Promedio se valida contra fracción exacta con cuantización técnica declarada, sin floats/epsilon arbitrario. Q2 mantiene solo sort de final_total; el comparador admite únicamente selecciones válidas del conjunto empatado en el cutoff.

En PG real se verificaron 10/100/1000, datos controlados, frontera temporal y empates; Mongo real pendiente. Índices: scripts seguros Mongo timestamp/order_id implementados, sin índice de total; PG cast a timestamptz no indexable directamente por su volatilidad STABLE. B-Tree textual solo como propuesta explícita, sin cambiar SQL ni declarar uso. P-03/04/05/06/15 no se resuelven por implementar pruebas. Ver [consultas y validación](11-consultas-y-validacion.md).
