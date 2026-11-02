# Métricas y evidencia

Fuentes: P p.3 §7 y p.4 §8.2; S pp.5,8–11; U §4.8. REQ-012–014, 032–034, 039. Esquema y KPIs confirmados; las fórmulas operativas no definidas por las fuentes siguen siendo propuestas.

## CSV oficial

```text
timestamp_epoch,engine,profile,query_id,concurrency,run_number,throughput_qps,latency_p50_ms,latency_p95_ms,latency_p99_ms,cpu_throttled_seconds,max_rss_mb,disk_spill,status
```

No renombrar, reordenar ni agregar columnas. S p.8 exige una fila por repetición y nota de estado ok/spill/oom/error. Vocabularios de engine/profile/query_id, codificación de variantes, nulos y precisión temporal aún requieren definición; la prioridad de status cuando coexisten eventos tampoco se especifica. No exportar cero para una medición ausente.

| Columna | Unidad / significado | Fuente y recolección propuesta | Agregación y validación |
| --- | --- | --- | --- |
| timestamp_epoch | segundos desde epoch, instante por definir | Reloj del runner | Propuesta: inicio de medición UTC; contrastar marcas |
| engine | identificador del motor | Configuración efectiva | Coincidir con manifiesto |
| profile | identificador de perfil | Configuración y cgroups | Verificar límites reales |
| query_id | carga/variante por definir | Contrato de consulta | Resolver identificación de variantes sin añadir columnas |
| concurrency | clientes, entero | Runner | Verificar 1/10/50 y actividad real |
| run_number | repetición, entero | Matriz | Cobertura 1/2/3, sin duplicados |
| throughput_qps | consultas/s | Operaciones completadas y reloj monotónico | Propuesta: éxitos/tiempo medido; fallos aparte; contrastar conteos |
| latency_p50_ms | ms | Duración por solicitud, reloj monotónico | Percentil 50 de ventana; algoritmo pendiente |
| latency_p95_ms | ms | Igual origen | Percentil 95; comprobar p50 ≤ p95 |
| latency_p99_ms | ms | Igual origen | Percentil 99; comprobar p95 ≤ p99 |
| cpu_throttled_seconds | s | container_cpu_cfs_throttled_seconds_total (P §7); cpu.stat como contraste | Delta en segundos en ventana; convertir /1e6 solo al leer throttled_usec; detectar reinicios |
| max_rss_mb | MB decimal implementado provisionalmente en Fase 5, aprobación P-10 pendiente | container_memory_rss_bytes (P §7), cAdvisor; validar alcance efectivo | Máximo muestreado de RSS convertido a MB; no sustituir por working set; divisor por acordar |
| disk_spill | Booleano propuesto por correspondencia con disk_spill_detected (booleano exigido) | Registros/estadísticas del motor por ejecución | Codificación CSV por confirmar; evidencia de caso positivo/negativo, no ausencia de logs como falso |
| status | Nota ok/spill/oom/error según S p.8 | Runner, motor y eventos | Prioridad si hay eventos múltiples pendiente; timeout detallado en evidencia lateral |

La agregación de percentiles debe hacerse sobre observaciones de la ejecución, no promediar percentiles por cliente. Falta acordar inclusión de fallos/timeouts, consultas que cruzan ventanas y método de cuantiles. No fusionar las tres repeticiones en una sola fila. El máximo de RSS por muestreo puede perder picos; registrar intervalo y alcance (proceso/contenedor). La fuente exigida de RSS ya está identificada; el divisor MB/MiB y su alcance deben cerrarse antes de implementar (P-10). S p.11 pide explicar cómo resumir repeticiones (media/mediana); el reporte conservará los tres valores y justificará el estadístico, sin reemplazar filas originales.

## Telemetría y evidencia lateral propuesta

Guardar por ejecución manifiesto, configuración efectiva, marcas de etapa, solicitudes crudas, logs de runner/motor, snapshots de contadores cgroup, exportaciones de Prometheus e inspección de estado del contenedor. Un manifiesto lateral enlazará fila CSV y evidencias por clave única, incluida variante; no altera columnas oficiales. Conservar originales y hashes, con política de almacenamiento pendiente.

OOM: contrastar incrementos de memory.events (oom/oom_kill), eventos y estado Docker y logs; código 137 por sí solo no demuestra OOM. Registrar muerte/reinicio y alcance temporal incluso si el runner no termina normalmente. Spill: obtener evidencia específica del motor y configuración usada, sin inferirlo solo por lentitud o actividad de disco. Errores: conservar tipo, mensaje, instante, operación y timeout; no descartar ejecuciones para favorecer un motor.

Propuestas adicionales, no métricas del profesor verificadas: uso de CPU, memoria corriente/working set, IO y duración por etapa para diagnóstico. Su presencia no reemplaza ninguna columna exigida. Limitaciones: frecuencia de scrape, pérdida de logs tras reinicio, permisos y visibilidad parcial de la VM. El catálogo confirmado de P §7 se detalla a continuación; propuestas adicionales deben permanecer separadas.

## Catálogo confirmado y correspondencia

| KPI literal de P p.3 §7 | Unidad | Fuente exigida / evidencia | Exportación |
| --- | --- | --- | --- |
| throughput_qps | queries/s | Runner | Columna homónima |
| latency_p50_ms, latency_p95_ms, latency_p99_ms | ms | Runner | Columnas homónimas |
| container_cpu_cfs_throttled_seconds_total | s | cAdvisor, contador cgroup | Delta → cpu_throttled_seconds |
| container_memory_rss_bytes | bytes | cAdvisor | Máximo y conversión → max_rss_mb |
| disk_spill_detected | boolean | Interna del motor, logs/plan según disponibilidad | Correspondencia propuesta → disk_spill |
| oom_killed | boolean | Evidencia de estabilidad, eventos/estado | Evidencia lateral y nota status, sin añadir columna |

P §7 exige cAdvisor, Node Exporter (host: I/O, disco, swap) y Prometheus con scrape_interval: 1s. No enumera nombres concretos de series Node Exporter ni algoritmos de detección internos: elegirlos y registrar su procedencia durante la implementación, sin atribuirlos al manual. Verificar continuidad de scrape, etiquetas del contenedor y deltas contra contadores; documentar datos faltantes.

S p.10 exige capturas o logs de spill/OOM. Si no ocurren en una ejecución real, conservar evidencia de observación y ausencia, sin fabricarlos ni asumir que permitir disco obliga a usarlo. El ejemplo de S p.7 es ficticio y no se reutiliza como resultado. M3 exige métricas normalizadas por 1,000 documentos (P p.1 §1); su operacionalización está OPEN (P-14), separada del CSV oficial. CPU utilizada es una propuesta de fuente necesaria para operacionalizar M3, no un KPI ya enumerado en §7.

## Convenciones operativas implementadas en Fase 4 (propuestas)

U6 §§8–11 autoriza implementar la medición sin aprobar automáticamente los detalles académicos de P-10. [docs/12](12-automatizacion-benchmarks.md) es la definición única detallada: QPS de éxitos íntegramente dentro de ventana fija; R7 exacto combinado entre clientes en SQLite, ns a ms con Decimal; errores aparte, cruces de borde excluidos en ambos indicadores y conteo de muestras. Ventana incompleta deja QPS/percentiles vacíos; cero éxitos de ventana completa da QPS=0 observado y percentiles ausentes. No se promedian percentiles por cliente.

Identificadores implementados: mongo/postgres, perfiles oficiales completos, Q1/Q2 sin variante embebida. Epoch refiere inicio de medición o, si no llegó, finalización del intento con timestamp_scope lateral. Spill 0/1 solo conocido; ausencia vacía. Precedencia propuesta oom → error/incompleto/ausencia → spill → ok. Telemetría cgroup limitada: delta throttled_usec/1e6 y oom_kill, snapshots con tiempos/alcance; no RSS ni spill inferidos. Sus bordes aproximados exigen validación en Fase 5. El divisor de max_rss_mb sigue pendiente porque no se implementó sustituto. Toda fila sin indicadores obligatorios tiene status=error y eligible_for_final_analysis=false.

Un CSV por intento confirmado conserva las 14 columnas; result.json registra variante y hash de fila. El consolidador exige sidecars y produce mapa externo ordinal/hash/variante/id; un cat de CSV pierde trazabilidad y no es entrada auditada. Pilotos/test/definitivos no se mezclan. Declaraciones de caché manual y configuración efectiva son evidencia separada; no confundirlas con métricas de rendimiento. El piloto PG real reducido de docs/evidence/phase4/ es evidencia del software y está excluido del análisis final, sin declarar comportamiento de RSS/spill/OOM ni ganadores.

## Implementación de telemetría de Fase 5 (U7)

[docs/13](13-observabilidad-y-telemetria.md) define el método vigente implementado: series originales a 1s por ID completo/labels/perfil, muestras frescas y finitas; delta throttling last−first estrictamente dentro de la ventana, sin extrapolación. Sus first/last/covered_seconds se guardan porque omite bordes y no equivale exactamente a 300s continuos ni a increase(). cpu.stat es contraste separado, no un reemplazo con otro alcance temporal. RSS=max observado/1000000, MB decimal propuesto; no pico absoluto ni working set. La elección operativa no cierra P-10/P-38 sin aceptación.

Nombre literal P §7 container_memory_rss_bytes frente a nombre **real** cAdvisor 0.60.6 container_memory_rss: misma unidad bytes, discrepancia nominal documentada/contrastada con catálogo y scraping, sin renombrar max_rss_mb. OOM usa evento Docker con timeNano en ventana y continuidad/identidad; estado OOM nuevo posterior puede ser solo intento y se etiqueta así. Spill usa registros reales por PID/intervalo PG o token/tag/profile Mongo, con true/false mediante cobertura válida/null insuficiente. EXPLAIN posterior nunca prueba lo ya cronometrado.

telemetry-evidence.json conserva PromQL/respuestas/samples/errores, clocks/ventana, identidades/versiones/recursos observados y referencias a journals; commit de Fase 4 incluye sus hashes. Ausencia/error/gap excluye elegibilidad; no se completan ceros. Cero constante con muestras/cobertura válidas sí es observado. Los pilotos reales PG con fuente suficiente pueden tener status=ok, pero mode=pilot/eligible=false siempre los excluye de resultados finales. El intento fallido inicial se conserva con nulos/status=error, no se reemplaza por la ejecución corregida.


## Análisis incremental implementado — U8 / Fase 6

[Guía operativa](14-analisis-y-reporte.md). reporting/ conserva el CSV oficial sin cambios; lee filas comprometidas con su mapa de variante y valida metadata/evidencia. Cada informe conserva snapshots y hashes; no se sobrescriben fuentes, no se toma el lock del runner y no se hacen consultas de bases de datos para analizar resultados. Archivos incompletos quedan pendientes; commits corruptos son fallidos e impiden un FINAL.

Los resúmenes se calculan con Decimal sobre repeticiones válidas y homogéneas: media, mediana, mínimo y máximo de los KPIs de cada repetición. La media/mediana de tres P99 es un resumen de P99 por repetición, nunca el percentil de todas las latencias combinadas. Tablas identifican n/3 y excluyen errores, OOM e incompletos de estadística de rendimiento, sin ocultar sus estados. Las repeticiones no constituyen una demostración de significancia estadística; no se añaden pruebas inferenciales injustificadas.

Comparaciones Mongo/PostgreSQL requieren tres repeticiones 1–3 por escenario y la misma cohorte: dataset/hash, protocolo, host/boot, versiones de código/dependencias, monitoreo y política de matriz. Las variantes no se mezclan. Q2 requiere pareja explícita para contraste descriptivo; eso no establece equivalencia de allowDiskUse/work_mem ni aprobación de P-02/P-14. Diferencia = PG − Mongo; porcentaje = 100 × diferencia / Mongo, no calculable si base=0. Matrices base/extendida se separan incluso si comparten celdas.

Gráficas: mediana de P99 por concurrencia con huecos; throttling/QPS por repetición; RSS con muestras temporales reales de la ventana exacta, MB decimales observados y discontinuidades de scraping. Un máximo aislado no permite reconstruir una curva. El máximo observado no garantiza el pico instantáneo. Las figuras piloto llevan identificación no definitiva.

M3 sigue NO CALCULABLE sin documentos realmente procesados y CPU utilizada atribuible: QPS, cantidad del dataset y tiempo de throttling no sustituyen esos insumos. Los planes auxiliares no acreditan el comportamiento de una ejecución cronometrada previa. El nuevo vínculo opcional de EXPLAIN con archivo fuente verifica hash/lectura completa fuera de medición, sin modificar la consulta.

FINAL requiere matriz completa aprobada, una cohorte definitiva, 500000 equivalentes, protocolo íntegro, preflight/variantes/límites/telemetría válidos, auditoría completa de hashes, RSS temporal y planes vinculados. Sin esos insumos se genera únicamente un parcial explícito; informe parcial no convierte una fila inválida en válida ni resuelve decisiones pendientes.
