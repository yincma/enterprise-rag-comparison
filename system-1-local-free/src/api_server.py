"""
FastAPI RESTful API服务器
提供RAG系统的HTTP API接口
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import logging
import time
import asyncio
import tempfile
from pathlib import Path

# 本地模块
from .rag_pipeline import rag_pipeline
from .utils.config import config_manager
from .utils.helpers import format_file_size, get_system_info
from .utils.memory_optimizer import get_memory_stats, start_memory_monitoring, stop_memory_monitoring
from .utils.resilience import resilience_manager

logger = logging.getLogger(__name__)

# Pydantic模型定义
class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str = Field(..., description="查询文本", min_length=1, max_length=1000)
    top_k: Optional[int] = Field(5, description="检索文档数量", ge=1, le=20)
    similarity_threshold: Optional[float] = Field(0.7, description="相似度阈值", ge=0.0, le=1.0)
    include_sources: bool = Field(True, description="是否包含来源信息")

class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str = Field(..., description="角色", regex="^(user|assistant)$")
    content: str = Field(..., description="消息内容", min_length=1)

class ChatRequest(BaseModel):
    """聊天请求模型"""
    messages: List[ChatMessage] = Field(..., description="对话历史")
    top_k: Optional[int] = Field(5, description="检索文档数量", ge=1, le=20)
    similarity_threshold: Optional[float] = Field(0.7, description="相似度阈值", ge=0.0, le=1.0)

class QueryResponse(BaseModel):
    """查询响应模型"""
    success: bool = Field(..., description="是否成功")
    answer: str = Field(..., description="回答")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="参考来源")
    query_time: float = Field(..., description="查询耗时(秒)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

class ChatResponse(BaseModel):
    """聊天响应模型"""
    success: bool = Field(..., description="是否成功")
    response: str = Field(..., description="AI回复")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="参考来源")
    response_time: float = Field(..., description="响应耗时(秒)")

class DocumentUploadResponse(BaseModel):
    """文档上传响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    processed_files: int = Field(..., description="已处理文件数")
    added_chunks: int = Field(..., description="添加的文本块数")
    failed_files: Optional[List[str]] = Field(None, description="失败文件列表")

class SystemStatus(BaseModel):
    """系统状态模型"""
    system_health: Dict[str, Any] = Field(..., description="系统健康状态")
    memory_stats: Dict[str, Any] = Field(..., description="内存统计")
    knowledge_base_stats: Dict[str, Any] = Field(..., description="知识库统计")
    resilience_status: Dict[str, Any] = Field(..., description="弹性状态")
    uptime: float = Field(..., description="运行时间(秒)")

# 创建FastAPI应用
app = FastAPI(
    title="企业RAG知识问答系统API",
    description="基于Ollama和ChromaDB的零成本本地化RAG解决方案RESTful API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
app_start_time = time.time()

# 依赖注入函数
async def get_rag_pipeline():
    """获取RAG流程实例"""
    return rag_pipeline

# API端点定义
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("FastAPI服务器启动中...")
    
    # 启动内存监控
    start_memory_monitoring()
    
    # 执行健康检查
    health = rag_pipeline.health_check()
    if health["overall"] != "healthy":
        logger.warning(f"系统健康状态异常: {health}")
    
    logger.info("FastAPI服务器启动完成")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("FastAPI服务器关闭中...")
    
    # 停止内存监控
    stop_memory_monitoring()
    
    logger.info("FastAPI服务器已关闭")

@app.get("/", summary="根路径", description="API服务器根路径")
async def root():
    """根路径"""
    return {
        "message": "企业RAG知识问答系统API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/health",
        "timestamp": time.time()
    }

@app.get("/health", response_model=SystemStatus, summary="健康检查", description="获取系统健康状态")
async def health_check(rag: Any = Depends(get_rag_pipeline)):
    """健康检查端点"""
    try:
        system_health = rag.health_check()
        memory_stats = get_memory_stats()
        knowledge_base_stats = rag.get_knowledge_base_stats()
        resilience_status = resilience_manager.get_system_resilience_status()
        uptime = time.time() - app_start_time
        
        return SystemStatus(
            system_health=system_health,
            memory_stats=memory_stats,
            knowledge_base_stats=knowledge_base_stats,
            resilience_status=resilience_status,
            uptime=uptime
        )
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")

@app.post("/query", response_model=QueryResponse, summary="知识库查询", description="向知识库查询问题")
async def query_knowledge_base(
    request: QueryRequest,
    rag: Any = Depends(get_rag_pipeline)
):
    """知识库查询端点"""
    start_time = time.time()
    
    try:
        result = rag.query_knowledge_base(
            query=request.query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            include_source_info=request.include_sources
        )
        
        query_time = time.time() - start_time
        
        if result["success"]:
            return QueryResponse(
                success=True,
                answer=result["answer"],
                sources=result.get("retrieved_documents") if request.include_sources else None,
                query_time=query_time,
                metadata={
                    "retrieval_count": result.get("retrieval_count", 0),
                    "context_length": result.get("context_length", 0)
                }
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "查询失败")
            )
    
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询处理失败: {str(e)}")

@app.post("/chat", response_model=ChatResponse, summary="对话聊天", description="与AI进行多轮对话")
async def chat_with_ai(
    request: ChatRequest,
    rag: Any = Depends(get_rag_pipeline)
):
    """对话聊天端点"""
    start_time = time.time()
    
    try:
        # 转换消息格式
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        result = rag.chat_with_context(
            messages=messages,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        response_time = time.time() - start_time
        
        if result["success"]:
            return ChatResponse(
                success=True,
                response=result["response"],
                sources=result.get("retrieved_documents"),
                response_time=response_time
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "对话失败")
            )
    
    except Exception as e:
        logger.error(f"对话失败: {e}")
        raise HTTPException(status_code=500, detail=f"对话处理失败: {str(e)}")

@app.post("/documents", response_model=DocumentUploadResponse, summary="上传文档", description="上传文档到知识库")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    rag: Any = Depends(get_rag_pipeline)
):
    """文档上传端点"""
    if not files:
        raise HTTPException(status_code=400, detail="没有上传文件")
    
    # 验证文件
    max_file_size = config_manager.get_app_setting("ui.max_file_size_mb", 100) * 1024 * 1024
    supported_formats = ['.pdf', '.docx', '.txt', '.md']
    
    temp_files = []
    
    try:
        # 保存临时文件
        for file in files:
            if file.size > max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件 {file.filename} 大小超过限制({format_file_size(max_file_size)})"
                )
            
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in supported_formats:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的文件格式: {file_extension}，支持格式: {supported_formats}"
                )
            
            # 保存临时文件
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=file_extension,
                prefix=f"upload_{int(time.time())}_"
            )
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            temp_files.append(temp_file.name)
        
        # 处理文档
        result = rag.add_documents_to_knowledge_base(temp_files)
        
        # 后台清理临时文件
        background_tasks.add_task(cleanup_temp_files, temp_files)
        
        return DocumentUploadResponse(
            success=result["success"],
            message=f"成功处理 {result['successful_documents']} 个文档",
            processed_files=result["successful_documents"],
            added_chunks=result["added_chunks"],
            failed_files=result.get("failed_files")
        )
    
    except HTTPException:
        # 清理临时文件
        cleanup_temp_files(temp_files)
        raise
    except Exception as e:
        # 清理临时文件
        cleanup_temp_files(temp_files)
        logger.error(f"文档上传处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@app.get("/documents/stats", summary="知识库统计", description="获取知识库统计信息")
async def get_knowledge_base_stats(rag: Any = Depends(get_rag_pipeline)):
    """获取知识库统计信息"""
    try:
        result = rag.get_knowledge_base_stats()
        
        if result["success"]:
            return result["statistics"]
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "获取统计信息失败")
            )
    
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@app.delete("/documents", summary="清空知识库", description="清空所有文档")
async def clear_knowledge_base(rag: Any = Depends(get_rag_pipeline)):
    """清空知识库"""
    try:
        result = rag.clear_knowledge_base()
        
        if result["success"]:
            return {"message": result["message"]}
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "清空知识库失败")
            )
    
    except Exception as e:
        logger.error(f"清空知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空知识库失败: {str(e)}")

@app.get("/system/info", summary="系统信息", description="获取系统信息")
async def get_system_information():
    """获取系统信息"""
    try:
        system_info = get_system_info()
        return {
            "system_info": system_info,
            "app_info": {
                "name": config_manager.get_app_setting("app.name", "企业RAG系统"),
                "version": config_manager.get_app_setting("app.version", "1.0.0"),
                "uptime": time.time() - app_start_time
            }
        }
    
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")

@app.get("/system/memory", summary="内存统计", description="获取内存使用统计")
async def get_memory_statistics():
    """获取内存统计"""
    try:
        return get_memory_stats()
    
    except Exception as e:
        logger.error(f"获取内存统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取内存统计失败: {str(e)}")

# 辅助函数
def cleanup_temp_files(file_paths: List[str]):
    """清理临时文件"""
    for file_path in file_paths:
        try:
            Path(file_path).unlink(missing_ok=True)
            logger.debug(f"清理临时文件: {file_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {file_path}, 错误: {e}")

# 错误处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP异常处理器"""
    logger.error(f"HTTP异常: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "timestamp": time.time()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """通用异常处理器"""
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "服务器内部错误",
            "timestamp": time.time()
        }
    )

# 主函数
def run_api_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """运行API服务器"""
    import uvicorn
    
    logger.info(f"启动API服务器: http://{host}:{port}")
    logger.info(f"API文档地址: http://{host}:{port}/docs")
    
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    run_api_server()