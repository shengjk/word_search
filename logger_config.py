import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(name=None, app_name='word_search'):
    # 根据操作系统选择合适的日志目录
    if sys.platform == 'win32':
        base_dir = os.getenv('APPDATA')
        if not base_dir:
            base_dir = os.path.expanduser('~')
        log_dir = os.path.join(base_dir, app_name, 'logs')
    elif sys.platform == 'darwin':
        log_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', app_name, 'logs')
    else:  # Linux 和其他系统
        log_dir = os.path.join(os.path.expanduser('~'), '.local', 'share', app_name, 'logs')
    
    # 创建日志目录
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 使用传入的name创建logger实例，如果未提供则使用root logger
    logger = logging.getLogger(name) if name else logging.getLogger()
    logger.setLevel(logging.INFO)

    # 防止重复添加处理器
    if logger.handlers:
        return logger

    # 创建轮转文件处理器
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'word_search.log'),
        maxBytes=20 * 1024 * 1024,  # 20MB
        backupCount=2,  # 保留2个备份文件
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建格式化器，添加模块名称
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger