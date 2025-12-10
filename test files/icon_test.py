import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QIcon
import ctypes

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Иконка панели задач')

        self.setWindowIcon(QIcon('assets/images/white-quackduck-visible.ico'))

        self.setGeometry(100, 100, 600, 400)

if __name__ == '__main__':
    app = QApplication(sys.argv)

    myappid = 'mycompany.myproduct.subproduct.version'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app.setWindowIcon(QIcon('assets/images/white-quackduck-visible.ico'))

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())
