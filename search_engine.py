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
import threading
import psutil

logger = logger_config.setup_logger(__name__)

class DocumentScanner(QThread):
    progress_updated = pyqtSignal(int)
    scan_completed = pyqtSignal(tuple)
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DocumentScanner, cls).__new__(cls)
                # 在创建实例时就调用父类的初始化方法
                super(DocumentScanner, cls._instance).__init__()
            return cls._instance

    def __init__(self, directory, specific_files=None):
        # 每次初始化时都重置状态
        self._initialized = True
        self.directory = directory
        self.specific_files = specific_files
        self.inverted_index = defaultdict(list)
        self.documents = []
        # 保留缓存管理器实例，这样可以继续使用已经持久化的缓存数据
        if not hasattr(self, 'cache_manager'):
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
        
        try:
            # 获取初始系统资源使用情况
            process = psutil.Process()
            initial_cpu_percent = psutil.cpu_percent(interval=1)
            initial_memory = process.memory_info().rss / 1024 / 1024
            logger.info(f"\n[系统资源] 初始状态:")
            logger.info(f"[系统资源] CPU使用率: {initial_cpu_percent}%")
            logger.info(f"[系统资源] 内存使用: {initial_memory:.2f}MB")

            # 获取所有文档路径或使用指定的文件列表
            def is_valid_path(path):
                try:
                    # 检查路径长度
                    if len(str(path)) > 260:  # Windows MAX_PATH限制
                        logger.warning(f"路径过长: {path}")
                        return False
                    # 检查是否是系统目录
                    if any(system_dir in str(path).lower() for system_dir in ['windows', 'system32', 'programdata', 'application data']):
                        logger.warning(f"跳过系统目录: {path}")
                        return False
                    # 检查是否是符号链接
                    if path.is_symlink():
                        logger.warning(f"跳过符号链接: {path}")
                        return False
                    # 验证路径是否可访问
                    resolved_path = path.resolve()
                    # 检查解析后的路径深度
                    if len(resolved_path.parts) > 20:  # 限制目录深度
                        logger.warning(f"目录深度过大: {path}")
                        return False
                    return True
                except Exception as e:
                    logger.warning(f"无效路径: {path}, 错误: {str(e)}")
                    return False

            if self.specific_files:
                docx_files = [Path(f) for f in self.specific_files if f.endswith('.docx') and is_valid_path(Path(f))]
                pdf_files = [Path(f) for f in self.specific_files if f.endswith('.pdf') and is_valid_path(Path(f))]
            else:
                # 使用安全的文件遍历
                docx_files = []
                pdf_files = []
                try:
                    base_path = Path(self.directory)
                    for item in base_path.rglob('*'):
                        if not is_valid_path(item):
                            continue
                        if item.is_file():
                            if item.suffix.lower() == '.docx':
                                docx_files.append(item)
                            elif item.suffix.lower() == '.pdf':
                                pdf_files.append(item)
                except Exception as e:
                    logger.error(f"遍历目录时发生错误: {str(e)}")
                    self.scan_completed.emit(([], defaultdict(list)))
                    return
            total_files = len(docx_files) + len(pdf_files)
            
            logger.info(f"找到 {len(docx_files)} 个Word文档和 {len(pdf_files)} 个PDF文档")
            
            if total_files == 0:
                logger.info("未找到任何文档")
                self.scan_completed.emit(([], defaultdict(list)))
                return

            # 根据系统CPU核心数动态调整进程数，但不超过系统核心数的75%
            self.cpu_count = max(2, min(self.cpu_count * 3 // 4, 8))  # 增加最大进程数限制
            # 根据CPU数量动态调整批处理大小
            batch_size = max(10, min(20, self.cpu_count * 3))  # 增加批处理大小
            
            # 分批处理Word文档
            docx_results = []
            logger.info("\n开始处理Word文档...")
            for i in range(0, len(docx_files), batch_size):
                batch_files = docx_files[i:i + batch_size]
                logger.info(f"处理Word文档批次 {i//batch_size + 1}/{(len(docx_files)-1)//batch_size + 1}")
                try:
                    with multiprocessing.Pool(processes=self.cpu_count) as pool:
                        batch_results = list(pool.imap(partial(process_document, doc_type='docx', cache_manager=self.cache_manager), batch_files))
                        docx_results.extend([r for r in batch_results if r])
                        progress = min(50, int((i + len(batch_files)) / total_files * 50))
                        self.progress_updated.emit(progress)
                        
                        # 监控系统资源使用
                        current_cpu_percent = psutil.cpu_percent()
                        current_memory = process.memory_info().rss / 1024 / 1024
                        memory_increase = current_memory - initial_memory
                        logger.info(f"\n[系统资源] Word文档批次 {i//batch_size + 1} 处理后:")
                        logger.info(f"[系统资源] CPU使用率: {current_cpu_percent}%")
                        logger.info(f"[系统资源] 当前内存: {current_memory:.2f}MB (增加: {memory_increase:.2f}MB)")
                except (BrokenPipeError, EOFError) as e:
                    logger.error(f"处理Word文档时发生错误: {str(e)}")
                    continue

            # 分批处理PDF文档
            pdf_results = []
            logger.info("\n开始处理PDF文档...")
            for i in range(0, len(pdf_files), batch_size):
                batch_files = pdf_files[i:i + batch_size]
                logger.info(f"处理PDF文档批次 {i//batch_size + 1}/{(len(pdf_files)-1)//batch_size + 1}")
                try:
                    with multiprocessing.Pool(processes=self.cpu_count) as pool:
                        batch_results = list(pool.imap(partial(process_document, doc_type='pdf', cache_manager=self.cache_manager), batch_files))
                        pdf_results.extend([r for r in batch_results if r])
                        progress = 50 + min(50, int((i + len(batch_files)) / total_files * 50))
                        self.progress_updated.emit(progress)
                        
                        # 监控系统资源使用
                        current_cpu_percent = psutil.cpu_percent()
                        current_memory = process.memory_info().rss / 1024 / 1024
                        memory_increase = current_memory - initial_memory
                        logger.info(f"\n[系统资源] PDF文档批次 {i//batch_size + 1} 处理后:")
                        logger.info(f"[系统资源] CPU使用率: {current_cpu_percent}%")
                        logger.info(f"[系统资源] 当前内存: {current_memory:.2f}MB (增加: {memory_increase:.2f}MB)")
                except (BrokenPipeError, EOFError) as e:
                    logger.error(f"处理PDF文档时发生错误: {str(e)}")
                    continue

            # 合并结果
            self.documents = docx_results + pdf_results
            self.inverted_index = self.build_inverted_index(self.documents)

            # 清理临时数据
            for doc in self.documents:
                doc.pop('words', None)

            total_time = time.time() - start_time
            final_cpu_percent = psutil.cpu_percent()
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - initial_memory
            
            logger.info("文档扫描完成")
            logger.info(f"总用时: {total_time:.2f}秒")
            logger.info(f"成功处理: {len(self.documents)}/{total_files} 个文档")
            logger.info(f"索引词数量: {len(self.inverted_index)}")
            logger.info(f"\n[系统资源] 最终状态:")
            logger.info(f"[系统资源] CPU使用率: {final_cpu_percent}%")
            logger.info(f"[系统资源] 内存使用: {final_memory:.2f}MB (总增加: {memory_increase:.2f}MB)")
            self.scan_completed.emit((self.documents, self.inverted_index))
        except Exception as e:
            logger.error(f"扫描文档时发生错误: {str(e)}")
            self.scan_completed.emit(([], defaultdict(list)))

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