# Automatización de benchmarks — Fase 4

Implementación autorizada por U6 (solicitud Fase 4), con validación parcial en Cloud al 2026-11-01. Fuentes normativas: P p.3 §§6–7 y p.4 §§8.1–8.2; S pp.7–10,13; [requisitos](01-requisitos-y-trazabilidad.md) REQ-008–015, 064–074. Los métodos que esos documentos no definen son propuestas operativas, no decisiones académicas aprobadas. Fase 5 no se implementa aquí.

## Arquitectura e interfaces

`benchmark_runner` llama a benchmark/cli.py; scripts/run_benchmarks.sh es la entrada Bash y reutiliza common.sh. matrix.py construye escenarios; config.py valida protocolo y hashes; preflight.py verifica datos/consultas/índices; environment.py y scripts/benchmark_environment.sh reutilizan inicio/verificación de infraestructura; runner.py coordina workers.py y timing.py; metrics.py agrega; telemetry.py define proveedores; results.py escribe/manifiesta/reanuda/consolida; cache.py gestiona la constancia manual.

Única adaptación de código preexistente: `QueryExecutor.open_session()` en queries/execution.py abre queries/native.py. No cambia execute(), SQL, pipelines, variantes ni validadores de Fase 3. El transporte anterior docker exec/mongosh/psql sirve para preflight y corrección, pero crearía procesos/conexiones por operación si se usara en la ventana medida. NativeSession mantiene conexiones reales con psycopg/PyMongo y reutiliza exactamente QuerySpec.sql/pipeline/options. La regresión de Fases 2/3 y las pruebas nativas comprueban la adaptación. Generador, importadores, Compose, imágenes, límites e índices anteriores permanecen intactos.

Dependencias fijadas en requirements-benchmark.txt: psycopg/psycopg-binary 3.3.6, pymongo 4.19.0, dnspython 2.9.1 y typing_extensions 4.16.0. Se instalaron en un venv temporal Python 3.12 de Cloud; no son nuevas versiones de motores. Las imágenes siguen siendo las propuestas de Fase 1. Registrar versiones efectivas; no se certifica compatibilidad física Kubuntu por instalarlas en Cloud.

## Matriz y selección

| Modo | Celdas sin repetición | Repeticiones | Variantes Q2 |
| --- | --- | --- | --- |
| base | 36 | 108 | Una explícita por motor; otra omitida y registrada |
| extended | 54 | 162 | Ambas por motor |
| single | 1 | 1 | Una explícita para Q2; default para Q1 |

Mongo: allow_disk_false / allow_disk_true. PostgreSQL: work_mem_4mb / work_mem_64mb. Los IDs de perfil oficiales se conservan en CSV; CLI admite baseline, medium y severe. Filtros --engine, --profile, --query, --variant, --concurrency y --run-number reducen el plan y su conteo visible. Base exige --base-mongo-variant y --base-postgres-variant aun si se filtra un motor, para no esconder la elección original. No suma otra modalidad Q2 a las dos extendidas.

P-02 continúa OPEN: capacidad de planificar 162 no equivale a aprobación del cruce académico. S p.7 pide ambas variantes y P p.3 declara 108; el reporte deberá explicar el alcance autorizado. Orden actual determinista: motor, perfil, consulta, variante, concurrencia y repetición según el catálogo; no es balanceo aleatorio aprobado (P-08). Duración nominal 12h36 para 108 y 18h54 para 162, sin preflight/drenaje/caché/fallos.

## Clientes y protocolo

Un hilo por cliente, con sesión propia; se conservan exactamente 1/10/50 clientes. U6 §6 permite threading aunque P p.4 menciona Python multiproceso: se elige por I/O de bases, sin compartir sesiones ni pagar IPC por operación. El GIL, decodificación y escritura local pueden limitar el runner; la prueba simulada verifica concurrencia lógica, no capacidad física de 50 clientes. Registrar CPU del runner y revisar saturación local antes de conclusiones. El runner vive fuera de los cgroups de motores; no dispone de una reserva CPU garantizada.

Cada cliente abre/verifica versión y variante, ejecuta una comprobación contra el oráculo fuera de medición y espera la coordinación común. Pool Mongo privado de tamaño máximo 1, sin retryReads/retryWrites; PG conexión dedicada sin prepared statements automáticos ni reutilización entre escenarios. PG fija work_mem, UTC, statement_timeout y modo lectura en esa misma sesión, comprueba work_mem antes/después y cierra. Esto sustituye SET LOCAL de la CLI de corrección por una sesión exclusiva descartada: no cambia configuración global ni contamina otra conexión. Mongo pasa allowDiskUse como opción aggregate y maxTimeMS, jamás como etapa. Ambos consumen completamente las respuestas, descartándolas después de contarlas.

Etapas por intento:

1. Preflight: archivo/manifiesto íntegro, lectura completa del dataset del motor seleccionado y oráculo, índice, salud y recursos reales, espacio y drivers. En modo estricto se prepara comprobación de ambos motores, 500000 y todas las consultas/variantes; requiere equivalencia real, no recibos viejos.
2. Clientes preparados y comprobados; constancia de caché u omisión registrada.
3. Warmup de 60 s; después drenar consultas en vuelo. Sus operaciones nunca entran en percentiles/QPS.
4. Ventana común de 300 s con reloj monotónico en nanosegundos.
5. Drenar consultas en vuelo, verificar/cerrar sesiones y conservar registros.
6. Cooldown de 60 s sin carga; agregación y finalización inmutable después.

Tiempos reducidos solo en pilot (test es interno, no opción CLI). definitive exige exactamente 60/300/60 y caché manual. Un timeout o fallo individual cancela la repetición completa, sin reducir clientes ni reintentar silenciosamente. El timeout predeterminado de 120000 ms es provisional/parametrizable y queda en manifiesto, no exigencia del manual. Cada operación tiene timeout; la preparación/cierre tiene un plazo adicional acotado. Un hilo que no termine deja el intento incompleto y detiene la orquestación. SIGINT/SIGTERM cancelan, cierran conexiones y conservan motivo; no generan commit ni fila definitiva. Una muerte abrupta se reconoce por started.json sin commit, aunque no permita conocer la señal exacta.

## Caché y seguridad

El literal de P p.3 es `sync; echo 3 >/proc/sys/vm/drop_caches`. El programa nunca ejecuta esa operación, sudo, escrituras privilegiadas ni contenedores privilegiados. --cache skip es solo piloto y queda como desviación, sin equivalencia al protocolo. --cache manual espera en TTY la constancia `CACHE_CLEARED <id-del-intento>` después de preparar clientes; la persona debe realizar por separado únicamente el procedimiento autorizado en su host. Se conserva la constancia fuera del CSV. Es declaración del operador, no prueba del estado de caché ni autorización académica de P-07; no garantiza vaciar buffers internos.

El camino normal llama start_services.sh y verify_resources.sh para aplicar perfil y verificar hoja/ancestros; no basta exportar variables. Antes de medir detiene solo el otro motor del proyecto para reducir interferencia, conservando volúmenes. Las comprobaciones de equivalencia se hacen antes del aislamiento. --use-existing-services omite esa gestión solo en piloto: exige salud y límites efectivos del motor elegido, y registra aislamiento/ancestros incompletos. El verificador puede rechazar baseline Cloud por cuota padre insuficiente. No se borra ni reinicia ningún dato, ni se instalan paquetes automáticamente.

## Latencias, QPS y bordes

La operación incluida cumple inicio >= inicio de medición, inicio < fin y terminación <= fin. Se mide desde antes de enviar la consulta hasta consumir toda la respuesta, con monotonic_ns; creación de conexión, SET/SHOW, preflight, diario y apagado quedan fuera. Las que cruzan el fin se drenan pero se excluyen tanto de QPS como de latencias; se cuenta excluded_boundary. La igualdad exacta de terminación con fin se admite. La ventana usa el mismo reloj para todos los hilos. No se incluyen operaciones del cooldown.

QPS = éxitos incluidos / duración fija de medición. Fallos se registran aparte; nunca cuentan como éxitos. Si la ventana queda incompleta, QPS y percentiles oficiales quedan vacíos y status=error/oom; las operaciones crudas se conservan. Una ventana completa sin éxitos tiene QPS=0 observado, percentiles ausentes y status=error.

Cada hilo escribe operaciones (fase, inicio, fin, resultado, clase de error) en SQLite propio, con caché de 2 MiB y commit cada 64 operaciones/finalización. No retiene respuestas ni una lista ilimitada de latencias. El agregador transmite lecturas a metrics.sqlite, ordena en disco y calcula cuantiles exactos Hyndman–Fan tipo 7: h=(n−1)p, interpolación lineal entre índices floor(h) y ceil(h), luego ns/1000000 con Decimal. Sin histogramas aproximados, float de importes ni redondeo prematuro. sample count y exclusiones quedan en JSON. Los diarios crecen en disco según operaciones; se requiere espacio libre (umbral inicial 256 MiB, no garantía para matriz completa) y vigilar carga de escritura/saturación del runner. Caída antes del flush puede perder operaciones de un intento incompleto, que jamás se considera finalizado.

## Telemetría y estados

La fábrica make_telemetry es el punto único de conexión de proveedores; la interfaz capabilities/start/sample/stop/unavailable permite proveedores futuros sin modificar las consultas. CgroupTelemetry solo lee rutas cgroups v2 accesibles del host local: delta de cpu.stat.throttled_usec dividido por 1e6, y delta de memory.events.oom_kill. Guarda snapshots y tiempos; contadores ausentes/reiniciados producen null. No confunde eventos/períodos con segundos. Las lecturas envuelven aproximadamente la ventana, incluyendo la breve coordinación inicial y demora final observables en snapshots: no afirmar alineación perfecta. Hace falta contrastar/sincronizar en Fase 5.

max_rss_mb y disk_spill permanecen ausentes: memory.current, memory.stat anon, working set y RSS del runner NO sustituyen RSS del contenedor. No hay detector fiable de spill en esta fase; allowDiskUse=true no prueba spill, ni latencia alta tampoco. El adaptador ausente devuelve null, nunca cero. El máximo RSS/CPU propio del runner es diagnóstico separado y tiene alcance de proceso/intento, no columna oficial.

OOM positivo puede respaldarse por incremento oom_kill durante las lecturas o Docker State.OOMKilled observado al terminar el intento; se guarda fuente/alcance. Este último no permite atribuir instante exacto ni causalidad a una consulta. Exit 137 solo no basta. Sin observabilidad no se afirma OOM=false. No se provocó OOM real ni spill para pruebas.

Precedencia propuesta: oom positivo → oom; fallo, ventana incompleta, cero muestras o telemetría obligatoria ausente → error; spill positivo con todo lo necesario → spill; de otro modo ok. Las clases conexión/timeout/consulta/configuración/cancelación y métricas faltantes quedan en evidencia. No se añaden estados al CSV. BLOCKED es diagnóstico de preflight, sin fila de medición para escenario no ejecutado. No hay reintentos automáticos; un intento finalizado con error queda registrado y no se vuelve a ejecutar por --resume.

**Antecedente del cierre de Fase 4: la ejecución definitiva quedó bloqueada intencionalmente en esa entrega**, antes de activar servicios/caché, porque no hay proveedor completo de RSS/spill y telemetría. No hay --force. Además siguen pendientes Mongo real, equivalencia, índice PG y aprobaciones históricas. U7 autorizó después Fase 5: reemplazó el bloqueo fijo por comprobaciones reales del proveedor y preservó los demás gates; consultar docs/13. No basta eliminar una puerta ni aprobar metodologías por inferencia. Preparar el protocolo estricto no significa que sus condiciones ya se cumplan.

## CSV y manifiestos

Cabecera exacta (P p.4 §8.2):

```text
timestamp_epoch,engine,profile,query_id,concurrency,run_number,throughput_qps,latency_p50_ms,latency_p95_ms,latency_p99_ms,cpu_throttled_seconds,max_rss_mb,disk_spill,status
```

Una fila por repetición finalizada; una cabecera por archivo. engine=mongo/postgres, profile=PROFILE_A_BASELINE/PROFILE_B_MEDIUM/PROFILE_C_SEVERE, query_id=Q1/Q2, concurrencia/repetición enteras. timestamp_epoch es frontera de medición; si nunca se llegó, es finalización del intento, con timestamp_scope explícito en JSON. Booleano spill se codifica 0/1, ausencia celda vacía; nulos de métricas no se sustituyen por 0. Estas convenciones operativas siguen propuestas (P-10/P-32).

Cada experimento guarda experiment.json: UUID/fecha, protocolo/plan, versión/hashes del runner/consultas, identidad/hash/configuración del dataset, drivers, imágenes/id y versiones observadas, host/kernel/boot/CPU/memoria observados. Cada intento guarda started.json, preflight.json (recursos verificados frente a solicitados, dataset real, variantes e índices), diarios, metrics.sqlite, result.json, results.csv y commit.json con hashes. Una invocación registra reanudación e intentos incompletos. Nunca se vuelca inspect.Env, DSN ni contraseña.

La clave id del escenario incluye motor/perfil/consulta/variante/concurrencia/repetición; UUID de experimento distingue ejecuciones y dataset. Como variant no existe en CSV, cada CSV de intento lleva result.json con variante/id y hash de fila. Para unir resultados usar consolidate: genera CSV intacto y .manifest.json con ordinal/hash de cada fila, variante, id de escenario/experimento e identidad de motores. Un CSV suelto concatenado con cat pierde trazabilidad y no se admite como consolidación auditada. Colisiones/duplicados ambiguos se rechazan.

Los archivos se instalan exclusivamente mediante escritura temporal propia, fsync y enlace atómico sin sobrescritura, con lock fcntl por experimento. commit.json es el punto de finalización; una fila sin commit no prueba éxito. Un fallo entre escrituras deja evidencia incompleta conservada. La consolidación requiere CSV y manifiesto juntos; no usar una salida que quedó sin su manifiesto.

## Reanudación

Repetir el comando original con --resume y el mismo --experiment/--output. Exige misma configuración, dataset/hash, fuentes, drivers, imagen/versión, protocolo, host/boot y selección. No mezcla cambios de perfil ni variantes. Verifica hashes de todo archivo confirmado, cabecera, tipos, identificador/variante y ausencia de duplicados. CSV confirmado corrupto bloquea y se preserva para revisión; no se repara silenciosamente. Un started sin commit se conserva, se clasifica su CSV parcial y se crea otro attempt UUID. La consolidación reconoce el intento posterior confirmado, conservando el historial incompleto. Una repetición con error ya confirmada se omite en resume y el resultado global sigue siendo error; repetirla deliberadamente requiere un experimento nuevo identificado, sin borrar el anterior.

consolidate rechaza planes sin finalizar, intentos todavía sin resolver, datasets/protocolos/fuentes incompatibles, versiones distintas de un mismo motor y filas duplicadas. Pilotos/test/definitivos no se mezclan incluso con --allow-nonfinal; por defecto además exige eligible_for_final_analysis=true en todas las filas. --allow-nonfinal es salida diagnóstica explícita, nunca resultados académicos.

## Uso en Kubuntu

Preparar primero [infraestructura](09-instalacion-kubuntu.md), [datos](10-generacion-y-carga-datos.md) y [consultas](11-consultas-y-validacion.md). Crear el .env local según .env.example sin incorporarlo al respaldo. No copiar contraseñas en comandos/manifiestos. Instalación explícita por el usuario, sin privilegios:

```bash
python3 -m venv .local/benchmark-venv
.local/benchmark-venv/bin/python -m pip install -r requirements-benchmark.txt
export BENCHMARK_PYTHON="$PWD/.local/benchmark-venv/bin/python"
./scripts/run_benchmarks.sh --help
./scripts/run_benchmarks.sh plan --matrix base --base-mongo-variant allow_disk_false --base-postgres-variant work_mem_4mb
./scripts/run_benchmarks.sh plan --matrix extended
./scripts/run_benchmarks.sh plan --matrix extended --engine postgres --profile severe --query Q2 --variant work_mem_64mb
```

Los comandos plan no requieren motores ni empiezan mediciones. Un piloto real, con archivo existente e importado idéntico, por ejemplo:

```bash
./scripts/run_benchmarks.sh run --matrix single --mode pilot --engine postgres --profile severe \
  --query Q2 --variant work_mem_4mb --concurrency 1 --run-number 1 \
  --file data/orders.jsonl --output results --experiment pilot-pg-q2 \
  --warmup 2 --measurement 5 --cooldown 2 --cache skip --execute-selected
```

El camino normal gestiona ambos servicios del proyecto; requiere suficiente espacio y la aceptación explícita de adaptación swap de Fase 1. Solo si ya hay un motor de prueba preparado, añadir --use-existing-services para evitar gestión de servicios y registrar esa desviación. No es modo definitivo. El proceso retorna 1 si midió pero status=error por telemetría ausente; eso es esperado en Fase 4 y no es PASS académico. Códigos: 0 plan/éxito completo, 1 repetición finalizada con error/oom, 2 bloqueo de configuración/preflight, 130 cancelación. Bash puede devolver 1 antes de Python por prerrequisitos ausentes.

Ejemplo de solicitud definitiva, actualmente bloqueada (no ejecutarla para obtener resultados en Cloud):

```bash
./scripts/run_benchmarks.sh run --matrix base --mode definitive \
  --base-mongo-variant allow_disk_false --base-postgres-variant work_mem_4mb \
  --file data/orders.jsonl --output results --experiment estudio-base \
  --cache manual --execute-selected --confirm-matrix
```

Nunca hay matriz por omisión; más de una repetición exige --confirm-matrix. La extendida usa --matrix extended y conserva la advertencia de falta de aprobación. El modo definitivo no acepta duraciones reducidas. Para reanudar se repite el mismo comando con --resume; no editar ni eliminar los originales. Consolidación diagnóstica explícita de pilotos finalizados compatibles:

```bash
./scripts/run_benchmarks.sh consolidate --inputs results/pilots/pilot-pg-q2 \
  --output results/pilotos-diagnostico.csv --allow-nonfinal
```

## Pruebas, evidencia y errores

```bash
.local/benchmark-venv/bin/python -m unittest discover -s tests -v
bash -n scripts/run_benchmarks.sh scripts/benchmark_environment.sh
./tests/test_infrastructure.sh
```

20 unitarias de runner: matrices, filtros/IDs/variantes, protocolo, tiempos/bordes/QPS/R7, 1/10/50 clientes, errores/cancelación/cierre, Mongo mock (solo interfaz), telemetría faltante/deltas, CSV/locks, corrupción, reanudación y consolidación. Ejecutor y telemetría simulados solo se admiten con mode=test interno; el CLI no permite ese modo. Los tests no guardan resultados ficticios en el proyecto ni los presentan como integración.

Integración real opt-in en tests/test_benchmark_integration.py requiere PG ya activo, drivers y DATA_PG_CONTAINER/DATA_DATABASE_NAME de la infraestructura de pruebas. RUN_BENCHMARK_INTEGRATION=1 habilita una prueba que crea base/rol nuevos de prueba, conserva ambos sin borrar datos previos, genera/importa 100 documentos, valida las tres sesiones PG, prueba conexión rechazada/consulta inválida/timeout y ejecuta un único piloto Q1 reducido con reanudación y bloqueo definitivo. Credencial aleatoria solo temporal, sin respaldo; no usar una base ajena. BENCHMARK_EVIDENCE_DIR opcional conserva CSV/metadatos reales etiquetados. No existe simulación CLI de base de datos.

Evidencia Cloud real en [phase4](evidence/phase4/README.md). El piloto prueba el camino del runner, no rendimiento comparable: duración mínima, datos pequeños, cache omitida, RSS/spill/CPU inaccesibles y perfil de prueba Cloud. Mongo sigue sin integración real por disco; no se afirma validación cruzada ni 50 conexiones reales. La suite completa informa separadamente integraciones omitidas sin opt-in; no contarlas como aprobadas.

Errores comunes: --matrix base sin ambas variantes, Q2 sin variant, falta de .env/drivers/dataset, totals-only para Q2, imagen/versión/dataset alterados al reanudar, hoja cgroup fuera de perfil, ancestros insuficientes, endpoint privado ambiguo/inaccesible, índices académicamente bloqueados, poco espacio, .lock ocupado o CSV corrupto. Resolver la causa y conservar evidencias; no desactivar validaciones para producir filas ok.

Pendiente en Kubuntu: versión de distribución, salud/persistencia/perfiles y ancestros de ambos motores; dataset de 500000 idéntico; integración real Mongo y equivalencia; aceptaciones de alias/tipos/índice/swap/metodología; 1/10/50 conexiones reales, capacidad del runner y disco; autorización y evidencia de caché; RSS/spill/OOM/telemetría sincronizada de Fase 5. Fase 4 IN_PROGRESS: implementada y parcialmente validada, no certificación experimental final. Detenerse aquí; Fase 5 requiere nueva instrucción.

Referencias técnicas de las nuevas dependencias: [psycopg y conexiones](https://www.psycopg.org/psycopg3/docs/basic/usage.html), [configuración de conexiones psycopg](https://www.psycopg.org/psycopg3/docs/api/connections.html), [MongoClient PyMongo](https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html), metadatos de publicación [psycopg 3.3.6](https://pypi.org/pypi/psycopg/3.3.6/json) y [pymongo 4.19.0](https://pypi.org/pypi/pymongo/4.19.0/json). Las versiones se contrastaron con PyPI y la instalación aislada; las referencias no reemplazan P/S ni demuestran compatibilidad Kubuntu/Mongo real.


## Extensión vigente de Fase 5 — U7

[Observabilidad](13-observabilidad-y-telemetria.md) amplía esta guía sin duplicar protocolo. Con .env.monitoring/MONITORING_PROMETHEUS_URL, la fábrica usa ExperimentalTelemetry; prepara fuentes, verifica sesiones y recibe set_window monotónica/epoch. finish después de cooldown obtiene muestras originales, RSS/throttling, eventos OOM y spill real por operación, guarda evidencia/restaura instrumentos y reutiliza el commit/CSV existentes. max RSS es máximo observado, throttling cubre first/last de muestras interiores; bordes/gaps/relojes se declaran. Los antiguos párrafos de telemetría siempre ausente describen exclusivamente Fase 4 sin este proveedor.

La versión del runner pasó a 1.1.0-provisional: hashes incluyen observability/ y config/monitoring/, y configuración de monitoreo forma parte del manifiesto. No reanudar experimentos 1.0 mezclándolos con nuevas fuentes/método. Los originales se preservan. Fallback sin monitoreo sigue incompleto; piloto no es resultado final aun con status=ok. Definitivo exige fuentes/sesiones/series/espacio y stack Docker íntegros, además de 500000/ambos/índices/perfiles/caché; no se ejecutó en Cloud. Fase 6 requiere nueva instrucción.


## Continuidad posterior — U8

La prohibición de implementar Fase 6 que figura en el cierre histórico anterior fue reemplazada por U8. El análisis offline/reportes ya está implementado en [guía de análisis](14-analisis-y-reporte.md), sin sustituir runner, protocolo, consultas ni telemetría. No hay autorización de Fase 7 ni mediciones definitivas; pendientes físicos/académicos conservados.
