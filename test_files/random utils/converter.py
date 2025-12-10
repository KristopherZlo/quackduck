import os
import threading
import zipfile
from tkinter import Tk, Button, Label, filedialog, messagebox, Listbox, MULTIPLE, END
from tkinter import ttk
from pydub import AudioSegment

class AudioConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("Конвертер Аудио в WAV")
        master.geometry("600x400")
        master.resizable(False, False)

        # Список выбранных файлов
        self.file_list = []

        # Кнопка для добавления файлов
        self.add_button = Button(master, text="Добавить файлы", command=self.add_files)
        self.add_button.pack(pady=10)

        # Список отображения выбранных файлов
        self.listbox = Listbox(master, selectmode=MULTIPLE, width=80)
        self.listbox.pack(pady=10)

        # Кнопка для начала конвертации
        self.convert_button = Button(master, text="Форматировать", command=self.start_conversion)
        self.convert_button.pack(pady=10)

        # Индикатор прогресса
        self.progress = ttk.Progressbar(master, orient='horizontal', length=400, mode='determinate')
        self.progress.pack(pady=10)

        # Метка для отображения состояния
        self.status_label = Label(master, text="")
        self.status_label.pack(pady=10)

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите аудиофайлы",
            filetypes=(("Audio Files", "*.mp3 *.ogg *.wav *.flac *.aac *.m4a"), ("All Files", "*.*"))
        )
        for file in files:
            if file not in self.file_list:
                self.file_list.append(file)
                self.listbox.insert(END, file)

    def start_conversion(self):
        if not self.file_list:
            messagebox.showwarning("Предупреждение", "Пожалуйста, добавьте файлы для конвертации.")
            return

        # Выбор папки для сохранения ZIP-архива
        save_dir = filedialog.askdirectory(title="Выберите папку для сохранения ZIP-архива")
        if not save_dir:
            return

        # Запуск процесса конвертации в отдельном потоке
        threading.Thread(target=self.convert_files, args=(save_dir,), daemon=True).start()

    def convert_files(self, save_dir):
        try:
            self.convert_button.config(state='disabled')
            self.add_button.config(state='disabled')
            self.status_label.config(text="Начинается конвертация...")
            total_files = len(self.file_list)
            self.progress['maximum'] = total_files
            converted_files = []

            for idx, file_path in enumerate(self.file_list, start=1):
                self.status_label.config(text=f"Конвертация: {os.path.basename(file_path)}")
                self.progress['value'] = idx - 1
                self.master.update_idletasks()

                # Определение формата файла
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in ['.mp3', '.ogg', '.flac', '.aac', '.m4a', '.wav']:
                    messagebox.showerror("Ошибка", f"Неподдерживаемый формат файла: {file_ext}")
                    continue

                # Конвертация в WAV
                audio = AudioSegment.from_file(file_path)
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                wav_path = os.path.join(save_dir, f"{base_name}.wav")
                audio.export(wav_path, format="wav")
                converted_files.append(wav_path)

            # Создание ZIP-архива
            zip_path = os.path.join(save_dir, "converted_files.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in converted_files:
                    zipf.write(file, arcname=os.path.basename(file))

            # Очистка сконвертированных файлов, если нужно
            # for file in converted_files:
            #     os.remove(file)

            self.progress['value'] = total_files
            self.status_label.config(text="Конвертация завершена!")
            messagebox.showinfo("Успех", f"Файлы успешно конвертированы и упакованы в {zip_path}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")
        finally:
            self.convert_button.config(state='normal')
            self.add_button.config(state='normal')
            self.progress['value'] = 0

def main():
    root = Tk()
    app = AudioConverterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
