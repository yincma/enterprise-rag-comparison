"""
AWS Lambda Authorizer
系统二：基于AWS Nova的企业级RAG知识问答系统

自定义认证和授权逻辑
"""

import json
import logging
import os
import re
import time
import jwt
import boto3
from typing import Dict, Any, List

# 配置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 全局变量
USER_POOL_ID = os.environ.get('USER_POOL_ID')
APP_CLIENT_ID = os.environ.get('APP_CLIENT_ID')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Cognito客户端
cognito_client = boto3.client('cognito-idp', region_name=REGION)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda Authorizer主处理器
    
    Args:
        event: API Gateway Authorizer事件
        context: Lambda上下文
        
    Returns:
        IAM策略响应
    """
    try:
        logger.info(f"Authorizer事件: {json.dumps(event, default=str)}")
        
        # 提取token
        token = extract_token(event)
        if not token:
            logger.warning("未找到Authorization token")
            raise Exception('Unauthorized')
        
        # 验证token
        user_info = verify_token(token)
        if not user_info:
            logger.warning("Token验证失败")
            raise Exception('Unauthorized')
        
        logger.info(f"用户认证成功: {user_info.get('sub', 'unknown')}")
        
        # 生成IAM策略
        policy = generate_policy(
            principal_id=user_info.get('sub', 'unknown'),
            effect='Allow',
            resource=event['methodArn'],
            context=user_info
        )
        
        return policy
    
    except Exception as e:
        logger.error(f"认证失败: {str(e)}")
        # 返回拒绝访问的策略
        return generate_policy(
            principal_id='unauthorized',
            effect='Deny',
            resource=event['methodArn']
        )

def extract_token(event: Dict[str, Any]) -> str:
    """
    从事件中提取token
    
    Args:
        event: API Gateway事件
        
    Returns:
        提取的token
    """
    auth_token = event.get('authorizationToken', '')
    
    # 支持Bearer token格式
    if auth_token.startswith('Bearer '):
        return auth_token.split(' ')[1]
    
    # 直接返回token
    return auth_token

def verify_token(token: str) -> Dict[str, Any]:
    """
    验证JWT token
    
    Args:
        token: JWT token
        
    Returns:
        用户信息字典
    """
    try:
        # 解码token但不验证签名（用于快速检查）
        unverified_header = jwt.get_unverified_header(token)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        
        # 基本验证
        if not unverified_payload.get('sub'):
            logger.error("Token缺少subject")
            return None
        
        # 检查token是否过期
        exp = unverified_payload.get('exp', 0)
        if exp < time.time():
            logger.error("Token已过期")
            return None
        
        # 检查issuer
        iss = unverified_payload.get('iss', '')
        expected_iss = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
        if iss != expected_iss:
            logger.error(f"无效的issuer: {iss}")
            return None
        
        # 检查audience (client_id)
        aud = unverified_payload.get('aud', '')
        if aud != APP_CLIENT_ID:
            # 也检查token_use，有时候aud在access token中不是client_id
            token_use = unverified_payload.get('token_use', '')
            if token_use == 'access':
                client_id = unverified_payload.get('client_id', '')
                if client_id != APP_CLIENT_ID:
                    logger.error(f"无效的client_id: {client_id}")
                    return None
            else:
                logger.error(f"无效的audience: {aud}")
                return None
        
        # 验证用户状态（可选）
        if USER_POOL_ID:
            try:
                user_response = cognito_client.admin_get_user(
                    UserPoolId=USER_POOL_ID,
                    Username=unverified_payload['sub']
                )
                
                user_status = user_response.get('UserStatus', '')
                if user_status != 'CONFIRMED':
                    logger.error(f"用户状态无效: {user_status}")
                    return None
                    
            except Exception as e:
                logger.warning(f"无法验证用户状态: {str(e)}")
        
        # 返回用户信息
        return {
            'sub': unverified_payload.get('sub'),
            'email': unverified_payload.get('email'),
            'username': unverified_payload.get('cognito:username', unverified_payload.get('username')),
            'groups': unverified_payload.get('cognito:groups', []),
            'token_use': unverified_payload.get('token_use'),
            'scope': unverified_payload.get('scope', ''),
            'exp': unverified_payload.get('exp'),
            'iat': unverified_payload.get('iat'),
        }
        
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT token无效: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Token验证错误: {str(e)}")
        return None

def generate_policy(principal_id: str, effect: str, resource: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    生成IAM策略
    
    Args:
        principal_id: 主体ID
        effect: Allow或Deny
        resource: 资源ARN
        context: 上下文信息
        
    Returns:
        IAM策略字典
    """
    # 构建基础策略
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': get_resource_arn(resource)
                }
            ]
        }
    }
    
    # 添加上下文信息
    if context and effect == 'Allow':
        policy['context'] = {
            'user_id': str(context.get('sub', '')),
            'email': str(context.get('email', '')),
            'username': str(context.get('username', '')),
            'groups': json.dumps(context.get('groups', [])),
            'token_use': str(context.get('token_use', '')),
            'scope': str(context.get('scope', '')),
        }
    
    return policy

def get_resource_arn(method_arn: str) -> str:
    """
    获取资源ARN，支持通配符
    
    Args:
        method_arn: 方法ARN
        
    Returns:
        资源ARN
    """
    # 解析ARN: arn:aws:execute-api:region:account:api-id/stage/method/resource
    arn_parts = method_arn.split(':')
    if len(arn_parts) >= 6:
        api_gateway_arn = ':'.join(arn_parts[:6])
        return f"{api_gateway_arn}/*/*"  # 允许访问所有方法和资源
    
    return method_arn