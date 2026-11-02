#!/usr/bin/env python3
"""Repara extracción de caracteres de control, corrige hash largos, compila PDF existente.
No consulta ni modifica bases de datos ni resultados.csv. Python stdlib + pdflatex + pdfinfo.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = root / 'reports' / 'latex'
    active = report / 'informe-activo.tex'
    if not active.is_file():
        raise RuntimeError('Falta informe-activo.tex; no se modificó ningún archivo.')
    text = active.read_text(encoding='utf-8')
    match = re.search(r'\\newcommand\{\\artifactdir\}\{(generado-ampliado-[^{}]+)\}', text)
    if not match:
        raise RuntimeError('No se reconoció la carpeta activa; no se modificó ningún archivo.')
    folder = match.group(1)
    resources = (report / folder).resolve()
    if not resources.is_dir() or resources.parent != report.resolve():
        raise RuntimeError('Carpeta activa inválida o fuera del reporte')
    build = resources / 'build'
    if not build.is_dir():
        raise RuntimeError('No existe carpeta de compilación previa; revisar')
    print('Recursos activos:', resources, flush=True)
    if not shutil.which('pdflatex') or not shutil.which('pdfinfo'):
        raise RuntimeError('Requiere pdflatex y pdfinfo instalados')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    changed = []
    # Los TXT son extractos transformados desde PDF/docs, no los archivos originales.
    for path in sorted(resources.glob('*.txt')):
        old = path.read_text(encoding='utf-8')
        replacement_count = 0
        clean = []
        for ch in old:
            code = ord(ch)
            if (code < 32 and ch not in '\n\t') or 0x7f <= code <= 0x9f:
                clean.append(f'[U+{code:04X}]')
                replacement_count += 1
            else:
                clean.append(ch)
        if replacement_count:
            path.with_name(path.name + '.previo-reparacion').write_text(old, encoding='utf-8')
            path.write_text(''.join(clean), encoding='utf-8')
            changed.append({'path': str(path), 'caracteres_control': replacement_count})
            print(f'Reparado: {path.name}: {replacement_count} controles.', flush=True)

    # Los digest de imagen Docker >64 caracteres necesitan puntos de quiebre en columnas p{}.
    compose = resources / 'compose.tex'
    if compose.is_file():
        source = compose.read_text(encoding='utf-8')
        def break_long(m):
            digest = m.group()
            return r'\allowbreak{}'.join(digest[i:i+8] for i in range(0, len(digest), 8))
        fixed, count = re.subn(r'[a-fA-F0-9]{24,}', break_long, source)
        if count:
            compose.with_name(compose.name + '.previo-reparacion').write_text(source, encoding='utf-8')
            compose.write_text(fixed, encoding='utf-8')
            changed.append({'path': str(compose), 'digests_fragmentados': count})
            print(f'Tabla Docker: {count} cadenas hex largas con cortes invisibles.', flush=True)

    latex = ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', f'-output-directory={folder}/build', 'main.tex']
    commands = []
    for pass_num in range(1, 4):
        proc = subprocess.run(latex, cwd=report, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        logpath = build / f'reparacion-pasada-{pass_num}.txt'
        logpath.write_text(proc.stdout, encoding='utf-8')
        commands.append({'command': latex, 'exit_code': proc.returncode, 'log': str(logpath)})
        print(f'LaTeX pasada {pass_num}: exit_code={proc.returncode}', flush=True)
        if proc.returncode != 0:
            matches = re.findall(r'^!.*(?:\n.*){0,4}', proc.stdout, re.M)
            print((matches[0] if matches else '\n'.join(proc.stdout.splitlines()[-25:])), file=sys.stderr)
            print('No se sustituyó main.pdf; revisar', logpath, file=sys.stderr)
            return 1
    log = (build / 'main.log').read_text(encoding='utf-8', errors='replace')
    problem_refs = bool(re.search(r'undefined references|undefined citations|Reference .+ undefined|Citation .+ undefined', log, re.I))
    overfull = re.findall(r'Overfull \\[hv]box[^\n]*', log)
    if problem_refs or overfull:
        print('PDF no publicado por advertencias:', 'refs=', problem_refs, 'overfull=', len(overfull), file=sys.stderr)
        for item in overfull[:8]:
            print(item, file=sys.stderr)
        return 2
    newpdf = build / 'main.pdf'
    if not newpdf.is_file() or newpdf.stat().st_size < 10000:
        print('PDF nuevo ausente o demasiado pequeño; anterior preservado.', file=sys.stderr)
        return 3
    proc = subprocess.run(['pdfinfo', str(newpdf)], capture_output=True, text=True)
    pagesmatch = re.search(r'^Pages:\s+(\d+)', proc.stdout, re.M)
    if proc.returncode or not pagesmatch:
        print('pdfinfo no pudo comprobar páginas; anterior preservado.', file=sys.stderr)
        return 4
    pages = int(pagesmatch.group(1))
    if pages < 9:
        print(f'Nuevo PDF solo tiene {pages} páginas: revisar; anterior preservado.', file=sys.stderr)
        return 5
    oldpdf = report / 'main.pdf'
    if oldpdf.is_file():
        backup = report / f'main-pre-reparacion-{stamp}.pdf'
        shutil.copy2(oldpdf, backup)
        print('Copia del PDF anterior:', backup, flush=True)
    tmp = report / ('main-preparado-' + uuid.uuid4().hex + '.pdf')
    shutil.copy2(newpdf, tmp)
    os.replace(tmp, oldpdf)
    print(f'OK: PDF publicado: {oldpdf} ({pages} páginas)', flush=True)

    # Corregir estado anterior, manteniendo el incidente histórico explícito.
    status = report / 'ESTADO_ENTREGABLE.md'
    if status.is_file():
        old = status.read_text(encoding='utf-8')
        old = old.replace('| Compilación aceptada automáticamente | False |', '| Compilación aceptada automáticamente | True (reparación local posterior) |')
        old = old.replace('| Páginas del PDF nuevo | None |', f'| Páginas del PDF nuevo | {pages} |')
        old += (f'\n## Compilación reparada ({stamp} UTC)\n'
                f'- PDF vigente: `{oldpdf}`; páginas: {pages}.\n'
                '- Error anterior: U+001B en un extracto del playbook; corregido en archivo derivado.\n'
                '- Cadenas hex largas en la tabla Docker fragmentadas para permitir saltos de línea.\n'
                '- Tres pasadas de pdflatex con retorno cero; sin referencias indefinidas ni overfull detectados.\n'
                '- Resultados.csv, commit.json y bases de datos: no modificados.\n'
                '- Revisión visual y validación académica completa: pendientes.\n')
        status.write_text(old, encoding='utf-8')
    reporttext = report / 'INFORME_EJECUCION_CHATGPT.md'
    if reporttext.is_file():
        old = reporttext.read_text(encoding='utf-8')
        old = old.replace('\nBLOQUEADO\n', '\nCOMPILACIÓN REPARADA Y PDF VERIFICADO; revisión visual pendiente\n', 1)
        old += (f'\n**H. ACTUALIZACIÓN LOCAL {stamp} UTC**\n'
                f'- PDF nuevo: `{oldpdf}` ({pages} páginas).\n'
                '- Comandos ejecutados: pdflatex x3 (código 0), pdfinfo (páginas verificadas).\n'
                f'- Recursos: `{resources}`.\n'
                '- Error previo de escape documentado; fuentes originales de datos preservadas.\n'
                '- Inspección visual pendiente.\n')
        reporttext.write_text(old, encoding='utf-8')
    audit_path = resources / 'auditoria.json'
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        audit['compilation_repair'] = {'utc': stamp, 'success': True, 'pages': pages, 'commands': commands, 'changes': changed, 'visual_inspection': 'pendiente'}
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
