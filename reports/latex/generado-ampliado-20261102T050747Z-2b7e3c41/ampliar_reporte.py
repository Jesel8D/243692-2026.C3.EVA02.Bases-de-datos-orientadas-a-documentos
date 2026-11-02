#!/usr/bin/env python3
"""
Generador offline del informe académico parcial.
No ejecuta benchmarks, Docker, consultas ni limpieza de cachés.
No modifica resultados originales, dataset, runner o preflight.
"""
import argparse
import ast
import csv
import hashlib
import io
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

COLUMNS = (
    "timestamp_epoch,engine,profile,query_id,concurrency,run_number,"
    "throughput_qps,latency_p50_ms,latency_p95_ms,latency_p99_ms,"
    "cpu_throttled_seconds,max_rss_mb,disk_spill,status"
).split(",")

NAMES = {"mongodb": "MongoDB", "postgresql": "PostgreSQL"}
ALIASES = {
    "mongo": "mongodb", "mongodb": "mongodb",
    "postgres": "postgresql", "postgresql": "postgresql"
}
RUNS = {
    "mongodb": "results/definitive/definitivo-q1-perfil-a-optimizado-20261101",
    "postgresql": "results/definitive/definitivo-pg-q1-a-c1-20261101-v2"
}
REPORTED = {
    "mongodb": {
        "version": "9.0.4", "throughput_qps": 0.5467,
        "latency_p50_ms": 1818.41, "latency_p95_ms": 1861.30,
        "latency_p99_ms": 1902.25, "max_rss_mb": 1026.65,
        "cpu_throttled_seconds": 0, "disk_spill": "0",
        "status": "ok", "operations": 164
    },
    "postgresql": {
        "version": "18.6", "throughput_qps": 0.4167,
        "latency_p50_ms": 2353.83, "latency_p95_ms": 2562.62,
        "latency_p99_ms": 2800.77, "max_rss_mb": 108.22,
        "cpu_throttled_seconds": 0.083895, "disk_spill": "1",
        "status": "spill", "operations": 125
    }
}
DOCS = [
    "AGENTS.md", "PLANS.md",
    "docs/01-requisitos-y-trazabilidad.md",
    "docs/05-metricas-y-evidencia.md",
    "docs/07-decisiones-y-pendientes.md",
    "docs/08-handoff.md",
    "docs/09-instalacion-kubuntu.md",
    "docs/10-generacion-y-carga-datos.md",
    "docs/11-consultas-y-validacion.md",
    "docs/12-automatizacion-benchmarks.md",
    "docs/13-observabilidad-y-telemetria.md",
    "docs/14-analisis-y-reporte.md"
]
LIMIT = 24 * 1024 * 1024

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def stable(path, limit=LIMIT):
    before = path.stat()
    if before.st_size > limit:
        raise ValueError("Archivo omitido por tamaño: " + str(path))
    data = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Archivo cambió durante lectura: " + str(path))
    return data

def rel(root, path):
    return path.resolve().relative_to(root.resolve()).as_posix()

def confined(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Ruta fuera del proyecto: " + str(name))
    return path

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")

def tex(value):
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
        "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
        "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        "→": r"$\to$", "≥": r"$\geq$", "≤": r"$\leq$",
        "×": r"$\times$", "✓": "[si]", "✗": "[no]", "\u00a0": " "
    }
    return "".join(replacements.get(char, char) for char in str(value))

def cell(value):
    value = str(value)
    if re.fullmatch(r"[a-fA-F0-9]{64}", value):
        parts = [value[i:i + 8] for i in range(0, 64, 8)]
        return r"\texttt{" + r"\allowbreak{}".join(parts) + "}"
    result = []
    for char in value:
        result.append(tex(char))
        if char in "/_-.":
            result.append(r"\allowbreak{}")
    return "".join(result)

def table(headers, rows, spec):
    return "\n".join([
        r"\begin{longtable}{" + spec + "}",
        r"\toprule",
        " & ".join(tex(x) for x in headers) + r" \\",
        r"\midrule\endhead",
        *[" & ".join(cell(x) for x in row) + r" \\" for row in rows],
        r"\bottomrule\end{longtable}"
    ])

def leaves(obj, prefix=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = prefix + "." + str(key) if prefix else str(key)
            yield from leaves(value, name)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from leaves(value, prefix + "[" + str(index) + "]")
    else:
        yield prefix, obj

def objects(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from objects(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from objects(value)

def number(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Número ausente, negativo o no finito")
    return value

def integer(value):
    value = number(value)
    if not value.is_integer():
        raise ValueError("Se esperaba un entero")
    return int(value)

def parse_csv(data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if reader.fieldnames != COLUMNS:
        raise ValueError("Cabecera distinta de las 14 columnas oficiales")
    rows = list(reader)
    for row in rows:
        if set(row) != set(COLUMNS) or any(v is None for v in row.values()):
            raise ValueError("Fila con columnas ausentes o adicionales")
    return rows

def validate(row, engine):
    if ALIASES.get(row["engine"].strip().lower()) != engine:
        raise ValueError("Motor diferente del seleccionado")
    if row["profile"].upper() != "PROFILE_A_BASELINE":
        raise ValueError("Perfil diferente de A")
    if row["query_id"].upper() != "Q1":
        raise ValueError("Consulta diferente de Q1")
    if integer(row["concurrency"]) != 1 or integer(row["run_number"]) != 1:
        raise ValueError("Concurrencia o repetición diferentes de 1")
    if number(row["timestamp_epoch"]) <= 0:
        raise ValueError("Timestamp no positivo")
    values = {key: number(row[key]) for key in COLUMNS[6:12]}
    if values["throughput_qps"] <= 0 or values["max_rss_mb"] <= 0:
        raise ValueError("QPS o RSS no positivo")
    if not (
        values["latency_p50_ms"] <= values["latency_p95_ms"]
        <= values["latency_p99_ms"]
    ):
        raise ValueError("Percentiles inconsistentes")
    if row["disk_spill"] != REPORTED[engine]["disk_spill"]:
        raise ValueError("Spill distinto del confirmado por el responsable")
    if row["status"].lower() != REPORTED[engine]["status"]:
        raise ValueError("Estado distinto del confirmado por el responsable")
    return values

def find_commit(path, run):
    current = path.parent
    while current.is_relative_to(run):
        candidate = current / "commit.json"
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
        if current == run:
            break
        current = current.parent
    return None

def json_documents(root, run, sources):
    documents = []
    if not run.is_dir():
        return documents
    for path in sorted(run.rglob("*.json")):
        if path.is_symlink():
            continue
        try:
            data = stable(path)
            obj = json.loads(data)
            documents.append((path, obj))
            sources.append({
                "path": rel(root, path), "sha256": sha(data), "kind": "run_json"
            })
        except (OSError, ValueError, UnicodeError) as exc:
            sources.append({"path": rel(root, path), "error": str(exc)})
    return documents

def select_run(root, run, engine, sources, notes):
    if not run.is_dir():
        notes.append("No existe " + rel(root, run))
        return None, []
    documents = json_documents(root, run, sources)
    eligibility = []
    for path, obj in documents:
        for key, value in leaves(obj):
            if key.rsplit(".", 1)[-1].lower() == "eligible_for_final_analysis":
                eligibility.append({
                    "source": rel(root, path), "field": key, "value": value
                })
    if any(item["value"] is not True for item in eligibility):
        notes.append(
            NAMES[engine] + ": declaración local de elegibilidad negativa "
            "o ambigua; no se admitió automáticamente la medición."
        )
        return None, documents

    candidates = []
    for path in sorted(run.rglob("*.csv")):
        if path.is_symlink():
            continue
        try:
            data = stable(path)
            rows = parse_csv(data)
            commit_path = find_commit(path, run)
            if commit_path is None:
                raise ValueError("No se encontró commit.json asociado")
            commit_data = stable(commit_path)
            commit = json.loads(commit_data)
            if isinstance(commit, dict):
                status = str(commit.get("status", "")).lower()
                if status in {"failed", "error", "aborted", "uncommitted", "rollback"}:
                    raise ValueError("Commit con estado no aceptable")
                if commit.get("committed") is False:
                    raise ValueError("Commit explícitamente no confirmado")
        except (OSError, ValueError, UnicodeError, csv.Error) as exc:
            sources.append({"path": rel(root, path), "csv_error": str(exc)})
            continue

        for row_number, row in enumerate(rows, 1):
            try:
                values = validate(row, engine)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                sources.append({
                    "path": rel(root, path), "row": row_number,
                    "excluded": str(exc)
                })
                continue
            bound = any(
                value == sha(data) for _, value in leaves(commit)
                if isinstance(value, str)
            )
            differences = []
            for field in COLUMNS[6:12]:
                tolerance = (
                    0.000051 if field == "throughput_qps" else
                    0.00000051 if field == "cpu_throttled_seconds" else
                    0.0051
                )
                if abs(values[field] - REPORTED[engine][field]) > tolerance:
                    differences.append(field)
            candidates.append({
                "engine": engine, "row": row, "values": values,
                "csv": rel(root, path), "row_number": row_number,
                "csv_sha256": sha(data),
                "commit": rel(root, commit_path),
                "commit_sha256": sha(commit_data),
                "csv_hash_recognized_in_commit": bound,
                "eligibility_fields": eligibility,
                "eligibility_provenance": (
                    "Campo local y confirmación explícita del responsable"
                    if eligibility else
                    "Confirmación explícita del responsable; "
                    "campo local no reconocido automáticamente"
                ),
                "rounding_differences": differences,
                "_csv_bytes": data, "_commit_bytes": commit_data,
                "_run": run
            })

    grouped = {}
    for item in candidates:
        key = tuple(item["row"][column] for column in COLUMNS)
        grouped.setdefault(key, []).append(item)
    unique = []
    for copies in grouped.values():
        bound = [item for item in copies if item["csv_hash_recognized_in_commit"]]
        unique.append((bound or copies)[0])
    if len(unique) > 1:
        bound = [item for item in unique if item["csv_hash_recognized_in_commit"]]
        if len(bound) == 1:
            unique = bound
    if len(unique) != 1:
        notes.append(
            NAMES[engine] + ": " + str(len(unique)) +
            " candidatos distintos; no se eligió uno arbitrariamente."
        )
        return None, documents
    item = unique[0]
    if not eligibility:
        notes.append(
            NAMES[engine] + ": elegibilidad confirmada por el usuario; "
            "campo local no reconocido."
        )
    if not item["csv_hash_recognized_in_commit"]:
        notes.append(
            NAMES[engine] + ": asociación CSV/commit por directorio; "
            "vínculo criptográfico exacto no reconocido."
        )
    if item["rounding_differences"]:
        notes.append(
            NAMES[engine] + ": diferencias frente al resumen comunicado en " +
            ", ".join(item["rounding_differences"]) +
            ". Se conservan los valores originales del CSV."
        )
    return item, documents

def visible_code(text):
    return text.encode("ascii", "backslashreplace").decode("ascii")

def inspect_sources(root, out, sources, notes):
    documents = {}
    for name in DOCS:
        path = root / name
        if not path.is_file() or path.is_symlink():
            notes.append("Fuente pendiente: " + name)
            continue
        try:
            data = stable(path)
            documents[name] = data.decode("utf-8")
            sources.append({"path": name, "sha256": sha(data), "kind": "document"})
        except (OSError, ValueError, UnicodeError) as exc:
            notes.append("No se leyó " + name + ": " + str(exc))

    for folder in ("benchmark", "queries", "reporting", "scripts", "config", "observability"):
        directory = root / folder
        if not directory.is_dir():
            notes.append("Carpeta pendiente: " + folder)
            continue
        for path in sorted(directory.rglob("*")):
            if (
                not path.is_file() or path.is_symlink()
                or path.suffix.lower() not in {".py", ".sql", ".js", ".json", ".md", ".yaml", ".yml", ".txt"}
                or "__pycache__" in path.parts
            ):
                continue
            try:
                data = stable(path)
                sources.append({
                    "path": rel(root, path), "sha256": sha(data), "kind": "source"
                })
            except (OSError, ValueError):
                continue

    questions = []
    for name in ("playbook.pdf", "playbook_sesion.pdf"):
        path = next((
            p for p in (root / "docs" / "reference" / name, root / name)
            if p.is_file() and not p.is_symlink()
        ), None)
        if path is None:
            notes.append("Manual no encontrado: " + name)
            continue
        data = stable(path, 64 * 1024 * 1024)
        sources.append({
            "path": rel(root, path), "sha256": sha(data), "kind": "manual"
        })
        if not shutil.which("pdftotext"):
            notes.append("Falta pdftotext: no se extrajo " + name)
            continue
        process = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True, text=True, errors="replace"
        )
        if process.returncode:
            notes.append("Falló extracción de " + name)
            continue
        write(out / (name + ".txt"), process.stdout)
        for page_number, page in enumerate(process.stdout.split("\f"), 1):
            lines = page.splitlines()
            selected = set()
            for index, line in enumerate(lines):
                if re.search(r"\bM[123]\b", line):
                    selected.update(range(max(0, index - 1), min(len(lines), index + 3)))
            if selected and len(questions) < 3:
                filename = "preguntas-" + str(len(questions) + 1) + ".txt"
                write(out / filename, visible_code(
                    "\n".join(lines[i] for i in sorted(selected)[:12])
                ))
                questions.append(
                    r"\paragraph{Fuente: " + cell(rel(root, path)) +
                    ", página " + str(page_number) + "}\n" +
                    r"\lstinputlisting{\artifactdir/" + filename + "}"
                )
    if not questions:
        notes.append("Formulación normativa M1/M2/M3 pendiente de cotejo humano.")
    write(
        out / "preguntas.tex",
        "\n".join(questions) or
        r"\pendiente{No se identificó automáticamente la formulación "
        r"normativa M1/M2/M3. No se inventa su correspondencia.}"
    )

    extracts = []
    for name in (
        "docs/07-decisiones-y-pendientes.md",
        "docs/11-consultas-y-validacion.md",
        "docs/12-automatizacion-benchmarks.md",
        "docs/13-observabilidad-y-telemetria.md",
        "docs/14-analisis-y-reporte.md"
    ):
        text = documents.get(name)
        if text is None:
            continue
        lines = text.splitlines()
        selected = set()
        for index, line in enumerate(lines):
            if re.search(r"cache|caché|reuse|reutil|preflight|RSS|spill|timestamp", line, re.I):
                selected.update(range(max(0, index - 1), min(len(lines), index + 2)))
                if len(selected) >= 9:
                    break
        if not selected:
            continue
        filename = "extracto-" + str(len(extracts) + 1) + ".txt"
        write(out / filename, visible_code("\n".join(
            str(i + 1) + ": " + lines[i] for i in sorted(selected)[:9]
        )))
        extracts.append(
            r"\paragraph{Fuente: " + cell(name) + "}\n" +
            r"\lstinputlisting{\artifactdir/" + filename + "}"
        )
    write(
        out / "extractos.tex",
        "\n".join(extracts) or
        r"\pendiente{No se obtuvieron extractos documentales reconocibles.}"
    )

def extract_queries(root, out, sources, notes):
    candidates = []
    directory = root / "queries"
    if directory.is_dir():
        for path in sorted(directory.rglob("*")):
            if (
                not path.is_file() or path.is_symlink()
                or path.suffix.lower() not in {".py", ".sql", ".js", ".json"}
            ):
                continue
            try:
                data = stable(path)
                text = data.decode("utf-8")
            except (OSError, ValueError, UnicodeError):
                continue
            if path.suffix == ".py":
                try:
                    tree = ast.parse(text)
                except SyntaxError:
                    continue
                for node in tree.body:
                    names = []
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        names = [node.name]
                    elif isinstance(node, ast.Assign):
                        names = [
                            target.id for target in node.targets
                            if isinstance(target, ast.Name)
                        ]
                    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                        names = [node.target.id]
                    if any(re.search(r"q[12]", name, re.I) for name in names):
                        segment = "\n".join(text.splitlines()[node.lineno - 1:node.end_lineno])
                        candidates.append((path, data, segment, node.lineno, node.end_lineno))
            elif re.search(r"q[12]", path.name, re.I):
                candidates.append((path, data, text, 1, len(text.splitlines())))
    blocks = []
    for index, (path, data, segment, first, last) in enumerate(candidates[:4], 1):
        original = "consulta-original-" + str(index) + path.suffix
        (out / original).write_bytes(data)
        excerpt = "consulta-extracto-" + str(index) + ".txt"
        write(out / excerpt, visible_code("\n".join(segment.splitlines()[:48])))
        blocks.extend([
            r"\paragraph{Fuente original: " + cell(rel(root, path)) +
            ", líneas " + str(first) + "--" + str(last) + "}",
            "Se conserva la fuente completa como recurso editable. "
            "El extracto visual muestra hasta 48 líneas y representa "
            "caracteres fuera de ASCII mediante escapes Unicode.",
            r"\lstinputlisting{\artifactdir/" + excerpt + "}"
        ])
        sources.append({
            "path": rel(root, path), "sha256": sha(data),
            "kind": "query_listing", "first_line": first,
            "last_line": last, "original_copy": original
        })
    if not blocks:
        notes.append("No se reconocieron automáticamente bloques originales Q1/Q2.")
    write(
        out / "consultas.tex",
        "\n".join(blocks) or
        r"\pendiente{No se reconocieron bloques Q1/Q2. No se reconstruyeron consultas.}"
    )

def host_info():
    result = {
        "captura_utc": now(),
        "arquitectura": platform.machine(),
        "kernel": platform.release(),
        "CPU_logicas_visibles": os.cpu_count()
    }
    for path, pattern, key in [
        ("/etc/os-release", r'^PRETTY_NAME=(.*)$', "sistema_operativo"),
        ("/proc/cpuinfo", r"^model name\s*:\s*(.+)$", "modelo_CPU")
    ]:
        try:
            match = re.search(pattern, Path(path).read_text(), re.M)
            if match:
                result[key] = match.group(1).strip('"')
        except OSError:
            pass
    try:
        match = re.search(
            r"^MemTotal:\s+(\d+)\s+kB",
            Path("/proc/meminfo").read_text(), re.M
        )
        if match:
            result["RAM_total_host_MiB"] = round(int(match.group(1)) / 1024, 2)
    except OSError:
        pass
    path = Path("/sys/fs/cgroup/cgroup.controllers")
    result["interfaz_cgroups_v2_presente"] = path.is_file()
    if path.is_file():
        result["controladores"] = path.read_text().strip()
    return result

def compose_info(root, sources):
    rows = []
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        data = stable(path)
        sources.append({"path": name, "sha256": sha(data), "kind": "compose"})
        active = False
        service = None
        for line in data.decode("utf-8").splitlines():
            if re.match(r"^services:\s*(?:#.*)?$", line):
                active = True
                continue
            if active and re.match(r"^[A-Za-z][\w-]*:", line):
                active = False
            if not active:
                continue
            match = re.match(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
            if match:
                service = match.group(1)
                rows.append([service, "Imagen no reconocida en el extracto"])
            image = re.match(r"^\s+image:\s*(.+)$", line)
            if image and service and rows:
                rows[-1][1] = image.group(1).strip()
    return rows

def dataset_info(root, sources, notes):
    rows = []
    for name in ("data/orders-42.jsonl.manifest.json", "data/equivalence-42.json"):
        path = root / name
        if not path.is_file():
            notes.append("Fuente pendiente: " + name)
            continue
        try:
            data = stable(path)
            obj = json.loads(data)
            sources.append({"path": name, "sha256": sha(data), "kind": "dataset_evidence"})
            rows.append([name, "SHA-256: " + sha(data)])
            allowed = {
                "seed", "documents", "document_count", "num_documents",
                "total_documents", "total_items", "item_count", "status",
                "verified_documents", "logical_hash", "logical_sha256", "sha256"
            }
            for key, value in leaves(obj):
                if (
                    key.rsplit(".", 1)[-1].lower() in allowed
                    and isinstance(value, (str, int, float, bool))
                ):
                    rows.append([key, value])
        except (OSError, ValueError, UnicodeError) as exc:
            notes.append("No se interpretó " + name + ": " + str(exc))
    return rows[:16]

def plans_info(root, out, run_docs, sources, notes):
    documents = [item for group in run_docs.values() for item in group]
    known = {path for path, _ in documents}
    for directory in (root / "plans", root / "results"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.json")):
            if path in known or path.is_symlink() or not re.search(r"explain|plan", path.name, re.I):
                continue
            try:
                documents.append((path, json.loads(stable(path))))
                known.add(path)
            except (OSError, ValueError, UnicodeError):
                continue
    found = []
    for path, document in documents:
        for obj in objects(document):
            if isinstance(obj.get("Plan"), dict):
                nodes = []
                stack = [obj["Plan"]]
                while stack:
                    node = stack.pop()
                    if not isinstance(node, dict):
                        continue
                    if "Node Type" in node:
                        nodes.append(node)
                    stack.extend(reversed(node.get("Plans", [])))
                if any("Actual Rows" in node for node in nodes):
                    found.append(("postgresql", path, nodes, obj))
                    break
            if isinstance(obj.get("executionStats"), dict):
                found.append(("mongodb", path, [], obj["executionStats"]))
                break
    blocks = []
    for engine, path, nodes, obj in found[:3]:
        data = stable(path)
        sources.append({"path": rel(root, path), "sha256": sha(data), "kind": "existing_plan"})
        blocks.extend([
            r"\subsection*{Artefacto existente: " + cell(rel(root, path)) + "}",
            "La pertenencia exacta a la ventana consolidada debe cotejarse. "
            "No se usa para completar spill de otra ejecución."
        ])
        if engine == "postgresql":
            rows = [[
                node.get("Node Type", "ND"),
                node.get("Actual Rows", "ND"),
                node.get("Actual Loops", "ND"),
                node.get("Sort Method", "ND"),
                str(node.get("Temp Read Blocks", "ND")) + "/" +
                str(node.get("Temp Written Blocks", "ND"))
            ] for node in nodes[:14]]
            blocks.extend([
                r"{\scriptsize",
                table(
                    ["Nodo", "Filas", "Loops", "Ordenamiento", "Temp R/W"],
                    rows, r"p{0.24\linewidth}rrp{0.22\linewidth}p{0.15\linewidth}"
                ), "}"
            ])
        else:
            stages = sorted({
                value for key, value in leaves(obj)
                if key.rsplit(".", 1)[-1] == "stage" and isinstance(value, str)
            })
            rows = [
                ["nReturned", obj.get("nReturned", "ND")],
                ["totalDocsExamined", obj.get("totalDocsExamined", "ND")],
                ["totalKeysExamined", obj.get("totalKeysExamined", "ND")],
                ["executionTimeMillis", obj.get("executionTimeMillis", "ND")],
                ["Etapas reconocidas", ", ".join(stages) or "ND"]
            ]
            blocks.append(table(
                ["Campo", "Valor"], rows, r"p{0.42\linewidth}p{0.47\linewidth}"
            ))
        blocks.append("ND significa campo no presente o no reconocido, no cero.")
    if not blocks:
        notes.append("No se reconocieron planes JSON ejecutados; revisar otros formatos.")
    write(
        out / "planes.tex",
        "\n".join(blocks) or
        r"\pendiente{No se reconocieron planes ejecutados. No se ejecutaron consultas "
        r"para generarlos. Revisar posibles planes de texto u otros formatos.}"
    )
    return len(found)

def make_figures(out, selected, run_docs, notes):
    write(out / "series.tex", r"\pendiente{No se reconoció una serie RSS con identidad suficiente.}")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        notes.append("Figuras no generadas: falta matplotlib; no se instaló software.")
        return []
    items = sorted(selected, key=lambda item: item["engine"])
    if not items:
        return []
    colors = {"mongodb": "#196b3a", "postgresql": "#245a9a"}
    created = []
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 5.4))
    fields = [
        ("throughput_qps", "Throughput (QPS)"),
        ("latency_p50_ms", "P50 (ms)"),
        ("latency_p95_ms", "P95 (ms)"),
        ("latency_p99_ms", "P99 (ms)")
    ]
    for ax, (field, label) in zip(axes.flat, fields):
        values = [item["values"][field] for item in items]
        ax.bar(
            [NAMES[item["engine"]] for item in items], values,
            color=[colors[item["engine"]] for item in items], width=0.5
        )
        ax.set_ylabel(label)
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=0.2)
        ax.margins(y=0.18)
        for index, value in enumerate(values):
            ax.annotate(
                format(value, ".7g"), (index, value), xytext=(0, 4),
                textcoords="offset points", ha="center", fontsize=8
            )
    fig.suptitle("Q1 / Perfil A / C=1 / R=1: observaciones individuales")
    fig.tight_layout()
    fig.savefig(out / "comparacion.pdf", bbox_inches="tight")
    plt.close(fig)
    created.append("comparacion.pdf")
    for filename, xfield, yfield, xlabel, ylabel in [
        ("p99.pdf", None, "latency_p99_ms", "Concurrencia", "P99 (ms)"),
        ("throttling.pdf", "throughput_qps", "cpu_throttled_seconds",
         "Throughput (QPS)", "CPU throttling (s)")
    ]:
        fig, ax = plt.subplots(figsize=(8.4, 3))
        for item in items:
            x = 1 if xfield is None else item["values"][xfield]
            ax.scatter(
                [x], [item["values"][yfield]], s=65,
                label=NAMES[item["engine"]], color=colors[item["engine"]]
            )
        if xfield is None:
            ax.set_xticks([1, 10, 50])
            ax.set_xlim(0, 52)
            ax.text(
                0.98, 0.95, "C=10 y C=50: sin observaciones incorporadas",
                transform=ax.transAxes, ha="right", va="top", fontsize=8
            )
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title("Puntos reales; sin ajuste ni interpolación")
        ax.grid(alpha=0.2)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / filename, bbox_inches="tight")
        plt.close(fig)
        created.append(filename)
    fig, ax = plt.subplots(figsize=(8.4, 3))
    values = [item["values"]["max_rss_mb"] for item in items]
    ax.bar(
        [NAMES[item["engine"]] for item in items], values,
        color=[colors[item["engine"]] for item in items], width=0.5
    )
    ax.set_ylabel("Valor original de max_rss_mb")
    ax.set_title("RSS máximo / Q1 / Perfil A / C=1 / R=1")
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    ax.margins(y=0.18)
    for index, value in enumerate(values):
        ax.annotate(
            format(value, ".8g"), (index, value), xytext=(0, 4),
            textcoords="offset points", ha="center"
        )
    fig.tight_layout()
    fig.savefig(out / "rss.pdf", bbox_inches="tight")
    plt.close(fig)
    created.append("rss.pdf")

    blocks = []
    for item in items:
        engine = item["engine"]
        candidates = []
        for source, obj in run_docs.get(engine, []):
            if not isinstance(obj, dict) or not isinstance(obj.get("data"), dict):
                continue
            for series in obj["data"].get("result", []):
                if not isinstance(series, dict):
                    continue
                metric = series.get("metric", {})
                if metric.get("__name__") != "container_memory_rss":
                    continue
                identity = " ".join(str(metric.get(key, "")) for key in (
                    "name", "container", "container_label_com_docker_compose_service"
                )).lower()
                if ("mongo" if engine == "mongodb" else "postgres") not in identity:
                    continue
                samples = []
                for sample in series.get("values", []):
                    try:
                        timestamp = float(sample[0])
                        value = number(sample[1])
                        if math.isfinite(timestamp):
                            samples.append((timestamp, value))
                    except (ValueError, TypeError, IndexError):
                        continue
                if len(samples) >= 2:
                    candidates.append((source, sorted(samples)))
        if len(candidates) != 1:
            continue
        source, samples = candidates[0]
        fig, ax = plt.subplots(figsize=(8.4, 3))
        ax.plot(
            [t - samples[0][0] for t, _ in samples],
            [v for _, v in samples], color=colors[engine], linewidth=1
        )
        ax.set_xlabel("Segundos desde la primera muestra almacenada")
        ax.set_ylabel("container_memory_rss (bytes)")
        ax.set_title(NAMES[engine] + ": serie existente; ventana por cotejar")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        filename = "serie-" + engine + ".pdf"
        fig.savefig(out / filename, bbox_inches="tight")
        plt.close(fig)
        created.append(filename)
        blocks.append(
            r"\reportfigure{" + filename + "}{Serie RSS original. "
            "No se equipara automáticamente con la ventana de medición. Fuente: " +
            cell(str(source.relative_to(item["_run"]))) +
            "}{fig:serie-" + engine + "}"
        )
    if blocks:
        write(out / "series.tex", "\n".join(blocks))
    else:
        notes.append("No se fabricaron series temporales a partir de máximos RSS.")
    return created

MAIN = r'''
\documentclass[11pt,letterpaper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[spanish,es-tabla]{babel}
\usepackage[margin=2.4cm,headheight=15pt]{geometry}
\usepackage{lmodern,microtype,amsmath}
\usepackage{graphicx,booktabs,longtable,tabularx,array}
\usepackage{xcolor,listings,fancyhdr}
\usepackage[hidelinks]{hyperref}
\usepackage{url}
\urlstyle{same}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.35em}
\setlength{\emergencystretch}{4em}
\renewcommand{\arraystretch}{1.12}
\setcounter{tocdepth}{2}
\setcounter{secnumdepth}{2}
\input{informe-activo.tex}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small MongoDB y PostgreSQL JSONB}
\fancyhead[R]{\small Informe parcial}
\fancyfoot[C]{\thepage}
\hypersetup{
 pdftitle={MongoDB y PostgreSQL JSONB: informe académico parcial},
 pdfauthor={Jesel Moreno Zuniga}
}
\newcommand{\pendiente}[1]{%
 \par\smallskip\noindent
 \fbox{\parbox{0.94\linewidth}{\small\textbf{Pendiente:} #1}}
 \par\smallskip}
\lstset{
 basicstyle=\ttfamily\scriptsize,
 breaklines=true,columns=fullflexible,keepspaces=true,
 showstringspaces=false,frame=single,
 aboveskip=0.6em,belowskip=0.6em
}
\newcommand{\reportfigure}[3]{%
 \IfFileExists{\artifactdir/#1}{%
 \begin{figure}[!htbp]\centering
 \includegraphics[width=0.92\linewidth]{\artifactdir/#1}
 \caption{#2}\label{#3}\end{figure}
 }{\pendiente{Figura no generada. #2}}}
\begin{document}
\begin{titlepage}\centering
{\Large Universidad Politécnica de Chiapas\par}
\vspace{0.6cm}
{\large Licenciatura en Ingeniería en Tecnologías de la Información
e Innovación Digital\par}
\vspace{0.7cm}
{\large Base de datos en la nube\par}
\vspace{0.9cm}
{\LARGE\bfseries Análisis comparativo del rendimiento de MongoDB
y PostgreSQL JSONB bajo restricciones de CPU y memoria
en agregaciones de documentos JSON anidados\par}
\vspace{0.7cm}
{\Large Informe académico parcial\par}
\vspace{0.7cm}
\begin{tabularx}{0.92\linewidth}{rX}
Estudiante: & Jesel Moreno Zuniga\\
Grupo: & 7B\\
Profesor: & Horacio Irán Solís Cisneros\\
Actividad: & 2026.C3.EVA02
\end{tabularx}
\vfill
{1 de noviembre de 2026\par}
\smallskip
\begin{minipage}{0.91\linewidth}\small
La matriz prevista comprende 108 ejecuciones. El responsable confirma
dos mediciones definitivas elegibles. El documento distingue la evidencia
cotejada localmente, la información comunicada y los pendientes.
\end{minipage}
\end{titlepage}

\section*{Resumen}
Se estudia el comportamiento de MongoDB y PostgreSQL JSONB en
agregaciones sobre 500\,000 documentos JSON anidados. El diseño incluye
tres perfiles de CPU y memoria, dos consultas, tres concurrencias y
tres repeticiones, para 108 ejecuciones previstas en la matriz base.
El protocolo establece calentamiento de 60 segundos, medición de
300 segundos y enfriamiento de 60 segundos.

El responsable confirma dos mediciones definitivas elegibles para Q1,
perfil A, concurrencia 1 y repetición 1. Las tablas documentan su cotejo
contra CSV y archivos de commit existentes. Se registran throughput,
percentiles, CPU throttling, RSS máximo, spill y estado de ejecución,
sin completar datos ausentes con cero.

El alcance es descriptivo: una observación por motor no permite inferir
variación entre repeticiones, efectos de concurrencia o superioridad
general. Se conserva la limitación del índice textual de PostgreSQL
frente al cast temporal de Q2. También se documenta que la reutilización
del preflight se bloqueó al cambiar de motor, sin atribuir un ahorro
de tiempo no demostrado.

\textbf{Palabras clave:} MongoDB, JSONB, agregaciones, cgroups v2,
latencia, RSS, throttling, reproducibilidad.
\tableofcontents
\clearpage

\section*{Introducción y justificación}
\addcontentsline{toc}{section}{Introducción y justificación}
El soporte JSON en sistemas relacionales y las bases orientadas a
documentos permiten formular agregaciones sobre estructuras similares.
Sin embargo, la equivalencia funcional no implica igualdad de planes,
representación física o administración de memoria. Una comparación
defendible requiere conservar la fuente de datos, la semántica y las
condiciones que explican cada observación.

Este trabajo examina dos cargas: desanidado y agrupamiento de ítems,
y filtrado temporal con ordenamiento y Top-K. La restricción explícita
de CPU y memoria permite plantear preguntas sobre capacidad, latencia
y trabajo temporal, sin asumir que una sola cifra representa todo el
comportamiento de un motor.

La entrega es parcial. Las operaciones ejecutadas dentro de una ventana
no son repeticiones independientes del escenario. Los pilotos previos,
las mediciones definitivas y los escenarios pendientes deben mantenerse
separados. Se distinguen hechos comunicados por el responsable,
archivos examinados durante la generación y limitaciones pendientes.

\textbf{Objetivo general.} Comparar MongoDB y PostgreSQL JSONB mediante
agregaciones sobre 500\,000 documentos anidados bajo cuotas de CPU y
memoria controladas.

\textbf{Objetivos específicos.} Verificar equivalencia de datos;
conservar consultas originales; medir rendimiento y señales de recursos;
describir índices y planes existentes; y delimitar el alcance de las
conclusiones de una matriz incompleta.

\input{\artifactdir/01-entorno.tex}
\input{\artifactdir/02-metodologia.tex}
\input{\artifactdir/03-resultados.tex}
\input{\artifactdir/04-graficas.tex}
\input{\artifactdir/05-planes.tex}
\input{\artifactdir/06-interpretacion.tex}
\input{\artifactdir/07-recomendaciones.tex}
\input{\artifactdir/08-conclusiones.tex}
\clearpage
\addcontentsline{toc}{section}{Referencias}
\begin{thebibliography}{9}
\bibitem{pgmemory} PostgreSQL Global Development Group. \textit{PostgreSQL 18: Resource Consumption}. \url{https://www.postgresql.org/docs/18/runtime-config-resource.html}.
\bibitem{pgexplain} PostgreSQL Global Development Group. \textit{PostgreSQL 18: Using EXPLAIN}. \url{https://www.postgresql.org/docs/18/using-explain.html}.
\bibitem{pgindex} PostgreSQL Global Development Group. \textit{PostgreSQL 18: Indexes on Expressions}. \url{https://www.postgresql.org/docs/18/indexes-expressional.html}.
\bibitem{wiredtiger} MongoDB. \textit{WiredTiger Storage Engine}. \url{https://www.mongodb.com/docs/manual/core/wiredtiger/}.
\bibitem{mongolimits} MongoDB. \textit{Aggregation Pipeline Limits}. \url{https://www.mongodb.com/docs/manual/core/aggregation-pipeline-limits/}.
\bibitem{docker} Docker. \textit{Resource constraints}. \url{https://docs.docker.com/engine/containers/resource_constraints/}.
\bibitem{kernel} The Linux Kernel documentation. \textit{Control Group v2}. \url{https://docs.kernel.org/admin-guide/cgroup-v2.html}.
\end{thebibliography}
\appendix
\input{\artifactdir/09-anexos.tex}
\end{document}
'''

SECTIONS = {
"01-entorno.tex": r'''
\section{Especificaciones del host, Docker y observabilidad}
\subsection{Equipo y sistema operativo}
\input{\artifactdir/host.tex}
La captura corresponde al momento de generación del informe. Aunque
se realice en el equipo experimental, no demuestra la frecuencia,
disponibilidad de memoria o carga exacta durante las mediciones.
Las CPU lógicas visibles no deben confundirse con núcleos físicos.

El entorno comunicado utiliza Kubuntu nativo, Docker Engine y Compose,
con cgroups v2. Las versiones comunicadas son MongoDB 9.0.4 y
PostgreSQL 18.6. Una etiqueta de imagen, una versión de biblioteca y la
versión del servidor son evidencias diferentes. Debe cotejarse esa
correspondencia con los artefactos de la cohorte.

\subsection{Arquitectura y servicios}
\input{\artifactdir/compose.tex}
Los servicios e imágenes se extraen de archivos Compose existentes.
Son configuración declarada, no comprobación de salud, persistencia
o límites efectivos. El generador no invoca Docker.

El esquema describe responsabilidades conceptuales y no una topología
de red inferida.
\begin{center}
\begin{tabular}{c}
\fbox{\parbox{0.79\linewidth}{\centering JSONL, manifiesto y equivalencia}}\\[0.2cm]
$\downarrow$\\[0.1cm]
\fbox{\parbox{0.79\linewidth}{\centering Runner: consulta, perfil, concurrencia y ventanas}}\\[0.2cm]
$\downarrow$\\[0.1cm]
\fbox{\parbox{0.34\linewidth}{\centering MongoDB}}\quad
\fbox{\parbox{0.34\linewidth}{\centering PostgreSQL JSONB}}\\[0.2cm]
$\downarrow$\\[0.1cm]
\fbox{\parbox{0.79\linewidth}{\centering CSV, telemetría, preflight y commit}}
\end{tabular}
\end{center}

\subsection{Perfiles de recursos}
\begin{table}[!htbp]\centering
\caption{Perfiles oficiales comunicados.}\label{tab:perfiles}
\begin{tabular}{lrr}\toprule
Perfil & CPU & Memoria (MiB)\\\midrule
\texttt{PROFILE\_A\_BASELINE} & 4 & 4096\\
\texttt{PROFILE\_B\_MEDIUM} & 2 & 2048\\
\texttt{PROFILE\_C\_SEVERE} & 1 & 1024\\
\bottomrule\end{tabular}
\end{table}
Docker y cgroups permiten imponer restricciones \cite{docker,kernel}.
Una cuota equivalente a cuatro CPU no acredita reserva de cuatro
núcleos ni exclusividad. La presencia de cgroups v2 tampoco sustituye
los límites efectivos del cgroup de cada motor.

El límite de memoria no es RSS máximo. La ausencia de swap no equivale
automáticamente al cumplimiento literal de otra opción de swappiness;
las adaptaciones requieren registro.

\subsection{Observabilidad y unidades}
La arquitectura comunicada utiliza Prometheus, cAdvisor y Node Exporter.
La interpretación exige identificar contenedor, etiquetas, intervalo y
ventana. Una serie vacía no equivale a cero. Los contadores requieren
deltas y control de resets.

RSS, working set y uso total del cgroup son señales distintas.
La columna se llama \texttt{max\_rss\_mb}, mientras que la comunicación
reciente usa MiB. Se conservan valores originales, sin convertir ni
renombrar la unidad silenciosamente. La fórmula del recolector y su
correspondencia con la cohorte deben cotejarse.
''',
"02-metodologia.tex": r'''
\section{Metodología y baseline}
\subsection{Preguntas de investigación M1/M2/M3}
Las preguntas de lectura se refieren a rendimiento, recursos y
comportamiento bajo concurrencia. La identificación normativa M1/M2/M3
debe conservar la formulación de los playbooks. Los extractos reconocidos
se presentan sin inventar una correspondencia.
\input{\artifactdir/preguntas.tex}

\subsection{Generación}
El responsable confirma 500\,000 documentos, semilla 42 y
1\,499\,443 ítems, aproximadamente tres por orden. La estructura incluye
órdenes, clientes, ubicaciones, productos, pagos y metadatos.
El desanidado produce una cardinalidad intermedia distinta del número
de documentos.

La semilla favorece repetibilidad, pero también importan generador y
dependencias. Por ello se conservan manifiesto y hashes. Las distribuciones
no se deducen de una descripción general.

SHA-256 comunicado del JSONL:
\begin{quote}\small
\nolinkurl{9fecf656a02cf6d369517ae4d59f47072e4de4025ae9db6280611347fb557afb}
\end{quote}
Hash lógico comunicado:
\begin{quote}\small
\nolinkurl{3490c8c2b9a58f58ee69849dd55f00d556e64456168964d0cf74262e95cc7715}
\end{quote}
\input{\artifactdir/dataset.tex}

\subsection{Carga y equivalencia}
Se comunican 500\,000 documentos importados en cada motor y equivalencia
lógica completa PASS. No implica igualdad binaria entre JSONL, BSON y
JSONB ni igualdad de espacio físico.

La igualdad de documentos no sustituye validar resultados de Q1/Q2.
Tipos, fechas, orden y empates requieren los controles del proyecto.
Importación y equivalencia son precondiciones, no resultados de rendimiento.

\subsection{Índices y aceptación}
MongoDB dispone, según el responsable, de \texttt{\_id} y de índices
simples en \texttt{timestamp} y \texttt{order\_id}.
PostgreSQL tiene PRIMARY KEY en \texttt{id} y B-Tree textual en
\texttt{data\textgreater\textgreater{}'timestamp'}.

Q2 convierte ese texto a \texttt{timestamptz}. Se distinguen:
\begin{enumerate}
\item existencia, definición y validez física;
\item compatibilidad con el predicado;
\item utilización efectiva en un plan;
\item aprobación académica.
\end{enumerate}
La expresión consultada importa para un índice sobre expresiones
\cite{pgindex}. La aceptación del responsable no demuestra uso,
compatibilidad con el cast ni aprobación del profesor.
La limitación permanece aunque las mediciones actuales sean Q1.

\subsection{Consultas}
Q1 desanida ítems, filtra \texttt{price > 50}, calcula subtotales y
agrupa por país y categoría, produciendo sumatoria, promedio y conteo.
Deben mantenerse expresiones y tipos originales.

Q2 selecciona órdenes completadas en un rango temporal, ordena por
importe final descendente y recupera Top-1000. No hay resultados
definitivos Q2 incorporados.

Los extractos proceden de archivos reales y se conservan fuentes completas.
La selección automática no acredita por sí sola su invocación por el runner.
\input{\artifactdir/consultas.tex}

\subsection{Variantes, matriz y protocolo}
La matriz base selecciona \texttt{allow\_disk\_false} y
\texttt{work\_mem\_4mb}. Las variantes \texttt{allow\_disk\_true}
y \texttt{work\_mem\_64mb} se mantienen separadas. No son presupuestos
internos equivalentes de memoria.

El diseño comprende:
\[
3\text{ perfiles}\times2\text{ motores}\times2\text{ consultas}
\times3\text{ concurrencias}\times3\text{ repeticiones}=108.
\]
Las concurrencias son 1, 10 y 50. Una repetición por escenario comprende
36 ejecuciones y no completa el protocolo.

Se establecen 60 s de warmup, 300 s de medición y 60 s de cooldown.
La duración total incluye preparación y controles: los 53 minutos y
38 segundos comunicados para PostgreSQL no sustituyen la ventana ni
se usan como denominador de QPS.

Debe conservarse el criterio del runner sobre operaciones en los límites
de ventana. No se reconstruye la latencia media desde la inversa de QPS
ni se inventa conteo de operaciones.

\subsection{Cachés y secuencia}
El warmup no acredita estabilización. Caché del motor, caché del sistema
operativo y conexiones son controles distintos. Un comando en un script
no demuestra que se ejecutara en cada repetición.

Este generador no limpia cachés, reinicia servicios ni ejecuta operaciones
privilegiadas. Las condiciones deben cotejarse con evidencia existente.

\subsection{Preflight e incidencia}
El responsable confirma 135 pruebas automatizadas aprobadas para la
optimización. La reutilización se bloqueó al cambiar de motor.
Los casos probados y el intento de reutilización son evidencias distintas.

No hay comparación temporal válida antes/después. No se afirma ahorro
experimental. Se registra la incidencia sin modificar resultados
comprometidos ni suprimir controles.

\subsection{Contrato}
La cabecera conserva 14 columnas:
\begin{lstlisting}
timestamp_epoch,engine,profile,query_id,concurrency,run_number,throughput_qps,latency_p50_ms,latency_p95_ms,latency_p99_ms,cpu_throttled_seconds,max_rss_mb,disk_spill,status
\end{lstlisting}
\texttt{spill} puede coexistir con elegibilidad. Las ausencias no se
completan con cero. La confirmación del responsable se distingue del
reconocimiento automático de campos en las evidencias.
''',
"03-resultados.tex": r'''
\section{Resultados consolidados}
\subsection{Cobertura y procedencia}
El responsable confirma dos mediciones elegibles Q1/A/C1/R1, una por
motor. La cobertura y el cotejo local se distinguen.
\input{\artifactdir/cobertura.tex}
\input{\artifactdir/procedencia.tex}

La asociación de CSV y commit por directorio no se presenta como
verificación criptográfica cuando no se reconoce el hash correspondiente.

\subsection{Valores originales}
Las tablas conservan los decimales del CSV y no se corrigen para
coincidir con un resumen redondeado.
\input{\artifactdir/metricas.tex}
Spill no cuantifica bytes o número de volcados. El throttling positivo
es una señal de la ventana, no una explicación causal completa.

\subsection{Resumen comunicado}
\begin{table}[!htbp]\centering\small
\caption{Cifras comunicadas y redondeadas; no son nuevas mediciones.}
\begin{tabular}{lrr}\toprule
Métrica & MongoDB & PostgreSQL\\\midrule
QPS & 0.5467 & 0.4167\\
P50 (ms) & 1818.41 & 2353.83\\
P95 (ms) & 1861.30 & 2562.62\\
P99 (ms) & 1902.25 & 2800.77\\
RSS comunicado como MiB & 1026.65 & 108.22\\
Throttling (s) & 0 & 0.083895\\
Spill & 0 & 1\\
Consultas completadas comunicadas & 164 & 125\\
\bottomrule\end{tabular}
\end{table}
Los conteos se identifican como comunicados, sin deducirlos de QPS.
La unidad RSS debe reconciliarse con el recolector.

\subsection{Comparación descriptiva}
\input{\artifactdir/comparacion.tex}
Cada motor aporta una observación. Las operaciones comparten condiciones
y no son réplicas independientes. No se presentan pruebas de significancia
o intervalos no sustentados.

\subsection{Pilotos y pendientes}
Los pilotos de 15 segundos precedieron a los índices secundarios completos.
Se mantienen como exploración de funcionamiento y telemetría.

No se incorporan Q2, B/C ni C10/C50. Las otras 106 celdas no tienen
resultado elegible comunicado en esta entrega. Pendiente, bloqueada e
incompleta son estados distintos que requieren registros reales.
''',
"04-graficas.tex": r'''
\section{Análisis gráfico}
Las figuras usan valores leídos de los CSV admitidos. No completan
escenarios ni introducen ajustes o intervalos ficticios.
\reportfigure{comparacion.pdf}
{Throughput y percentiles individuales Q1/A/C1/R1. No son promedios
entre repeticiones.}{fig:comparacion}
P50, P95 y P99 son resúmenes de una ventana, no tres réplicas.
\reportfigure{p99.pdf}
{P99 frente a concurrencia. Solo C=1 tiene observaciones.}{fig:p99}
\reportfigure{throttling.pdf}
{Throttling frente a QPS. Dos puntos no sustentan una relación causal.}
{fig:throttling}
\reportfigure{rss.pdf}
{RSS máximo original. No se convierte MB a MiB sin cotejar el recolector.}
{fig:rss}
Un máximo no reconstruye evolución temporal. Las series se incluyen solo
si existen muestras e identidad suficiente. Su intervalo no se equipara
automáticamente con la ventana de medición.
\input{\artifactdir/series.tex}
''',
"05-planes.tex": r'''
\section{Planes de ejecución}
La evidencia prevista es \texttt{explain("executionStats")} y
\texttt{EXPLAIN (ANALYZE, BUFFERS)}. Solo se utilizan artefactos existentes;
no se ejecutan consultas para completarlos.
\input{\artifactdir/planes.tex}

\subsection{Escaneos y cardinalidades}
Escaneo secuencial, índice y filtro representan trabajo distinto.
Filas estimadas y reales, loops y cardinalidades intermedias aportan
contexto. La existencia del índice no acredita su elección.

En Q1 desanidar puede ampliar el flujo hacia filtro y agregación.
El total de ítems no determina grupos ni costo del operador.
En Q2 la selectividad condiciona el ordenamiento sin demostrar una
ruta específica.

\subsection{Agregación y buffers}
En PostgreSQL, método de ordenamiento y bloques temporales describen el
plan cuando están presentes. Buffers no son RSS y costos estimados no
son tiempos observados \cite{pgexplain}. Ausencia de campo no significa cero.

En MongoDB, documentos y claves examinados describen acceso. No se
atribuyen etapas ausentes ni se trasladan campos entre versiones.

\subsection{Límites de atribución}
Un EXPLAIN adicional ejecuta su propio trabajo y no completa spill de
otra ventana. El estado CSV no identifica operador ni tamaño temporal.
Un plan Q1 no demuestra Q2 o uso del índice para el cast temporal.
''',
"06-interpretacion.tex": r'''
\section{Interpretación y amenazas a la validez}
\subsection{Alcance}
Q1/A/C1/R1 no permite generalizar a otros perfiles, concurrencias o
consultas. Las operaciones comparten procesos y cachés, de modo que no
reemplazan repeticiones independientes.

Promediar percentiles no produce un percentil global. La inversa de QPS
no sustituye necesariamente la latencia media, por los límites y
criterios de contabilización.

\subsection{CPU}
PostgreSQL comunica 0.083895 segundos de throttling y MongoDB cero.
La señal positiva no demuestra que CPU explique la diferencia temporal.
Cero no excluye espera de E/S u otros cuellos de botella.

La cuota define capacidad permitida y no uso constante. Sin B/C ni
C10/C50 no se caracteriza respuesta a cuotas menores o saturación.

\subsection{Memoria}
RSS exige revisar alcance y unidades. No representa automáticamente toda
la memoria atribuible: memoria compartida, procesos y caché del host
pueden tener coberturas diferentes.

PostgreSQL distingue buffers compartidos de memoria de operaciones.
\texttt{work\_mem} no es un límite global y puede multiplicarse con
sesiones y operaciones \cite{pgmemory}. WiredTiger mantiene caché propia
e interactúa con la caché del sistema de archivos \cite{wiredtiger}.
Estas explicaciones no atribuyen por sí solas el RSS de las ventanas.

No se afirman tamaños internos sin configuración ni se suman señales
heterogéneas para fabricar una memoria total.

\subsection{Spill}
Las políticas y planes diferentes son explicaciones posibles del spill,
pero no demuestran causalidad. Se requiere evidencia del operador
y de la ventana para cuantificar trabajo temporal.

El permiso de disco de MongoDB condiciona etapas, sin obligarlas a
derramar \cite{mongolimits}. No equivale a \texttt{work\_mem}.
Las variantes se analizan separadamente.

\subsection{Índices y semántica}
La aceptación del responsable no transforma un índice textual en temporal.
La elegibilidad Q1 no demuestra la ruta de Q2. La equivalencia lógica
no obliga a estructuras internas iguales.

\subsection{Amenazas}
\begin{itemize}
\item \textbf{Interna:} orden, cachés, carga, límites, ventanas y resets.
\item \textbf{Constructo:} unidad RSS, spill, cálculo de QPS y errores.
\item \textbf{Comparación:} variantes, índices, versiones y planes.
\item \textbf{Externa:} un host, una semilla y dos consultas.
\item \textbf{Conclusión:} una repetición por motor no estima variabilidad.
\end{itemize}
Las 135 pruebas del preflight no son medición de ahorro temporal.
El bloqueo al cambiar de motor permanece como incidencia operativa.
''',
"07-recomendaciones.tex": r'''
\section{Recomendaciones para la nube}
Son criterios generales, no selección validada de proveedor o instancia.
\subsection{Dimensionamiento}
CPU y memoria deben contrastarse con throughput requerido, latencia,
estados y margen. Cuotas locales no equivalen automáticamente a vCPU
dedicadas, créditos o almacenamiento remoto.

RSS individual no define un mínimo seguro. No se recomienda reducir
memoria hasta el máximo observado ni aumentar CPU solo por throttling.
Deben contemplarse concurrencia, cachés y trabajo temporal.

\subsection{Concurrencia y escalabilidad}
Más clientes podrían aumentar colas sin mejorar QPS, pero no está
demostrado aquí. C10/C50 no reciben recomendaciones cuantitativas.

Escalar horizontalmente introduce coordinación, red y consistencia.
Los beneficios no se deducen de un contenedor local por motor.

\subsection{Selección del motor}
Q1 no representa toda la aplicación. Importan transacciones, escrituras,
modelo de datos, índices y operación. Dos observaciones no establecen
un ganador general. Q2 requiere evaluación y exposición de la limitación
del índice textual.

\subsection{Memoria y almacenamiento}
La memoria por operación debe revisarse con sesiones, límite del
contenedor y almacenamiento temporal. Aumentar parámetros puede trasladar
presión desde disco a memoria. Spill no implica automáticamente fallo;
su ausencia tampoco garantiza una ejecución óptima.

\subsection{Observabilidad}
Deben conservarse identificadores, commit, consultas, variantes, límites
y cobertura. Los paneles deben distinguir ausencia de datos y cero.
La reutilización del preflight requiere contexto compatible; su bloqueo
no permite afirmar ahorro demostrado.
''',
"08-conclusiones.tex": r'''
\section*{Conclusiones}
\addcontentsline{toc}{section}{Conclusiones}
La importación de 500\,000 documentos y equivalencia completa son
controles de preparación, no resultados de rendimiento.

La entrega se limita a dos mediciones comunicadas Q1/A/C1/R1, con cotejo
local y sus límites registrados por separado. No representa 108 ejecuciones.

MongoDB comunica mayor QPS y menores percentiles; PostgreSQL comunica
menor RSS, throttling positivo y spill. No establecen superioridad general
ni causalidad. RSS requiere reconciliar unidad y alcance.

No se incorporan Q2, B/C ni C10/C50 ni se infieren tendencias. Los pilotos
se mantienen separados. El índice textual conserva su limitación:
existencia, compatibilidad, uso y aprobación son condiciones diferentes.

La optimización del preflight tiene 135 pruebas aprobadas según el
responsable, pero su reutilización se bloqueó al cambiar de motor.
No se atribuye ahorro temporal sin comparación válida.

Las actualizaciones deben incorporar solo evidencias reales y revisar
conclusiones conforme a la cobertura efectivamente alcanzada.
''',
"09-anexos.tex": r'''
\section{Reproducibilidad y auditoría}
\texttt{auditoria.json} conserva fuentes, hashes, selección y compilación.
\texttt{ESTADO\_ENTREGABLE.md} identifica cumplidos y pendientes.
El reporte anterior se respalda en \texttt{reports/latex-backups/}.

Se usa una carpeta nueva de recursos para evitar figuras antiguas.
La asociación CSV/commit por directorio no se presenta como vínculo
criptográfico si este no se reconoce. Una declaración local negativa
impide admitir automáticamente la fila. La aprobación docente no se infiere.

Las fuentes originales de consultas se conservan sin cambios. Los
extractos visuales pueden representar caracteres mediante escapes.
Su selección no sustituye revisar las invocaciones reales del runner.

\section{Extractos documentales}
Son material de trazabilidad, no certificación integral de cumplimiento.
Deben revisarse junto con referencias P/S y decisiones vigentes.
\input{\artifactdir/extractos.tex}
'''
}

BIB = r'''
@misc{pgmemory,
 author={{PostgreSQL Global Development Group}},
 title={PostgreSQL 18: Resource Consumption},
 howpublished={\url{https://www.postgresql.org/docs/18/runtime-config-resource.html}}
}
@misc{pgexplain,
 author={{PostgreSQL Global Development Group}},
 title={PostgreSQL 18: Using EXPLAIN},
 howpublished={\url{https://www.postgresql.org/docs/18/using-explain.html}}
}
@misc{pgindex,
 author={{PostgreSQL Global Development Group}},
 title={PostgreSQL 18: Indexes on Expressions},
 howpublished={\url{https://www.postgresql.org/docs/18/indexes-expressional.html}}
}
@misc{wiredtiger,
 author={{MongoDB}},
 title={WiredTiger Storage Engine},
 howpublished={\url{https://www.mongodb.com/docs/manual/core/wiredtiger/}}
}
@misc{mongolimits,
 author={{MongoDB}},
 title={Aggregation Pipeline Limits},
 howpublished={\url{https://www.mongodb.com/docs/manual/core/aggregation-pipeline-limits/}}
}
@misc{docker,
 author={{Docker}},
 title={Resource constraints},
 howpublished={\url{https://docs.docker.com/engine/containers/resource_constraints/}}
}
@misc{kernel,
 author={{The Linux Kernel documentation}},
 title={Control Group v2},
 howpublished={\url{https://docs.kernel.org/admin-guide/cgroup-v2.html}}
}
'''

def metrics(out, selected):
    blocks = []
    provenance = []
    for item in selected:
        engine = item["engine"]
        row = item["row"]
        blocks.append(
            r"\subsubsection*{" + tex(NAMES[engine]) + ": Q1/A/C1/R1}"
        )
        rows = [
            ["Throughput (QPS)", row["throughput_qps"]],
            ["P50 (ms)", row["latency_p50_ms"]],
            ["P95 (ms)", row["latency_p95_ms"]],
            ["P99 (ms)", row["latency_p99_ms"]],
            ["CPU throttling (s)", row["cpu_throttled_seconds"]],
            ["RSS: columna max_rss_mb", row["max_rss_mb"]],
            ["Disk spill", row["disk_spill"]],
            ["Estado", row["status"]],
            ["Timestamp epoch original", row["timestamp_epoch"]]
        ]
        blocks.append(table(["Métrica", "Valor original"], rows, r"p{0.58\linewidth}r"))
        provenance.extend([
            [NAMES[engine] + ": CSV", item["csv"]],
            ["Fila de datos", item["row_number"]],
            ["SHA-256 CSV", item["csv_sha256"]],
            ["Commit", item["commit"]],
            ["SHA-256 commit", item["commit_sha256"]],
            ["Hash CSV reconocido en commit",
             "Sí" if item["csv_hash_recognized_in_commit"] else "No; asociación por directorio"],
            ["Elegibilidad", item["eligibility_provenance"]]
        ])
        (out / (engine + "-fuente.csv")).write_bytes(item["_csv_bytes"])
        (out / (engine + "-commit.json")).write_bytes(item["_commit_bytes"])
    write(
        out / "metricas.tex",
        "\n".join(blocks) or
        r"\pendiente{No se admitieron filas automáticamente. Revisar auditoria.json.}"
    )
    write(
        out / "procedencia.tex",
        table(["Elemento", "Procedencia"], provenance, r"p{0.34\linewidth}p{0.55\linewidth}")
        if provenance else r"\pendiente{Cotejo local de CSV y commit no completado.}"
    )
    write(out / "cobertura.tex", table(
        ["Concepto", "Cantidad"],
        [
            ["Ejecuciones planificadas", 108],
            ["Mediciones elegibles confirmadas por el responsable", 2],
            ["Filas cotejadas y admitidas por el generador", len(selected)],
            ["Otras celdas sin resultado elegible comunicado", 106]
        ], r"p{0.78\linewidth}r"
    ))
    by_engine = {item["engine"]: item for item in selected}
    if len(by_engine) == 2:
        mongo = by_engine["mongodb"]["values"]
        pg = by_engine["postgresql"]["values"]
        qps = (mongo["throughput_qps"] / pg["throughput_qps"] - 1) * 100
        p99 = pg["latency_p99_ms"] / mongo["latency_p99_ms"]
        text = (
            "En las ventanas leídas, el throughput de MongoDB fue " +
            tex(format(qps, ".2f")) + r"\% mayor que PostgreSQL. "
            "El cociente P99 PostgreSQL/MongoDB fue " + tex(format(p99, ".3f")) +
            ". Son cocientes descriptivos individuales, no estimaciones "
            "poblacionales ni evidencia causal."
        )
    else:
        text = r"\pendiente{No se derivan cocientes sin cotejar ambas mediciones.}"
    write(out / "comparacion.tex", text)

def backup(root, report, token):
    directory = root / "reports" / "latex-backups"
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / ("reporte-anterior-" + token + ".zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(report.rglob("*")):
            if path.is_symlink():
                raise RuntimeError("Enlace simbólico en el reporte: " + str(path))
            name = path.relative_to(root / "reports").as_posix()
            if path.is_file():
                bundle.write(path, name)
            elif path.is_dir():
                bundle.writestr(name + "/", "")
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError("Falló la comprobación del respaldo")
    return archive

def compile_pdf(report, out, notes):
    result = {"success": False, "pages": None, "visual_inspection": "pendiente"}
    if not shutil.which("pdflatex"):
        result["error"] = "Falta pdflatex; no se instaló software"
        notes.append(result["error"])
        return result
    build = out / "build"
    build.mkdir()
    build_name = build.relative_to(report).as_posix()
    result["build"] = str(build)
    latex = [
        "pdflatex", "-interaction=nonstopmode", "-halt-on-error",
        "-output-directory=" + build_name, "main.tex"
    ]
    commands = [latex, latex, latex]
    result["commands"] = []
    for index, command in enumerate(commands, 1):
        process = subprocess.run(
            command, cwd=report, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, errors="replace"
        )
        write(build / ("comando-" + str(index) + ".txt"), process.stdout)
        result["commands"].append({"argv": command, "returncode": process.returncode})
        if process.returncode:
            result["error"] = "Falló " + " ".join(command)
            notes.append(result["error"])
            return result
    log = (build / "main.log").read_text(encoding="utf-8", errors="replace")
    result["unresolved_references"] = bool(re.search(
        r"undefined references|undefined citations|Reference .+ undefined|Citation .+ undefined",
        log, re.I
    ))
    result["overfull"] = re.findall(r"Overfull \\[hv]box[^\n]*", log)
    pdf = build / "main.pdf"
    if not pdf.is_file():
        result["error"] = "No se produjo PDF"
        return result
    if shutil.which("pdfinfo"):
        process = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
        match = re.search(r"^Pages:\s+(\d+)", process.stdout, re.M)
        if match:
            result["pages"] = int(match.group(1))
    if result["unresolved_references"] or result["overfull"]:
        result["error"] = (
            "PDF en build pendiente de revisar referencias o Overfull; "
            "no se sustituyó main.pdf"
        )
        notes.append(result["error"])
        return result
    temporary = report / ("main-nuevo-" + uuid4().hex + ".pdf")
    shutil.copy2(pdf, temporary)
    os.replace(temporary, report / "main.pdf")
    result["success"] = True
    if result["pages"] is not None and not 12 <= result["pages"] <= 18:
        notes.append(
            "Extensión: " + str(result["pages"]) +
            " páginas, fuera del objetivo orientativo 12–18; no se añadió relleno."
        )
    return result

class Checks(unittest.TestCase):
    def test_header(self):
        with self.assertRaises(ValueError):
            parse_csv(b"engine,status\nmongodb,ok\n")
    def test_missing(self):
        with self.assertRaises(ValueError):
            number("")
    def test_nonfinite(self):
        for value in ("nan", "inf", "-1"):
            with self.assertRaises(ValueError):
                number(value)
    def test_integer(self):
        with self.assertRaises(ValueError):
            integer("1.5")
    def test_tex(self):
        self.assertEqual(tex("a_b&c"), r"a\_b\&c")
    def test_false(self):
        self.assertEqual(
            list(leaves({"x": {"eligible_for_final_analysis": False}})),
            [("x.eligible_for_final_analysis", False)]
        )

def tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Fallaron pruebas del generador")
    return result.testsRun

def status_file(report, audit, notes):
    compilation = audit.get("compilation", {})
    selected = audit.get("selected", [])
    lines = [
        "# ESTADO DEL ENTREGABLE", "",
        "Generado: " + now(), "",
        "## Auditoría de requisitos", "",
        "| Requisito | Estado |", "|---|---|",
        "| Portada EVA02 con datos proporcionados | Fuentes generadas si se completó esa etapa |",
        "| Siete secciones, introducción, conclusiones y anexos | " +
        str(audit.get("sources_generated", False)) + " |",
        "| Dos mediciones elegibles confirmadas por el usuario | 2 |",
        "| Filas cotejadas y admitidas localmente | " + str(len(selected)) + " |",
        "| Resultados originales modificados | No |",
        "| Benchmarks o consultas ejecutados | No |",
        "| Limitación del índice textual | Conservada en las fuentes generadas |",
        "| Pruebas del generador ejecutadas | " + str(audit.get("tests_run", 0)) + " |",
        "| 135 pruebas del preflight | Comunicadas; no repetidas |",
        "| Reutilización al cambiar motor | Bloqueada según responsable; ahorro no demostrado |",
        "| Compilación aceptada automáticamente | " + str(compilation.get("success", False)) + " |",
        "| Páginas del PDF nuevo | " + str(compilation.get("pages", "ND")) + " |",
        "| Revisión visual | Pendiente |", "",
        "## Respaldo y recursos", "",
        "- Respaldo: `" + audit.get("backup", "pendiente") + "`.",
        "- Recursos: `" + audit.get("resources", "pendiente") + "`.", "",
        "## Evidencias admitidas", ""
    ]
    for item in selected:
        lines.extend([
            "- " + NAMES[item["engine"]] + ": `" + item["csv"] + "`.",
            "  - Fila: " + str(item["row_number"]) + ".",
            "  - CSV SHA-256: `" + item["csv_sha256"] + "`.",
            "  - Commit: `" + item["commit"] + "`.",
            "  - Commit SHA-256: `" + item["commit_sha256"] + "`.",
            "  - Vínculo hash reconocido: " + str(item["csv_hash_recognized_in_commit"]) + ".",
            "  - Elegibilidad: " + item["eligibility_provenance"] + "."
        ])
    lines.extend([
        "", "## Pendientes", "",
        "- Revisión completa de los playbooks y trazabilidad P/S.",
        "- Confirmar consultas invocadas por el runner y formulación M1/M2/M3.",
        "- Cotejar versiones, variantes y límites efectivos.",
        "- Reconciliar MB/MiB con el recolector.",
        "- Asociar planes y series con sus ventanas.",
        "- Revisar cada página, tablas, figuras y referencias.",
        "- Actualizar docs/08-handoff.md tras revisar su contenido real.",
        "", "## Observaciones", ""
    ])
    lines.extend("- " + note for note in notes)
    if not compilation.get("success"):
        lines.extend([
            "",
            "**main.pdf no fue sustituido por un PDF nuevo verificado.**",
            "Si existe, puede seguir siendo el documento anterior."
        ])
    write(report / "ESTADO_ENTREGABLE.md", "\n".join(lines) + "\n")

def execution_report(root, report, audit, notes):
    compilation = audit.get("compilation", {})
    state = "COMPLETADO Y VERIFICADO" if compilation.get("success") else "BLOQUEADO"
    lines = [
        "**A. RESUMEN DEL TRABAJO**", "",
        "Generación local del informe parcial. Consultar la auditoría para "
        "distinguir archivos cotejados y datos comunicados.", "",
        "**B. ESTADO DE EJECUCIÓN**", "", state, "",
        "La revisión visual sigue pendiente incluso si la compilación pasó.", "",
        "**C. ARCHIVOS CREADOS O MODIFICADOS**", "",
        "| Archivo | Ruta absoluta | Creado/Modificado | Estado |",
        "|---|---|---|---|"
    ]
    for path in (
        root / "ampliar_reporte.py",
        report / "main.tex",
        report / "main.pdf",
        report / "ESTADO_ENTREGABLE.md"
    ):
        state_text = "Existe" if path.is_file() else "No encontrado"
        if path.name == "main.pdf" and not compilation.get("success"):
            state_text += "; no acreditado como PDF nuevo"
        lines.append(
            "| " + path.name + " | " + str(path) + " | " +
            ("Creado por el bloque shell" if path.name == "ampliar_reporte.py"
             else "Ver auditoría de esta ejecución") + " | " + state_text + " |"
        )
    lines.extend([
        "", "**D. COMANDOS EJECUTADOS Y RESULTADOS**", "",
        "- Pruebas del generador: " + str(audit.get("tests_run", 0)) + ".",
        "- Páginas verificadas del PDF nuevo: " + str(compilation.get("pages", "ND")) + "."
    ])
    for item in compilation.get("commands", []):
        lines.append(
            "- `" + " ".join(item["argv"]) + "`: retorno " +
            str(item["returncode"]) + "."
        )
    lines.extend([
        "", "**E. CONTENIDO DEL REPORTE**", "",
        "- Siete secciones, portada, introducción, conclusiones, bibliografía y anexos.",
        "- Filas admitidas localmente: " + str(len(audit.get("selected", []))) + ".",
        "- No se generaron benchmarks ni resultados de escenarios ausentes.",
        "", "**F. ERRORES Y PENDIENTES**", ""
    ])
    lines.extend("- " + note for note in notes)
    lines.extend([
        "- Revisión visual y cotejo humano integral de requisitos pendientes.",
        "", "**G. SIGUIENTE ACCIÓN PARA EL USUARIO**", "",
        "```bash",
        "cat reports/latex/ESTADO_ENTREGABLE.md",
        "```"
    ])
    write(report / "INFORME_EJECUCION_CHATGPT.md", "\n".join(lines) + "\n")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--mongo-run", default=RUNS["mongodb"])
    parser.add_argument("--postgres-run", default=RUNS["postgresql"])
    parser.add_argument("--no-compile", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    count = tests()
    if args.self_test:
        return 0

    root = Path(args.root).resolve()
    if not (root / "docs").is_dir():
        raise SystemExit("La raíz no contiene docs/. No se modificó el reporte.")
    report = root / "reports" / "latex"
    if report.is_symlink():
        raise SystemExit("reports/latex es un enlace simbólico; revisar.")
    report.mkdir(parents=True, exist_ok=True)
    token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    out = report / ("generado-ampliado-" + token)
    notes = []
    audit = {
        "created_utc": now(), "tests_run": count,
        "benchmarks_executed": False, "databases_accessed": False,
        "original_results_modified": False,
        "preflight_tests_reported_by_user": 135,
        "preflight_tests_rerun": False,
        "sources": [], "selected": [], "sources_generated": False
    }
    code = 1
    try:
        archive = backup(root, report, token)
        audit["backup"] = rel(root, archive)
        out.mkdir()
        audit["resources"] = rel(root, out)
        selected = []
        run_docs = {}
        for engine, name in (
            ("mongodb", args.mongo_run), ("postgresql", args.postgres_run)
        ):
            run = confined(root, name)
            item, documents = select_run(
                root, run, engine, audit["sources"], notes
            )
            run_docs[engine] = documents
            if item:
                selected.append(item)
        audit["selected"] = [
            {key: value for key, value in item.items() if not key.startswith("_")}
            for item in selected
        ]
        inspect_sources(root, out, audit["sources"], notes)
        extract_queries(root, out, audit["sources"], notes)
        host = host_info()
        audit["host_capture"] = host
        write(out / "host.tex", table(
            ["Campo observado al generar", "Valor"],
            list(host.items()), r"p{0.34\linewidth}p{0.55\linewidth}"
        ))
        compose_rows = compose_info(root, audit["sources"])
        write(
            out / "compose.tex",
            table(
                ["Servicio declarado", "Imagen declarada"],
                compose_rows, r"p{0.30\linewidth}p{0.59\linewidth}"
            ) if compose_rows else
            r"\pendiente{Servicios Compose no reconocidos automáticamente.}"
        )
        dataset_rows = dataset_info(root, audit["sources"], notes)
        write(
            out / "dataset.tex",
            table(
                ["Fuente o campo leído", "Valor"],
                dataset_rows, r"p{0.41\linewidth}p{0.48\linewidth}"
            ) if dataset_rows else
            r"\pendiente{Manifiesto y equivalencia no interpretados.}"
        )
        audit["plans_recognized"] = plans_info(
            root, out, run_docs, audit["sources"], notes
        )
        metrics(out, selected)
        audit["figures_created"] = make_figures(out, selected, run_docs, notes)
        for name, content in SECTIONS.items():
            write(out / name, content)
        write(report / "informe-referencias.bib", BIB)
        write(
            report / "informe-activo.tex",
            r"\newcommand{\artifactdir}{" + out.name + "}\n"
        )
        write(report / "main.tex", MAIN)
        write(out / "ampliar_reporte.py", Path(__file__).read_text(encoding="utf-8"))
        audit["sources_generated"] = True
        if args.no_compile:
            audit["compilation"] = {
                "success": False, "reason": "Omitida por --no-compile"
            }
            code = 0
        else:
            audit["compilation"] = compile_pdf(report, out, notes)
            code = 0 if audit["compilation"].get("success") else 1
    except Exception as exc:
        audit["error"] = type(exc).__name__ + ": " + str(exc)
        notes.append(audit["error"])
        audit.setdefault("compilation", {"success": False})
        code = 1
    finally:
        audit["notes"] = notes
        if out.is_dir():
            write(out / "auditoria.json", json.dumps(audit, ensure_ascii=False, indent=2))
        status_file(report, audit, notes)
        execution_report(root, report, audit, notes)

    print(json.dumps({
        "script": str(Path(__file__).resolve()),
        "backup": audit.get("backup"),
        "resources": audit.get("resources"),
        "csv_rows_admitted": len(audit.get("selected", [])),
        "compilation": audit.get("compilation"),
        "status": str(report / "ESTADO_ENTREGABLE.md"),
        "execution_report": str(report / "INFORME_EJECUCION_CHATGPT.md"),
        "error": audit.get("error")
    }, ensure_ascii=False, indent=2))
    return code

if __name__ == "__main__":
    sys.exit(main())
