"""
AWS Lambda查询处理器
系统二：基于AWS Nova的企业级RAG知识问答系统
"""

import json
import logging
import os
import time
import boto3
from typing import Dict, Any, List

# 配置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS客户端
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
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
        start_time = time.time()
        
        knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'amazon.nova-pro-v1:0')
        
        if not knowledge_base_id:
            logger.error("Knowledge Base ID未配置")
            return _create_fallback_response(question, start_time)
        
        logger.info(f"查询Knowledge Base: {knowledge_base_id}, 问题: {question}")
        
        # 使用Bedrock Knowledge Base进行检索增强生成
        response = bedrock_agent_runtime.retrieve_and_generate(
            input={
                'text': question
            },
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': knowledge_base_id,
                    'modelArn': f'arn:aws:bedrock:{os.environ.get("AWS_REGION", "us-east-1")}::foundation-model/{model_id}',
                    'retrievalConfiguration': {
                        'vectorSearchConfiguration': {
                            'numberOfResults': top_k
                        }
                    }
                }
            }
        )
        
        processing_time = time.time() - start_time
        
        # 提取生成的答案
        output = response.get('output', {})
        answer = output.get('text', '抱歉，我无法找到相关信息来回答您的问题。')
        
        # 提取来源信息
        sources = []
        citations = response.get('citations', [])
        
        for citation in citations:
            retrieved_references = citation.get('retrievedReferences', [])
            for ref in retrieved_references:
                content = ref.get('content', {})
                location = ref.get('location', {})
                
                source_info = {
                    'content': content.get('text', ''),
                    'document': location.get('s3Location', {}).get('uri', '未知文档'),
                    'confidence': ref.get('metadata', {}).get('score', 0.0)
                }
                sources.append(source_info)
        
        result = {
            "answer": answer,
            "sources": sources,
            "processing_time": processing_time,
            "citations_count": len(citations),
            "model_used": model_id
        }
        
        logger.info(f"Knowledge Base查询完成，耗时: {processing_time:.2f}秒，来源数量: {len(sources)}")
        return result
    
    except Exception as e:
        logger.error(f"Knowledge Base查询失败: {str(e)}", exc_info=True)
        return _create_fallback_response(question, start_time, str(e))

def _create_fallback_response(question: str, start_time: float, error_msg: str = None) -> Dict[str, Any]:
    """
    创建备用响应（当Knowledge Base不可用时）
    """
    try:
        logger.info("使用备用模式：直接调用Bedrock模型")
        
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'amazon.nova-pro-v1:0')
        
        # 构建提示词
        prompt = f"""请基于你的知识回答以下问题。如果你不确定答案，请诚实地说明。

问题: {question}

请提供准确、有用的回答："""
        
        # 调用Bedrock模型
        if 'nova' in model_id.lower():
            # Nova模型格式
            body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 1000,
                    "temperature": 0.1,
                    "topP": 0.9
                }
            }
        else:
            # 其他模型格式
            body = {
                "prompt": prompt,
                "max_tokens": 1000,
                "temperature": 0.1,
                "top_p": 0.9
            }
        
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        
        # 解析响应（根据模型类型）
        if 'nova' in model_id.lower():
            answer = response_body.get('results', [{}])[0].get('outputText', '抱歉，我无法回答您的问题。')
        else:
            answer = response_body.get('completion', '抱歉，我无法回答您的问题。')
        
        processing_time = time.time() - start_time
        
        return {
            "answer": f"{answer}\n\n⚠️ 注意：此回答基于模型的一般知识，未使用企业知识库。" + (f" 错误信息: {error_msg}" if error_msg else ""),
            "sources": [],
            "processing_time": processing_time,
            "citations_count": 0,
            "model_used": model_id,
            "fallback_mode": True
        }
    
    except Exception as fallback_error:
        logger.error(f"备用模式也失败了: {str(fallback_error)}")
        return {
            "answer": "抱歉，服务暂时不可用，请稍后再试。",
            "sources": [],
            "processing_time": time.time() - start_time,
            "citations_count": 0,
            "error": True
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
        "version": "2.0.0",
        "timestamp": str(int(time.time())),
        "environment": os.environ.get('ENVIRONMENT', 'unknown'),
        "region": os.environ.get('AWS_REGION', 'us-east-1'),
        "knowledge_base_id": os.environ.get('KNOWLEDGE_BASE_ID', 'not_configured'),
        "checks": {
            "bedrock": check_bedrock_availability(),
            "knowledge_base": check_knowledge_base_availability(),
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

def check_knowledge_base_availability() -> Dict[str, Any]:
    """检查Knowledge Base可用性"""
    try:
        knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
        if not knowledge_base_id:
            return {
                "status": "warning",
                "message": "Knowledge Base ID未配置"
            }
        
        # 尝试获取Knowledge Base信息
        bedrock_agent = boto3.client('bedrock-agent', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        kb_info = bedrock_agent.get_knowledge_base(knowledgeBaseId=knowledge_base_id)
        
        status = kb_info.get('knowledgeBase', {}).get('status', 'UNKNOWN')
        
        return {
            "status": "ok" if status == "ACTIVE" else "warning",
            "message": f"Knowledge Base状态: {status}",
            "knowledge_base_id": knowledge_base_id,
            "kb_status": status
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Knowledge Base不可用: {str(e)}"
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