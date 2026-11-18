"""もじゆう君: PDF points are the only document coordinate system."""
import sys, os, json, copy, tempfile
from pathlib import Path
import pymupdf as fitz
from PySide6.QtCore import Qt, QPointF, QRectF, QSizeF, QMarginsF, QTimer
from PySide6.QtGui import (QFont, QImage, QPixmap, QPainter, QColor, QPen, QAction,
    QKeySequence, QTextCursor, QTextOption, QPdfWriter, QPageSize, QPageLayout)
from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsView,
    QGraphicsScene, QGraphicsTextItem, QGraphicsRectItem, QGraphicsItem,
    QFileDialog, QMessageBox, QToolBar, QLabel, QDoubleSpinBox, QColorDialog)
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QLineEdit, QPushButton, QInputDialog, QComboBox, QMenu)

APP = 'もじゆう君'
# QTextDocument uses a stable 72 DPI layout device: 1 scene unit = 1 PDF point.
LAYOUT_DEVICE = None

def layout_device():
    global LAYOUT_DEVICE
    if LAYOUT_DEVICE is None:
        LAYOUT_DEVICE = QImage(1, 1, QImage.Format.Format_RGB32)
        LAYOUT_DEVICE.setDotsPerMeterX(2835)
        LAYOUT_DEVICE.setDotsPerMeterY(2835)
    return LAYOUT_DEVICE

class Handle(QGraphicsRectItem):
    def __init__(self, owner, corner):
        super().__init__(-4, -4, 8, 8, owner)
        self.owner, self.corner = owner, corner
        self.setBrush(QColor('#ffffff'))
        self.setPen(QPen(QColor('#2463eb'), 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor if corner in (0, 3) else Qt.CursorShape.SizeBDiagCursor)
        self.setZValue(20)

    def mousePressEvent(self, event):
        self.owner.finish_edit()
        self.owner.window.commit()
        r = self.owner.sceneBoundingRect()
        corners = [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]
        self.anchor = corners[3-self.corner]
        self.vector = corners[self.corner] - self.anchor
        self.start_size = self.owner.size
        event.accept()

    def mouseMoveEvent(self, event):
        v = event.scenePos() - self.anchor
        d = self.vector.x()**2 + self.vector.y()**2
        ratio = (v.x()*self.vector.x() + v.y()*self.vector.y()) / max(d, .001)
        self.owner.set_size(max(1, min(500, self.start_size * max(.01, ratio))))
        r = self.owner.boundingRect()
        offsets = [r.bottomRight(), r.bottomLeft(), r.topRight(), r.topLeft()]
        self.owner.setPos(self.anchor - offsets[self.corner])
        self.owner.window.sync_controls()
        event.accept()

    def mouseReleaseEvent(self, event):
        self.owner.window.commit()
        event.accept()

class TextBox(QGraphicsTextItem):
    def __init__(self, window, data):
        super().__init__()
        self.window = window
        self.size = data.get('size', 24.)
        self.color = data.get('color', '#20252d')
        self.handles = []
        self.editing = False
        self.document().documentLayout().setPaintDevice(layout_device())
        self.document().setDocumentMargin(0)
        opt = self.document().defaultTextOption()
        opt.setWrapMode(QTextOption.WrapMode.NoWrap)
        self.document().setDefaultTextOption(opt)
        self.setTextWidth(-1)
        self.setPlainText(data.get('text', ''))
        self.setDefaultTextColor(QColor(self.color))
        self.set_size(self.size)
        self.setPos(data.get('x', 0), data.get('y', 0))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)
        self.handles = [Handle(self, i) for i in range(4)]
        self.document().contentsChanged.connect(self.changed)
        self.update_handles()

    def set_size(self, value):
        self.size = float(value)
        font = QFont('Yu Gothic')
        font.setPointSizeF(self.size)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self.setFont(font)
        self.update_handles()

    def update_handles(self):
        r = self.boundingRect()
        for h, p in zip(self.handles, [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]):
            h.setPos(p)
            h.setVisible(self.isSelected() and not self.editing and not self.window.exporting)
        self.update()

    def changed(self):
        self.update_handles()
        self.window.update_title()

    def data_dict(self):
        return dict(text=self.toPlainText(), x=self.x(), y=self.y(), size=self.size, color=self.color)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update_handles()
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected() and not self.window.exporting:
            pen = QPen(QColor('#2463eb'), 0, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())

    def start_edit(self):
        self.window.commit()
        self.editing = True
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setSelected(True)
        self.update_handles()

    def finish_edit(self):
        if self.editing:
            self.editing = False
            self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            cursor = self.textCursor()
            cursor.clearSelection()
            self.setTextCursor(cursor)
            self.update_handles()
            self.window.commit()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.finish_edit()

    def mouseDoubleClickEvent(self, event):
        self.start_edit()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self.window.commit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.window.commit()

    def keyPressEvent(self, event):
        if self.editing and event.key() == Qt.Key.Key_Escape:
            self.finish_edit()
            event.accept()
        else:
            super().keyPressEvent(event)

class Canvas(QGraphicsView):
    def __init__(self, window):
        super().__init__(window.scene)
        self.window = window
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor('#dce2eb'))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

    def mousePressEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        item = self.itemAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.RightButton:
            if self.window.doc and self.window.page_rect.contains(point):
                self.window.show_stamp_menu(point, event.globalPosition().toPoint())
                event.accept()
                return
        if event.button() == Qt.MouseButton.LeftButton and self.window.doc and item == self.window.background:
            self.window.finish_edits()
            self.window.scene.clearSelection()
            if self.window.page_rect.contains(point):
                self.window.add_box(point)
                event.accept()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        focus = self.scene().focusItem()
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not (isinstance(focus, TextBox) and focus.editing):
            self.window.delete_selected()
        else:
            super().keyPressEvent(event)

class Window(QMainWindow):
    # Practical leading-tone resolution: replace each dim triad with the
    # major chord a semitone above its root (e.g. Bdim -> C).
    DIM_EASY_PROXY = {
        'Bdim':'Dm', 'Cdim':'Ebm', 'C#dim':'Em', 'Ddim':'Fm',
        'D#dim':'F#m', 'Edim':'Gm', 'Fdim':'Abm', 'F#dim':'Am',
        'Gdim':'Bbm', 'G#dim':'Bm', 'Adim':'Cm', 'A#dim':'C#m',
        'Bbdim':'Dbm',
    }
    # Natural minor triads; every chromatic tonic is represented with a
    # conventional spelling. Chord degrees are spelled by key, not guessed
    # from pitch classes, so flats and diminished chords display correctly.
    DIATONIC = {
        '長調': {
            'C':['C','Dm','Em','F','G','Am','Bdim'],
            'Db':['Db','Ebm','Fm','Gb','Ab','Bbm','Cdim'],
            'D':['D','Em','F#m','G','A','Bm','C#dim'],
            'Eb':['Eb','Fm','Gm','Ab','Bb','Cm','Ddim'],
            'E':['E','F#m','G#m','A','B','C#m','D#dim'],
            'F':['F','Gm','Am','Bb','C','Dm','Edim'],
            'Gb':['Gb','Abm','Bbm','Cb','Db','Ebm','Fdim'],
            'G':['G','Am','Bm','C','D','Em','F#dim'],
            'Ab':['Ab','Bbm','Cm','Db','Eb','Fm','Gdim'],
            'A':['A','Bm','C#m','D','E','F#m','G#dim'],
            'Bb':['Bb','Cm','Dm','Eb','F','Gm','Adim'],
            'B':['B','C#m','D#m','E','F#','G#m','A#dim'],
        },
        '短調': {
            'Am':['Am','Bdim','C','Dm','Em','F','G'],
            'Bbm':['Bbm','Cdim','Db','Ebm','Fm','Gb','Ab'],
            'Bm':['Bm','C#dim','D','Em','F#m','G','A'],
            'Cm':['Cm','Ddim','Eb','Fm','Gm','Ab','Bb'],
            'C#m':['C#m','D#dim','E','F#m','G#m','A','B'],
            'Dm':['Dm','Edim','F','Gm','Am','Bb','C'],
            'Ebm':['Ebm','Fdim','Gb','Abm','Bbm','Cb','Db'],
            'Em':['Em','F#dim','G','Am','Bm','C','D'],
            'Fm':['Fm','Gdim','Ab','Bbm','Cm','Db','Eb'],
            'F#m':['F#m','G#dim','A','Bm','C#m','D','E'],
            'Gm':['Gm','Adim','Bb','Cm','Dm','Eb','F'],
            'Abm':['Abm','Bbdim','Cb','Dbm','Ebm','Fb','Gb'],
        },
    }
    def __init__(self):
        super().__init__()
        self.doc = None
        self.source = None
        self.output = None
        self.boxes = []
        self.history = [[]]
        self.history_index = 0
        self.saved_state = []
        self.exporting = False
        self.restoring = False
        self.default_color = '#20252d'
        self.stamps = self.load_stamps()
        self.scene = QGraphicsScene(self)
        self.view = Canvas(self)
        self.setCentralWidget(self.view)
        self.scene.selectionChanged.connect(self.sync_controls)
        self.resize(1100, 850)
        self.setMinimumSize(760, 500)
        toolbar = QToolBar('編集', self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self.action(toolbar, 'PDFを開く', self.open_dialog, 'Ctrl+O')
        self.action(toolbar, 'PDF保存', self.save_dialog, 'Ctrl+S')
        self.action(toolbar, '別名で保存', lambda: self.save_dialog(True), 'Ctrl+Shift+S')
        toolbar.addSeparator()
        self.action(toolbar, '元に戻す', self.undo, 'Ctrl+Z')
        self.action(toolbar, 'やり直す', self.redo, 'Ctrl+Y')
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(' 文字サイズ '))
        self.size_control = QDoubleSpinBox()
        self.size_control.setRange(1, 500)
        self.size_control.setDecimals(2)
        self.size_control.setSuffix(' pt')
        self.size_control.setValue(24)
        self.size_control.setKeyboardTracking(False)
        self.size_control.setAccessibleName('文字サイズ pt')
        self.size_control.valueChanged.connect(self.change_size)
        toolbar.addWidget(self.size_control)
        self.action(toolbar, '文字色', self.change_color)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(' 表示 '))
        self.zoom = QDoubleSpinBox()
        self.zoom.setRange(25, 400)
        self.zoom.setDecimals(0)
        self.zoom.setSuffix(' %')
        self.zoom.setValue(100)
        self.zoom.setKeyboardTracking(False)
        self.zoom.valueChanged.connect(self.set_zoom)
        toolbar.addWidget(self.zoom)
        self.action(toolbar, '全体表示', self.fit_page)
        self.action(toolbar, '用紙に合わせる', lambda: self.fit_preset('A4'))
        self.action(toolbar, 'iPad 13インチ', lambda: self.fit_preset('iPad'))
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(' スタンプ '))
        self.stamp_picker = QComboBox()
        self.stamp_picker.setMinimumWidth(130)
        self.refresh_stamps()
        toolbar.addWidget(self.stamp_picker)
        self.action(toolbar, '貼り付け', self.place_stamp)
        self.action(toolbar, '登録/編集', self.manage_stamps)
        self.statusBar().showMessage('PDFを開く → 空白をクリックして入力 → Escで編集終了 → 四隅で文字サイズ変更')
        self.setStyleSheet('QToolBar { spacing: 5px; padding: 9px; background: #f7f9fc; } QToolButton {padding: 7px;} QDoubleSpinBox {padding: 5px;} QStatusBar {padding: 5px;}')
        self.update_title()

    def action(self, toolbar, name, callback, shortcut=None):
        a = QAction(name, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(lambda checked=False: callback())
        toolbar.addAction(a)
        return a

    def state(self):
        return [b.data_dict() for b in self.boxes]

    def dirty(self):
        return self.state() != self.saved_state

    def update_title(self):
        name = self.source.name if self.source else 'PDFを開いてください'
        self.setWindowTitle(f'{APP} — {name}' + (' *' if self.dirty() else ''))

    def commit(self):
        if self.restoring:
            return
        state = self.state()
        if state != self.history[self.history_index]:
            self.history = self.history[:self.history_index+1] + [copy.deepcopy(state)]
            self.history_index += 1
        self.update_title()

    def finish_edits(self):
        for b in self.boxes:
            b.finish_edit()
        self.commit()

    def restore(self):
        self.restoring = True
        for b in self.boxes:
            self.scene.removeItem(b)
        self.boxes = []
        for data in self.history[self.history_index]:
            box = TextBox(self, data)
            self.scene.addItem(box)
            self.boxes.append(box)
        self.restoring = False
        self.update_title()

    def undo(self):
        self.finish_edits()
        if self.history_index > 0:
            self.history_index -= 1
            self.restore()

    def redo(self):
        self.finish_edits()
        if self.history_index + 1 < len(self.history):
            self.history_index += 1
            self.restore()

    def confirm_discard(self):
        self.finish_edits()
        if not self.dirty():
            return True
        result = QMessageBox.question(self, APP, '変更をPDFに保存しますか？',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if result == QMessageBox.StandardButton.Save:
            return self.save_dialog()
        return result == QMessageBox.StandardButton.Discard

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, 'PDFを開く', '', 'PDF (*.pdf)')
        if path and self.confirm_discard():
            try:
                self.load_pdf(path)
            except Exception as e:
                QMessageBox.warning(self, '開けませんでした', str(e))

    def load_pdf(self, path):
        data = Path(path).read_bytes()
        doc = fitz.open(stream=data, filetype='pdf')
        if doc.needs_pass:
            doc.close()
            raise ValueError('パスワード付きPDFには、この試作品は対応していません。')
        if len(doc) != 1:
            doc.close()
            raise ValueError('この試作品は単一ページ専用です。1ページのPDFを選んでください。')
        if doc[0].rect.width < 1 or doc[0].rect.height < 1:
            doc.close()
            raise ValueError('ページサイズが不正です。')
        self.restoring = True
        self.boxes = []
        self.scene.clear()
        if self.doc:
            self.doc.close()
        self.doc, self.source_bytes = doc, data
        self.source = Path(path).resolve()
        self.output = None
        r = doc[0].rect
        self.page_rect = QRectF(0, 0, r.width, r.height)
        self.background = self.scene.addPixmap(QPixmap())
        self.background.setZValue(-100)
        self.background.setShapeMode(self.background.ShapeMode.BoundingRectShape)
        self.scene.setSceneRect(self.page_rect.adjusted(-30, -30, 30, 30))
        self.history, self.history_index, self.saved_state = [[]], 0, []
        self.restoring = False
        self.fit_page()
        self.render_background()
        self.update_title()

    def render_background(self):
        if not self.doc:
            return
        z = min(4., max(1., self.zoom.value()/100 * self.devicePixelRatioF()))
        # Bound preview memory for unusually large engineering PDFs.
        z = min(z, (16000000 / (self.page_rect.width()*self.page_rect.height()))**.5)
        pix = self.doc[0].get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        self.background.setPixmap(QPixmap.fromImage(image))
        self.background.setScale(1/z)

    def set_zoom(self, value):
        self.view.resetTransform()
        self.view.scale(value/100, value/100)
        self.render_background()

    def fit_preset(self, preset):
        if not self.doc:
            return
        # A4 and iPad presets express the intended viewing scale. Actual screen
        # fit is then limited by the current window viewport.
        if preset == 'A4':
            self.fit_page()
            self.statusBar().showMessage('A4表示：用紙全体がウィンドウに収まる倍率です。')
        else:
            self.fit_page()
            self.statusBar().showMessage('iPad 13インチ向け：ページ全体を見渡せる倍率です。PDFの用紙サイズは変わりません。')

    def stamp_path(self):
        base = Path(os.environ.get('APPDATA', str(Path.home()))) / 'Mojiyuu'
        base.mkdir(parents=True, exist_ok=True)
        return base / 'stamps.json'

    def load_stamps(self):
        try:
            data = json.loads(self.stamp_path().read_text(encoding='utf-8'))
            return [x for x in data if isinstance(x, dict) and x.get('name') and x.get('text')]
        except (OSError, ValueError, TypeError):
            return [{'name': '確認', 'text': '確認', 'size': 18, 'color': '#20252d'},
                    {'name': '済', 'text': '済', 'size': 18, 'color': '#d02020'}]

    def save_stamps(self):
        p = self.stamp_path()
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.stamps, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, p)

    def refresh_stamps(self):
        self.stamp_picker.clear()
        self.stamp_picker.addItems([x['name'] for x in self.stamps])

    def place_stamp(self, point=None):
        if not self.doc:
            QMessageBox.information(self, APP, '先にPDFを開いてください。')
            return
        i = self.stamp_picker.currentIndex()
        if i < 0 or i >= len(self.stamps):
            return
        stamp = self.stamps[i]
        center = point if point is not None else self.view.mapToScene(self.view.viewport().rect().center())
        pos = center - QPointF(25, 12)
        pos.setX(max(0, min(pos.x(), self.page_rect.width()-40)))
        pos.setY(max(0, min(pos.y(), self.page_rect.height()-24)))
        box = self.add_box(pos, stamp['text'], editing=False)
        box.set_size(float(stamp.get('size', 18)))
        box.color = stamp.get('color', '#20252d')
        box.setDefaultTextColor(QColor(box.color))
        self.commit()

    @staticmethod
    def chord_text(chords, easy=False):
        if not easy:
            return '   '.join(chords)
        return '   '.join(Window.chord_stamp_text(c) for c in chords)

    @staticmethod
    def chord_stamp_text(chord):
        """Single selectable chord; diminished degree gets a half-diminished label and minor proxy."""
        if chord in Window.DIM_EASY_PROXY:
            root=chord[:-3]
            return f'{root}m7-5 ({Window.DIM_EASY_PROXY[chord]})'
        return chord

    def place_chord_stamp(self, kind, key, chord, point):
        text=self.chord_stamp_text(chord)
        box=self.add_box(point,text,editing=False)
        box.set_size(18)
        box.color=self.default_color
        box.setDefaultTextColor(QColor(box.color))
        box.setData(0,f'{key} {kind}: {text}')
        self.commit()
        return box

    def place_named_stamp(self, kind, key, point, easy=False):
        """Place one built-in stamp at a PDF scene point."""
        if kind in self.DIATONIC:
            chords = self.DIATONIC[kind][key]
            text = self.chord_text(chords, easy)
            size = 12.0
            color = self.default_color
            label = f'{key} {kind}' + (' 簡単代理' if easy else ' ダイアトニックコード')
        else:
            marks = {
                '小節線': ('│', 36.0),
                '太い小節線': ('┃', 36.0),
                '複縦線': ('‖', 30.0),
                '終止線': ('𝄂', 30.0),
            }
            text, size = marks[kind]
            color = self.default_color
            label = kind
        box = self.add_box(point, text, editing=False)
        box.set_size(size)
        box.color = color
        box.setDefaultTextColor(QColor(color))
        box.setData(0, label)
        self.commit()
        return box

    def show_stamp_menu(self, point, global_point):
        menu = QMenu(self)
        for kind, caption in (('長調','長調'),('短調','短調')):
            keys_menu=menu.addMenu(caption)
            for key,chords in self.DIATONIC[kind].items():
                key_menu=keys_menu.addMenu(key)
                for chord in chords:
                    label=self.chord_stamp_text(chord)
                    action=key_menu.addAction(label)
                    action.triggered.connect(
                        lambda checked=False,k=key,t=kind,c=chord,p=point: self.place_chord_stamp(t,k,c,p))
        bars = menu.addMenu('小節線')
        for kind in ('小節線', '太い小節線', '複縦線', '終止線'):
            action = bars.addAction(kind)
            action.triggered.connect(lambda checked=False, k=kind: self.place_named_stamp(k, '', point))
        menu.addSeparator()
        custom = menu.addAction('登録した文字スタンプ')
        custom.triggered.connect(lambda checked=False, p=point: self.place_stamp(p))
        menu.exec(global_point)

    def manage_stamps(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('文字スタンプの登録・編集')
        dlg.resize(460, 390)
        layout = QVBoxLayout(dlg)
        items = QListWidget()
        layout.addWidget(items)
        def refill(select=-1):
            items.clear()
            for s in self.stamps:
                items.addItem(f"{s['name']}　|　{s['text']}　|　{s.get('size',18)} pt")
            if 0 <= select < items.count(): items.setCurrentRow(select)
        def add_or_edit():
            idx = items.currentRow()
            existing = self.stamps[idx] if idx >= 0 else {}
            name, ok = QInputDialog.getText(dlg, 'スタンプ名', '一覧に表示する名前:', text=existing.get('name',''))
            if not ok or not name.strip(): return
            val, ok = QInputDialog.getMultiLineText(dlg, 'スタンプ文字', '貼り付ける文字:', existing.get('text',''))
            if not ok or not val: return
            size, ok = QInputDialog.getDouble(dlg, '文字サイズ', 'サイズ (pt):', float(existing.get('size',18)), 1, 500, 1)
            if not ok: return
            color = QColorDialog.getColor(QColor(existing.get('color','#20252d')), dlg, 'スタンプ文字色')
            if not color.isValid(): return
            rec = dict(name=name.strip(), text=val, size=size, color=color.name())
            if idx >= 0: self.stamps[idx] = rec
            else: self.stamps.append(rec)
            self.save_stamps(); self.refresh_stamps(); refill(self.stamps.index(rec))
        def delete_item():
            idx = items.currentRow()
            if idx >= 0:
                self.stamps.pop(idx); self.save_stamps(); self.refresh_stamps(); refill(min(idx,items.count()-1))
        buttons = QHBoxLayout()
        for label, cb in [('追加/編集',add_or_edit),('削除',delete_item),('閉じる',dlg.accept)]:
            b = QPushButton(label); b.clicked.connect(cb); buttons.addWidget(b)
        layout.addLayout(buttons)
        refill(0)
        dlg.exec()

    def fit_page(self):
        if self.doc:
            v = self.view.viewport().size()
            z = min((v.width()-70)/self.page_rect.width(), (v.height()-70)/self.page_rect.height())*100
            self.zoom.setValue(max(25, min(400, z)))

    def add_box(self, point, text='', editing=True):
        self.commit()
        box = TextBox(self, dict(text=text, x=point.x(), y=point.y(), size=self.size_control.value(), color=self.default_color))
        self.scene.addItem(box)
        self.boxes.append(box)
        self.scene.clearSelection()
        box.setSelected(True)
        self.commit()
        if editing:
            box.start_edit()
        return box

    def selected(self):
        return [b for b in self.boxes if b.isSelected()]

    def sync_controls(self):
        selected = self.selected()
        if selected:
            self.size_control.blockSignals(True)
            self.size_control.setValue(selected[0].size)
            self.size_control.blockSignals(False)

    def change_size(self, value):
        self.commit()
        for b in self.selected():
            b.set_size(value)
        self.commit()

    def change_color(self):
        selected = self.selected()
        color = QColorDialog.getColor(QColor(selected[0].color if selected else self.default_color), self, '文字色')
        if color.isValid():
            self.commit()
            self.default_color = color.name()
            for b in selected:
                b.color = color.name()
                b.setDefaultTextColor(color)
            self.commit()

    def delete_selected(self):
        self.commit()
        for b in self.selected():
            self.scene.removeItem(b)
            self.boxes.remove(b)
        self.commit()

    def export_pdf(self, path):
        """Qt draws the SAME text layout into a vector overlay with embedded fonts."""
        target = Path(path).resolve()
        if target == self.source:
            raise ValueError('元PDFは上書きできません。別の名前で保存してください。')
        self.finish_edits()
        with tempfile.TemporaryDirectory(prefix='mojiyuu-') as temp:
            overlay_path = str(Path(temp) / 'overlay.pdf')
            writer = QPdfWriter(overlay_path)
            writer.setResolution(72)
            writer.setPageSize(QPageSize(QSizeF(self.page_rect.width(), self.page_rect.height()), QPageSize.Unit.Point))
            writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Point)
            writer.setTitle(APP)
            painter = QPainter(writer)
            if not painter.isActive():
                raise RuntimeError('PDFの描画を開始できませんでした。')
            painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
            try:
                for b in self.boxes:
                    if not b.toPlainText():
                        continue
                    painter.save()
                    painter.translate(b.pos())
                    # drawContents does not inherit QGraphicsTextItem's default color.
                    from PySide6.QtGui import QAbstractTextDocumentLayout, QPalette
                    context = QAbstractTextDocumentLayout.PaintContext()
                    context.palette.setColor(QPalette.ColorRole.Text, QColor(b.color))
                    b.document().documentLayout().draw(painter, context)
                    painter.restore()
            finally:
                painter.end()
            del writer
            with fitz.open(stream=self.source_bytes, filetype='pdf') as result:
                page = result[0]
                # Keep original MediaBox/CropBox and rotation. Counter-rotate
                # the overlay into the original page's unrotated coordinates.
                if any(b.toPlainText() for b in self.boxes):
                    with fitz.open(overlay_path) as overlay:
                        page.show_pdf_page(page.rect * page.derotation_matrix, overlay, 0,
                                           rotate=page.rotation, overlay=True)
                fd, temporary = tempfile.mkstemp(prefix='.mojiyuu-', suffix='.pdf', dir=target.parent)
                os.close(fd)
                try:
                    result.save(temporary, garbage=3, deflate=True)
                    with fitz.open(temporary) as check:
                        if len(check) != 1:
                            raise RuntimeError('保存したPDFを検証できませんでした。')
                    os.replace(temporary, target)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
        self.output = target
        self.saved_state = copy.deepcopy(self.state())
        self.update_title()

    def save_dialog(self, save_as=False):
        if not self.doc:
            QMessageBox.information(self, APP, '先にPDFを開いてください。')
            return False
        self.finish_edits()
        outside = [b for b in self.boxes if b.toPlainText() and not self.page_rect.contains(b.sceneBoundingRect())]
        if outside and QMessageBox.question(self, APP, 'ページの外にはみ出す文字があります。はみ出した部分は保存されません。続けますか？') != QMessageBox.StandardButton.Yes:
            return False
        path = str(self.output) if self.output and not save_as else ''
        if not path:
            suggested = str(self.source.with_name(self.source.stem + '_もじゆう.pdf'))
            path, _ = QFileDialog.getSaveFileName(self, 'PDFとして保存', suggested, 'PDF (*.pdf)')
        if not path:
            return False
        if not path.lower().endswith('.pdf'):
            path += '.pdf'
        try:
            self.export_pdf(path)
            self.statusBar().showMessage(f'保存しました：{path}  ／ 再度開いたPDFの追加文字は元PDFの一部になります。')
            return True
        except Exception as e:
            QMessageBox.warning(self, '保存できませんでした', str(e))
            return False

    def closeEvent(self, event):
        if self.confirm_discard():
            event.accept()
        else:
            event.ignore()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setFont(QFont('Yu Gothic UI', 10))
    window = Window()
    window.show()
    if len(sys.argv) > 1:
        try:
            window.load_pdf(sys.argv[1])
        except Exception as e:
            QMessageBox.warning(window, APP, str(e))
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
