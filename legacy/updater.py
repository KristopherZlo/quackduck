import sys
import os
import time
import shutil
import traceback

def main():
    # Get the paths from command-line arguments
    app_dir = sys.argv[1]
    extracted_path = sys.argv[2]

    # Wait for the main application to exit
    time.sleep(2)  # Wait a bit to ensure the main app has closed

    log_file = os.path.join(extracted_path, 'update_log.txt')

    try:
        with open(log_file, 'w') as log:
            log.write(f"Starting update process...\n")

            # Paths to old and new files
            internal_folder = os.path.join(app_dir, "_internal")
            exe_file = os.path.join(app_dir, "quackduck.exe")

            new_internal_folder = os.path.join(extracted_path, "_internal")
            new_exe_file = os.path.join(extracted_path, "quackduck.exe")

            log.write(f"Deleting old files...\n")

            # Delete old files
            if os.path.exists(internal_folder):
                shutil.rmtree(internal_folder)
                log.write(f"Deleted old internal folder.\n")
            else:
                log.write(f"Old internal folder not found.\n")

            if os.path.exists(exe_file):
                os.remove(exe_file)
                log.write(f"Deleted old executable.\n")
            else:
                log.write(f"Old executable not found.\n")

            # Copy new files
            log.write(f"Copying new files...\n")
            if os.path.exists(new_internal_folder):
                shutil.copytree(new_internal_folder, internal_folder)
                log.write(f"Copied new internal folder.\n")
            else:
                log.write(f"New '_internal' folder not found in the archive.\n")
                sys.exit(1)

            if os.path.exists(new_exe_file):
                shutil.copy2(new_exe_file, exe_file)
                log.write(f"Copied new executable.\n")
            else:
                log.write(f"New 'quackduck.exe' not found in the archive.\n")
                sys.exit(1)

            # Clean up the extracted update files
            shutil.rmtree(extracted_path)
            log.write(f"Cleaned up extracted files.\n")

            # Restart the main application
            log.write(f"Restarting application...\n")
            os.startfile(exe_file)

    except Exception as e:
        with open(log_file, 'a') as log:
            log.write(f"Failed to update application: {e}\n")
            traceback.print_exc(file=log)
        sys.exit(1)

if __name__ == '__main__':
    main()
