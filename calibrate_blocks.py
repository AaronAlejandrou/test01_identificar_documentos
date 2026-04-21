import sys
import json
import copy
import argparse
from pathlib import Path

try:
    import fitz
    import numpy as np
    import cv2
except ImportError:
    print("Faltan dependencias base: pip install pymupdf numpy opencv-python")
    sys.exit(1)

try:
    from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
                                   QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsEllipseItem,
                                   QGraphicsTextItem, QGraphicsItem, QVBoxLayout, QHBoxLayout, 
                                   QWidget, QSplitter, QListWidget, QListWidgetItem, QLineEdit, 
                                   QLabel, QPushButton, QCheckBox, QStatusBar, QToolBar, QMessageBox)
    from PySide6.QtGui import QPixmap, QImage, QColor, QPen, QBrush, QPainter, QCursor, QKeyEvent, QAction, QKeySequence, QWheelEvent, QMouseEvent, QPalette
    from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject, QEvent
except ImportError:
    print("Por favor instala PySide6 para usar el nuevo calibrador: pip install PySide6")
    sys.exit(1)

# ============================================================
# UTILS
# ============================================================

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(path: str, cfg: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def render_page(file_path: str, page_num: int, dpi: int, canonical_w: int, canonical_h: int) -> np.ndarray:
    p = Path(file_path)
    if p.suffix.lower() == ".pdf":
        doc = fitz.open(file_path)
        if page_num >= doc.page_count:
            page_num = doc.page_count - 1
        page = doc.load_page(page_num)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(file_path)
        if img is None:
            raise RuntimeError(f"No se pudo abrir: {file_path}")
    return cv2.resize(img, (canonical_w, canonical_h), interpolation=cv2.INTER_CUBIC)

def numpy_to_qimage(img: np.ndarray) -> QImage:
    h, w, ch = img.shape
    bytes_per_line = ch * w
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format_RGB888)
    # Copiamos para evitar problemas de memoria
    return qimg.copy()

def bbox_to_rect(bbox, w, h):
    x1, y1, x2, y2 = bbox
    return QRectF(x1*w, y1*h, (x2-x1)*w, (y2-y1)*h)

def rect_to_bbox(rect, w, h):
    x1 = rect.left() / w
    y1 = rect.top() / h
    x2 = rect.right() / w
    y2 = rect.bottom() / h
    return [round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)]


# ============================================================
# CUSTOM GRAPHICS ITEMS
# ============================================================

class BoxItem(QGraphicsRectItem):
    """Caja redimensionable para text_fields y signature_fields."""
    def __init__(self, key: str, section: str, bbox: list, can_w: int, can_h: int):
        super().__init__(bbox_to_rect(bbox, can_w, can_h))
        self.key = key
        self.section = section
        self.can_w = can_w
        self.can_h = can_h
        
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        color = QColor("red") if section == "text_fields" else QColor("blue")
        self.setPen(QPen(color, 2))
        self.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
        
        self.label = QGraphicsTextItem(key, self)
        self.label.setDefaultTextColor(color)
        self.label.setPos(self.rect().topLeft() + QPointF(0, -20))
        
        self.resizing = False
        self.resize_dir = None
        self.MARGIN = 8

    def _get_resize_dir(self, pos):
        r = self.rect()
        left = abs(pos.x() - r.left()) < self.MARGIN
        right = abs(pos.x() - r.right()) < self.MARGIN
        top = abs(pos.y() - r.top()) < self.MARGIN
        bottom = abs(pos.y() - r.bottom()) < self.MARGIN

        if left and top: return 'tl'
        if right and top: return 'tr'
        if left and bottom: return 'bl'
        if right and bottom: return 'br'
        if left: return 'l'
        if right: return 'r'
        if top: return 't'
        if bottom: return 'b'
        return None

    def hoverMoveEvent(self, event):
        d = self._get_resize_dir(event.pos())
        if d in ('tl', 'br'): self.setCursor(Qt.SizeFDiagCursor)
        elif d in ('tr', 'bl'): self.setCursor(Qt.SizeBDiagCursor)
        elif d in ('l', 'r'): self.setCursor(Qt.SizeHorCursor)
        elif d in ('t', 'b'): self.setCursor(Qt.SizeVerCursor)
        else: self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        d = self._get_resize_dir(event.pos())
        if d:
            self.resizing = True
            self.resize_dir = d
            self.setFlag(QGraphicsItem.ItemIsMovable, False)
        else:
            self.resizing = False
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            r = self.rect()
            p = event.pos()
            d = self.resize_dir

            if 'l' in d: r.setLeft(p.x())
            if 'r' in d: r.setRight(p.x())
            if 't' in d: r.setTop(p.y())
            if 'b' in d: r.setBottom(p.y())
            
            # Prevent negative width/height
            if r.width() < 10: 
                if 'l' in d: r.setLeft(r.right() - 10)
                else: r.setRight(r.left() + 10)
            if r.height() < 10: 
                if 't' in d: r.setTop(r.bottom() - 10)
                else: r.setBottom(r.top() + 10)

            self.setRect(r)
            self.label.setPos(self.rect().topLeft() + QPointF(0, -20))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setBrush(QBrush(QColor("yellow")))
            painter.setPen(QPen(Qt.black, 1))
            r = self.rect()
            m = self.MARGIN / 2
            pts = [
                r.topLeft(), QPointF(r.center().x(), r.top()), r.topRight(),
                QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()),
                r.bottomLeft(), QPointF(r.center().x(), r.bottom()), r.bottomRight()
            ]
            for p in pts:
                painter.drawRect(QRectF(p.x() - m, p.y() - m, m*2, m*2))
        
    def get_bbox(self):
        # Mapeamos a la escena para incluir movimientos
        scene_rect = self.mapToScene(self.rect()).boundingRect()
        return rect_to_bbox(scene_rect, self.can_w, self.can_h)

class RadioOptionItem(QGraphicsEllipseItem):
    """Punto interactivo para opciones de radio."""
    def __init__(self, group_name: str, option_name: str, nx: float, ny: float, radius: float, can_w: int, can_h: int):
        cx, cy = nx * can_w, ny * can_h
        super().__init__(cx - radius, cy - radius, radius*2, radius*2)
        self.group_name = group_name
        self.option_name = option_name
        self.can_w = can_w
        self.can_h = can_h
        
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        color = QColor(0, 180, 0)
        self.setPen(QPen(color, 2))
        self.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
        
        self.label = QGraphicsTextItem(f"{group_name}: {option_name}", self)
        self.label.setDefaultTextColor(color)
        self.label.setPos(self.rect().topRight() + QPointF(5, -10))
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            color = QColor(0, 255, 255) if self.isSelected() else QColor(0, 180, 0)
            self.setPen(QPen(color, 3 if self.isSelected() else 2))
            self.setZValue(10 if self.isSelected() else 0)
        return super().itemChange(change, value)

    def get_norm_center(self):
        scene_center = self.mapToScene(self.rect().center())
        return [round(scene_center.x() / self.can_w, 6), round(scene_center.y() / self.can_h, 6)]


# ============================================================
# GRAPHICS VIEW CON SOPORTE PAN/ZOOM
# ============================================================

class DocumentView(QGraphicsView):
    item_selected = Signal(str, str) # key, type
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        
        self.panning = False
        self.space_pressed = False

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.space_pressed = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.space_pressed = False
        super().keyReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.NoModifier or event.modifiers() == Qt.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor
            if event.angleDelta().y() > 0:
                self.scale(zoom_in_factor, zoom_in_factor)
            else:
                self.scale(zoom_out_factor, zoom_out_factor)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self.space_pressed):
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.panning = True
            # Falso press para activar el hand drag instantáneamente
            event = QMouseEvent(QEvent.MouseButtonPress, event.pos(), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        super().mousePressEvent(event)
        
        # Notificar selección
        items = self.scene().selectedItems()
        if items:
            item = items[0]
            if isinstance(item, BoxItem):
                self.item_selected.emit(item.key, item.section)
            elif isinstance(item, RadioOptionItem):
                self.item_selected.emit(f"{item.group_name}::{item.option_name}", "radio_groups")

    def mouseReleaseEvent(self, event):
        if self.panning:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.panning = False
            event = QMouseEvent(QEvent.MouseButtonRelease, event.pos(), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        super().mouseReleaseEvent(event)

    def fit_screen(self):
        self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)

    def fit_width(self):
        rect = self.scene().itemsBoundingRect()
        rect.setHeight(self.viewport().height())
        self.fitInView(rect, Qt.KeepAspectRatioByExpanding)

    def zoom_100(self):
        self.resetTransform()


# ============================================================
# MAIN WINDOW
# ============================================================

class CalibrateWindow(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.cfg_path = args.config
        self.cfg = load_config(self.cfg_path)
        self.can_w = int(self.cfg["canonical"]["width"])
        self.can_h = int(self.cfg["canonical"]["height"])
        
        self.history = [copy.deepcopy(self.cfg)]
        self.history_idx = 0
        
        self.setWindowTitle(f"Calibrador de Bloques PRO - {Path(self.cfg_path).name}")
        self.resize(1400, 900)
        
        self.init_ui()
        self.load_page(self.args.page - 1)
        
    def init_ui(self):
        # Toolbar
        toolbar = QToolBar("Principal")
        self.addToolBar(toolbar)
        
        btn_save = QAction("Guardar (S)", self)
        btn_save.triggered.connect(self.save_data)
        btn_save.setShortcut(QKeySequence("S"))
        toolbar.addAction(btn_save)
        
        btn_undo = QAction("Undo (Ctrl+Z)", self)
        btn_undo.triggered.connect(self.undo)
        btn_undo.setShortcut(QKeySequence.Undo)
        toolbar.addAction(btn_undo)
        
        btn_redo = QAction("Redo (Ctrl+Y)", self)
        btn_redo.triggered.connect(self.redo)
        btn_redo.setShortcut(QKeySequence.Redo)
        toolbar.addAction(btn_redo)
        
        toolbar.addSeparator()
        
        btn_fit = QAction("Fit Screen (F)", self)
        btn_fit.triggered.connect(lambda: self.view.fit_screen())
        btn_fit.setShortcut(QKeySequence("F"))
        toolbar.addAction(btn_fit)
        
        btn_100 = QAction("100% (1)", self)
        btn_100.triggered.connect(lambda: self.view.zoom_100())
        btn_100.setShortcut(QKeySequence("1"))
        toolbar.addAction(btn_100)
        
        toolbar.addSeparator()
        
        btn_prev_pg = QAction("Pág Ant", self)
        btn_prev_pg.triggered.connect(lambda: self.load_page(self.current_page - 1))
        toolbar.addAction(btn_prev_pg)
        
        self.lbl_page = QLabel(" Pág: 1 ")
        toolbar.addWidget(self.lbl_page)
        
        btn_next_pg = QAction("Pág Sig", self)
        btn_next_pg.triggered.connect(lambda: self.load_page(self.current_page + 1))
        toolbar.addAction(btn_next_pg)
        
        # Splitter Layout
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)
        
        # Left Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar campo...")
        self.search_box.textChanged.connect(self.filter_list)
        left_layout.addWidget(self.search_box)
        
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.on_list_item_changed)
        left_layout.addWidget(self.list_widget)
        
        # Checkboxes visibilidad
        self.chk_text = QCheckBox("Mostrar Textos (T)")
        self.chk_text.setChecked(True)
        self.chk_text.stateChanged.connect(self.refresh_scene)
        left_layout.addWidget(self.chk_text)
        
        self.chk_sign = QCheckBox("Mostrar Firmas (G)")
        self.chk_sign.setChecked(True)
        self.chk_sign.stateChanged.connect(self.refresh_scene)
        left_layout.addWidget(self.chk_sign)
        
        self.chk_radio = QCheckBox("Mostrar Radios (R)")
        self.chk_radio.setChecked(True)
        self.chk_radio.stateChanged.connect(self.refresh_scene)
        left_layout.addWidget(self.chk_radio)
        
        self.chk_labels = QCheckBox("Mostrar Labels (H)")
        self.chk_labels.setChecked(True)
        self.chk_labels.stateChanged.connect(self.toggle_labels)
        left_layout.addWidget(self.chk_labels)
        
        splitter.addWidget(left_panel)
        
        # Right View
        self.scene = QGraphicsScene()
        self.view = DocumentView(self.scene)
        self.view.item_selected.connect(self.on_scene_item_selected)
        splitter.addWidget(self.view)
        
        splitter.setSizes([300, 1100])
        
        # Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        
        # Global Shortcuts
        self.addAction(self.create_shortcut("T", lambda: self.chk_text.toggle()))
        self.addAction(self.create_shortcut("G", lambda: self.chk_sign.toggle()))
        self.addAction(self.create_shortcut("R", lambda: self.chk_radio.toggle()))
        self.addAction(self.create_shortcut("H", lambda: self.chk_labels.toggle()))
        self.addAction(self.create_shortcut("N", self.select_next))
        self.addAction(self.create_shortcut("P", self.select_prev))

    def create_shortcut(self, key, func):
        act = QAction(self)
        act.setShortcut(QKeySequence(key))
        act.triggered.connect(func)
        return act

    def load_page(self, page_num):
        if page_num < 0: return
        try:
            img = render_page(self.args.input, page_num, self.args.dpi, self.can_w, self.can_h)
            self.current_page = page_num
            self.lbl_page.setText(f" Pág: {self.current_page + 1} ")
            
            qimg = numpy_to_qimage(img)
            self.pixmap = QPixmap.fromImage(qimg)
            self.refresh_scene()
            self.view.fit_screen()
        except Exception as e:
            print(f"Error cargando página: {e}")

    def refresh_scene(self):
        self.scene.clear()
        self.scene.addItem(QGraphicsPixmapItem(self.pixmap))
        
        self.list_widget.clear()
        self.items_map = {}
        
        # Text Fields
        if self.chk_text.isChecked():
            for k, bbox in self.cfg.get("text_fields", {}).items():
                item = BoxItem(k, "text_fields", bbox, self.can_w, self.can_h)
                self.scene.addItem(item)
                self.items_map[k] = item
                self.add_list_item(k, "TEXT")

        # Signature Fields
        if self.chk_sign.isChecked():
            for k, bbox in self.cfg.get("signature_fields", {}).items():
                item = BoxItem(k, "signature_fields", bbox, self.can_w, self.can_h)
                self.scene.addItem(item)
                self.items_map[k] = item
                self.add_list_item(k, "SIGN")

        # Checkboxes/Radios
        if self.chk_radio.isChecked():
            for grp, grp_cfg in self.cfg.get("checkbox_groups", {}).items():
                radius = max(4, int(round(grp_cfg.get("radius_norm", 0.008) * self.can_w)))
                for opt, (nx, ny) in grp_cfg.get("options", {}).items():
                    key = f"{grp}::{opt}"
                    item = RadioOptionItem(grp, opt, nx, ny, radius, self.can_w, self.can_h)
                    self.scene.addItem(item)
                    self.items_map[key] = item
                    self.add_list_item(key, "RADIO")

        self.toggle_labels()

    def add_list_item(self, key, type_str):
        li = QListWidgetItem(f"[{type_str}] {key}")
        li.setData(Qt.UserRole, key)
        self.list_widget.addItem(li)

    def filter_list(self, text):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def on_list_item_changed(self, current, previous):
        if not current: return
        key = current.data(Qt.UserRole)
        item = self.items_map.get(key)
        if item:
            self.scene.clearSelection()
            item.setSelected(True)
            self.view.ensureVisible(item)
            self.status.showMessage(f"Seleccionado: {key}")

    def on_scene_item_selected(self, key, type_str):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.UserRole) == key:
                self.list_widget.setCurrentItem(item)
                break

    def select_next(self):
        idx = self.list_widget.currentRow() + 1
        if idx < self.list_widget.count():
            self.list_widget.setCurrentRow(idx)

    def select_prev(self):
        idx = self.list_widget.currentRow() - 1
        if idx >= 0:
            self.list_widget.setCurrentRow(idx)

    def toggle_labels(self):
        show = self.chk_labels.isChecked()
        for item in self.scene.items():
            if isinstance(item, (BoxItem, RadioOptionItem)):
                item.label.setVisible(show)

    def push_history(self):
        self.history = self.history[:self.history_idx+1]
        self.history.append(copy.deepcopy(self.cfg))
        self.history_idx += 1

    def undo(self):
        if self.history_idx > 0:
            self.history_idx -= 1
            self.cfg = copy.deepcopy(self.history[self.history_idx])
            self.refresh_scene()
            self.status.showMessage("Undo realizado.")

    def redo(self):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self.cfg = copy.deepcopy(self.history[self.history_idx])
            self.refresh_scene()
            self.status.showMessage("Redo realizado.")

    def update_cfg_from_scene(self):
        changed = False
        for key, item in self.items_map.items():
            if isinstance(item, BoxItem):
                new_bbox = item.get_bbox()
                old_bbox = self.cfg[item.section][item.key]
                if new_bbox != old_bbox:
                    self.cfg[item.section][item.key] = new_bbox
                    changed = True
            elif isinstance(item, RadioOptionItem):
                new_c = item.get_norm_center()
                old_c = self.cfg["checkbox_groups"][item.group_name]["options"][item.option_name]
                if new_c != old_c:
                    self.cfg["checkbox_groups"][item.group_name]["options"][item.option_name] = new_c
                    changed = True
        return changed

    def save_data(self):
        if self.update_cfg_from_scene():
            self.push_history()
        save_config(self.cfg_path, self.cfg)
        self.status.showMessage(f"Guardado exitoso en {self.cfg_path}", 3000)

    # Teclado fino
    def keyPressEvent(self, event: QKeyEvent):
        items = self.scene.selectedItems()
        if not items:
            return super().keyPressEvent(event)
            
        item = items[0]
        step = 10 if event.modifiers() == Qt.ShiftModifier else 1
        dx = dy = 0
        
        if event.key() == Qt.Key_Left: dx = -step
        elif event.key() == Qt.Key_Right: dx = step
        elif event.key() == Qt.Key_Up: dy = -step
        elif event.key() == Qt.Key_Down: dy = step
        else:
            return super().keyPressEvent(event)
            
        if event.modifiers() == Qt.AltModifier and isinstance(item, BoxItem):
            # Redimensionar (agrandar/achicar bottom-right)
            r = item.rect()
            r.setRight(r.right() + dx)
            r.setBottom(r.bottom() + dy)
            item.setRect(r.normalized())
        else:
            # Mover
            item.moveBy(dx, dy)
            
        self.update_cfg_from_scene()


def main():
    ap = argparse.ArgumentParser(description="Calibrador de Bloques PRO")
    ap.add_argument("input", help="Ruta al PDF o imagen")
    ap.add_argument("--config", required=True, help="Ruta al JSON a editar")
    ap.add_argument("--mode", default="text", help="Modo (Legacy, ya no restringe UI)")
    ap.add_argument("--dpi", type=int, default=200, help="DPI de render si es PDF")
    ap.add_argument("--page", type=int, default=1, help="Número de página a calibrar (1-indexed)")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Look moderno
    
    # Modo oscuro base
    dark_palette = app.palette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)

    window = CalibrateWindow(args)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
