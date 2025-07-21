# 系统二：AWS Bedrock企业级RAG系统
# Terraform输出定义

# 基础信息输出
output "account_id" {
  description = "AWS账户ID"
  value       = local.account_id
}

output "region" {
  description = "部署区域"
  value       = local.region
}

output "environment" {
  description = "部署环境"
  value       = var.environment
}

# S3存储桶信息
output "document_bucket_name" {
  description = "文档存储S3桶名称"
  value       = aws_s3_bucket.document_storage.bucket
}

output "document_bucket_arn" {
  description = "文档存储S3桶ARN"
  value       = aws_s3_bucket.document_storage.arn
}

output "document_bucket_domain_name" {
  description = "文档存储S3桶域名"
  value       = aws_s3_bucket.document_storage.bucket_domain_name
}

# API Gateway信息
output "api_gateway_id" {
  description = "API Gateway ID"
  value       = aws_api_gateway_rest_api.rag_api.id
}

output "api_gateway_url" {
  description = "API Gateway基础URL"
  value       = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
}

output "api_gateway_execution_arn" {
  description = "API Gateway执行ARN"
  value       = aws_api_gateway_rest_api.rag_api.execution_arn
}

# API端点
output "query_endpoint" {
  description = "查询API端点"
  value       = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/query"
}

output "upload_endpoint" {
  description = "文档上传API端点"
  value       = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/upload"
}

# Lambda函数信息
output "lambda_functions" {
  description = "Lambda函数信息"
  value = {
    query_handler = {
      function_name = aws_lambda_function.query_handler.function_name
      arn          = aws_lambda_function.query_handler.arn
      invoke_arn   = aws_lambda_function.query_handler.invoke_arn
    }
  }
}

# IAM角色信息
output "lambda_execution_role_arn" {
  description = "Lambda执行角色ARN"
  value       = aws_iam_role.lambda_execution_role.arn
}

output "lambda_execution_role_name" {
  description = "Lambda执行角色名称"
  value       = aws_iam_role.lambda_execution_role.name
}

# CloudWatch日志组
output "cloudwatch_log_groups" {
  description = "CloudWatch日志组信息"
  value = {
    for log_group_name, log_group in aws_cloudwatch_log_group.lambda_logs : log_group_name => {
      name = log_group.name
      arn  = log_group.arn
    }
  }
}

# 配置信息（用于应用程序）
output "environment_variables" {
  description = "应用程序环境变量"
  value = {
    ENVIRONMENT       = var.environment
    AWS_REGION       = var.aws_region
    S3_BUCKET        = aws_s3_bucket.document_storage.bucket
    BEDROCK_MODEL_ID = var.bedrock_model_id
    API_GATEWAY_URL  = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
  }
  sensitive = false
}

# 部署信息
output "deployment_info" {
  description = "部署信息摘要"
  value = {
    project_name     = var.project_name
    environment      = var.environment
    region          = var.aws_region
    deployment_time = timestamp()
    
    # 服务端点
    endpoints = {
      api_base_url = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
      query_api    = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/query"
      upload_api   = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/upload"
    }
    
    # 资源标识
    resources = {
      s3_bucket           = aws_s3_bucket.document_storage.bucket
      api_gateway_id      = aws_api_gateway_rest_api.rag_api.id
      lambda_function     = aws_lambda_function.query_handler.function_name
      execution_role      = aws_iam_role.lambda_execution_role.name
    }
  }
}

# 监控信息
output "monitoring_info" {
  description = "监控和日志信息"
  value = {
    cloudwatch_log_groups = [
      for log_group in aws_cloudwatch_log_group.lambda_logs : log_group.name
    ]
    
    # CloudWatch Dashboard URL（需要手动创建）
    cloudwatch_dashboard_url = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${var.project_name}-${var.environment}"
    
    # X-Ray追踪URL
    xray_traces_url = "https://${var.aws_region}.console.aws.amazon.com/xray/home?region=${var.aws_region}#/traces"
  }
}

# 安全信息
output "security_info" {
  description = "安全配置信息"
  value = {
    # IAM策略
    bedrock_access_policy_arn = aws_iam_policy.bedrock_access.arn
    s3_access_policy_arn     = aws_iam_policy.s3_access.arn
    
    # S3安全配置
    s3_encryption_enabled     = true
    s3_public_access_blocked  = true
    s3_versioning_enabled     = true
    
    # API Gateway安全
    api_authorization = "NONE"  # 注意：生产环境应启用认证
  }
}

# 成本估算信息
output "cost_estimation" {
  description = "成本估算信息"
  value = {
    estimated_monthly_cost_usd = "50-150"  # 基于使用量的估算
    
    cost_factors = {
      bedrock_model_invocations = "按调用次数和tokens计费"
      lambda_invocations       = "按请求数和执行时间计费"
      api_gateway_requests     = "按API调用次数计费"
      s3_storage              = "按存储容量计费"
      cloudwatch_logs         = "按日志存储和查询计费"
    }
    
    # 成本优化建议
    optimization_tips = [
      "合理配置Lambda内存以平衡性能和成本",
      "定期清理无用的日志和存储",
      "监控Bedrock模型使用量",
      "考虑使用Reserved Capacity降低成本"
    ]
  }
}

# 下一步操作指引
output "next_steps" {
  description = "部署后的下一步操作"
  value = {
    instructions = [
      "1. 配置Bedrock模型访问权限",
      "2. 上传测试文档到S3存储桶",
      "3. 创建Bedrock Knowledge Base",
      "4. 部署Lambda函数代码",
      "5. 测试API端点功能",
      "6. 配置监控和告警",
      "7. 设置CI/CD流程"
    ]
    
    # 有用的命令
    useful_commands = {
      test_api = "curl -X POST ${output.query_endpoint} -d '{\"question\":\"测试问题\"}'",
      view_logs = "aws logs tail /aws/lambda/${aws_lambda_function.query_handler.function_name} --follow",
      list_s3_files = "aws s3 ls s3://${aws_s3_bucket.document_storage.bucket}/"
    }
  }
}

# 开发者信息
output "developer_info" {
  description = "开发者相关信息"
  value = {
    # 本地开发环境变量文件内容
    env_file_content = <<-EOF
      AWS_REGION=${var.aws_region}
      ENVIRONMENT=${var.environment}
      S3_BUCKET=${aws_s3_bucket.document_storage.bucket}
      BEDROCK_MODEL_ID=${var.bedrock_model_id}
      API_GATEWAY_URL=https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}
    EOF
    
    # 测试脚本示例
    test_script_example = <<-EOF
      #!/bin/bash
      # 测试API端点
      API_URL="https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
      
      # 测试查询接口
      curl -X POST $API_URL/query \
        -H "Content-Type: application/json" \
        -d '{"question": "什么是RAG系统？", "top_k": 3}'
    EOF
  }
}