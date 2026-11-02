# Diseño experimental

Diseño reconciliado con P pp.1–3 §§1–7 y S pp.3–8 (fuentes en [requisitos](01-requisitos-y-trazabilidad.md)). Los requisitos confirmados se distinguen de propuestas de ejecución aún pendientes. REQ-001, 006–013, 024, 029–034, 037–039.

## Preguntas y variables

Enunciados de P p.1 §1 (acentos normalizados del PDF), corroborados en S p.4:

- M1: ¿Cómo cambian la latencia P95 y P99 de las agregaciones sobre documentos anidados cuando se limita de forma estricta la CPU y la memoria?
- M2: ¿Qué motor usa de forma más eficiente los buffers de ordenamiento y agrupamiento antes de volcar a disco temporal o fallar por falta de memoria (OOM)?
- M3: ¿Cuál es la huella de CPU y memoria por cada 1 000 documentos procesados en el motor documental frente al motor con JSONB?

M3 no define cómo contar documentos procesados, CPU consumida ni normalizar memoria. El CSV no incluye estos indicadores directamente: requiere evidencia lateral y definición aprobada (P-14), sin confundir segundos de throttling con tiempo de CPU utilizado.

Variables independientes: motor (MongoDB/PostgreSQL JSONB), perfil (baseline/medium/severe), carga (Q1/Q2), concurrencia (1/10/50); las modalidades de memoria Q2 añaden un factor por motor con alcance pendiente de confirmar. Dependientes: QPS, latencias, throttling, memoria, spill y estabilidad/status; ver métricas. Controladas propuestas: mismo dataset/semilla, consultas equivalentes, versiones, índices documentados, hardware, almacenamiento, ausencia de carga ajena y protocolo de caché.

| Perfil del manual referido por U §3 | CPU | Memoria | mem_swappiness |
| --- | --- | --- | --- |
| PROFILE_A_BASELINE | 4 | 4096 MB | 0 |
| PROFILE_B_MEDIUM | 2 | 2048 MB | 0 |
| PROFILE_C_SEVERE | 1 | 1024 MB | 0 |

Las unidades efectivas MB/MiB y la compatibilidad de swappiness en cgroups v2 deben verificarse; no se declara aplicación efectiva.

## Matriz y variantes

Producto base: 2 motores × 3 perfiles × 2 consultas × 3 concurrencias = 36 celdas. Cada celda tiene 3 repeticiones: 108 ejecuciones base. Q1 aporta 18 celdas/54 ejecuciones y Q2 otras 18/54.

P p.2 §5.2 especifica MongoDB allowDiskUse:false / true y PostgreSQL SET work_mem = '4MB' / '64MB'. S p.7 exige reportar ambas variantes. P p.3 §6 y S p.8, sin embargo, declaran 36 celdas sin dimensión de variante. No explican cómo cruzarlas ni cuál sería la modalidad base.

| Diseño | Q1 | Q2 | Total de ejecuciones (3 repeticiones) |
| --- | --- | --- | --- |
| Base declarada sin desglosar modalidades | 18 celdas | 18 celdas | 108 |
| Propuesta de cruce completo de ambas modalidades por motor | 18 celdas | 36 celdas | 162 |

La propuesta añade 18 celdas/54 ejecuciones: total 54 celdas. Fórmula general, con m/p modalidades Q2 totales por motor: celdas = 18 + 9(m+p); ejecuciones = 54 + 27(m+p). Aquí m=p=2 produciría 162. No sumar otra base Q2 a las dos modalidades (eso duplicaría mediciones). Otra interpretación es limitar variantes a ciertas celdas; necesitaría enumeración justificada. El cruce completo es PROPOSED, no decisión aprobada ni cifra impuesta por el profesor (P-02).

## Ciclo

Limpieza de caché → warmup 60 s → medición 300 s → cooldown 60 s (U §3). P p.3 §6 indica literalmente `sync; echo 3 >/proc/sys/vm/drop_caches`. Se documenta como fuente, no como instrucción para ejecutarlo ahora. Es una acción privilegiada de alcance Linux/VM que puede afectar otras cargas; no equivale a vaciar cachés internas de motores. La adaptación segura al entorno local requiere aprobación (P-07). No ejecutar drop_caches ni comandos privilegiados durante esta fase. Cada ejecución necesita identificador y marcas de etapa. La ventana medida excluye warmup/cooldown (propuesta).

108 × 420 s = 45,360 s = 12 h 36 min como duración nominal secuencial base; excluye limpieza, carga, reinicios, fallos y variantes. Con 162 ejecuciones serían 68,040 s = 18 h 54 min, también sin sobrecostes. No son estimaciones garantizadas del tiempo real.

## Comparabilidad y validez

Propuestas pendientes: medir un motor a la vez con recursos equivalentes; balancear/registrar orden con semilla; separar recursos del runner y telemetría; calcular deltas de contadores sin reiniciarlos artificialmente. Mantener mismo contenido y comparación de resultados antes de medir.

Riesgos: caché desigual, índices asimétricos, precisión/timestamps distintos, presión externa del host Kubuntu nativo (antes Windows/WSL2; reemplazado por U3), límites de cgroups ancestros menores que contenedores, sobrecarga de observabilidad y 50 clientes, sesgo por orden/temperatura, consultas fallidas tratadas como rápidas y supervivencia tras OOM. Conservar intentos fallidos; no reemplazarlos silenciosamente. Políticas de reintento y exclusión requieren aprobación (P-08).

## Implementación de automatización (U6)

Fase 4 implementa los dos planes sin resolver P-02: `plan --matrix base` exige variante Q2 para ambos motores; `plan --matrix extended` produce 54/162 con advertencia de no aprobación. Escenario/variante/repetición tienen ID determinista y manifiesto externo, sin añadir columnas al CSV. Filtros conservan el conteo de la selección, no redefinen la matriz original.

La política operativa provisional cuenta éxitos que empiezan y terminan dentro de la ventana común de 300 s; drena/excluye cruces de borde de QPS y latencias. Warmup/cooldown quedan fuera. Orden de catálogo determinista, sin balanceo aprobado; no hay reintentos automáticos. Recursos del runner quedan separados de los motores. Skip de caché es solo piloto; constancia manual no demuestra por sí sola caché vacía. RSS/spill ausentes impiden mediciones definitivas. Métodos y riesgos en [guía del runner](12-automatizacion-benchmarks.md), P-29–35; no sustituyen M3 ni aprueban política académica final.
