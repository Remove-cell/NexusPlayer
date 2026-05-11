import sys, os, json
import time
from datetime import datetime
import vlc
from PySide6.QtWidgets import (QApplication, QMainWindow, QFrame, QVBoxLayout, 
                               QHBoxLayout, QWidget, QPushButton, QSlider, QLabel, 
                               QFileDialog, QInputDialog, QMessageBox, QMenu, QListWidget, 
                               QStackedWidget, QListWidgetItem, QComboBox, QAbstractItemView,
                               QDialog, QFormLayout, QLineEdit)
from PySide6.QtCore import Qt, QTimer, Signal, QRect, QPointF, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPalette, QKeyEvent, QCursor, QActionGroup, QAction, QPixmap, QPainter, QFontDatabase, QShortcut, QKeySequence

# 🌟 2. วางฟังก์ชันนี้ไว้นอกสุดของคลาส เพื่อเอาไว้ชี้เป้าไฟล์ตอนทำ .exe
def resource_path(relative_path):
    """ คืนค่า Path ที่ถูกต้องเสมอ ไม่ว่าจะรันผ่าน Python ปกติ หรือรันผ่าน .exe """
    try:
        # PyInstaller จะสร้างโฟลเดอร์จำลองชื่อ _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ==========================================
# ℹ️ คลาสหน้าต่าง Media Info
# ==========================================
class MediaInfoDialog(QDialog):
    def __init__(self, main_window, info_data):
        super().__init__(main_window)
        self.setWindowTitle("Media Information")
        self.setMinimumWidth(350)
        self.setStyleSheet("background-color: #1C1C1E; color: white; font-size: 13px; border-radius: 8px;")
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        for key, value in info_data.items():
            lbl_key = QLabel(f"<b>{key}:</b>")
            lbl_key.setStyleSheet("color: #8E8E93;")
            lbl_val = QLabel(str(value))
            lbl_val.setWordWrap(True)
            form_layout.addRow(lbl_key, lbl_val)
        layout.addLayout(form_layout)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton { background-color: #5E5CE6; color: white; border-radius: 5px; padding: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #7D7AFF; }
            QPushButton:pressed { margin-top: 1px; }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

# ==========================================
# 📋 คลาส Playlist 
# ==========================================
class PlaylistWidget(QListWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setStyleSheet("""
            QListWidget { background-color: transparent; color: white; border: none; outline: none; padding: 5px; font-size: 13px; }
            QListWidget::item { padding: 8px; border-radius: 6px; margin-bottom: 2px; }
            QListWidget::item:selected { background-color: #5E5CE6; font-weight: bold; }
            QListWidget::item:hover:!selected { background-color: #2C2C2E; }
        """)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Shift, Qt.Key_Control, Qt.Key_A): 
            super().keyPressEvent(event)
        elif event.key() == Qt.Key_Delete: 
            self.main_window.remove_selected_items()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.currentItem():
                self.main_window.play_selected_from_list(self.currentItem())
        else: 
            self.main_window.keyPressEvent(event)

# ==========================================
# 🖼️ คลาสรูปภาพอัจฉริยะ
# ==========================================
class ImageFrame(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setStyleSheet("background-color: black;")
        self.setMouseTracking(True)
        self._pixmap = None
        self.zoom_factor = 1.0
        self.offset = QPointF(0, 0)
        self.is_panning = False
        self.last_mouse_pos = QPointF()

    def set_image(self, path):
        self._pixmap = QPixmap(path)
        self.reset_view()

    def reset_view(self):
        self.zoom_factor = 1.0
        if self._pixmap and not self._pixmap.isNull():
            fit_scale = min(self.width() / self._pixmap.width(), self.height() / self._pixmap.height())
            w = self._pixmap.width() * fit_scale
            h = self._pixmap.height() * fit_scale
            self.offset = QPointF((self.width() - w) / 2, (self.height() - h) / 2)
        else: self.offset = QPointF(0, 0)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.zoom_factor == 1.0: self.reset_view()

    def paintEvent(self, event):
        if not self._pixmap or self._pixmap.isNull(): return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        fit_scale = min(self.width() / self._pixmap.width(), self.height() / self._pixmap.height())
        current_scale = fit_scale * self.zoom_factor
        current_w = self._pixmap.width() * current_scale
        current_h = self._pixmap.height() * current_scale
        painter.drawPixmap(int(self.offset.x()), int(self.offset.y()), int(current_w), int(current_h), self._pixmap)

    def wheelEvent(self, event):
        if not self._pixmap: return
        old_zoom = self.zoom_factor
        if event.angleDelta().y() > 0: self.zoom_factor *= 1.15
        else: self.zoom_factor /= 1.15
        self.zoom_factor = max(1.0, min(self.zoom_factor, 50.0)) 
        mouse_pos = event.position()
        if self.zoom_factor == 1.0: self.reset_view()
        else:
            scale_ratio = self.zoom_factor / old_zoom
            self.offset = mouse_pos - (mouse_pos - self.offset) * scale_ratio
            self.update()
        self.main_window.show_zoom_osd(self.zoom_factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.zoom_factor > 1.0:
            self.is_panning = True
            self.last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            
    def mouseMoveEvent(self, event):
        self.main_window.wake_up_ui()
        if self.is_panning:
            delta = event.position() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton: 
            self.is_panning = False
            self.setCursor(Qt.ArrowCursor)
        elif event.button() == Qt.RightButton: 
            self.main_window.show_context_menu(event.globalPosition().toPoint())
            
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton: self.main_window.toggle_fullscreen()

# ==========================================
# 🎬 คลาสวิดีโอคอนเทนเนอร์
# ==========================================
class VideoContainer(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setStyleSheet("background-color: black;")
        self.setMouseTracking(True)
        self.video_frame = QFrame(self)
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setMouseTracking(True)
        self.zoom_factor = 1.0
        self.offset = QPointF(0, 0)
        self.is_panning = False
        self.last_mouse_pos = QPointF()

    def reset_view(self):
        self.zoom_factor = 1.0
        self.offset = QPointF(0, 0)
        self.video_frame.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.zoom_factor == 1.0: self.reset_view()
        else: self.apply_transform()

    def apply_transform(self):
        w = self.width() * self.zoom_factor
        h = self.height() * self.zoom_factor
        self.video_frame.setGeometry(int(self.offset.x()), int(self.offset.y()), int(w), int(h))

    def wheelEvent(self, event):
        if self.main_window.media_player.get_media() is None: return
        old_zoom = self.zoom_factor
        if event.angleDelta().y() > 0: self.zoom_factor *= 1.15
        else: self.zoom_factor /= 1.15
        self.zoom_factor = max(1.0, min(self.zoom_factor, 10.0))
        mouse_pos = event.position()
        if self.zoom_factor == 1.0: self.reset_view()
        else:
            scale_ratio = self.zoom_factor / old_zoom
            self.offset = mouse_pos - (mouse_pos - self.offset) * scale_ratio
            self.apply_transform()
        self.main_window.show_zoom_osd(self.zoom_factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.zoom_factor > 1.0:
            self.is_panning = True
            self.last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            
    def mouseMoveEvent(self, event):
        self.main_window.wake_up_ui()
        if self.is_panning:
            delta = event.position() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = event.position()
            self.apply_transform()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton: 
            self.is_panning = False
            self.setCursor(Qt.ArrowCursor)
        elif event.button() == Qt.RightButton: 
            self.main_window.show_context_menu(event.globalPosition().toPoint())
            
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton: self.main_window.toggle_fullscreen()

class ClickableLabel(QLabel):
    clicked = Signal()
    def __init__(self, text="00:00 / 00:00"):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter) 
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            background-color: #2C2C2E; 
            color: #E5E5EA; 
            font-family: monospace; 
            font-size: 11.5px; 
            font-weight: bold; 
            border-radius: 6px; 
            padding: 3px 5px;
        """)
        
        # 🌟 เตรียมตัวแปรสำหรับระบบสไลด์ข้อความ
        self._full_text = text
        self.scroll_pos = 0
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.update_scroll)

    def setText(self, text):
        self._full_text = text
        self.scroll_pos = 0
        # 🌟 เช็กว่าข้อความยาวเกินความกว้างของแคปซูลไหม (ใช้ fontMetrics ตรวจสอบ)
        fm = self.fontMetrics()
        if fm.horizontalAdvance(text) > self.width() - 10:
            # ถ้าข้อความยาวไป ให้เติมช่องว่างหัวท้ายแล้วเริ่มสไลด์!
            self._full_text = "   " + text + "   " 
            self.scroll_timer.start(150) # ความเร็วในการสไลด์ (150ms)
        else:
            # ถ้าข้อความสั้น (เช่น ตัวเลขเวลาปกติ) ให้หยุดสไลด์
            self.scroll_timer.stop()
            super().setText(text)

    def update_scroll(self):
        if len(self._full_text) > 0:
            # 🌟 สมการสไลด์ข้อความจาก "ซ้ายไปขวา" ตามคำสั่งบอส
            self.scroll_pos = (self.scroll_pos + 1) % len(self._full_text)
            display_str = self._full_text[self.scroll_pos:] + self._full_text[:self.scroll_pos]
            super().setText(display_str)
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton: self.clicked.emit()

# ==========================================
# 🌌 คลาสหน้าจอเริ่มต้น (Empty State)
# ==========================================
class EmptyStateFrame(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        # ไอคอนตรงกลาง
        icon_label = QLabel("🎬")
        icon_label.setStyleSheet("font-size: 70px; color: #48484A;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # ข้อความหลัก
        text_label = QLabel("Drag & Drop Media Here")
        text_label.setStyleSheet("font-size: 24px; color: #8E8E93; font-weight: bold;")
        text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(text_label)

        # ข้อความรอง
        sub_text = QLabel("or use the playlist to add files, folders, and URLs")
        sub_text.setStyleSheet("font-size: 14px; color: #636366;")
        sub_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub_text)

# ==========================================
# 🌐 คลาสหน้าต่างจัดการ URL และประวัติ
# ==========================================
class URLHistoryDialog(QDialog):
    def __init__(self, history_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 Open URL & History")
        self.setMinimumSize(450, 300)
        if parent: self.setStyleSheet(parent.styleSheet())
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 1. โซนกรอก URL
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://... (วางลิงก์ที่นี่)")
        input_layout.addWidget(self.url_input)
        
        self.btn_play = QPushButton("▶️ Play")
        self.btn_play.setStyleSheet("background-color: #34C759; color: white; font-weight: bold; padding: 6px 15px; border-radius: 6px;")
        input_layout.addWidget(self.btn_play)
        layout.addLayout(input_layout)
        
# 2. โซนแสดงประวัติ
        layout.addWidget(QLabel("📜 ประวัติการเข้าชม:"))
        self.history_list_widget = QListWidget()
        self.history_list_widget.addItems(history_list)
        
        # 🌟 เวทมนตร์แยกเลเยอร์: ทำให้กล่องประวัติมีมิติ ไม่กลืนกับพื้นหลัง
        self.history_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2C2C2E; /* สีเทาเข้มให้ลอยออกมาจากสีพื้นฐาน */
                border: 1px solid #3A3A3D; /* เส้นขอบบางๆ ตัดสายตา */
                border-radius: 6px; /* ขอบโค้งมน */
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px; /* เว้นระยะบรรทัดให้อ่านง่าย */
                border-radius: 4px;
                color: #E5E5EA;
            }
            QListWidget::item:hover {
                background-color: #3A3A3D; /* สว่างขึ้นตอนเอาเมาส์ชี้ */
            }
            QListWidget::item:selected {
                background-color: #5E5CE6; /* เรืองแสงสีม่วงตอนกดเลือก */
                color: white;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.history_list_widget)
        
        # 🌟 ทำให้กดเลือกประวัติแล้วข้อความเด้งขึ้นไปบนช่องกรอกอัตโนมัติ
        self.history_list_widget.itemClicked.connect(lambda item: self.url_input.setText(item.text()))
        self.history_list_widget.itemDoubleClicked.connect(self.accept)
                
        # 3. โซนปุ่มจัดการ (ลบ/ล้าง)
        manage_layout = QHBoxLayout()
        self.btn_del_selected = QPushButton("➖ ลบที่เลือก")
        self.btn_del_selected.setStyleSheet("background-color: #FF9500; color: white; font-weight: bold; padding: 6px 15px; border-radius: 6px;")
        self.btn_clear_all = QPushButton("🗑️ ล้างทั้งหมด")
        self.btn_clear_all.setStyleSheet("background-color: #FF3B30; color: white; font-weight: bold; padding: 6px 15px; border-radius: 6px;")
        
        manage_layout.addWidget(self.btn_del_selected)
        manage_layout.addWidget(self.btn_clear_all)
        manage_layout.addStretch()
        layout.addLayout(manage_layout)
        
        # เชื่อมปุ่มต่างๆ
        self.btn_play.clicked.connect(self.accept)
        self.btn_del_selected.clicked.connect(self.delete_selected)
        self.btn_clear_all.clicked.connect(self.history_list_widget.clear)
        
    def delete_selected(self):
        for item in self.history_list_widget.selectedItems():
            self.history_list_widget.takeItem(self.history_list_widget.row(item))
            
    def get_url(self):
        return self.url_input.text().strip()
        
    def get_history(self):
        # ดึงประวัติที่เหลืออยู่ (หลังจากโดนลบ) กลับไปเซฟ
        return [self.history_list_widget.item(i).text() for i in range(self.history_list_widget.count())]
    
# ==========================================
# 🎚️ คลาสสไลเดอร์แบบกระโดด (Jump Slider)
# ==========================================
class JumpSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # คำนวณพิกัดที่เมาส์จิ้ม แล้วกระโดดไปตรงนั้นทันที!
            val = int((event.position().x() / self.width()) * self.maximum())
            self.setValue(val)
            self.sliderMoved.emit(val)
        super().mousePressEvent(event)

# ==========================================
# 🌟 หน้าต่างหลัก NexusPlayer (Premium UI)
# ==========================================
class NexusPlayer(QMainWindow):
    def __init__(self, initial_files=None):
        super().__init__()
        self.setWindowTitle("NexusPlayer - Phase 31: Premium UI Design")
        self.resize(1050, 650)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        
        self.history_file = os.path.join(os.path.expanduser('~'), '.nexus_history.json')
        self.playback_history = {}
        self.is_resume_enabled = True
        self.has_resumed_current = False
        self.current_media_type = "video" 
        self.current_playing_path = "" 
        self.loop_mode = 1 
        self.last_volume = 80 
        
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.playback_history = json.load(f)
            except: pass

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # 🌟 1. ลบ main_split ทิ้ง! ให้ media_stack (หน้าจอวิดีโอ) ยึดพื้นที่ 100%
        self.media_stack = QStackedWidget(self.central_widget)
        self.layout.addWidget(self.media_stack, stretch=1)

        self.empty_state_frame = EmptyStateFrame(self)
        self.media_stack.addWidget(self.empty_state_frame)
        self.media_stack.setCurrentWidget(self.empty_state_frame) # สั่งให้โชว์หน้านี้เป็นหน้าแรก
        
        self.video_container = VideoContainer(self)
        self.media_stack.addWidget(self.video_container)
        self.image_frame = ImageFrame(self)
        self.media_stack.addWidget(self.image_frame)
        
        # 📋 Playlist Section (แผงกระจกลอยทับ)
        self.playlist_container = QWidget(self.central_widget) 
        self.playlist_container.setFixedWidth(300)
        self.playlist_container.setObjectName("GlassDrawer")
        
        # 🌟 ปรับลดตัวเลข 220 ตัวสุดท้ายลงเหลือ 140 (ยิ่งน้อยยิ่งใสทะลุวิดีโอ) 🌟
        self.playlist_container.setStyleSheet("""
            QWidget#GlassDrawer { 
                background-color: rgba(20, 20, 22, 140); /* 🪟 โปร่งแสง 55% มองทะลุวิดีโอชัดเจน! */
                border-left: 1px solid rgba(94, 92, 230, 180); /* ขอบเรืองแสงสีม่วง */
            }
            QListWidget { background-color: transparent; border: none; }
        """)
        self.playlist_container.hide()
        pl_layout = QVBoxLayout(self.playlist_container)
        pl_layout.setContentsMargins(0, 0, 0, 0)
        pl_layout.setSpacing(0)
        # ❌ เราเตะคำสั่งยัด Playlist ลง Layout ทิ้งไปแล้ว มันเลยลอยเป็นอิสระ!

        # 📋 แถบเครื่องมือ Playlist (Meatballs Menu Layout)
        self.pl_toolbar = QWidget()
        self.pl_toolbar.setStyleSheet("background-color: #1A1A1D; border-bottom: 1px solid #222;")
        pl_tb_layout = QHBoxLayout(self.pl_toolbar)
        pl_tb_layout.setContentsMargins(8, 8, 8, 8)
        pl_tb_layout.setSpacing(5)

        # 1. ปุ่ม Add File
        self.btn_add_file = QPushButton("➕")
        self.btn_add_file.setFixedWidth(28)
        self.btn_add_file.setToolTip("Add File to Queue")
        self.btn_add_file.setFocusPolicy(Qt.NoFocus)
        self.btn_add_file.setCursor(Qt.PointingHandCursor)
        self.btn_add_file.setStyleSheet(self.get_btn_style("#34C759", "#32D74B"))
        self.btn_add_file.clicked.connect(self.enqueue_files)
        pl_tb_layout.addWidget(self.btn_add_file)

        # 2. กล่องตัวกรอง
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["📝 Custom", "🔤 Name", "📅 Date", "📦 Size", "🏷️ Type"])
        self.sort_combo.setFocusPolicy(Qt.NoFocus)
        self.sort_combo.setCursor(Qt.PointingHandCursor)
        self.sort_combo.currentIndexChanged.connect(self.sort_playlist)
        pl_tb_layout.addWidget(self.sort_combo, stretch=1)

        # 🌟 [เพิ่มใหม่] ปุ่มสลับทิศทาง (มากไปน้อย / น้อยไปมาก)
        self.sort_ascending = True 
        self.btn_sort_direction = QPushButton("🔼")
        self.btn_sort_direction.setFixedWidth(28)
        self.btn_sort_direction.setToolTip("Toggle Sort Order")
        self.btn_sort_direction.setFocusPolicy(Qt.NoFocus)
        self.btn_sort_direction.setCursor(Qt.PointingHandCursor)
        self.btn_sort_direction.setStyleSheet(self.get_btn_style("#48484A", "#636366"))
        self.btn_sort_direction.clicked.connect(self.toggle_sort_direction)
        pl_tb_layout.addWidget(self.btn_sort_direction)

        # 3. ปุ่ม Remove
        self.btn_remove = QPushButton("➖")
        self.btn_remove.setFixedWidth(28)
        self.btn_remove.setToolTip("Remove Selected")
        self.btn_remove.setFocusPolicy(Qt.NoFocus)
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.setStyleSheet(self.get_btn_style("#FF3B30", "#FF453A"))
        self.btn_remove.clicked.connect(self.remove_selected_items)
        pl_tb_layout.addWidget(self.btn_remove)

        # 4. ปุ่ม 3 จุด (Meatballs Menu)
        self.btn_more = QPushButton("⋮")
        self.btn_more.setFixedWidth(28)
        self.btn_more.setToolTip("More Options")
        self.btn_more.setFocusPolicy(Qt.NoFocus)
        self.btn_more.setCursor(Qt.PointingHandCursor)
        self.btn_more.setStyleSheet(self.get_btn_style("#48484A", "#636366"))
        self.btn_more.clicked.connect(self.show_playlist_more_menu)
        pl_tb_layout.addWidget(self.btn_more)

        # 🌟 นี่คือ "กาว" บรรทัดที่หายไปครับ! สั่งเอาแถบเครื่องมือไปประกอบร่างใน Playlist 🌟
        pl_layout.addWidget(self.pl_toolbar)

        self.playlist_widget = PlaylistWidget(self)
        self.playlist_widget.itemDoubleClicked.connect(self.play_selected_from_list)
        pl_layout.addWidget(self.playlist_widget)

# 🎛️ Control Panel Section (Pro Layout 2-Tier)
        self.control_panel = QWidget()
        self.control_panel.setStyleSheet("background-color: #1A1A1D; border-top: 1px solid #222;")
        self.layout.addWidget(self.control_panel)
        
        # 🌟 เปลี่ยนเป็นแนวตั้ง (VBoxLayout) เพื่อวาง Timeline ไว้ชั้นบน
        self.control_main_layout = QVBoxLayout(self.control_panel)
        self.control_main_layout.setContentsMargins(15, 10, 15, 15)
        self.control_main_layout.setSpacing(8)
        
        # === 🔼 แถวบน: Timeline เต็มจอความกว้าง ===
        self.timeline = JumpSlider(Qt.Horizontal) # 🌟 ใช้สไลเดอร์ตัวใหม่ที่เราสร้าง!
        self.timeline.setMaximum(1000)
        self.timeline.setFocusPolicy(Qt.NoFocus)
        self.timeline.setCursor(Qt.PointingHandCursor)
        self.timeline.setToolTip("Seek Timeline")
        
        # 🌟 ระบบดักจับการแย่งเมาส์ (ห้ามวิดีโออัปเดตตอนเรากำลังรูด)
        self._is_seeking = False
        self.timeline.sliderPressed.connect(self.on_seek_start)
        self.timeline.sliderReleased.connect(self.on_seek_end)
        self.timeline.sliderMoved.connect(self.set_position)
        self.control_main_layout.addWidget(self.timeline)

        # === 🔽 แถวล่าง: ปุ่มควบคุมจัดกลุ่ม ซ้าย-ขวา ===
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)
        self.control_main_layout.addLayout(self.btn_layout)

        # --- 🟢 กลุ่มซ้าย (ควบคุมการเล่น + เสียง) ---
        self.prev_btn = QPushButton("⏮") # 🌟 เพิ่มปุ่มย้อนกลับ
        self.prev_btn.setFixedWidth(35)
        self.prev_btn.setFocusPolicy(Qt.NoFocus)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.setStyleSheet(self.get_btn_style("#48484A", "#636366"))
        self.prev_btn.setToolTip("Previous (P)")
        self.prev_btn.clicked.connect(self.play_previous)
        self.btn_layout.addWidget(self.prev_btn)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedWidth(75)
        self.play_btn.setFocusPolicy(Qt.NoFocus)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setStyleSheet(self.get_btn_style("#34C759", "#32D74B"))
        self.play_btn.setToolTip("Play/Pause (Space)")
        self.play_btn.clicked.connect(self.toggle_play)
        self.btn_layout.addWidget(self.play_btn)

        self.next_btn = QPushButton("⏭") # 🌟 เพิ่มปุ่มถัดไป
        self.next_btn.setFixedWidth(35)
        self.next_btn.setFocusPolicy(Qt.NoFocus)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setStyleSheet(self.get_btn_style("#48484A", "#636366"))
        self.next_btn.setToolTip("Next (N)")
        self.next_btn.clicked.connect(self.play_next)
        self.btn_layout.addWidget(self.next_btn)

        self.time_label = ClickableLabel("00:00 / 00:00")
        self.time_display_mode = 0
        self.time_label.setFixedWidth(140) # ลดความเทอะทะลงอีกนิด
        self.time_label.setToolTip("Click to change time format")
        self.time_label.clicked.connect(self.toggle_time_mode)
        self.btn_layout.addWidget(self.time_label)
        
        self.vol_lock_btn = QPushButton("🔒")
        self.vol_lock_btn.setFixedWidth(25)
        self.vol_lock_btn.setStyleSheet("background-color: transparent; color: #8E8E93; border: none; font-size: 15px;")
        self.vol_lock_btn.setFocusPolicy(Qt.NoFocus)
        self.vol_lock_btn.setCursor(Qt.PointingHandCursor)
        self.vol_lock_btn.setToolTip("Unlock Extra Volume (200%)")
        self.is_volume_unlocked = False
        self.vol_lock_btn.clicked.connect(self.toggle_volume_lock)
        self.btn_layout.addWidget(self.vol_lock_btn)

        self.volume_slider = JumpSlider(Qt.Horizontal)
        self.volume_slider.setMaximum(100) 
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setFocusPolicy(Qt.NoFocus)
        self.volume_slider.setCursor(Qt.PointingHandCursor)
        self.volume_slider.setToolTip("Adjust Volume (Up/Down Arrow)")
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.btn_layout.addWidget(self.volume_slider)

        # 🚀 สปริงดัน: ดันปุ่มกลุ่มซ้ายให้อยู่ซ้าย และกลุ่มขวาไปชิดขวาสุด
        self.btn_layout.addStretch()

        # --- 🔵 กลุ่มขวา (การตั้งค่า + เครื่องมือเสริม) ---
        self.speed_btn = QPushButton("1.0x")
        self.speed_btn.setFixedWidth(45)
        self.speed_btn.setStyleSheet("background-color: transparent; color: #E5E5EA; font-weight: bold; border: none;")
        self.speed_btn.setCursor(Qt.PointingHandCursor)
        self.speed_btn.setFocusPolicy(Qt.NoFocus)
        self.speed_btn.setToolTip("Reset Speed (=)\nIncrease/Decrease ( [ or ] )")
        self.speed_btn.clicked.connect(self.reset_speed)
        self.btn_layout.addWidget(self.speed_btn)

        self.loop_btn = QPushButton("🔂") # เอาตัวเลข 1 ออก ให้เป็นไอคอนมินิมอล
        self.loop_btn.setFixedWidth(35)
        self.loop_btn.setFocusPolicy(Qt.NoFocus)
        self.loop_btn.setCursor(Qt.PointingHandCursor)
        self.loop_btn.setStyleSheet(self.get_btn_style("#32ADE6", "#41B6E6"))
        self.loop_btn.setToolTip("Toggle Loop Mode")
        self.loop_btn.clicked.connect(self.toggle_loop_mode)
        self.btn_layout.addWidget(self.loop_btn)

        self.resume_btn = QPushButton("⏳") # เปลี่ยนเป็นไอคอนล้วน
        self.resume_btn.setFixedWidth(35)
        self.resume_btn.setFocusPolicy(Qt.NoFocus)
        self.resume_btn.setCursor(Qt.PointingHandCursor)
        self.resume_btn.setStyleSheet(self.get_btn_style("#FF2D55", "#FF375F"))
        self.resume_btn.setToolTip("Toggle Auto-Resume")
        self.resume_btn.clicked.connect(self.toggle_resume_mode)
        self.btn_layout.addWidget(self.resume_btn)

        self.open_btn = QPushButton("📂")
        self.open_btn.setFixedWidth(35)
        self.open_btn.setFocusPolicy(Qt.NoFocus)
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setStyleSheet(self.get_btn_style("#5E5CE6", "#7D7AFF"))
        self.open_btn.setToolTip("Open Media File (Ctrl+O)")
        self.open_btn.clicked.connect(self.open_file)
        self.btn_layout.addWidget(self.open_btn)

        self.stream_btn = QPushButton("📺")
        self.stream_btn.setFixedWidth(35)
        self.stream_btn.setFocusPolicy(Qt.NoFocus)
        self.stream_btn.setCursor(Qt.PointingHandCursor)
        self.stream_btn.setStyleSheet(self.get_btn_style("#FF9500", "#FF9F0A"))
        self.stream_btn.setToolTip("Open Network Stream")
        self.stream_btn.clicked.connect(self.open_stream_dialog)
        self.btn_layout.addWidget(self.stream_btn)

        self.toggle_pl_btn = QPushButton("📝") # ถอดคำว่า List ออก
        self.toggle_pl_btn.setFixedWidth(35)
        self.toggle_pl_btn.setFocusPolicy(Qt.NoFocus)
        self.toggle_pl_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_pl_btn.setStyleSheet(self.get_btn_style("#48484A", "#636366"))
        self.toggle_pl_btn.setToolTip("Toggle Playlist (Ctrl+L)")
        self.toggle_pl_btn.clicked.connect(self.toggle_playlist_ui)
        self.btn_layout.addWidget(self.toggle_pl_btn)

        # 🌟 เสียบปุ่มลูกโลก (URL History) แทรกตรงกลางตรงนี้ครับ!
        self.url_btn = QPushButton("🌐")
        self.url_btn.setFixedWidth(35)
        self.url_btn.setFocusPolicy(Qt.NoFocus)
        self.url_btn.setCursor(Qt.PointingHandCursor)
        self.url_btn.setStyleSheet(self.get_btn_style("#48484A", "#636366"))
        self.url_btn.setToolTip("Open URL & History (Ctrl+U)")
        self.url_btn.clicked.connect(self.open_url_dialog)
        self.btn_layout.addWidget(self.url_btn)

        self.fullscreen_btn = QPushButton("⛶") # ถอดคำว่า Full ออก
        self.fullscreen_btn.setFixedWidth(35)
        self.fullscreen_btn.setFocusPolicy(Qt.NoFocus)
        self.fullscreen_btn.setCursor(Qt.PointingHandCursor)
        self.fullscreen_btn.setStyleSheet(self.get_btn_style("#8E8E93", "#AEAEB2"))
        self.fullscreen_btn.setToolTip("Fullscreen (F / F11)")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.btn_layout.addWidget(self.fullscreen_btn)

        self.vlc_instance = vlc.Instance("--quiet")
        self.media_player = self.vlc_instance.media_player_new()
        self.media_player.set_hwnd(self.video_container.video_frame.winId())
        self.media_player.audio_set_volume(80)
        self.media_player.video_set_mouse_input(False)
        self.media_player.video_set_key_input(False)

        self._handling_end = False 
        self.playback_rate = 1.0
        self.is_speed_on_cooldown = False
        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.setInterval(1000)
        self.cooldown_timer.timeout.connect(self.deactivate_cooldown)

        self.pending_skip_seconds = 0
        self.skip_execute_timer = QTimer(self)
        self.skip_execute_timer.setSingleShot(True)
        self.skip_execute_timer.setInterval(400) 
        self.skip_execute_timer.timeout.connect(self.execute_skip)

        self.is_showing_osd = False
        self.osd_display_timer = QTimer(self)
        self.osd_display_timer.setSingleShot(True)
        self.osd_display_timer.setInterval(1500)
        self.osd_display_timer.timeout.connect(self.clear_osd)

        self.is_mini_player = False
        self.saved_geometry = QRect() 
        self.video_aspect_ratio = 16.0 / 9.0  
        self.last_snapped_w = 480
        self.last_snapped_h = 270
        self._is_snapping = False

        self.snap_timer = QTimer(self)
        self.snap_timer.setSingleShot(True)
        self.snap_timer.setInterval(150) 
        self.snap_timer.timeout.connect(self.snap_to_aspect_ratio)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()

        self.cinema_timer = QTimer(self)
        self.cinema_timer.setInterval(3000)
        self.cinema_timer.timeout.connect(self.hide_ui_for_cinema)
        self.cinema_timer.start()

        # 🌟 โหลดฟอนต์ส่วนตัว (ฝังเข้าแอป)
        self.custom_font_family = "'Segoe UI', -apple-system, sans-serif" # ฟอนต์สำรองกันเหนียว
        
        # 📌 เปลี่ยนชื่อ "Prompt-Regular.ttf" เป็นชื่อไฟล์ฟอนต์ของบอส
        font_path = resource_path("GoogleSans_17pt-Regular.ttf") 
        
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                # ดึงชื่อฟอนต์ที่โหลดสำเร็จมาเก็บไว้
                self.custom_font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
                
        # 🌟 เตรียมไฟล์จำประวัติ URL และผูกคีย์ลัด
        self.url_history_file = resource_path("url_history.json")
        self.load_url_history()
        
        # 🎯 กลุ่มคีย์ลัดระดับ Global (QShortcut) กดตรงไหนก็ติดชัวร์!
        self.shortcut_url = QShortcut(QKeySequence("Ctrl+U"), self)
        self.shortcut_url.activated.connect(self.open_url_dialog)

        self.shortcut_playlist = QShortcut(QKeySequence("Ctrl+L"), self)
        self.shortcut_playlist.activated.connect(self.toggle_playlist_ui)

        self.shortcut_add_folder = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        self.shortcut_add_folder.activated.connect(self.enqueue_folder)        

        # 🌟 เรียกใช้เวทมนตร์ QSS Theme (บรรทัดเดิมที่มีอยู่แล้ว)
        self.apply_premium_theme()

        if initial_files:
            QTimer.singleShot(100, lambda: self.load_initial_files(initial_files))

# ==========================================
    # 🎨 เวทมนตร์ UI (Helper Methods)
    # ==========================================
    def get_btn_style(self, base_color, hover_color):
        """ระบบช่วยสร้าง CSS ให้ปุ่มมีเอฟเฟกต์ยุบตัวและ Hover แบบอัตโนมัติ"""
        return f"""
            QPushButton {{ background-color: {base_color}; color: white; border-radius: 5px; padding: 5px; font-weight: bold; border: none; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:pressed {{ background-color: {base_color}; margin-top: 1px; }}
        """

    def apply_premium_theme(self):
        """ยัดสไตล์ชีทแบบ Premium Dark Theme เข้าไปในแอป"""
        
        # 🌟 ดึงชื่อฟอนต์ที่เราฝังไว้มาใช้งาน
        font_name = getattr(self, 'custom_font_family', "'Segoe UI'")
        
        # 🌟 ลบตัว f ออกไปแล้ว และใช้คำว่า CUSTOM_FONT_HERE เพื่อแทนที่ด้วย .replace() ตอนท้ายสุดครับ
        qss = """
        QWidget {
            font-family: "CUSTOM_FONT_HERE", 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif;
            color: #E5E5EA;
        }
        QMainWindow {
            background-color: #000000;
        }
        QSlider {
            outline: none; 
            background: transparent;
        }
        QSlider::groove:horizontal {
            background: #3A3A3D; 
            height: 4px; 
            border-radius: 2px;
        }
        QSlider::sub-page:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5E5CE6, stop:1 #8E8CFF); 
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #FFFFFF;
            border: 2px solid #5E5CE6; 
            width: 14px;
            height: 14px;
            margin: -5px 0px; 
            border-radius: 7px; 
        }
        QSlider::handle:horizontal:hover {
            background: #5E5CE6; 
            border: 2px solid #FFFFFF; 
        }
        QSlider::handle:horizontal:pressed {
            background: #32ADE6; 
            border: 2px solid #FFFFFF;
        }
        QScrollBar:vertical {
            background-color: transparent;
            width: 10px;
            margin: 0px 2px 0px 2px; 
        }
        QScrollBar::handle:vertical {
            background-color: #48484A;
            min-height: 40px;
            border-radius: 3px; 
        }
        QScrollBar::handle:vertical:hover {
            background-color: #5E5CE6; 
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
            border: none;
            background: none;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        QScrollBar:horizontal {
            background-color: transparent;
            height: 10px;
            margin: 2px 0px 2px 0px;
        }
        QScrollBar::handle:horizontal {
            background-color: #48484A;
            min-width: 40px;
            border-radius: 3px;
        }
        QScrollBar::handle:horizontal:hover {
            background-color: #5E5CE6;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
            border: none;
            background: none;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
        QComboBox QAbstractItemView {
            background-color: #2C2C2E;
            color: white;
            selection-background-color: #5E5CE6;
            border-radius: 4px;
            outline: none;
            border: none;
        }
        QMessageBox, QDialog, QInputDialog {
            background-color: #1C1C1E;
            color: #FFFFFF;
        }
        QMessageBox QLabel, QInputDialog QLabel {
            color: #FFFFFF;
            font-size: 13px;
        }
        QMessageBox QPushButton, QInputDialog QPushButton {
            background-color: #48484A;
            color: white;
            border-radius: 4px;
            padding: 6px 20px;
            font-weight: bold;
            min-width: 60px;
        }
        QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
            background-color: #5E5CE6;
        }
        QLineEdit {
            background-color: #2C2C2E;
            color: #FFFFFF;
            border: 1px solid #3A3A3D;
            border-radius: 4px;
            padding: 6px;
            font-size: 13px;
        }
        QLineEdit:focus {
            border: 1px solid #5E5CE6;
        }
        QToolTip {
            background-color: #121214;
            color: #FFFFFF;
            border: 2px solid #5E5CE6;
            border-radius: 6px;
            padding: 6px 12px;
            font-family: "CUSTOM_FONT_HERE", 'Segoe UI', -apple-system, sans-serif;
            font-size: 12px;
            font-weight: normal;
        }
        """.replace("CUSTOM_FONT_HERE", font_name) # 🌟 ใช้คำสั่ง replace นำชื่อฟอนต์มาเสียบแทนที่ตรงนี้ครับ!
        
        self.setStyleSheet(qss)

    # ==========================================
    # ฟังก์ชันการทำงานทั้งหมดเหมือน V.30
    # ==========================================
    def export_playlist(self):
        if self.playlist_widget.count() == 0:
            QMessageBox.information(self, "Export Playlist", "Playlist is empty.")
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Playlist", "", "Nexus Playlist (*.json)")
        if filepath:
            paths = [self.playlist_widget.item(i).data(Qt.UserRole) for i in range(self.playlist_widget.count())]
            try:
                with open(filepath, 'w', encoding='utf-8') as f: json.dump(paths, f, indent=4)
                self.wake_up_ui(); self.is_showing_osd = True
                self.time_label.setText("💾 Playlist Saved"); self.osd_display_timer.start(2500)
            except Exception as e: QMessageBox.warning(self, "Error", f"Failed to save playlist:\n{str(e)}")

    def import_playlist(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Playlist", "", "Nexus Playlist (*.json)")
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f: paths = json.load(f)
                if self.playlist_widget.count() > 0:
                    if QMessageBox.question(self, "Load Playlist", "Do you want to clear current playlist before loading?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                        self.clear_playlist()
                for p in paths: self.add_to_playlist(p, play_now=False)
                if self.playlist_widget.count() > 0 and not self.media_player.is_playing():
                    self.load_media(self.playlist_widget.item(0).data(Qt.UserRole))
                self.wake_up_ui(); self.is_showing_osd = True
                self.time_label.setText("📂 Playlist Loaded"); self.osd_display_timer.start(2500)
            except Exception as e: QMessageBox.warning(self, "Error", f"Failed to load playlist:\n{str(e)}")

    def show_media_info(self):
        if not self.current_playing_path: return
        info = {"File Name": os.path.basename(self.current_playing_path), "Location": self.current_playing_path}
        if self.current_media_type == "image":
            info["Media Type"] = "Image"
            if self.image_frame._pixmap: info["Resolution"] = f"{self.image_frame._pixmap.width()} x {self.image_frame._pixmap.height()} pixels"
            try: info["File Size"] = f"{(os.path.getsize(self.current_playing_path) / 1024):.2f} KB"
            except: pass
        elif self.current_media_type == "video":
            media = self.media_player.get_media()
            if media:
                info["Media Type"] = "Video / Audio Stream"
                media.parse() 
                size = self.media_player.video_get_size(0)
                if size and size[0] > 0: info["Resolution"] = f"{size[0]} x {size[1]} pixels"
                try:
                    tracks = media.tracks_get()
                    if tracks:
                        video_codecs = []; audio_codecs = []
                        for t in tracks:
                            codec_str = t.codec.to_bytes(4, byteorder='little').decode('ascii', errors='ignore')
                            if t.type == vlc.TrackType.video: video_codecs.append(codec_str.upper())
                            elif t.type == vlc.TrackType.audio: audio_codecs.append(f"{codec_str.upper()} ({t.audio.channels} Ch, {t.audio.rate}Hz)")
                        if video_codecs: info["Video Codec"] = ", ".join(video_codecs)
                        if audio_codecs: info["Audio Codec"] = ", ".join(audio_codecs)
                except: info["Track Info"] = "Requires newer VLC binding to parse tracks."
                stats = vlc.MediaStats()
                if media.get_stats(stats): info["Input Bitrate"] = f"{int(stats.demux_bitrate * 8000)} kbps"
        dialog = MediaInfoDialog(self, info)
        dialog.exec()

    def toggle_volume_lock(self):
        if not self.is_volume_unlocked:
            reply = QMessageBox.warning(self, "Volume Warning", "⚠️ Warning: Extra volume (up to 200%) can damage your speakers and hearing.\n\nAre you sure you want to unlock it?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.is_volume_unlocked = True; self.volume_slider.setMaximum(200); self.vol_lock_btn.setText("🔓")
                self.vol_lock_btn.setStyleSheet("background-color: transparent; color: #FF3B30; border: none; font-size: 15px;")
        else:
            self.is_volume_unlocked = False; self.volume_slider.setValue(min(self.volume_slider.value(), 100))
            self.volume_slider.setMaximum(100); self.vol_lock_btn.setText("🔒")
            self.vol_lock_btn.setStyleSheet("background-color: transparent; color: #8E8E93; border: none; font-size: 15px;")

    def set_volume(self, volume):
        self.media_player.audio_set_volume(volume)
        
        # 🌟 เวทมนตร์เปลี่ยนสี: ถ้าเสียงทะลุ 100% ให้จับหลอดเสียงเปลี่ยนเป็นโหมด "Overdrive" (สีไฟบรรลัยกัลป์)
        if volume > 100:
            self.volume_slider.setStyleSheet("""
                QSlider { background: transparent; outline: none; }
                QSlider::groove:horizontal { background: #3A3A3D; height: 4px; border-radius: 2px; }
                QSlider::sub-page:horizontal { 
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF9500, stop:1 #FF3B30); 
                    border-radius: 2px; 
                }
                QSlider::handle:horizontal { 
                    background: #FFFFFF; border: 2px solid #FF3B30; 
                    width: 14px; height: 14px; margin: -5px 0px; border-radius: 7px; 
                }
                QSlider::handle:horizontal:hover { background: #FF3B30; border: 2px solid #FFFFFF; }
                QSlider::handle:horizontal:pressed { background: #FF9500; border: 2px solid #FFFFFF; }
            """)
        else:
            # 🌟 ถ้าเสียงกลับมาปกติ (<= 100) ให้ล้างสีทิ้ง เพื่อให้มันกลับไปดึงสีม่วงจากธีมหลักมาใช้!
            self.volume_slider.setStyleSheet("")

        # อัปเดต Dynamic Island 
        if not self.is_mini_player:
            self.wake_up_ui()
            self.is_showing_osd = True
            if volume > 100: self.time_label.setText(f"🔥 Vol: {volume}%")
            else: self.time_label.setText(f"🔊 Vol: {volume}%" if volume > 0 else "🔇 Muted")
            self.osd_display_timer.start(1000)

    def change_volume_via_keys(self, step):
        max_vol = 200 if self.is_volume_unlocked else 100
        self.volume_slider.setValue(max(0, min(self.volume_slider.value() + step, max_vol)))

    def toggle_mute(self):
        if self.volume_slider.value() > 0:
            self.last_volume = self.volume_slider.value(); self.volume_slider.setValue(0)
        else: self.volume_slider.setValue(self.last_volume if self.last_volume > 0 else 80)

    def add_skip(self, seconds):
        if self.current_media_type != "video" or self.media_player.get_media() is None: return
        self.wake_up_ui(); self.pending_skip_seconds += seconds; self.is_showing_osd = True 
        self.time_label.setText(f"⏩ +{self.pending_skip_seconds}s" if self.pending_skip_seconds > 0 else f"⏪ {self.pending_skip_seconds}s")
        self.skip_execute_timer.start()

    def execute_skip(self):
        if self.pending_skip_seconds == 0 or self.media_player.get_media() is None: return
        current_time_ms = self.media_player.get_time(); total_time_ms = self.media_player.get_length()
        if current_time_ms >= 0:
            self.media_player.set_time(max(0, min(current_time_ms + (self.pending_skip_seconds * 1000), total_time_ms)))
        self.pending_skip_seconds = 0; self.osd_display_timer.start(500) 

    def activate_cooldown(self):
        self.is_speed_on_cooldown = True
        self.speed_btn.setStyleSheet("background-color: rgba(255, 149, 0, 0.15); color: #FF9F0A; font-weight: bold; border-radius: 4px; padding: 2px;")
        self.cooldown_timer.start()

    def deactivate_cooldown(self):
        self.is_speed_on_cooldown = False
        self.speed_btn.setStyleSheet("background-color: transparent; color: #E5E5EA; font-weight: bold; border: none;")

    def change_speed(self, step):
        if self.is_speed_on_cooldown or self.current_media_type != "video" or self.media_player.get_media() is None: return
        new_rate = max(0.25, min(self.playback_rate + step, 4.0))
        if new_rate != self.playback_rate:
            self.playback_rate = new_rate; self.media_player.set_rate(self.playback_rate)
            self.speed_btn.setText(f"{self.playback_rate:.2g}x"); self.activate_cooldown()

    def reset_speed(self):
        if self.is_speed_on_cooldown or self.current_media_type != "video" or self.media_player.get_media() is None: return
        if self.playback_rate != 1.0:
            self.playback_rate = 1.0; self.media_player.set_rate(self.playback_rate)
            self.speed_btn.setText("1.0x"); self.activate_cooldown()

    def enqueue_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Add to Playlist", "", 
            "All Supported Media (*.mp4 *.mkv *.avi *.ts *.mov *.flv *.wmv *.webm *.m4v *.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma *.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff);;Video Files (*.mp4 *.mkv *.avi *.ts *.mov *.flv *.wmv *.webm *.m4v);;Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;Image Files (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff);;All Files (*.*)"
        )
        if file_paths: 
            for path in file_paths: self.add_to_playlist(path, play_now=False)

    def enqueue_url(self):
        url, ok = QInputDialog.getText(self, "Add URL to Playlist", "Enter Video URL:")
        if ok and url:
            clean_url = self.sanitize_url(url)
            if clean_url: self.add_to_playlist(clean_url, play_now=False)

    def enqueue_folder(self):
        """ระบบสแกนและดึงไฟล์มีเดียทั้งหมดในโฟลเดอร์เข้าคิวอัตโนมัติ"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Add")
        if folder_path:
            # นามสกุลไฟล์ที่รองรับทั้งหมด
            supported_exts = {'.mp4', '.mkv', '.avi', '.ts', '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.mp3', '.wav', '.flac'}
            media_files = []
            
            # กวาดหาไฟล์ทุกซอกทุกมุมในโฟลเดอร์ (รวมถึงโฟลเดอร์ย่อย)
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in supported_exts:
                        media_files.append(os.path.join(root, file))
            
            if media_files:
                # 🌟 จัดเรียงตัวอักษรให้ถูกต้อง (EP.1, EP.2 จะได้เรียงสวยงาม)
                media_files.sort()
                for path in media_files:
                    self.add_to_playlist(path, play_now=False)
                
                # โชว์เตือน Dynamic Island ว่าดึงมาได้กี่ไฟล์
                self.wake_up_ui()
                self.is_showing_osd = True
                self.time_label.setText(f"📁 Added {len(media_files)} files")
                self.osd_display_timer.start(3000)
            else:
                QMessageBox.information(self, "No Media Found", "No supported media files found in this folder.")

    # ==========================================
    # 🍔 ระบบเมนู 3 จุด (Meatballs Menu) ของ Playlist
    # ==========================================
    def show_playlist_more_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #1C1C1E; color: white; border: 1px solid #333; padding: 5px; border-radius: 6px; }
            QMenu::item { padding: 8px 30px 8px 20px; border-radius: 4px; font-size: 13px; }
            QMenu::item:selected { background-color: #5E5CE6; font-weight: bold; }
            QMenu::separator { height: 1px; background-color: #333; margin: 4px 10px; }
        """)

        act_folder = QAction("📁 Add Folder (Ctrl+Shift+O)", self)
        act_folder.triggered.connect(self.enqueue_folder)
        menu.addAction(act_folder)

        act_url = QAction("🔗 Add URL", self)
        act_url.triggered.connect(self.enqueue_url)
        menu.addAction(act_url)

        menu.addSeparator() # เส้นคั่นหมวดหมู่

        act_save = QAction("💾 Save Playlist", self)
        act_save.triggered.connect(self.export_playlist)
        menu.addAction(act_save)

        act_load = QAction("📂 Load Playlist", self)
        act_load.triggered.connect(self.import_playlist)
        menu.addAction(act_load)

        menu.addSeparator() # เส้นคั่นหมวดหมู่ก่อนลบ

        act_clear = QAction("🗑️ Clear All", self)
        act_clear.triggered.connect(self.clear_playlist)
        menu.addAction(act_clear)

        # สั่งให้เมนูเด้งโผล่ขึ้นมาใต้ปุ่ม [ ⋮ ] พอดีเป๊ะ
        pos = self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height() + 2))
        menu.exec(pos)

    def add_to_playlist(self, path, play_now=False):
        is_url = path.startswith(("http", "rtsp", "rtmp"))
        norm_path = os.path.normpath(path) if not is_url else path
        
        existing_paths = [os.path.normpath(self.playlist_widget.item(i).data(Qt.UserRole)) if not self.playlist_widget.item(i).data(Qt.UserRole).startswith(("http", "rtsp", "rtmp")) else self.playlist_widget.item(i).data(Qt.UserRole) for i in range(self.playlist_widget.count())]
            
        if norm_path in existing_paths:
            self.wake_up_ui(); self.is_showing_osd = True; self.time_label.setText("⚠️ Item already in Playlist"); self.osd_display_timer.start(2500)
            if play_now:
                idx = existing_paths.index(norm_path); self.playlist_widget.setCurrentRow(idx)
                self.load_media(self.playlist_widget.item(idx).data(Qt.UserRole))
            return 

        if is_url:
            parts = path.split('/')
            filename = parts[-1] if parts[-1] else parts[-2]
            if not filename or '?' in filename: filename = f"Stream_{datetime.now().strftime('%H%M%S')}"
            file_size = 0; file_date = time.time(); file_type = "url"
            
            # 🌟 สำหรับ URL ให้โชว์แค่ชื่อลิงก์
            display_text = filename 
        else:
            filename = os.path.basename(path)
            try: 
                file_size = os.path.getsize(path) 
                file_date = os.path.getmtime(path)
                
                f_size_mb = file_size / (1024 * 1024) 
                duration = self.get_duration_str(path)
                info_str = f"[{duration}] " if duration else ""
                
                # 🌟 [เพิ่มตรงนี้] ใช้เครื่องมือหั่นชื่อไฟล์ ให้เหลือความยาวสูงสุด 30 ตัวอักษร
                short_name = self.truncate_filename(filename, 30)
                
                # 🌟 ใช้ชื่อที่หั่นแล้ว (short_name) มารวมร่างแทน
                display_text = f"{info_str}{short_name} ({f_size_mb:.1f} MB)"
                
            except: 
                file_size = 0; file_date = 0
                short_name = self.truncate_filename(filename, 40) # กันเหนียว
                display_text = short_name
                
            file_type = os.path.splitext(path)[1].lower()

        # 🌟 โค้ดส่วนที่เหลือเหมือนเดิมเป๊ะ
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, path); item.setData(Qt.UserRole + 1, filename.lower())
        item.setData(Qt.UserRole + 2, file_date); item.setData(Qt.UserRole + 3, file_size)
        item.setData(Qt.UserRole + 4, file_type); item.setData(Qt.UserRole + 5, self.playlist_widget.count()) 
        self.playlist_widget.addItem(item)
        
        if play_now or not self.current_playing_path:
            self.playlist_widget.setCurrentItem(item); self.load_media(path)

        item = QListWidgetItem(filename)
        item.setData(Qt.UserRole, path); item.setData(Qt.UserRole + 1, filename.lower())
        item.setData(Qt.UserRole + 2, file_date); item.setData(Qt.UserRole + 3, file_size)
        item.setData(Qt.UserRole + 4, file_type); item.setData(Qt.UserRole + 5, self.playlist_widget.count()) 
        self.playlist_widget.addItem(item)
        
        if play_now or not self.current_playing_path:
            self.playlist_widget.setCurrentItem(item); self.load_media(path)

    def sort_playlist(self):
        index = self.sort_combo.currentIndex()
        items = []
        while self.playlist_widget.count() > 0: items.append(self.playlist_widget.takeItem(0))
        
        # 🌟 ใส่ทิศทางตามที่บอสกดปุ่ม (Ascending / Descending)
        rev = not self.sort_ascending
        
        if index == 0:   items.sort(key=lambda x: x.data(Qt.UserRole + 5), reverse=rev) 
        elif index == 1: items.sort(key=lambda x: x.data(Qt.UserRole + 1), reverse=rev) 
        elif index == 2: items.sort(key=lambda x: x.data(Qt.UserRole + 2), reverse=rev) 
        elif index == 3: items.sort(key=lambda x: x.data(Qt.UserRole + 3), reverse=rev) 
        elif index == 4: items.sort(key=lambda x: x.data(Qt.UserRole + 4), reverse=rev) 
        
        for item in items: self.playlist_widget.addItem(item)
        self.highlight_playing_item()

    def remove_selected_items(self):
        playing_item_removed = False
        for item in self.playlist_widget.selectedItems():
            # เช็กว่าเรากำลังแกล้งลบไฟล์ที่กำลังเล่นอยู่หรือเปล่า?
            if item.data(Qt.UserRole) == self.current_playing_path:
                playing_item_removed = True
            self.playlist_widget.takeItem(self.playlist_widget.row(item))
            
        # 🌟 ถ้าไฟล์ที่เล่นอยู่โดนดึงออก ให้ตัดจบแล้วกลับหน้า Empty State ทันที
        if playing_item_removed:
            self.stop_video()
            self.current_playing_path = ""
            self.media_stack.setCurrentWidget(self.empty_state_frame)
            self.setWindowTitle("NexusPlayer - Ready")
            self.time_label.setText("00:00 / 00:00")

        # 🌟 ถ้าลบจนคิวเกลี้ยง ก็ให้ล้างระบบทั้งหมด
        if self.playlist_widget.count() == 0:
            self.clear_playlist()

    def clear_playlist(self):
        self.playlist_widget.clear()
        self.stop_video()
        self.current_playing_path = ""
        # 🌟 สั่งให้กลับไปโชว์หน้า Empty State และเปลี่ยนชื่อแอปกลับไปเป็นหน้าจอรอรับไฟล์
        self.media_stack.setCurrentWidget(self.empty_state_frame)
        self.setWindowTitle("NexusPlayer - Ready")
        self.time_label.setText("00:00 / 00:00")

    def highlight_playing_item(self):
        for i in range(self.playlist_widget.count()):
            if self.playlist_widget.item(i).data(Qt.UserRole) == self.current_playing_path:
                self.playlist_widget.setCurrentRow(i); break

    def get_current_playing_index(self):
        for i in range(self.playlist_widget.count()):
            if self.playlist_widget.item(i).data(Qt.UserRole) == self.current_playing_path: return i
        return -1

    def auto_play_next(self):
        count = self.playlist_widget.count()
        if count == 0: 
            self.media_stack.setCurrentWidget(self.empty_state_frame) # กันเหนียว
            return
        if self.loop_mode == 1: self.load_media(self.current_playing_path)
        elif self.loop_mode == 2: 
            next_idx = (self.get_current_playing_index() + 1) % count
            self.playlist_widget.setCurrentRow(next_idx); self.load_media(self.playlist_widget.item(next_idx).data(Qt.UserRole))
        else: 
            idx = self.get_current_playing_index()
            if idx < count - 1:
                self.playlist_widget.setCurrentRow(idx + 1); self.load_media(self.playlist_widget.item(idx + 1).data(Qt.UserRole))
            else: 
                # 🌟 เล่นจบหมดคิวแล้ว ให้เด้งกลับหน้า Empty State แบบหล่อๆ
                self.stop_video()
                self.media_stack.setCurrentWidget(self.empty_state_frame)
                self.setWindowTitle("NexusPlayer - Ready")

    def play_next(self):
        count = self.playlist_widget.count()
        if count == 0: return
        idx = self.get_current_playing_index()
        if idx < count - 1:
            self.playlist_widget.setCurrentRow(idx + 1); self.load_media(self.playlist_widget.item(idx + 1).data(Qt.UserRole))
        else:
            if self.loop_mode == 2: 
                self.playlist_widget.setCurrentRow(0); self.load_media(self.playlist_widget.item(0).data(Qt.UserRole))
            else: 
                # 🌟 กด Next จนทะลุคิวสุดท้าย ให้เด้งกลับหน้า Empty State
                self.stop_video()
                self.media_stack.setCurrentWidget(self.empty_state_frame)
                self.setWindowTitle("NexusPlayer - Ready")

    def play_previous(self):
        count = self.playlist_widget.count()
        if count == 0: return
        idx = self.get_current_playing_index()
        if idx > 0:
            self.playlist_widget.setCurrentRow(idx - 1); self.load_media(self.playlist_widget.item(idx - 1).data(Qt.UserRole))
        else:
            if self.current_media_type == "video" and self.media_player.get_media() is not None: self.media_player.set_position(0.0)

    def play_selected_from_list(self, item): self.load_media(item.data(Qt.UserRole))

    def toggle_playlist_ui(self):
        pl_width = 300
        pl_height = self.media_stack.height() 
        start_x = self.width() # จุดซ่อน (หลุดขอบจอขวามือ)
        end_x = self.width() - pl_width # จุดโชว์ (ชิดขอบขวาพอดี)
        y_pos = self.media_stack.y() 

        if self.playlist_container.isHidden():
            # 🎬 แอคชัน 1: สไลด์เข้ามาโชว์ (Slide In)
            self.playlist_container.setGeometry(start_x, y_pos, pl_width, pl_height)
            self.playlist_container.show()
            self.playlist_container.raise_() # 🌟 สั่งให้กระจกลอยขึ้นมาทับวิดีโอ!
            
            self.pl_anim = QPropertyAnimation(self.playlist_container, b"geometry")
            self.pl_anim.setDuration(350) # ความเร็ว 350ms นุ่มๆ
            self.pl_anim.setStartValue(QRect(start_x, y_pos, pl_width, pl_height))
            self.pl_anim.setEndValue(QRect(end_x, y_pos, pl_width, pl_height))
            self.pl_anim.setEasingCurve(QEasingCurve.OutCubic) # หน่วงตอนท้ายแบบรถหรูเบรก
            self.pl_anim.start()
            
            self.toggle_pl_btn.setStyleSheet(self.get_btn_style("#5E5CE6", "#7D7AFF"))
            self.is_playlist_open_before_hide = True
        else:
            # 🎬 แอคชัน 2: สไลด์เก็บกลับไป (Slide Out)
            self.pl_anim = QPropertyAnimation(self.playlist_container, b"geometry")
            self.pl_anim.setDuration(300)
            self.pl_anim.setStartValue(self.playlist_container.geometry())
            self.pl_anim.setEndValue(QRect(start_x, y_pos, pl_width, pl_height))
            self.pl_anim.setEasingCurve(QEasingCurve.InCubic) # เร่งความเร็วตอนรูดเก็บ
            self.pl_anim.finished.connect(self.playlist_container.hide) # รูดจบแล้วค่อยซ่อนตัว
            self.pl_anim.start()
            
            self.toggle_pl_btn.setStyleSheet(self.get_btn_style("#48484A", "#636366"))
            self.is_playlist_open_before_hide = False

    def show_zoom_osd(self, zoom_factor):
        self.wake_up_ui(); self.is_showing_osd = True
        self.time_label.setText("🔍 Zoom: Auto Fit" if zoom_factor == 1.0 else f"🔍 Zoom: {int(zoom_factor * 100)}%")
        self.osd_display_timer.start(1500)

    def load_media(self, path):
        if self.current_playing_path and self.current_media_type == "video": self.save_history()
        self.current_playing_path = path 
        self.highlight_playing_item()
        ext = path.lower().split('.')[-1]
        
        # 🌟 คัดแยกรูปภาพ (ที่เหลือส่งให้ VLC จัดการทั้งหมด ทั้งวิดีโอและไฟล์เสียง!)
        if ext in ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif', 'tiff', 'ico', 'svg']:
            self.current_media_type = "image"; self.show_image(path)
        else:
            self.current_media_type = "video"; self.play_video(path)

    def show_image(self, path):
        self.media_player.stop(); self.media_stack.setCurrentWidget(self.image_frame)
        self.image_frame.set_image(path) 
        filename = path.split('/')[-1] if "/" in path else path.split('\\')[-1]
        self.setWindowTitle(f"NexusPlayer - Viewing Image: {filename}")
        self.play_btn.setEnabled(False); self.play_btn.setStyleSheet(self.get_btn_style("#48484A", "#48484A"))
        self.timeline.setEnabled(False); self.time_label.setText("🖼️ Image Viewer"); self.wake_up_ui()

    def play_video(self, path):
        self.media_stack.setCurrentWidget(self.video_container)
        self.play_btn.setEnabled(True); self.timeline.setEnabled(True)
        self.has_resumed_current = False; self.video_container.reset_view() 
        self.media_player.set_media(self.vlc_instance.media_new(path))
        self.media_player.play(); self.playback_rate = 1.0 
        self.deactivate_cooldown(); self.speed_btn.setText("1.0x"); self.pending_skip_seconds = 0
        filename = path.split('/')[-1] if "/" in path else path.split('\\')[-1]
        self.setWindowTitle(f"NexusPlayer - Playing: {filename[:50]}...")
        self.play_btn.setText("⏸ Pause"); self.play_btn.setStyleSheet(self.get_btn_style("#5E5CE6", "#7D7AFF"))
        self.wake_up_ui()

    def toggle_resume_mode(self):
        self.is_resume_enabled = not self.is_resume_enabled
        if self.is_resume_enabled:
            self.resume_btn.setText("⏳ ON"); self.resume_btn.setStyleSheet(self.get_btn_style("#FF2D55", "#FF375F"))
        else:
            self.resume_btn.setText("⏳ OFF"); self.resume_btn.setStyleSheet(self.get_btn_style("#48484A", "#636366"))

    def save_history(self):
        if self.current_media_type != "video": return 
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f: json.dump(self.playback_history, f)
        except: pass

    def closeEvent(self, event):
        self.save_history(); event.accept()

    def update_ui(self):
        if self.current_media_type == "image": return 
        if self.media_player.get_state() == vlc.State.Ended:
            if not self._handling_end: self._handling_end = True; QTimer.singleShot(100, self.auto_play_next)
        else: self._handling_end = False

        # 🌟 แยกเงื่อนไข: ให้ทำงานเสมอถ้าวิดีโอเล่นอยู่ (ถอด not self.is_showing_osd ออกจากตรงนี้)
        if self.media_player.is_playing() and self.pending_skip_seconds == 0:
            current_time_ms = self.media_player.get_time(); total_time_ms = self.media_player.get_length()
            pos = self.media_player.get_position()
            
            # 1. 🟢 อัปเดตหลอด Timeline เสมอ! 
            # 🌟 [แก้ตรงนี้] เพิ่มเงื่อนไขว่าต้องไม่ได้กำลังรูดสไลเดอร์ (not self._is_seeking)
            if pos >= 0 and not getattr(self, '_is_seeking', False): 
                self.timeline.setValue(int(pos * 1000))

            if total_time_ms > 0:
                if not self.has_resumed_current:
                    self.has_resumed_current = True 
                    if self.is_resume_enabled and self.current_playing_path in self.playback_history:
                        saved_time = self.playback_history[self.current_playing_path]
                        if 0 < saved_time < (total_time_ms - 5000):
                            self.media_player.set_time(saved_time); self.wake_up_ui(); self.is_showing_osd = True
                            self.time_label.setText("⏳ Resumed Playback"); self.osd_display_timer.start(3000)
                            return 
                else: 
                    self.playback_history[self.current_playing_path] = current_time_ms

                # 2. 🟢 อัปเดตตัวเลขเวลา *เฉพาะตอนที่ Dynamic Island ว่างเท่านั้น!*
                if not self.is_showing_osd:
                    if self.time_display_mode == 0: text = f"{self.format_time(current_time_ms)} / {self.format_time(total_time_ms)}"
                    elif self.time_display_mode == 1: text = f"-{self.format_time(total_time_ms - current_time_ms)} / {self.format_time(total_time_ms)}"
                    else: text = f"{self.format_time(current_time_ms, True)}"
                    self.time_label.setText(text)
                    
    def load_initial_files(self, files):
        for file in files:
            if file.lower().split('.')[-1] in ['srt', 'ass', 'vtt', 'sub']:
                if self.media_player.get_media() is not None and self.current_media_type == "video": self.media_player.video_set_subtitle_file(os.path.normpath(file))
            else: self.add_to_playlist(file, play_now=False)
        if self.playlist_widget.count() > 0:
            self.load_media(self.playlist_widget.item(0).data(Qt.UserRole))
            if self.playlist_widget.count() > 1:
                self.playlist_container.show(); self.toggle_pl_btn.setStyleSheet(self.get_btn_style("#5E5CE6", "#7D7AFF"))

    def toggle_loop_mode(self):
        self.loop_mode = (self.loop_mode + 1) % 3
        if self.loop_mode == 0: self.loop_btn.setText("➡️ Next"); self.loop_btn.setStyleSheet(self.get_btn_style("#48484A", "#636366"))
        elif self.loop_mode == 1: self.loop_btn.setText("🔂 1"); self.loop_btn.setStyleSheet(self.get_btn_style("#32ADE6", "#41B6E6"))
        else: self.loop_btn.setText("🔁 All"); self.loop_btn.setStyleSheet(self.get_btn_style("#FF3B30", "#FF453A"))

    def take_snapshot(self):
        if self.current_media_type != "video" or self.media_player.get_media() is None: return
        pictures_dir = os.path.join(os.path.expanduser('~'), 'Pictures', 'NexusCaptures')
        if not os.path.exists(pictures_dir): os.makedirs(pictures_dir)
        filename = f"nexus_snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        result = self.media_player.video_take_snapshot(0, os.path.normpath(os.path.join(pictures_dir, filename)), 0, 0)
        self.wake_up_ui(); self.is_showing_osd = True
        self.time_label.setText(f"📸 Saved: {filename}" if result == 0 else "❌ Snapshot Failed")
        self.osd_display_timer.start(3000)

    def show_context_menu(self, global_pos):
        if not self.current_playing_path: return
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1C1C1E; color: white; border: 1px solid #333; padding: 5px; } QMenu::item { padding: 5px 30px 5px 20px; } QMenu::item:selected { background-color: #5E5CE6; border-radius: 3px; }")
        info_action = QAction("ℹ️ Media Info", self); info_action.triggered.connect(self.show_media_info); menu.addAction(info_action); menu.addSeparator()

        if self.current_media_type == "video" and self.media_player.get_media() is not None:
            audio_menu = menu.addMenu("🔊 Audio Track")
            audio_tracks = self.media_player.audio_get_track_description(); audio_group = QActionGroup(self)
            if audio_tracks:
                for tid, tname in audio_tracks:
                    try: name_str = tname.decode('utf-8')
                    except: name_str = str(tname)
                    action = QAction(name_str, self, checkable=True); action.setChecked(tid == self.media_player.audio_get_track()); action.setData(tid)
                    audio_group.addAction(action); audio_menu.addAction(action)
            else: no_audio = QAction("No Audio Tracks", self); no_audio.setEnabled(False); audio_menu.addAction(no_audio)
            audio_group.triggered.connect(lambda action: self.media_player.audio_set_track(action.data()))

            sub_menu = menu.addMenu("📝 Subtitle")
            sub_tracks = self.media_player.video_get_spu_description(); sub_group = QActionGroup(self)
            if sub_tracks:
                for tid, tname in sub_tracks:
                    try: name_str = tname.decode('utf-8')
                    except: name_str = str(tname)
                    action = QAction(name_str, self, checkable=True); action.setChecked(tid == self.media_player.video_get_spu()); action.setData(tid)
                    sub_group.addAction(action); sub_menu.addAction(action)
            else: no_sub = QAction("No Subtitles", self); no_sub.setEnabled(False); sub_menu.addAction(no_sub)
            sub_group.triggered.connect(lambda action: self.media_player.video_set_spu(action.data()))
        menu.exec(global_pos)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 🌟 เวลาย่อ/ขยายแอป แผงกระจกต้องยืดหดตามความสูงวิดีโอ และเกาะขอบขวาไว้ตลอด
        if hasattr(self, 'playlist_container') and not self.playlist_container.isHidden():
            pl_width = 300
            pl_height = self.media_stack.height()
            x_pos = self.width() - pl_width
            y_pos = self.media_stack.y()
            self.playlist_container.setGeometry(x_pos, y_pos, pl_width, pl_height)

        # 🌟 [เพิ่มตรงนี้] อัปเดตพิกัดแผงควบคุมลอยฟ้า
        if self.isFullScreen():
            self.update_floating_controls()

    def snap_to_aspect_ratio(self):
        if not self.is_mini_player or self.video_aspect_ratio <= 0: return
        cw, ch = self.width(), self.height(); dw, dh = abs(cw - self.last_snapped_w), abs(ch - self.last_snapped_h)
        if dw == 0 and dh == 0: return
        tw, th = cw, ch
        if dw > 0 and dh == 0: th = int(cw / self.video_aspect_ratio)
        elif dh > 0 and dw == 0: tw = int(ch * self.video_aspect_ratio)
        else:
            if (dw / self.last_snapped_w) > (dh / self.last_snapped_h): th = int(cw / self.video_aspect_ratio)
            else: tw = int(ch * self.video_aspect_ratio)
        self._is_snapping = True; self.resize(tw, th); self.last_snapped_w, self.last_snapped_h = tw, th; self._is_snapping = False

    def toggle_mini_player(self):
        if self.isFullScreen(): self.showNormal()
        self.is_mini_player = not self.is_mini_player
        if self.is_mini_player:
            self.saved_geometry = self.geometry(); self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.control_panel.hide(); self.playlist_container.hide()
            w, h = 480, 270 
            if self.current_media_type == "video" and self.media_player.get_media() is not None:
                size = self.media_player.video_get_size(0)
                if size and len(size) == 2 and size[0] > 0 and size[1] > 0:
                    self.video_aspect_ratio = size[0] / size[1]
                    if self.video_aspect_ratio >= 1: h = int(w / self.video_aspect_ratio)
                    else: h = 360; w = int(h * self.video_aspect_ratio)
            self.last_snapped_w, self.last_snapped_h = w, h
            self.setMinimumSize(240, int(240 / self.video_aspect_ratio)); self.setMaximumSize(16777215, 16777215)
            geom = QApplication.primaryScreen().availableGeometry()
            self._is_snapping = True; self.setGeometry(geom.width() - w - 20, geom.height() - h - 20, w, h); self._is_snapping = False; self.show()
        else:
            self.snap_timer.stop(); self.setWindowFlag(Qt.WindowStaysOnTopHint, False); self.setMinimumSize(0, 0)
            if not self.saved_geometry.isNull(): self.setGeometry(self.saved_geometry)
            self.control_panel.show(); self.show()

    def wake_up_ui(self):
        if self.is_mini_player: return
        self.cinema_timer.start() # เริ่มนับ 3 วิใหม่ทุกครั้งที่ขยับเมาส์
        self.setCursor(Qt.ArrowCursor) # โชว์ลูกศรเมาส์
        
        # 🌟 ถ้าแผงควบคุมมันซ่อนอยู่ ให้กระชากมันกลับขึ้นมา
        if self.control_panel.isHidden():
            self.control_panel.show()
            
            # ถ้าเป็น Fullscreen ต้องจับมันขึ้นมาอยู่บนสุดและจัดพิกัดใหม่เสมอ
            if self.isFullScreen():
                self.control_panel.raise_()
                self.update_floating_controls()
                
            # 🌟 คืนชีพ Playlist เฉพาะกรณีที่ก่อนหน้านี้บอสเปิดมันทิ้งไว้
            if getattr(self, 'is_playlist_open_before_hide', False):
                self.playlist_container.show()

    def hide_ui_for_cinema(self):
        # 🌟 1. ดักจับตำแหน่งเมาส์: เช็กว่าเมาส์ชี้แช่อยู่บน "แผงปุ่ม" หรือ "Playlist" ไหม?
        pos = self.mapFromGlobal(QCursor.pos())
        is_hovering_controls = self.control_panel.geometry().contains(pos) and not self.control_panel.isHidden()
        is_hovering_playlist = self.playlist_container.geometry().contains(pos) and not self.playlist_container.isHidden()
        
        # ถ้าเมาส์ชี้ปุ่มอยู่ = ห้ามซ่อน! ปล่อยไว้แบบนั้นแหละ
        if is_hovering_controls or is_hovering_playlist:
            return 
            
        # 🌟 2. ถ้าเมาส์วางนิ่งๆ กลางจอ และวิดีโอกำลังเล่น ให้ร่ายเวทมนตร์ซ่อน UI
        if self.current_media_type == "image" or self.media_player.is_playing():
            self.setCursor(Qt.BlankCursor) # ซ่อนเมาส์
            
            # จำสถานะ Playlist วินาทีสุดท้าย ก่อนจะจับมันซ่อน
            self.is_playlist_open_before_hide = not self.playlist_container.isHidden()
            
            self.control_panel.hide()
            self.playlist_container.hide()

    def toggle_fullscreen(self):
        if self.is_mini_player: self.toggle_mini_player(); return
        
        if self.isFullScreen(): 
            self.showNormal()
            self.setCursor(Qt.ArrowCursor)
            
            # 🌟 1. [กลับโหมดปกติ] ดันแผงควบคุมกลับเข้า Layout ปกติ
            self.control_panel.setParent(self.central_widget)
            self.layout.addWidget(self.control_panel)
            self.control_panel.setStyleSheet("background-color: #1A1A1D; border-top: 1px solid #222; border-radius: 0px;")
            self.control_panel.show()
        else:
            self.showFullScreen()
            
            # 🌟 2. [เข้า Fullscreen] ดึงแผงควบคุมออกมาลอยทับ (Overlay) เหมือน Playlist!
            self.control_panel.setParent(self.media_stack)
            # ปรับดีไซน์เป็น "แคปซูลลอย" โค้งมน โปร่งแสงนิดๆ
            self.control_panel.setStyleSheet("background-color: rgba(26, 26, 29, 210); border: 1px solid #3A3A3D; border-radius: 16px;")
            self.control_panel.raise_()
            self.control_panel.show()
            self.update_floating_controls() # จัดตำแหน่งใหม่ให้ลอยสวยๆ
            
            if self.current_media_type == "image" or self.media_player.is_playing(): 
                self.hide_ui_for_cinema()
        
    def update_floating_controls(self):
        """จัดตำแหน่งแผงควบคุมให้ลอยอยู่ตรงกลางขอบล่าง (เฉพาะโหมด Fullscreen)"""
        if self.isFullScreen() and hasattr(self, 'control_panel') and not self.control_panel.isHidden():
            # ทำให้แผงหดสั้นลง (กว้างสุด 950px) ไม่ยาวเทอะทะเต็มจอ
            panel_w = min(self.width() - 120, 950) 
            panel_h = self.control_panel.minimumSizeHint().height()
            
            # จัดให้อยู่ตรงกลาง และลอยขึ้นมาจากขอบล่าง 40px
            x_pos = (self.width() - panel_w) // 2
            y_pos = self.height() - panel_h - 40
            
            self.control_panel.setGeometry(x_pos, y_pos, panel_w, panel_h)

    def clear_osd(self): self.is_showing_osd = False

    def keyPressEvent(self, event: QKeyEvent):
        self.wake_up_ui()
        key, vk, text, modifiers = event.key(), event.nativeVirtualKey(), event.text(), event.modifiers()
        
        is_esc = (key == Qt.Key_Escape or vk == 27)
        is_f = (key == Qt.Key_F or vk == 70 or text in ['ด', 'โ'])
        is_f11 = (key == Qt.Key_F11) 
        is_alt_enter = (key == Qt.Key_Return or key == Qt.Key_Enter) and (modifiers & Qt.AltModifier) 
        is_space = (key == Qt.Key_Space or vk == 32 or text == ' ')
        is_k = (key == Qt.Key_K or text in ['า', 'ษ']) 
        is_m = (key == Qt.Key_M or text in ['ท', '?']) 
        is_j = (key == Qt.Key_J or text in ['่', '๋']) 
        is_l = (key == Qt.Key_L or text in ['ส', 'ศ']) 
        is_n = (key == Qt.Key_N or text in ['ื', '์']) 
        is_p = (key == Qt.Key_P or text in ['ย', 'ญ']) 
        is_o = (key == Qt.Key_O or vk == 79 or text in ['น', 'ฯ'])
        is_v = (key == Qt.Key_V or vk == 86 or text in ['อ', 'ฮ'])
        is_t = (key == Qt.Key_T or vk == 84 or text in ['ธ', 'ะ'])
        is_s = (key == Qt.Key_S or vk == 83 or text in ['ห', 'ฆ'])
        is_i = (key == Qt.Key_I or vk == 73 or text in ['ร', 'ณ']) 
        
        if key == Qt.Key_Right: self.add_skip(5); return
        elif key == Qt.Key_Left: self.add_skip(-5); return
        elif key == Qt.Key_Up: self.change_volume_via_keys(5); return
        elif key == Qt.Key_Down: self.change_volume_via_keys(-5); return

        if event.isAutoRepeat(): return

        if is_esc and self.isFullScreen(): self.toggle_fullscreen()
        elif is_f or is_f11 or is_alt_enter: self.toggle_fullscreen()
        elif (is_space or is_k) and self.current_media_type == "video": self.toggle_play()
        elif is_m: self.toggle_mute()
        elif is_j: self.add_skip(-10)
        elif is_l: self.add_skip(10)
        elif is_n: self.play_next()
        elif is_p: self.play_previous()
        elif is_s: self.take_snapshot() 
        elif is_i: self.show_media_info() 
        elif is_o and (modifiers & Qt.ControlModifier): self.open_file()
        elif is_v and (modifiers & Qt.ControlModifier): self.paste_content()
        elif key == Qt.Key_BracketRight or text in [']', 'ล']: self.change_speed(0.25)
        elif key == Qt.Key_BracketLeft or text in ['[', 'บ']: self.change_speed(-0.25)
        elif key == Qt.Key_Equal or text in ['=', 'ช']: self.reset_speed()
        elif is_t: self.toggle_mini_player()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls: return
        dropped_files = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if len(dropped_files) == 1:
            file_path = dropped_files[0]
            ext = file_path.lower().split('.')[-1]
            if ext in ['srt', 'ass', 'vtt', 'sub']:
                if self.current_media_type == "video" and self.media_player.get_media() is not None:
                    success = self.media_player.video_set_subtitle_file(os.path.normpath(file_path))
                    self.wake_up_ui(); self.is_showing_osd = True
                    if success:
                        self.time_label.setText(f"📝 Loaded: {os.path.normpath(file_path).split(os.sep)[-1]}")
                        self.media_player.set_position(0.0) 
                    else: self.time_label.setText("❌ Subtitle Blocked")
                    self.osd_display_timer.start(2500)
            else: self.add_to_playlist(file_path, play_now=True)
        else:
            for fp in dropped_files: self.add_to_playlist(fp)
            self.playlist_container.show()
            self.toggle_pl_btn.setStyleSheet(self.get_btn_style("#5E5CE6", "#7D7AFF"))

    def set_position(self, position):
        if self.current_media_type == "video" and self.media_player.get_media() is not None:
            self.media_player.set_position(position / 1000.0)

    def on_seek_start(self):
        self._is_seeking = True # บอกให้แอปรู้ว่า "บอสกำลังรูดสไลเดอร์อยู่นะ ห้ามกวน!"

    def on_seek_end(self):
        self._is_seeking = False # ปล่อยมือแล้ว อัปเดตวิดีโอต่อได้!
        self.set_position(self.timeline.value())

    def set_position(self, position):
        if self.current_media_type == "video" and self.media_player.get_media() is not None:
            self.media_player.set_position(position / 1000.0)
            
            # 🌟 อัปเดตตัวเลขเวลาให้วิ่งตามนิ้วเราทันทีตอนรูดแบบ Real-time
            total_time_ms = self.media_player.get_length()
            if total_time_ms > 0:
                current_time_ms = int((position / 1000.0) * total_time_ms)
                if self.time_display_mode == 0: text = f"{self.format_time(current_time_ms)} / {self.format_time(total_time_ms)}"
                elif self.time_display_mode == 1: text = f"-{self.format_time(total_time_ms - current_time_ms)} / {self.format_time(total_time_ms)}"
                else: text = f"{self.format_time(current_time_ms, True)}"
                self.time_label.setText(text)

    def toggle_time_mode(self):
        self.time_display_mode = (self.time_display_mode + 1) % 3
        self.timer.setInterval(40 if self.time_display_mode == 2 else 500)
        self.update_ui()

    def format_time(self, milliseconds, is_detailed=False):
        if milliseconds < 0: return "00:00"
        seconds = int(milliseconds / 1000); ms = int(milliseconds % 1000)
        minutes, seconds = divmod(seconds, 60); hours, minutes = divmod(minutes, 60)
        if is_detailed: return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}.{ms:03d}"
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"

    def sanitize_url(self, url_text):
        url_text = url_text.strip()
        if "youtube.com" in url_text or "youtu.be" in url_text:
            QMessageBox.warning(self, "Unsupported URL", "NexusPlayer requires a direct video link.\nYouTube page URLs are not supported directly.")
            return None
        if url_text.startswith(("http://", "https://", "rtsp://", "rtmp://")): return url_text
        if url_text.startswith("www.") or "." in url_text: return "http://" + url_text 
        return None

    def open_stream_dialog(self):
        url, ok = QInputDialog.getText(self, "Network Stream", "Enter Video URL:")
        if ok and url:
            clean_url = self.sanitize_url(url)
            if clean_url: self.add_to_playlist(clean_url, play_now=True)

    def paste_content(self):
        clipboard = QApplication.clipboard()
        if clipboard.mimeData().hasUrls():
            urls = clipboard.mimeData().urls()
            if urls and urls[0].isLocalFile(): self.add_to_playlist(urls[0].toLocalFile(), play_now=True)
        elif clipboard.mimeData().hasText():
            clean_url = self.sanitize_url(clipboard.mimeData().text())
            if clean_url: self.add_to_playlist(clean_url, play_now=True)

    def open_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Media", "", 
            "All Supported Media (*.mp4 *.mkv *.avi *.ts *.mov *.flv *.wmv *.webm *.m4v *.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma *.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff);;Video Files (*.mp4 *.mkv *.avi *.ts *.mov *.flv *.wmv *.webm *.m4v);;Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;Image Files (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff);;All Files (*.*)"
        )
        if file_paths: 
            for path in file_paths: self.add_to_playlist(path)
            self.load_media(file_paths[0])
            if len(file_paths) > 1: self.playlist_container.show(); self.toggle_pl_btn.setStyleSheet(self.get_btn_style("#5E5CE6", "#7D7AFF"))

    def load_url_history(self):
        """โหลดประวัติ URL จากไฟล์"""
        self.url_history = []
        try:
            if os.path.exists(self.url_history_file):
                with open(self.url_history_file, 'r', encoding='utf-8') as f:
                    self.url_history = json.load(f)
        except Exception: pass

    def save_url_history(self):
        """เซฟประวัติ URL ลงไฟล์"""
        try:
            with open(self.url_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.url_history, f)
        except Exception: pass

    def open_url_dialog(self):
        """เปิดหน้าต่าง URL ขึ้นมา"""
        dialog = URLHistoryDialog(self.url_history, self)
        if dialog.exec() == QDialog.Accepted:
            url = dialog.get_url()
            new_history = dialog.get_history() # ดึงประวัติที่บอสอาจจะกดลบไปแล้วมา
            
            if url:
                # ถ้ามีลิงก์ใหม่ ให้ดันขึ้นไปบนสุด
                if url in new_history: new_history.remove(url)
                new_history.insert(0, url)
                
                # โยนเข้าคิวแล้วสั่งเล่น
                self.add_to_playlist(url)
                self.load_media(url)
                if self.playlist_container.isHidden():
                    self.toggle_playlist_ui()
                    
            # เซฟประวัติล่าสุดกลับลงไฟล์ (จำกัดไว้แค่ 30 ลิงก์ล่าสุด จะได้ไม่หนักแอป)
            self.url_history = new_history[:30]
            self.save_url_history()

    def toggle_play(self):
        if self.current_media_type == "image": return
        if self.media_player.get_media() is None: self.open_file(); return
        if self.media_player.is_playing(): self.media_player.pause(); self.play_btn.setText("▶ Play"); self.wake_up_ui()
        else: self.media_player.play(); self.play_btn.setText("⏸ Pause")

    def stop_video(self):
        if self.current_media_type == "video":
            self.save_history(); self.media_player.stop()
            self.play_btn.setText("▶ Play"); self.timeline.setValue(0)
        self.wake_up_ui()

    def toggle_sort_direction(self):
        """สลับทิศทางการเรียงลำดับ"""
        self.sort_ascending = not self.sort_ascending
        self.btn_sort_direction.setText("🔼" if self.sort_ascending else "🔽")
        self.sort_playlist()

    def get_duration_str(self, path):
        """ดึงความยาววิดีโอ/เสียง แบบด่วนโดยไม่ต้องเล่น"""
        try:
            m = self.vlc_instance.media_new(path)
            m.parse() # สั่ง parse เพื่อดึง Metadata
            duration_ms = m.get_duration()
            if duration_ms <= 0: return ""
            return self.format_time(duration_ms)
        except: return ""

    def truncate_filename(self, filename, max_chars=30):
        """ระบบหั่นชื่อไฟล์อัจฉริยะ โชว์หัว-ท้าย ป้องกันชื่อยาวทะลุขอบ"""
        if len(filename) <= max_chars:
            return filename
        # เก็บหัวไว้ 15 ตัวอักษร เก็บหาง (รวมนามสกุล) ไว้ 12 ตัวอักษร ตรงกลางใส่ ...
        return filename[:15] + "..." + filename[-12:]

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NexusPlayer(sys.argv[1:] if len(sys.argv) > 1 else [])
    window.show()
    sys.exit(app.exec())