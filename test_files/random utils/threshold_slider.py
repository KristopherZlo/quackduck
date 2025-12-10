import sys
import platform
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSlider,
)
from PyQt5.QtCore import Qt, QTimer

# Проверка операционной системы
current_os = platform.system()

if current_os == "Windows":
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
else:
    raise NotImplementedError(f"Операционная система {current_os} не поддерживается этим скриптом.")


class VolumeController:
    def __init__(self):
        if current_os == "Windows":
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            self.volume = cast(interface, POINTER(IAudioEndpointVolume))

    def get_volume(self):
        if current_os == "Windows":
            # Получение громкости в диапазоне 0 - 100
            return int(self.volume.GetMasterVolumeLevelScalar() * 100)
        return 0


class DarkWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мониторинг громкости")
        self.setGeometry(100, 100, 400, 100)  # Размер окна: ширина=400, высота=100

        # Инициализация контроллера громкости
        self.volume_controller = VolumeController()

        # Установка центрального виджета
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Создание вертикального компоновщика
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Создание слайдера
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, 100)
        self.slider.setValue(self.volume_controller.get_volume())
        self.slider.setTickPosition(QSlider.NoTicks)
        self.slider.setEnabled(False)  # Отключаем возможность изменения пользователем
        self.slider.setFixedHeight(30)  # Устанавливаем высоту для видимости ручки
        main_layout.addWidget(self.slider)

        # Применение тёмной темы и настройки стилей
        self.apply_dark_theme()

        # Установка таймера для обновления громкости
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_volume)
        self.timer.start(1)  # Обновление каждые 1 мс

    def update_volume(self):
        current_volume = self.volume_controller.get_volume()
        self.slider.setValue(current_volume)

    def apply_dark_theme(self):
        dark_stylesheet = """
            QWidget {
                background-color: #2b2b2b;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 1px;
                background: #444444;
                margin: 0px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: none;
                width: 10px;
                height: 10px;
                margin: -4px 0; /* Центрируем ручку по вертикали */
                border-radius: 5px;
            }
            QSlider::handle:horizontal:hover {
                background: #dddddd;
            }
        """
        self.setStyleSheet(dark_stylesheet)


def main():
    app = QApplication(sys.argv)
    window = DarkWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
