import sys
from PySide6.QtCore import (Qt, QPropertyAnimation, QRect, QEasingCurve,
                            QTimer, Signal, Property)
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
                               QHBoxLayout, QVBoxLayout, QLabel, QFrame)


class MenuSelector(QFrame):
    def __init__(self):
        super().__init__()
        self.setGeometry(0, 0, 4, 12)

        # For position animation
        self._animPos = QPropertyAnimation(self, b"geometry")
        self._animPos.setDuration(200)
        self._animPos.setEasingCurve(QEasingCurve.InOutCubic)

        # For color animation
        self._bgColor = QColor("#0078d4")  # Initial color
        self._animColor = QPropertyAnimation(self, b"bgColor")
        self._animColor.setDuration(200)
        self._animColor.setEasingCurve(QEasingCurve.InOutCubic)

    # -------------------- bgColor property for animation --------------------
    @Property(QColor)
    def bgColor(self):
        return self._bgColor

    @bgColor.setter
    def bgColor(self, c: QColor):
        self._bgColor = c
        self.update()

    def animateColorChange(self, new_color: QColor):
        self._animColor.stop()
        self._animColor.setStartValue(self._bgColor)
        self._animColor.setEndValue(new_color)
        self._animColor.start()

    # -------------------- Rendering --------------------
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._bgColor)
        p.end()

    # -------------------- Movement animation --------------------
    def moveTo(self, start_rect: QRect, end_rect: QRect, container_top: int):
        """Animation of 'stretching' and 'compressing' from start_rect to end_rect."""
        start_y = start_rect.top() - container_top + (start_rect.height() - 12) // 2
        end_y   = end_rect.top() - container_top   + (end_rect.height()   - 12) // 2

        bigger = QRect(self.x(), min(start_y, end_y), 4, abs(end_y - start_y) + 12)
        self._animPos.stop()
        self._animPos.setStartValue(self.geometry())
        self._animPos.setEndValue(bigger)
        self._animPos.start()

        def step2():
            self._animPos.stop()
            final_rect = QRect(self.x(), end_y, 4, 12)
            self._animPos.setStartValue(bigger)
            self._animPos.setEndValue(final_rect)
            self._animPos.start()

        QTimer.singleShot(200, step2)


class MenuButton(QLabel):
    clicked = Signal()

    def __init__(self, text: str):
        super().__init__(text)
        self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.setFixedHeight(50)
        self.setStyleSheet("""
            QLabel {
                padding-left: 10px;
                background: transparent;
                color: #ffffff;
                font-size: 15px;
            }
            QLabel:hover {
                background: #363636;
            }
        """)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet("""
                QLabel {
                    padding-left: 10px;
                    background: #363636;
                    color: #ffffff;
                    font-size: 15px;
                }
                QLabel:hover {
                    background: #363636;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    padding-left: 10px;
                    background: transparent;
                    color: #ffffff;
                    font-size: 15px;
                }
                QLabel:hover {
                    background: #363636;
                }
            """)


class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(200)
        self.setStyleSheet("background: #252525;")

        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(20, 20, 20, 20)
        self.layout_main.setSpacing(20)

        self.selector = MenuSelector()
        self.selector.setParent(self)
        self.selector.hide()

        self.menu_items = []
        self.active_item = None

        # Color map for the menu
        self.color_map = {
            "appearance":  "#0078d4",
            "general":     "#8300e8",
            "audio":       "#ff8c00",
            "skin store":  "#e81123",
            "about":       "#68217a"
        }

        # Create buttons
        self.btn_appearance = self.create_menu_button("appearance")
        self.btn_general    = self.create_menu_button("general")
        self.btn_audio      = self.create_menu_button("audio")
        self.btn_store      = self.create_menu_button("skin store")
        self.btn_about      = self.create_menu_button("about")

        for btn in [self.btn_appearance, self.btn_general, self.btn_audio,
                    self.btn_store, self.btn_about]:
            self.layout_main.addWidget(btn)

        self.layout_main.addStretch()

    def create_menu_button(self, text: str) -> MenuButton:
        w = MenuButton(text)
        w.clicked.connect(lambda: self.set_active_item(w))
        self.menu_items.append(w)
        return w

    def showEvent(self, event):
        # When the sidebar is already showing and geometry is calculated
        super().showEvent(event)
        # Set 'appearance' as active
        if not self.active_item:
            self.set_active_item(self.btn_appearance)

    def set_active_item(self, w: MenuButton):
        if self.active_item == w:
            return

        old_item = self.active_item
        self.active_item = w

        # Change button styles
        for item in self.menu_items:
            item.set_active(item == w)

        # Show selector if it's hidden
        if not self.selector.isVisible():
            self.selector.show()

        # Animate selector color
        new_color = self.color_map.get(w.text(), "#0078d4")
        self.selector.animateColorChange(QColor(new_color))

        # Animate movement
        if old_item:
            old_rect = old_item.geometry()
            new_rect = w.geometry()
            self.selector.moveTo(old_rect, new_rect, 0)
        else:
            # On first show, set selector directly under the needed button
            rect = w.geometry()
            y = rect.top() + (rect.height() - 12) // 2
            self.selector.setGeometry(10, y, 4, 12)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sidebar Demo")
        self.setGeometry(100, 100, 800, 600)

        # Background for the whole window
        self.setStyleSheet("QMainWindow { background: #252525; }")

        central = QWidget()
        self.setCentralWidget(central)

        hbox = QHBoxLayout(central)
        self.sidebar = Sidebar()
        hbox.addWidget(self.sidebar)

        # Empty area on the right
        placeholder = QWidget()
        hbox.addWidget(placeholder, 1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
