# Procedencia y límites de la evidencia

- Protocolo fuente: `playbook.pdf` compartido en esta conversación, Universidad Politécnica de Chiapas, Bases de Datos en la Nube (2026).
- Medición PostgreSQL: `results/definitive/definitivo-pg-q1-a-c1-20261101-v2/bc0a8de32c1719c76fca6946/attempt-708f060a15574a85b9c78a57ae8113f0/`.
- Medición MongoDB: `results/definitive/definitivo-q1-perfil-a-optimizado-20261101/4f537e29c5c322d57cebb3b9/attempt-49fe681fa4fc4261b69ac54edfe44904/`.
- El usuario compartió los valores originales de `results.csv` y marcadores de `eligible_for_final_analysis=True` de `result.json`; las dos carpetas tenían `commit.json` según la verificación realizada en su equipo.
- El preflight Mongo marcó `global_validation.status=FULL`, tiempo `2159.565` s. El intento de reutilización para PostgreSQL fue `BLOCKED` por condición de contadores/identidad/recuento; no hubo nueva medida de PostgreSQL en esa invocación.
- Suite local comunicada: `Ran 135 tests in 9.474s`, `OK (skipped=12)`.
- No se proporcionaron los planes reales de ejecución de ambas consultas ni telemetría completa por segundo; no se inventan.
- El índice PostgreSQL tipo BTree de texto de `data->>timestamp` no garantiza uso por Q2, que castea a `timestamptz`; aceptación del operador no es aprobación del docente.
