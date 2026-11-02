# Generación, carga y verificación de datos — Fase 2

## Estado y alcance

Implementación terminada y validación parcial: unitarias y PostgreSQL real comprobados en Cloud; MongoDB real, equivalencia real entre ambos motores y carga de 500,000 órdenes en Kubuntu pendientes. Fase 2 IN_PROGRESS por validación incompleta, sin bloqueo de desarrollo por Fase 1. No se cambia infraestructura, imágenes ni límites; al cierre de Fase 2 no había Q1/Q2 ejecutables. U5 los implementa después en Fase 3 (docs/11), sin runner, benchmarks ni resultados de rendimiento.

Fuentes: P (playbook.pdf) p.1 §2, pp.1–2 §4, pp.2–3 §5; S (playbook_sesion.pdf) pp.3,6–7. U4 es la solicitud de Fase 2, §§3–18. Ver [contrato original](03-dataset-y-consultas.md), [trazabilidad](01-requisitos-y-trazabilidad.md) y [pendientes](07-decisiones-y-pendientes.md). Los campos originales son requisitos; tipos secundarios, distribuciones, fórmulas y alias descritos abajo son propuestas provisionales implementadas por autorización de U4, no aprobaciones del profesor.

## Requisitos operativos

Python 3 con biblioteca estándar, sin pip, drivers ni servicios externos. Probado con Python 3.12.14; previsto para 3.10+ de Kubuntu, otras versiones pendientes de comprobación. Se usa SHA-256 con contador para el PRNG, independiente del módulo random de Python. Las fechas no dependen del reloj ni de la zona horaria local. Conservar la versión 1.0.0 del generador y esquema orders-v1-provisional; los cambios de algoritmo/contrato deberán versionarse y producir nuevos archivos.

Para cargar: servicios existentes de Fase 1 en marcha, .env local ya configurado y acceso al socket Docker local. Los scripts reutilizan common.sh, Compose y los IDs de contenedores; no publican puertos ni instalan paquetes. Los clientes mongosh y psql son los de las imágenes existentes. Autenticación con variables de inicialización dentro del contenedor, sin contraseñas en argv, informes o dataset; .env debe corresponder a esa instalación. Cambiar cuentas dentro del motor requiere sincronizar su configuración, no borrar volúmenes.

No se requiere acceder al equipo físico ni iniciar contenedores para generar/validar archivos o correr unitarias. No se debe completar Fase 1 ficticiamente para continuar desarrollo.

## Contrato implementado (provisional v1)

JSON Lines UTF-8: un objeto por línea, claves ordenadas, terminador LF, números JSON sin comillas. Los archivos son comunes a ambos motores; no son Extended JSON. El validador estricto rechaza campos ausentes/adicionales, claves duplicadas, NaN/Infinity, floats binarios en objetos Python, UUID no canónicos, fechas inválidas, importes incoherentes y duplicados. Máximo 1 MiB por línea de entrada como protección; cada orden generada queda muy por debajo.

| Campo | Representación implementada |
| --- | --- |
| order_id | UUIDv5 canónico como string; namespace fijo, semilla e índice de orden |
| timestamp | String UTC de segundos YYYY-MM-DDTHH:MM:SSZ, sin formatos/offsets mezclados |
| customer | id UUID string; tier standard/silver/gold; segment retail/business; geo objeto |
| customer.geo | country/state/city/zip strings coherentes de catálogo; coordinates [longitud,latitud] numéricas a 6 decimales |
| items | Arreglo de 1..5 artículos |
| items[] | sku/category/brand strings; qty entero 1..6; price decimal monetario; tax_pct numérico; discounts lista de 0..1 importes decimales de descuento por línea |
| payment | method/status strings; transaction_id UUID string; gateway_latency_ms entero 10..1500; totals objeto obligatorio |
| payment.totals | subtotal, discount, tax y final_total, todos importes a dos decimales |
| payment.final_total | Alias provisional del total calculado, presente por defecto; no sustituye totals |
| metadata | channel/user_agent strings sintéticos; session_id UUID; flags objeto con gift/priority booleanos |

Se conserva la estructura principal y anidamiento aproximado de P/S. El manual no define forma de coordinates, discounts, flags ni totals, tipos de subcampos, moneda o fórmula contable: esta es una concreción de trabajo, no una transcripción literal completa del profesor. Sin datos personales reales. Los importes se interpretan en una unidad monetaria sintética común, sin tasas de conversión entre países.

### Totals, precisión y reversibilidad

P §4 exige totals; P §5.2 consulta final_total. La adaptación P-03 conserva totals y añade payment.final_total = payment.totals.final_total. Alternativas históricas: corregir consulta o contrato mediante aprobación; ninguna se aplica silenciosamente. Para generar sin alias usar `--payment-layout totals-only`: conserva totals y su información. Ese layout no prepara directamente la ruta Q2 original; no mezclar layouts en una misma carga. Regenerar a ruta nueva, no alterar datos cargados ni versiones antiguas automáticamente.

Cálculo propuesto por artículo: bruto = qty × price; descuento = suma(discounts); impuesto = (bruto − descuento) × tax_pct / 100, redondeado a centavos ROUND_HALF_UP por línea. totals acumula bruto/descuentos/impuestos; final_total = subtotal − discount + tax. Q1 original usa bruto sin esos ajustes: este generador no modifica la definición de Q1.

Python usa Decimal exacto y escribe tokens JSON numéricos. El adaptador Mongo convierte decimales a BSON Decimal128 mediante Extended JSON solo en el transporte y conserva enteros como BSON enteros. PostgreSQL recibe los mismos tokens JSON en data JSONB (numéricos exactos). No hay conversión por double. Se normaliza la escala numérica al comparar: 1 y 1.00 son semánticamente equivalentes; strings "1.00", booleanos y fechas BSON no se confunden con números/strings UTC. BSON double inesperado se rechaza, no se redondea para ocultar pérdida. Los rangos generados caben en la precisión Decimal128; no se aceptan importes arbitrarios fuera del contrato.

Identidad provisional: orders.id UUID = data.order_id; en MongoDB _id técnico = order_id string, para aprovechar unicidad nativa y detectar duplicados sin imponer un índice unique adicional a order_id. _id se valida pero se excluye del documento lógico comparado; la información de negocio es idéntica en ambos motores. No se renombra ni elimina order_id. Estas propuestas siguen P-04/P-05/P-06, sin estado APPROVED.

## Distribuciones propuestas y explícitas

- Semilla predeterminada 42; count predeterminado 500000. UUID y entidades sintéticos deterministas (UUIDv5 por semilla/tipo/índice; clientes de un catálogo lógico de 100,000 posibles IDs).
- Longitud items uniforme en 1..5: media poblacional 3, no exactamente tres en toda muestra. La muestra observada de 1,000, semilla 42, tiene media 2.873; no es una tolerancia exigida por el manual ni una medición de rendimiento. La media de la carga definitiva deberá registrarse, no forzarse sin decisión.
- Ubicaciones uniformes entre Tuxtla Gutiérrez/MX, Austin/US, Bogotá/CO, Madrid/ES y Buenos Aires/AR; coordenadas cerca del centro, con perturbación uniforme ±0.02 grados, sin datos personales. Catálogo coherente de estado/ciudad/código postal; no catálogo exhaustivo real.
- Categorías uniformes electronics/home/books/clothing/sports/food; 10,000 SKU y 30 marcas sintéticos. qty uniforme 1..6.
- price: probabilidad 55% de 0.01..50.00; 35% de 50.01..500.00; 10% de 500.01..2000.00. Centavos uniformes dentro de cada banda. Permite ítems que pasan/fallan price > 50.
- tax_pct uniforme 0/8/16; descuento por línea con probabilidad 20%, entre 1% y 10% de su bruto, redondeado a centavos. No son reglas fiscales reales ni requisitos del profesor.
- payment.status: completed 70%, pending 15%, failed 10%, refunded 5%; method uniforme card/transfer/cash/wallet; gateway_latency_ms uniforme entero 10..1500 (dato sintético, nunca latencia medida).
- Fechas uniformes en [2025-07-01T00:00:00Z, 2026-10-01T00:00:00Z), parametrizables. Hay órdenes fuera/dentro del filtro de 2026 y múltiples estados, importes y grupos. Las muestras pequeñas no garantizan 1,000 completadas para Q2. No se garantiza spill/OOM ni se alteran las distribuciones para favorecer un motor.
- tier: standard 50%, silver/gold 25%; segment uniforme retail/business; channel uniforme web/mobile/store; user_agent entre dos valores sintéticos; gift 10%, priority 5%.

## Generación y manifiesto

Desde la raíz del proyecto (elegir una carpeta de trabajo con espacio suficiente):

```bash
mkdir -p data
./scripts/generate_data.sh --output data/orders-42.jsonl --seed 42
# Prueba rápida, no la carga definitiva:
./scripts/generate_data.sh --output data/small-42.jsonl --seed 42 --count 1000 --progress-every 250
./scripts/validate_data.sh --file data/small-42.jsonl
sha256sum data/small-42.jsonl
```

La primera orden usa el predeterminado 500,000: está preparada para ejecución local, no se ejecutó en Cloud. Contenido incremental, una orden a la vez; no se mantiene una lista con 500,000 registros. El validador usa SQLite temporal en disco para UUID únicos con caché acotada, y estadísticas incrementales. Asegurar espacio para JSONL, SQLite temporal y ambos volúmenes; no se establece un tamaño de dataset medido de 500,000 que no se haya generado.

Se crea `<archivo>.manifest.json` con semilla, cantidad, versiones, intervalo, layout, perfil de distribución/PRNG/UUID, hash SHA-256 de bytes y hash lógico normalizado, conteos de ítems/estados. Fecha de generación y versión Python están en metadata del manifiesto, no en los documentos deterministas. Dos manifiestos pueden diferir en la fecha y conservar hashes idénticos. Progreso por stderr, resumen JSON por stdout; `--progress-every 0` lo desactiva. No hay sobrescritura: usar una ruta nueva. Un proceso interrumpido conserva archivos parciales/manifiesto vacío para inspección; no se permiten importar sin validar manifiesto/hash.

Hashes de referencia realmente verificados, configuración predeterminada salvo count:

| Semilla | Count | SHA-256 JSONL |
| --- | --- | --- |
| 42 | 100 | 4654466a1e399e3ed332a5d044b1b8478ef6dfe55509f8dbf1249fca66db0587 |
| 42 | 1000 | 20c4e83b3694a07c80da80a681639df4b5931490d283c0ac37b638225aaec20a |

## Carga no destructiva

Los servicios deben estar disponibles. Los scripts de datos no los inician ni cambian perfiles. Preparación de servicios y aceptación de swap siguen [Fase 1](09-instalacion-kubuntu.md). La base Mongo usa el nombre POSTGRES_DB de la configuración para mantener un destino lógico explícito; la colección es orders. PG usa public.orders con id UUID PRIMARY KEY y data JSONB NOT NULL. Se verifica estructura y PK de una tabla existente; no se altera una tabla incompatible.

```bash
./scripts/import_mongodb.sh --file data/orders-42.jsonl --batch-size 250
./scripts/import_postgresql.sh --file data/orders-42.jsonl --batch-size 250
./scripts/count_records.sh
```

Primero se valida todo el archivo, esquema, fechas, UUID únicos, conteos y hash contra manifiesto; después se permiten escrituras. Batch-size 1..1000 controla memoria y tamaño de transporte. Mongo: insertMany ordered y lectura posterior del lote. PostgreSQL: COPY CSV de UUID + JSON dentro de BEGIN/COMMIT por lote, ON_ERROR_STOP, sin interpolar JSON en literales SQL. Cada lote se lee y compara íntegro contra el archivo; se comprueba conteo final. No hay upsert, DROP, TRUNCATE, DELETE ni reemplazos. No se crean índices del total ni cambios de work_mem/allowDiskUse.

Por defecto el destino debe estar vacío. Un destino con datos se rechaza antes de insertar. Recuperación explícita tras una carga parcial:

```bash
./scripts/import_mongodb.sh --file data/orders-42.jsonl --resume
./scripts/import_postgresql.sh --file data/orders-42.jsonl --resume
```

resume acepta únicamente UUID ya presentes cuyo contenido completo coincida; inserta faltantes, nunca reemplaza divergencias. Un fallo Mongo puede dejar parte de un lote insertado; PG revierte su lote fallido, aunque conserva lotes anteriores. No hay transacción entre motores ni rollback global automático. Datos ajenos pueden hacer fallar el conteo final: no se eliminan. Conservar el informe/estado e investigar. No correr cargadores concurrentes ni modificar archivo/manifiesto durante carga/comparación. Se verifica que el archivo no cambie durante la operación, pero no es un protocolo de snapshot distribuido.

Los índices del manual siguen compatibles: timestamp string homogéneo y order_id scalar en Mongo; id UUID y timestamp extraíble en PG. En Fase 2 solo se usa la PK nativa y _id; construir/verificar índices timestamp/order_id y decidir la expresión temporal B-Tree pertenece a Fase 3/P-06. Esta diferencia provisional está registrada; no ejecutar benchmarks sobre una indexación aún no aprobada.

## Integridad y equivalencia

```bash
# Comparación completa por defecto, todos los UUID y contenido contra la fuente:
./scripts/compare_data.sh --file data/orders-42.jsonl --report data/equivalence-42.json
# Muestra reproducible: no demuestra igualdad completa:
./scripts/compare_data.sh --file data/orders-42.jsonl --sample-size 100 --sample-seed 7
# Diagnóstico parcial de un solo motor:
./scripts/count_records.sh --engine postgres
./scripts/compare_data.sh --file data/small-42.jsonl --engine postgres
```

Comparación completa: conteo total idéntico, recorrido de todos los UUID del archivo por lotes, lectura de cada documento, tipos/esquema y cálculos validados, contenido canónico idéntico frente a fuente. Con conteos iguales, UUID de fuente únicos y todos los esperados presentes, no quedan extras. Verifica arrays, cantidades, importes, fechas, payment/metadata/customer completos; ignora solo orden de claves y escala equivalente de números exactos, y separa id/_id técnicos como se documentó. Comparar ambos motores con la misma fuente establece equivalencia lógica; `--engine postgres` o mongo prueba solo ese motor.

Muestra: selección por los menores hashes SHA-256 de sample-seed:order_id, memoria proporcional al tamaño solicitado; ranking independiente de random. Se siguen verificando los conteos totales, pero contenido solo de la muestra. El informe dice sample, checked y scope, sin afirmar igualdad global. En comparación full se produce hash lógico del contenido validado en orden de archivo; no depende del orden físico de los motores. No son métricas de rendimiento ni CSV del benchmark. `--report` crea un JSON nuevo sin credenciales, sin sobrescribir informes existentes.

## Pruebas y limitaciones

```bash
python3 -m unittest discover -s tests -p 'test_dataset*.py' -v
./tests/test_infrastructure.sh
# Solo con servicios iniciados; crea bases aisladas, conserva sus datos:
./tests/test_data_integration.sh --run both
# Si solo hay un motor disponible:
./tests/test_data_integration.sh --run postgres
```

Las pruebas de integración requieren opt-in; sin él se informa skip. Crean base phase2test_<UUID> y 100 registros, no borran bases, tablas, colecciones ni volúmenes. En PG también verifican rollback de un COPY con un UUID duplicado después de una fila nueva. La comparación usa los importadores reales; no un fixture de respuestas del motor. Unitarias con adaptador de memoria prueban manejo de fallos, claramente sin evidencia de base real.

Ejecutado en Cloud: 19 unitarias (10/1000 registros, golden hash, límites de memoria de generación pequeña, determinismo, UUID/fechas/estructura/números, duplicados, cálculos, layouts, errores y adaptadores); generación CLI de 100 repetida con cmp/hash idénticos; PostgreSQL real con 100, lectura total/muestra, rechazo de destino no vacío, resume idéntico y rollback de lote; suite Bash/Compose de Fase 1. No se generaron ni cargaron 500,000 documentos. El ensayo de memoria con 1,000 verifica un límite generoso del heap Python, no una medición de la carga masiva.

MongoDB no disponible: imagen retirada en Fase 1 tras agotar almacenamiento; Cloud conserva espacio insuficiente para volver a descargar/crear ambos motores de forma razonable. No se ejecutó integración real Mongo ni comparación real entre ambos. No se cambia la versión ni se eliminan datos para hacer pasar pruebas. Pendientes: ejecución de integración both, generación/carga definitiva de 500,000, conteos/equivalencia completa y compatibilidad/recursos del Kubuntu físico. El desarrollo no se bloqueó por ausencia del equipo.

## Diagnóstico y reproducción

- Manifiesto/hash distintos: detener carga, comprobar semilla, count, start/end, layout y versión del generador. Regenerar con esos valores a ruta nueva; conservar archivos originales.
- Esquema/fecha/UUID duplicado: el error indica línea y categoría. No se corrige silenciosamente ni se borran destinos.
- orders no vacío: revisar si corresponde al mismo manifiesto antes de usar resume. Divergencia de un UUID no se reemplaza.
- Error Docker/autenticación/timeout: revisar servicios y cuentas dentro de contenedores, permisos del socket y logs localmente. Detalles del servidor se omiten por defecto porque pueden incluir datos; no publicar inspect.Env ni .env. `--timeout 120` es por comando/lote, no garantía de carga completa.
- Tabla PG incompatible: conservarla y elegir una base de trabajo correcta; no ejecutar migración destructiva automática.
- Archivo cambiado/concurrencia: detener escritores y repetir verificación; los lotes previos pueden estar comprometidos. No afirmar snapshot consistente mientras haya escritores.
- Sin espacio: revisar disco de trabajo/temporales/volúmenes; no ejecutar prune ni borrar datos automáticamente.

Para reproducir un dataset anterior, leer su manifiesto y usar exactamente seed/count/start/end/payment_layout con la misma versión de esquema/generador; verificar SHA-256 de bytes antes de importar. La fecha metadata no debe copiarse para forzar igualdad: se compara el dataset, no la fecha de ejecución.

Respaldo fase2-dataset-kubuntu.zip contiene código, infraestructura sin cambios, documentación, manuales y pruebas; excluye datasets generados, informes operativos, .env reales, credenciales, volúmenes, cachés, temporales y ZIP anteriores. Estos últimos se conservan aparte como historia. No iniciar Fase 3 sin nueva instrucción y resolución de decisiones para consultas/índices.
