"""Render one content model to Markdown/HTML and optional PDF, escaping input text."""
from pathlib import Path
from html import escape

def cell(value):return str(value).replace('|',r'\|').replace('\n','<br>')

def markdown(doc):
    lines=['# '+doc['title'],'',doc['university'],doc['course'],'','**'+doc['banner']+'**','',
        'Estudiante: '+doc['student'],'Grupo: '+doc['group'],'Docente: '+doc['teacher'],'Fecha: '+doc['date'],'Estado: '+doc['state'],'','Índice:']
    lines += [f"{s['number']}. {s['title']}" for s in doc['sections']]
    def blocks(items):
        out=[]
        for block in items:
            kind=block['type']
            if kind=='p':out += ['',block['text'],'']
            elif kind=='sub':out += ['','### '+block['text'],'']
            elif kind=='image':out += ['',f"![{cell(block['caption'])}]({block['file']})",'',block['caption'],'']
            elif kind=='table':
                out += ['','| '+' | '.join(cell(h) for h in block['headers'])+' |','| '+' | '.join('---' for _ in block['headers'])+' |']
                out += ['| '+' | '.join(cell(v) for v in row)+' |' for row in block['rows']]
                if not block['rows']:out += ['| '+' | '.join(['Sin observaciones']+['—']*(len(block['headers'])-1))+' |']
                out += ['']
        return out
    for s in doc['sections']:lines += ['',f"## {s['number']} — {s['title']}",'',*blocks(s['blocks'])]
    lines += ['','## Anexos','',*blocks(doc['annex'])]
    return '\n'.join(lines)+'\n'

def html(doc):
    css=(Path(__file__).parent/'templates/print.css').read_text()
    out=['<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>'+escape(doc['title'])+'</title><style>'+css+'</style></head><body>',
         '<header class="cover"><p>'+escape(doc['university'])+'</p><p>'+escape(doc['course'])+'</p><h1>'+escape(doc['title'])+'</h1><p class="banner">'+escape(doc['banner'])+'</p>']
    for label,key in [('Estudiante','student'),('Grupo','group'),('Docente','teacher')]:out.append('<p>'+label+': <span class="editable" contenteditable="true">'+escape(doc[key])+'</span></p>')
    out += ['<p>Fecha: '+doc['date']+' · Estado: '+escape(doc['state'])+'</p></header><nav aria-label="Índice"><h2>Índice</h2><ol>']
    for s in doc['sections']:out.append(f'<li><a href="#seccion-{s["number"]}">'+escape(s['title'])+'</a></li>')
    out.append('</ol><a href="#anexos">Anexos</a></nav>')
    def blocks(items):
        values=[]
        for b in items:
            if b['type']=='p':values.append('<p>'+escape(b['text'])+'</p>')
            elif b['type']=='sub':values.append('<h3>'+escape(b['text'])+'</h3>')
            elif b['type']=='image':values.append('<figure><img src="'+escape(b['file'],quote=True)+'" alt="'+escape(b['caption'],quote=True)+'"><figcaption>'+escape(b['caption'])+'</figcaption></figure>')
            elif b['type']=='table':
                text='<table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in b['headers'])+'</tr></thead><tbody>'
                text+=''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in b['rows'])
                if not b['rows']:text+='<tr><td colspan="'+str(len(b['headers']))+'">Sin observaciones</td></tr>'
                values.append(text+'</tbody></table>')
        return ''.join(values)
    for s in doc['sections']:out.append(f'<section id="seccion-{s["number"]}"><h2>{s["number"]} — '+escape(s['title'])+'</h2>'+blocks(s['blocks'])+'</section>')
    out.append('<section id="anexos"><h2>Anexos</h2>'+blocks(doc['annex'])+'</section><footer>Documento estático. Consultar cobertura, procedencia y limitaciones antes de interpretar resultados.</footer></body></html>')
    return '\n'.join(out)+'\n'

def pdf_document(doc,root,target):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fontdir=Path('/usr/share/fonts/truetype/dejavu')
    if (fontdir/'DejaVuSans.ttf').exists():
        pdfmetrics.registerFont(TTFont('Academic',str(fontdir/'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('AcademicBold',str(fontdir/'DejaVuSans-Bold.ttf')))
        font='Academic';bold='AcademicBold'
    else:font='Helvetica';bold='Helvetica-Bold'
    styles=getSampleStyleSheet()
    for name in ('Normal','Title','Heading1','Heading2','Heading3'):styles[name].fontName=font
    styles['Normal'].fontSize=9;styles['Normal'].leading=13
    small=ParagraphStyle('Small',fontName=font,fontSize=7.5,leading=10,wordWrap='CJK')
    width,height=landscape(A4);usable=width-64
    document=SimpleDocTemplate(str(target),pagesize=(width,height),leftMargin=32,rightMargin=32,topMargin=36,bottomMargin=32,title=doc['title'],author=doc['university'])
    content=[]
    def p(text,style='Normal'):return Paragraph(escape(str(text)),styles[style])
    content += [p(doc['university'],'Heading1'),p(doc['course']),Spacer(1,16),p(doc['title'],'Title'),Spacer(1,12),p(doc['banner'],'Heading2')]
    for label,key in [('Estudiante','student'),('Grupo','group'),('Docente','teacher'),('Fecha','date'),('Estado','state')]:content += [p(label+': '+doc[key]),Spacer(1,7)]
    content += [PageBreak(),p('Índice','Heading1')]
    content += [p(str(s['number'])+'. '+s['title']) for s in doc['sections']]
    content += [p('Anexos'),PageBreak()]
    def append(items):
        for b in items:
            if b['type']=='p':content.extend([p(b['text']),Spacer(1,8)])
            elif b['type']=='sub':content.append(p(b['text'],'Heading2'))
            elif b['type']=='image':
                content.append(Image(str(Path(root)/b['file']),width=usable*.92,height=usable*.92*4.6/8.5));content.append(p(b['caption']))
            elif b['type']=='table':
                rows=b['rows'] or [['Sin observaciones']+['—']*(len(b['headers'])-1)]
                data=[[Paragraph(escape(str(v)),small) for v in row] for row in [b['headers'],*rows]]
                n=len(b['headers']);weights=[2.6 if n>=5 and i==0 else 1 for i in range(n)]
                tab=Table(data,colWidths=[usable*w/sum(weights) for w in weights],repeatRows=1,hAlign='LEFT')
                tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#ddeaf3')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#becbd6')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]));content.extend([tab,Spacer(1,12)])
    for s in doc['sections']:content.append(p(str(s['number'])+' — '+s['title'],'Heading1'));append(s['blocks'])
    content.append(p('Anexos','Heading1'));append(doc['annex'])
    def footer(canvas,docobj):
        canvas.setFont(font,7);canvas.drawString(32,18,doc['banner'][:120]);canvas.drawRightString(width-32,18,str(docobj.page))
    document.build(content,onFirstPage=footer,onLaterPages=footer)
