import multiprocessing
from pathlib import Path
from collections import defaultdict
from functools import partial
import time
import jieba
import math
from difflib import get_close_matches
from PyQt6.QtCore import QThread, pyqtSignal
from cache_manager import CacheManager
import logger_config
from document_processor import process_document

logger = logger_config.setup_logger(__name__)

class DocumentScanner(QThread):
    progress_updated = pyqtSignal(int)
    scan_completed = pyqtSignal(tuple)

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.inverted_index = defaultdict(list)
        self.documents = []
        self.cpu_count = multiprocessing.cpu_count()
        self.cache_manager = CacheManager()

    def build_inverted_index(self, documents):
        inverted_index = defaultdict(list)
        for doc_id, doc in enumerate(documents):
            if doc is None:
                continue
            for pos, word in enumerate(doc['words']):
                inverted_index[word].append((doc_id, pos))
        return inverted_index

    def run(self):
        logger.info("\n开始扫描文档...")
        start_time = time.time()
        self.documents = []
        self.inverted_index.clear()
        
        # 获取所有文档路径
        docx_files = list(Path(self.directory).rglob('*.docx'))
        pdf_files = list(Path(self.directory).rglob('*.pdf'))
        total_files = len(docx_files) + len(pdf_files)
        
        logger.info(f"找到 {len(docx_files)} 个Word文档和 {len(pdf_files)} 个PDF文档")
        
        if total_files == 0:
            logger.info("未找到任何文档")
            self.scan_completed.emit(([], defaultdict(list)))
            return

        self.cpu_count = min(self.cpu_count, 4)  # 限制最大进程数
        batch_size = 10  # 每批处理的文件数
        
        # 分批处理Word文档
        docx_results = []
        logger.info("\n开始处理Word文档...")
        for i in range(0, len(docx_files), batch_size):
            batch_files = docx_files[i:i + batch_size]
            logger.info(f"处理Word文档批次 {i//batch_size + 1}/{(len(docx_files)-1)//batch_size + 1}")
            with multiprocessing.Pool(processes=self.cpu_count) as pool:
                batch_results = list(pool.imap(partial(process_document, doc_type='docx', cache_manager=self.cache_manager), batch_files))
                docx_results.extend([r for r in batch_results if r])
                progress = min(50, int((i + len(batch_files)) / total_files * 50))
                self.progress_updated.emit(progress)

        # 分批处理PDF文档
        pdf_results = []
        logger.info("\n开始处理PDF文档...")
        for i in range(0, len(pdf_files), batch_size):
            batch_files = pdf_files[i:i + batch_size]
            logger.info(f"处理PDF文档批次 {i//batch_size + 1}/{(len(pdf_files)-1)//batch_size + 1}")
            with multiprocessing.Pool(processes=self.cpu_count) as pool:
                batch_results = list(pool.imap(partial(process_document, doc_type='pdf', cache_manager=self.cache_manager), batch_files))
                pdf_results.extend([r for r in batch_results if r])
                progress = 50 + min(50, int((i + len(batch_files)) / total_files * 50))
                self.progress_updated.emit(progress)

        # 合并结果
        self.documents = docx_results + pdf_results
        self.inverted_index = self.build_inverted_index(self.documents)

        # 清理临时数据
        for doc in self.documents:
            doc.pop('words', None)

        total_time = time.time() - start_time
        logger.info("文档扫描完成")
        logger.info(f"总用时: {total_time:.2f}秒")
        logger.info(f"成功处理: {len(self.documents)}/{total_files} 个文档")
        logger.info(f"索引词数量: {len(self.inverted_index)}")
        self.scan_completed.emit((self.documents, self.inverted_index))

def search_documents(documents, inverted_index, keyword):
    if not keyword:
        return []

    logger.info(f"开始搜索关键词: {keyword}")
    start_time = time.time()

    # 使用结巴分词处理搜索关键词
    keywords = jieba.lcut(keyword)
    logger.info(f"分词结果: {', '.join(keywords)}")
    doc_scores = defaultdict(float)
    total_docs = len(documents)

    # 计算IDF值
    idf_scores = {}
    for word in keywords:
        doc_freq = len(set(doc_id for doc_id, _ in inverted_index.get(word, [])))
        idf_scores[word] = math.log(total_docs / (doc_freq + 1)) + 1

    # 对每个分词后的关键词进行搜索
    for word in keywords:
        # 支持模糊匹配，但限制相似词数量
        similar_words = get_close_matches(word, inverted_index.keys(), n=2, cutoff=0.8)
        logger.info(f"处理关键词: {word}, 找到相似词: {', '.join(similar_words)}")
        for similar_word in similar_words:
            matches = inverted_index[similar_word]
            logger.info(f"相似词 '{similar_word}' 在 {len(set(doc_id for doc_id, _ in matches))} 个文档中找到匹配")
            doc_positions = defaultdict(list)
            
            # 收集每个文档中的位置信息
            for doc_id, pos in matches:
                doc_positions[doc_id].append(pos)
            
            for doc_id, positions in doc_positions.items():
                doc = documents[doc_id]
                # 计算TF值
                tf = len(positions) / len(doc['content'].split())
                # 计算位置权重
                position_weights = sum(1 / (pos + 1) for pos in positions)
                # 计算最终得分：TF-IDF * 位置权重
                score = tf * idf_scores.get(word, 1.0) * position_weights
                # 相似词匹配的得分稍微降低
                if similar_word != word:
                    score *= 0.8
                doc_scores[doc_id] += score

    # 按得分排序并返回结果
    search_results = []
    for doc_id, score in sorted(doc_scores.items(), key=lambda x: x[1], reverse=True):
        doc = documents[doc_id]
        search_results.append({
            'path': doc['path'],
            'type': doc['type'],
            'score': score,
            'content': doc['content'],
            'positions': doc['word_positions']
        })

    search_time = time.time() - start_time
    logger.info(f"搜索完成，用时: {search_time:.2f}秒，找到 {len(search_results)} 个结果")
    return search_results