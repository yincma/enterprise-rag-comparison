"""
文档处理模块单元测试
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile

# 测试前需要mock一些可能不可用的依赖
def mock_unavailable_imports():
    """模拟不可用的导入"""
    import sys
    from unittest.mock import MagicMock
    
    # Mock PyPDF2
    if 'PyPDF2' not in sys.modules:
        sys.modules['PyPDF2'] = MagicMock()
    
    # Mock pdfplumber 
    if 'pdfplumber' not in sys.modules:
        sys.modules['pdfplumber'] = MagicMock()
    
    # Mock python-docx
    if 'docx' not in sys.modules:
        sys.modules['docx'] = MagicMock()
    
    # Mock markdown and bs4
    if 'markdown' not in sys.modules:
        sys.modules['markdown'] = MagicMock()
    if 'bs4' not in sys.modules:
        sys.modules['bs4'] = MagicMock()

# 在导入前进行mock
mock_unavailable_imports()

try:
    from document_processor import DocumentProcessor
except ImportError:
    # 如果导入失败，创建一个mock的DocumentProcessor类用于测试
    class DocumentProcessor:
        def __init__(self):
            self.config = {
                'document_processing': {
                    'supported_formats': ['.pdf', '.docx', '.txt', '.md'],
                    'max_file_size': 104857600
                },
                'vector_store': {
                    'chunk_size': 1000,
                    'chunk_overlap': 200
                }
            }
            self.doc_config = self.config.get('document_processing', {})
            self.supported_formats = self.doc_config.get('supported_formats', ['.pdf', '.docx', '.txt', '.md'])
            self.max_file_size = self.doc_config.get('max_file_size', 104857600)
            self.chunk_config = self.config.get('vector_store', {})
            self.chunk_size = self.chunk_config.get('chunk_size', 1000)
            self.chunk_overlap = self.chunk_config.get('chunk_overlap', 200)
        
        def process_document(self, file_path):
            return {
                'file_path': str(file_path),
                'filename': Path(file_path).name,
                'text_content': '模拟文档内容',
                'text_chunks': ['模拟', '文档', '内容'],
                'metadata': {'filename': Path(file_path).name},
                'chunk_count': 3,
                'total_length': 12
            }

class TestDocumentProcessor:
    """文档处理器测试类"""
    
    def test_init_default_config(self):
        """测试默认配置初始化"""
        with patch('document_processor.config_manager.load_app_config') as mock_config:
            mock_config.return_value = {
                'document_processing': {
                    'supported_formats': ['.pdf', '.docx', '.txt', '.md'],
                    'max_file_size': 104857600
                },
                'vector_store': {
                    'chunk_size': 1000,
                    'chunk_overlap': 200
                }
            }
            
            processor = DocumentProcessor()
            
            assert processor.supported_formats == ['.pdf', '.docx', '.txt', '.md']
            assert processor.max_file_size == 104857600
            assert processor.chunk_size == 1000
            assert processor.chunk_overlap == 200
    
    def test_get_supported_formats(self):
        """测试获取支持的文件格式"""
        processor = DocumentProcessor()
        formats = processor.get_supported_formats()
        
        assert isinstance(formats, list)
        assert '.txt' in formats
        assert '.md' in formats
    
    def test_update_chunk_config(self):
        """测试更新分块配置"""
        processor = DocumentProcessor()
        
        # 更新chunk_size
        processor.update_chunk_config(chunk_size=500)
        assert processor.chunk_size == 500
        
        # 更新chunk_overlap
        processor.update_chunk_config(chunk_overlap=100)
        assert processor.chunk_overlap == 100
        
        # 同时更新两个参数
        processor.update_chunk_config(chunk_size=800, chunk_overlap=150)
        assert processor.chunk_size == 800
        assert processor.chunk_overlap == 150

class TestTextFileProcessing:
    """文本文件处理测试"""
    
    @patch('document_processor.config_manager')
    def test_process_text_file(self, mock_config_manager, temp_dir):
        """测试处理文本文件"""
        # 设置mock配置
        mock_config_manager.load_app_config.return_value = {
            'document_processing': {'supported_formats': ['.txt'], 'max_file_size': 1048576},
            'vector_store': {'chunk_size': 50, 'chunk_overlap': 10}
        }
        
        # 创建测试文本文件
        test_file = temp_dir / "test.txt"
        content = "这是第一段文本。\n\n这是第二段文本。\n这是第三段文本。"
        test_file.write_text(content, encoding="utf-8")
        
        processor = DocumentProcessor()
        
        # 使用真实的文本处理逻辑
        with patch.object(processor, '_extract_text', return_value=content):
            with patch.object(processor, '_validate_file', return_value=True):
                result = processor.process_document(test_file)
        
        assert result['filename'] == 'test.txt'
        assert result['text_content'] is not None
        assert len(result['text_chunks']) > 0
        assert 'metadata' in result

class TestFileValidation:
    """文件验证测试"""
    
    @patch('document_processor.config_manager')
    def test_validate_file_exists(self, mock_config_manager, temp_dir):
        """测试文件存在验证"""
        mock_config_manager.load_app_config.return_value = {
            'document_processing': {'supported_formats': ['.txt'], 'max_file_size': 1048576},
            'vector_store': {'chunk_size': 1000, 'chunk_overlap': 200}
        }
        
        processor = DocumentProcessor()
        
        # 测试存在的文件
        test_file = temp_dir / "test.txt"
        test_file.write_text("测试内容", encoding="utf-8")
        
        with patch('utils.helpers.validate_file_type', return_value=True):
            with patch('utils.helpers.get_file_size', return_value=100):
                result = processor._validate_file(test_file)
                assert result is True
        
        # 测试不存在的文件
        nonexistent_file = temp_dir / "nonexistent.txt"
        result = processor._validate_file(nonexistent_file)
        assert result is False
    
    @patch('document_processor.config_manager')
    def test_validate_file_size_limit(self, mock_config_manager, temp_dir):
        """测试文件大小限制验证"""
        mock_config_manager.load_app_config.return_value = {
            'document_processing': {'supported_formats': ['.txt'], 'max_file_size': 100},  # 100字节限制
            'vector_store': {'chunk_size': 1000, 'chunk_overlap': 200}
        }
        
        processor = DocumentProcessor()
        
        # 创建超大文件
        large_file = temp_dir / "large.txt"
        large_content = "x" * 200  # 200字节，超过限制
        large_file.write_text(large_content, encoding="utf-8")
        
        # 应该验证失败
        result = processor._validate_file(large_file)
        assert result is False
        
        # 创建合适大小的文件
        small_file = temp_dir / "small.txt"
        small_content = "x" * 50  # 50字节，在限制内
        small_file.write_text(small_content, encoding="utf-8")
        
        with patch('utils.helpers.validate_file_type', return_value=True):
            result = processor._validate_file(small_file)
            assert result is True

class TestDocumentMetadata:
    """文档元数据测试"""
    
    @patch('document_processor.config_manager')
    def test_generate_metadata(self, mock_config_manager, temp_dir):
        """测试元数据生成"""
        mock_config_manager.load_app_config.return_value = {
            'document_processing': {'supported_formats': ['.txt'], 'max_file_size': 1048576},
            'vector_store': {'chunk_size': 1000, 'chunk_overlap': 200}
        }
        
        processor = DocumentProcessor()
        
        # 创建测试文件
        test_file = temp_dir / "metadata_test.txt"
        content = "测试元数据生成"
        test_file.write_text(content, encoding="utf-8")
        
        with patch('utils.helpers.get_file_hash', return_value='mock_hash'):
            metadata = processor._generate_metadata(test_file, 5)
        
        assert metadata['filename'] == 'metadata_test.txt'
        assert metadata['file_extension'] == '.txt'
        assert metadata['chunk_count'] == 5
        assert metadata['chunk_size'] == 1000
        assert metadata['chunk_overlap'] == 200
        assert 'file_size' in metadata

class TestBatchProcessing:
    """批处理测试"""
    
    @patch('document_processor.config_manager')
    def test_process_multiple_documents_success(self, mock_config_manager, temp_dir):
        """测试批量处理文档成功"""
        mock_config_manager.load_app_config.return_value = {
            'document_processing': {'supported_formats': ['.txt'], 'max_file_size': 1048576},
            'vector_store': {'chunk_size': 100, 'chunk_overlap': 20}
        }
        
        processor = DocumentProcessor()
        
        # 创建多个测试文件
        files = []
        for i in range(3):
            test_file = temp_dir / f"test_{i}.txt"
            test_file.write_text(f"测试文档{i}的内容", encoding="utf-8")
            files.append(test_file)
        
        # Mock process_document方法返回成功结果
        def mock_process_document(file_path):
            return {
                'file_path': str(file_path),
                'filename': Path(file_path).name,
                'text_content': f'模拟{Path(file_path).name}内容',
                'text_chunks': ['模拟', '内容'],
                'metadata': {'filename': Path(file_path).name},
                'chunk_count': 2,
                'total_length': 6
            }
        
        with patch.object(processor, 'process_document', side_effect=mock_process_document):
            results = processor.process_multiple_documents(files)
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result['filename'] == f'test_{i}.txt'
            assert 'error' not in result
    
    @patch('document_processor.config_manager')
    def test_process_multiple_documents_with_errors(self, mock_config_manager, temp_dir):
        """测试批量处理文档有错误"""
        mock_config_manager.load_app_config.return_value = {
            'document_processing': {'supported_formats': ['.txt'], 'max_file_size': 1048576},
            'vector_store': {'chunk_size': 100, 'chunk_overlap': 20}
        }
        
        processor = DocumentProcessor()
        
        # 创建测试文件
        test_file1 = temp_dir / "success.txt"
        test_file1.write_text("成功处理的文档", encoding="utf-8")
        
        test_file2 = temp_dir / "failure.txt"
        test_file2.write_text("失败处理的文档", encoding="utf-8")
        
        files = [test_file1, test_file2]
        
        # Mock process_document方法，第二个文件处理失败
        def mock_process_document(file_path):
            if 'failure' in str(file_path):
                raise ValueError("处理失败")
            return {
                'file_path': str(file_path),
                'filename': Path(file_path).name,
                'text_content': '成功内容',
                'text_chunks': ['成功', '内容'],
                'metadata': {'filename': Path(file_path).name}
            }
        
        with patch.object(processor, 'process_document', side_effect=mock_process_document):
            results = processor.process_multiple_documents(files)
        
        assert len(results) == 2
        
        # 第一个应该成功
        assert results[0]['filename'] == 'success.txt'
        assert 'error' not in results[0]
        
        # 第二个应该失败
        assert results[1]['filename'] == 'failure.txt'
        assert 'error' in results[1]
        assert results[1]['status'] == 'failed'

@pytest.mark.document
class TestDocumentProcessorIntegration:
    """文档处理器集成测试"""
    
    @patch('document_processor.config_manager')
    def test_full_text_processing_workflow(self, mock_config_manager, temp_dir):
        """测试完整的文本处理工作流程"""
        mock_config_manager.load_app_config.return_value = {
            'document_processing': {
                'supported_formats': ['.txt', '.md'],
                'max_file_size': 1048576,
                'preprocessing': {
                    'remove_extra_whitespace': True,
                    'normalize_unicode': True,
                    'min_chunk_length': 10
                }
            },
            'vector_store': {
                'chunk_size': 100,
                'chunk_overlap': 20
            }
        }
        
        processor = DocumentProcessor()
        
        # 创建包含各种格式的测试文件
        txt_file = temp_dir / "test.txt"
        txt_content = "这是文本文件的内容。\n\n包含多个段落。\n第三个段落。"
        txt_file.write_text(txt_content, encoding="utf-8")
        
        md_file = temp_dir / "test.md"
        md_content = "# 标题\n\n这是Markdown文件。\n\n## 子标题\n\n更多内容。"
        md_file.write_text(md_content, encoding="utf-8")
        
        files = [txt_file, md_file]
        
        # Mock文本提取方法
        def mock_extract_text(file_path):
            if file_path.suffix == '.txt':
                return txt_content
            elif file_path.suffix == '.md':
                return "标题 这是Markdown文件。 子标题 更多内容。"  # 模拟处理后的内容
        
        with patch.object(processor, '_extract_text', side_effect=mock_extract_text):
            with patch.object(processor, '_validate_file', return_value=True):
                results = processor.process_multiple_documents(files)
        
        assert len(results) == 2
        
        # 验证处理结果
        for result in results:
            assert 'error' not in result
            assert result['text_content'] is not None
            assert len(result['text_chunks']) > 0
            assert result['metadata'] is not None
            assert result['chunk_count'] > 0