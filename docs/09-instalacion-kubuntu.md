# Instalación e infraestructura en Kubuntu nativo

## Alcance y estado

Fase 1 implementada y validada estáticamente; estado BLOCKED para cierre por pruebas de contenedores y equipo físico pendientes. Solo MongoDB y PostgreSQL: no hay dataset, consultas Q1/Q2, runner ni telemetría implementados. Requisitos relevantes: REQ-002, 007, 017–019, 025–026, 028 (índices diferidos), 035 y REQ-041–047. U3 identifica la solicitud de Fase 1; reemplaza Windows/Docker Desktop/WSL2 por Kubuntu nativo sin borrar el antecedente histórico.

Equipo declarado por el usuario: Ryzen 7 5700X, RAM DDR4 32 GB, x86_64, Kubuntu en partición independiente. Versión exacta de Kubuntu/kernel aún sin identificar. No se probaron comandos en ese equipo; no se modifican particiones, arranque ni la instalación de Windows.

## Versiones y fuentes consultadas

Investigación realizada el 2026-11-01; fuentes oficiales:

- [MongoDB release notes](https://www.mongodb.com/docs/manual/release-notes/): identifica 9.0 como serie estable actual.
- [Política PostgreSQL](https://www.postgresql.org/support/versioning/): 18.6 estable soportada; 19 RC no se selecciona.
- [Docker Official Images MongoDB](https://github.com/docker-library/official-images/blob/master/library/mongo) y [PostgreSQL](https://github.com/docker-library/official-images/blob/master/library/postgres): manifiestos consultados, tags linux/amd64 confirmados.
- [Docker Engine en Ubuntu](https://docs.docker.com/engine/install/ubuntu/) y [Compose Plugin](https://docs.docker.com/compose/install/linux/): instalación nativa. Comprobar la versión Ubuntu base antes de elegir repositorio; una derivada no equivale a soporte certificado de todas sus variantes.
- [Recursos Docker](https://docs.docker.com/engine/containers/resource_constraints/), [métricas/cgroups](https://docs.docker.com/engine/containers/runmetrics/), [Compose services](https://docs.docker.com/reference/compose-file/services/) y [controladores cgroups v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).
- [Moby 28.4: cgroup2_linux.go](https://github.com/moby/moby/blob/v28.4.0/pkg/sysinfo/cgroup2_linux.go) marca MemorySwappiness=false; [daemon_unix.go](https://github.com/moby/moby/blob/v28.4.0/daemon/daemon_unix.go) descarta el valor cuando no hay soporte.
- [Imagen oficial postgres y volumen PG18](https://github.com/docker-library/docs/blob/master/postgres/README.md): desde PG18 el volumen se monta en /var/lib/postgresql; no se reutiliza ciegamente la ruta de PG17.

| Componente | Selección propuesta y fijada en configuración | Evidencia / límite |
| --- | --- | --- |
| MongoDB | mongo:9.0.4-resolute | Tag oficial amd64 y pull completo confirmado en Cloud; WiredTiger sin sharding |
| PostgreSQL | postgres:18.6-bookworm | Tag oficial amd64 y pull completo confirmado en Cloud; JSONB nativo |
| Docker Engine | Nativo, versión estable soportada por Ubuntu base | Cloud: 28.4.0; versión local pendiente, no promesa de compatibilidad |
| Compose Plugin | Soporte de up --wait y config --format json | Cloud: 2.40.3 probado en configuración; registrar versión local |

Referencias de imagen fijadas también por digest de manifiesto:

```text
mongo:9.0.4-resolute@sha256:714cc3db1e396e5a464b8443ccde50e53283368809401f53f1997b684ddb5be0
postgres:18.6-bookworm@sha256:5c4783a8cc3f0074912164f94dfa1be4e043438f0f707cf968d7af9a0d31a2c8
```

Los pulls verificaron existencia/digest, no ejecución correcta. Selecciones PROPOSED (P-11): el usuario pidió proponer versiones, no aprobó aún estas concretas para mediciones finales. Cambiar tag requiere cambiar también digest y revalidar volumen/migración; nunca actualizar majors sobre datos existentes automáticamente. Los sistemas base de las imágenes difieren (Ubuntu/Debian): se documenta como condición experimental, no se presume equivalencia interna.

## Requisitos previos y diagnóstico de solo lectura

Linux x86_64, Bash, GNU coreutils, awk/grep/sed y Docker Engine local con Compose Plugin. Python 3 para las pruebas de configuración. MongoDB moderno requiere instrucciones CPU compatibles (comprobar AVX en el host); el hardware declarado no sustituye una prueba. Espacio libre suficiente para imágenes y copias del storage driver, volúmenes y futuro dataset; Cloud agotó su disco de 7.9 GiB y no sirve de estimación de tamaño local.

```bash
./scripts/setup_kubuntu.sh
./scripts/check_environment.sh
cat /etc/os-release
uname -r
lscpu
free -h
df -h
```

El asistente no instala ni modifica nada. Lee VERSION_ID y UBUNTU_CODENAME (o VERSION_CODENAME); si Docker existe, informa y no lo sobrescribe. Inventariar versiones con dpkg-query antes de cambiar paquetes. No mezclar docker.io/podman-docker con docker-ce sin revisar conflictos manualmente.

## Instalación manual de Engine y Compose Plugin

Primero confirmar que la versión Ubuntu base está soportada en la guía enlazada y que no hay una instalación que deba conservarse. La página consultada enumera Ubuntu 22.04, 24.04, 26.04 y 26.10; volver a comprobarlo al instalar. Los siguientes pasos requieren que el usuario los ejecute deliberadamente, con revisión previa; ningún script del proyecto los ejecuta.

1. Si ya hay Docker, evaluar procedencia y compatibilidad, sin desinstalarlo automáticamente.
2. Seguir el método del repositorio apt oficial de Docker: instalar ca-certificates/curl, incorporar clave GPG oficial y repositorio stable correspondiente a la arquitectura y Ubuntu base. No sobrescribir archivos de repositorios existentes sin revisarlos.
3. Revisar versiones disponibles (`apt-cache policy docker-ce docker-compose-plugin`) e instalar explícitamente los paquetes oficiales: docker-ce, docker-ce-cli, containerd.io, docker-buildx-plugin y docker-compose-plugin. Registrar sus versiones exactas para el manifiesto local. Las órdenes con sudo de la guía son acciones manuales, no autorización general para este asistente.
4. Verificar acceso al daemon local. El proyecto no inicia/reinicia el daemon ni agrega usuarios a grupos. El acceso al socket Docker concede capacidades equivalentes a root; cualquier ajuste de permisos debe decidirlo el usuario. No usar chmod 666 sobre el socket. No instalar Docker Desktop ni docker-compose Python legado.

```bash
docker --host=unix:///var/run/docker.sock version
docker --host=unix:///var/run/docker.sock compose version
docker --host=unix:///var/run/docker.sock info --format 'cgroups={{.CgroupVersion}} driver={{.CgroupDriver}}'
cat /sys/fs/cgroup/cgroup.controllers
```

Debe observarse versión cgroups 2 y controladores cpu/memory. La mera existencia de controllers no demuestra delegación al contenedor. Si no se cumple, detener la validación y diagnosticar con documentación del sistema; no cambiar GRUB ni el kernel automáticamente. Los scripts fijan el socket Unix local e ignoran selectores de daemon remoto para evitar actuar sobre otro equipo; rootless y sockets alternativos quedan fuera de la configuración preparada y requieren revisión.

## Preparación de configuración local

```bash
cp .env.example .env
chmod 600 .env
```

Editar .env localmente: configurar contraseñas de desarrollo no vacías, no enviarlas al asistente ni incorporarlas a respaldos. MONGO_USERNAME y POSTGRES_USER son administradores locales de desarrollo; no son una política de roles para producción. Las imágenes inicializan credenciales solo en volúmenes vacíos: cambiar .env no cambia cuentas existentes. Los scripts no borran volúmenes para corregir contraseñas.

| Variable | Propósito / restricción |
| --- | --- |
| PROJECT_NAME | Prefijo de contenedores/red/volúmenes; conservar para reutilizar datos |
| RESOURCE_PROFILE | baseline, medium o severe cuando no hay argumento CLI |
| MONGO_IMAGE / POSTGRES_IMAGE | Imagen oficial con patch/variante explícitos y digest propuesto |
| MONGO_USERNAME / MONGO_PASSWORD | Autenticación administrativa MongoDB (admin) |
| POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB | Usuario/base inicial PostgreSQL |
| PUBLISH_PORTS | false por defecto; true carga config/ports.local.yml |
| MONGO_PORT / POSTGRES_PORT | 27017/5432 por defecto; publicados solo en 127.0.0.1 |
| HEALTH_TIMEOUT_SECONDS | Espera de arranque, 240 s por defecto |
| ACCEPT_NO_SWAP_ADAPTATION | false por defecto; true acepta explícitamente alternativa sin swap para arrancar |
| RESOURCE_CPUS / RESOURCE_MEMORY_MB | auto deriva del perfil; valores explícitos deben coincidir con el manual |
| CPU_PERIOD_US | 100000 us; se rechaza otro periodo en esta implementación |

Sintaxis .env deliberadamente restringida: KEY=value, sin comillas, espacios, expansión `$`, `#` dentro del valor ni ejecución de shell. Contraseñas pueden usar letras, números y signos admitidos por common.sh. No se ejecuta `source .env`. El archivo explícito es autoritativo para las variables admitidas; otras variables son rechazadas. ENV_FILE permite usar un archivo alternativo (ruta absoluta recomendada) para pruebas aisladas. La salida de `docker compose config` completo puede contener contraseñas: usar `config --quiet`; no compartir dumps de inspect.Env ni archivos de configuración resueltos.

## Perfiles y swap: adaptación explícita

| CLI | ID oficial | quota/period (us) | Memoria Compose | Bytes esperados |
| --- | --- | --- | --- | --- |
| baseline | PROFILE_A_BASELINE | 400000/100000 | 4096m | 4294967296 |
| medium | PROFILE_B_MEDIUM | 200000/100000 | 2048m | 2147483648 |
| severe | PROFILE_C_SEVERE | 100000/100000 | 1024m | 1073741824 |

Se conserva la notación `m` del manual como unidades binarias de Docker (MiB); el usuario las denomina MB. No se intercambian por millones de bytes sin registrar la diferencia. No es afinidad ni reserva de núcleos; es cuota CFS agregada. El host/ancestros pueden imponer techos menores y ambos motores comparten hardware.

El manual exige mem_swappiness=0. Compose conserva la solicitud literal, pero cgroups v2 no expone un control equivalente por contenedor en la versión Moby consultada; Docker puede descartarla y mostrar null en inspect. **No se declara satisfecha la exigencia literal** por tenerla en YAML.

Alternativa implementada (P-19, PROPOSED para el experimento): memswap_limit igual a mem_limit. La semántica Docker establece un total RAM+swap igual a RAM; por tanto memory.swap.max debe ser 0. Prohíbe swap para ese cgroup y es una restricción más fuerte, no una equivalencia universal de swappiness. No se toca vm.swappiness ni swap global del host. Para usarla en preparación/pilotos, el usuario debe leer esta diferencia y cambiar explícitamente ACCEPT_NO_SWAP_ADAPTATION=true. El script rehúsa arrancar si no lo hace. Esa aceptación local no demuestra compatibilidad ni aprueba automáticamente su uso académico definitivo: registrar aceptación/evidencia en P-19 antes de benchmarks.

Una salida normalizada de Compose puede omitir mem_swappiness:0 al serializar ceros; las pruebas comprueban también la declaración fuente. Solo inspect y los archivos del cgroup permiten conocer la solicitud que sobrevive y su efecto. No basta docker stats ni free dentro del contenedor para determinar swap.

## Inicio, cambio de perfil y detención

Después de completar .env y aceptar deliberadamente la alternativa documentada:

```bash
./scripts/start_services.sh baseline
./scripts/healthcheck.sh
./scripts/verify_resources.sh baseline
./scripts/stop_services.sh
./scripts/start_services.sh medium
./scripts/verify_resources.sh medium
./scripts/stop_services.sh
./scripts/start_services.sh severe
./scripts/verify_resources.sh severe
./scripts/stop_services.sh
```

start usa `up -d --wait`, valida argumentos/configuración, espera salud y conserva datos; no declara recursos aplicados solo porque arranque. Repetir con otro perfil puede recrear contenedores del mismo proyecto para cambiar límites; mantener las imágenes y el nombre de proyecto conserva los volúmenes. Evitar cambios mientras haya cargas activas. stop usa compose stop y espera apagado limpio: no elimina contenedores, red ni volúmenes. No ejecutar down -v, prune ni limpieza de cachés del host.

Red bridge interna de Compose, DNS mongodb:27017 y postgres:5432, sin puertos de host por defecto. El override opcional publica solo loopback; su conectividad externa local aún debe probarse si se habilita. healthcheck.sh prueba autenticación dentro de cada contenedor, estado, código de salida y OOMKilled sin ejecutar Q1/Q2. Los diagnósticos de logs son manuales para evitar exponer datos/credenciales por accidente.

## Verificación efectiva y configuraciones internas

verify_resources.sh consulta Docker info, campos no sensibles de inspect, cpu.max (quota/period), memory.max, memory.swap.max/current reales dentro del namespace privado del contenedor. Recorre ancestros accesibles desde /proc/PID/cgroup en el host nativo: un límite de hoja no anula un techo padre. Devuelve error ante diferencias, falta de lectura, perfil incorrecto o adaptación no aceptada. Muestra image ID e imagen; conservar evidencia local con fecha/versión. No mide rendimiento ni induce presión/OOM.

MongoDB selecciona WiredTiger sin sharding, con caché automática de la versión; PostgreSQL conserva parámetros internos por defecto, sin igualar artificialmente cachés. PostgreSQL dispone de shm_size=256m, que dimensiona /dev/shm, no reserva memoria adicional fuera del cgroup. No se fija work_mem ni allowDiskUse aquí: son variantes de fases posteriores. Diferencias de caché automática, shared_buffers, workers, locale y almacenamiento de las imágenes deben registrarse/contrastarse antes del experimento. No se crean orders, índices ni datos; contrato e identidad siguen pendientes para Fases 2–3.

## Pruebas

```bash
./tests/test_infrastructure.sh
# Acción explícita: crea un proyecto aislado y marcadores mínimos de persistencia.
./tests/test_containers.sh --run
```

La primera suite no inicia contenedores: Bash, Compose, variables, perfiles, rechazo de incompatibilidades, sintaxis .env y loopback. Usa fixtures de configuración, nunca mediciones. La segunda genera credenciales efímeras locales, acepta adaptación solo para ese proyecto de prueba y verifica salud, SELECT 1/JSONB, ping MongoDB y persistencia de un marcador tras force-recreate; intenta verificar recursos severe. No carga órdenes ni benchmark. Al terminar (incluso error) detiene su proyecto, elimina solo su archivo temporal de credenciales y conserva contenedores/red/volúmenes de prueba, sin borrar datos previos. Estos recursos quedan para inspección manual; no forman parte del ZIP.

Cloud: Bash/configuración pasan; pull de ambas imágenes confirmado. Prueba conjunta de contenedores abortó con `no space left on device` antes de salud/persistencia/recursos. Entorno Debian 13 anidado, no Kubuntu físico; límite padre 2 CPU/8 GiB, Engine 28.4.0, Compose 2.40.3, kernel 6.18.57. check_environment identifica baseline incompatible en Cloud. La imagen MongoDB descargada por esta tarea fue retirada de la caché de Cloud para recuperar espacio documental; no se retiraron imágenes previas, contenedores, volúmenes ni datos. No se usó prune. Prueba aislada posterior de PG: healthy, JSONB y una fila persistida tras recrear; hoja severe cpu.max=100000 100000, memory.max=1073741824 y memory.swap.max=0, inspect swappiness=null. MongoDB y validación integral/ancestros siguen pendientes. Ver handoff para resultados finales.

Pendiente en Kubuntu: identificar versión, validar paquetes/controladores, ejecutar suites, salud, persistencia, conectividad opcional y recursos/ancestros de los tres perfiles, confirmar aceptación de la adaptación y registrar versiones internas. La Fase 1 no puede marcarse COMPLETED por código escrito.

## Problemas frecuentes

- Daemon/socket sin acceso: revisar instalación/permisos manualmente; no reiniciar ni cambiar permisos globales desde scripts.
- Compose rechaza variables: completar .env; usar el script que exporta recursos derivados, no compose up aislado sin parametrización.
- Swappiness descartada o memory.swap.max ausente/distinto de 0: detener validación; conservar advertencia y no asumir cumplimiento.
- Perfil o ancestro incompatible: guardar cpu.max/memory.max; no modificar límites padre/kernel automáticamente.
- Autenticación falla tras editar contraseñas: el volumen conserva cuentas originales; recuperar configuración anterior o planificar cambio autorizado, nunca borrar volúmenes como solución automática.
- Cambio major/PGDATA: no reutilizar volumen de otra major sin migración; PG18 monta /var/lib/postgresql. Congelar versiones antes del dataset.
- Disco lleno: revisar df/docker system df (solo lectura); no ejecutar limpieza global ni eliminar datos para hacer pasar una prueba.
- Servicio unhealthy: revisar `docker compose logs --tail 50` localmente; no publicar logs completos sin revisión. El healthcheck puede competir por CPU en severe; documentar su sobrecarga futura.

## Extensiones futuras y respaldo

Un runner/importador podrá unirse a la red del proyecto usando nombres de servicio; las credenciales deberán manejarse sin incrustarlas en código. Los volúmenes admitirán el dataset una vez aprobado el contrato. Prometheus, cAdvisor y Node Exporter se añadirán en Fase 5; no hay servicios vacíos de reserva ni configuraciones definitivas. Consultas, perfiles de concurrencia y CSV pertenecen a fases posteriores.

El archivo fase1-infraestructura-kubuntu.zip incluye documentación actual, pruebas, scripts, configuraciones y PDF originales. Excluye .env reales, credenciales, temporales, cachés, volúmenes, datos y ZIP previos. Recuperarlo desde /workspace/fase1-infraestructura-kubuntu.zip; si el enlace local no descarga, usar el explorador de archivos del entorno.
