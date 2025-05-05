import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def start_file_watcher(app, project_path):
    observer = None
    if project_path and os.path.exists(project_path) and os.path.exists(os.path.join(project_path, '.git')):
        observer = Observer()
        event_handler = FileChangeHandler(app)
        observer.schedule(event_handler, project_path, recursive=True)
        observer.start()
    return observer

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_modified(self, event):
        if not event.is_directory:
            self.app.update_opening_hours()
            self.app.update_code_analysis()
            self.app.update_charts()

    def on_created(self, event):
        if not event.is_directory:
            self.app.update_opening_hours()
            self.app.update_code_analysis()
            self.app.update_charts()

    def on_deleted(self, event):
        if not event.is_directory:
            self.app.update_opening_hours()
            self.app.update_code_analysis()
            self.app.update_charts()