"""
API端点测试套件
测试FastAPI REST接口的各种功能
"""

import pytest
import requests
import tempfile
import json
from pathlib import Path
from typing import Dict, Any
import time

# 测试配置
API_BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 30

class TestAPIEndpoints:
    """API端点测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """测试设置"""
        self.base_url = API_BASE_URL
        self.session = requests.Session()
        self.session.timeout = TEST_TIMEOUT
        
        # 检查API服务器是否运行
        try:
            response = self.session.get(f"{self.base_url}/")
            response.raise_for_status()
        except requests.exceptions.RequestException:
            pytest.skip("API服务器未运行，跳过API测试")
    
    def test_root_endpoint(self):
        """测试根端点"""
        response = self.session.get(f"{self.base_url}/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs_url" in data
        assert data["message"] == "企业RAG知识问答系统API"
    
    def test_health_check(self):
        """测试健康检查端点"""
        response = self.session.get(f"{self.base_url}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "system_health" in data
        assert "memory_stats" in data
        assert "knowledge_base_stats" in data
        assert "resilience_status" in data
        assert "uptime" in data
        
        # 检查系统健康状态
        system_health = data["system_health"]
        assert "overall" in system_health
        assert system_health["overall"] in ["healthy", "degraded", "failing"]
    
    def test_system_info(self):
        """测试系统信息端点"""
        response = self.session.get(f"{self.base_url}/system/info")
        assert response.status_code == 200
        
        data = response.json()
        assert "system_info" in data
        assert "app_info" in data
        
        app_info = data["app_info"]
        assert "name" in app_info
        assert "version" in app_info
        assert "uptime" in app_info
    
    def test_memory_stats(self):
        """测试内存统计端点"""
        response = self.session.get(f"{self.base_url}/system/memory")
        assert response.status_code == 200
        
        data = response.json()
        assert "memory_info" in data
        
        memory_info = data["memory_info"]
        assert "process_memory_mb" in memory_info
        assert "system_memory_used_percent" in memory_info
    
    def test_knowledge_base_stats(self):
        """测试知识库统计端点"""
        response = self.session.get(f"{self.base_url}/documents/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_chunks" in data
        assert "collection_name" in data
        assert "embedding_model" in data
        
        # 验证数据类型
        assert isinstance(data["total_chunks"], int)
        assert data["total_chunks"] >= 0
    
    def test_query_endpoint_validation(self):
        """测试查询端点的数据验证"""
        # 测试空查询
        response = self.session.post(
            f"{self.base_url}/query",
            json={"query": ""}
        )
        assert response.status_code == 422  # 验证错误
        
        # 测试过长查询
        response = self.session.post(
            f"{self.base_url}/query",
            json={"query": "x" * 1001}  # 超过1000字符限制
        )
        assert response.status_code == 422
        
        # 测试无效的top_k
        response = self.session.post(
            f"{self.base_url}/query",
            json={"query": "测试查询", "top_k": 0}
        )
        assert response.status_code == 422
        
        # 测试无效的相似度阈值
        response = self.session.post(
            f"{self.base_url}/query",
            json={"query": "测试查询", "similarity_threshold": 1.5}
        )
        assert response.status_code == 422
    
    def test_query_endpoint_success(self):
        """测试查询端点成功响应"""
        response = self.session.post(
            f"{self.base_url}/query",
            json={
                "query": "什么是RAG？",
                "top_k": 5,
                "similarity_threshold": 0.7,
                "include_sources": True
            }
        )
        
        # 无论知识库是否有数据，都应该返回200
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert "answer" in data
        assert "query_time" in data
        assert "metadata" in data
        
        # 检查数据类型
        assert isinstance(data["success"], bool)
        assert isinstance(data["answer"], str)
        assert isinstance(data["query_time"], (int, float))
        assert data["query_time"] >= 0
    
    def test_chat_endpoint_validation(self):
        """测试聊天端点的数据验证"""
        # 测试空消息列表
        response = self.session.post(
            f"{self.base_url}/chat",
            json={"messages": []}
        )
        assert response.status_code == 422
        
        # 测试无效角色
        response = self.session.post(
            f"{self.base_url}/chat",
            json={
                "messages": [
                    {"role": "invalid_role", "content": "测试消息"}
                ]
            }
        )
        assert response.status_code == 422
        
        # 测试空内容
        response = self.session.post(
            f"{self.base_url}/chat",
            json={
                "messages": [
                    {"role": "user", "content": ""}
                ]
            }
        )
        assert response.status_code == 422
    
    def test_chat_endpoint_success(self):
        """测试聊天端点成功响应"""
        response = self.session.post(
            f"{self.base_url}/chat",
            json={
                "messages": [
                    {"role": "user", "content": "你好，请介绍一下自己"}
                ],
                "top_k": 3,
                "similarity_threshold": 0.6
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert "response" in data
        assert "response_time" in data
        
        # 检查数据类型
        assert isinstance(data["success"], bool)
        assert isinstance(data["response"], str)
        assert isinstance(data["response_time"], (int, float))
    
    def test_document_upload_validation(self):
        """测试文档上传验证"""
        # 测试无文件上传
        response = self.session.post(f"{self.base_url}/documents")
        assert response.status_code == 422
    
    def test_document_upload_with_text_file(self):
        """测试上传文本文件"""
        # 创建临时测试文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("这是一个测试文档。\n\n包含测试内容用于验证文档上传功能。\n")
            temp_file_path = f.name
        
        try:
            with open(temp_file_path, 'rb') as f:
                files = {'files': ('test.txt', f, 'text/plain')}
                response = self.session.post(
                    f"{self.base_url}/documents",
                    files=files
                )
            
            assert response.status_code == 200
            
            data = response.json()
            assert "success" in data
            assert "processed_files" in data
            assert "added_chunks" in data
            
            # 检查处理结果
            assert data["success"] is True
            assert data["processed_files"] >= 1
            assert data["added_chunks"] >= 1
            
        finally:
            # 清理临时文件
            Path(temp_file_path).unlink(missing_ok=True)
    
    def test_clear_knowledge_base(self):
        """测试清空知识库"""
        response = self.session.delete(f"{self.base_url}/documents")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试不存在的端点
        response = self.session.get(f"{self.base_url}/nonexistent")
        assert response.status_code == 404
        
        # 测试错误的HTTP方法
        response = self.session.patch(f"{self.base_url}/query")
        assert response.status_code == 405

@pytest.mark.integration
class TestAPIIntegration:
    """API集成测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """集成测试设置"""
        self.base_url = API_BASE_URL
        self.session = requests.Session()
        self.session.timeout = TEST_TIMEOUT
        
        # 检查API服务器
        try:
            response = self.session.get(f"{self.base_url}/")
            response.raise_for_status()
        except requests.exceptions.RequestException:
            pytest.skip("API服务器未运行，跳过集成测试")
    
    def test_full_workflow(self):
        """测试完整工作流程"""
        # 1. 检查初始状态
        response = self.session.get(f"{self.base_url}/documents/stats")
        initial_stats = response.json()
        initial_chunks = initial_stats.get("total_chunks", 0)
        
        # 2. 上传测试文档
        test_content = """
        # RAG系统介绍
        
        RAG（Retrieval-Augmented Generation）是一种结合了信息检索和文本生成的技术。
        
        ## 主要优势
        - 提高回答的准确性
        - 减少幻觉现象
        - 支持实时信息更新
        
        ## 应用场景
        RAG特别适用于知识问答、文档搜索和智能客服等场景。
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(test_content)
            temp_file_path = f.name
        
        try:
            # 上传文档
            with open(temp_file_path, 'rb') as f:
                files = {'files': ('rag_intro.md', f, 'text/markdown')}
                upload_response = self.session.post(
                    f"{self.base_url}/documents",
                    files=files
                )
            
            assert upload_response.status_code == 200
            upload_data = upload_response.json()
            assert upload_data["success"] is True
            assert upload_data["processed_files"] == 1
            assert upload_data["added_chunks"] > 0
            
            # 等待处理完成
            time.sleep(2)
            
            # 3. 验证文档已添加
            response = self.session.get(f"{self.base_url}/documents/stats")
            new_stats = response.json()
            new_chunks = new_stats.get("total_chunks", 0)
            assert new_chunks > initial_chunks
            
            # 4. 测试查询功能
            query_response = self.session.post(
                f"{self.base_url}/query",
                json={
                    "query": "什么是RAG？",
                    "top_k": 3,
                    "include_sources": True
                }
            )
            
            assert query_response.status_code == 200
            query_data = query_response.json()
            assert query_data["success"] is True
            assert len(query_data["answer"]) > 0
            
            # 检查是否包含相关信息
            answer = query_data["answer"].lower()
            assert any(keyword in answer for keyword in ["rag", "检索", "生成", "retrieval"])
            
            # 5. 测试聊天功能
            chat_response = self.session.post(
                f"{self.base_url}/chat",
                json={
                    "messages": [
                        {"role": "user", "content": "RAG有什么优势？"}
                    ]
                }
            )
            
            assert chat_response.status_code == 200
            chat_data = chat_response.json()
            assert chat_data["success"] is True
            assert len(chat_data["response"]) > 0
            
            # 6. 测试多轮对话
            multi_chat_response = self.session.post(
                f"{self.base_url}/chat",
                json={
                    "messages": [
                        {"role": "user", "content": "什么是RAG？"},
                        {"role": "assistant", "content": chat_data["response"]},
                        {"role": "user", "content": "它适用于哪些场景？"}
                    ]
                }
            )
            
            assert multi_chat_response.status_code == 200
            multi_chat_data = multi_chat_response.json()
            assert multi_chat_data["success"] is True
            
            # 7. 清理：清空知识库（可选）
            # clear_response = self.session.delete(f"{self.base_url}/documents")
            # assert clear_response.status_code == 200
            
        finally:
            # 清理临时文件
            Path(temp_file_path).unlink(missing_ok=True)

@pytest.mark.performance
class TestAPIPerformance:
    """API性能测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """性能测试设置"""
        self.base_url = API_BASE_URL
        self.session = requests.Session()
        
        # 检查API服务器
        try:
            response = self.session.get(f"{self.base_url}/")
            response.raise_for_status()
        except requests.exceptions.RequestException:
            pytest.skip("API服务器未运行，跳过性能测试")
    
    def test_query_response_time(self):
        """测试查询响应时间"""
        start_time = time.time()
        
        response = self.session.post(
            f"{self.base_url}/query",
            json={"query": "测试查询性能"}
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 10.0  # 响应时间应少于10秒
        
        # 检查API返回的时间统计
        data = response.json()
        api_query_time = data.get("query_time", 0)
        assert api_query_time > 0
        assert api_query_time <= response_time  # API统计时间应该小于等于总时间
    
    def test_concurrent_queries(self):
        """测试并发查询"""
        import concurrent.futures
        import threading
        
        def make_query(query_id):
            response = self.session.post(
                f"{self.base_url}/query",
                json={"query": f"并发查询测试 {query_id}"}
            )
            return response.status_code, response.json()
        
        # 执行5个并发查询
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_query, i) for i in range(5)]
            results = [future.result() for future in futures]
        
        # 验证所有查询都成功
        for status_code, data in results:
            assert status_code == 200
            assert data["success"] is True

if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])