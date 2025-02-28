from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QProgressBar, QTextEdit,
                             QFileDialog)
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor, QTextDocument
from PyQt6.QtCore import Qt
from search_engine import DocumentScanner, search_documents
import logger_config
import jieba

logger = logger_config.setup_logger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Word文档全文检索系统")
        self.setMinimumSize(800, 600)
        self.documents = []
        self.inverted_index = {}  # 初始化inverted_index
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

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 执行搜索
        results = search_documents(self.documents, self.inverted_index, keyword)

        # 显示搜索结果
        self.display_search_results(results, keyword)
        self.progress_bar.setVisible(False)

    def display_search_results(self, results, keyword):
        if not results:
            self.results_display.setText("未找到匹配的文档")
            return

        # 清空当前显示
        self.results_display.clear()
        self.results_display.setHtml("")

        # 构建HTML内容
        html_content = ""
        for i, result in enumerate(results):
            # 添加文档标题和路径（使用HTML格式）
            html_content += f"\n<p>文档 {i+1}:</p>"
            html_content += f"<p><b style='font-size: 14px;'>路径: {result['path']}</b></p>"
            html_content += f"<p>类型: {result['type'].upper()}</p>"
            html_content += f"<p>相关度得分: {result['score']:.4f}</p>"

            # 显示文档内容预览
            content = result['content'][:500] + "..." if len(result['content']) > 500 else result['content']
            # 高亮关键词
            for kw in jieba.lcut(keyword):
                content = content.replace(kw, f"<span style='background-color: yellow;'>{kw}</span>")
            html_content += f"<p>内容预览:</p>"
            html_content += f"<p>{content}</p><br>"

        # 设置HTML内容
        self.results_display.setHtml(html_content)
        self.results_display.moveCursor(QTextCursor.MoveOperation.Start)
        self.results_display.ensureCursorVisible()