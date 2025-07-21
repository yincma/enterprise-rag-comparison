"""
向量存储模块
基于ChromaDB实现文档向量化存储和检索
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
import uuid

# 向量数据库和嵌入模型
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# 本地模块
from .utils.config import config_manager
from .utils.helpers import measure_performance, Timer, create_directory_if_not_exists

logger = logging.getLogger(__name__)

class VectorStore:
    """向量存储管理器"""
    
    def __init__(self):
        """初始化向量存储"""
        self.config = config_manager.load_app_config()
        self.model_config = config_manager.load_model_config()
        
        # 向量存储配置
        self.vector_config = self.config.get('vector_store', {})
        self.persist_directory = Path(self.vector_config.get('persist_directory', './data/vector_db'))
        self.collection_name = self.vector_config.get('collection_name', 'enterprise_documents')
        
        # 确保数据目录存在
        create_directory_if_not_exists(self.persist_directory)
        
        # 嵌入模型配置
        self.embedding_config = self.model_config.get('embedding', {})
        self.embedding_model_name = self.embedding_config.get('model_name', 'all-MiniLM-L6-v2')
        
        # 检索配置
        self.retrieval_config = self.vector_config
        self.top_k = self.retrieval_config.get('top_k', 5)
        self.similarity_threshold = self.retrieval_config.get('similarity_threshold', 0.7)
        
        # 初始化组件
        self._init_chromadb()
        self._init_embedding_model()
        
        logger.info(f"向量存储初始化完成: {self.persist_directory}")
    
    def _init_chromadb(self):
        """初始化ChromaDB客户端"""
        try:
            # 配置ChromaDB设置
            settings = Settings(
                persist_directory=str(self.persist_directory),
                anonymized_telemetry=False,
                is_persistent=True
            )
            
            # 创建持久化客户端
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=settings
            )
            
            # 获取或创建集合
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name
                )
                logger.info(f"成功连接到现有集合: {self.collection_name}")
            except Exception:
                # 集合不存在，创建新集合
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "企业文档向量存储集合"}
                )
                logger.info(f"成功创建新集合: {self.collection_name}")
        
        except Exception as e:
            logger.error(f"ChromaDB初始化失败: {e}")
            raise
    
    def _init_embedding_model(self):
        """初始化嵌入模型"""
        try:
            with Timer("加载嵌入模型"):
                # 模型参数
                model_kwargs = self.embedding_config.get('model_kwargs', {'device': 'cpu'})
                
                # 加载SentenceTransformer模型
                self.embedding_model = SentenceTransformer(
                    self.embedding_model_name,
                    **model_kwargs
                )
                
                # 获取向量维度
                self.embedding_dimension = self.embedding_model.get_sentence_embedding_dimension()
                
                logger.info(f"嵌入模型加载完成: {self.embedding_model_name}, 维度: {self.embedding_dimension}")
        
        except Exception as e:
            logger.error(f"嵌入模型初始化失败: {e}")
            raise
    
    @measure_performance
    def add_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        添加文档到向量存储
        
        Args:
            documents: 文档列表，每个文档包含text_chunks和metadata
            
        Returns:
            添加结果统计
        """
        if not documents:
            return {"added_chunks": 0, "total_documents": 0}
        
        all_texts = []
        all_metadatas = []
        all_ids = []
        
        total_chunks = 0
        
        with Timer(f"处理 {len(documents)} 个文档"):
            for doc in documents:
                if 'error' in doc:
                    logger.warning(f"跳过错误文档: {doc.get('filename', 'unknown')}")
                    continue
                
                text_chunks = doc.get('text_chunks', [])
                if not text_chunks:
                    continue
                
                base_metadata = doc.get('metadata', {})
                
                # 为每个文本块生成ID和元数据
                for i, chunk in enumerate(text_chunks):
                    if not chunk.strip():
                        continue
                    
                    chunk_id = str(uuid.uuid4())
                    chunk_metadata = {
                        **base_metadata,
                        'chunk_index': i,
                        'chunk_id': chunk_id,
                        'document_id': base_metadata.get('file_hash', chunk_id),
                        'text_length': len(chunk)
                    }
                    
                    all_texts.append(chunk)
                    all_metadatas.append(chunk_metadata)
                    all_ids.append(chunk_id)
                    total_chunks += 1
        
        if not all_texts:
            logger.warning("没有有效的文本块可以添加")
            return {"added_chunks": 0, "total_documents": len(documents)}
        
        # 生成嵌入向量
        with Timer(f"生成 {len(all_texts)} 个文本块的嵌入向量"):
            embeddings = self._generate_embeddings(all_texts)
        
        # 添加到ChromaDB
        with Timer("添加向量到数据库"):
            self.collection.add(
                embeddings=embeddings,
                documents=all_texts,
                metadatas=all_metadatas,
                ids=all_ids
            )
        
        result = {
            "added_chunks": len(all_texts),
            "total_documents": len(documents),
            "total_collection_size": self.collection.count()
        }
        
        logger.info(f"成功添加 {len(all_texts)} 个文本块到向量数据库")
        return result
    
    @measure_performance
    def search(
        self, 
        query: str, 
        top_k: Optional[int] = None, 
        similarity_threshold: Optional[float] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似文档
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            similarity_threshold: 相似度阈值
            filter_metadata: 元数据过滤条件
            
        Returns:
            搜索结果列表
        """
        if not query.strip():
            return []
        
        # 使用参数或默认值
        k = top_k or self.top_k
        threshold = similarity_threshold or self.similarity_threshold
        
        with Timer(f"向量检索查询: {query[:50]}..."):
            # 生成查询向量
            query_embedding = self._generate_embeddings([query])[0]
            
            # 搜索参数
            search_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": k,
                "include": ["documents", "metadatas", "distances"]
            }
            
            # 添加过滤条件
            if filter_metadata:
                search_kwargs["where"] = filter_metadata
            
            # 执行搜索
            results = self.collection.query(**search_kwargs)
            
            # 处理搜索结果
            processed_results = []
            
            if results and results['documents'] and results['documents'][0]:
                documents = results['documents'][0]
                metadatas = results['metadatas'][0]
                distances = results['distances'][0]
                
                for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
                    # 转换距离为相似度分数（0-1，1最相似）
                    similarity_score = 1 / (1 + distance)
                    
                    # 应用相似度阈值
                    if similarity_score >= threshold:
                        result_item = {
                            'content': doc,
                            'metadata': metadata,
                            'similarity_score': similarity_score,
                            'distance': distance,
                            'rank': i + 1
                        }
                        processed_results.append(result_item)
            
            logger.info(f"检索完成，返回 {len(processed_results)} 个相关结果")
            return processed_results
    
    def search_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        """
        根据文档ID搜索所有相关块
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档块列表
        """
        try:
            results = self.collection.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"]
            )
            
            processed_results = []
            if results and results['documents']:
                for doc, metadata in zip(results['documents'], results['metadatas']):
                    processed_results.append({
                        'content': doc,
                        'metadata': metadata
                    })
            
            return processed_results
        
        except Exception as e:
            logger.error(f"根据文档ID搜索失败: {e}")
            return []
    
    def delete_document(self, document_id: str) -> bool:
        """
        删除指定文档的所有块
        
        Args:
            document_id: 文档ID
            
        Returns:
            是否删除成功
        """
        try:
            # 先查找要删除的块
            existing_chunks = self.collection.get(
                where={"document_id": document_id},
                include=["documents"]
            )
            
            if not existing_chunks or not existing_chunks['ids']:
                logger.warning(f"未找到要删除的文档: {document_id}")
                return False
            
            # 删除所有相关块
            self.collection.delete(
                where={"document_id": document_id}
            )
            
            deleted_count = len(existing_chunks['ids'])
            logger.info(f"成功删除文档 {document_id} 的 {deleted_count} 个文本块")
            return True
        
        except Exception as e:
            logger.error(f"删除文档失败: {document_id}, 错误: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            统计信息字典
        """
        try:
            total_count = self.collection.count()
            
            # 获取样本数据以分析
            sample_results = self.collection.peek(limit=100)
            
            stats = {
                "total_chunks": total_count,
                "collection_name": self.collection_name,
                "embedding_model": self.embedding_model_name,
                "embedding_dimension": self.embedding_dimension,
                "persist_directory": str(self.persist_directory)
            }
            
            # 如果有数据，添加更多统计信息
            if sample_results and sample_results['metadatas']:
                # 统计文档数量
                document_ids = set()
                file_types = {}
                
                for metadata in sample_results['metadatas']:
                    if 'document_id' in metadata:
                        document_ids.add(metadata['document_id'])
                    
                    if 'file_extension' in metadata:
                        ext = metadata['file_extension']
                        file_types[ext] = file_types.get(ext, 0) + 1
                
                stats.update({
                    "unique_documents": len(document_ids),
                    "file_types": file_types
                })
            
            return stats
        
        except Exception as e:
            logger.error(f"获取集合统计信息失败: {e}")
            return {"error": str(e)}
    
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        生成文本嵌入向量
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表
        """
        try:
            # 编码参数
            encode_kwargs = self.embedding_config.get('encode_kwargs', {
                'normalize_embeddings': True,
                'batch_size': 32
            })
            
            # 生成嵌入向量
            embeddings = self.embedding_model.encode(
                texts,
                **encode_kwargs
            )
            
            # 转换为列表格式
            return embeddings.tolist()
        
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            raise
    
    def clear_collection(self) -> bool:
        """
        清空集合中的所有数据
        
        Returns:
            是否清空成功
        """
        try:
            # 删除现有集合
            self.client.delete_collection(self.collection_name)
            
            # 重新创建集合
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "企业文档向量存储集合"}
            )
            
            logger.info(f"集合 {self.collection_name} 已清空")
            return True
        
        except Exception as e:
            logger.error(f"清空集合失败: {e}")
            return False
    
    def update_search_params(self, top_k: Optional[int] = None, similarity_threshold: Optional[float] = None):
        """
        更新搜索参数
        
        Args:
            top_k: 新的返回结果数量
            similarity_threshold: 新的相似度阈值
        """
        if top_k is not None:
            self.top_k = top_k
            logger.info(f"搜索结果数量已更新为: {top_k}")
        
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
            logger.info(f"相似度阈值已更新为: {similarity_threshold}")


# 全局向量存储实例
vector_store = VectorStore()