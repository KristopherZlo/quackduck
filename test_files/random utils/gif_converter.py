import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QLabel, QProgressBar, QListWidget, QMessageBox,
    QComboBox, QLineEdit, QDialog, QGridLayout, QFrame, QSizePolicy, QGraphicsRectItem, QGraphicsView, QGraphicsScene, QGraphicsItem
)
from PyQt5.QtGui import QMovie, QPixmap, QPainter, QColor, QIcon, QCursor, QPen, QIntValidator
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QPoint, QRectF
from PIL import Image
import imageio

class Worker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    info = pyqtSignal(str)

    def __init__(self, files, resize_option, custom_size, crop_rect, watermark_path, watermark_pos, watermark_size, output_dir):
        super().__init__()
        self.files = files
        self.resize_option = resize_option      # Tuple (width, height) or None
        self.custom_size = custom_size          # Tuple (width, height) or None
        self.crop_rect = crop_rect              # Tuple (left, upper, right, lower) or None
        self.watermark_path = watermark_path
        self.watermark_pos = watermark_pos      # Tuple (x, y)
        self.watermark_size = watermark_size    # Tuple (width, height)
        self.output_dir = output_dir

    def run(self):
        total = len(self.files)
        for index, file in enumerate(self.files):
            try:
                self.info.emit(f"Обработка: {os.path.basename(file)}")
                self.process_gif(file)
            except Exception as e:
                self.info.emit(f"Ошибка при обработке {file}: {str(e)}")
            self.progress.emit(int(((index + 1) / total) * 100))
        self.finished.emit()

    def process_gif(self, filepath):
        # Открываем GIF и получаем информацию о нём
        gif = imageio.mimread(filepath)
        if not gif:
            self.info.emit(f"Файл {filepath} не содержит кадров.")
            return

        frames = []
        original_size = gif[0].shape[1], gif[0].shape[0]  # (width, height)

        # Определяем размеры ресайза на основе оригинального размера
        if self.resize_option:
            target_size = self.resize_option
        elif self.custom_size:
            target_size = self.custom_size
        else:
            target_size = original_size

        for frame in gif:
            img = Image.fromarray(frame)

            # Обрезка
            if self.crop_rect:
                img = img.crop(self.crop_rect)

            # Ресайз
            if self.resize_option or self.custom_size:
                img = img.resize(target_size, Image.ANTIALIAS)

            # Добавление водяного знака
            if self.watermark_path and os.path.exists(self.watermark_path):
                try:
                    watermark = Image.open(self.watermark_path).convert("RGBA")
                    # Изменение размера водяного знака
                    watermark = watermark.resize(self.watermark_size, Image.ANTIALIAS)

                    # Позиция водяного знака
                    position = self.watermark_pos
                    img = img.convert("RGBA")
                    img.paste(watermark, position, watermark)
                    img = img.convert("P", palette=Image.ADAPTIVE)
                except Exception as e:
                    self.info.emit(f"Ошибка при добавлении водяного знака к {filepath}: {str(e)}")

            frames.append(img)

        # Сохранение нового GIF
        output_path = os.path.join(self.output_dir, os.path.basename(filepath))
        try:
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                loop=0,
                optimize=True,
                duration=100
            )
            self.info.emit(f"Сохранено: {output_path}")
        except Exception as e:
            self.info.emit(f"Ошибка при сохранении {output_path}: {str(e)}")

class ResizableCropRectItem(QGraphicsRectItem):
    def __init__(self, rect, parent=None):
        super().__init__(rect, parent)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.setBrush(QColor(0, 0, 0, 50))
        self.setPen(QPen(QColor(255, 255, 255), 2, Qt.DashLine))
        self.setAcceptHoverEvents(True)
        self.handle_size = 8.0
        self.handles = {}
        self.update_handles_pos()

    def update_handles_pos(self):
        # Define handles at corners and edges
        s = self.handle_size
        rect = self.rect()
        self.handles = {
            'top_left': QRectF(rect.topLeft().x() - s / 2, rect.topLeft().y() - s / 2, s, s),
            'top_right': QRectF(rect.topRight().x() - s / 2, rect.topRight().y() - s / 2, s, s),
            'bottom_left': QRectF(rect.bottomLeft().x() - s / 2, rect.bottomLeft().y() - s / 2, s, s),
            'bottom_right': QRectF(rect.bottomRight().x() - s / 2, rect.bottomRight().y() - s / 2, s, s),
            'top': QRectF(rect.center().x() - s / 2, rect.top() - s / 2, s, s),
            'bottom': QRectF(rect.center().x() - s / 2, rect.bottom() - s / 2, s, s),
            'left': QRectF(rect.left() - s / 2, rect.center().y() - s / 2, s, s),
            'right': QRectF(rect.right() - s / 2, rect.center().y() - s / 2, s, s),
        }

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(QColor(255, 255, 255))
        for handle in self.handles.values():
            painter.drawRect(handle)

    def hoverMoveEvent(self, event):
        cursor = Qt.ArrowCursor
        for handle, rect in self.handles.items():
            if rect.contains(event.pos()):
                if 'left' in handle or 'right' in handle:
                    cursor = Qt.SizeHorCursor
                elif 'top' in handle or 'bottom' in handle:
                    cursor = Qt.SizeVerCursor
                elif 'top_left' in handle or 'bottom_right' in handle:
                    cursor = Qt.SizeFDiagCursor
                elif 'top_right' in handle or 'bottom_left' in handle:
                    cursor = Qt.SizeBDiagCursor
                break
        self.setCursor(cursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

class PreviewWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.gif_path = None
        self.movie = None
        self.pixmap_item = None
        self.crop_rect_item = None
        self.setRenderHint(QPainter.Antialiasing)
        self.setAlignment(Qt.AlignCenter)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setStyleSheet("background-color: #1e1e1e;")

    def load_gif(self, filepath):
        self.scene().clear()
        self.movie = QMovie(filepath)
        if not self.movie.isValid():
            QMessageBox.warning(self, "Ошибка", f"Невозможно загрузить файл: {filepath}")
            return
        self.gif_path = filepath
        self.movie.frameChanged.connect(self.update_frame)
        self.movie.start()
        self.current_pixmap = self.movie.currentPixmap()
        self.pixmap_item = self.scene().addPixmap(self.current_pixmap)
        self.scene().setSceneRect(self.pixmap_item.boundingRect())
        self.setSceneRect(self.scene().itemsBoundingRect())
        self.setup_crop_rect()

    def update_frame(self, frame_number):
        if self.pixmap_item:
            self.pixmap_item.setPixmap(self.movie.currentPixmap())

    def setup_crop_rect(self):
        if self.pixmap_item:
            # Инициализируем область обрезки как 80% от размера изображения
            pixmap = self.pixmap_item.pixmap()
            width = pixmap.width()
            height = pixmap.height()
            crop_width = width * 0.8
            crop_height = height * 0.8
            x = (width - crop_width) / 2
            y = (height - crop_height) / 2
            self.crop_rect = QRectF(x, y, crop_width, crop_height)
            if self.crop_rect_item:
                self.scene().removeItem(self.crop_rect_item)
            self.crop_rect_item = ResizableCropRectItem(self.crop_rect)
            self.scene().addItem(self.crop_rect_item)

    def get_crop_rect_original(self):
        # Получаем координаты области обрезки в оригинальных размерах
        if not self.crop_rect_item or not self.pixmap_item:
            return None
        # Получаем оригинальный размер изображения
        original_size = self.pixmap_item.pixmap().size()
        # Получаем размер сцены
        scene_rect = self.scene().sceneRect()
        # Получаем область обрезки
        crop_rect = self.crop_rect_item.rect()
        # Вычисляем масштабные коэффициенты
        scale_x = original_size.width() / scene_rect.width()
        scale_y = original_size.height() / scene_rect.height()
        # Вычисляем область обрезки в оригинальных пикселях
        left = int(crop_rect.x() * scale_x)
        top = int(crop_rect.y() * scale_y)
        right = int((crop_rect.x() + crop_rect.width()) * scale_x)
        bottom = int((crop_rect.y() + crop_rect.height()) * scale_y)
        return (left, top, right, bottom)

class GifProcessor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GIF Утилита")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #2b2b2b; color: #ffffff;")

        self.selected_files = []
        self.watermark_path = ""
        self.watermark_label = None
        self.watermark_size = (100, 100)  # Default size

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()

        # Левая панель: управление
        control_layout = QVBoxLayout()
        control_layout.setSpacing(15)
        control_layout.setContentsMargins(20, 20, 20, 20)

        # Кнопки выбора файлов и водяного знака
        btn_select_files = QPushButton("Выбрать GIF-файлы")
        btn_select_files.clicked.connect(self.select_files)
        btn_select_watermark = QPushButton("Выбрать водяной знак")
        btn_select_watermark.clicked.connect(self.select_watermark)
        control_layout.addWidget(btn_select_files)
        control_layout.addWidget(btn_select_watermark)

        # Список выбранных файлов
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background-color: #3c3c3c; color: #ffffff;")
        self.list_widget.itemClicked.connect(self.preview_gif)
        control_layout.addWidget(QLabel("Выбранные GIF:"))
        control_layout.addWidget(self.list_widget)

        # Информация о текущей картинке
        self.image_info_label = QLabel("Информация о картинке")
        self.image_info_label.setStyleSheet("background-color: #3c3c3c; padding: 5px;")
        self.image_info_label.setWordWrap(True)
        control_layout.addWidget(self.image_info_label)

        # Настройки ресайза
        resize_group = QFrame()
        resize_layout = QVBoxLayout()

        resize_layout.addWidget(QLabel("Размер:"))
        self.resize_combo = QComboBox()
        self.resize_combo.addItem("Исходный размер")
        self.resize_combo.addItem("Другое...")
        self.resize_combo.currentIndexChanged.connect(self.resize_option_changed)
        resize_layout.addWidget(self.resize_combo)

        self.custom_resize_input = QHBoxLayout()
        self.custom_width = QLineEdit()
        self.custom_width.setPlaceholderText("Ширина")
        self.custom_width.setValidator(QIntValidator(1, 10000))
        self.custom_height = QLineEdit()
        self.custom_height.setPlaceholderText("Высота")
        self.custom_height.setValidator(QIntValidator(1, 10000))
        self.custom_resize_input.addWidget(QLabel("Ширина:"))
        self.custom_resize_input.addWidget(self.custom_width)
        self.custom_resize_input.addWidget(QLabel("Высота:"))
        self.custom_resize_input.addWidget(self.custom_height)
        self.custom_resize_input_widget = QWidget()
        self.custom_resize_input_widget.setLayout(self.custom_resize_input)
        self.custom_resize_input_widget.hide()
        resize_layout.addWidget(self.custom_resize_input_widget)

        resize_group.setLayout(resize_layout)
        control_layout.addWidget(resize_group)

        # Интерактивный Crop
        crop_group = QFrame()
        crop_layout = QVBoxLayout()
        btn_crop = QPushButton("Настроить обрезку")
        btn_crop.clicked.connect(self.enable_crop_mode)
        crop_layout.addWidget(btn_crop)
        crop_group.setLayout(crop_layout)
        control_layout.addWidget(crop_group)

        # Кнопка обработки
        self.btn_process = QPushButton("Обработать")
        self.btn_process.clicked.connect(self.process_files)
        control_layout.addWidget(self.btn_process)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #05B8CC;
                width: 20px;
            }
        """)
        control_layout.addWidget(self.progress_bar)

        # Информация о процессе
        self.info_label = QLabel("Информация о процессе")
        self.info_label.setStyleSheet("background-color: #3c3c3c; padding: 5px;")
        self.info_label.setWordWrap(True)
        control_layout.addWidget(self.info_label)

        control_layout.addStretch()
        main_layout.addLayout(control_layout, 3)

        # Правая панель: превью
        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(10)
        preview_layout.setContentsMargins(20, 20, 20, 20)

        self.preview_info_label = QLabel("Информация о текущем GIF")
        self.preview_info_label.setStyleSheet("background-color: #3c3c3c; padding: 5px;")
        self.preview_info_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_info_label)

        self.preview_widget = PreviewWidget()
        preview_layout.addWidget(QLabel("Превью:"))
        preview_layout.addWidget(self.preview_widget)
        main_layout.addLayout(preview_layout, 7)

        self.setLayout(main_layout)

    def resize_option_changed(self, index):
        if self.resize_combo.currentText() == "Другое...":
            self.custom_resize_input_widget.show()
        else:
            self.custom_resize_input_widget.hide()

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выбрать GIF-файлы", "", "GIF Files (*.gif)"
        )
        if files:
            self.selected_files = files
            self.list_widget.clear()
            for file in files:
                self.list_widget.addItem(file)
            # Очистить превью и информацию
            self.preview_widget.scene().clear()
            self.preview_info_label.setText("Информация о текущем GIF")
            self.image_info_label.setText("Информация о картинке")

    def select_watermark(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Выбрать водяной знак", "", "Image Files (*.png *.jpg *.bmp)"
        )
        if file:
            self.watermark_path = file
            self.info_label.setText(f"Водяной знак: {os.path.basename(file)}")
            pixmap = QPixmap(file)
            if pixmap.isNull():
                QMessageBox.warning(self, "Ошибка", "Невозможно загрузить водяной знак.")
                return
            scaled_pixmap = pixmap.scaled(self.watermark_size[0], self.watermark_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # Добавление водяного знака на превью
            self.watermark_label = QLabel(self.preview_widget)
            self.watermark_label.setPixmap(scaled_pixmap)
            self.watermark_label.setScaledContents(True)
            self.watermark_label.setFixedSize(scaled_pixmap.size())
            self.watermark_label.setStyleSheet("background-color: rgba(0,0,0,0);")
            self.watermark_label.setCursor(QCursor(Qt.OpenHandCursor))
            self.watermark_label.move(
                self.preview_widget.width() - self.watermark_label.width() - 10,
                self.preview_widget.height() - self.watermark_label.height() - 10
            )
            self.watermark_label.show()
            # Реализация перемещения водяного знака
            self.watermark_label.mousePressEvent = self.start_move_watermark
            self.watermark_label.mouseMoveEvent = self.move_watermark
            self.watermark_label.mouseReleaseEvent = self.end_move_watermark

    def start_move_watermark(self, event):
        if event.button() == Qt.LeftButton:
            self.watermark_label.dragging = True
            self.watermark_label.offset = event.pos()

    def move_watermark(self, event):
        if hasattr(self.watermark_label, 'dragging') and self.watermark_label.dragging:
            new_pos = self.watermark_label.mapToParent(event.pos() - self.watermark_label.offset)
            # Ограничиваем перемещение внутри превью
            new_x = max(0, min(new_pos.x(), self.preview_widget.width() - self.watermark_label.width()))
            new_y = max(0, min(new_pos.y(), self.preview_widget.height() - self.watermark_label.height()))
            self.watermark_label.move(new_x, new_y)

    def end_move_watermark(self, event):
        if event.button() == Qt.LeftButton:
            self.watermark_label.dragging = False

    def preview_gif(self, item):
        filepath = item.text()
        self.preview_widget.load_gif(filepath)
        # Извлекаем информацию о GIF
        try:
            gif = imageio.mimread(filepath)
            if not gif:
                self.preview_info_label.setText("Файл не содержит кадров.")
                return
            frames = len(gif)
            original_width, original_height = gif[0].shape[1], gif[0].shape[0]
            self.preview_info_label.setText(
                f"Файл: {os.path.basename(filepath)}\n"
                f"Размер: {original_width}x{original_height} пикселей\n"
                f"Кадров: {frames}"
            )
            self.image_info_label.setText(
                f"Исходный размер: {original_width}x{original_height} пикселей\n"
                f"Кадров: {frames}"
            )
            # Обновляем resize_combo с реальными размерами
            self.populate_resize_options(original_width, original_height)
        except Exception as e:
            self.preview_info_label.setText(f"Ошибка: {str(e)}")
            self.image_info_label.setText(f"Ошибка: {str(e)}")

    def populate_resize_options(self, width, height):
        self.resize_combo.blockSignals(True)
        self.resize_combo.clear()
        self.resize_combo.addItem("Исходный размер")
        # Добавляем несколько предустановленных размеров
        predefined_sizes = [
            (1920, 1080),
            (1280, 720),
            (854, 480),
            (640, 360),
            (426, 240)
        ]
        for w, h in predefined_sizes:
            if w <= width and h <= height:
                self.resize_combo.addItem(f"{w}x{h}")
        self.resize_combo.addItem("Другое...")
        self.resize_combo.blockSignals(False)

    def enable_crop_mode(self):
        QMessageBox.information(self, "Информация", "Используйте мышь для перемещения и изменения размеров области обрезки в превью.")

    def process_files(self):
        if not self.selected_files:
            QMessageBox.warning(self, "Предупреждение", "Нет выбранных файлов для обработки.")
            return

        output_dir = QFileDialog.getExistingDirectory(
            self, "Выбрать папку для сохранения", ""
        )
        if not output_dir:
            return

        # Определение размера ресайза
        resize_option = None
        custom_size = None
        resize_text = self.resize_combo.currentText()
        if resize_text == "Исходный размер":
            pass  # Не изменяем размер
        elif resize_text == "Другое...":
            try:
                width = int(self.custom_width.text())
                height = int(self.custom_height.text())
                if width <= 0 or height <= 0:
                    raise ValueError
                custom_size = (width, height)
            except:
                QMessageBox.warning(self, "Ошибка", "Введите корректные размеры.")
                return
        else:
            try:
                width, height = map(int, resize_text.split('x'))
                resize_option = (width, height)
            except:
                QMessageBox.warning(self, "Ошибка", "Некорректный формат размера.")
                return

        # Получаем область обрезки
        crop_rect = self.preview_widget.get_crop_rect_original()

        # Водяной знак позиция и размер
        watermark_pos = (0, 0)
        watermark_size = self.watermark_size
        if hasattr(self, 'watermark_label') and self.watermark_label.isVisible():
            watermark_pos = (self.watermark_label.x(), self.watermark_label.y())
            watermark_size = (self.watermark_label.width(), self.watermark_label.height())

        self.thread = Worker(
            self.selected_files,
            resize_option,
            custom_size,
            crop_rect,
            self.watermark_path,
            watermark_pos,
            watermark_size,
            output_dir
        )
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.processing_finished)
        self.thread.info.connect(self.update_info)
        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def processing_finished(self):
        QMessageBox.information(self, "Готово", "Все файлы обработаны.")
        self.progress_bar.setValue(0)
        self.info_label.setText("Обработка завершена.")

    def update_info(self, message):
        self.info_label.setText(message)

def main():
    app = QApplication(sys.argv)
    window = GifProcessor()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
