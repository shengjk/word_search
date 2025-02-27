# 文档检索系统 / Document Search System

[English Version](#english-version)

## 中文版本

### 项目介绍
这是一个基于Python开发的文档全文检索系统，支持Word和PDF文档的内容搜索。系统采用PyQt6构建用户界面，提供了简单直观的操作方式，能够快速扫描指定文件夹中的文档并建立索引，实现高效的全文检索功能。

### 主要特性
- 支持Word (.docx) 和 PDF 文件格式
- 中文分词支持，提供精确的搜索结果
- 模糊匹配功能，提高搜索容错率
- 实时显示文档扫描进度
- 搜索结果按相关度排序
- 关键词高亮显示
- 显示关键词所在上下文

### 安装说明
1. 确保已安装Python 3.6或更高版本
2. 安装所需依赖：
```bash
pip install PyQt6 python-docx PyPDF2 jieba
```
3. 运行程序：
```bash
python word_search.py
```

### 使用指南
1. 启动程序后，点击"浏览"按钮选择要检索的文件夹
2. 系统会自动扫描文件夹中的Word和PDF文档并建立索引
3. 在搜索框中输入关键词，按回车或点击"搜索"按钮
4. 系统将显示包含关键词的文档列表，并按相关度排序
5. 搜索结果中会显示文件路径、相关度得分和关键词所在上下文
6. 关键词和文件路径会以黄色高亮显示

---

## English Version

### Project Introduction
This is a full-text document search system developed in Python, supporting content search in Word and PDF documents. The system uses PyQt6 to build the user interface, providing a simple and intuitive operation method that can quickly scan documents in specified folders and build indexes for efficient full-text retrieval.

### Key Features
- Support for Word (.docx) and PDF file formats
- Chinese word segmentation support for accurate search results
- Fuzzy matching capability for better search tolerance
- Real-time document scanning progress display
- Search results sorted by relevance
- Keyword highlighting
- Context display around keywords

### Installation
1. Ensure Python 3.6 or higher is installed
2. Install required dependencies:
```bash
pip install PyQt6 python-docx PyPDF2 jieba
```
3. Run the program:
```bash
python word_search.py
```

### User Guide
1. After launching the program, click the "Browse" button to select the folder to search
2. The system will automatically scan Word and PDF documents in the folder and build an index
3. Enter keywords in the search box and press Enter or click the "Search" button
4. The system will display a list of documents containing the keywords, sorted by relevance
5. Search results will show file paths, relevance scores, and context around keywords
6. Keywords and file paths are highlighted in yellow