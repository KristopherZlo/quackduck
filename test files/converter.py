import os
import threading
import zipfile
from tkinter import Tk, Button, Label, filedialog, messagebox, Listbox, MULTIPLE, END
from tkinter import ttk
from pydub import AudioSegment

class AudioConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("Audio to WAV Converter")
        master.geometry("600x400")
        master.resizable(False, False)

        # List of selected files
        self.file_list = []

        # Button for adding files
        self.add_button = Button(master, text="Add files", command=self.add_files)
        self.add_button.pack(pady=10)

        # Display list of selected files
        self.listbox = Listbox(master, selectmode=MULTIPLE, width=80)
        self.listbox.pack(pady=10)

        # Button to start conversion
        self.convert_button = Button(master, text="Format", command=self.start_conversion)
        self.convert_button.pack(pady=10)

        # Progress indicator
        self.progress = ttk.Progressbar(master, orient='horizontal', length=400, mode='determinate')
        self.progress.pack(pady=10)

        # Label to display the state
        self.status_label = Label(master, text="")
        self.status_label.pack(pady=10)

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Select audio files",
            filetypes=(("Audio Files", "*.mp3 *.ogg *.wav *.flac *.aac *.m4a"), ("All Files", "*.*"))
        )
        for file in files:
            if file not in self.file_list:
                self.file_list.append(file)
                self.listbox.insert(END, file)

    def start_conversion(self):
        if not self.file_list:
            messagebox.showwarning("Warning", "Please add files for conversion.")
            return

        # Select a folder to save the ZIP archive
        save_dir = filedialog.askdirectory(title="Select a folder to save the ZIP archive")
        if not save_dir:
            return

        # Launch the conversion process in a separate thread
        threading.Thread(target=self.convert_files, args=(save_dir,), daemon=True).start()

    def convert_files(self, save_dir):
        try:
            self.convert_button.config(state='disabled')
            self.add_button.config(state='disabled')
            self.status_label.config(text="Conversion begins...")
            total_files = len(self.file_list)
            self.progress['maximum'] = total_files
            converted_files = []

            for idx, file_path in enumerate(self.file_list, start=1):
                self.status_label.config(text=f"Conversion: {os.path.basename(file_path)}")
                self.progress['value'] = idx - 1
                self.master.update_idletasks()

                # File format definition
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in ['.mp3', '.ogg', '.flac', '.aac', '.m4a', '.wav']:
                    messagebox.showerror("Error", f"Unsupported file format: {file_ext}")
                    continue

                # Convert to WAV
                audio = AudioSegment.from_file(file_path)
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                wav_path = os.path.join(save_dir, f"{base_name}.wav")
                audio.export(wav_path, format="wav")
                converted_files.append(wav_path)

            # Create a ZIP archive
            zip_path = os.path.join(save_dir, "converted_files.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in converted_files:
                    zipf.write(file, arcname=os.path.basename(file))

            # Cleaning up converted files if needed
            # for file in converted_files:
            #     os.remove(file)

            self.progress['value'] = total_files
            self.status_label.config(text="Conversion complete!")
            messagebox.showinfo("Success", f"Files have been successfully converted and packed into {zip_path}")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
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
