import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QStackedWidget, QLineEdit, QComboBox, QCheckBox, QSlider, QProgressBar, QScrollArea,
    QFrame, QFileDialog, QSpinBox
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QIcon
from PyQt5.QtMultimedia import QSoundEffect


class SidebarButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setCheckable(True)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 16px;
                border: none;
                font-size: 14px;
                color: #ccc;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:checked {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border-left: 4px solid #8c5aff;
                padding-left: 12px;
            }
        """)


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Settings")
        self.setWindowIcon(QIcon("assets/images/settings.ico"))
        self.resize(1000, 600)

        container = QWidget()
        self.setCentralWidget(container)

        # Main layout no margins/spaces
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QVBoxLayout()
        self.sidebar.setContentsMargins(0, 0, 0, 10)  # 10px from bottom for version label
        self.sidebar.setSpacing(0)

        # App Title (no duck icon)
        self.app_title = QHBoxLayout()
        self.app_title.setContentsMargins(20, 20, 20, 20)
        self.app_title.setSpacing(10)

        self.app_label = QLabel("Settings")
        self.app_label.setStyleSheet("font-weight:600;font-size:16px;color:#fff;")

        self.app_title.addWidget(self.app_label)
        self.app_title.addStretch()

        self.sidebar.addLayout(self.app_title)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color:#3a3a3a;")
        self.sidebar.addWidget(line)

        # Nav buttons with emojis in front
        self.btn_general = SidebarButton("⚙️ General")
        self.btn_appearance = SidebarButton("🎨 Appearance")
        self.btn_advanced = SidebarButton("🛠️ Advanced")
        self.btn_about = SidebarButton("❓ About")

        self.btn_general.setChecked(True)
        for btn in [self.btn_general, self.btn_appearance, self.btn_advanced, self.btn_about]:
            btn.clicked.connect(self.change_tab)
            self.sidebar.addWidget(btn)

        self.sidebar.addStretch()

        # Version label 10px above bottom (we did this with margins)
        version_label = QLabel("v1.5.0")
        version_label.setStyleSheet("color:#aaa;font-size:12px;")
        version_label.setAlignment(Qt.AlignCenter)
        self.sidebar.addWidget(version_label)

        # Stacked widget for tabs
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QWidget { color: #ccc; background: #1e1e1e; }")

        # Create tabs
        self.stack.addWidget(self.general_tab())
        self.stack.addWidget(self.appearance_tab())
        self.stack.addWidget(self.advanced_tab())
        self.stack.addWidget(self.about_tab())

        main_layout.addWidget(self.sidebar_container())
        main_layout.addWidget(self.stack, 1)

        self.apply_stylesheet()

    def sidebar_container(self):
        w = QWidget()
        w.setLayout(self.sidebar)
        w.setFixedWidth(220)
        w.setStyleSheet("background-color:#2a2a2a;")
        return w

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #1e1e1e;
            }
            QCheckBox, QRadioButton, QLabel, QComboBox, QSpinBox, QLineEdit {
                font-size:14px;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #2f2f2f;
                border:1px solid #444;
                border-radius:4px;
                padding:4px;
                color:#ccc;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border:1px solid #8c5aff;
                outline: none;
            }
            QPushButton {
                background:#8c5aff;
                color:#fff;
                border:none;
                border-radius:4px;
                padding:8px 14px;
                font-size:14px;
            }
            QPushButton:hover {
                background:#a978ff;
            }
            QSlider::groove:horizontal {
                background:#444;
                height:6px;
                border-radius:3px;
            }
            QSlider::handle:horizontal {
                background:#8c5aff;
                width:14px;
                height:14px;
                margin:-4px 0;
                border-radius:7px;
            }
            QSlider::sub-page:horizontal {
                background:#8c5aff;
                border-radius:3px;
            }
            QProgressBar {
                background:#444;
                border-radius:4px;
                height:8px;
            }
            QProgressBar::chunk {
                background:#8c5aff;
            }
            QScrollBar:vertical {
                background:#2f2f2f; width:8px;
            }
            QScrollBar::handle:vertical {
                background:#8c5aff; border-radius:4px; min-height:20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height:0; background:none;
            }
        """)

    def change_tab(self):
        sender = self.sender()
        if sender == self.btn_general:
            self.btn_general.setChecked(True)
            self.btn_appearance.setChecked(False)
            self.btn_advanced.setChecked(False)
            self.btn_about.setChecked(False)
            self.stack.setCurrentIndex(0)
        elif sender == self.btn_appearance:
            self.btn_general.setChecked(False)
            self.btn_appearance.setChecked(True)
            self.btn_advanced.setChecked(False)
            self.btn_about.setChecked(False)
            self.stack.setCurrentIndex(1)
        elif sender == self.btn_advanced:
            self.btn_general.setChecked(False)
            self.btn_appearance.setChecked(False)
            self.btn_advanced.setChecked(True)
            self.btn_about.setChecked(False)
            self.stack.setCurrentIndex(2)
        elif sender == self.btn_about:
            self.btn_general.setChecked(False)
            self.btn_appearance.setChecked(False)
            self.btn_advanced.setChecked(False)
            self.btn_about.setChecked(True)
            self.stack.setCurrentIndex(3)

    def general_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(20)

        title = QLabel("General Settings")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:10px;")
        layout.addWidget(title)

        # Pet Name
        pet_name_box = QVBoxLayout()
        lbl_petname = QLabel("Pet Name:")
        self.petName = QLineEdit()
        self.petName.setPlaceholderText("e.g. Fluffy")
        pet_name_box.addWidget(lbl_petname)
        pet_name_box.addWidget(self.petName)
        layout.addLayout(pet_name_box)

        # Input Device
        mic_box = QVBoxLayout()
        lbl_mic = QLabel("Input Device:")
        self.micDevice = QComboBox()
        self.micDevice.addItems(["Microphone (Default)", "External Mic", "Virtual Input"])
        mic_box.addWidget(lbl_mic)
        mic_box.addWidget(self.micDevice)
        layout.addLayout(mic_box)

        # Activation Threshold
        lbl_thresh = QLabel("Activation Threshold:")
        self.thresholdValue = QLabel("10%")
        self.thresholdSlider = QSlider(Qt.Horizontal)
        self.thresholdSlider.setRange(0,100)
        self.thresholdSlider.setValue(10)
        def update_thresh(v):
            self.thresholdValue.setText(f"{v}%")
        self.thresholdSlider.valueChanged.connect(update_thresh)

        thresh_layout = QVBoxLayout()
        thresh_layout.addWidget(lbl_thresh)
        h_thresh = QHBoxLayout()
        h_thresh.addWidget(self.thresholdValue)
        h_thresh.addWidget(self.thresholdSlider)
        thresh_layout.addLayout(h_thresh)
        layout.addLayout(thresh_layout)

        # Enable Sound Checkbox
        cb_layout = QVBoxLayout()
        self.enableSound = QCheckBox("Enable Sound")
        self.enableSound.setChecked(True)
        self.enableSound.stateChanged.connect(self.toggle_volume_slider)
        cb_layout.addWidget(self.enableSound)

        # Volume Slider (like threshold)
        lbl_volume = QLabel("Volume:")
        self.volumeValue = QLabel("50%")
        self.volumeSlider = QSlider(Qt.Horizontal)
        self.volumeSlider.setRange(0,100)
        self.volumeSlider.setValue(50)

        def update_volume(v):
            self.volumeValue.setText(f"{v}%")
        self.volumeSlider.valueChanged.connect(update_volume)

        # Play sound on release
        self.soundEffect = QSoundEffect()
        self.soundEffect.setSource(QUrl.fromLocalFile("assets/skins/default/wuak.wav"))
        self.volumeSlider.sliderReleased.connect(self.play_quack_sound)

        vol_layout = QVBoxLayout()
        vol_layout.addWidget(lbl_volume)
        h_vol = QHBoxLayout()
        h_vol.addWidget(self.volumeValue)
        h_vol.addWidget(self.volumeSlider)
        vol_layout.addLayout(h_vol)
        cb_layout.addLayout(vol_layout)

        self.showName = QCheckBox("Show Pet's Name Above the Duck")
        cb_layout.addWidget(self.showName)
        layout.addLayout(cb_layout)

        layout.addStretch()

        # Actions at bottom right
        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background:#444;")
        save_btn = QPushButton("Save")
        # Save should be purple by default from global QSS
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        layout.addLayout(act_box)

        return w

    def toggle_volume_slider(self):
        enabled = self.enableSound.isChecked()
        # Show/hide volume controls
        # volume controls: lbl_volume, volumeValue, volumeSlider
        # We stored lbl_volume as a local var. Let's store them as class attributes for toggling visibility.
        # We'll store references on creation so we can toggle:
        # Already done above? We used local vars. Let's fix that:
        # We'll keep references as self.volumeLabel, etc.

        # Adjusting code: Move lbl_volume out to class scope (done in code rewriting):
        # Actually, we already created them inside general_tab. Let's store references:
        # We'll do it after we create them in general_tab:
        # They are local currently. Let's fix that by making them class attributes.
        # We'll set them after creation:
        # self.volumeSlider, self.volumeValue and lbl_volume were created as locals. We'll store lbl_volume as class variable by creating it before usage.

        # Let's do that: We'll define lbl_volume as self.volumeLabel in general_tab. Modify code above:
        # Replacing "lbl_volume = QLabel("Volume:")" with "self.volumeLabel = QLabel("Volume:")"
        # We'll do similar for about tab steps.

    def appearance_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(20)

        title = QLabel("Appearance")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:10px;")
        layout.addWidget(title)

        # Pet Size
        size_box = QVBoxLayout()
        lbl_size = QLabel("Pet Size:")
        self.petSize = QComboBox()
        self.petSize.addItems(["x1","x2","x3","x5","x10"])
        size_box.addWidget(lbl_size)
        size_box.addWidget(self.petSize)
        layout.addLayout(size_box)

        # Skins Folder
        folder_box = QVBoxLayout()
        lbl_folder = QLabel("Skins Folder:")
        f_hbox = QHBoxLayout()
        self.folderPath = QLineEdit()
        self.folderPath.setPlaceholderText("No folder selected...")
        self.folderPath.setReadOnly(True)
        choose_btn = QPushButton("Browse...")
        choose_btn.setStyleSheet("background:#8c5aff;")
        def choose_folder():
            folder = QFileDialog.getExistingDirectory(self, "Select Skins Folder")
            if folder:
                self.folderPath.setText(folder)
        choose_btn.clicked.connect(choose_folder)
        f_hbox.addWidget(self.folderPath)
        f_hbox.addWidget(choose_btn)
        folder_box.addWidget(lbl_folder)
        folder_box.addLayout(f_hbox)
        layout.addLayout(folder_box)

        lbl_skins = QLabel("Skins Preview")
        lbl_skins.setStyleSheet("font-size:16px;color:#ddd;")
        layout.addWidget(lbl_skins)

        scroll = QScrollArea()
        scroll.setStyleSheet("border:none;")
        scroll.setWidgetResizable(True)
        skin_container = QWidget()
        skin_layout = QHBoxLayout(skin_container)
        skin_layout.setSpacing(20)

        for name in ["Default Duck","Night Duck","Retro Duck"]:
            skin_item = self.create_skin_item(name)
            skin_layout.addWidget(skin_item)

        scroll.setWidget(skin_container)
        layout.addWidget(scroll)

        layout.addStretch()
        # Actions at bottom right
        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background:#444;")
        save_btn = QPushButton("Save")
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        layout.addLayout(act_box)

        return w

    def create_skin_item(self, name):
        item = QFrame()
        item.setStyleSheet("background:#2f2f2f;border-radius:4px;padding:10px;")
        item_layout = QVBoxLayout(item)
        item_layout.setContentsMargins(10,10,10,10)
        img_lbl = QLabel()
        img_lbl.setFixedSize(64,64)
        img_lbl.setStyleSheet("background:#444;border-radius:4px;")
        img_lbl.setAlignment(Qt.AlignCenter)
        skin_name = QLabel(name)
        skin_name.setStyleSheet("font-size:12px;color:#ccc;text-align:center;")
        skin_name.setAlignment(Qt.AlignCenter)
        item_layout.addWidget(img_lbl, alignment=Qt.AlignCenter)
        item_layout.addSpacing(10)
        item_layout.addWidget(skin_name)
        return item

    def advanced_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(20)

        title = QLabel("Advanced Settings")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:10px;")
        layout.addWidget(title)

        # Floor Level
        floor_box = QVBoxLayout()
        lbl_floor = QLabel("Floor Level (pixels):")
        self.floorLevel = QSpinBox()
        self.floorLevel.setRange(0,1000)
        self.floorLevel.setValue(0)
        floor_box.addWidget(lbl_floor)
        floor_box.addWidget(self.floorLevel)
        layout.addLayout(floor_box)

        # Name Offset
        offset_box = QVBoxLayout()
        lbl_offset = QLabel("Name Offset Y (pixels):")
        self.nameOffset = QSpinBox()
        self.nameOffset.setRange(-1000,1000)
        self.nameOffset.setValue(0)
        offset_box.addWidget(lbl_offset)
        offset_box.addWidget(self.nameOffset)
        layout.addLayout(offset_box)

        # Base Font Size
        font_box = QVBoxLayout()
        lbl_font = QLabel("Base Font Size:")
        self.fontBaseSize = QSpinBox()
        self.fontBaseSize.setRange(6,50)
        self.fontBaseSize.setValue(14)
        font_box.addWidget(lbl_font)
        font_box.addWidget(self.fontBaseSize)
        layout.addLayout(font_box)

        # Language
        lang_box = QVBoxLayout()
        lbl_lang = QLabel("Language:")
        self.language = QComboBox()
        self.language.addItems(["English","Russian"])
        lang_box.addWidget(lbl_lang)
        lang_box.addWidget(self.language)
        layout.addLayout(lang_box)

        # Autostart
        auto_box = QHBoxLayout()
        self.autostart = QCheckBox("Run at System Startup")
        self.autostart.setChecked(True)
        auto_box.addWidget(self.autostart)
        auto_box.addStretch()
        layout.addLayout(auto_box)

        reset_btn = QPushButton("Reset All Settings")
        reset_btn.setStyleSheet("background:#a00;color:#fff;")
        layout.addWidget(reset_btn)

        layout.addStretch()

        # Actions at bottom right
        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background:#444;")
        save_btn = QPushButton("Save")
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        layout.addLayout(act_box)

        return w

    def about_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(20)

        title = QLabel("About QuackDuck")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:10px;")
        layout.addWidget(title)

        p1 = QLabel("QuackDuck is a commercial virtual pet application.\nAll rights reserved.\n\nVersion: 1.5.0\nDeveloped by zl0yxp")
        p1.setStyleSheet("font-size:14px;color:#ccc;")
        p1.setAlignment(Qt.AlignTop)
        layout.addWidget(p1)

        h2 = QLabel("Support")
        h2.setStyleSheet("font-size:16px;color:#ddd;")
        layout.addWidget(h2)
        p2 = QLabel("For suggestions or questions, use Issues on GitHub or our contact form.")
        p2.setStyleSheet("font-size:14px;color:#ccc;")
        p2.setAlignment(Qt.AlignTop)
        layout.addWidget(p2)

        layout.addStretch()
        # Actions at bottom right
        act_box = QHBoxLayout()
        act_box.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background:#444;")
        close_btn.clicked.connect(lambda: print("Close about (demo)"))
        act_box.addWidget(close_btn)
        layout.addLayout(act_box)

        return w

    def play_quack_sound(self):
        # Play sound effect when volume slider released
        self.soundEffect.play()

    def toggle_volume_slider(self):
        enabled = self.enableSound.isChecked()
        # Find volume widgets and hide/show them
        # They are in general_tab. We'll store them as class attributes in general_tab creation:
        # We must update general_tab code to store self.volumeLabel, etc. as attributes.
        # Let's do that now: Replace local variables in general_tab volume section with self.volumeLabel, etc.

    # We'll redefine general_tab now with class attributes for volume controls:
    def general_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(20)

        title = QLabel("General Settings")
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:10px;")
        layout.addWidget(title)

        # Pet Name
        pet_name_box = QVBoxLayout()
        lbl_petname = QLabel("Pet Name:")
        self.petName = QLineEdit()
        self.petName.setPlaceholderText("e.g. Fluffy")
        pet_name_box.addWidget(lbl_petname)
        pet_name_box.addWidget(self.petName)
        layout.addLayout(pet_name_box)

        # Input Device
        mic_box = QVBoxLayout()
        lbl_mic = QLabel("Input Device:")
        self.micDevice = QComboBox()
        self.micDevice.addItems(["Microphone (Default)", "External Mic", "Virtual Input"])
        mic_box.addWidget(lbl_mic)
        mic_box.addWidget(self.micDevice)
        layout.addLayout(mic_box)

        # Activation Threshold
        lbl_thresh = QLabel("Activation Threshold:")
        self.thresholdValue = QLabel("10%")
        self.thresholdSlider = QSlider(Qt.Horizontal)
        self.thresholdSlider.setRange(0,100)
        self.thresholdSlider.setValue(10)
        def update_thresh(v):
            self.thresholdValue.setText(f"{v}%")
        self.thresholdSlider.valueChanged.connect(update_thresh)

        thresh_layout = QVBoxLayout()
        thresh_layout.addWidget(lbl_thresh)
        h_thresh = QHBoxLayout()
        h_thresh.addWidget(self.thresholdValue)
        h_thresh.addWidget(self.thresholdSlider)
        thresh_layout.addLayout(h_thresh)
        layout.addLayout(thresh_layout)

        # Enable Sound Checkbox
        cb_layout = QVBoxLayout()
        self.enableSound = QCheckBox("Enable Sound")
        self.enableSound.setChecked(True)
        self.enableSound.stateChanged.connect(self.toggle_volume_slider)
        cb_layout.addWidget(self.enableSound)

        # Volume Slider (like threshold)
        self.volumeLabel = QLabel("Volume:")
        self.volumeValue = QLabel("50%")
        self.volumeSlider = QSlider(Qt.Horizontal)
        self.volumeSlider.setRange(0,100)
        self.volumeSlider.setValue(50)

        def update_volume(v):
            self.volumeValue.setText(f"{v}%")
        self.volumeSlider.valueChanged.connect(update_volume)

        self.soundEffect = QSoundEffect()
        self.soundEffect.setSource(QUrl.fromLocalFile("assets/skins/default/wuak.wav"))
        self.volumeSlider.sliderReleased.connect(self.play_quack_sound)

        vol_layout = QVBoxLayout()
        vol_layout.addWidget(self.volumeLabel)
        h_vol = QHBoxLayout()
        h_vol.addWidget(self.volumeValue)
        h_vol.addWidget(self.volumeSlider)
        vol_layout.addLayout(h_vol)
        cb_layout.addLayout(vol_layout)

        self.showName = QCheckBox("Show Pet's Name Above the Duck")
        cb_layout.addWidget(self.showName)
        layout.addLayout(cb_layout)

        layout.addStretch()

        # Actions at bottom right
        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background:#444;")
        save_btn = QPushButton("Save")
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        layout.addLayout(act_box)

        return w

    def toggle_volume_slider(self):
        enabled = self.enableSound.isChecked()
        self.volumeLabel.setVisible(enabled)
        self.volumeValue.setVisible(enabled)
        self.volumeSlider.setVisible(enabled)


if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec_())
