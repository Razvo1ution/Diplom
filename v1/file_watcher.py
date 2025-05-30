from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt5.QtCore import QObject, pyqtSignal
import os
import time
import logging

# Настройка логирования
logging.basicConfig(filename='devmetrics.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class UpdateSignal(QObject):
    update_needed = pyqtSignal()

def start_file_watcher(app, project_path):
    observer = None
    if project_path and os.path.exists(project_path) and os.path.exists(os.path.join(project_path, '.git')):
        observer = Observer()
        signal = UpdateSignal()
        signal.update_needed.connect(app.update_opening_hours)
        signal.update_needed.connect(app.update_code_analysis)
        signal.update_needed.connect(app.update_charts)
        event_handler = FileChangeHandler(signal)
        observer.schedule(event_handler, project_path, recursive=True)
        observer.start()
        logging.info(f"File watcher started for {project_path}")
    else:
        logging.warning(f"File watcher not started: invalid project path {project_path}")
    return observer

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, signal):
        self.signal = signal
        self.last_event_time = 0
        self.debounce_interval = 1  # Секунды между событиями

    def on_modified(self, event):
        if not event.is_directory:
            self.debounce_and_emit(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self.debounce_and_emit(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.debounce_and_emit(event.src_path)

    def debounce_and_emit(self, path):
        current_time = time.time()
        if current_time - self.last_event_time >= self.debounce_interval:
            logging.info(f"Emitting update signal for file change: {path}")
            self.signal.update_needed.emit()
            self.last_event_time = current_time