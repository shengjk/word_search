import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, \
    QPushButton, QLineEdit, QLabel, QFileDialog, QTextEdit, QProgressBar
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QProgressBar, QTextEdit,
                             QFileDialog)
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor, QTextDocument
from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import docx
import os
import PyPDF2
from collections import defaultdict
import jieba
from difflib import get_close_matches

class DocumentScanner(QThread):
    progress_updated = pyqtSignal(int)
    scan_completed = pyqtSignal(tuple)

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.inverted_index = defaultdict(list)
        self.documents = []

    def build_inverted_index(self, doc_id, text):
        words = jieba.lcut(text.lower())
        word_positions = defaultdict(list)
        for pos, word in enumerate(words):
            word_positions[word].append(pos)
            self.inverted_index[word].append((doc_id, pos))
        return word_positions

    def run(self):
        self.documents = []
        self.inverted_index.clear()
        docx_files = list(Path(self.directory).rglob('*.docx'))
        pdf_files = list(Path(self.directory).rglob('*.pdf'))
        total_files = len(docx_files) + len(pdf_files)
        processed_files = 0

        for file_path in docx_files:
            try:
                doc = docx.Document(file_path)
                text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                doc_id = len(self.documents)
                word_positions = self.build_inverted_index(doc_id, text)
                self.documents.append({
                    'path': str(file_path),
                    'content': text,
                    'type': 'docx',
                    'word_positions': word_positions
                })
            except Exception as e:
                print(f"Error processing Word document {file_path}: {e}")

            processed_files += 1
            self.progress_updated.emit(int(processed_files / total_files * 100))

        for file_path in pdf_files:
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = '\n'.join([page.extract_text() for page in pdf_reader.pages])
                    doc_id = len(self.documents)
                    word_positions = self.build_inverted_index(doc_id, text)
                    self.documents.append({
                        'path': str(file_path),
                        'content': text,
                        'type': 'pdf',
                        'word_positions': word_positions
                    })
            except Exception as e:
                print(f"Error processing PDF {file_path}: {e}")

            processed_files += 1
            self.progress_updated.emit(int(processed_files / total_files * 100))

        self.scan_completed.emit((self.documents, self.inverted_index))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Word文档全文检索系统")
        self.setMinimumSize(800, 600)
        self.documents = []
        self.setup_ui()

    def setup_ui(self):
        # 创建主窗口部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建顶部控制栏
        control_layout = QHBoxLayout()
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText("选择文档所在文件夹（支持Word和PDF）")
        browse_button = QPushButton("浏览")
        browse_button.clicked.connect(self.browse_folder)
        control_layout.addWidget(self.folder_path)
        control_layout.addWidget(browse_button)

        # 创建搜索栏
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词")
        self.search_input.returnPressed.connect(self.search_documents)
        search_button = QPushButton("搜索")
        search_button.clicked.connect(self.search_documents)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)

        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        # 创建结果显示区域
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)

        # 添加所有组件到主布局
        layout.addLayout(control_layout)
        layout.addLayout(search_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.results_display)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.folder_path.setText(folder)
            self.scan_documents(folder)

    def scan_documents(self, folder):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.scanner = DocumentScanner(folder)
        self.scanner.progress_updated.connect(self.update_progress)
        self.scanner.scan_completed.connect(self.scan_finished)
        self.scanner.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def scan_finished(self, scan_result):
        self.documents, self.inverted_index = scan_result
        self.progress_bar.setVisible(False)
        docx_count = sum(1 for doc in self.documents if doc.get('type') == 'docx')
        pdf_count = sum(1 for doc in self.documents if doc.get('type') == 'pdf')
        self.results_display.setText(f"已扫描 {docx_count} 个Word文档和 {pdf_count} 个PDF文档")

    def search_documents(self):
        keyword = self.search_input.text().lower()
        if not keyword:
            return

        # 使用结巴分词处理搜索关键词
        keywords = jieba.lcut(keyword)
        results = []
        doc_scores = defaultdict(float)

        # 对每个分词后的关键词进行搜索
        for word in keywords:
            # 支持模糊匹配
            similar_words = get_close_matches(word, self.inverted_index.keys(), n=3, cutoff=0.7)
            for similar_word in similar_words:
                for doc_id, pos in self.inverted_index[similar_word]:
                    # 根据词频和位置计算文档得分
                    doc = self.documents[doc_id]
                    freq = len(doc['word_positions'][similar_word])
                    position_score = 1.0 / (pos + 1)  # 关键词出现位置越靠前，得分越高
                    similarity_score = 1.0 if word == similar_word else 0.7  # 完全匹配得分更高
                    doc_scores[doc_id] += freq * position_score * similarity_score

        # 根据得分对文档排序
        scored_docs = [(doc_id, score) for doc_id, score in doc_scores.items()]
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        for doc_id, score in scored_docs:
            doc = self.documents[doc_id]
            results.append(f"文件: {doc['path']}\n得分: {score:.2f}\n")
            
            # 获取关键词上下文
            content = doc['content'].lower()
            contexts = []
            for word in keywords:
                similar_words = get_close_matches(word, self.inverted_index.keys(), n=3, cutoff=0.7)
                for similar_word in similar_words:
                    positions = doc['word_positions'].get(similar_word, [])
                    for pos in positions:
                        start = max(0, content.rfind(' ', 0, pos) - 30)
                        end = min(len(content), content.find(' ', pos + len(similar_word)) + 30)
                        context = content[start:end].strip()
                        contexts.append(context)
            
            if contexts:
                results.append(f"上下文:\n" + "\n...".join(contexts[:3]) + "\n\n")

        if results:
            self.results_display.setText(''.join(results))
        else:
            self.results_display.setText("未找到匹配的结果")

        # 高亮显示关键词和文件路径
        cursor = self.results_display.textCursor()
        format = QTextCharFormat()
        format.setBackground(QColor("yellow"))

        # 先高亮文件路径
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        while True:
            cursor = self.results_display.document().find("文件: ", cursor)
            if cursor.isNull():
                break
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, 4)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(format)

        # 高亮所有关键词及其相似词
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for word in keywords:
            similar_words = get_close_matches(word, self.inverted_index.keys(), n=3, cutoff=0.7)
            for similar_word in similar_words:
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                while True:
                    cursor = self.results_display.document().find(similar_word, cursor, 
                                                                 QTextDocument.FindFlag.FindCaseSensitively)
                    if cursor.isNull():
                        break
                    cursor.mergeCharFormat(format)

        # 再高亮关键词
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        while cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(keyword)):
            if cursor.selectedText().lower() == keyword:
                cursor.mergeCharFormat(format)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, -len(keyword) + 1)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()