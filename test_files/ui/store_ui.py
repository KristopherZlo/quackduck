import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QStackedWidget,
                            QGridLayout, QLineEdit, QSlider, QComboBox,
                            QProgressBar, QSpacerItem, QSizePolicy, QScrollArea,
                            QFrame, QFileDialog)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QFontDatabase, QFont, QPalette, QColor

class ToggleSwitch(QWidget):
    def __init__(self, initial_state=False):
        super().__init__()
        self.setFixedSize(44, 24)
        self._checked = initial_state
        
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        self.setStyleSheet("""
            background-color: #484848;
            border-radius: 12px;
        """)
        
        if initial_state:
            self.setStyleSheet("""
                background-color: #0078d4;
                border-radius: 12px;
            """)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.animate_toggle()
        self.update()

    def animate_toggle(self):
        self.animation.setStartValue(0 if self._checked else 1)
        self.animation.setEndValue(1 if self._checked else 0)
        self.animation.start()
        
        if self._checked:
            self.setStyleSheet("""
                background-color: #0078d4;
                border-radius: 12px;
            """)
        else:
            self.setStyleSheet("""
                background-color: #484848;
                border-radius: 12px;
            """)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QBrush
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Рисуем круглый индикатор
        painter.setBrush(QBrush(QColor("white")))
        painter.setPen(Qt.PenStyle.NoPen)
        
        if self._checked:
            painter.drawEllipse(23, 3, 18, 18)
        else:
            painter.drawEllipse(3, 3, 18, 18)

class CustomSlider(QSlider):
    def __init__(self, orientation=Qt.Orientation.Horizontal):
        super().__init__(orientation)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: #363636;
                margin: 0px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 2px;
            }
        """)

class CustomComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QComboBox {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                color: white;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 20px;
            }
            QComboBox::down-arrow {
                image: url(icons/chevron-down.svg);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #363636;
                border: none;
                selection-background-color: #0078d4;
                selection-color: white;
                color: white;
            }
        """)

class CustomLineEdit(QLineEdit):
    def __init__(self, placeholder=""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #363636;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                color: white;
                min-width: 200px;
            }
            QLineEdit::placeholder {
                color: #888;
            }
        """)

class SettingsCard(QWidget):
    def __init__(self, icon_name, title, description="", control=None):
        super().__init__()
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        # Иконка и текст
        info_layout = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(QIcon(f"icons/{icon_name}.svg").pixmap(QSize(24, 24)))
        icon.setFixedSize(24, 24)
        
        text_layout = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 14px;")
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #888; font-size: 12px; margin-right: 30px;")
        desc_label.setWordWrap(True)
        
        text_layout.addWidget(title_label)
        if description:
            text_layout.addWidget(desc_label)
            
        info_widget = QWidget()
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.addWidget(icon)
        info_layout.addLayout(text_layout)
        info_layout.addStretch()
        info_widget.setLayout(info_layout)
        
        layout.addWidget(info_widget, stretch=1)
        
        # Добавляем контрол, если он есть
        if control:
            layout.addWidget(control)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #363636;
                border-radius: 8px;
            }
            QWidget:hover {
                border-color: white;
            }
        """)
        
        # Устанавливаем отступы для карточки
        layout.setContentsMargins(20, 20, 20, 20)

class ScrollableSettings(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.1);
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

def setup_appearance_page(self):
    scroll_content = QWidget()
    layout = QVBoxLayout(scroll_content)
    layout.setSpacing(15)
    
    # Заголовок
    title = QLabel("Appearance")
    title.setStyleSheet("color: white; font-size: 24px; margin-bottom: 20px;")
    layout.addWidget(title)
    
    # Pet Name
    name_input = CustomLineEdit("Enter pet name")
    pet_name_card = SettingsCard(
        "tag",
        "Pet name",
        "Affects the pet's characteristics and behavior",
        name_input
    )
    layout.addWidget(pet_name_card)
    
    # Show Name
    toggle = ToggleSwitch(True)
    show_name_card = SettingsCard(
        "eye",
        "Show name",
        "Enable or disable the display of the name above the pet's head",
        toggle
    )
    layout.addWidget(show_name_card)
    
    # Pet Size
    size_combo = CustomComboBox()
    size_combo.addItems(["Small", "Medium", "Big"])
    pet_size_card = SettingsCard(
        "maximize-2",
        "Pet size",
        "The size of the pet on the screen",
        size_combo
    )
    layout.addWidget(pet_size_card)
    
    # Skins Folder
    folder_widget = QWidget()
    folder_layout = QHBoxLayout(folder_widget)
    folder_layout.setContentsMargins(0, 0, 0, 0)
    
    folder_input = CustomLineEdit("path/to/your/skins...")
    folder_input.setReadOnly(True)
    
    folder_button = QPushButton("Select")
    folder_button.setIcon(QIcon("icons/folder-open.svg"))
    folder_button.setStyleSheet("""
        QPushButton {
            background-color: #0078d4;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            color: white;
        }
        QPushButton:hover {
            background-color: #1982d4;
        }
    """)
    
    folder_layout.addWidget(folder_input)
    folder_layout.addWidget(folder_button)
    
    skins_folder_card = SettingsCard(
        "folder",
        "Skins folder path...",
        "Specify the folder containing additional skins, if you have any",
        folder_widget
    )
    layout.addWidget(skins_folder_card)
    
    # Skin Preview Grid
    preview_grid = QWidget()
    preview_grid.setStyleSheet("""
        QWidget {
            background-color: #2d2d2d;
            border-radius: 8px;
            min-height: 300px;
        }
    """)
    grid_layout = QGridLayout(preview_grid)
    
    # Добавляем плейсхолдеры для скинов
    for i in range(10):
        skin_card = QFrame()
        skin_card.setStyleSheet("""
            QFrame {
                background-color: #363636;
                border: 1px solid #494949;
                border-radius: 4px;
                min-width: 120px;
                min-height: 120px;
            }
            QFrame:hover {
                border-color: white;
            }
        """)
        grid_layout.addWidget(skin_card, i // 4, i % 4)
    
    layout.addWidget(preview_grid)
    layout.addStretch()
    
    # Создаем скроллируемую область
    scroll = ScrollableSettings()
    scroll.setWidget(scroll_content)
    
    # Добавляем скроллируемую область в страницу
    page_layout = QVBoxLayout(self.appearance_page)
    page_layout.addWidget(scroll)

def setup_general_page(self):
    scroll_content = QWidget()
    layout = QVBoxLayout(scroll_content)
    layout.setSpacing(15)
    
    title = QLabel("General")
    title.setStyleSheet("color: white; font-size: 24px; margin-bottom: 20px;")
    layout.addWidget(title)
    
    # Language
    lang_combo = CustomComboBox()
    lang_combo.addItems(["Russian", "English"])
    lang_card = SettingsCard(
        "globe",
        "Language",
        "The application's interface language",
        lang_combo
    )
    layout.addWidget(lang_card)
    
    # Floor Level
    floor_input = CustomLineEdit()
    floor_input.setValidator(QIntValidator())
    floor_card = SettingsCard(
        "layers",
        "Floor level",
        "The minimum level where the pet will stand (in pixels)",
        floor_input
    )
    layout.addWidget(floor_card)
    
    # Name Offset
    offset_input = CustomLineEdit()
    offset_input.setValidator(QIntValidator())
    offset_card = SettingsCard(
        "arrow-up",
        "Name offset",
        "Vertical offset (Y-axis) for the pet's name (in pixels)",
        offset_input
    )
    layout.addWidget(offset_card)
    
    # Font Size
    font_input = CustomLineEdit()
    font_input.setValidator(QIntValidator())
    font_input.setText("16")
    font_card = SettingsCard(
        "type",
        "Font size",
        "Base font size for the pet's name, which scales with the pet's size",
        font_input
    )
    layout.addWidget(font_card)
    
    # Autostart
    toggle = ToggleSwitch()
    autostart_card = SettingsCard(
        "zap",
        "Autostart",
        "Launch the pet with your system",
        toggle
    )
    layout.addWidget(autostart_card)
    
    # Reset Button
    reset_button = QPushButton("Reset")
    reset_button.setStyleSheet("""
        QPushButton {
            background-color: #e81123;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            color: white;
        }
        QPushButton:hover {
            background-color: #f81123;
        }
    """)
    reset_card = SettingsCard(
        "refresh-ccw",
        "Reset All Settings",
        "Reset all settings to their default values",
        reset_button
    )
    layout.addWidget(reset_card)
    
    layout.addStretch()
    
    scroll = ScrollableSettings()
    scroll.setWidget(scroll_content)
    
    page_layout = QVBoxLayout(self.general_page)
    page_layout.addWidget(scroll)

    def setup_audio_page(self):
        layout = QVBoxLayout(self.audio_page)
        title = QLabel("Audio")
        title.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(title)

    def setup_store_page(self):
        layout = QVBoxLayout(self.store_page)
        title = QLabel("Skin store")
        title.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(title)

    def setup_about_page(self):
        layout = QVBoxLayout(self.about_page)
        title = QLabel("About")
        title.setStyleSheet("color: white; font-size: 24px;")
        layout.addWidget(title)

    def switch_page(self, index):
        # Отключаем все кнопки
        for btn in [self.appearance_btn, self.general_btn, 
                   self.audio_btn, self.store_btn, self.about_btn]:
            btn.setChecked(False)
        
        # Включаем нужную кнопку
        [self.appearance_btn, self.general_btn, 
         self.audio_btn, self.store_btn, self.about_btn][index].setChecked(True)
        
        # Переключаем страницу
        self.stacked_widget.setCurrentIndex(index)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())