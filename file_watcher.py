from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt6.QtCore import QObject, pyqtSignal
import os
import time

class FileWatcher(QObject):
    file_added = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.observer = None
        self.handler = None
        self.watching = False

    def start_watching(self, directory):
        if self.watching:
            self.stop_watching()

        self.handler = DocFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(self.handler, directory, recursive=True)
        self.observer.start()
        self.watching = True

    def stop_watching(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.watching = False

class DocFileHandler(FileSystemEventHandler):
    def __init__(self, watcher):
        super().__init__()
        self.watcher = watcher
        self.last_event_time = 0
        self.cooldown = 1  # 冷却时间（秒）

    def on_created(self, event):
        if event.is_directory:
            return
            
        current_time = time.time()
        if current_time - self.last_event_time < self.cooldown:
            return

        file_path = event.src_path
        _, ext = os.path.splitext(file_path)
        
        if ext.lower() in [".docx", ".pdf"]:
            self.last_event_time = current_time
            self.watcher.file_added.emit(file_path)