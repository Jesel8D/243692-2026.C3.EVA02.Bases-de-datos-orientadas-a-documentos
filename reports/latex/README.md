# Reporte académico parcial — MongoDB vs PostgreSQL JSONB

**Contenido:** `main.tex` (fuente editable), `main.pdf` (compilado), `generated/measurements_partial.csv` (copia auxiliar de dos filas definitivas), `generated/metrics.tex` (cifras para tablas y gráficos), `update_results.py` (lectura segura de CSV originales confirmados), y `fuentes.md` (trazabilidad).

## Instalación en Kubuntu

1. Descomprime esta carpeta **dentro de** `/home/mz/Documents/Evaluacion-base-de-datos/reports/latex/`, dejando `main.tex` directamente en `reports/latex/main.tex`.
2. Para usar los datos ya incorporados (idénticos a los comunicados en el chat): `cd reports/latex && pdflatex -interaction=nonstopmode -halt-on-error main.tex && pdflatex -interaction=nonstopmode -halt-on-error main.tex`.
3. Para volver a extraer y verificar **los originales de tu proyecto**, desde `reports/latex/`: `python3 update_results.py --project-root ../..`. El programa comprueba la presencia de `commit.json`, sus hashes y la elegibilidad, y actualiza únicamente `generated/`.
4. Después, compila de nuevo `pdflatex` dos veces. Se generará `reports/latex/main.pdf`.

**Advertencia:** el documento es un **avance parcial**: dos mediciones definitivas individuales Q1, perfil A, concurrencia 1, una por motor; ninguna ejecución Q2; no se completaron las 108 repeticiones. No sustituye las evidencias originales. Los PDFs preexistentes de `reports/academico-parcial` y `reports/piloto-real` no estaban adjuntos y no se incorporaron ni inspeccionaron.

**Antes de entregar:** verifica el título, autor(es), fecha, información del host, gráficas y si el docente pide evidencia adicional de `explain`/`EXPLAIN ANALYZE`. Conserva los archivos del experimento original.
