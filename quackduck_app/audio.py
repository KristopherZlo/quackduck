import logging

import numpy as np
import sounddevice as sd
from PyQt6 import QtCore


class MicrophoneListener(QtCore.QThread):
    """
    Background thread that measures microphone volume and emits a normalized value.
    """

    volume_signal = QtCore.pyqtSignal(int)

    def __init__(self, device_index=None, activation_threshold=10, parent=None):
        super().__init__(parent)
        self.device_index = device_index
        self.activation_threshold = activation_threshold
        self.running = True

    def run(self):
        def audio_callback(indata, frames, time, status):
            try:
                if status:
                    logging.warning("Status: %s", status)
                volume_norm = np.linalg.norm(indata) * 10
                volume_percentage = min(int(volume_norm), 100)
                self.volume_signal.emit(volume_percentage)
            except Exception as exc:
                logging.error("Error in audio_callback: %s", exc)

        try:
            with sd.InputStream(
                device=self.device_index,
                channels=1,
                samplerate=22050,
                blocksize=1024,
                callback=audio_callback,
            ):
                while self.running:
                    sd.sleep(200)
        except Exception as exc:
            logging.error("Error opening audio stream: %s", exc)
            self.running = False

    def stop(self):
        self.running = False
        self.wait()

    def update_settings(self, device_index=None, activation_threshold=None):
        if device_index is not None:
            self.device_index = device_index
        if activation_threshold is not None:
            self.activation_threshold = activation_threshold
