# Instrucciones persistentes

Proyecto académico: comparación reproducible de MongoDB y PostgreSQL JSONB bajo contención de CPU y memoria, Bases de Datos en la Nube, Ingeniería en Tecnologías de la Información e Innovación Digital, Universidad Politécnica de Chiapas.

## Autoridad y reglas

1. Respetar instrucciones explícitas del usuario, playbook.pdf, playbook_sesion.pdf, decisiones aprobadas y propuestas provisionales, en ese orden.
2. No inventar especificaciones, mediciones, resultados ni referencias. Si faltan manuales, registrar el bloqueo.
3. No modificar requisitos sin documentar la razón y obtener aprobación cuando corresponda.
4. Mantener reproducibilidad, condiciones experimentales y resultados originales.
5. Distinguir requisitos, decisiones aprobadas y propuestas; consultar docs/07-decisiones-y-pendientes.md.
6. Mantener trazabilidad con docs/01-requisitos-y-trazabilidad.md.
7. Validar cambios cuando sea posible y registrar verificaciones efectivamente realizadas.
8. Documentar limitaciones del entorno; Cloud prepara el proyecto y los benchmarks definitivos se ejecutan localmente.
9. Evitar complejidad innecesaria.
10. No agregar funcionalidades ajenas al objetivo académico.

## Restricciones técnicas

Favorecer Python para datos, automatización y análisis; Docker Compose para infraestructura. Parametrizar configuraciones, no incrustar secretos y fijar versiones explícitas reproducibles una vez aprobadas. Conservar exactamente el CSV de docs/05-metricas-y-evidencia.md y la equivalencia semántica de consultas. No alterar resultados para favorecer un motor ni sustituir mediciones reales por datos ficticios. Evitar operaciones destructivas sobre el host. No ejecutar comandos privilegiados, borrar datos, modificar configuración global, desplegar, solicitar credenciales ni hacer commits o pushes sin autorización expresa aplicable.

## Flujo por fase

1. Identificar objetivo y archivos relevantes en PLANS.md y docs/08-handoff.md.
2. Revisar requisitos y fuentes disponibles.
3. Comprobar dependencias.
4. Implementar únicamente el alcance autorizado.
5. Ejecutar verificaciones disponibles.
6. Documentar resultados y limitaciones.
7. Registrar decisiones importantes.
8. Actualizar handoff y entregar resumen.

Consultar los originales conservados en docs/reference/playbook.pdf y docs/reference/playbook_sesion.pdf; las referencias P y S con página se definen en docs/01-requisitos-y-trazabilidad.md. La Fase 0 documental está completada; las ambigüedades abiertas del registro no se convierten en decisiones aprobadas. Git/GitHub no es requisito para cerrar la revisión documental.

No comenzar automáticamente la siguiente fase. Durante Fase 0 solo documentación: no generadores, consultas ejecutables, servicios operativos, runners, configuraciones definitivas de telemetría ni resultados experimentales. Consultar docs/ para detalles; no duplicarlos aquí.

## Plataforma y alcance vigente (Fases 1–6)

Por instrucción explícita del usuario, Kubuntu Linux nativo en x86_64 reemplaza Windows/Docker Desktop/WSL2. Usar Docker Engine local y Compose Plugin; versión exacta de Kubuntu pendiente de identificación. Conservar el antecedente en docs/07. Alcance histórico U3 de Fase 1: Compose, scripts seguros, pruebas de infraestructura y documentación. Historial: U4 autorizó Fase 2 sin esperar equipo físico. U5 autorizó Fase 3 (consultas, corrección, índices seguros y planes). U6 autorizó Fase 4 (runner/matrices/pilotos). U7 autorizó Fase 5: Prometheus/cAdvisor/Node Exporter y telemetría integrada. U8 autoriza exclusivamente Fase 6: análisis offline, progreso y reportes incrementales/parciales/finales, gráficas y pruebas; no autoriza Fase 7 ni benchmarks definitivos. Consultar docs/14-analisis-y-reporte.md; no mezclar cohortes/variantes ni pilotos con mediciones académicas. Consultar docs/13-observabilidad-y-telemetria.md. No sustituir RSS, atribuir spill mediante otro EXPLAIN ni completar ausencias con cero; profiling requiere activación explícita acotada/restauración. Consultar docs/12-automatizacion-benchmarks.md. Mantener pendientes Mongo/Kubuntu y telemetría; ninguna fila sin métricas obligatorias es válida para análisis final. Consultar docs/11-consultas-y-validacion.md. Consultar docs/10-generacion-y-carga-datos.md. Las adaptaciones del contrato siguen provisionales, sin aprobación inferida. Ver docs/09-instalacion-kubuntu.md. No confundir pull/configuración con salud, persistencia o límites efectivos. La adaptación sin swap requiere aceptación explícita; no equivale a cumplimiento literal de mem_swappiness=0. Estado actual y evidencia en docs/08-handoff.md.
