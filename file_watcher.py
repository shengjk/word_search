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
        self.watched_directory = None

    def start_watching(self, directory):
        if self.watching and self.watched_directory == directory:
            return

        if self.watching:
            self.stop_watching()

        # 先初始化handler
        self.handler = DocFileHandler(self)
        
        # 扫描目录下的所有文件
        self.scan_existing_files(directory)

        self.observer = Observer()
        self.observer.schedule(self.handler, directory, recursive=True)
        self.observer.start()
        self.watching = True
        self.watched_directory = directory

    def scan_existing_files(self, directory):
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file_path)
                if ext.lower() in [".docx", ".pdf"]:
                    self.handler.processed_files.add(file_path)

    def stop_watching(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.watching = False
            self.watched_directory = None

class DocFileHandler(FileSystemEventHandler):
    def __init__(self, watcher):
        super().__init__()
        self.watcher = watcher
        self.processed_files = set()
        self.is_processing = False

    def on_created(self, event):
        if event.is_directory or self.is_processing:
            return
            
        file_path = event.src_path
        if file_path in self.processed_files:
            return

        _, ext = os.path.splitext(file_path)
        
        if ext.lower() in [".docx", ".pdf"]:
            self.is_processing = True
            try:
                self.watcher.file_added.emit(file_path)
            finally:
                self.processed_files.add(file_path)
                self.is_processing = False
            self.is_processing = False