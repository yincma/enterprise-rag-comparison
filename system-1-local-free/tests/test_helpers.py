"""
辅助函数模块单元测试
"""

import pytest
import time
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

from utils.helpers import (
    get_file_hash, get_file_size, format_file_size, clean_text,
    split_text_into_chunks, measure_performance, get_system_info,
    validate_file_type, create_directory_if_not_exists, sanitize_filename,
    Timer, retry_on_failure
)

class TestFileOperations:
    """文件操作函数测试"""
    
    def test_get_file_hash(self, temp_dir):
        """测试文件哈希计算"""
        test_file = temp_dir / "test.txt"
        content = "测试内容"
        test_file.write_text(content, encoding="utf-8")
        
        # 计算预期的MD5值
        expected_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        
        # 测试函数
        actual_hash = get_file_hash(test_file)
        assert actual_hash == expected_hash
    
    def test_get_file_size(self, temp_dir):
        """测试文件大小获取"""
        test_file = temp_dir / "test.txt"
        content = "测试内容" * 100
        test_file.write_text(content, encoding="utf-8")
        
        size = get_file_size(test_file)
        assert size > 0
        assert size == len(content.encode("utf-8"))
    
    @pytest.mark.parametrize("size_bytes,expected", [
        (0, "0 B"),
        (1024, "1.0 KB"),
        (1024*1024, "1.0 MB"),
        (1024*1024*1024, "1.0 GB"),
        (1536, "1.5 KB"),  # 1.5KB
        (2*1024*1024 + 512*1024, "2.5 MB")  # 2.5MB
    ])
    def test_format_file_size(self, size_bytes, expected):
        """测试文件大小格式化"""
        result = format_file_size(size_bytes)
        assert result == expected

class TestTextProcessing:
    """文本处理函数测试"""
    
    @pytest.mark.parametrize("input_text,expected", [
        ("  普通文本  ", "普通文本"),
        ("多个    空格   的文本", "多个 空格 的文本"),
        ("", ""),
        ("   \n\n  换行符  \n  ", "换行符"),
        ("制表符\t\t\t文本", "制表符 文本")
    ])
    def test_clean_text(self, input_text, expected):
        """测试文本清理"""
        result = clean_text(input_text)
        assert result == expected
    
    def test_split_text_into_chunks_normal(self):
        """测试正常文本分割"""
        text = "这是第一段文本内容。\n\n这是第二段文本内容。\n这是第三段文本内容。"
        chunks = split_text_into_chunks(text, chunk_size=50, chunk_overlap=10)
        
        assert len(chunks) >= 1  # 至少有一个块
        for chunk in chunks:
            assert len(chunk.strip()) >= 10  # 检查最小块长度过滤
    
    def test_split_text_into_chunks_long_text(self):
        """测试长文本分割"""
        long_text = "A" * 1000 + "B" * 1000 + "C" * 1000
        chunks = split_text_into_chunks(long_text, chunk_size=500, chunk_overlap=100)
        
        assert len(chunks) > 1
        # 检查重叠
        if len(chunks) > 1:
            # 第一个块的结尾应该和第二个块的开头有重叠
            first_end = chunks[0][-100:]
            second_start = chunks[1][:100]
            # 应该有部分重叠内容
            assert len(set(first_end) & set(second_start)) > 0
    
    def test_split_text_into_chunks_empty_separators(self):
        """测试空分隔符处理（修复后的bug）"""
        text = "测试文本" * 100
        # 包含空字符串的分隔符列表
        separators = ["\n\n", "\n", " ", ""]
        
        # 不应该抛出异常
        chunks = split_text_into_chunks(text, chunk_size=50, chunk_overlap=10, separators=separators)
        assert len(chunks) > 0
    
    def test_split_text_into_chunks_short_text(self):
        """测试短文本分割"""
        short_text = "这是一个足够长的短文本用于测试文本分割功能确保不会被最小长度过滤掉"
        chunks = split_text_into_chunks(short_text, chunk_size=100, chunk_overlap=20)
        
        assert len(chunks) >= 1
        if len(chunks) == 1:
            assert short_text in chunks[0]

class TestPerformanceDecorator:
    """性能测试装饰器测试"""
    
    def test_measure_performance_success(self, caplog):
        """测试性能测量装饰器正常执行"""
        import logging
        caplog.set_level(logging.INFO)
        
        @measure_performance
        def test_function():
            time.sleep(0.01)  # 模拟一些工作
            return "success"
        
        result = test_function()
        assert result == "success"
        
        # 检查日志记录
        log_messages = [record.message for record in caplog.records]
        assert any("test_function 性能指标" in msg for msg in log_messages)
        assert any("执行时间" in msg for msg in log_messages)
        assert any("执行状态: 成功" in msg for msg in log_messages)
    
    def test_measure_performance_exception(self, caplog):
        """测试性能测量装饰器异常处理"""
        import logging
        caplog.set_level(logging.INFO)
        
        @measure_performance
        def failing_function():
            raise ValueError("测试异常")
        
        with pytest.raises(ValueError, match="测试异常"):
            failing_function()
        
        # 检查日志记录
        log_messages = [record.message for record in caplog.records]
        assert any("failing_function 性能指标" in msg for msg in log_messages)
        assert any("执行状态: 失败" in msg for msg in log_messages)

class TestSystemInfo:
    """系统信息函数测试"""
    
    @patch('psutil.cpu_count')
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_get_system_info(self, mock_disk, mock_memory, mock_cpu_percent, mock_cpu_count):
        """测试系统信息获取"""
        # 设置mock返回值
        mock_cpu_count.return_value = 4
        mock_cpu_percent.return_value = 25.5
        
        mock_memory_obj = MagicMock()
        mock_memory_obj.total = 8 * 1024**3  # 8GB
        mock_memory_obj.available = 4 * 1024**3  # 4GB
        mock_memory_obj.percent = 50.0
        mock_memory.return_value = mock_memory_obj
        
        mock_disk_obj = MagicMock()
        mock_disk_obj.total = 100 * 1024**3  # 100GB
        mock_disk_obj.used = 40 * 1024**3   # 40GB
        mock_disk_obj.free = 60 * 1024**3   # 60GB
        mock_disk.return_value = mock_disk_obj
        
        info = get_system_info()
        
        assert info["cpu_count"] == 4
        assert info["cpu_percent"] == 25.5
        assert info["memory_total"] == 8.0
        assert info["memory_available"] == 4.0
        assert info["memory_percent"] == 50.0
        assert info["disk_usage"]["total"] == 100.0
        assert info["disk_usage"]["percent"] == 40.0

class TestFileValidation:
    """文件验证函数测试"""
    
    @pytest.mark.parametrize("filename,extensions,expected", [
        ("test.txt", [".txt", ".md"], True),
        ("test.PDF", [".pdf"], True),  # 大小写不敏感
        ("test.doc", [".txt", ".pdf"], False),
        ("test", [".txt"], False),  # 无扩展名
        ("test.txt.backup", [".txt"], False)  # 错误扩展名
    ])
    def test_validate_file_type(self, temp_dir, filename, extensions, expected):
        """测试文件类型验证"""
        test_file = temp_dir / filename
        test_file.touch()  # 创建空文件
        
        result = validate_file_type(test_file, extensions)
        assert result == expected
    
    def test_create_directory_if_not_exists(self, temp_dir):
        """测试目录创建"""
        new_dir = temp_dir / "new" / "nested" / "directory"
        
        # 目录不存在
        assert not new_dir.exists()
        
        # 创建目录
        result_dir = create_directory_if_not_exists(new_dir)
        
        # 验证结果
        assert result_dir.exists()
        assert result_dir.is_dir()
        assert result_dir == new_dir
        
        # 再次调用应该不会出错
        result_dir2 = create_directory_if_not_exists(new_dir)
        assert result_dir2 == new_dir

    @pytest.mark.parametrize("filename,expected", [
        ("normal_file.txt", "normal_file.txt"),
        ("file with spaces.txt", "file with spaces.txt"),
        ("file<with>bad:chars.txt", "filewithbadchars.txt"),
        ("file/with\\path|chars?.txt", "filewithpathchars.txt"),
        ("very_long_filename" + "x" * 200 + ".txt", "very_long_filename" + "x" * 178 + ".txt")
    ])
    def test_sanitize_filename(self, filename, expected):
        """测试文件名清理"""
        result = sanitize_filename(filename)
        assert result == expected

class TestTimer:
    """计时器测试"""
    
    def test_timer_context_manager(self, caplog):
        """测试计时器上下文管理器"""
        import logging
        caplog.set_level(logging.INFO)
        
        with Timer("测试操作"):
            time.sleep(0.01)
        
        log_messages = [record.message for record in caplog.records]
        assert any("测试操作完成" in msg for msg in log_messages)
        assert any("耗时" in msg for msg in log_messages)

class TestRetryDecorator:
    """重试装饰器测试"""
    
    def test_retry_success_on_first_attempt(self):
        """测试第一次尝试成功"""
        @retry_on_failure(max_retries=3)
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_retry_success_after_failures(self):
        """测试重试后成功"""
        call_count = 0
        
        @retry_on_failure(max_retries=3, delay=0.001)  # 很短的延迟
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("临时失败")
            return "最终成功"
        
        result = flaky_function()
        assert result == "最终成功"
        assert call_count == 3
    
    def test_retry_final_failure(self):
        """测试最终失败"""
        @retry_on_failure(max_retries=2, delay=0.001)
        def always_failing_function():
            raise RuntimeError("总是失败")
        
        with pytest.raises(RuntimeError, match="总是失败"):
            always_failing_function()

@pytest.mark.utils
class TestHelpersIntegration:
    """辅助函数集成测试"""
    
    def test_file_processing_workflow(self, temp_dir):
        """测试文件处理工作流程"""
        # 1. 创建测试文件
        test_file = temp_dir / "integration_test.txt"
        content = "集成测试内容\n\n包含多行文本\n用于测试完整流程"
        test_file.write_text(content, encoding="utf-8")
        
        # 2. 验证文件
        assert validate_file_type(test_file, [".txt"])
        
        # 3. 获取文件信息
        size = get_file_size(test_file)
        hash_value = get_file_hash(test_file)
        formatted_size = format_file_size(size)
        
        assert size > 0
        assert len(hash_value) == 32  # MD5哈希长度
        assert "B" in formatted_size
        
        # 4. 处理文本内容
        cleaned_content = clean_text(content)
        chunks = split_text_into_chunks(cleaned_content, chunk_size=100, chunk_overlap=20)
        
        assert len(chunks) >= 1
        assert all(len(chunk.strip()) >= 10 for chunk in chunks if chunk.strip())  # 最小块长度检查
    
    def test_directory_and_filename_handling(self, temp_dir):
        """测试目录和文件名处理"""
        # 1. 创建目录结构
        nested_dir = temp_dir / "level1" / "level2"
        created_dir = create_directory_if_not_exists(nested_dir)
        
        assert created_dir.exists()
        assert created_dir.is_dir()
        
        # 2. 清理文件名
        bad_filename = "bad<file>name?.txt"
        clean_filename = sanitize_filename(bad_filename)
        
        # 3. 创建文件
        test_file = created_dir / clean_filename
        test_file.write_text("测试内容", encoding="utf-8")
        
        assert test_file.exists()
        assert validate_file_type(test_file, [".txt"])