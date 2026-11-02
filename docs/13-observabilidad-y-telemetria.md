# Observabilidad y telemetría — Fase 5

Estado al 2026-11-01: implementada y parcialmente validada (IN_PROGRESS). U7 autorizó esta fase; U8 autorizó posteriormente análisis offline de Fase 6. No Fase 7 ni benchmarks definitivos. Fuentes normativas: P p.3 §7 (Prometheus/cAdvisor/Node Exporter y KPIs), P p.4 §8.2 (CSV), S pp.5,8–11 (límites reales, estados y evidencia), U7 §§3–20. Las fórmulas operativas, instrumentos y unidades no fijadas por P/S siguen propuestas, sin aprobar automáticamente P-10/P-14. [Handoff](08-handoff.md) registra las pruebas exactas.

## Arquitectura y versiones

config/monitoring/compose.monitoring.yml define un proyecto separado con Prometheus, cAdvisor y Node Exporter; no modifica docker-compose.yml ni límites/versiones/volúmenes de los motores. Prometheus captura cada segundo; el runner existente solicita las series de su repetición y guarda evidencia con CSV/JSON/commit de Fase 4. observability/ contiene configuración, cliente HTTP, selección de series, identidad, eventos, spill, proveedor y CLI. No hay segundo runner ni Grafana.

| Componente | Referencia explícita verificada | Digest de índice multiarquitectura |
| --- | --- | --- |
| Prometheus | prom/prometheus:v3.15.1 | sha256:fa3302279710be2f21a8301ec17a8b4f2301fd829bd113839b3b6b02b6f191a2 |
| cAdvisor | ghcr.io/google/cadvisor:0.60.6 | sha256:b8e7d1093144fd088f425ff003d75a4aa405de075db78dae3bc563730b1bd07a |
| Node Exporter | prom/node-exporter:v1.12.1 | sha256:1b4e4438faca4dd7e001dd445d161a4a2091b0fededa84093b3a8dfeae1f1be0 |

Releases y manifiestos oficiales consultados; linux/amd64 existe. Los tres pulls fueron verificados. La imagen Prometheus recién descargada se retiró después de agotar el disco VFS de Cloud; ninguna imagen previa, volumen o dato se eliminó. Para integración Cloud se usó el binario oficial Prometheus 3.15.1 linux-amd64, archivo SHA256 `6a726885328ad9efebbf36e876ce2fb6225468a71fd1e7ce3ba666d5f4d97a84`, cotejado con sha256sums.txt oficial. cAdvisor/Node sí se ejecutaron en Docker. La variante binaria de prueba no demuestra ejecución completa del Compose de producción. [Versiones y evidencia](evidence/phase5/README.md).

## Red, permisos y persistencia

Red monitoring interna y separada de la red database. Exportadores sin puertos de host; Prometheus publica solamente 127.0.0.1:19090. Datos TSDB en volumen nombrado prometheus_data; configuración montada solo lectura. prometheus.yml no contiene secretos y se conserva con modo 0644 para que el usuario nobody de la imagen oficial pueda leer el bind mount. Raíz de contenedores readonly, cap_drop ALL, no-new-privileges y ningún contenedor privileged. Los servicios de monitoreo no reciben los límites baseline/medium/severe destinados al motor: comparten CPU/RAM/IO del host y pueden contaminar las mediciones; medir su sobrecarga en Kubuntu antes de conclusiones.

cAdvisor usa namespace cgroup del host, /sys y raíz del host en /rootfs solo lectura, DockerRootDir montado y socket Docker. **Montar docker.sock con :ro no convierte la API Docker en solo lectura**: un proceso comprometido puede controlar el daemon. Esta autoridad es considerable aunque no exista privileged. Node Exporter comparte UTS del host para nodename y monta raíz, /proc y /sys del host solo lectura; puede observar información de procesos/sistema. No se comparte PID del host ni se monta /dev/kmsg ni se amplían capacidades para ocultar incompatibilidades. Los accesos se aceptan explícitamente con MONITORING_ACCEPT_HOST_ACCESS=true antes de start; nunca se conceden silenciosamente por el script.

cAdvisor exporta únicamente las etiquetas de contenedor autorizadas: com.docker.compose.project, com.docker.compose.service y academic.profile, además de sus etiquetas técnicas. No se exportan todas las etiquetas/variables de entorno. Su imagen distroless no contiene wget; se comprueba mediante scraping real y targets UP, al igual que Node Exporter. Prometheus tiene healthcheck HTTP /-/ready con wget de su base BusyBox; su ejecución dentro de imagen permanece pendiente en Kubuntu. Healthcheck de proceso o HTTP 200 aislado no acredita series válidas.

## Configuración de Prometheus y almacenamiento

prometheus.yml fija scrape_interval=1s, scrape_timeout=800ms y evaluation_interval=1s para cadvisor:8080, node-exporter:9100 y el propio Prometheus. cAdvisor fija housekeeping mínimo/máximo a 1s sin ajuste dinámico. No se ahorra almacenamiento alterando la frecuencia. Retención predeterminada 7d, parametrizable con mínimo 24h, y retención por tamaño desactivada (0B): un límite de tamaño podría eliminar datos antes del plazo temporal. El proveedor rechaza una política de tamaño no documentada para definitivos. Prometheus normaliza 7d como 1w; se compara duración semántica, no cadenas distintas de igual valor.

La matriz nominal extendida dura 18h54 sin preparación ni interrupciones; planificar margen y extender retención si se reanuda días después. La persistencia no garantiza espacio. monitoring.sh storage informa espacio del filesystem del proyecto y advierte que puede diferir del volumen Docker. El preflight definitivo además exige el volumen TSDB escribible/persistente identificado y consulta df -Pk /prometheus dentro de su contenedor. Estima 24h a partir de prometheus_tsdb_head_series observado, 1 muestra/s, 3 bytes/muestra más 50% de margen; exige como mínimo esa estimación y MONITORING_MIN_FREE_MB (1024 por defecto). No es garantía de compresión ni incluye exactamente WAL/chunks/series nuevas. Registrar cardinalidad, tamaño real y carga del host en piloto local. Para S series, bloques aproximados a 1–3 bytes/muestra son S×86400×[1,3] bytes/día, más índice, WAL, head y retención; CPU depende de cardinalidad/exportadores/IO y no se inventa un consumo numérico.

## Identidad y disponibilidad

El ID Docker completo de 64 caracteres viene del snapshot de Fase 4. Se contrasta con inspect seleccionado: proyecto, servicio, perfil, imagen/id, cuota/periodo/memoria, StartedAt y RestartCount. Nunca se vuelca inspect.Env. Las series se descubren por container_last_seen, cgroup id que termina exactamente en el ID (docker/cgroupfs o systemd scope), etiquetas Compose/perfil y frescura. No basta coincidencia parcial de nombre. Dos series frescas ambiguas bloquean. Series antiguas tras recreación/etiquetado no se usan; si la consulta de rango sigue siendo ambigua se bloquea conservadoramente.

Cambiar perfil recrea el motor y obtiene otro ID; se resuelve de nuevo en cada repetición. Antes/después deben coincidir ID, imagen, perfil, recursos, StartedAt y reinicios. Identidad alterada invalida la medición; un OOM positivo puede conservarse aun si el motor murió. El preflight definitivo exige también los tres servicios de monitoreo Docker identificados por proyecto/servicio, imágenes fijadas y configuración sin privilegios extra. El endpoint binario nativo usado en Cloud es solo piloto.

/api/v1/targets debe devolver exactamente un target UP reciente por job, sin lastError y con intervalo 1s. Se verifican versiones reales de Prometheus/cAdvisor/Node Exporter, configuración efectiva de retención, series no vacías, finitas y recientes. HTTP 200 no implica medición: vacío, NaN, duplicados, ambigüedad, target DOWN y desfase bloquean. Node Exporter debe coincidir con nodename/kernel/boot_epoch del Linux observado por el runner; en Cloud ese Linux es anidado, no el Kubuntu físico.

## Métricas y PromQL

| Fuente | Métrica | Tratamiento |
| --- | --- | --- |
| cAdvisor | container_cpu_cfs_throttled_seconds_total | Obligatoria; delta de muestras dentro de ventana |
| cAdvisor | container_memory_rss | Obligatoria; máximo observado, bytes a MB decimales |
| cAdvisor | container_cpu_usage_seconds_total | Diagnóstico; no es throttling |
| cAdvisor | container_cpu_cfs_throttled_periods_total | Diagnóstico; no es segundos |
| cAdvisor | container_memory_usage_bytes / container_memory_working_set_bytes | Diagnóstico; no sustituyen RSS |
| cAdvisor | container_memory_failcnt | Disponibilidad comprobada; no demuestra OOM kill |
| Node Exporter | node_cpu_seconds_total, node_memory_MemAvailable_bytes | Solo host |
| Node Exporter | node_disk_read_bytes_total / node_disk_written_bytes_total / node_disk_reads_completed_total / node_disk_writes_completed_total | Solo host/IO; no atribución automática al motor |
| Node Exporter | node_vmstat_pswpin / node_vmstat_pswpout, node_uname_info, node_boot_time_seconds | Swap/identidad del host |
| Docker / motor | OOM y spill | Evidencia específica descrita debajo |

P p.3 enumera container_memory_rss_bytes; el nombre real de cAdvisor 0.60.6 es **container_memory_rss** con unidad bytes, corroborado en documentación/versiones y scraping Cloud. Se registra la diferencia de nombre sin cambiar la columna max_rss_mb ni reemplazar la magnitud. Catálogo por métrica en evidencia identifica ausentes, incluso si son opcionales. En Cloud las siete métricas de cAdvisor de la tabla estuvieron disponibles; errores de filesystem por permisos VFS impidieron algunas estadísticas auxiliares, no estas métricas. No se amplió privilegio para suprimirlos.

Ejemplos conceptuales, no resultados:

```promql
container_last_seen{job="cadvisor"}
container_cpu_cfs_throttled_seconds_total{job="cadvisor",id="/docker/ID_COMPLETO"}[306000ms]
container_memory_rss{job="cadvisor",id="/docker/ID_COMPLETO"}[306000ms]
node_memory_MemAvailable_bytes{job="node"}
```

El código construye selectores con escaping JSON, ID validado y rangos enteros en ms (no sintaxis inválida 10.0s). Usa query instantánea con selector de rango para obtener muestras originales; query_range con step podría reutilizar valores por lookback. No promedia percentiles del runner ni calcula latencia a partir de Prometheus.

## Throttling y RSS

Se seleccionan muestras cuyo timestamp está dentro de [inicio,fin]. Deben existir al menos dos, con cobertura de bordes y separaciones no mayores a 2.5s. Contadores negativos/decrecientes invalidan delta: no se oculta un reinicio usando increase(). cpu_throttled_seconds = último contador − primero, en segundos ya provistos por cAdvisor. **Representa el subintervalo observado entre esas dos muestras**, no un incremento exacto en ambos bordes continuos de los 300s: se conservan first/last/covered_seconds, muestras y método. No incluye warmup/cooldown. increase() extrapolaría a bordes y trataría resets de otro modo; por eso no se presenta como idéntico ni se usa silenciosamente.

cpu.stat.throttled_usec/1000000 antes/después se conserva como contraste opcional separado: sus snapshots envuelven aproximadamente la ventana y no reemplazan ni deben igualar forzosamente el delta Prometheus. nr_throttled no se exporta como tiempo.

max_rss_mb = max(container_memory_rss dentro de ventana)/1000000. Se elige MB decimal explícitamente como propuesta P-38, no MiB implícito. Es máximo **observado** con scraping/housekeeping 1s, no pico instantáneo absoluto. memory.current, working set, memoria total y RSS del runner no son sustitutos. Ausente no se convierte en 0. Un contador constante o RSS realmente cero solo produce cero si existen muestras válidas que lo respaldan.

## Relojes y límites

El runner conserva el protocolo 60/300/60 y la inclusión de operaciones definida en docs/12. Entrega al proveedor inicio/fin monotónicos y epoch_ns del inicio, calculado con el par de relojes. El fin epoch se deriva sumando duración monotónica; nunca se envía monotonic_ns a Prometheus como Unix time. Durante medición se contrasta el offset epoch−monotonic sin peticiones HTTP pesadas; cambio >100ms o incertidumbre de lectura >10ms invalida la asociación. Prometheus time() debe quedar dentro del intervalo de petición local con margen de 100ms; targets/series deben ser recientes.

Al finalizar consultas y cooldown se consulta un rango que rodea la ventana; se guardan únicamente los valores calculados dentro de ella, conservando respuesta cruda y offset. El retraso de consulta no extiende la ventana. No se interpolan picos ni se rellenan gaps. Incluso un salto de reloj observado al finalizar se trata conservadoramente como invalidez. El muestreo no puede atribuir todo incremento o pico al nanosegundo exacto; esta limitación sigue pendiente de aceptación metodológica, sin ocultarla como precisión continua.

## OOM

Antes de preparar clientes se abre docker events continuo filtrado por ID completo, con journal SQLite y timestamps timeNano. OOM confirmado requiere evento oom dentro de la ventana epoch exacta; ausencia solo se declara false cuando el stream estuvo activo/cubrió la ventana y no hubo cambio de identidad/lifecycle. Stream caído, reinicio, die sin oom o información insuficiente producen null. memory.events.oom_kill directo es contraste adicional cuando está accesible; failcnt, memoria al límite, fallo de malloc, error de consulta o exit137 no equivalen a OOM kill.

Docker State.OOMKilled nuevo observado al finalizar se registra como evidencia de **intento**, incluso si ocurrió fuera de la ventana medida, y status=oom excluido del análisis final. No atribuirle causalidad a una consulta o instante que no se conoce. Eventos/journal/estado/ventana quedan ligados al intento. No se provocó OOM real; casos positivos del detector son unitarios simulados y están etiquetados.

## Spill: tres estados internos

Mapping: confirmed → true/CSV 1; not_detected mediante mecanismo válido → false/CSV 0; insufficient → null/CSV vacío. Nunca inferir por latencia ni por allowDiskUse=true. EXPLAIN de Fase 3 es diagnóstico auxiliar separado: una ejecución nueva no prueba spill de las consultas cronometradas anteriores.

**PostgreSQL:** con MONITORING_SPILL_CAPTURE=true, cada sesión exclusiva fija log_temp_files=0 antes de medir y verifica ajuste, backend_pid, prefijo `%m [%p] `, timezone UTC/Etc/UTC/GMT, logging_collector=off y destino stderr/mensajes en inglés o C. No hay cambio de GUC global; al cerrar la conexión se descarta el ajuste. Hace falta permiso SET para ese parámetro, que no se otorga automáticamente al ejecutar benchmarks. La integración Cloud creó un rol nuevo de prueba y le concedió solo ese permiso y SELECT; no cambió otros roles ni configuraciones globales.

Un stream Docker logs json-file bloqueante, iniciado antes de warmup y cerrado después de drenar, conserva solo eventos de archivo temporal: timestamp, PID y tamaño; no vuelca SQL ni credenciales. Se cruzan con los intervalos reales de operaciones measurement exitosas enteramente incluidas. La precisión milisegundo del prefijo permite únicamente 1ms de tolerancia explícita de asociación. Eventos de otros backends o warmup no se atribuyen. Líneas temporales no parseables, stream interrumpido o eventos no atribuibles dentro de ventana dejan unknown. Un cero solo se obtiene con logging verificado en todas las sesiones, stream completo y operaciones incluidas, sin archivos detectados. Es evidencia del mecanismo de temporales, no conteo global de pg_stat_database ni un EXPLAIN posterior. El logging añade trabajo/IO al camino de la consulta que derrama; su sobrecarga debe declararse y evaluarse localmente.

**MongoDB:** activación explícita y acotada de profiling nivel 1 en la base del experimento, con filtro exclusivo command.comment.benchmark_token. Se rechaza profiling ya activo y se guarda el estado de restauración antes de modificarlo. No se cambia slowms/sampleRate global. Cada aggregate original lleva comment con token/cliente/fase/secuencia; no cambia pipeline ni allowDiskUse. Hay canario original fuera de medición: sin usedDisk booleano explícito, strict no avanza a warmup/medición. Se leen registros reales system.profile y se comparan tags contra las operaciones incluidas; Solo se leen entradas command.aggregate=orders: getMore no debe sobrescribir la evidencia de la agregación. usedDisk:true confirma, false explícito con cobertura completa permite 0, campos ausentes o pérdida por colección capped producen unknown. No se interpreta omisión como false.

Profiling añade escritura/CPU al motor, no es instrumentación gratis. Se restaura nivel/filtro anterior en finally/cancelación normal, comprobando que no hubo cambio externo antes de sobrescribirlo. Un SIGKILL o pérdida de host puede impedir restauración: mongo-profile-restore.json registra database/token/estado previo para intervención explícita. Consultar getProfilingStatus y verificar filtro/token antes de restaurar el nivel/filtro de ese archivo; no apagar profiling de otra tarea ni borrar system.profile. No se implementa una limpieza destructiva. Esta ruta está probada unitariamente con cliente simulado, **no con Mongo real**; su integración y compatibilidad de usedDisk siguen pendientes. Si no existe una señal explícita suficiente, el definitivo bloquea o invalida la fila; no se presume cobertura.

## Integración, evidencia y errores

make_telemetry en benchmark/telemetry.py sigue siendo fábrica única. Con .env.monitoring o MONITORING_PROMETHEUS_URL configurado construye ExperimentalTelemetry con snapshot/escenario/protocolo; sin ello conserva el fallback limitado de Fase 4, incapaz de completar métricas obligatorias. El preflight guarda probe/identidades/catálogo/targets; prepare inicia evidencia antes de clientes, configure_client activa instrumentación fuera del timer, clients_ready valida sesiones reales, set_window recibe ambos relojes, start/sample/stop registran límites y finish consulta/agrega/restaura después del cooldown. No se duplica protocolo ni runner. La confirmación temprana fija que el dataset definitivo tenga 500000 y que targets existan; cada repetición conserva todos los gates de datos/consultas/índices/perfil más telemetría. No se deshabilitó el preflight de Fase 4.

Se modificaron de forma acotada benchmark/telemetry.py, runner.py, workers.py, cli.py, preflight.py, config.py y versión a 1.1.0-provisional, además de queries/native.py. Motivos: hooks de ciclo, tag en diario, ajuste por sesión/aggregate comment, reloj y configuración/hash de monitoreo. results.py, metrics.py y SQL/pipelines permanecen intactos. Regresión de datos/consultas/runner/CSV/recuperación y pruebas nuevas documentadas en handoff. Los hashes incluyen observability/ y config/monitoring/; cambiar código/config/dataset/versiones impide reanudar mezclando protocolos, conservando originales.

telemetry-evidence.json, journals docker-events/engine-logs, muestras/API PromQL, snapshots de identidad, clocks y profiler se incluyen en los hashes de commit de Fase 4. La fila mantiene exactamente las 14 columnas. Falta de cualquier KPI/oom, gap, error de integridad o ventana incompleta produce error/oom y no elegibilidad. Pilotos jamás son eligible_for_final_analysis aunque status=ok y sus campos sean reales. Los errores no se reparan con ceros ni reintentos ocultos. Reanudar respeta commits ya finalizados, incluso error; repetir deliberadamente requiere nuevo experimento identificado.

## Uso local y scripts

Instalar Docker Engine/Compose y verificar Kubuntu/cgroups v2 según [docs/09](09-instalacion-kubuntu.md). Preparar datos/consultas y venv con requirements-benchmark.txt según [docs/10](10-generacion-y-carga-datos.md), [docs/11](11-consultas-y-validacion.md) y [docs/12](12-automatizacion-benchmarks.md). Esta fase no añade librerías Python obligatorias a las ya fijadas; cliente Prometheus usa stdlib.

```bash
cp config/monitoring/monitoring.env.example .env.monitoring
# Editar conscientemente: MONITORING_ACCEPT_HOST_ACCESS=true y, si se acepta instrumentación, MONITORING_SPILL_CAPTURE=true.
# Ajustar DockerRootDir, puerto/URL, retención y espacio según el host real.
./scripts/monitoring.sh config
./scripts/monitoring.sh validate
./scripts/monitoring.sh start
./scripts/monitoring.sh health
./scripts/monitoring.sh targets
./scripts/monitoring.sh storage
```

validate usa promtool de la imagen fijada; opcional MONITORING_PROMTOOL=/ruta/al/promtool de la misma versión permite validación local sin descargar otra imagen. No modifica instalación global. El .env de motores sigue separado; no se solicitan ni guardan credenciales en el respaldo. Health/targets no verifican por sí solos el contenedor evaluado:

```bash
./scripts/monitoring.sh diagnose --container-id ID_COMPLETO
./scripts/monitoring.sh query --container-id ID_COMPLETO --seconds 10
./scripts/monitoring.sh export --container-id ID_COMPLETO --seconds 10 --output results/diagnostico-nuevo.json
```

Las consultas de diagnóstico son ventanas observadas, no nuevas consultas de base ni resultados de una repetición inexistente. No sobrescriben una salida existente. Para piloto real, con dataset ya cargado e idéntico, usar la entrada de Fase 4:

```bash
./scripts/run_benchmarks.sh run --matrix single --mode pilot --engine postgres --profile severe \
  --query Q2 --variant work_mem_4mb --concurrency 1 --run-number 1 \
  --file data/orders.jsonl --output results --experiment piloto-telemetria \
  --warmup 2 --measurement 5 --cooldown 2 --cache skip --execute-selected
```

Con un solo motor de pruebas ya preparado se admite --use-existing-services, exclusivamente piloto y con desviaciones registradas. Duraciones menores a dos intervalos de scraping pueden no tener muestras suficientes y quedan incompletas; no reducir gates para hacerlas pasar. --resume conserva resultados y exige misma configuración. Definitivos siguen sin autorización de ejecución y requieren todos los gates: 500000 equivalentes en ambos, consultas/variantes/índices conformes, perfil/ancestros, imágenes/host correctos, telemetría completa y caché autorizada. Mongo/Kubuntu y decisiones pendientes siguen visibles; esta fase no los aprueba.

```bash
./scripts/monitoring.sh stop
```

Detiene solo prometheus/cadvisor/node-exporter de su proyecto; no detiene motores, borra volúmenes ni elimina TSDB histórico. No hay prune/down -v ni cambios de kernel.

## Pruebas, compatibilidad y límites pendientes

Unitarias: construcción PromQL/ID, muestras/deltas/resets/MB, targets DOWN/stale, errores HTTP/200 vacío, nanosegundos/clock drift, OOM, spill PG/Mongo y restauración/CAS de profiler, hooks/CSV/manifiestos/resume/cancelación. Fixtures simulados solo prueban lógica en temporales y no se entregan como mediciones reales.

```bash
.local/benchmark-venv/bin/python -m unittest discover -s tests -v
./tests/test_infrastructure.sh
./scripts/monitoring.sh validate
```

Integración opt-in: RUN_MONITORING_INTEGRATION=1, MONITORING_PROMETHEUS_URL local, MONITORING_SPILL_CAPTURE=true, DATA_PG_CONTAINER completo y DATA_DATABASE_NAME de la base administrativa de pruebas. tests/test_observability_integration.py verifica targets/series/identidad, crea base/rol aislados nuevos conservados, importa 100 órdenes y ejecuta Q2 4MB con piloto 1/4/1s, recoge CPU/RSS/OOM/spill y reanuda sin duplicar. MONITORING_EVIDENCE_DIR opcional conserva evidencia real; no habilitar sobre un servidor ajeno. No se provoca spill/OOM para obtener positivos. Integración Mongo no ejecutada.

Problemas frecuentes: imagen distroless sin wget (usar targets reales), puerto local ocupado, DockerRootDir incorrecto, Docker rootless/socket distinto no soportado por scripts originales, montajes insuficientes, métricas cgroups v2 ausentes, cadvisor reiniciado/series históricas ambiguas, reloj o host distintos, scrape>800ms, logging PG/prefijo/permiso incorrectos, profiler activo/capped sin cobertura y disco insuficiente. Solución: conservar diagnóstico y corregir causa; no ampliar privilegios, rellenar nulos, bajar concurrencia/frecuencia ni ejecutar otro EXPLAIN para fabricar atribución.

Tras stop se observó exit2 en Node Exporter, sin OOM ni error de estado y sin causa confirmada en logs; no se afirma apagado limpio. El scraping previo sí fue válido. Revisar el cierre en Kubuntu y conservar cleanup-state.json.

Pendiente físico: versión Kubuntu, pila completa Docker con TSDB persistente/healthcheck Prometheus, ambos motores/perfiles/ancestros, scrape y reloj bajo carga 1/10/50, capacidad/retención y sobrecarga de monitoreo, Mongo real/usedDisk/profiler/Decimal128/equivalencia, 500000, OOM/spill positivos reales si ocurren y aceptación de políticas muestreadas/MB/caché/alias/índice. No es necesario forzar eventos para cerrar desarrollo; la validación experimental permanece parcial. Detenerse antes de Fase 6.

## Referencias técnicas consultadas

- [Prometheus v3.15.1](https://github.com/prometheus/prometheus/releases/tag/v3.15.1), [configuración](https://prometheus.io/docs/prometheus/latest/configuration/configuration/), [API](https://prometheus.io/docs/prometheus/latest/querying/api/), [almacenamiento](https://prometheus.io/docs/prometheus/latest/storage/).
- [cAdvisor v0.60.6](https://github.com/google/cadvisor/releases/tag/v0.60.6), [catálogo versionado](https://github.com/google/cadvisor/blob/v0.60.6/docs/storage/prometheus.md), [permisos de ejecución](https://github.com/google/cadvisor/blob/v0.60.6/docs/running.md); flags y nombres además comprobados en imagen real.
- [Node Exporter v1.12.1](https://github.com/prometheus/node_exporter/releases/tag/v1.12.1), [montajes de host](https://github.com/prometheus/node_exporter#using-docker).
- [PostgreSQL 18 logging](https://www.postgresql.org/docs/18/runtime-config-logging.html), [Mongo setProfilingLevel](https://www.mongodb.com/docs/manual/reference/method/db.setProfilingLevel/), [campos de profiler](https://www.mongodb.com/docs/manual/reference/database-profiler/).

Estas fuentes técnicas no reemplazan los requisitos P/S ni certifican compatibilidad física no probada.


## Continuidad posterior — U8

La prohibición de implementar Fase 6 que figura en el cierre histórico anterior fue reemplazada por U8. El análisis offline/reportes ya está implementado en [guía de análisis](14-analisis-y-reporte.md), sin sustituir runner, protocolo, consultas ni telemetría. No hay autorización de Fase 7 ni mediciones definitivas; pendientes físicos/académicos conservados.
