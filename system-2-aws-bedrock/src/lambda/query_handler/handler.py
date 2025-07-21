"""
AWS Lambda查询处理器
系统二：基于AWS Nova的企业级RAG知识问答系统
"""

import json
import logging
import os
import boto3
from typing import Dict, Any

# 配置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS客户端
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda函数主处理器
    
    Args:
        event: API Gateway事件
        context: Lambda上下文
        
    Returns:
        HTTP响应
    """
    try:
        logger.info(f"收到请求: {json.dumps(event, default=str)}")
        
        # 解析请求
        if 'body' in event and event['body']:
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return create_error_response(400, "无效的JSON格式")
        else:
            body = {}
        
        # 处理不同的HTTP方法
        http_method = event.get('httpMethod', 'GET')
        
        if http_method == 'POST':
            # 处理查询请求
            return handle_query_request(body)
        elif http_method == 'GET':
            # 处理健康检查
            return handle_health_check()
        else:
            return create_error_response(405, "不支持的HTTP方法")
    
    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)
        return create_error_response(500, "内部服务器错误")

def handle_query_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理查询请求
    
    Args:
        body: 请求体
        
    Returns:
        查询响应
    """
    try:
        # 提取查询参数
        question = body.get('question', '').strip()
        if not question:
            return create_error_response(400, "问题不能为空")
        
        top_k = body.get('top_k', 5)
        include_sources = body.get('include_sources', True)
        
        logger.info(f"处理查询: {question}")
        
        # 调用Bedrock进行查询
        response = query_bedrock_knowledge_base(question, top_k)
        
        # 格式化响应
        result = {
            "success": True,
            "question": question,
            "answer": response.get('answer', ''),
            "sources": response.get('sources', []) if include_sources else [],
            "metadata": {
                "top_k": top_k,
                "model_used": os.environ.get('BEDROCK_MODEL_ID', 'amazon.nova-pro-v1:0'),
                "processing_time": response.get('processing_time', 0)
            }
        }
        
        return create_success_response(result)
    
    except Exception as e:
        logger.error(f"查询处理失败: {str(e)}", exc_info=True)
        return create_error_response(500, f"查询处理失败: {str(e)}")

def query_bedrock_knowledge_base(question: str, top_k: int = 5) -> Dict[str, Any]:
    """
    查询Bedrock知识库
    
    Args:
        question: 用户问题
        top_k: 返回结果数量
        
    Returns:
        查询结果
    """
    try:
        import time
        start_time = time.time()
        
        # 注意：这是一个简化的示例实现
        # 实际实现需要配置Bedrock Knowledge Base
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'amazon.nova-pro-v1:0')
        
        # 构建提示词
        prompt = f"""基于以下上下文回答用户问题。如果无法找到相关信息，请说明无法回答。

用户问题: {question}

请提供准确、有用的回答："""
        
        # 调用Bedrock模型
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 1000,
                    "temperature": 0.1,
                    "topP": 0.9
                }
            })
        )
        
        # 解析响应
        response_body = json.loads(response['body'].read())
        
        processing_time = time.time() - start_time
        
        result = {
            "answer": response_body.get('results', [{}])[0].get('outputText', '抱歉，我无法回答您的问题。'),
            "sources": [],  # 需要实际的知识库检索来填充
            "processing_time": processing_time
        }
        
        logger.info(f"Bedrock查询完成，耗时: {processing_time:.2f}秒")
        return result
    
    except Exception as e:
        logger.error(f"Bedrock查询失败: {str(e)}")
        return {
            "answer": "抱歉，查询过程中发生错误，请稍后再试。",
            "sources": [],
            "processing_time": 0
        }

def handle_health_check() -> Dict[str, Any]:
    """
    处理健康检查请求
    
    Returns:
        健康检查响应
    """
    health_status = {
        "status": "healthy",
        "service": "RAG Query Handler",
        "version": "1.0.0",
        "timestamp": str(int(time.time())),
        "environment": os.environ.get('ENVIRONMENT', 'unknown'),
        "region": os.environ.get('AWS_REGION', 'us-east-1'),
        "checks": {
            "bedrock": check_bedrock_availability(),
            "s3": check_s3_availability()
        }
    }
    
    # 检查所有服务是否正常
    all_healthy = all(check["status"] == "ok" for check in health_status["checks"].values())
    if not all_healthy:
        health_status["status"] = "degraded"
    
    return create_success_response(health_status)

def check_bedrock_availability() -> Dict[str, Any]:
    """检查Bedrock服务可用性"""
    try:
        # 尝试列出模型来测试连接
        bedrock_client = boto3.client('bedrock', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        models = bedrock_client.list_foundation_models(maxResults=1)
        
        return {
            "status": "ok",
            "message": "Bedrock服务可用",
            "models_available": len(models.get('modelSummaries', []))
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Bedrock服务不可用: {str(e)}"
        }

def check_s3_availability() -> Dict[str, Any]:
    """检查S3服务可用性"""
    try:
        bucket_name = os.environ.get('S3_BUCKET')
        if not bucket_name:
            return {
                "status": "warning",
                "message": "S3存储桶未配置"
            }
        
        # 检查存储桶是否存在
        s3_client.head_bucket(Bucket=bucket_name)
        
        return {
            "status": "ok",
            "message": "S3服务可用",
            "bucket": bucket_name
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"S3服务不可用: {str(e)}"
        }

def create_success_response(data: Any, status_code: int = 200) -> Dict[str, Any]:
    """
    创建成功响应
    
    Args:
        data: 响应数据
        status_code: HTTP状态码
        
    Returns:
        API Gateway响应格式
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(data, ensure_ascii=False, default=str)
    }

def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    创建错误响应
    
    Args:
        status_code: HTTP状态码
        message: 错误消息
        
    Returns:
        API Gateway错误响应格式
    """
    error_response = {
        "success": False,
        "error": {
            "code": status_code,
            "message": message
        },
        "timestamp": str(int(time.time()))
    }
    
    return create_success_response(error_response, status_code)