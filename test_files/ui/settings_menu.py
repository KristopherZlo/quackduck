import sys
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QComboBox, QFrame,
    QHBoxLayout, QVBoxLayout, QScrollArea, QGridLayout, QApplication
)
from PyQt5.QtCore import Qt

# Вспомогательный виджет – стрелка для раскрытия/сворачивания
class ExpandArrow(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.expanded = False
        self.setFixedSize(20, 20)
        self.setStyleSheet("color: #888; font-size: 16px;")
        self.setAlignment(Qt.AlignCenter)
        self.setText("▼")
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.expanded = not self.expanded
        self.setText("▲" if self.expanded else "▼")
        # При клике вызываем метод toggleExpanded() у родительского виджета, если он определён
        if hasattr(self.parent(), "toggleExpanded"):
            self.parent().toggleExpanded(self.expanded)

# Страница "Appearance"
class AppearancePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Общий фон страницы (оттенок, аналогичный контейнеру)
        self.setStyleSheet("background-color: #252525;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Заголовок страницы
        header = QLabel("Appearance")
        header.setStyleSheet("color: white; font-size: 24px;")
        main_layout.addWidget(header)
        
        # --- Карточка "Pet name" ---
        petNameCard = QFrame()
        petNameCard.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #363636;
                border-radius: 8px;
            }
        """)
        petNameLayout = QHBoxLayout(petNameCard)
        petNameLayout.setContentsMargins(15, 15, 15, 15)
        petNameLayout.setSpacing(10)
        
        # Левая часть: информационный блок (иконка, заголовок, описание)
        infoWidget = QWidget()
        infoLayout = QVBoxLayout(infoWidget)
        infoLayout.setContentsMargins(0, 0, 0, 0)
        infoLayout.setSpacing(5)
        iconLabel = QLabel("🏷")  # Иконка (можно заменить на изображение)
        iconLabel.setStyleSheet("font-size: 18px; color: white;")
        titleLabel = QLabel("Pet name")
        titleLabel.setStyleSheet("color: white; font-size: 18px;")
        descLabel = QLabel("Affects the pet's characteristics and behavior")
        descLabel.setStyleSheet("color: #888; font-size: 14px;")
        infoLayout.addWidget(iconLabel)
        infoLayout.addWidget(titleLabel)
        infoLayout.addWidget(descLabel)
        petNameLayout.addWidget(infoWidget, 1)
        
        # Правая часть: поле ввода и стрелка для разворачивания
        inputWidget = QWidget()
        inputLayout = QHBoxLayout(inputWidget)
        inputLayout.setContentsMargins(0, 0, 0, 0)
        inputLayout.setSpacing(10)
        self.petNameEdit = QLineEdit()
        self.petNameEdit.setPlaceholderText("Enter pet name")
        self.petNameEdit.setStyleSheet("""
            QLineEdit {
                background-color: #363636;
                border: none;
                padding: 8px;
                border-radius: 4px;
                color: white;
            }
        """)
        self.expandArrow = ExpandArrow(self)
        inputLayout.addWidget(self.petNameEdit)
        inputLayout.addWidget(self.expandArrow)
        petNameLayout.addWidget(inputWidget)
        
        main_layout.addWidget(petNameCard)
        
        # --- Раскрывающийся блок (expanded content) для "Pet name" ---
        self.expandedContent = QFrame()
        self.expandedContent.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #363636;
                border-radius: 8px;
                padding: 15px;
            }
            QLabel { color: #ccc; }
        """)
        expLayout = QVBoxLayout(self.expandedContent)
        expLayout.setContentsMargins(15, 15, 15, 15)
        expLayout.setSpacing(10)
        speedLabel = QLabel("Speed: 2.2 units")
        timeoutLabel = QLabel("Timeout: 2 mins.")
        expLayout.addWidget(speedLabel)
        expLayout.addWidget(timeoutLabel)
        # Блок скрыт по умолчанию
        self.expandedContent.setVisible(False)
        main_layout.addWidget(self.expandedContent)
        
        # --- Карточка "Show pet name" ---
        showNameCard = QFrame()
        showNameCard.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #363636;
                border-radius: 8px;
                padding: 15px;
            }
            QLabel { color: white; }
        """)
        showNameLayout = QHBoxLayout(showNameCard)
        showNameLayout.setContentsMargins(15, 15, 15, 15)
        showNameLayout.setSpacing(10)
        # Левая часть – информационный блок
        infoWidget2 = QWidget()
        infoLayout2 = QVBoxLayout(infoWidget2)
        infoLayout2.setContentsMargins(0, 0, 0, 0)
        infoLayout2.setSpacing(5)
        iconLabel2 = QLabel("👁")
        iconLabel2.setStyleSheet("font-size: 18px; color: white;")
        titleLabel2 = QLabel("Show name")
        titleLabel2.setStyleSheet("color: white; font-size: 18px;")
        descLabel2 = QLabel("Enable or disable the display of the name above the pet's head")
        descLabel2.setStyleSheet("color: #888; font-size: 14px;")
        infoLayout2.addWidget(iconLabel2)
        infoLayout2.addWidget(titleLabel2)
        infoLayout2.addWidget(descLabel2)
        showNameLayout.addWidget(infoWidget2, 1)
        # Правая часть – переключатель (toggle)
        toggleWidget = QWidget()
        toggleLayout = QHBoxLayout(toggleWidget)
        toggleLayout.setContentsMargins(0, 0, 0, 0)
        toggleLayout.setSpacing(10)
        self.toggleState = QLabel("on")
        self.toggleState.setStyleSheet("color: white; font-size: 16px;")
        self.toggleSwitch = QPushButton()
        self.toggleSwitch.setCheckable(True)
        self.toggleSwitch.setChecked(True)
        self.toggleSwitch.setFixedSize(44, 24)
        self.toggleSwitch.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                border-radius: 12px;
            }
            QPushButton:!checked {
                background-color: #484848;
            }
        """)
        self.toggleSwitch.clicked.connect(
            lambda: self.toggleState.setText("on" if self.toggleSwitch.isChecked() else "off")
        )
        toggleLayout.addWidget(self.toggleState)
        toggleLayout.addWidget(self.toggleSwitch)
        showNameLayout.addWidget(toggleWidget)
        main_layout.addWidget(showNameCard)
        
        # --- Карточка "Pet size" ---
        petSizeCard = QFrame()
        petSizeCard.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #363636;
                border-radius: 8px;
                padding: 15px;
            }
            QLabel { color: white; }
        """)
        petSizeLayout = QHBoxLayout(petSizeCard)
        petSizeLayout.setContentsMargins(15, 15, 15, 15)
        petSizeLayout.setSpacing(10)
        # Левая часть – информационный блок
        infoWidget3 = QWidget()
        infoLayout3 = QVBoxLayout(infoWidget3)
        infoLayout3.setContentsMargins(0, 0, 0, 0)
        infoLayout3.setSpacing(5)
        iconLabel3 = QLabel("🔍")
        iconLabel3.setStyleSheet("font-size: 18px; color: white;")
        titleLabel3 = QLabel("Pet size")
        titleLabel3.setStyleSheet("color: white; font-size: 18px;")
        descLabel3 = QLabel("The size of the pet on the screen")
        descLabel3.setStyleSheet("color: #888; font-size: 14px;")
        infoLayout3.addWidget(iconLabel3)
        infoLayout3.addWidget(titleLabel3)
        infoLayout3.addWidget(descLabel3)
        petSizeLayout.addWidget(infoWidget3, 1)
        # Правая часть – комбобокс
        sizeCombo = QComboBox()
        sizeCombo.addItems(["Small", "Medium", "Big"])
        sizeCombo.setStyleSheet("""
            QComboBox {
                background-color: #363636;
                border: none;
                padding: 8px;
                border-radius: 4px;
                color: white;
            }
        """)
        petSizeLayout.addWidget(sizeCombo)
        main_layout.addWidget(petSizeCard)
        
        # --- Карточка "Skins folder path..." ---
        folderCard = QFrame()
        folderCard.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #363636;
                border-radius: 8px;
                padding: 15px;
            }
            QLabel { color: white; }
        """)
        folderLayout = QHBoxLayout(folderCard)
        folderLayout.setContentsMargins(15, 15, 15, 15)
        folderLayout.setSpacing(10)
        # Левая часть – информационный блок
        infoWidget4 = QWidget()
        infoLayout4 = QVBoxLayout(infoWidget4)
        infoLayout4.setContentsMargins(0, 0, 0, 0)
        infoLayout4.setSpacing(5)
        iconLabel4 = QLabel("📁")
        iconLabel4.setStyleSheet("font-size: 18px; color: white;")
        titleLabel4 = QLabel("Skins folder path...")
        titleLabel4.setStyleSheet("color: white; font-size: 18px;")
        descLabel4 = QLabel("Specify the folder containing additional skins, if you have any")
        descLabel4.setStyleSheet("color: #888; font-size: 14px;")
        infoLayout4.addWidget(iconLabel4)
        infoLayout4.addWidget(titleLabel4)
        infoLayout4.addWidget(descLabel4)
        folderLayout.addWidget(infoWidget4, 1)
        # Правая часть – поле ввода и кнопка выбора
        folderSelectWidget = QWidget()
        folderSelectLayout = QHBoxLayout(folderSelectWidget)
        folderSelectLayout.setContentsMargins(0, 0, 0, 0)
        folderSelectLayout.setSpacing(10)
        self.folderLine = QLineEdit()
        self.folderLine.setPlaceholderText("path/to/your/skins...")
        self.folderLine.setReadOnly(True)
        self.folderLine.setStyleSheet("""
            QLineEdit {
                background-color: #363636;
                border: none;
                padding: 8px;
                border-radius: 4px;
                color: white;
            }
        """)
        folderButton = QPushButton("Select")
        folderButton.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
        """)
        folderSelectLayout.addWidget(self.folderLine)
        folderSelectLayout.addWidget(folderButton)
        folderLayout.addWidget(folderSelectWidget)
        main_layout.addWidget(folderCard)
        
        # --- Блок предпросмотра скинов ---
        previewLabel = QLabel("Skin previews:")
        previewLabel.setStyleSheet("color: white; font-size: 18px;")
        main_layout.addWidget(previewLabel)
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setStyleSheet("background-color: #363636; border: none;")
        skinContainer = QWidget()
        gridLayout = QGridLayout(skinContainer)
        gridLayout.setSpacing(10)
        num_skins = 10
        for i in range(num_skins):
            skinCard = QFrame()
            skinCard.setFixedSize(120, 120)
            skinCard.setStyleSheet("""
                QFrame {
                    background-color: #363636;
                    border: 1px solid #494949;
                    border-radius: 4px;
                }
                QFrame:hover {
                    border: 1px solid #ffffff;
                }
            """)
            gridLayout.addWidget(skinCard, i // 5, i % 5)
        scrollArea.setWidget(skinContainer)
        main_layout.addWidget(scrollArea)
        
        main_layout.addStretch()
    
    # Метод для переключения видимости раскрывающегося блока
    def toggleExpanded(self, expand):
        self.expandedContent.setVisible(expand)

# Тестовый запуск страницы Appearance как отдельного окна
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppearancePage()
    window.resize(800, 1000)
    window.show()
    sys.exit(app.exec_())
