"""
RAG主流程模块
集成文档处理、向量检索和LLM生成的完整RAG流程
"""

import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import time
from pathlib import Path

# 本地模块
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from document_processor import document_processor
from vector_store import vector_store
from llm_manager import llm_manager
from utils.config import config_manager
from utils.helpers import measure_performance, Timer

logger = logging.getLogger(__name__)

class RAGPipeline:
    """RAG流程管理器"""
    
    def __init__(self):
        """初始化RAG流程"""
        self.config = config_manager.load_app_config()
        
        # 组件引用
        self.doc_processor = document_processor
        self.vector_store = vector_store
        self.llm = llm_manager
        
        # 检索配置
        self.retrieval_config = self.config.get('vector_store', {})
        self.top_k = self.retrieval_config.get('top_k', 5)
        self.similarity_threshold = self.retrieval_config.get('similarity_threshold', 0.7)
        
        # 性能监控
        self.enable_performance_tracking = self.config.get('monitoring', {}).get('enable_performance_tracking', True)
        
        logger.info("RAG流程管理器初始化完成")
    
    @measure_performance
    def add_documents_to_knowledge_base(
        self, 
        file_paths: Union[str, Path, List[Union[str, Path]]]
    ) -> Dict[str, Any]:
        """
        将文档添加到知识库
        
        Args:
            file_paths: 单个文件路径或文件路径列表
            
        Returns:
            添加结果统计
        """
        # 规范化文件路径
        if isinstance(file_paths, (str, Path)):
            file_paths = [file_paths]
        
        logger.info(f"开始将 {len(file_paths)} 个文档添加到知识库")
        
        with Timer("文档添加流程"):
            # 步骤1：处理文档
            with Timer("文档处理阶段"):
                processed_docs = self.doc_processor.process_multiple_documents(file_paths)
            
            # 过滤处理成功的文档
            successful_docs = [doc for doc in processed_docs if 'error' not in doc]
            failed_docs = [doc for doc in processed_docs if 'error' in doc]
            
            if not successful_docs:
                return {
                    "success": False,
                    "message": "没有文档处理成功",
                    "failed_documents": len(failed_docs),
                    "added_chunks": 0
                }
            
            # 步骤2：添加到向量存储
            with Timer("向量存储阶段"):
                vector_result = self.vector_store.add_documents(successful_docs)
            
            # 整合结果
            result = {
                "success": True,
                "total_documents": len(file_paths),
                "successful_documents": len(successful_docs),
                "failed_documents": len(failed_docs),
                "added_chunks": vector_result.get("added_chunks", 0),
                "collection_size": vector_result.get("total_collection_size", 0)
            }
            
            if failed_docs:
                result["failed_files"] = [doc["filename"] for doc in failed_docs]
                result["failure_reasons"] = [doc.get("error", "未知错误") for doc in failed_docs]
            
            logger.info(f"知识库更新完成: 成功 {result['successful_documents']} 个文档, {result['added_chunks']} 个文本块")
            return result
    
    @measure_performance
    def query_knowledge_base(
        self, 
        query: str, 
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        include_source_info: bool = True
    ) -> Dict[str, Any]:
        """
        查询知识库并生成回答
        
        Args:
            query: 用户查询
            top_k: 检索文档数量
            similarity_threshold: 相似度阈值
            include_source_info: 是否包含来源信息
            
        Returns:
            查询结果和生成的回答
        """
        if not query.strip():
            return {
                "success": False,
                "message": "查询不能为空",
                "answer": "",
                "retrieved_documents": []
            }
        
        logger.info(f"处理知识库查询: {query[:100]}...")
        
        with Timer("知识库查询流程"):
            # 步骤1：向量检索
            with Timer("向量检索阶段"):
                retrieved_docs = self.vector_store.search(
                    query=query,
                    top_k=top_k or self.top_k,
                    similarity_threshold=similarity_threshold or self.similarity_threshold
                )
            
            if not retrieved_docs:
                return {
                    "success": True,
                    "message": "未找到相关文档",
                    "answer": "抱歉，我在知识库中没有找到与您的问题相关的信息。请尝试使用不同的关键词重新提问。",
                    "retrieved_documents": [],
                    "query": query
                }
            
            # 步骤2：构建上下文
            context = self._build_context(retrieved_docs)
            
            # 步骤3：生成回答
            with Timer("LLM生成阶段"):
                answer = self.llm.generate_response(query, context=context)
            
            # 整理结果
            result = {
                "success": True,
                "query": query,
                "answer": answer,
                "retrieved_documents": self._format_retrieved_docs(retrieved_docs, include_source_info),
                "retrieval_count": len(retrieved_docs),
                "context_length": len(context),
                "response_time": time.time()
            }
            
            logger.info(f"查询完成，检索到 {len(retrieved_docs)} 个相关文档")
            return result
    
    @measure_performance
    def chat_with_context(
        self,
        messages: List[Dict[str, str]],
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        基于上下文的对话
        
        Args:
            messages: 对话历史 [{"role": "user/assistant", "content": "..."}]
            top_k: 检索文档数量
            similarity_threshold: 相似度阈值
            
        Returns:
            对话结果
        """
        if not messages:
            return {
                "success": False,
                "message": "对话历史不能为空"
            }
        
        # 获取最新用户消息
        latest_user_message = None
        for message in reversed(messages):
            if message.get('role') == 'user':
                latest_user_message = message.get('content', '')
                break
        
        if not latest_user_message:
            return {
                "success": False,
                "message": "未找到用户消息"
            }
        
        logger.info(f"处理对话查询: {latest_user_message[:100]}...")
        
        with Timer("上下文对话流程"):
            # 步骤1：基于最新消息检索相关文档
            retrieved_docs = self.vector_store.search(
                query=latest_user_message,
                top_k=top_k or self.top_k,
                similarity_threshold=similarity_threshold or self.similarity_threshold
            )
            
            # 步骤2：构建文档上下文
            doc_context = self._build_context(retrieved_docs) if retrieved_docs else None
            
            # 步骤3：生成对话回应
            with Timer("对话生成阶段"):
                response = self.llm.chat_with_history(messages, context=doc_context)
            
            # 整理结果
            result = {
                "success": True,
                "response": response,
                "retrieved_documents": self._format_retrieved_docs(retrieved_docs, True) if retrieved_docs else [],
                "retrieval_count": len(retrieved_docs) if retrieved_docs else 0,
                "has_context": doc_context is not None
            }
            
            return result
    
    def get_document_summary(self, document_id: str) -> Dict[str, Any]:
        """
        获取文档摘要
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档摘要信息
        """
        try:
            # 获取文档所有块
            doc_chunks = self.vector_store.search_by_document(document_id)
            
            if not doc_chunks:
                return {
                    "success": False,
                    "message": f"未找到文档: {document_id}"
                }
            
            # 合并所有文本块
            full_text = "\n".join([chunk['content'] for chunk in doc_chunks])
            
            # 生成摘要
            summary = self.llm.summarize_text(full_text)
            
            # 获取文档元数据
            metadata = doc_chunks[0]['metadata'] if doc_chunks else {}
            
            return {
                "success": True,
                "document_id": document_id,
                "filename": metadata.get('filename', ''),
                "summary": summary,
                "chunk_count": len(doc_chunks),
                "total_length": len(full_text),
                "metadata": metadata
            }
        
        except Exception as e:
            logger.error(f"获取文档摘要失败: {document_id}, 错误: {e}")
            return {
                "success": False,
                "message": f"获取摘要失败: {e}"
            }
    
    def delete_document_from_knowledge_base(self, document_id: str) -> Dict[str, Any]:
        """
        从知识库删除文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            删除结果
        """
        try:
            success = self.vector_store.delete_document(document_id)
            
            if success:
                logger.info(f"文档已从知识库删除: {document_id}")
                return {
                    "success": True,
                    "message": f"文档删除成功: {document_id}"
                }
            else:
                return {
                    "success": False,
                    "message": f"文档删除失败: {document_id}"
                }
        
        except Exception as e:
            logger.error(f"删除文档失败: {document_id}, 错误: {e}")
            return {
                "success": False,
                "message": f"删除操作失败: {e}"
            }
    
    def get_knowledge_base_stats(self) -> Dict[str, Any]:
        """
        获取知识库统计信息
        
        Returns:
            统计信息
        """
        try:
            vector_stats = self.vector_store.get_collection_stats()
            
            return {
                "success": True,
                "statistics": vector_stats,
                "system_info": {
                    "embedding_model": vector_stats.get("embedding_model"),
                    "llm_model": self.llm.model_name,
                    "collection_name": vector_stats.get("collection_name")
                }
            }
        
        except Exception as e:
            logger.error(f"获取知识库统计失败: {e}")
            return {
                "success": False,
                "message": f"获取统计信息失败: {e}"
            }
    
    def _build_context(self, retrieved_docs: List[Dict[str, Any]]) -> str:
        """
        构建上下文文本
        
        Args:
            retrieved_docs: 检索到的文档列表
            
        Returns:
            构建的上下文字符串
        """
        if not retrieved_docs:
            return ""
        
        context_parts = []
        
        for i, doc in enumerate(retrieved_docs, 1):
            content = doc['content']
            metadata = doc.get('metadata', {})
            filename = metadata.get('filename', f'文档{i}')
            
            # 格式化每个文档片段
            context_part = f"[文档{i}: {filename}]\n{content}\n"
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _format_retrieved_docs(
        self, 
        retrieved_docs: List[Dict[str, Any]], 
        include_source_info: bool = True
    ) -> List[Dict[str, Any]]:
        """
        格式化检索到的文档
        
        Args:
            retrieved_docs: 原始检索结果
            include_source_info: 是否包含来源信息
            
        Returns:
            格式化后的文档列表
        """
        formatted_docs = []
        
        for doc in retrieved_docs:
            formatted_doc = {
                "content": doc['content'],
                "similarity_score": round(doc['similarity_score'], 3),
                "rank": doc['rank']
            }
            
            if include_source_info:
                metadata = doc.get('metadata', {})
                formatted_doc.update({
                    "source": {
                        "filename": metadata.get('filename', ''),
                        "chunk_index": metadata.get('chunk_index', 0),
                        "file_extension": metadata.get('file_extension', ''),
                        "document_id": metadata.get('document_id', '')
                    }
                })
            
            formatted_docs.append(formatted_doc)
        
        return formatted_docs
    
    def clear_knowledge_base(self) -> Dict[str, Any]:
        """
        清空知识库
        
        Returns:
            清空结果
        """
        try:
            success = self.vector_store.clear_collection()
            
            if success:
                logger.info("知识库已清空")
                return {
                    "success": True,
                    "message": "知识库已成功清空"
                }
            else:
                return {
                    "success": False,
                    "message": "知识库清空失败"
                }
        
        except Exception as e:
            logger.error(f"清空知识库失败: {e}")
            return {
                "success": False,
                "message": f"清空操作失败: {e}"
            }
    
    def update_retrieval_params(
        self, 
        top_k: Optional[int] = None, 
        similarity_threshold: Optional[float] = None
    ):
        """
        更新检索参数
        
        Args:
            top_k: 新的检索数量
            similarity_threshold: 新的相似度阈值
        """
        if top_k is not None:
            self.top_k = top_k
            self.vector_store.update_search_params(top_k=top_k)
        
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
            self.vector_store.update_search_params(similarity_threshold=similarity_threshold)
        
        logger.info(f"检索参数已更新: top_k={self.top_k}, threshold={self.similarity_threshold}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        系统健康检查
        
        Returns:
            健康状态信息
        """
        health_status = {
            "overall": "healthy",
            "components": {},
            "timestamp": time.time()
        }
        
        try:
            # 检查LLM状态
            try:
                models = self.llm.list_available_models()
                health_status["components"]["llm"] = {
                    "status": "healthy",
                    "current_model": self.llm.model_name,
                    "available_models": len(models)
                }
            except Exception as e:
                health_status["components"]["llm"] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["overall"] = "degraded"
            
            # 检查向量存储状态
            try:
                stats = self.vector_store.get_collection_stats()
                health_status["components"]["vector_store"] = {
                    "status": "healthy",
                    "total_chunks": stats.get("total_chunks", 0),
                    "collection_name": stats.get("collection_name")
                }
            except Exception as e:
                health_status["components"]["vector_store"] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["overall"] = "degraded"
            
            # 检查文档处理器状态
            try:
                supported_formats = self.doc_processor.get_supported_formats()
                health_status["components"]["document_processor"] = {
                    "status": "healthy",
                    "supported_formats": supported_formats
                }
            except Exception as e:
                health_status["components"]["document_processor"] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["overall"] = "degraded"
        
        except Exception as e:
            health_status["overall"] = "error"
            health_status["error"] = str(e)
        
        return health_status


# 全局RAG流程实例
rag_pipeline = RAGPipeline()