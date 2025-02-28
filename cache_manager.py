import sqlite3
import os
import json
from pathlib import Path
from datetime import datetime
import sys
import logging
import zlib
import logger_config

logger = logger_config.setup_logger(__name__)

class CacheManager:
    def __init__(self, app_name='ip_search'):
        # 根据操作系统选择合适的缓存目录
        if sys.platform == 'win32':
            base_dir = os.getenv('APPDATA')
            if not base_dir:
                base_dir = os.path.expanduser('~')
            self.cache_dir = Path(base_dir) / app_name
        elif sys.platform == 'darwin':
            self.cache_dir = Path(os.path.expanduser('~')) / 'Library' / 'Application Support' / app_name
        else:  # Linux 和其他系统
            self.cache_dir = Path(os.path.expanduser('~')) / '.cache' / app_name
        
        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / 'document_cache.db'
        logger.info(f"缓存数据库路径: {self.db_path}")
        self.init_database()

    def init_database(self):
        logger.info("初始化缓存数据库...")
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_cache (
                    file_path TEXT PRIMARY KEY,
                    last_modified INTEGER,
                    content_hash TEXT,
                    cache_data BLOB,
                    created_at INTEGER
                )
            """)
            conn.commit()
        logger.info("缓存数据库初始化完成")

    def get_file_info(self, file_path):
        try:
            stat = os.stat(file_path)
            return {
                'last_modified': int(stat.st_mtime),
                'size': stat.st_size
            }
        except OSError as e:
            logger.error(f"获取文件信息失败: {file_path}, 错误: {str(e)}")
            return None

    def get_cached_document(self, file_path):
        logger.info(f"尝试获取缓存文档: {file_path}")
        file_info = self.get_file_info(file_path)
        if not file_info:
            logger.warning(f"无法获取文件信息: {file_path}")
            return None

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                # 使用流式方式读取BLOB数据
                cursor.execute("""SELECT cache_data FROM document_cache
                    WHERE file_path = ? AND last_modified = ?""", 
                    (str(file_path), file_info['last_modified']))
                
                row = cursor.fetchone()
                if not row:
                    logger.info(f"未找到缓存数据: {file_path}")
                    return None

                logger.info(f"找到缓存数据: {file_path}")
                # 使用流式解压缩
                decompressor = zlib.decompressobj()
                compressed_data = row[0]
                decompressed_data = decompressor.decompress(compressed_data)
                decompressed_data += decompressor.flush()

                return json.loads(decompressed_data)
        except sqlite3.Error as e:
            logger.error(f"数据库操作失败: {file_path}, 错误: {str(e)}")
            return None
        except (json.JSONDecodeError, zlib.error) as e:
            logger.error(f"缓存数据解析失败: {file_path}, 错误: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取缓存数据时发生未知错误: {file_path}, 错误: {str(e)}")
            return None

    def cache_document(self, file_path, document_data):
        logger.info(f"开始缓存文档: {file_path}")
        file_info = self.get_file_info(file_path)
        if not file_info:
            logger.error(f"无法获取文件信息，缓存失败: {file_path}")
            return False

        try:
            # 将数据转换为JSON字符串并压缩
            json_data = json.dumps(document_data)
            compressed_data = zlib.compress(json_data.encode('utf-8'), level=9)
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO document_cache
                    (file_path, last_modified, cache_data, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    str(file_path),
                    file_info['last_modified'],
                    compressed_data,
                    int(datetime.now().timestamp())
                ))
                conn.commit()
            logger.info(f"文档缓存成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"缓存文档失败: {file_path}, 错误: {str(e)}")
            return False

    def clear_cache(self):
        logger.info("清除所有缓存")
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_cache")
            conn.commit()
        logger.info("缓存清除完成")

    def remove_cache(self, file_path):
        logger.info(f"移除文档缓存: {file_path}")
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_cache WHERE file_path = ?", (str(file_path),))
            conn.commit()
        logger.info(f"文档缓存已移除: {file_path}")