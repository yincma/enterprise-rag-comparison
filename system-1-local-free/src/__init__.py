"""
企业级本地RAG知识问答系统
系统一：零成本本地化RAG解决方案

Author: 企业RAG研发团队
Version: 1.0.0
License: MIT
"""

__version__ = "1.0.0"
__author__ = "企业RAG研发团队"
__description__ = "基于Ollama和ChromaDB的零成本本地化RAG解决方案"

# 导入核心模块
from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from .llm_manager import LLMManager
from .rag_pipeline import RAGPipeline

__all__ = [
    "DocumentProcessor",
    "VectorStore", 
    "LLMManager",
    "RAGPipeline"
]