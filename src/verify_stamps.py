import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
import pymupdf as fitz
from mojiyuu import Window

root=Path(__file__).resolve().parents[1]
out_dir=root/'verification'
out_dir.mkdir(exist_ok=True)
app=QApplication([])
w=Window()
doc=fitz.open(); page=doc.new_page(width=595,height=842)
page.insert_text((35,25),'ALL DIATONIC CHORD STAMPS / BARLINES',fontsize=12)
src=out_dir/'スタンプテスト原稿.pdf'; doc.save(src); doc.close()
w.load_pdf(src)
expected=[]
for col,kind in enumerate(('長調','短調')):
    x=30+col*290
    for row,(key,chords) in enumerate(w.DIATONIC[kind].items()):
        text='   '.join(chords)
        box=w.add_box(QPointF(x,42+row*47),text,editing=False)
        box.set_size(11)
        box.color='#203d83'; box.setDefaultTextColor(QColor(box.color))
        box.setData(0,f'{key} {kind}')
        expected.extend(chords)
for i,kind in enumerate(('小節線','太い小節線','複縦線','終止線')):
    box=w.place_named_stamp(kind,'',QPointF(55+i*90,625))
    box.set_size(40)
out=out_dir/'右クリックスタンプ検証.pdf'
w.export_pdf(out)
with fitz.open(out) as check:
    txt=check[0].get_text()
    missing=[c for c in expected if c not in txt]
    marks=['│','┃','‖','𝄂']
    spans=[s for b in check[0].get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']]
    check[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7)).save(str(out_dir/'右クリックスタンプ検証.png'))
    assert not missing, missing
    assert len([s for s in spans if s['text'] in marks]) >= 3, [s['text'] for s in spans[-8:]]
    report={'major_keys':list(w.DIATONIC['長調']),'minor_keys':list(w.DIATONIC['短調']),
            'expected_chords':len(expected),'missing_chords':missing,
            'barline_spans':[s['text'] for s in spans if s['text'] in marks],
            'embedded_fonts':[f[3] for f in check[0].get_fonts(full=True) if check.extract_font(f[0])[3]],
            'images':len(check[0].get_images())}
    (out_dir/'stamp_test_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
# Check the bracketed easy substitution for every diminished chord in all 24 keys.
w.load_pdf(src)
expected_pairs=[]
for col,kind in enumerate(('長調','短調')):
    x=28+col*292
    for row,(key,chords) in enumerate(w.DIATONIC[kind].items()):
        text=w.chord_text(chords,easy=True)
        box=w.add_box(QPointF(x,42+row*47),text,editing=False)
        box.set_size(10)
        box.color='#203d83'; box.setDefaultTextColor(QColor(box.color))
        box.setData(0,f'{key} {kind} 簡単代理')
        expected_pairs.extend(f"{c[:-3]}m7-5 ({w.DIM_EASY_PROXY[c]})" for c in chords if c in w.DIM_EASY_PROXY)
easy_pdf=out_dir/'簡単代理コード一覧.pdf'
w.export_pdf(easy_pdf)
with fitz.open(easy_pdf) as check:
    txt=check[0].get_text()
    missing=[pair for pair in expected_pairs if pair not in txt]
    assert w.chord_stamp_text('Bdim')=='Bm7-5 (Dm)'
    assert len(expected_pairs)==24 and not missing, missing
    check[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7)).save(str(out_dir/'簡単代理コード一覧.png'))
    print(json.dumps({'easy_substitutions':expected_pairs,'missing':missing,'images':len(check[0].get_images())},ensure_ascii=False,indent=2))
# Seven separate text objects demonstrate one-chord-at-a-time selection for C major.
w.load_pdf(src)
choices=['C','Dm','Em','F','G','Am','Bdim']
for i,chord in enumerate(choices):
    w.place_chord_stamp('長調','C',chord,QPointF(28+i*76,300))
chosen_pdf=out_dir/'ハ長調コード個別スタンプ.pdf'
w.export_pdf(chosen_pdf)
with fitz.open(chosen_pdf) as check:
    spans=[s for b in check[0].get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']]
    chosen=[s for s in spans if 280<s['origin'][1]<360]
    assert [s['text'] for s in chosen]==['C','Dm','Em','F','G','Am','Bm7-5 (Dm)'],[s['text'] for s in chosen]
    check[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7)).save(str(out_dir/'ハ長調コード個別スタンプ.png'))
    print(json.dumps({'separate_stamps':[s['text'] for s in chosen],'count':len(chosen)},ensure_ascii=False))
w.close()



