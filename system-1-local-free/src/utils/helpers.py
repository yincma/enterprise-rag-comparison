"""
辅助函数模块
提供通用的工具函数
"""

import os
import hashlib
import time
import psutil
from typing import List, Dict, Any, Union, Optional
from pathlib import Path
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def get_file_hash(file_path: Union[str, Path]) -> str:
    """
    计算文件的MD5哈希值
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件的MD5哈希值
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_file_size(file_path: Union[str, Path]) -> int:
    """
    获取文件大小（字节）
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件大小（字节）
    """
    return os.path.getsize(file_path)

def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小为人类可读格式
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        格式化的文件大小字符串
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def clean_text(text: str) -> str:
    """
    清理文本内容
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 移除多余的空白字符
    text = ' '.join(text.split())
    
    # 移除特殊字符（可选）
    # text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
    
    return text.strip()

def split_text_into_chunks(
    text: str, 
    chunk_size: int = 1000, 
    chunk_overlap: int = 200,
    separators: Optional[List[str]] = None
) -> List[str]:
    """
    将文本分割成块
    
    Args:
        text: 要分割的文本
        chunk_size: 块大小
        chunk_overlap: 块重叠大小
        separators: 分割符列表
        
    Returns:
        文本块列表
    """
    if separators is None:
        separators = ["\n\n", "\n", " ", ""]
    
    chunks = []
    
    def _split_text(text: str, separators: List[str]) -> List[str]:
        """递归分割文本"""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []
        
        for separator in separators:
            if separator and separator in text:  # 检查分割符不为空且存在于文本中
                splits = text.split(separator)
                result = []
                current_chunk = ""
                
                for split in splits:
                    if len(current_chunk) + len(split) + len(separator) <= chunk_size:
                        if current_chunk:
                            current_chunk += separator + split
                        else:
                            current_chunk = split
                    else:
                        if current_chunk:
                            result.append(current_chunk)
                            # 处理重叠
                            overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
                            current_chunk = overlap_text + separator + split if overlap_text else split
                        else:
                            # 单个分割太长，继续递归分割
                            sub_chunks = _split_text(split, separators[1:])
                            result.extend(sub_chunks)
                
                if current_chunk:
                    result.append(current_chunk)
                
                return result
        
        # 如果所有分割符都无法分割，强制按字符分割
        result = []
        step = max(1, chunk_size - chunk_overlap)  # 确保步长至少为1
        for i in range(0, len(text), step):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                result.append(chunk)
        
        return result
    
    chunks = _split_text(text, separators)
    
    # 过滤掉过短的块
    min_chunk_length = 10  # 降低最小块长度要求
    chunks = [chunk for chunk in chunks if len(chunk.strip()) >= min_chunk_length]
    
    return chunks

def measure_performance(func):
    """
    性能测量装饰器
    
    Args:
        func: 要测量的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception as e:
            result = e
            success = False
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        execution_time = end_time - start_time
        memory_diff = end_memory - start_memory
        
        logger.info(f"函数 {func.__name__} 性能指标:")
        logger.info(f"  执行时间: {execution_time:.3f}秒")
        logger.info(f"  内存变化: {memory_diff:+.2f}MB")
        logger.info(f"  执行状态: {'成功' if success else '失败'}")
        
        if not success:
            raise result
        
        return result
    
    return wrapper

def get_system_info() -> Dict[str, Any]:
    """
    获取系统信息
    
    Returns:
        系统信息字典
    """
    return {
        "cpu_count": psutil.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_total": psutil.virtual_memory().total / 1024**3,  # GB
        "memory_available": psutil.virtual_memory().available / 1024**3,  # GB
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": {
            "total": psutil.disk_usage('/').total / 1024**3,  # GB
            "used": psutil.disk_usage('/').used / 1024**3,  # GB
            "free": psutil.disk_usage('/').free / 1024**3,  # GB
            "percent": (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
        }
    }

def validate_file_type(file_path: Union[str, Path], allowed_extensions: List[str]) -> bool:
    """
    验证文件类型
    
    Args:
        file_path: 文件路径
        allowed_extensions: 允许的文件扩展名列表
        
    Returns:
        是否为允许的文件类型
    """
    file_ext = Path(file_path).suffix.lower()
    return file_ext in [ext.lower() for ext in allowed_extensions]

def create_directory_if_not_exists(directory: Union[str, Path]) -> Path:
    """
    如果目录不存在则创建
    
    Args:
        directory: 目录路径
        
    Returns:
        目录路径对象
    """
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除不安全字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    import re
    # 移除不安全字符
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 限制长度
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    
    return filename

class Timer:
    """计时器上下文管理器"""
    
    def __init__(self, description: str = "操作"):
        self.description = description
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        logger.debug(f"开始{self.description}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        duration = end_time - self.start_time
        logger.info(f"{self.description}完成，耗时: {duration:.3f}秒")

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    失败重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"函数 {func.__name__} 经过 {max_retries} 次重试后仍然失败: {e}")
                        raise
                    else:
                        logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，{delay}秒后重试")
                        time.sleep(delay)
        return wrapper
    return decorator