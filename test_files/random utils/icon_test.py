import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QIcon
import ctypes  # Для работы с иконкой на панели задач (Windows)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Установка заголовка окна
        self.setWindowTitle('Иконка панели задач')

        # Установка иконки
        self.setWindowIcon(QIcon('assets/images/white-quackduck-visible.ico'))  # Используйте формат .ico для Windows

        # Размер и позиция окна
        self.setGeometry(100, 100, 600, 400)

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Установка иконки приложения для панели задач (Windows)
    myappid = 'mycompany.myproduct.subproduct.version'  # Произвольное имя приложения
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # Установка глобальной иконки для приложения
    app.setWindowIcon(QIcon('assets/images/white-quackduck-visible.ico'))

    # Создание и отображение главного окна
    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())
