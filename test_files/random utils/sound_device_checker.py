import sounddevice as sd
import numpy as np
import sys
import locale

def list_input_devices():
    print("Доступные устройства ввода:")
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            device_name = device['name']
            print(f"Индекс {idx}: {device_name}")
            print(f"  Max Input Channels: {device['max_input_channels']}")
            print(f"  Default Sample Rate: {device['default_samplerate']}\n")

def audio_callback(indata, frames, time, status):
    if status:
        print(f"Status: {status}", file=sys.stderr)
    # Предполагаем, что данные моно
    volume_norm = np.linalg.norm(indata) * 10
    volume_percentage = min(int(volume_norm), 100)
    print(f"Текущий уровень громкости: {volume_percentage}%", end='\r')

def main(device_index=None):
    try:
        if device_index is not None:
            device_info = sd.query_devices(device_index, 'input')
        else:
            device_info = sd.query_devices(sd.default.device[0], 'input')
        sample_rate = int(device_info['default_samplerate'])
        channels = device_info['max_input_channels']
        print(f"Используется устройство: {device_info['name']}")
        print(f"Частота дискретизации: {sample_rate} Гц")
        print(f"Количество каналов: {channels}\n")
    except Exception as e:
        print(f"Ошибка получения информации об устройстве: {e}")
        return

    print("Запись звука... Нажмите Ctrl+C для остановки.\n")

    try:
        with sd.InputStream(device=device_index,
                            channels=channels,
                            samplerate=sample_rate,
                            callback=audio_callback):
            sd.sleep(int(1e9))  # Бесконечный цикл
    except KeyboardInterrupt:
        print("\nОстановка записи.")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    # Установка системной локали для корректного отображения кириллицы
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        pass  # Если установка локали не удалась, продолжаем

    list_input_devices()
    try:
        device_input = input("Введите индекс устройства для использования: ")
        device_index = int(device_input)
    except ValueError:
        print("Некорректный ввод. Используется устройство по умолчанию.\n")
        device_index = None

    main(device_index)
