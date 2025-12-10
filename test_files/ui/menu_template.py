import sys
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QVBoxLayout, QWidget,
    QListWidget, QLabel, QPushButton, QStackedWidget, QLineEdit,
    QComboBox, QSlider, QProgressBar, QCheckBox,
    QSpacerItem, QSizePolicy, QSpinBox, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor


# Определение структуры MARGINS для DWM (не используется, но оставлено для будущих изменений)
class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int)
    ]


# Определение типа HRESULT вручную
HRESULT = ctypes.c_long  # Обычно HRESULT представляет собой 32-битное целое число


# Функции DWM, необходимые для применения размытия (не используются, так как эффект размытия удалён)
dwmapi = ctypes.WinDLL('dwmapi')
DwmExtendFrameIntoClientArea = dwmapi.DwmExtendFrameIntoClientArea
DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND, ctypes.POINTER(MARGINS)]
DwmExtendFrameIntoClientArea.restype = HRESULT  # Используем определённый тип HRESULT


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.init_ui()
        self.start = QPoint(0, 0)
        self.pressing = False

    def init_ui(self):
        self.setFixedHeight(40)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                /* Удалены закруглённые углы */
            }
            QLabel {
                color: white;
                font-size: 16px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 16px;
                width: 40px;
                height: 40px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-radius: 5px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        self.title = QLabel("Настройки")
        self.title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.title.setStyleSheet("background-color: transparent;")  # Убираем фон

        layout.addWidget(self.title)
        layout.addStretch()

        # Кнопка закрытия окна
        self.close_button = QPushButton("✖")
        self.close_button.setToolTip("Закрыть")
        self.close_button.clicked.connect(self.parent.close)

        layout.addWidget(self.close_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = event.globalPosition().toPoint()
            self.pressing = True

    def mouseMoveEvent(self, event):
        if self.pressing:
            self.parent.move(self.parent.pos() + event.globalPosition().toPoint() - self.start)
            self.start = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.pressing = False


class SettingsWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Настройки")
        self.resize(900, 700)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)  # Без рамки для стиля
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Заголовочная панель
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Основной контент
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Левая панель
        left_panel = QWidget()
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;  /* Более тёмный серый фон */
                /* Удалены закруглённые углы */
                border-right: 1px solid #444444;
            }
            QListWidget {
                background: transparent;
                color: white;
                border: none;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 12px;
            }
            QListWidget::item:selected {
                background: #444444;
                /* Убираем обводку */
                outline: none;
                border: 1px solid #2a2a2a;  /* Устанавливаем обводку цвета фона левой панели */
            }
            QLabel {
                color: gray;
                font-size: 12px;
            }
        """)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 20, 0, 20)
        left_layout.setSpacing(10)

        self.list_widget = QListWidget()
        self.list_widget.addItems(["Общее", "Внешний вид", "Расширенные", "О программе"])  # Переименовано "Общие" в "Общее"
        self.list_widget.setCurrentRow(0)
        left_layout.addWidget(self.list_widget)

        left_layout.addStretch()

        version_label = QLabel("Версия 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: gray; font-size: 12px;")
        left_layout.addWidget(version_label)

        # Стековые страницы
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.create_general_page())
        self.stacked_widget.addWidget(self.create_appearance_page())
        self.stacked_widget.addWidget(self.create_advanced_page())
        self.stacked_widget.addWidget(self.create_about_page())

        # Связь выбора в списке с переключением страниц
        self.list_widget.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)

        # Добавление панелей в основной контент
        content_layout.addWidget(left_panel)
        content_layout.addWidget(self.stacked_widget)

        main_layout.addLayout(content_layout)

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;  /* Практически чёрный фон */
                color: white;
                font-family: "Segoe UI", sans-serif;
                font-size: 14px;
                /* Удалены закруглённые углы */
            }
            QPushButton {
                background-color: #3c3c3c;
                border: none;
                padding: 10px 20px;
                color: white;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #606060;
            }
            QLineEdit, QComboBox, QSlider, QProgressBar, QSpinBox {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
                color: white;
                font-size: 14px;
            }
            QCheckBox {
                color: white;
                font-size: 14px;
            }
            QLabel {
                color: white;
                font-size: 14px;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 5px;
                text-align: center;
                height: 10px;  /* Уменьшена высота вдвое */
                padding: 1px;  /* Добавлен padding 1px */
            }
            QProgressBar::chunk {
                background-color: #05B8CC;
                width: 1px;
            }
        """)

    def create_general_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Имя питомца
        pet_name_label = QLabel("Имя питомца:")
        name_layout = QHBoxLayout()
        pet_name_edit = QLineEdit()
        name_info_button = QPushButton("ℹ️")
        name_info_button.setFixedSize(30, 30)
        name_info_button.setToolTip("Информация об имени питомца")
        name_layout.addWidget(pet_name_edit)
        name_layout.addWidget(name_info_button)

        # Выбор микрофона
        mic_label = QLabel("Выберите микрофон:")
        mic_combo = QComboBox()
        mic_combo.addItems(["Микрофон 1", "Микрофон 2", "Микрофон 3"])

        # Порог активации
        threshold_label = QLabel("Порог активации (0-100):")
        threshold_layout = QHBoxLayout()
        threshold_slider = QSlider(Qt.Orientation.Horizontal)
        threshold_slider.setRange(0, 100)
        threshold_slider.setValue(10)
        threshold_value_label = QLabel("10")
        threshold_slider.valueChanged.connect(lambda val: threshold_value_label.setText(str(val)))
        threshold_layout.addWidget(threshold_slider)
        threshold_layout.addWidget(threshold_value_label)

        # Уровень микрофона
        mic_level_preview = QProgressBar()
        mic_level_preview.setRange(0, 100)
        mic_level_preview.setValue(50)

        # Настройки звука
        enable_sound_checkbox = QCheckBox("Включить звук")
        autostart_checkbox = QCheckBox("Запускать при старте системы")

        # Кнопки
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        cancel_button = QPushButton("Отмена")
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Подключение кнопок к действиям
        save_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.close)

        # Добавление виджетов в общий layout
        layout.addWidget(pet_name_label)
        layout.addLayout(name_layout)
        layout.addWidget(mic_label)
        layout.addWidget(mic_combo)
        layout.addWidget(threshold_label)
        layout.addLayout(threshold_layout)
        layout.addWidget(mic_level_preview)
        layout.addWidget(enable_sound_checkbox)
        layout.addWidget(autostart_checkbox)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        return page

    def create_appearance_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Уровень пола
        floor_level_label = QLabel("Уровень пола (пикселей от низа):")
        floor_level_spin = QSpinBox()
        floor_level_spin.setRange(0, 1000)
        floor_level_spin.setValue(100)

        # Размер питомца
        pet_size_label = QLabel("Размер питомца:")
        pet_size_combo = QComboBox()
        pet_size_combo.addItems(["Маленький", "Средний", "Большой"])

        # Кнопки "Выбрать скин" и "Выбрать папку со скинами" на одной линии
        skin_buttons_layout = QHBoxLayout()
        skin_selection_button = QPushButton("Выбрать скин")
        skin_folder_button = QPushButton("Выбрать папку со скинами")
        skin_buttons_layout.addWidget(skin_selection_button)
        skin_buttons_layout.addWidget(skin_folder_button)

        # Предпросмотр скинов
        skins_label = QLabel("Предпросмотр скинов:")
        skins_scroll = QScrollArea()
        skins_scroll.setWidgetResizable(True)
        skins_container = QWidget()
        skins_grid = QGridLayout(skins_container)
        skins_grid.setSpacing(15)

        # Пример добавления виджетов скинов
        for i in range(8):
            skin_preview = QWidget()
            skin_preview.setFixedSize(120, 120)
            skin_preview.setStyleSheet("""
                QWidget {
                    background-color: #444444;
                    border: 1px solid #121212;  /* Цвет фона правой панели */
                    border-radius: 10px;
                }
            """)
            # Добавление изображения скина (замените "path_to_skin_image.png" на реальные пути)
            pixmap = QPixmap("path_to_skin_image.png")
            if pixmap.isNull():
                # Если изображение не найдено, используем placeholder
                pixmap = QPixmap(120, 120)
                pixmap.fill(QColor("#555555"))
            label = QLabel()
            label.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            skin_preview_layout = QVBoxLayout(skin_preview)
            skin_preview_layout.addWidget(label)
            skins_grid.addWidget(skin_preview, i//4, i%4)

        skins_scroll.setWidget(skins_container)

        # Строка с путём до папки со скинами
        skins_path_label = QLabel("Путь к папке со скинами: C:\\Path\\To\\Skins")
        skins_path_label.setStyleSheet("color: gray; font-size: 12px;")
        skins_path_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Кнопки
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        cancel_button = QPushButton("Отмена")
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Подключение кнопок к действиям
        save_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.close)

        # Добавление виджетов в общий layout
        layout.addWidget(floor_level_label)
        layout.addWidget(floor_level_spin)
        layout.addWidget(pet_size_label)
        layout.addWidget(pet_size_combo)
        layout.addLayout(skin_buttons_layout)
        layout.addWidget(skins_label)
        layout.addWidget(skins_scroll)
        layout.addWidget(skins_path_label)  # Добавлена строка с путём
        layout.addStretch()
        layout.addLayout(buttons_layout)

        return page

    def create_advanced_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Кнопка сброса настроек
        reset_button = QPushButton("Сбросить все настройки")
        reset_button.setStyleSheet("""
            QPushButton {
                background-color: #a00;
            }
            QPushButton:hover {
                background-color: #c00;
            }
            QPushButton:pressed {
                background-color: #e00;
            }
        """)

        # Кнопки
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        cancel_button = QPushButton("Отмена")
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Подключение кнопок к действиям
        save_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.close)

        # Добавление виджетов в общий layout
        layout.addWidget(reset_button)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        return page

    def create_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Информация о приложении
        info_label = QLabel("""
            <h2>Моё Приложение</h2>
            <p>Это пример приложения с окном настроек.</p>
            <p>Версия: 1.0.0</p>
        """)
        info_label.setWordWrap(True)

        # Кнопки поддержки
        support_buttons_layout = QHBoxLayout()
        support_button = QPushButton("Поддержать автора ☕")
        telegram_button = QPushButton("Telegram")
        github_button = QPushButton("GitHub")
        support_buttons_layout.addWidget(support_button)
        support_buttons_layout.addWidget(telegram_button)
        support_buttons_layout.addWidget(github_button)

        # Кнопки
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        cancel_button = QPushButton("Отмена")
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Подключение кнопок к действиям
        save_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.close)

        # Добавление виджетов в общий layout
        layout.addWidget(info_label)
        layout.addLayout(support_buttons_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        return page

    def save_settings(self):
        # Здесь должна быть логика сохранения настроек
        print("Настройки сохранены!")
        self.close()


def main():
    # Устанавливаем атрибуты до создания QApplication
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.EnableHighDpiScaling, True)
    except AttributeError:
        try:
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        except AttributeError:
            print("EnableHighDpiScaling attribute not found. Продолжаем без установки этого атрибута.")

    app = QApplication(sys.argv)

    # Применение стиля Fusion
    app.setStyle("Fusion")

    # Применение темной палитры
    dark_palette = app.palette()
    dark_palette.setColor(app.palette().ColorRole.Window, QColor("#121212"))  # Практически чёрный
    dark_palette.setColor(app.palette().ColorRole.WindowText, QColor("#ffffff"))
    dark_palette.setColor(app.palette().ColorRole.Base, QColor("#3c3c3c"))
    dark_palette.setColor(app.palette().ColorRole.AlternateBase, QColor("#2b2b2b"))
    dark_palette.setColor(app.palette().ColorRole.ToolTipBase, QColor("#ffffff"))
    dark_palette.setColor(app.palette().ColorRole.ToolTipText, QColor("#ffffff"))
    dark_palette.setColor(app.palette().ColorRole.Text, QColor("#ffffff"))
    dark_palette.setColor(app.palette().ColorRole.Button, QColor("#3c3c3c"))
    dark_palette.setColor(app.palette().ColorRole.ButtonText, QColor("#ffffff"))
    dark_palette.setColor(app.palette().ColorRole.BrightText, QColor("#ff0000"))
    dark_palette.setColor(app.palette().ColorRole.Link, QColor("#1E90FF"))
    dark_palette.setColor(app.palette().ColorRole.Highlight, QColor("#1E90FF"))
    dark_palette.setColor(app.palette().ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(dark_palette)

    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
