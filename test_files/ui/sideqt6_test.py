import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QStackedWidget, QLineEdit, QComboBox, QSlider, QScrollArea,
    QProgressBar, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, pyqtSignal, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QBrush

# ----------------------------
# Кастомный переключатель (toggle switch)
# ----------------------------
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, initial=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self._active = initial
        self._circle_position = 23 if self._active else 3
        self.animation = QPropertyAnimation(self, b"circle_position")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)

    def mousePressEvent(self, event):
        self._active = not self._active
        self.toggled.emit(self._active)
        start = self._circle_position
        end = 23 if self._active else 3
        self.animation.stop()
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        self.animation.start()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bg_color = QColor("#0078d4") if self._active else QColor("#484848")
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)
        painter.setBrush(QBrush(QColor("white")))
        circle_rect = QRect(self._circle_position, 3, 18, 18)
        painter.drawEllipse(circle_rect)

    def get_circle_position(self):
        return self._circle_position

    def set_circle_position(self, pos):
        self._circle_position = pos
        self.update()

    circle_position = pyqtProperty(int, fget=get_circle_position, fset=set_circle_position)

# ----------------------------
# Виджет-стрелка для расширения (expand arrow)
# ----------------------------
class ExpandArrow(QLabel):
    toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setFixedSize(20, 20)
        self.expanded = False
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("color: #888; font-size: 16px;")
        self.updateArrow()

    def mousePressEvent(self, event):
        self.expanded = not self.expanded
        self.updateArrow()
        self.toggled.emit(self.expanded)

    def updateArrow(self):
        self.setText("▲" if self.expanded else "▼")

# ----------------------------
# Виджет с расширяемым содержимым (анимация slideDown/slideUp)
# ----------------------------
class ExpandableContent(QWidget):
    def __init__(self):
        super().__init__()
        self.setMaximumHeight(0)
        self.setVisible(False)
        self.animation = QPropertyAnimation(self, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)

    def toggle(self, expand):
        self.animation.stop()
        if expand:
            self.setVisible(True)
            self.animation.setStartValue(0)
            self.animation.setEndValue(self.sizeHint().height())
            self.animation.start()
        else:
            self.animation.setStartValue(self.maximumHeight())
            self.animation.setEndValue(0)
            self.animation.start()
            self.animation.finished.connect(lambda: self.setVisible(False))

# ----------------------------
# Виджет строки настроек
# ----------------------------
class SettingItem(QWidget):
    def __init__(self, icon="", title="", description="", control_widget=None):
        super().__init__()
        # Для соответствия CSS‑стилям задаём отступы и закругления
        self.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #363636;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        # Левая часть (иконка и текст)
        leftWidget = QWidget()
        leftLayout = QVBoxLayout(leftWidget)
        leftLayout.setContentsMargins(0, 0, 0, 0)
        topRow = QHBoxLayout()
        iconLabel = QLabel(icon)
        iconLabel.setFixedSize(24, 24)
        iconLabel.setStyleSheet("color: white;")
        topRow.addWidget(iconLabel)
        titleLabel = QLabel(title)
        titleLabel.setStyleSheet("color: white; font-size: 18px;")
        topRow.addWidget(titleLabel)
        topRow.addStretch()
        leftLayout.addLayout(topRow)
        descLabel = QLabel(description)
        descLabel.setStyleSheet("color: #888; font-size: 14px;")
        leftLayout.addWidget(descLabel)
        layout.addWidget(leftWidget)
        # Правая часть – управляющий элемент (если он есть)
        if control_widget:
            layout.addWidget(control_widget)
        else:
            layout.addStretch()

# ----------------------------
# Виджет карточки скина для магазина
# ----------------------------
class SkinCardShop(QWidget):
    def __init__(self, img, title_text, desc, borderColor):
        super().__init__()
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #363636;
                border: 1px solid {borderColor};
                border-radius: 8px;
                padding: 20px;
            }}
        """)
        layout = QHBoxLayout(self)
        # Превью скина
        preview = QLabel()
        preview.setFixedSize(100, 100)
        preview.setStyleSheet(f"""
            background-image: url({img});
            background-position: center;
            background-repeat: no-repeat;
            border-radius: 4px;
            background-color: #252525;
        """)
        layout.addWidget(preview)
        # Информация о скине
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        priceLabel = QLabel("5.99 €")
        priceLabel.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        titleLabel = QLabel(title_text)
        titleLabel.setStyleSheet("font-size: 18px; color: white;")
        descLabel = QLabel(desc)
        descLabel.setStyleSheet("color: #888;")
        hashtagsLabel = QLabel("#" + " #".join(title_text.lower().split()))
        hashtagsLabel.setStyleSheet("color: #0078d4; font-size: 14px;")
        info_layout.addWidget(priceLabel)
        info_layout.addWidget(titleLabel)
        info_layout.addWidget(descLabel)
        info_layout.addWidget(hashtagsLabel)
        purchaseButton = QPushButton("Purchase")
        purchaseButton.setStyleSheet("""
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        """)
        info_layout.addWidget(purchaseButton, alignment=Qt.AlignRight | Qt.AlignBottom)
        layout.addWidget(info)

# ----------------------------
# Страница "Appearance"
# ----------------------------
class AppearancePage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Appearance")
        title.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(title)

        # Card "Pet name"
        petNameEdit = QLineEdit()
        petNameEdit.setPlaceholderText("Enter pet name")
        petNameEdit.setFixedHeight(30)
        petNameLayout = QHBoxLayout()
        petNameLayout.setSpacing(10)
        petNameLayout.addWidget(petNameEdit)
        arrow = ExpandArrow()
        petNameLayout.addWidget(arrow)
        petNameContainer = QWidget()
        petNameContainer.setLayout(petNameLayout)
        petNameItem = SettingItem(icon="🏷", title="Pet name",
                                  description="Affects the pet's characteristics and behavior",
                                  control_widget=petNameContainer)
        layout.addWidget(petNameItem)

        # Расширяемое содержимое (аналог таблицы)
        expandedContent = ExpandableContent()
        ec_layout = QVBoxLayout(expandedContent)
        ec_layout.setContentsMargins(20, 10, 20, 10)
        row1 = QLabel("Speed: 2.2 units")
        row1.setStyleSheet("color: #ccc;")
        row2 = QLabel("Timeout: 2 mins.")
        row2.setStyleSheet("color: #ccc;")
        ec_layout.addWidget(row1)
        ec_layout.addWidget(row2)
        layout.addWidget(expandedContent)
        arrow.toggled.connect(expandedContent.toggle)

        # Card "Show name" с переключателем
        toggleSwitch = ToggleSwitch(initial=True)
        showNameItem = SettingItem(icon="👁", title="Show name",
                                   description="Enable or disable the display of the name above the pet's head",
                                   control_widget=toggleSwitch)
        layout.addWidget(showNameItem)

        # Card "Pet size" с комбобоксом
        sizeCombo = QComboBox()
        sizeCombo.addItems(["Small", "Medium", "Big"])
        petSizeItem = SettingItem(icon="🔍", title="Pet size",
                                  description="The size of the pet on the screen",
                                  control_widget=sizeCombo)
        layout.addWidget(petSizeItem)

        # Card "Skins folder path..."
        folderLine = QLineEdit()
        folderLine.setPlaceholderText("path/to/your/skins...")
        folderLine.setReadOnly(True)
        folderButton = QPushButton("Select")
        folderButton.setStyleSheet("""
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        """)
        folderLayout = QHBoxLayout()
        folderLayout.setSpacing(10)
        folderLayout.addWidget(folderLine)
        folderLayout.addWidget(folderButton)
        folderWidget = QWidget()
        folderWidget.setLayout(folderLayout)
        folderItem = SettingItem(icon="📁", title="Skins folder path...",
                                 description="Specify the folder containing additional skins, if you have any",
                                 control_widget=folderWidget)
        layout.addWidget(folderItem)

        # Большой блок предпросмотра скинов
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background-color: #363636; border-radius: 8px;")
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(10)
        for i in range(10):
            skinCard = QFrame()
            skinCard.setFixedSize(120, 120)
            skinCard.setStyleSheet("background-color: #363636; border: 1px solid #494949; border-radius: 4px;")
            grid.addWidget(skinCard, i // 5, i % 5)
        scrollArea.setWidget(container)
        layout.addWidget(scrollArea)
        layout.addStretch()

# ----------------------------
# Страница "General"
# ----------------------------
class GeneralPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("General")
        title.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(title)

        # Card "Language"
        langCombo = QComboBox()
        langCombo.addItems(["Russian", "English"])
        languageItem = SettingItem(icon="🌐", title="Language",
                                   description="The application's interface language",
                                   control_widget=langCombo)
        layout.addWidget(languageItem)

        # Card "Floor level"
        floorEdit = QLineEdit()
        floorEdit.setText("0")
        floorItem = SettingItem(icon="🗺", title="Floor level",
                                description="The minimum level where the pet will stand (in pixels)",
                                control_widget=floorEdit)
        layout.addWidget(floorItem)

        # Card "Name offset"
        offsetEdit = QLineEdit()
        offsetEdit.setText("0")
        offsetItem = SettingItem(icon="⬆", title="Name offset",
                                 description="Vertical offset (Y-axis) for the pet's name (in pixels)",
                                 control_widget=offsetEdit)
        layout.addWidget(offsetItem)

        # Card "Font size"
        fontEdit = QLineEdit()
        fontEdit.setText("16")
        fontItem = SettingItem(icon="🔤", title="Font size",
                               description="Base font size for the pet's name, which scales with the pet's size",
                               control_widget=fontEdit)
        layout.addWidget(fontItem)

        # Card "Autostart"
        autostartSwitch = ToggleSwitch(initial=False)
        autostartItem = SettingItem(icon="⚡", title="Autostart",
                                    description="Launch the pet with your system",
                                    control_widget=autostartSwitch)
        layout.addWidget(autostartItem)

        # Card "Reset All Settings"
        resetButton = QPushButton("Reset")
        resetButton.setStyleSheet("""
            background-color: #e81123;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        """)
        resetItem = SettingItem(icon="🔄", title="Reset All Settings",
                                description="Reset all settings to their default values",
                                control_widget=resetButton)
        layout.addWidget(resetItem)

        layout.addStretch()

# ----------------------------
# Страница "Audio"
# ----------------------------
class AudioPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Audio")
        title.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(title)

        # Card "Input device"
        deviceCombo = QComboBox()
        deviceCombo.addItems(["Default microphone"])
        inputDeviceItem = SettingItem(icon="🎤", title="Input device", description="", control_widget=deviceCombo)
        layout.addWidget(inputDeviceItem)

        # Card "Activation threshold"
        thresholdSlider = QSlider(Qt.Horizontal)
        thresholdSlider.setMinimum(0)
        thresholdSlider.setMaximum(100)
        thresholdSlider.setValue(50)
        thresholdLabel = QLabel("50")
        thresholdLabel.setStyleSheet("color: white;")
        thresholdSlider.valueChanged.connect(lambda val: thresholdLabel.setText(str(val)))
        thresholdWidget = QWidget()
        hbox = QHBoxLayout(thresholdWidget)
        hbox.setSpacing(10)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(thresholdLabel)
        hbox.addWidget(thresholdSlider)
        thresholdItem = SettingItem(icon="🎚", title="Activation threshold",
                                    description="Sound volume threshold at which the pet plays a listening animation",
                                    control_widget=thresholdWidget)
        layout.addWidget(thresholdItem)

        # Card "Microphone level preview"
        micProgress = QProgressBar()
        micProgress.setMaximum(100)
        micProgress.setValue(70)
        micProgress.setTextVisible(False)
        micProgress.setFixedHeight(4)
        micProgress.setStyleSheet("""
            QProgressBar {
                background-color: #e0e0e0;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 2px;
            }
        """)
        micLabel = QLabel("70")
        micLabel.setStyleSheet("color: white;")
        micWidget = QWidget()
        hbox2 = QHBoxLayout(micWidget)
        hbox2.setSpacing(10)
        hbox2.setContentsMargins(0, 0, 0, 0)
        hbox2.addWidget(micLabel)
        hbox2.addWidget(micProgress)
        micItem = SettingItem(icon="📊", title="Microphone level preview", description="", control_widget=micWidget)
        layout.addWidget(micItem)

        # Card "Sound effects"
        effectsSwitch = ToggleSwitch(initial=True)
        effectsItem = SettingItem(icon="🎵", title="Sound effects", description="", control_widget=effectsSwitch)
        layout.addWidget(effectsItem)

        # Card "Effects volume"
        effectsVolumeSlider = QSlider(Qt.Horizontal)
        effectsVolumeSlider.setMinimum(0)
        effectsVolumeSlider.setMaximum(100)
        effectsVolumeSlider.setValue(50)
        effectsVolumeLabel = QLabel("50")
        effectsVolumeLabel.setStyleSheet("color: white;")
        effectsVolumeSlider.valueChanged.connect(lambda val: effectsVolumeLabel.setText(str(val)))
        effectsVolumeWidget = QWidget()
        hbox3 = QHBoxLayout(effectsVolumeWidget)
        hbox3.setSpacing(10)
        hbox3.setContentsMargins(0, 0, 0, 0)
        hbox3.addWidget(effectsVolumeLabel)
        hbox3.addWidget(effectsVolumeSlider)
        effectsVolumeItem = SettingItem(icon="🔊", title="Effects volume", description="", control_widget=effectsVolumeWidget)
        layout.addWidget(effectsVolumeItem)
        self.effectsVolumeItem = effectsVolumeItem

        # При переключении звуковых эффектов показываем/скрываем регулировку громкости
        effectsSwitch.toggled.connect(self.onEffectsToggled)

        layout.addStretch()

    def onEffectsToggled(self, active):
        self.effectsVolumeItem.setVisible(active)

# ----------------------------
# Страница "Skin store"
# ----------------------------
class SkinStorePage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Skin store")
        title.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(title)

        skins = [
            ("skin1.png", "Classic Duckling", "Cute yellow duckling", "#FF5733"),
            ("skin2.png", "Night Duck", "Dark themed duck", "#33FF57"),
            ("skin3.png", "Space Duck", "Duck with a space suit", "#3357FF"),
            ("skin4.png", "Golden Duck", "Duck made of gold", "#FF33A8"),
            ("skin5.png", "Cyber Duck", "High-tech cyber duck", "#33FFF6"),
        ]
        for img, title_text, desc, color in skins:
            card = SkinCardShop(img, title_text, desc, color)
            layout.addWidget(card)

        layout.addStretch()

# ----------------------------
# Страница "About"
# ----------------------------
class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("About")
        title.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(title)

        aboutContent = QWidget()
        aboutLayout = QVBoxLayout(aboutContent)
        aboutLayout.setAlignment(Qt.AlignCenter)
        appTitle = QLabel("Quack Duck")
        appTitle.setStyleSheet("font-size: 32px; color: white;")
        aboutLayout.addWidget(appTitle)
        # Кнопки действий
        buttonsWidget = QWidget()
        btnLayout = QHBoxLayout(buttonsWidget)
        btnLayout.setSpacing(20)
        supportButton = QPushButton("Buy me a coffee")
        supportButton.setStyleSheet("""
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        """)
        telegramButton = QPushButton("Telegram")
        telegramButton.setStyleSheet("""
            background-color: #0088cc;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        """)
        githubButton = QPushButton("GitHub")
        githubButton.setStyleSheet("""
            background-color: #333;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        """)
        btnLayout.addWidget(supportButton)
        btnLayout.addWidget(telegramButton)
        btnLayout.addWidget(githubButton)
        aboutLayout.addWidget(buttonsWidget)
        layout.addWidget(aboutContent)
        devlove = QLabel("Developed with 💜 by zl0yxp")
        devlove.setStyleSheet("color: #888; font-size: 14px;")
        devlove.setAlignment(Qt.AlignCenter)
        layout.addWidget(devlove)
        layout.addStretch()

# ----------------------------
# Виджет бокового меню
# ----------------------------
class SidebarWidget(QWidget):
    menuClicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(250)
        self.setStyleSheet("background-color: #252525;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        # Анимированная полоса-селектор
        self.menu_selector = QFrame(self)
        self.menu_selector.setStyleSheet("background-color: #0078d4; border-radius: 2px;")
        self.menu_selector.setGeometry(0, 0, 4, 12)
        self.menu_selector.show()
        # Логотип
        logoLayout = QHBoxLayout()
        logoIcon = QLabel()
        logoIcon.setFixedSize(40, 40)
        logoIcon.setStyleSheet("background-color: #0078d4; border-radius: 8px;")
        logoText = QLabel("Quack Duck")
        logoText.setStyleSheet("color: white; font-size: 16px;")
        logoLayout.addWidget(logoIcon)
        logoLayout.addWidget(logoText)
        layout.addLayout(logoLayout)
        layout.addSpacing(30)
        # Элементы меню
        self.menu_items = []
        menu_definitions = [
            ("appearance", "#0078d4", "Appearance"),
            ("general", "#00b294", "General"),
            ("audio", "#ff8c00", "Audio"),
            ("skinstore", "#e81123", "Skin store"),
            ("about", "#68217a", "About"),
        ]
        for page, color, text in menu_definitions:
            btn = QPushButton(text)
            btn.setObjectName(page)
            btn.page = page
            btn.menuColor = color
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 12px;
                    margin: 8px 0;
                    border-radius: 6px;
                    background: transparent;
                    color: white;
                    font-size: 18px;
                }
                QPushButton:checked {
                    background-color: #363636;
                }
                QPushButton:hover {
                    background-color: #363636;
                }
            """)
            btn.clicked.connect(self.handleMenuClicked)
            layout.addWidget(btn)
            self.menu_items.append(btn)
        if self.menu_items:
            self.menu_items[0].setChecked(True)
        layout.addStretch()
        version = QLabel("Version 1.5.3")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(version)
        self.resizeEvent(None)

    def handleMenuClicked(self):
        sender = self.sender()
        self.animateSelector(sender)
        self.menuClicked.emit(sender.page)

    def animateSelector(self, targetBtn):
        pos = targetBtn.pos()
        height = targetBtn.height()
        target_top = pos.y() + (height - 12) / 2
        animation = QPropertyAnimation(self.menu_selector, b"geometry")
        animation.setDuration(200)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        animation.setStartValue(self.menu_selector.geometry())
        newRect = QRect(0, int(target_top), 4, 12)
        animation.setEndValue(newRect)
        animation.start()
        self.currentAnimation = animation

    def resizeEvent(self, event):
        active = None
        for btn in self.menu_items:
            if btn.isChecked():
                active = btn
                break
        if active:
            pos = active.pos()
            height = active.height()
            target_top = pos.y() + (height - 12) / 2
            self.menu_selector.setGeometry(0, int(target_top), 4, 12)
        super().resizeEvent(event)

# ----------------------------
# Функция-обёртка для создания прокручиваемой области
# ----------------------------
def make_scrollable(widget):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    scroll.setStyleSheet("""
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        QScrollBar:vertical {
            width: 8px;
            background: #363636;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #666;
            border-radius: 4px;
        }
    """)
    return scroll

# ----------------------------
# Главное окно
# ----------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quack Duck Settings")
        self.setStyleSheet("background-color: #1e1e1e;")
        mainWidget = QWidget()
        mainLayout = QHBoxLayout(mainWidget)
        self.sidebar = SidebarWidget()
        self.content = QStackedWidget()
        # Создаём страницы и оборачиваем их в QScrollArea для корректного позиционирования
        self.appearancePage = AppearancePage()
        self.generalPage = GeneralPage()
        self.audioPage = AudioPage()
        self.skinstorePage = SkinStorePage()
        self.aboutPage = AboutPage()

        self.content.addWidget(make_scrollable(self.appearancePage))
        self.content.addWidget(make_scrollable(self.generalPage))
        self.content.addWidget(make_scrollable(self.audioPage))
        self.content.addWidget(make_scrollable(self.skinstorePage))
        self.content.addWidget(make_scrollable(self.aboutPage))

        mainLayout.addWidget(self.sidebar)
        mainLayout.addWidget(self.content)
        self.setCentralWidget(mainWidget)
        self.sidebar.menuClicked.connect(self.changePage)

    def changePage(self, pageName):
        mapping = {
            "appearance": 0,
            "general": 1,
            "audio": 2,
            "skinstore": 3,
            "about": 4
        }
        index = mapping.get(pageName, 0)
        self.content.setCurrentIndex(index)

# ----------------------------
# Запуск приложения
# ----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec_())
