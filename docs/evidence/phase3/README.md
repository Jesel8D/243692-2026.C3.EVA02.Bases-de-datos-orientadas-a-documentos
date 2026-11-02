# Evidencia real de corrección PostgreSQL — Fase 3

Estos nueve JSON proceden de la integración real PostgreSQL 18.6 en Codex Cloud, sin ejecutar un benchmark. Se conservan planes nativos y resumen por nodo, tipos efectivos, variantes, validaciones contra oráculo e inventario de índices. No contienen credenciales ni datasets masivos. MongoDB no fue ejecutado: cross-engine BLOCKED nunca significa equivalencia real aprobada.

Fuente controlada: [query_fixtures.py](../../../tests/query_fixtures.py), funciones controlled() y boundary_ties(). controlled usa diez órdenes válidas con filtros/frontera temporal/aritmética esperados; boundary_ties usa 1005 para comprobar Top-1000 sin ordenar secundariamente. Las bases de prueba se conservaron. Los originales SQL siguen en [q1.sql](../../../queries/postgresql/q1.sql) y [q2.sql](../../../queries/postgresql/q2.sql).

Cada artifact incorpora evidence_written_at_utc recuperado del mtime original al añadir metadatos de procedencia; timestamp_source deja explícito que no es el inicio de consulta ni un timestamp del benchmark. Los valores originales de planes/validaciones no se sustituyeron. Los tiempos presentes en EXPLAIN son diagnósticos reales pequeños, nunca latencia P50/P95/P99 ni evidencia de rendimiento masivo.

| Archivo | Contenido |
| --- | --- |
| [phase3test_b119c776b1ff4002a85250ccb4bb54a9_postgres_work_mem_4mb_boundary_tie.json](phase3test_b119c776b1ff4002a85250ccb4bb54a9_postgres_work_mem_4mb_boundary_tie.json) | Validación de empate en frontera |
| [phase3test_b119c776b1ff4002a85250ccb4bb54a9_postgres_work_mem_64mb_boundary_tie.json](phase3test_b119c776b1ff4002a85250ccb4bb54a9_postgres_work_mem_64mb_boundary_tie.json) | Validación de empate en frontera |
| [phase3test_cee003d881c443b28817209855663401_after_text_proposal_plan.json](phase3test_cee003d881c443b28817209855663401_after_text_proposal_plan.json) | Plan original y resumen |
| [phase3test_cee003d881c443b28817209855663401_postgres_indexes.json](phase3test_cee003d881c443b28817209855663401_postgres_indexes.json) | Índices físicos y comparabilidad pendiente |
| [phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q1_default_plan.json](phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q1_default_plan.json) | Plan original y resumen |
| [phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q1_validation.json](phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q1_validation.json) | Validación contra fuente/oráculo |
| [phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q2_validation.json](phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q2_validation.json) | Validación contra fuente/oráculo |
| [phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q2_work_mem_4mb_plan.json](phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q2_work_mem_4mb_plan.json) | Plan original y resumen |
| [phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q2_work_mem_64mb_plan.json](phase3test_dbce03e4cf8841519ce6132f50f9ef60_Q2_work_mem_64mb_plan.json) | Plan original y resumen |

Ver [guía de consultas](../../11-consultas-y-validacion.md) para interpretar PASS/FAIL/BLOCKED, precisión, empates y limitaciones. La creación textual del índice fue explícita en base aislada; el reporte continúa BLOCKED para comparabilidad de la consulta temporal original.
