# Reportes de Fase 6

No existen mediciones académicas definitivas. No se generó ningún resultado ficticio para rellenar informes. Los snapshots son copias por hash de fuentes reales anteriores o están vacíos; los fixtures unitarios se generan únicamente en directorios temporales.

## Versiones revisadas de entrega

- Informe académico **PARCIAL, 0/108**: [HTML](academico-parcial/20261101T180843Z-e7abcd9f5b/reporte.html), [Markdown](academico-parcial/20261101T180843Z-e7abcd9f5b/reporte.md), [PDF](academico-parcial/20261101T180843Z-e7abcd9f5b/reporte.pdf). Base planificada con Q2 false/4MB explícitas para esta plantilla; no aprobación académica de selección. Sin figuras ni valores fabricados.
- Diagnóstico de **PILOTO REAL, NO DEFINITIVO**: [HTML](piloto-real/20261101T180841Z-1e2a201164/reporte.html), [Markdown](piloto-real/20261101T180841Z-1e2a201164/reporte.md), [PDF](piloto-real/20261101T180841Z-1e2a201164/reporte.pdf). PostgreSQL/Q2/severe/work_mem4, un cliente, 100 órdenes y 1/4/1s, de Fase 5; no ejecución nueva ni comparación Mongo/PG. Tres figuras derivadas de su evidencia real, incluidos muestras RSS temporales. Planes PG de Fase 3 se muestran como auxiliares sobre otro dataset de 10 órdenes, sin vínculo académico final.
- [Captura ambiental Cloud independiente](entorno-cloud-fase6.json): observación actual de preparación, no prueba retrospectiva ni sustituto de Kubuntu físico.

Cada carpeta contiene analysis-manifest.json como marcador de construcción completa, hashes/versión/fuentes/dependencias; snapshots/index.json permite rastrear entradas originales. El informe académico no se etiqueta FINAL por falta de repeticiones/validaciones. La CLI rechaza FINAL sin datos; --allow-partial conserva etiqueta parcial.

Versiones anteriores se conservan dentro de piloto-real/ y academico-parcial/ como historial; pueden preceder a endurecimientos de validación. Usar los enlaces de entrega anteriores y conservar el directorio completo con figuras. Para actualizar con mediciones locales auténticas, consultar [guía operativa](../docs/14-analisis-y-reporte.md). No reutilizar el piloto como resultado académico ni como medición de Kubuntu.
