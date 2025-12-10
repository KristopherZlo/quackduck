import base64
import logging
import os
import random
import time
import webbrowser
from typing import List

import requests
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QBuffer, QIODevice, QPoint, QRect, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QCursor, QDesktopServices, QIcon, QMovie, QPixmap, QTransform
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QSpacerItem,
    QDoubleSpinBox,
)

from .core import GLOBAL_DEBUG_MODE, PROJECT_VERSION, get_system_accent_color, resource_path
from .i18n import translations
from .states import (
    AttackState,
    DraggingState,
    FallingState,
    IdleState,
    JumpingState,
    LandingState,
    ListeningState,
    PlayfulState,
    RunState,
    SleepingState,
    WalkingState,
)

# UI components and auxiliary windows for QuackDuck.


class DebugWindow(QtWidgets.QWidget):
    """
    Debugging helper window that exposes live duck state and controls.
    """

    def __init__(self, duck):
        super().__init__()
        self.duck = duck
        self.setWindowTitle("QuackDuck Ultimate Debug Mode")
        self.setGeometry(100, 100, 1200, 800)
        self.init_ui()
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_debug_info)
        self.update_timer.start(1000)

    def init_ui(self):
        self.setStyleSheet(
            """
        QWidget {
            background-color: #2a2a2a;
            color: #ccc;
            font-size: 14px;
        }
        QGroupBox {
            border: 1px solid #444;
            margin-top: 20px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 5px;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QPushButton {
            background-color: #3a3a3a;
            border: 1px solid #555;
            border-radius:3px;
            padding:4px;
            color:#ccc;
        }
        QScrollArea, QTextEdit, QListWidget {
            background-color: #1e1e1e;
            border:1px solid #444;
            color:#ccc;
        }
        QTabWidget::pane {
            border: 1px solid #444;
        }
        QTabBar::tab {
            background: #3a3a3a;
            padding:5px;
        }
        QTabBar::tab:selected {
            background: #444;
        }
        """
        )

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.params_widget = QWidget()
        self.params_layout = QVBoxLayout(self.params_widget)

        general_group = QGroupBox("General Settings (No Limits)")
        general_form = QFormLayout()

        self.petNameEdit = QLineEdit(self.duck.pet_name)
        self.petNameEdit.editingFinished.connect(self.update_pet_name)
        general_form.addRow("Pet Name:", self.petNameEdit)

        self.petSizeSpin = QSpinBox()
        self.petSizeSpin.setRange(-1000, 1000)
        self.petSizeSpin.setValue(self.duck.pet_size)
        self.petSizeSpin.valueChanged.connect(self.update_pet_size_spin)
        general_form.addRow("Pet Size:", self.petSizeSpin)

        self.activationSpin = QSpinBox()
        self.activationSpin.setRange(0, 9999)
        self.activationSpin.setValue(self.duck.activation_threshold)
        self.activationSpin.valueChanged.connect(self.update_activation_threshold)
        general_form.addRow("Activation Threshold:", self.activationSpin)

        self.sleepTimeoutSpin = QSpinBox()
        self.sleepTimeoutSpin.setRange(0, 999999)
        self.sleepTimeoutSpin.setValue(int(self.duck.sleep_timeout))
        self.sleepTimeoutSpin.valueChanged.connect(self.update_sleep_timeout)
        general_form.addRow("Sleep Timeout (sec):", self.sleepTimeoutSpin)

        self.idleDurationSpin = QDoubleSpinBox()
        self.idleDurationSpin.setRange(0.0, 999999.0)
        self.idleDurationSpin.setValue(self.duck.idle_duration)
        self.idleDurationSpin.setSuffix(" sec")
        self.idleDurationSpin.valueChanged.connect(self.update_idle_duration)
        general_form.addRow("Idle Duration:", self.idleDurationSpin)

        self.soundCheck = QCheckBox("Sound Enabled")
        self.soundCheck.setChecked(self.duck.sound_enabled)
        self.soundCheck.stateChanged.connect(self.update_sound_enabled)
        general_form.addRow(self.soundCheck)

        self.showNameCheck = QCheckBox("Show Name Above Duck")
        self.showNameCheck.setChecked(self.duck.show_name)
        self.showNameCheck.stateChanged.connect(self.update_show_name)
        general_form.addRow(self.showNameCheck)

        self.groundLevelSpin = QSpinBox()
        self.groundLevelSpin.setRange(-999999, 999999)
        self.groundLevelSpin.setValue(self.duck.ground_level_setting)
        self.groundLevelSpin.valueChanged.connect(self.update_ground_level)
        general_form.addRow("Ground Level (px):", self.groundLevelSpin)

        self.directionIntervalSpin = QDoubleSpinBox()
        self.directionIntervalSpin.setRange(0, 999999)
        self.directionIntervalSpin.setValue(float(self.duck.direction_change_interval))
        self.directionIntervalSpin.valueChanged.connect(self.update_direction_interval)
        general_form.addRow("Direction Change Interval (sec):", self.directionIntervalSpin)

        self.fontBaseSizeSpin = QSpinBox()
        self.fontBaseSizeSpin.setRange(1, 9999)
        self.fontBaseSizeSpin.setValue(self.duck.font_base_size)
        self.fontBaseSizeSpin.valueChanged.connect(self.update_font_base_size)
        general_form.addRow("Font Base Size:", self.fontBaseSizeSpin)

        self.autostartCheck = QCheckBox("Run at system startup")
        self.autostartCheck.setChecked(self.duck.autostart_enabled)
        self.autostartCheck.stateChanged.connect(self.update_autostart)
        general_form.addRow(self.autostartCheck)

        self.languageEdit = QLineEdit(self.duck.current_language)
        self.languageEdit.editingFinished.connect(self.update_language_line)
        general_form.addRow("Language (string):", self.languageEdit)

        self.nameOffsetSpin = QSpinBox()
        self.nameOffsetSpin.setRange(-999999, 999999)
        self.nameOffsetSpin.setValue(self.duck.name_offset_y)
        self.nameOffsetSpin.valueChanged.connect(self.update_name_offset)
        general_form.addRow("Name Offset Y:", self.nameOffsetSpin)

        self.soundIntervalMinSpin = QDoubleSpinBox()
        self.soundIntervalMinSpin.setRange(0, 999999)
        self.soundIntervalMinSpin.setValue(getattr(self.duck, "sound_interval_min", 60.0))
        self.soundIntervalMinSpin.valueChanged.connect(self.update_sound_interval_min)
        general_form.addRow("Sound Interval Min (sec):", self.soundIntervalMinSpin)

        self.soundIntervalMaxSpin = QDoubleSpinBox()
        self.soundIntervalMaxSpin.setRange(0, 999999)
        self.soundIntervalMaxSpin.setValue(getattr(self.duck, "sound_interval_max", 600.0))
        self.soundIntervalMaxSpin.valueChanged.connect(self.update_sound_interval_max)
        general_form.addRow("Sound Interval Max (sec):", self.soundIntervalMaxSpin)

        self.playfulProbSpin = QDoubleSpinBox()
        self.playfulProbSpin.setRange(0.0, 1.0)
        self.playfulProbSpin.setDecimals(4)
        self.playfulProbSpin.setValue(self.duck.playful_behavior_probability)
        self.playfulProbSpin.valueChanged.connect(self.update_playful_probability)
        general_form.addRow("Playful Behavior Probability:", self.playfulProbSpin)

        general_group.setLayout(general_form)
        self.params_layout.addWidget(general_group)

        extra_group = QGroupBox("Extra Controls")
        extra_layout = QHBoxLayout()

        double_click_btn = QPushButton("Trigger Double Click")
        double_click_btn.clicked.connect(self.trigger_double_click)
        extra_layout.addWidget(double_click_btn)

        play_sound_btn = QPushButton("Play Random Sound")
        play_sound_btn.clicked.connect(self.duck.play_random_sound)
        extra_layout.addWidget(play_sound_btn)

        open_settings_btn = QPushButton("Open Settings Window")
        open_settings_btn.clicked.connect(self.duck.open_settings)
        extra_layout.addWidget(open_settings_btn)

        self.methodEdit = QLineEdit()
        self.methodEdit.setPlaceholderText("Enter method name with no args, e.g. 'unstuck_duck'")
        call_method_btn = QPushButton("Call Method")
        call_method_btn.clicked.connect(self.call_method_by_name)
        extra_layout.addWidget(self.methodEdit)
        extra_layout.addWidget(call_method_btn)

        extra_group.setLayout(extra_layout)
        self.params_layout.addWidget(extra_group)

        self.params_layout.addStretch()
        self.tabs.addTab(self.params_widget, "Parameters & Extra")

        self.logs_states_widget = QWidget()
        logs_states_layout = QVBoxLayout(self.logs_states_widget)

        state_history_group = QGroupBox("Last 100 States + State Control")
        state_history_vlayout = QVBoxLayout()

        state_control_layout = QHBoxLayout()
        self.add_state_button(state_control_layout, "Idle", IdleState)
        self.add_state_button(state_control_layout, "Walk", WalkingState)
        self.add_state_button(state_control_layout, "Sleep", SleepingState)
        self.add_state_button(state_control_layout, "Jump", JumpingState)
        self.add_state_button(state_control_layout, "Fall", FallingState)
        self.add_state_button(state_control_layout, "Drag", DraggingState)
        self.add_state_button(state_control_layout, "Listen", ListeningState)
        self.add_state_button(state_control_layout, "Playful", PlayfulState)
        self.add_state_button(state_control_layout, "Run", RunState)
        self.add_state_button(state_control_layout, "Attack", AttackState)
        self.add_state_button(state_control_layout, "Land", LandingState)
        state_history_vlayout.addLayout(state_control_layout)

        self.state_history_list = QListWidget()
        state_history_vlayout.addWidget(self.state_history_list)

        state_history_group.setLayout(state_history_vlayout)
        logs_states_layout.addWidget(state_history_group)

        logs_states_layout.addStretch()
        self.tabs.addTab(self.logs_states_widget, "Logs & States")

    def add_state_button(self, layout, name, state_class):
        btn = QPushButton(name)
        btn.clicked.connect(lambda: self.duck.change_state(state_class(self.duck)))
        layout.addWidget(btn)

    def update_debug_info(self):
        """Refresh debug info but keep errors from crashing the window."""
        try:
            self.state_history_list.clear()
            history_slice = self.duck.state_history[-100:]
            for timestamp, old_st, new_st in history_slice:
                self.state_history_list.addItem(f"{timestamp}: {old_st} -> {new_st}")
        except Exception as exc:
            logging.error("Debug window update failed: %s", exc)

    def trigger_double_click(self):
        try:
            event = QtGui.QMouseEvent(
                QtCore.QEvent.Type.MouseButtonDblClick,
                QtCore.QPointF(self.duck.duck_x, self.duck.duck_y),
                QtCore.Qt.MouseButton.LeftButton,
                QtCore.Qt.MouseButton.LeftButton,
                QtCore.Qt.NoModifier,
            )
            self.duck.mouseDoubleClickEvent(event)
        except Exception as exc:
            logging.error("Failed to simulate double click: %s", exc)

    def call_method_by_name(self):
        method_name = self.methodEdit.text().strip()
        if not method_name:
            QtWidgets.QMessageBox.warning(self, "Method not found", "No method name provided.")
            return

        if not hasattr(self.duck, method_name):
            QtWidgets.QMessageBox.warning(self, "Method not found", f"No method {method_name} found on duck.")
            return

        method = getattr(self.duck, method_name)
        if not callable(method):
            QtWidgets.QMessageBox.warning(self, "Not callable", f"{method_name} is not callable.")
            return

        try:
            method()
        except Exception as exc:
            logging.error("Error calling %s: %s", method_name, exc)
            QtWidgets.QMessageBox.warning(self, "Error calling method", str(exc))

    def update_pet_name(self):
        self.duck.pet_name = self.petNameEdit.text().strip()
        self.duck.apply_settings()

    def update_pet_size_spin(self, value):
        self.duck.update_pet_size(value)
        self.duck.apply_settings()

    def update_activation_threshold(self, value):
        self.duck.activation_threshold = value
        self.duck.apply_settings()

    def update_sleep_timeout(self, value):
        self.duck.sleep_timeout = value
        self.duck.apply_settings()

    def update_idle_duration(self, value):
        self.duck.idle_duration = value
        self.duck.apply_settings()

    def update_sound_enabled(self, state):
        self.duck.sound_enabled = state == Qt.CheckState.Checked
        self.duck.apply_settings()

    def update_show_name(self, state):
        self.duck.show_name = state == Qt.CheckState.Checked
        self.duck.apply_settings()

    def update_ground_level(self, value):
        self.duck.update_ground_level(value)
        self.duck.apply_settings()

    def update_direction_interval(self, value):
        self.duck.direction_change_interval = value
        self.duck.apply_settings()

    def update_font_base_size(self, value):
        self.duck.font_base_size = value
        self.duck.apply_settings()

    def update_autostart(self, state):
        self.duck.autostart_enabled = state == Qt.CheckState.Checked
        if self.duck.autostart_enabled:
            self.duck.enable_autostart()
        else:
            self.duck.disable_autostart()
        self.duck.apply_settings()

    def update_language_line(self):
        lang_code = self.languageEdit.text().strip()
        self.duck.current_language = lang_code
        self.duck.apply_settings()

    def update_name_offset(self, value):
        self.duck.name_offset_y = value
        self.duck.apply_settings()

    def update_sound_interval_min(self, value):
        self.duck.sound_interval_min = value
        self.duck.apply_settings()

    def update_sound_interval_max(self, value):
        self.duck.sound_interval_max = value
        self.duck.apply_settings()

    def update_playful_probability(self, value):
        self.duck.playful_behavior_probability = value
        self.duck.apply_settings()

    def closeEvent(self, event):
        self.duck.debug_mode = False
        event.accept()
        super().closeEvent(event)


class HeartWindow(QtWidgets.QWidget):
    def __init__(self, x, y):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.opacity = 1.0
        self.start_time = time.time()
        self.duration = 2.0

        self.size = random.uniform(20, 50)
        self.dx = random.uniform(-20, 20)
        self.dy = random.uniform(-50, -100)

        heart_image_path = resource_path("assets/images/heart.png")

        if not os.path.exists(heart_image_path):
            logging.error("Error: File %s not found.", heart_image_path)
            QtWidgets.QMessageBox.Icon.Critical(
                self,
                translations.get("error_title", "Error!"),
                translations.get("file_not_found", "File not found:") + f" '{heart_image_path}'",
            )
            self.close()
            return

        self.image = QtGui.QPixmap(heart_image_path).scaled(
            int(self.size),
            int(self.size),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

        self.x = x - self.size / 2
        self.y = y - self.size / 2
        self.move(int(self.x), int(self.y))

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_position)
        self.timer.start(30)

        self.resize(int(self.size), int(self.size))

        self.show()

    def closeEvent(self, event):
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        self.timer = None
        logging.info("HeartWindow closed and cleaned up.")
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        try:
            painter.setOpacity(self.opacity)
            painter.drawPixmap(0, 0, self.image)
        finally:
            painter.end()

    def update_position(self):
        elapsed = time.time() - self.start_time
        if elapsed > self.duration:
            self.close()
            return

        progress = elapsed / self.duration
        self.x += self.dx * 0.02
        self.y += self.dy * 0.02
        self.opacity = 1.0 - progress
        self.move(int(self.x), int(self.y))
        self.update()


class NameWindow(QtWidgets.QWidget):
    """
    A small top-level window that displays the duck's name above the duck's head.
    """

    def __init__(self, duck):
        super().__init__()
        self.duck = duck
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self.label = QtWidgets.QLabel(self)
        self.label.setStyleSheet("QLabel { color: white; font-weight: bold; }")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_label()
        self.show()

    def update_label(self):
        base_size = getattr(self.duck, "font_base_size", 14)
        scaled_size = int(base_size * (self.duck.pet_size / 3))
        if scaled_size < 8:
            scaled_size = 8
        font = QtGui.QFont("Segoe UI", scaled_size)
        self.label.setFont(font)
        self.label.setText(self.duck.pet_name)
        self.label.adjustSize()
        self.adjustSize()

    def update_position(self):
        duck_x = self.duck.duck_x
        duck_y = self.duck.duck_y
        duck_w = self.duck.duck_width
        name_width = self.width()
        name_height = self.height()

        top_offset = self.duck.get_top_non_opaque_offset()
        offset_y = self.duck.name_offset_y + top_offset
        x = duck_x + (duck_w - name_width) / 2
        y = duck_y - offset_y

        screen = QtWidgets.QApplication.primaryScreen()
        screen_rect = screen.geometry()

        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x + name_width > screen_rect.width():
            x = screen_rect.width() - name_width
        if y + name_height > screen_rect.height():
            y = screen_rect.height() - name_height

        self.move(int(x), int(y))


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent=None):
        self.visible_icon_path = resource_path("assets/images/white-quackduck-visible.ico")
        self.hidden_icon_path = resource_path("assets/images/white-quackduck-hidden.ico")

        if not os.path.exists(self.visible_icon_path):
            logging.error("Icon file %s not found.", self.visible_icon_path)
            QtWidgets.QMessageBox.Icon.Critical(
                parent,
                translations.get("error_title", "Error!"),
                translations.get("file_not_found", "File not found:") + f": '{self.visible_icon_path}'",
            )
            super().__init__()
        else:
            icon = QtGui.QIcon(self.visible_icon_path)
            super().__init__(icon, parent)

        self.parent = parent
        self.setup_menu()
        self.activated.connect(self.icon_activated)

    def setup_menu(self):
        menu = QtWidgets.QMenu()

        settings_action = menu.addAction(translations.get("settings", "Settings"))
        settings_action.triggered.connect(self.parent.open_settings)

        unstuck_action = menu.addAction(translations.get("unstuck", "Unstuck"))
        unstuck_action.triggered.connect(self.parent.unstuck_duck)

        about_action = menu.addAction(translations.get("about", "About"))
        about_action.triggered.connect(self.show_about)

        check_updates_action = menu.addAction(translations.get("check_updates", "Update"))
        check_updates_action.triggered.connect(self.check_for_updates)

        menu.addSeparator()

        show_action = menu.addAction(translations.get("show", "Show"))
        hide_action = menu.addAction(translations.get("hide", "Hide"))

        menu.addSeparator()

        coffee_action = menu.addAction(translations.get("buy_me_a_coffee", "Buy me a coffee"))
        coffee_action.triggered.connect(lambda: webbrowser.open("https://buymeacoffee.com/zl0yxp"))

        exit_action = menu.addAction(translations.get("exit", "Close"))

        show_action.triggered.connect(self.show_duck)
        hide_action.triggered.connect(self.hide_duck)
        exit_action.triggered.connect(QtWidgets.QApplication.instance().quit)

        menu.addSeparator()

        if GLOBAL_DEBUG_MODE:
            debug_action = menu.addAction(translations.get("debug_mode", "Debug mode"))
            debug_action.triggered.connect(self.parent.show_debug_window)

        self.setContextMenu(menu)

        self.contextMenu().setStyleSheet(
            """
            QMenu {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #3a3a3a;
            }
            QMenu::separator {
                height: 1px;
                background: #444;
                margin: 5px 0;
            }
        """
        )

    def hide_duck(self):
        self.parent.hide()
        if hasattr(self.parent, "name_window") and self.parent.name_window and self.parent.name_window.isVisible():
            self.parent.name_window.hide()
        if os.path.exists(self.hidden_icon_path):
            self.setIcon(QtGui.QIcon(self.hidden_icon_path))
        self.parent.pause_duck(force_idle=False)

    def show_duck(self):
        self.parent.show()
        if hasattr(self.parent, "name_window") and self.parent.name_window and self.parent.show_name:
            self.parent.name_window.show()
        self.parent.raise_()
        self.parent.activateWindow()
        if os.path.exists(self.visible_icon_path):
            self.setIcon(QtGui.QIcon(self.visible_icon_path))
        self.parent.resume_duck()

    def icon_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick:
            self.parent.open_settings()
            self.show_duck()
        elif reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            if self.parent.isVisible():
                self.hide_duck()
            else:
                self.show_duck()

    def check_for_updates(self):
        self.parent.check_for_updates_manual()

    def show_about(self):
        about_text = "QuackDuck\nDeveloped with love by zl0yxp\nDiscord: zl0yxp\nTelegram: t.me/quackduckapp"
        QtWidgets.QMessageBox.information(
            self.parent,
            translations.get("about_title", "About"),
            about_text,
            QtWidgets.QMessageBox.Ok,
        )


class FlowLayout(QLayout):
    def __init__(self, parent=None, scale_factor=1.0):
        super().__init__(parent)
        self.itemList: List[QtWidgets.QLayoutItem] = []
        self.scale_factor = scale_factor

        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(int(10 * self.scale_factor))

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return QSize(0, 0)

    def doLayout(self, rect, testOnly):
        left, top, right, bottom = self.getContentsMargins()
        space = self.spacing()

        x = rect.x() + left
        y = rect.y() + top
        lineHeight = 0

        for item in self.itemList:
            widget = item.widget()
            hint = widget.sizeHint()

            if x + hint.width() > rect.right() - right and (x > rect.x() + left):
                x = rect.x() + left
                y = y + lineHeight + space
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))

            x = x + hint.width() + space
            lineHeight = max(lineHeight, hint.height())

        return y + lineHeight + bottom - rect.y()


class SidebarButton(QPushButton):
    def __init__(self, text, parent=None, scale_factor=1.0):
        super().__init__(text, parent)
        self.scale_factor = scale_factor
        scale = lambda val: int(val * self.scale_factor)

        self.setFixedHeight(scale(40))

        self.accent_qcolor = get_system_accent_color()
        self.accent_color = self.accent_qcolor.name()

        self.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCheckable(True)

        base_font_size = 14
        scaled_font_size = max(1, int(base_font_size * self.scale_factor))

        self.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                padding-left: {scale(16)}px;
                border: none;
                font-size: {scaled_font_size}px;
                color: #ccc;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
            QPushButton:checked {{
                background-color: #3a3a3a;
                color: #e0e0e0;
                border-left: {scale(4)}px solid {self.accent_color};
                padding-left: {scale(12)}px;
            }}
        """
        )


class SettingsWindow(QMainWindow):
    def __init__(self, duck):
        super().__init__()
        self.duck = duck
        self.scale_factor = getattr(self.duck, 'scale_factor', 1.0)
        s = lambda val: int(val * self.scale_factor)

        self.translations = translations
        self.accent_qcolor = get_system_accent_color()
        self.accent_color = self.accent_qcolor.name()

        self.setWindowTitle(self.translations.get("settings_title", "Settings"))
        icon_path = os.path.join(self.duck.resources.assets_dir, "images", "settings.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        base_w, base_h = 1000, 600
        self.resize(s(base_w), s(base_h))

        container = QWidget()
        self.setCentralWidget(container)

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QVBoxLayout()
        self.sidebar.setContentsMargins(0, 0, 0, s(10))
        self.sidebar.setSpacing(0)

        self.app_title = QHBoxLayout()
        self.app_title.setContentsMargins(s(20), s(20), s(20), s(20))
        self.app_title.setSpacing(s(10))

        self.app_label = QLabel(self.translations.get("settings_title", "Settings"))
        title_font_size = max(1, int(16 * self.scale_factor))
        self.app_label.setStyleSheet(f"font-weight:600;font-size:{title_font_size}px;color:#fff;")
        self.app_title.addWidget(self.app_label)
        self.app_title.addStretch()
        self.sidebar.addLayout(self.app_title)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color:#3a3a3a;")
        self.sidebar.addWidget(line)

        self.btn_general = SidebarButton(self.translations.get("page_button_general", "General"), scale_factor=self.scale_factor)
        self.btn_general.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_appearance = SidebarButton(self.translations.get("page_button_appearance", "Appearance"), scale_factor=self.scale_factor)
        self.btn_appearance.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_advanced = SidebarButton(self.translations.get("page_button_advanced", "Advanced"), scale_factor=self.scale_factor)
        self.btn_advanced.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_about = SidebarButton(self.translations.get("page_button_about", "About"), scale_factor=self.scale_factor)
        self.btn_about.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_store = SidebarButton("Магазин скинов", scale_factor=self.scale_factor)
        self.btn_store.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_general.setChecked(True)
        for btn in [self.btn_general, self.btn_appearance, self.btn_advanced, self.btn_about, self.btn_store]:
            btn.clicked.connect(self.change_tab)
            self.sidebar.addWidget(btn)

        self.sidebar.addStretch()

        version_label = QLabel(self.translations.get("version", "Version") + f" {PROJECT_VERSION}")
        version_label_font_size = max(1, int(12 * self.scale_factor))
        version_label.setStyleSheet(f"color:#aaa;font-size:{version_label_font_size}px;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar.addWidget(version_label)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QWidget { color: #ccc; }")

        self.stack.addWidget(self.general_tab())
        self.stack.addWidget(self.appearance_tab())
        self.stack.addWidget(self.advanced_tab())
        self.stack.addWidget(self.about_tab())
        self.stack.addWidget(self.store_tab())

        main_layout.addWidget(self.sidebar_container())
        main_layout.addWidget(self.stack, 1)

        self.apply_stylesheet()

        # Список буферов для QMovie
        self.store_buffers = []

        self.mic_preview_timer = QTimer(self)
        self.mic_preview_timer.timeout.connect(self.update_mic_preview)
        self.mic_preview_timer.start(100)

    def update_all_animations(self):
        """
        Вызывается каждые 300 мс. Перебираем все метки, переключаем кадры.
        """
        for item in self.anim_labels:
            label = item["label"]
            frames = item["frames"]
            idx = item["index"]
            if frames:
                idx = (idx + 1) % len(frames)
                item["index"] = idx
                label.setPixmap(frames[idx])

    def sidebar_container(self):
        s = lambda val: int(val * self.scale_factor)
        w = QWidget()
        w.setLayout(self.sidebar)
        w.setFixedWidth(s(220))
        w.setStyleSheet("background-color:#2a2a2a;")

        return w

    def apply_stylesheet(self):
        s = lambda val: int(val * self.scale_factor)
        base_font_size = 14
        scaled_font_size = max(1, int(base_font_size * self.scale_factor))
        self.setStyleSheet(f"""
            QMainWindow {{
                background: #1e1e1e;
            }}
            QCheckBox, QRadioButton, QLabel, QComboBox, QSpinBox, QLineEdit {{
                font-size:{scaled_font_size}px;
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background: #2f2f2f;
                border:1px solid #444;
                border-radius:3px;
                padding:{s(4)}px;
                color:#ccc;
            }}
            QComboBox QAbstractItemView {{
                background: #2f2f2f;
                border:1px solid #444;
                color:#ccc;
                selection-background-color:#3a3a3a;
                selection-color:#fff;
            }}

            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border:1px solid {self.accent_color};
                outline: none;
            }}
            QPushButton {{
                background-color: {self.accent_color};
                color:#fff;
                border:none;
                border-radius:3px;
                padding:{s(8)}px {s(14)}px;
                font-size:{scaled_font_size}px;
            }}
            QPushButton:hover {{
                background-color: {self.accent_qcolor.lighter(105).name()};
            }}
            QPushButton:pressed {{
                background:{self.accent_qcolor.lighter(110).name()};
            }}
            QSlider::groove:horizontal {{
                background:#444;
                height:{s(6)}px;
                border-radius:{s(3)}px;
            }}
            QSlider::handle:horizontal {{
                background:{self.accent_color};
                width:{s(14)}px;
                height:{s(14)}px;
                margin:-{s(4)}px 0;
                border-radius:{s(7)}px;
            }}
            QSlider::sub-page:horizontal {{
                background:{self.accent_color};
                border-radius:{s(3)}px;
            }}
            QProgressBar {{
                background:#444;
                border:1px solid #555555;
                border-radius:{s(3)}px;
                height:{s(12)}px;
                text-align:center;
                color:white;
                font-size:{scaled_font_size}px;
                padding:{s(5)}px;
            }}
            QProgressBar::chunk {{
                background:{self.accent_color};
                border-radius:{s(3)}px;
            }}
            QScrollBar:vertical {{
                background:#2f2f2f; width:{s(8)}px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.accent_color};
                border-radius:{s(3)}px;
                min-height:{s(20)}px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height:0;
                background:none;
            }}
            QPushButton#cancelButton {{
                background-color: #444;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton#cancelButton:hover {{
                background-color: #555;
            }}
        """)

        if hasattr(self, 'skins_container'):
            self.skins_container.setStyleSheet("background-color: #1e1e1e; ")

        if hasattr(self, 'skins_scroll'):
            self.skins_scroll.setStyleSheet("QScrollArea { background-color: #1e1e1e; border: 1px solid #444; border-radius: 3px; }")

    def change_tab(self):
        sender = self.sender()
        for b in [self.btn_general, self.btn_appearance, self.btn_advanced, self.btn_about, self.btn_store]:
            b.setChecked(False)

        if sender == self.btn_general:
            self.btn_general.setChecked(True)
            self.stack.setCurrentIndex(0)
        elif sender == self.btn_appearance:
            self.btn_appearance.setChecked(True)
            self.stack.setCurrentIndex(1)
        elif sender == self.btn_advanced:
            self.btn_advanced.setChecked(True)
            self.stack.setCurrentIndex(2)
        elif sender == self.btn_about:
            self.btn_about.setChecked(True)
            self.stack.setCurrentIndex(3)
        elif sender == self.btn_store:
            self.btn_store.setChecked(True)
            self.stack.setCurrentIndex(4)
            self.refresh_store()

    # General tab in a settings
    def general_tab(self):
        s = lambda val: int(val * self.scale_factor)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(s(20), s(20), s(20), s(20))
        layout.setSpacing(s(20))

        title_font_size = max(1, int(20 * self.scale_factor))
        title = QLabel(self.translations.get("page_button_general","General"))
        title.setStyleSheet(f"font-size:{title_font_size}px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:{s(10)}px;")
        layout.addWidget(title)

        # Pet Name
        pet_name_box = QVBoxLayout()
        lbl_petname = QLabel(self.translations.get("pet_name","Pet Name:"))
        h_name = QHBoxLayout()
        self.petName = QLineEdit()
        self.petName.setPlaceholderText(self.translations.get("enter_name_placeholder","Name..."))
        self.petName.setText(self.duck.pet_name)

        name_info_button = QPushButton("❓")
        name_info_button.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        name_info_button.setFixedSize(s(36), s(36))
        name_button_font = name_info_button.font()
        name_button_font.setPointSize(max(1,int(16 * self.scale_factor)))
        name_info_button.setFont(name_button_font)
        name_info_button.setToolTip(self.translations.get("info_about_pet_name_tooltip","Information about pet name"))
        name_info_button.setStyleSheet(f"QPushButton {{ padding:{s(4)}px; }}")
        name_info_button.clicked.connect(self.show_name_characteristics)

        h_name.addWidget(self.petName)
        h_name.addWidget(name_info_button)

        pet_name_box.addWidget(lbl_petname)
        pet_name_box.addLayout(h_name)
        layout.addLayout(pet_name_box)

        # Input Device
        mic_box = QVBoxLayout()
        lbl_mic = QLabel(self.translations.get("input_device_selection","Input Device:"))
        self.micDevice = QComboBox()
        devices = self.duck.get_input_devices()
        for idx,name in devices:
            self.micDevice.addItem(name,idx)
        if self.duck.selected_mic_index is not None:
            mic_idx = self.micDevice.findData(self.duck.selected_mic_index)
            if mic_idx>=0:self.micDevice.setCurrentIndex(mic_idx)
        mic_box.addWidget(lbl_mic)
        mic_box.addWidget(self.micDevice)
        layout.addLayout(mic_box)

        # Activation Threshold
        lbl_thresh = QLabel(self.translations.get("activation_threshold","Activation Threshold:"))
        self.thresholdValue = QLabel(f"{self.duck.activation_threshold}%")
        self.thresholdSlider = QSlider(Qt.Orientation.Horizontal)
        self.thresholdSlider.setRange(0,100)
        self.thresholdSlider.setValue(self.duck.activation_threshold)
        self.thresholdSlider.valueChanged.connect(lambda v: self.thresholdValue.setText(f"{v}%"))

        thresh_layout = QVBoxLayout()
        thresh_layout.addWidget(lbl_thresh)
        h_thresh = QHBoxLayout()
        h_thresh.addWidget(self.thresholdValue)
        h_thresh.addWidget(self.thresholdSlider)
        thresh_layout.addLayout(h_thresh)

        # Mic volume preview
        lbl_mic_level = QLabel(self.translations.get("mic_level","Sound Level:"))
        thresh_layout.addWidget(lbl_mic_level)
        self.mic_level_preview = QProgressBar()
        self.mic_level_preview.setRange(0,100)
        self.mic_level_preview.setValue(self.duck.current_volume if hasattr(self.duck,'current_volume') else 0)
        thresh_layout.addWidget(self.mic_level_preview)
        layout.addLayout(thresh_layout)

        # Enable Sound + volume
        cb_layout = QVBoxLayout()
        self.enableSound = QCheckBox(self.translations.get("turn_on_sound","Enable Sound"))
        self.enableSound.setChecked(self.duck.sound_enabled)
        self.enableSound.stateChanged.connect(self.toggle_volume_slider)
        cb_layout.addWidget(self.enableSound)

        self.volumeLabel = QLabel(self.translations.get("volume","Volume:"))
        self.volumeValue = QLabel("50%")
        self.volumeSlider = QSlider(Qt.Orientation.Horizontal)
        self.volumeSlider.setRange(0,100)
        volume_from_settings = self.duck.settings_manager.get_value('sound_volume',0.5,float)
        initial_vol = int(volume_from_settings*100)
        self.volumeSlider.setValue(initial_vol)
        self.volumeValue.setText(f"{initial_vol}%")

        def update_volume(v):
            self.volumeValue.setText(f"{v}%")
            vol = v / 100.0
            audio_output.setVolume(vol)
            self.duck.sound_effect.setVolume(vol)
            self.duck.sound_volume = vol
            self.duck.settings_manager.set_value('sound_volume', vol)
            self.duck.settings_manager.sync()

        self.volumeSlider.valueChanged.connect(update_volume)
        self.volumeSlider.sliderReleased.connect(self.play_random_sound_on_volume_release)

        default_skin_path = self.duck.skin_folder if self.duck.skin_folder else os.path.join(self.duck.resources.skins_dir,'default')
        sound_path = os.path.join(default_skin_path, 'wuak.wav')
        
        audio_output = QAudioOutput()
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(audio_output)
        url = QUrl.fromLocalFile(sound_path)

        if url.isValid():
            self.media_player.setSource(url)
        else:
            logging.error(f"Invalid sound file URL: {sound_path}")

        vol_layout = QVBoxLayout()
        vol_layout.addWidget(self.volumeLabel)
        h_vol = QHBoxLayout()
        h_vol.addWidget(self.volumeValue)
        h_vol.addWidget(self.volumeSlider)
        vol_layout.addLayout(h_vol)
        cb_layout.addLayout(vol_layout)

        self.showName = QCheckBox(self.translations.get("show_name_checkbox","Show name above duck"))
        self.showName.setChecked(self.duck.show_name)
        cb_layout.addWidget(self.showName)
        layout.addLayout(cb_layout)

        layout.addStretch()

        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton(self.translations.get("cancel_button","Cancel"))
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn = QPushButton(self.translations.get("save_button","Save"))
        save_btn.clicked.connect(self.save_general_settings)
        save_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        layout.addLayout(act_box)

        self.toggle_volume_slider()
        return w
    
    def play_quack_sound(self):
        if self.media_player:
            self.media_player.play()


    def play_random_sound_on_volume_release(self):
        if self.enableSound.isChecked():
            self.duck.play_random_sound()

    def toggle_volume_slider(self):
        enabled = self.enableSound.isChecked()
        self.volumeLabel.setVisible(enabled)
        self.volumeValue.setVisible(enabled)
        self.volumeSlider.setVisible(enabled)

    def play_quack_sound(self):
        self.soundEffect.play()

    def show_name_characteristics(self):
        name = self.petName.text().strip()
        if name:
            characteristics = self.duck.get_name_characteristics(name)
            info_text = "\n".join([f"{key}: {value}" for key, value in characteristics.items()])
            QMessageBox.information(self, self.translations.get("characteristics_title","Characteristics"), info_text)
        else:
            QMessageBox.information(
                self,
                self.translations.get("characteristics_title","Characteristics"),
                self.translations.get("characteristics_text","Enter a name to see characteristics.")
            )

    def save_general_settings(self):
        self.duck.pet_name = self.petName.text()
        idx = self.micDevice.currentIndex()
        self.duck.selected_mic_index = self.micDevice.itemData(idx)
        self.duck.activation_threshold = self.thresholdSlider.value()
        self.duck.sound_enabled = self.enableSound.isChecked()
        self.duck.show_name = self.showName.isChecked()
        self.duck.apply_settings()
        self.close()

    # Appearance tab in a settings
    def appearance_tab(self):
        s = lambda val: int(val * self.scale_factor)

        w = QWidget()
        self.appearance_layout = QVBoxLayout(w)
        self.appearance_layout.setContentsMargins(s(20), s(20), s(20), s(20))
        self.appearance_layout.setSpacing(s(20))

        title_font_size = max(1, int(20 * self.scale_factor))
        title = QLabel(self.translations.get("page_button_appearance","Appearance"))
        title.setStyleSheet(f"font-size:{title_font_size}px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:{s(10)}px;")
        self.appearance_layout.addWidget(title)

        # skins_help_box = QHBoxLayout()
        # where_to_get_skins_label = QLabel(self.translations.get("where_to_get_skins","Don't know where to get skins?"))
        # f = where_to_get_skins_label.font()
        # f.setBold(True)
        # where_to_get_skins_label.setFont(f)
        # skin_shop_btn = QPushButton("QD Skin Shop")
        # skin_shop_btn.self.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        # skin_shop_btn.clicked.connect(lambda: self.open_link("https://test.test"))
        # skins_help_box.addWidget(where_to_get_skins_label)
        # skins_help_box.addStretch()
        # skins_help_box.addWidget(skin_shop_btn)
        # self.appearance_layout.addLayout(skins_help_box)

        # Pet Size
        size_box = QVBoxLayout()
        lbl_size = QLabel(self.translations.get("pet_size","Pet size:"))
        self.petSize = QComboBox()
        size_map = {1:"x1",2:"x2",3:"x3",5:"x5",10:"x10"}
        for v,txt in size_map.items():
            self.petSize.addItem(txt,v)
        idx = self.petSize.findData(self.duck.pet_size)
        if idx>=0:
            self.petSize.setCurrentIndex(idx)
        size_box.addWidget(lbl_size)
        size_box.addWidget(self.petSize)
        self.appearance_layout.addLayout(size_box)

        folder_box = QVBoxLayout()
        lbl_folder = QLabel(self.translations.get("skin_folder_path","Skins folder path:"))
        f_hbox = QHBoxLayout()
        self.folderPath = QLineEdit()
        self.folderPath.setPlaceholderText(self.translations.get("not_selected","Not selected"))
        self.folderPath.setReadOnly(True)
        if self.duck.skin_folder:
            self.folderPath.setText(self.duck.skin_folder)
        choose_btn = QPushButton(self.translations.get("select_skin_folder_button","Select Skins Folder"))
        choose_btn.clicked.connect(self.select_skins_folder)
        choose_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        f_hbox.addWidget(self.folderPath)
        f_hbox.addWidget(choose_btn)
        folder_box.addWidget(lbl_folder)
        folder_box.addLayout(f_hbox)
        self.appearance_layout.addLayout(folder_box)

        lbl_skins_font_size = max(1, int(16 * self.scale_factor))
        lbl_skins = QLabel(self.translations.get("skins_preview","Skins Preview:"))
        lbl_skins.setStyleSheet(f"font-size:{lbl_skins_font_size}px;color:#ddd;")
        self.appearance_layout.addWidget(lbl_skins)

        self.skins_scroll = QScrollArea()
        self.skins_scroll.setWidgetResizable(True)
        self.skins_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.skins_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.skins_container = QWidget()
        self.skins_layout = FlowLayout(scale_factor=self.scale_factor)
        self.skins_container.setLayout(self.skins_layout)

        self.skins_scroll.setWidget(self.skins_container)
        self.skins_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.appearance_layout.addWidget(self.skins_scroll)

        self.load_skins_from_folder(self.duck.skin_folder)

        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton(self.translations.get("cancel_button","Cancel"))
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn = QPushButton(self.translations.get("save_button","Save"))
        save_btn.clicked.connect(self.save_appearance_settings)
        save_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        self.appearance_layout.addLayout(act_box)

        return w

    def select_skins_folder(self):
        """
        Called when user clicks the 'Select Skins Folder' button.
        Opens a directory dialog for the user to pick a folder,
        then calls load_skins_from_folder(...) with show_warning_on_empty=True.
        """
        folder = QFileDialog.getExistingDirectory(
            self,
            self.translations.get("select_skin_folder","Select skins folder")
        )
        if folder:
            self.folderPath.setText(folder)
            self.duck.skin_folder = folder
            self.duck.save_settings()

            self.load_skins_from_folder(folder, show_warning_on_empty=True)

    def load_skins_from_folder(self, folder, show_warning_on_empty=False):
        """
        Loads all available skin .zip files from the given folder into the UI preview.
        If show_warning_on_empty=True and no skins found, shows a messagebox warning.
        Otherwise, stays silent if no skins are found.

        Args:
            folder (str): path to the folder containing the .zip skin files
            show_warning_on_empty (bool): whether to display a warning if no skins are found.
        """
        # Clear current skin previews in the UI
        while self.skins_layout.count() > 0:
            item = self.skins_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # If folder is None or doesn't exist, just return; no warnings unless we want them
        if not folder or not os.path.exists(folder):
            logging.warning("No folder provided or folder does not exist.")
            return

        # Load the default skin preview (if you do that by default)
        frames = self.duck.resources.load_skin_frames_for_preview(is_default=True)
        default_item = self.create_default_skin_item(frames)
        if default_item:
            self.skins_layout.addWidget(default_item)

        has_skins = False

        # Scan for .zip files
        for file in os.listdir(folder):
            if file.lower().endswith(".zip"):
                # If you want to skip 'default' zip
                if 'default' in file.lower():
                    continue

                skin_path = os.path.join(folder, file)
                skin_item = self.create_skin_item(skin_path)
                if skin_item:
                    self.skins_layout.addWidget(skin_item)
                    has_skins = True

        if not has_skins and show_warning_on_empty:
            QMessageBox.warning(
                self,
                self.translations.get("warning_title", "Warning"),
                self.translations.get("no_skins_in_folder", "No skins in the selected folder.")
            )

    def create_default_skin_item(self, frames):
        s = lambda val: int(val * self.scale_factor)
        item = QFrame()
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.setStyleSheet("""
            QFrame {
                background:#2f2f2f; border-radius:3px;
            }
            QFrame:hover {
                background:#3a3a3a;
            }
        """)
        item_layout = QVBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)

        animation_label = QLabel()
        animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        animation_label.frames = frames
        animation_label.frame_index = 0
        animation_label.setFixedSize(s(128), s(128))

        # Local function to update animation frames
        def update_frame():
            if hasattr(animation_label, 'frames') and animation_label.frames:
                frame = animation_label.frames[animation_label.frame_index]
                scaled_frame = frame.scaled(s(128), s(128), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
                animation_label.setPixmap(scaled_frame)
                animation_label.frame_index = (animation_label.frame_index + 1) % len(animation_label.frames)

        # Setting up a timer for animation
        timer = QTimer(animation_label)
        timer.timeout.connect(update_frame)
        timer.start(150)
        update_frame()  # Setting the initial frame
        animation_label.timer = timer

        item_layout.addWidget(animation_label, alignment=Qt.AlignmentFlag.AlignCenter)
        item.setToolTip("Default Skin")

        # Handling a click to apply a skin
        def on_click(event):
            try:
                self.duck.selected_skin = None
                self.duck.resources.load_default_skin(lazy=False)
                self.duck.update_duck_skin()
                self.duck.apply_settings()
                QMessageBox.information(
                    self,
                    self.translations.get("success", "Success!"),
                    self.translations.get("skin_applied_successfully", "Skin successfully applied: Default")
                )
            except Exception as e:
                logging.error(f"Error applying default skin: {e}")
                QMessageBox.warning(
                    self,
                    self.translations.get("error_title", "Error"),
                    self.translations.get("failed_apply_skin", "Failed to apply skin: Default")
                )

        item.mousePressEvent = on_click
        return item

    def create_skin_item(self, skin_file):
        s = lambda val: int(val * self.scale_factor)

        if skin_file == "Default":
            frames = self.duck.resources.load_skin_frames_for_preview(is_default=True)
            frame_width = self.duck.resources.frame_width
            frame_height = self.duck.resources.frame_height
        else:
            frames = self.duck.resources.load_skin_frames_for_preview(skin_path=skin_file)
            frame_width = self.duck.resources.frame_width
            frame_height = self.duck.resources.frame_height
        if not frames:
            return None

        item = QFrame()
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.setStyleSheet("""
            QFrame {
                background:#2f2f2f; border-radius:3px;
            }
            QFrame:hover {
                background:#3a3a3a;
            }
        """)
        item_layout = QVBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)

        animation_label = QLabel()
        animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        animation_label.frames = frames
        animation_label.frame_index = 0
        animation_label.setFixedSize(s(128), s(128))

        def update_frame():
            if not animation_label.frames:
                logging.error("No frames available for animation.")
                return
            frm = animation_label.frames[animation_label.frame_index]
            frm_scaled = frm.scaled(
                int(frame_width * (animation_label.width() / frame_width)),
                int(frame_height * (animation_label.height() / frame_height)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            animation_label.setPixmap(frm_scaled)
            animation_label.frame_index = (animation_label.frame_index + 1) % len(animation_label.frames)

        timer = QTimer(animation_label)
        timer.timeout.connect(update_frame)
        timer.start(150)
        update_frame()
        animation_label.timer = timer

        skin_name_text = "Default" if skin_file == "Default" else os.path.basename(skin_file)
        item.setToolTip(skin_name_text)
        item_layout.addWidget(animation_label, alignment=Qt.AlignmentFlag.AlignCenter)

        def on_click(event):
            if skin_file == "Default":
                self.duck.resources.load_default_skin()
            else:
                success = self.duck.resources.load_skin(skin_file)
                if success:
                    self.duck.selected_skin = skin_file
                    self.duck.save_settings()
                    self.duck.update_duck_skin()
                    QMessageBox.information(
                        self,
                        self.translations.get("success", "Success!"),
                        self.translations.get("skin_applied_successfully", "Skin successfully applied:") + f" {skin_name_text}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        self.translations.get("error_title", "Error!"),
                        self.translations.get("failed_apply_skin", "Failed to apply skin:") + f" {skin_name_text}"
                    )
        item.mousePressEvent = on_click
        return item

    def save_appearance_settings(self):
        idx = self.petSize.currentIndex()
        pet_size = self.petSize.itemData(idx)
        self.duck.update_pet_size(pet_size)
        self.duck.apply_settings()
        self.close()

    # Advanced tab in a settings
    def advanced_tab(self):
        s = lambda val: int(val * self.scale_factor)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(s(20), s(20), s(20), s(20))
        layout.setSpacing(s(20))

        title_font_size = max(1, int(20 * self.scale_factor))
        title = QLabel(self.translations.get("page_button_advanced","Advanced"))
        title.setStyleSheet(f"font-size:{title_font_size}px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:{s(10)}px;")
        layout.addWidget(title)

        # Floor Level
        floor_box = QVBoxLayout()
        lbl_floor = QLabel(self.translations.get("floor_level","Floor level (pixels from bottom):"))
        self.floorLevel = QSpinBox()
        self.floorLevel.setRange(0,10000)
        self.floorLevel.setValue(self.duck.ground_level_setting)
        floor_box.addWidget(lbl_floor)
        floor_box.addWidget(self.floorLevel)
        layout.addLayout(floor_box)

        # Name Offset
        offset_box = QVBoxLayout()
        lbl_offset = QLabel(self.translations.get("name_offset_y","Name Offset Y (pixels):"))
        self.nameOffset = QSpinBox()
        self.nameOffset.setRange(-10000,10000)
        self.nameOffset.setValue(self.duck.name_offset_y)
        offset_box.addWidget(lbl_offset)
        offset_box.addWidget(self.nameOffset)
        layout.addLayout(offset_box)

        # Base Font Size
        font_box = QVBoxLayout()
        lbl_font = QLabel(self.translations.get("font_base_size","Base font size:"))
        self.fontBaseSize = QSpinBox()
        self.fontBaseSize.setRange(6,200)
        base_fs = getattr(self.duck,'font_base_size',14)
        self.fontBaseSize.setValue(base_fs)
        font_box.addWidget(lbl_font)
        font_box.addWidget(self.fontBaseSize)
        layout.addLayout(font_box)

        # Language
        lang_box = QVBoxLayout()
        lbl_lang = QLabel(self.translations.get("language_selection","Language:"))
        self.language = QComboBox()
        langs = {'en':'English','ru':'Русский'}
        for code,name in langs.items():
            self.language.addItem(name,code)
        idx = self.language.findData(self.duck.current_language)
        if idx>=0:
            self.language.setCurrentIndex(idx)
        lang_box.addWidget(lbl_lang)
        lang_box.addWidget(self.language)
        layout.addLayout(lang_box)

        # Autostart
        auto_box = QHBoxLayout()
        self.autostart = QCheckBox(self.translations.get("run_at_system_startup","Run at system startup"))
        self.autostart.setChecked(self.duck.autostart_enabled)
        auto_box.addWidget(self.autostart)
        auto_box.addStretch()
        layout.addLayout(auto_box)

        reset_btn = QPushButton(self.translations.get("reset_to_default_button","Reset all settings"))
        reset_btn.setStyleSheet("background:#a00;color:#fff;")
        reset_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        reset_btn.clicked.connect(self.reset_settings_clicked)
        layout.addWidget(reset_btn)

        layout.addStretch()

        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton(self.translations.get("cancel_button","Cancel"))
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn = QPushButton(self.translations.get("save_button","Save"))
        save_btn.clicked.connect(self.save_advanced_settings)
        save_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        layout.addLayout(act_box)

        return w

    def reset_settings_clicked(self):
        reply = QMessageBox.question(
            self,
            self.translations.get("reset_to_default_title","Reset settings"),
            self.translations.get("reset_to_default_conformation","Are you sure you want to reset all settings?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.duck.reset_settings()
            self.duck.selected_skin = None
            self.duck.update_duck_skin()
            self.duck.apply_settings()
            self.close()

    def save_advanced_settings(self):
        floor_level = self.floorLevel.value()
        name_offset = self.nameOffset.value()
        font_base_size = self.fontBaseSize.value()
        lang_code = self.language.itemData(self.language.currentIndex())
        autostart_enabled = self.autostart.isChecked()

        self.duck.update_ground_level(floor_level)
        self.duck.name_offset_y = name_offset
        self.duck.font_base_size = font_base_size
        self.duck.current_language = lang_code
        self.duck.autostart_enabled = autostart_enabled

        if autostart_enabled:
            self.duck.enable_autostart()
        else:
            self.duck.disable_autostart()

        self.duck.apply_settings()
        self.close()

    # About tab in a settings
    def about_tab(self):
        s = lambda val: int(val * self.scale_factor)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(s(20), s(20), s(20), s(20))
        layout.setSpacing(s(20))

        title_font_size = max(1, int(20 * self.scale_factor))
        title = QLabel(self.translations.get("page_button_about","About"))
        title.setStyleSheet(f"font-size:{title_font_size}px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:{s(10)}px;")
        layout.addWidget(title)

        info_label = QLabel(f"""
            <style>
                a {{
                    color: {self.accent_color};
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
            </style>
            <h2>QuackDuck</h2>
            <p>Developed with 💜 by zl0yxp</p>
            <p>Discord: zl0yxp</p>
            <p>Telegram: <a href="https://t.me/quackduckapp">t.me/quackduckapp</a></p>
            <p>GitHub: <a href="https://github.com/KristopherZlo/quackduck">KristopherZlo/quackduck</a></p>
        """)
        info_label.setWordWrap(True)
        info_label.setOpenExternalLinks(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(info_label)

        support_buttons_layout = QHBoxLayout()
        support_button = QPushButton(self.translations.get("buy_me_a_coffee_button_settings_window","Buy me a coffee ☕"))
        support_button.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        telegram_button = QPushButton("Telegram")
        telegram_button.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        github_button = QPushButton("GitHub")
        github_button.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        support_button.setStyleSheet("background:#444;")
        telegram_button.setStyleSheet("background:#444;")
        github_button.setStyleSheet("background:#444;")
        support_buttons_layout.addWidget(support_button)
        support_buttons_layout.addWidget(telegram_button)
        support_buttons_layout.addWidget(github_button)

        support_button.clicked.connect(lambda: self.open_link("https://buymeacoffee.com/zl0yxp"))
        telegram_button.clicked.connect(lambda: self.open_link("https://t.me/quackduckapp"))
        github_button.clicked.connect(lambda: self.open_link("https://github.com/KristopherZlo/quackduck"))

        layout.addLayout(support_buttons_layout)

        layout.addStretch()
        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton(self.translations.get("cancel_button","Cancel"))
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        act_box.addWidget(cancel_btn)
        layout.addLayout(act_box)

        return w

    def open_link(self, url):
        QDesktopServices.openUrl(QUrl(url))

    # Skin store tab in a settings
    def store_tab(self):
        """
        Create the 'Skin Store' tab with cards aligned vertically,
        each stretching to the full width of the window, having a minimum height of 130px.
        Each card has a 10px margin on all sides and an additional 10px below.
        """
        w = QWidget()
        layout = QVBoxLayout(w)
        s = lambda val: int(val * self.scale_factor)
        
        # Устанавливаем отступы и расстояние между карточками
        layout.setSpacing(10)  # 10px между карточками
        layout.setContentsMargins(10, 10, 10, 10)  # 10px отступы со всех сторон
        
        # Заголовок вкладки "Магазин скинов"
        title = QLabel("Магазин скинов")
        title.setStyleSheet(f"font-size:{s(18)}px; font-weight:bold; color:#fff;")
        layout.addWidget(title)
        
        # Добавляем 50px нижнего отступа после заголовка
        layout.addSpacing(50)
        
        # Создаём область прокрутки для карточек скинов
        self.store_scroll = QScrollArea()
        self.store_scroll.setWidgetResizable(True)
        self.store_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
        """)
        layout.addWidget(self.store_scroll, stretch=1)
        
        # Внутренний контейнер внутри области прокрутки
        self.store_container = QWidget()
        self.store_container.setStyleSheet("background-color: #1e1e1e; border: none;")
        
        # Вертикальный макет для карточек скинов с отступом 10px
        self.store_layout = QVBoxLayout(self.store_container)
        self.store_layout.setSpacing(10)  # 10px между карточками
        self.store_layout.setContentsMargins(10, 10, 10, 10)  # 10px отступы со всех сторон
        self.store_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Выравнивание карточек по верхнему краю
        
        # Устанавливаем контейнер в область прокрутки
        self.store_scroll.setWidget(self.store_container)
        
        return w

    def refresh_store(self):
        """
        Loads the list of skins from the backend.
        Each skin includes a base64-encoded preview GIF, price, and animations_str.
        """
        s = lambda val: int(val * self.scale_factor)
        lang = getattr(self.duck, 'current_language', 'en')
        if lang not in ("ru", "en"):
            lang = "en"

        url = f"http://127.0.0.1:5000/skins?lang={lang}"
        try:
            # Устанавливаем короткий таймаут, чтобы приложение не зависало
            resp = requests.get(url, timeout=2)
            resp.raise_for_status()  # Выбрасываем исключение при ошибке HTTP
            data = resp.json()
        except Exception as e:
            logging.error(f"Не удалось загрузить скины: {e}")
            data = []

        # Очищаем существующие карточки и сообщения
        while self.store_layout.count():
            child = self.store_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            else:
                self.store_layout.removeItem(child)

        # Если данные не получены, отображаем сообщение
        if not data:
            msg_label = QLabel("Магазин почему-то не доступен... :C")
            msg_label.setStyleSheet(f"color: rgba(255,255,255,80); font-size:{s(16)}px;")
            msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.store_layout.addWidget(msg_label)
            return

        # Очищение списка буферов перед загрузкой новых
        self.store_buffers.clear()

        for skin in data:
            skin_id = skin.get("id", "")
            name = skin.get("name", "No name")
            description = skin.get("description", "")
            rarity_color = skin.get("rarity_color", "#333")
            anim_str = skin.get("animations_str", "")
            preview_b64 = skin.get("preview", "")
            price = skin.get("price", "")

            # Создание карточки как QFrame, растягивающейся на всю ширину
            block = QFrame()
            block.setStyleSheet(f"""
                QFrame {{
                    background-color: #2f2f2f;
                    border: 2px solid {rarity_color};
                    border-radius: 8px;
                }}
            """)
            block.adjustSize()

            # Горизонтальное расположение для карточки
            block_layout = QHBoxLayout(block)
            block_layout.setSpacing(15)  # Отступ между превью и текстом
            block_layout.setContentsMargins(10, 10, 10, 10)  # Внутренние отступы 10px

            # Левая сторона - Превью GIF
            if preview_b64:
                try:
                    preview_data = base64.b64decode(preview_b64)
                    buffer = QBuffer()
                    buffer.setData(preview_data)
                    buffer.open(QIODevice.ReadOnly)
                    movie = QMovie()
                    movie.setDevice(buffer)
                    preview_label = QLabel()
                    preview_label.setFixedSize(100, 100)  # Фиксированный размер QLabel 100x100
                    preview_label.setStyleSheet("border: none;")  # Убираем границу

                    # Центрируем превью по вертикали
                    preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                    # Подключаем обработчик изменения кадра
                    movie.frameChanged.connect(lambda frame_num, m=movie, l=preview_label: self.handle_frame_change(m, l))
                    movie.start()
                    self.store_buffers.append(buffer)  # Сохраняем буфер, чтобы он не был собран мусором
                    block_layout.addWidget(preview_label, alignment=Qt.AlignmentFlag.AlignTop)
                except Exception as e:
                    logging.error(f"Не удалось загрузить превью для скина {skin_id}: {e}")
                    # Заполнитель, если превью не удалось загрузить
                    preview_label = QLabel("No Preview")
                    preview_label.setStyleSheet("color:#aaa; border: none;")
                    preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    preview_label.setFixedSize(100, 100)
                    block_layout.addWidget(preview_label, alignment=Qt.AlignmentFlag.AlignTop)
            else:
                # Заполнитель, если превью отсутствует
                preview_label = QLabel("No Preview")
                preview_label.setStyleSheet("color:#aaa; border: none;")
                preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                preview_label.setFixedSize(100, 100)
                block_layout.addWidget(preview_label, alignment=Qt.AlignmentFlag.AlignTop)

            # Правая сторона - Текст и кнопка "Купить"
            right_layout = QVBoxLayout()
            right_layout.setSpacing(8)  # Отступ между элементами
            right_layout.setContentsMargins(0, 0, 0, 0)

            # Контейнер для текста с прозрачным фоном
            text_container = QWidget()
            text_container.setStyleSheet("background-color: rgba(255, 255, 255, 0);")  # Прозрачный фон

            text_layout = QVBoxLayout(text_container)

            # Название и цена в горизонтальном макете
            name_price_layout = QHBoxLayout()

            # Название скина
            name_label = QLabel(name)
            name_label.setStyleSheet(f"color:#fff; font-weight:bold; font-size:{s(14)}px; border:none;")
            name_label.setWordWrap(True)
            name_price_layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignLeft)

            # Цена скина
            price_label = QLabel(price)  # Отображаем цену напрямую без символа рубля
            price_label.setStyleSheet(f"color:#ffd700; font-weight:bold; font-size:{s(14)}px; border:none;")
            price_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            name_price_layout.addWidget(price_label, alignment=Qt.AlignmentFlag.AlignRight)

            text_layout.addLayout(name_price_layout)

            # Описание скина
            desc_label = QLabel(description)
            desc_label.setStyleSheet(f"color:#ccc; font-size:{s(12)}px; border:none;")
            desc_label.setWordWrap(True)
            desc_label.adjustSize()
            text_layout.addWidget(desc_label, alignment=Qt.AlignmentFlag.AlignLeft)

            # Строка анимаций
            anim_label = QLabel(anim_str)
            anim_label.setStyleSheet(f"color:#aaa; font-size:{s(12)}px; border:none;")
            anim_label.setWordWrap(True)
            text_layout.addWidget(anim_label, alignment=Qt.AlignmentFlag.AlignLeft)

            # Добавляем текстовый контейнер в правый макет
            right_layout.addWidget(text_container, alignment=Qt.AlignmentFlag.AlignTop)

            # Кнопка "Купить" с уменьшенными размерами и эффектом наведения
            buy_btn = QPushButton("Купить")
            buy_btn.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
            buy_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#444; color:#fff; border:none; border-radius:4px;
                    padding:{s(4)}px {s(8)}px; font-size:{s(12)}px;
                    min-height: {s(24)}px;  /* Уменьшенная минимальная высота */
                    min-width: {s(60)}px;   /* Уменьшенная минимальная ширина */
                }}
                QPushButton:hover {{
                    background:#555;
                }}
                QPushButton:pressed {{
                    background:#666;
                }}
            """)
            buy_btn.clicked.connect(lambda _, sid=skin_id: self.buy_skin(sid))
            buy_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            right_layout.addWidget(buy_btn, alignment=Qt.AlignmentFlag.AlignRight)

            # Добавляем stretch, чтобы кнопка "Купить" располагалась внизу
            right_layout.addStretch()

            # Добавляем текстовый блок и кнопку в правую часть
            block_layout.addLayout(right_layout)

            # Добавляем карточку в layout магазина с выравниванием по верхнему краю и растягиванием
            self.store_layout.addWidget(block, alignment=Qt.AlignmentFlag.AlignTop)

    def buy_skin(self, skin_id):
        """
        Открываем страницу браузера для «покупки».
        После покупки пользователь вернётся на /download?token=..., 
        но приложение само не знает, успешна ли покупка.
        
        Для демонстрации сделаем отдельный 'complete_purchase' - 
        эмуляцию успешной покупки, где скачиваем файл и сообщаем пользователю.
        """
        url = f"http://127.0.0.1:5000/buy?skin_id={skin_id}"
        webbrowser.open(url)

        # Дополнительно можем запустить таймер, который через N секунд проверит условно 
        # 'был ли куплен?' - тут упрощённо демонстрируем:
        QTimer.singleShot(5000, lambda: self.complete_purchase(skin_id))

    def complete_purchase(self, skin_id):
        """
        Эмуляция 'успешной покупки': скачиваем файл и кладём в user skin folder.
        Путь к папке: self.duck.skin_folder (или другой).
        Показываем благодарность.
        """
        # В реальности нужно как-то получить токен для /download. 
        # Тут - фейк: cразу качаем "skins/<skin_id>.zip" - 
        # Или, например, берём последнюю запись JSON, ищем zip_path...
        # Для упрощения: качаем /download_direct?skin_id=... (доп. endpoint)
        
        # Если у нас уже есть zip_path в available-skins.json, 
        # можем запросить "http://127.0.0.1:5000/download_direct?skin_id=skin_id"

        # Создадим фейковый запрос:
        try:
            r = requests.get(f"http://127.0.0.1:5000/download_direct?skin_id={skin_id}", timeout=5)
            if r.status_code != 200:
                return  # Если не 200, считаем, что не скачалось

            # Кладём файл в user skin folder
            user_folder = self.duck.skin_folder or os.path.expanduser("~/my_skins")
            os.makedirs(user_folder, exist_ok=True)

            zip_path = os.path.join(user_folder, f"{skin_id}.zip")
            with open(zip_path, "wb") as f:
                f.write(r.content)

            # Показываем пользователю окошко "спасибо"
            QMessageBox.information(
                self,
                "Спасибо!",
                ("Спасибо, что поддержали приложение и купили скин.\n"
                 "Скин загружен в вашу папку скинов, отправлен на почту и "
                 "доступен для скачивания в браузере!")
            )
        except Exception as e:
            print("complete_purchase error:", e)

    def handle_frame_change(self, movie, label):
        pixmap = movie.currentPixmap()
        if not pixmap.isNull():
            image = pixmap.toImage()
            scaled_image = image.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            label.setPixmap(QPixmap.fromImage(scaled_image))

    def update_mic_preview(self):
        if hasattr(self, 'duck') and hasattr(self.duck, 'current_volume'):
            self.mic_level_preview.setValue(int(self.duck.current_volume))
        else:
            logging.warning("Duck object or current_volume attribute is missing.")
