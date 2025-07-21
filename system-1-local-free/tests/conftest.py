"""
测试配置文件
提供测试夹具和共用测试工具
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import yaml
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

@pytest.fixture
def temp_dir():
    """创建临时目录"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def test_config_dir(temp_dir):
    """创建测试配置目录"""
    config_dir = temp_dir / "config"
    config_dir.mkdir()
    
    # 创建测试应用配置
    app_config = {
        "app": {
            "name": "测试RAG系统",
            "version": "1.0.0",
            "debug": True
        },
        "vector_store": {
            "persist_directory": str(temp_dir / "vector_db"),
            "collection_name": "test_documents",
            "chunk_size": 500,
            "chunk_overlap": 50,
            "top_k": 3,
            "similarity_threshold": 0.5
        },
        "document_processing": {
            "supported_formats": [".txt", ".md"],
            "max_file_size": 1048576  # 1MB
        },
        "logging": {
            "log_directory": str(temp_dir / "logs"),
            "log_file": "test.log"
        }
    }
    
    # 创建测试模型配置
    model_config = {
        "llm": {
            "provider": "test",
            "model_name": "test-model",
            "temperature": 0.1,
            "max_tokens": 100
        },
        "embedding": {
            "model_name": "test-embedding",
            "dimension": 384
        },
        "prompts": {
            "qa_template": "测试问答模板: {context} 问题: {question}",
            "chat_template": "测试对话模板: {chat_history} 上下文: {context} 问题: {question}"
        }
    }
    
    # 保存配置文件
    with open(config_dir / "app_config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(app_config, f, default_flow_style=False, allow_unicode=True)
    
    with open(config_dir / "model_config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(model_config, f, default_flow_style=False, allow_unicode=True)
    
    return config_dir

@pytest.fixture
def test_text_file(temp_dir):
    """创建测试文本文件"""
    test_file = temp_dir / "test.txt"
    content = "这是一个测试文档。\n\n包含多行文本内容。\n测试文本处理功能。"
    test_file.write_text(content, encoding="utf-8")
    return test_file

@pytest.fixture
def test_markdown_file(temp_dir):
    """创建测试Markdown文件"""
    test_file = temp_dir / "test.md"
    content = """# 测试文档

## 第一章
这是第一章的内容。

## 第二章
这是第二章的内容，包含更多信息。

- 列表项目1
- 列表项目2
- 列表项目3
"""
    test_file.write_text(content, encoding="utf-8")
    return test_file

@pytest.fixture
def sample_documents():
    """示例文档数据"""
    return [
        {
            "filename": "doc1.txt",
            "text_content": "这是第一个测试文档的内容。包含一些重要信息。",
            "text_chunks": ["这是第一个测试文档的内容。", "包含一些重要信息。"],
            "metadata": {
                "filename": "doc1.txt",
                "file_extension": ".txt",
                "file_size": 100,
                "chunk_count": 2
            }
        },
        {
            "filename": "doc2.txt", 
            "text_content": "这是第二个测试文档。提供更多的测试数据。",
            "text_chunks": ["这是第二个测试文档。", "提供更多的测试数据。"],
            "metadata": {
                "filename": "doc2.txt",
                "file_extension": ".txt",
                "file_size": 120,
                "chunk_count": 2
            }
        }
    ]

@pytest.fixture
def mock_embedding_model():
    """模拟嵌入模型"""
    class MockEmbeddingModel:
        def __init__(self):
            self.model_name = "mock-embedding-model"
            
        def encode(self, texts, **kwargs):
            # 返回模拟的嵌入向量
            import numpy as np
            return np.random.rand(len(texts), 384).tolist()
            
        def get_sentence_embedding_dimension(self):
            return 384
    
    return MockEmbeddingModel()

@pytest.fixture
def mock_llm_client():
    """模拟LLM客户端"""
    class MockLLMClient:
        def generate(self, model, prompt, system=None, options=None, stream=False):
            if stream:
                return iter([{"response": "测试"}, {"response": "回答"}])
            else:
                return {
                    "response": "这是一个测试回答。基于提供的上下文信息。",
                    "eval_count": 10,
                    "eval_duration": 1000000000  # 1秒，以纳秒为单位
                }
        
        def list(self):
            return {
                "models": [
                    {"name": "test-model:latest", "size": 1000000}
                ]
            }
        
        def pull(self, model_name, stream=False):
            if stream:
                return iter([{"status": "下载完成"}])
            return {"status": "success"}
    
    return MockLLMClient()

class TestDataGenerator:
    """测试数据生成器"""
    
    @staticmethod
    def create_test_chunks(count=5, size=100):
        """创建测试文本块"""
        chunks = []
        for i in range(count):
            content = f"测试文本块 {i+1}。" + "内容" * (size // 10)
            chunks.append(content)
        return chunks
    
    @staticmethod
    def create_test_metadata(filename="test.txt"):
        """创建测试元数据"""
        return {
            "filename": filename,
            "file_extension": Path(filename).suffix,
            "file_size": 1000,
            "chunk_count": 5,
            "created_time": 1640995200,  # 2022-01-01
            "modified_time": 1640995200
        }

# 全局测试数据生成器
test_data = TestDataGenerator()