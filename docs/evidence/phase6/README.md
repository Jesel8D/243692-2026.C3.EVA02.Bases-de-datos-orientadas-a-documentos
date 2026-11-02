# Evidencia de validación de Fase 6

Fecha: 2026-11-01. Solo validación de software y análisis offline; cero consultas/benchmarks nuevos, cero mediciones académicas definitivas. No se arrancaron motores/exportadores en esta fase.

- unit-reporting.txt: 33 pruebas nuevas aprobadas; fixtures sintéticos privados en TemporaryDirectory, no mediciones reales.
- regression.txt: 126 casos, 114 aprobados y 12 integraciones omitidas. Comando Cloud con drivers anteriores: PYTHONPATH=/tmp/phase4-venv/lib/python3.12/site-packages python3 -m unittest discover -s tests -v. Las integraciones históricas de fases anteriores no se suman como repetidas aquí.
- infrastructure.txt: sintaxis Bash, Compose baseline/medium/severe y configuraciones negativas. No prueba contenedores ni límites reales.
- promtool.txt: binario oficial 3.15.1 valida sintaxis de config/monitoring/prometheus.yml; monitoring.sh config también pasó, sin iniciar servicios.
- validation-summary.json: sintaxis AST/Bash, conservación respecto a Fase 5 y verificación de hashes/PDF/siete secciones de reportes reales. Único cambio previo fuera de Markdown: query_tool.py, enlace opcional de dataset a EXPLAIN, cubierto por dos unitarias y pendiente de prueba real.
- progress-pilot.json / validation-pilot.json: piloto real de Fase 5 leído offline, una repetición técnicamente válida, **0 académicas**; auditoría all de hashes. No validar Mongo/Kubuntu a partir de ello.
- final-blocked.json: solicitud FINAL sin mediciones bloqueada con código 2, sin generar carpeta final. Informe parcial vacío se genera por separado, sin métricas falsas.
- report-pilot-build.json / report-academic-build.json: rutas de entregas inmutables; sus analysis-manifest.json verifican contenido/código/dependencias. PDF revisado con pdfinfo/pdftotext y portada/figura visual; legibilidad comprobada. Ver [catálogo](../../../reports/README.md).
- documentation-validation.json: enlaces locales, inventario de fuentes/requisitos/decisiones, sintaxis documental y revisión de alcance.
- archive-verification.json: inventario/exclusiones, permisos, bytes/CRC y conservación de originales para fase6-reporte-kubuntu.zip. El hash SHA256 del ZIP se conserva fuera de él para evitar autorreferencia.

Limitaciones: sin resultados definitivos, sin reporte FINAL real, sin pruebas nuevas de bases/monitoreo, sin equipo físico. Los casos sintéticos verifican el software exclusivamente; no se guardaron sus CSV/figuras/informes en el proyecto. Los reportes disponibles usan evidencia histórica real o una plantilla vacía claramente parcial.
