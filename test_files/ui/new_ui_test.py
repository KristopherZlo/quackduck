import sys
import os
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QRect, QEasingCurve, QTimer, Property,
    Signal, QPointF, QEvent
)
from PySide6.QtGui import (
    QPainter, QColor, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QScrollArea, QFrame, QLineEdit, QComboBox,
    QSpinBox, QPushButton, QProgressBar, QSlider, QSizePolicy
)

###############################################################################
# Загрузка иконок из локальной папки icons/
###############################################################################
def load_icon_svg(name: str, color: str = "#fff", size: int = 24) -> QPixmap:
    """
    Ищет файл иконки в папке 'icons' по имени, например 'feather.svg'.
    Меняет в ней 'stroke="currentColor"' на нужный цвет, 
    и возвращает QPixmap заданного размера.
    """
    # Путь до файла:
    icon_path = os.path.join("icons", f"{name}.svg")
    if not os.path.isfile(icon_path):
        # Если иконки нет, вернём пустой
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        return pix

    # Считываем исходный SVG:
    with open(icon_path, "r", encoding="utf-8") as f:
        raw_svg = f.read()

    # Меняем currentColor на нужный
    svg_data = raw_svg.replace("currentColor", color)

    # Через временный QSvgWidget отрисовываем в QPixmap
    from PySide6.QtSvgWidgets import QSvgWidget
    widget = QSvgWidget()
    widget.load(bytearray(svg_data, 'utf-8'))
    widget.setMinimumSize(size, size)

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    widget.render(pix)
    return pix

###############################################################################
# Hover-подсветка с плавным переходом бордюра + «свечение» курсора
###############################################################################
class HoverGlowFrame(QFrame):
    """
    - При наведении мыши (enterEvent) анимируем цвет бордюра (borderColor) за 0.3c
    - Одновременно рисуем белое «свечение» в paintEvent (radial gradient), 
      которое следует за курсором с плавной интерполяцией.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Начальное состояние бордюра (#363636), при ховере (#ffffff)
        self._normalColor = QColor("#363636")
        self._hoverColor  = QColor("#ffffff")
        self._borderColor = self._normalColor

        self._anim = QPropertyAnimation(self, b"borderColor")
        self._anim.setDuration(300)  # 0.3s
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        # Свечение
        self._targetPos = QPointF(0, 0)
        self._currentPos = QPointF(0, 0)
        self.setMouseTracking(True)

        self._glowTimer = QTimer(self)
        self._glowTimer.setInterval(16)  # ~60 FPS
        self._glowTimer.timeout.connect(self._animateGlow)

        # Включим «обгон» событий мыши
        self.setAttribute(Qt.WA_Hover, True)

    # -------------------- СВОЙСТВО borderColor (анимируемое) -----------------
    @Property(QColor)
    def borderColor(self):
        return self._borderColor

    @borderColor.setter
    def borderColor(self, c: QColor):
        self._borderColor = c
        self.update()

    # -------------------- Hover Events --------------------
    def enterEvent(self, event):
        super().enterEvent(event)
        # Запускаем анимацию к hoverColor
        self._anim.stop()
        self._anim.setStartValue(self.borderColor)
        self._anim.setEndValue(self._hoverColor)
        self._anim.start()

        self._glowTimer.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        # Запускаем анимацию к normalColor
        self._anim.stop()
        self._anim.setStartValue(self.borderColor)
        self._anim.setEndValue(self._normalColor)
        self._anim.start()

        self._glowTimer.stop()
        self.update()  # пересобрать paintEvent, убрав свечение

    def mouseMoveEvent(self, e):
        # Обновляем целевые координаты
        self._targetPos = e.position()
        self._glowTimer.start()
        self.update()
        super().mouseMoveEvent(e)

    # -------------------- Анимация следования «огонька» за курсором --------------------
    def _animateGlow(self):
        # Плавно приближаем _currentPos к _targetPos
        dx = self._targetPos.x() - self._currentPos.x()
        dy = self._targetPos.y() - self._currentPos.y()
        alpha = 0.2  # коэффициент сглаживания
        self._currentPos.setX(self._currentPos.x() + alpha * dx)
        self._currentPos.setY(self._currentPos.y() + alpha * dy)
        self.update()

    # -------------------- Рисуем бордюр и свечение --------------------
    def paintEvent(self, e):
        super().paintEvent(e)

        # 1) Рисуем бордюр (потому что стандартными стилями Qt transition не сделать):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        radius = 8  # скругление
        penW = 1
        pen = QColor(self._borderColor)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(penW // 2, penW // 2, -penW, -penW), radius, radius)

        # 2) Рисуем свечение, если мышь внутри
        if self.underMouse():
            # Белый полупрозрачный круг
            radius_glow = 150
            gradient_color = QColor(255, 255, 255, 30)  # посильнее, чем 20
            cx, cy = self._currentPos.x(), self._currentPos.y()

            p.setPen(Qt.NoPen)
            glow_rect = QRect(int(cx - radius_glow),
                              int(cy - radius_glow),
                              radius_glow * 2,
                              radius_glow * 2)
            p.setBrush(gradient_color)
            p.drawEllipse(glow_rect)

        p.end()

###############################################################################
# Переключатель (аналог чекбокса) с плавным переходом цвета за 0.3s
###############################################################################
class ToggleSwitch(QWidget):
    clicked = Signal(bool)

    def __init__(self, initial=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self._checked = initial

        # Для плавной анимации цвета зададим Property backgroundColor
        self._bgColor = QColor("#0078d4") if self._checked else QColor("#484848")
        self._anim = QPropertyAnimation(self, b"backgroundColor")
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        # Положение «бегунка»
        self._handleX = 20 if initial else 0

    # -------------------- фоновый цвет (Property) --------------------
    @Property(QColor)
    def backgroundColor(self):
        return self._bgColor

    @backgroundColor.setter
    def backgroundColor(self, c):
        self._bgColor = c
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        # закрашиваем фон прямоугольника:
        r = rect.height() // 2
        p.setPen(Qt.NoPen)
        p.setBrush(self._bgColor)
        p.drawRoundedRect(rect, r, r)

        # «кружок»-бегунок
        circle = QRect(int(3 + self._handleX), 3, 18, 18)
        p.setBrush(QColor("#fff"))
        p.drawEllipse(circle)
        p.end()

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self.setChecked(not self._checked)

    def setChecked(self, val: bool):
        if self._checked == val:
            return
        self._checked = val
        # Запускаем анимацию цвета
        self._anim.stop()
        start_color = self._bgColor
        end_color = QColor("#0078d4") if val else QColor("#484848")
        self._anim.setStartValue(start_color)
        self._anim.setEndValue(end_color)
        self._anim.start()

        # Анимация «бегунка»
        start_x = self._handleX
        end_x   = 20 if val else 0
        run = QPropertyAnimation(self, b"handleX")
        run.setDuration(300)
        run.setEasingCurve(QEasingCurve.InOutCubic)
        run.setStartValue(start_x)
        run.setEndValue(end_x)
        run.valueChanged.connect(self._on_handle_changed)
        run.start(QPropertyAnimation.DeleteWhenStopped)

        self.clicked.emit(val)

    def isChecked(self):
        return self._checked

    # -------------------- свойство handleX (положение бегунка) --------------------
    @Property(float)
    def handleX(self):
        return self._handleX

    @handleX.setter
    def handleX(self, v):
        self._handleX = v
        self.update()

    def _on_handle_changed(self, val):
        self._handleX = val
        self.update()

###############################################################################
# Анимированный синий «селектор» в меню
###############################################################################
class MenuSelector(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:#0078d4; border-radius:2px;")
        self.setGeometry(0, 0, 4, 12)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def moveTo(self, start_rect: QRect, end_rect: QRect, container_top: int):
        start_y = start_rect.top() - container_top + (start_rect.height() - 12) // 2
        end_y = end_rect.top() - container_top + (end_rect.height() - 12) // 2

        bigger = QRect(self.x(), min(start_y, end_y), 4, abs(end_y - start_y) + 12)
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(bigger)
        self._anim.start()

        def step2():
            self._anim.stop()
            final_rect = QRect(self.x(), end_y, 4, 12)
            self._anim.setStartValue(bigger)
            self._anim.setEndValue(final_rect)
            self._anim.start()

        QTimer.singleShot(200, step2)

###############################################################################
# Стрелочка (▼/▲), которая раскрывает блок
###############################################################################
class ExpandArrow(QLabel):
    clicked = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = False
        self.setFixedSize(20, 20)
        self.setStyleSheet("background:transparent; color:#888; font-size:18px;")
        self._update_arrow()

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self.active = not self.active
        self._update_arrow()
        self.clicked.emit(self.active)

    def _update_arrow(self):
        self.setText("▲" if self.active else "▼")

###############################################################################
# Карточка настройки (иконка + заголовок + описание), с HoverGlowFrame
###############################################################################
class SettingCard(HoverGlowFrame):
    """
    Справа (self.right_box) можно добавлять виджеты: 
    ToggleSwitch, кнопки, и т.п.
    """
    def __init__(self, icon_name, title, desc, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingCard")
        # Отключаем свой бордюр HoverGlowFrame, т.к. он уже будет рисоваться анимацией
        # при paintEvent. Но у нас QPainter рисует, 
        # поэтому оставим setStyleSheet с прозрачным border, 
        # а анимацией управлятся в HoverGlowFrame.
        self.setStyleSheet("""
            #SettingCard {
                background:#2d2d2d;
                border-radius:8px;
            }
        """)

        # Внутренний лейаут
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Левая часть (иконка + текст)
        left_box = QHBoxLayout()
        left_box.setSpacing(10)

        icon_lbl = QLabel()
        # Грузим локальную иконку:
        icon_lbl.setPixmap(load_icon_svg(icon_name, "#fff", 20))
        icon_lbl.setFixedSize(24, 24)
        icon_lbl.setAlignment(Qt.AlignCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(4)
        lab_title = QLabel(title)
        lab_title.setStyleSheet("font-size:15px;")
        lab_desc = QLabel(desc)
        lab_desc.setStyleSheet("font-size:13px; color:#888;")
        lab_desc.setWordWrap(True)
        text_box.addWidget(lab_title)
        text_box.addWidget(lab_desc)

        left_box.addWidget(icon_lbl, 0, Qt.AlignVCenter)
        left_box.addLayout(text_box, 1)

        main_layout.addLayout(left_box, 2)

        # Правая часть
        self.right_box = QHBoxLayout()
        self.right_box.setContentsMargins(0,0,0,0)
        self.right_box.setSpacing(10)
        self.right_box.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        main_layout.addLayout(self.right_box, 1)

    def addRightWidget(self, w):
        self.right_box.addWidget(w)

###############################################################################
# Маленький квадратик в «большом предпросмотре»
###############################################################################
class PreviewTile(HoverGlowFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 100)
        self.setStyleSheet("""
            QFrame {
                background:#363636;
                border-radius:4px;
            }
        """)

###############################################################################
# Большой блок предпросмотра (2 строки по 5 квадратиков)
###############################################################################
class LargeSkinPreview(HoverGlowFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background:#2d2d2d; border-radius:8px; }")
        vLay = QVBoxLayout(self)
        vLay.setContentsMargins(10,10,10,10)
        vLay.setSpacing(10)

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        for i in range(5):
            row1.addWidget(PreviewTile())
        for i in range(5):
            row2.addWidget(PreviewTile())

        vLay.addLayout(row1)
        vLay.addLayout(row2)

###############################################################################
# Карточка скина для Skin store
###############################################################################
class StoreCard(HoverGlowFrame):
    def __init__(self, border_color, title, desc, tags, price, parent=None):
        super().__init__(parent)
        self._normalBorder = QColor(border_color)
        self._hoverBorder  = QColor(border_color)  # можете менять по желанию
        self._borderColor = self._normalBorder

        # Переопределим _normalColor / _hoverColor, если хотим (иначе возьмём стандарт)
        self._anim.setStartValue(self._borderColor)
        self._anim.setEndValue(self._borderColor)

        self.setObjectName("StoreCard")
        self.setStyleSheet("QFrame { background:#363636; border-radius:8px; }")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(20)

        # Превью (пока просто фон)
        preview = QLabel("No image")
        preview.setFixedSize(100, 100)
        preview.setStyleSheet("background:#252525; border-radius:4px;")
        preview.setAlignment(Qt.AlignCenter)

        right_vb = QVBoxLayout()
        right_vb.setSpacing(8)
        lb_title = QLabel(title)
        lb_title.setStyleSheet("font-size:16px;")
        lb_desc = QLabel(desc)
        lb_desc.setStyleSheet("font-size:14px; color:#ccc;")
        lb_desc.setWordWrap(True)

        lb_tags = QLabel(tags)
        lb_tags.setStyleSheet("font-size:13px; color:#0078d4;")
        lb_tags.setWordWrap(True)

        # Нижняя часть: цена слева, кнопка справа
        row_btm = QHBoxLayout()
        row_btm.setSpacing(10)
        lb_price = QLabel(price)
        lb_price.setStyleSheet("font-size:18px;")
        btn_buy = QPushButton("Purchase")

        row_btm.addWidget(lb_price, 0, Qt.AlignLeft)
        row_btm.addStretch()
        row_btm.addWidget(btn_buy, 0, Qt.AlignRight)

        right_vb.addWidget(lb_title)
        right_vb.addWidget(lb_desc)
        right_vb.addWidget(lb_tags)
        right_vb.addStretch(1)
        right_vb.addLayout(row_btm)

        lay.addWidget(preview, 0, Qt.AlignTop)
        lay.addLayout(right_vb, 1)

    # Переопределим paintEvent, чтобы нарисовать бордюр нужным цветом
    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        pen = self._borderColor
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect.adjusted(0,0,-1,-1), 8, 8)
        p.end()

###############################################################################
# Основное окно
###############################################################################
class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quack Duck Settings")
        self.resize(1100, 700)

        # Глобальный стиль
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background:#252525;
                color:#fff;
                font-family: system-ui, -apple-system, sans-serif;
            }
            QLineEdit, QSpinBox, QComboBox {
                background:#363636;
                border-radius:4px;
                border:1px solid #494949;
                color:#ccc;
                padding:6px 8px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border:1px solid #0078d4;
                outline: none;
            }
            /* Стили выпадающего списка */
            QComboBox::drop-down {
                width:30px;
                border:none;
                background:transparent;
            }
            QComboBox::down-arrow {
                image: url("icons/arrow-down.svg");
                width:20px;
                height:20px;
            }

            /* Стили кнопок */
            QPushButton {
                background:#0078d4;
                border:none;
                border-radius:4px;
                color:#fff;
                font-size:14px;
                padding:6px 12px;
            }
            QPushButton:hover {
                background:#1890f0;
            }
            QPushButton:pressed {
                background:#0c70aa;
            }

            /* Скроллбар */
            QScrollArea {
                background:#252525;
                border:none;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background:transparent;
                margin:0;
                border:none;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background:#666;
                border-radius:3px;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                height:0; width:0;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QHBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # Левая колонка (sidebar)
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(250)
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(20, 20, 20, 20)
        side_lay.setSpacing(20)

        # Логотип
        row_logo = QHBoxLayout()
        row_logo.setSpacing(10)
        logo_bg = QLabel()
        logo_bg.setFixedSize(40, 40)
        logo_bg.setStyleSheet("background:#0078d4; border-radius:8px;")
        logo_txt = QLabel("Quack Duck")
        logo_txt.setStyleSheet("font-size:16px;")
        row_logo.addWidget(logo_bg, 0)
        row_logo.addWidget(logo_txt, 0)
        side_lay.addLayout(row_logo)

        # Селектор
        self.selector = MenuSelector()
        self.selector.setParent(self.sidebar)
        self.selector.hide()

        self.menu_items = []
        self.active_item = None

        # Кнопки меню
        self.btn_appearance = self.create_menu_button("feather", "Appearance", "#0078d4")
        self.btn_general    = self.create_menu_button("globe",   "General",    "#00b294")
        self.btn_audio      = self.create_menu_button("volume-2","Audio",      "#ff8c00")
        self.btn_store      = self.create_menu_button("shopping-cart","Skin store","#e81123")
        self.btn_about      = self.create_menu_button("info",    "About",      "#68217a")

        for b in [self.btn_appearance, self.btn_general, self.btn_audio, self.btn_store, self.btn_about]:
            side_lay.addWidget(b, 0)

        side_lay.addStretch(1)

        vers_label = QLabel("Version 1.5.3")
        vers_label.setStyleSheet("color:#888; font-size:12px;")
        side_lay.addWidget(vers_label)

        main_lay.addWidget(self.sidebar, 0)

        # Правая область - QStackedWidget
        self.stack = QStackedWidget()
        main_lay.addWidget(self.stack, 1)

        # Страницы
        self.page_appearance = self.make_page_appearance()
        self.page_general    = self.make_page_general()
        self.page_audio      = self.make_page_audio()
        self.page_store      = self.make_page_store()
        self.page_about      = self.make_page_about()

        self.stack.addWidget(self.page_appearance)
        self.stack.addWidget(self.page_general)
        self.stack.addWidget(self.page_audio)
        self.stack.addWidget(self.page_store)
        self.stack.addWidget(self.page_about)

        # Стартуем с Appearance
        self.set_active_item(self.btn_appearance)

    def create_menu_button(self, icon_name, text, color):
        w = QWidget()
        w.setProperty("menu-color", color)
        w.setFixedHeight(50)
        w.setStyleSheet("background:transparent;")
        w.setCursor(Qt.PointingHandCursor)

        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(load_icon_svg(icon_name, "#fff", 24))
        icon_lbl.setFixedSize(24, 24)
        icon_lbl.setAlignment(Qt.AlignCenter)

        txt_lbl = QLabel(text)
        txt_lbl.setStyleSheet("font-size:15px;")

        lay.addWidget(icon_lbl, 0, Qt.AlignVCenter)
        lay.addWidget(txt_lbl, 0, Qt.AlignVCenter)
        lay.addStretch(1)

        def handle_click(evt):
            self.on_menu_clicked(w)
        w.mousePressEvent = handle_click

        self.menu_items.append(w)
        return w

    def on_menu_clicked(self, w):
        self.set_active_item(w)

    def set_active_item(self, w):
        if self.active_item == w:
            return
        old_item = self.active_item
        self.active_item = w

        # Подсветка активной кнопки
        for item in self.menu_items:
            if item == w:
                item.setStyleSheet("background:#363636; border-radius:6px;")
            else:
                item.setStyleSheet("background:transparent;")

        # Показываем селектор
        if not self.selector.isVisible():
            self.selector.show()

        # Анимируем
        sidebar_top = self.sidebar.mapToGlobal(self.sidebar.rect().topLeft()).y()
        if old_item:
            old_rect = old_item.geometry()
            new_rect = w.geometry()
            old_top_global = old_item.mapToGlobal(old_rect.topLeft())
            new_top_global = w.mapToGlobal(new_rect.topLeft())

            sr = QRect(old_top_global.x(), old_top_global.y() - sidebar_top,
                       old_rect.width(), old_rect.height())
            nr = QRect(new_top_global.x(), new_top_global.y() - sidebar_top,
                       new_rect.width(), new_rect.height())
            self.selector.moveTo(sr, nr, 0)
        else:
            r = w.geometry()
            top_global = w.mapToGlobal(r.topLeft())
            y_local = top_global.y() - sidebar_top
            self.selector.setGeometry(10, y_local + (r.height() - 12)//2, 4, 12)

        idx = self.menu_items.index(w)
        self.stack.setCurrentIndex(idx)

    ###########################################################################
    # Appearance
    ###########################################################################
    def make_page_appearance(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20,20,20,20)
        lay.setSpacing(20)

        title = QLabel("Appearance")
        title.setStyleSheet("font-size:26px;")
        lay.addWidget(title)

        # Карточка "Pet name" + раскрывающийся блок
        c_name = SettingCard("feather", "Pet name", "Affects the pet's characteristics and behavior")
        arrow = ExpandArrow()
        self.expanded_block = QFrame()
        self.expanded_block.setStyleSheet("background:#2d2d2d; border-radius:8px;")
        self.expanded_block.setVisible(False)
        self.expanded_block.setMaximumHeight(0)

        def on_arrow_click(state: bool):
            if state:
                self.expanded_block.setVisible(True)
                anim = QPropertyAnimation(self.expanded_block, b"maximumHeight")
                anim.setDuration(300)
                anim.setStartValue(0)
                anim.setEndValue(100)
                anim.start()
            else:
                anim = QPropertyAnimation(self.expanded_block, b"maximumHeight")
                anim.setDuration(300)
                anim.setStartValue(self.expanded_block.maximumHeight())
                anim.setEndValue(0)
                def hide_after():
                    self.expanded_block.setVisible(False)
                anim.finished.connect(hide_after)
                anim.start()

        arrow.clicked.connect(on_arrow_click)

        rowN = QHBoxLayout()
        rowN.addStretch(1)
        ed_name = QLineEdit()
        ed_name.setPlaceholderText("Enter pet name...")
        rowN.addWidget(ed_name)
        rowN.addWidget(arrow)
        c_name.right_box.addLayout(rowN)
        lay.addWidget(c_name)

        # контент внутри раскрывающегося
        v_in = QVBoxLayout(self.expanded_block)
        v_in.setContentsMargins(10,10,10,10)
        lb_speed = QLabel("Speed: 2.2 units\nTimeout: 2 mins.")
        lb_speed.setStyleSheet("color:#ccc;")
        v_in.addWidget(lb_speed)
        lay.addWidget(self.expanded_block)

        # Show name
        c_show = SettingCard("eye", "Show name", "Enable or disable the display of the name above the pet's head")
        row_sh = QHBoxLayout()
        row_sh.addStretch(1)
        lb_sh = QLabel("on")
        tg_sh = ToggleSwitch(True)
        def on_tg_sh(b):
            lb_sh.setText("on" if b else "off")
        tg_sh.clicked.connect(on_tg_sh)
        row_sh.addWidget(lb_sh)
        row_sh.addWidget(tg_sh)
        c_show.right_box.addLayout(row_sh)
        lay.addWidget(c_show)

        # Pet size
        c_size = SettingCard("maximize-2", "Pet size", "The size of the pet on the screen")
        row_sz = QHBoxLayout()
        row_sz.addStretch(1)
        cb_size = QComboBox()
        cb_size.addItems(["Small", "Medium", "Big"])
        row_sz.addWidget(cb_size)
        c_size.right_box.addLayout(row_sz)
        lay.addWidget(c_size)

        # Folder
        c_folder = SettingCard("folder", "Skins folder path...", "Specify the folder containing additional skins")
        row_fd = QHBoxLayout()
        row_fd.addStretch(1)
        ed_folder = QLineEdit()
        ed_folder.setPlaceholderText("path/to/skins...")
        ed_folder.setReadOnly(True)
        btn_sel = QPushButton("Select")
        row_fd.addWidget(ed_folder)
        row_fd.addWidget(btn_sel)
        c_folder.right_box.addLayout(row_fd)
        lay.addWidget(c_folder)

        # Большой блок предпросмотра
        preview = LargeSkinPreview()
        lay.addWidget(preview)

        lay.addStretch(1)
        return w

    ###########################################################################
    # General
    ###########################################################################
    def make_page_general(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20,20,20,20)
        lay.setSpacing(20)

        lb = QLabel("General")
        lb.setStyleSheet("font-size:26px;")
        lay.addWidget(lb)

        # Language
        c_lang = SettingCard("globe", "Language", "The application's interface language")
        row_lg = QHBoxLayout()
        row_lg.addStretch(1)
        cb_lang = QComboBox()
        cb_lang.addItems(["Russian", "English"])
        row_lg.addWidget(cb_lang)
        c_lang.right_box.addLayout(row_lg)
        lay.addWidget(c_lang)

        # Floor
        c_floor = SettingCard("feather", "Floor level", "The minimum level (in pixels)")
        row_fl = QHBoxLayout()
        row_fl.addStretch(1)
        sp_floor = QSpinBox()
        row_fl.addWidget(sp_floor)
        c_floor.right_box.addLayout(row_fl)
        lay.addWidget(c_floor)

        # Name offset
        c_off = SettingCard("feather", "Name offset", "Vertical offset for the pet's name")
        row_of = QHBoxLayout()
        row_of.addStretch(1)
        sp_off = QSpinBox()
        row_of.addWidget(sp_off)
        c_off.right_box.addLayout(row_of)
        lay.addWidget(c_off)

        # Font size
        c_fs = SettingCard("feather", "Font size", "Base font size for the pet's name")
        row_fs = QHBoxLayout()
        row_fs.addStretch(1)
        sp_fs = QSpinBox()
        sp_fs.setValue(16)
        row_fs.addWidget(sp_fs)
        c_fs.right_box.addLayout(row_fs)
        lay.addWidget(c_fs)

        # Autostart
        c_auto = SettingCard("feather", "Autostart", "Launch with your system")
        row_at = QHBoxLayout()
        row_at.addStretch(1)
        lb_aut = QLabel("off")
        tg_aut = ToggleSwitch(False)
        def on_tg_aut(b):
            lb_aut.setText("on" if b else "off")
        tg_aut.clicked.connect(on_tg_aut)
        row_at.addWidget(lb_aut)
        row_at.addWidget(tg_aut)
        c_auto.right_box.addLayout(row_at)
        lay.addWidget(c_auto)

        # Reset
        c_rst = SettingCard("feather", "Reset All Settings", "Reset all to defaults")
        row_rs = QHBoxLayout()
        row_rs.addStretch(1)
        btn_rst = QPushButton("Reset")
        btn_rst.setStyleSheet("background:#e81123; padding:6px 30px;")
        row_rs.addWidget(btn_rst)
        c_rst.right_box.addLayout(row_rs)
        lay.addWidget(c_rst)

        lay.addStretch(1)
        return w

    ###########################################################################
    # Audio
    ###########################################################################
    def make_page_audio(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20,20,20,20)
        lay.setSpacing(20)

        lb = QLabel("Audio")
        lb.setStyleSheet("font-size:26px;")
        lay.addWidget(lb)

        # Input device
        c_in = SettingCard("mic", "Input device", "Select your microphone")
        row_in = QHBoxLayout()
        row_in.addStretch(1)
        cb_in = QComboBox()
        cb_in.addItem("Default microphone")
        row_in.addWidget(cb_in)
        c_in.right_box.addLayout(row_in)
        lay.addWidget(c_in)

        # Activation threshold
        c_thr = SettingCard("volume-2", "Activation threshold", "Volume threshold for 'listening' animation")
        row_thr = QHBoxLayout()
        row_thr.addStretch(1)

        lb_thr = QLabel("50")
        sld_thr = QSlider(Qt.Horizontal)
        sld_thr.setRange(0, 100)
        sld_thr.setValue(50)
        sld_thr.setStyleSheet("""
            QSlider::groove:horizontal {
                height:4px;
                background:#363636;
                border-radius:2px;
            }
            QSlider::handle:horizontal {
                width:16px;
                height:16px;
                background:#0078d4;
                border-radius:8px;
                margin:-6px 0;
            }
        """)
        def on_thr_val(v):
            lb_thr.setText(str(v))
        sld_thr.valueChanged.connect(on_thr_val)
        row_thr.addWidget(lb_thr)
        row_thr.addWidget(sld_thr)
        c_thr.right_box.addLayout(row_thr)
        lay.addWidget(c_thr)

        # Microphone level preview
        c_lvl = SettingCard("volume-2", "Microphone level preview", "")
        row_lvl = QHBoxLayout()
        row_lvl.addStretch(1)
        lb_mic = QLabel("70")
        pb_mic = QProgressBar()
        pb_mic.setRange(0, 100)
        pb_mic.setValue(70)
        pb_mic.setTextVisible(False)
        pb_mic.setStyleSheet("""
            QProgressBar {
                background:#e0e0e0;
                border:none;
                border-radius:2px;
                height:2px;
            }
            QProgressBar::chunk {
                background:#0078d4;
                border-radius:2px;
            }
        """)
        row_lvl.addWidget(lb_mic)
        row_lvl.addWidget(pb_mic)
        c_lvl.right_box.addLayout(row_lvl)
        lay.addWidget(c_lvl)

        # Sound effects
        c_sfx = SettingCard("music", "Sound effects", "")
        row_sfx = QHBoxLayout()
        row_sfx.addStretch(1)
        lb_sfx = QLabel("on")
        tg_sfx = ToggleSwitch(True)
        row_sfx.addWidget(lb_sfx)
        row_sfx.addWidget(tg_sfx)
        c_sfx.right_box.addLayout(row_sfx)
        lay.addWidget(c_sfx)

        # Effects volume (прячем, если off)
        self.c_vol = SettingCard("volume-2", "Effects volume", "")
        row_ev = QHBoxLayout()
        row_ev.addStretch(1)
        lb_ev = QLabel("50")
        sld_ev = QSlider(Qt.Horizontal)
        sld_ev.setRange(0, 100)
        sld_ev.setValue(50)
        sld_ev.setStyleSheet("""
            QSlider::groove:horizontal {
                height:4px;
                background:#363636;
                border-radius:2px;
            }
            QSlider::handle:horizontal {
                width:16px;
                height:16px;
                background:#0078d4;
                border-radius:8px;
                margin:-6px 0;
            }
        """)
        def on_ev_val(v):
            lb_ev.setText(str(v))
        sld_ev.valueChanged.connect(on_ev_val)
        row_ev.addWidget(lb_ev)
        row_ev.addWidget(sld_ev)
        self.c_vol.right_box.addLayout(row_ev)
        lay.addWidget(self.c_vol)

        # Логика скрытия:
        def on_sfx_change(b):
            lb_sfx.setText("on" if b else "off")
            self.c_vol.setVisible(b)

        tg_sfx.clicked.connect(on_sfx_change)

        lay.addStretch(1)
        return w

    ###########################################################################
    # Skin store
    ###########################################################################
    def make_page_store(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20,20,20,20)
        lay.setSpacing(20)

        lb = QLabel("Skin store")
        lb.setStyleSheet("font-size:26px;")
        lay.addWidget(lb)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        lay.addWidget(scroll, 1)

        cont = QWidget()
        cont_lay = QVBoxLayout(cont)
        cont_lay.setContentsMargins(0,0,0,0)
        cont_lay.setSpacing(10)

        c1 = StoreCard("#FF5733", "Classic Duckling", "Cute yellow duckling", "#classic #yellow #cute", "5.99 €")
        c2 = StoreCard("#33FF57", "Night Duck",       "Dark themed duck", "#night #dark #stealth", "5.99 €")
        c3 = StoreCard("#3357FF", "Space Duck",       "Duck with space suit", "#space #futuristic #cool", "5.99 €")
        c4 = StoreCard("#FF33A8", "Golden Duck",      "Duck made of gold", "#golden #luxury #shiny", "5.99 €")
        c5 = StoreCard("#33FFF6", "Cyber Duck",       "High-tech cyber duck", "#cyber #tech #modern", "5.99 €")

        for card in [c1, c2, c3, c4, c5]:
            cont_lay.addWidget(card)

        cont_lay.addStretch(1)
        scroll.setWidget(cont)
        return w

    ###########################################################################
    # About
    ###########################################################################
    def make_page_about(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20,20,20,20)
        lay.setSpacing(20)

        lb = QLabel("About")
        lb.setStyleSheet("font-size:26px;")
        lay.addWidget(lb)

        center_box = QVBoxLayout()
        center_box.setSpacing(20)

        h2 = QLabel("Quack Duck")
        h2.setStyleSheet("font-size:24px;")
        h2.setAlignment(Qt.AlignCenter)
        center_box.addWidget(h2)

        row_btn = QHBoxLayout()
        row_btn.setSpacing(20)
        btn_coffee = QPushButton("Buy me a coffee")
        btn_tg     = QPushButton("Telegram")
        btn_tg.setStyleSheet("background:#0088cc;")
        btn_git    = QPushButton("GitHub")
        row_btn.addWidget(btn_coffee)
        row_btn.addWidget(btn_tg)
        row_btn.addWidget(btn_git)
        center_box.addLayout(row_btn)

        lay.addLayout(center_box)

        dev_lab = QLabel("Developed with 💜 by zl0yxp")
        dev_lab.setStyleSheet("color:#888; font-size:14px;")
        dev_lab.setAlignment(Qt.AlignCenter)
        lay.addWidget(dev_lab)

        lay.addStretch(1)
        return w

###############################################################################
# Запуск
###############################################################################
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SettingsWindow()
    win.show()
    sys.exit(app.exec())
