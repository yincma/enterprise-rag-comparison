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
    ENVIRONMENT            = var.environment
    AWS_REGION            = var.aws_region
    S3_BUCKET             = aws_s3_bucket.document_storage.bucket
    BEDROCK_MODEL_ID      = var.bedrock_model_id
    BEDROCK_EMBEDDING_MODEL_ID = var.bedrock_embedding_model_id
    KNOWLEDGE_BASE_ID     = aws_bedrockagent_knowledge_base.enterprise_kb.id
    DATA_SOURCE_ID        = aws_bedrockagent_data_source.s3_data_source.data_source_id
    API_GATEWAY_URL       = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
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
    # CloudWatch配置
    cloudwatch_log_groups = [
      for log_group in aws_cloudwatch_log_group.lambda_logs : log_group.name
    ]
    
    api_gateway_logs = aws_cloudwatch_log_group.api_gateway_logs.name
    
    # Dashboard
    dashboard_name = aws_cloudwatch_dashboard.main.dashboard_name
    dashboard_url = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
    
    # 告警配置
    alarms = {
      high_request_rate = aws_cloudwatch_metric_alarm.high_request_rate.alarm_name
      high_error_rate = aws_cloudwatch_metric_alarm.high_error_rate.alarm_name
      lambda_duration = aws_cloudwatch_metric_alarm.lambda_duration.alarm_name
      lambda_errors = aws_cloudwatch_metric_alarm.lambda_errors.alarm_name
      cost_alert = var.environment == "prod" ? aws_cloudwatch_metric_alarm.cost_alert[0].alarm_name : "disabled"
    }
    
    # 自定义指标
    custom_metrics = {
      bedrock_requests = "${var.project_name}/${var.environment}/BedrockRequests"
      bedrock_errors = "${var.project_name}/${var.environment}/BedrockErrors"
      cold_starts = "${var.project_name}/${var.environment}/ColdStarts"
    }
    
    # X-Ray配置
    xray_tracing_enabled = var.enable_xray_tracing
    xray_sampling_rule = aws_xray_sampling_rule.main.rule_name
    xray_traces_url = "https://${var.aws_region}.console.aws.amazon.com/xray/home?region=${var.aws_region}#/traces"
    
    # SNS告警主题
    alerts_topic_arn = aws_sns_topic.alerts.arn
  }
}

# 基础安全信息
output "basic_security_info" {
  description = "基础安全配置信息"
  value = {
    # IAM策略
    bedrock_access_policy_arn = aws_iam_policy.bedrock_access.arn
    s3_access_policy_arn     = aws_iam_policy.s3_access.arn
    
    # S3安全配置
    s3_encryption_enabled     = true
    s3_public_access_blocked  = true
    s3_versioning_enabled     = true
    
    # API Gateway认证
    api_authorization = "COGNITO_USER_POOLS"
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

# Bedrock Knowledge Base信息
output "knowledge_base_info" {
  description = "Bedrock Knowledge Base信息"
  value = {
    knowledge_base_id  = aws_bedrockagent_knowledge_base.enterprise_kb.id
    knowledge_base_arn = aws_bedrockagent_knowledge_base.enterprise_kb.arn
    data_source_id     = aws_bedrockagent_data_source.s3_data_source.data_source_id
    collection_arn     = aws_opensearchserverless_collection.knowledge_base_collection.arn
    collection_endpoint = aws_opensearchserverless_collection.knowledge_base_collection.collection_endpoint
  }
}

# OpenSearch Serverless信息
output "opensearch_info" {
  description = "OpenSearch Serverless集合信息"
  value = {
    collection_name = aws_opensearchserverless_collection.knowledge_base_collection.name
    collection_arn  = aws_opensearchserverless_collection.knowledge_base_collection.arn
    collection_endpoint = aws_opensearchserverless_collection.knowledge_base_collection.collection_endpoint
    dashboard_endpoint = aws_opensearchserverless_collection.knowledge_base_collection.dashboard_endpoint
  }
}

# VPC网络信息
output "vpc_info" {
  description = "VPC网络配置信息"
  value = {
    vpc_id = aws_vpc.main.id
    vpc_cidr = aws_vpc.main.cidr_block
    
    public_subnets = {
      for i, subnet in aws_subnet.public : "subnet-${i + 1}" => {
        id = subnet.id
        cidr = subnet.cidr_block
        az = subnet.availability_zone
      }
    }
    
    private_subnets = {
      for i, subnet in aws_subnet.private : "subnet-${i + 1}" => {
        id = subnet.id
        cidr = subnet.cidr_block
        az = subnet.availability_zone
      }
    }
    
    nat_gateways = {
      for i, nat in aws_nat_gateway.main : "nat-${i + 1}" => {
        id = nat.id
        public_ip = aws_eip.nat[i].public_ip
      }
    }
    
    vpc_endpoints = {
      s3 = aws_vpc_endpoint.s3.id
      bedrock = aws_vpc_endpoint.bedrock.id
      bedrock_runtime = aws_vpc_endpoint.bedrock_runtime.id
    }
  }
}

# 安全组信息
output "security_groups" {
  description = "安全组配置信息"
  value = {
    lambda_sg = {
      id = aws_security_group.lambda.id
      name = aws_security_group.lambda.name
    }
    api_gateway_sg = {
      id = aws_security_group.api_gateway.id
      name = aws_security_group.api_gateway.name
    }
    vpc_endpoints_sg = {
      id = aws_security_group.vpc_endpoints.id
      name = aws_security_group.vpc_endpoints.name
    }
  }
}

# 认证信息
output "authentication_info" {
  description = "Cognito认证配置信息"
  value = {
    user_pool_id = aws_cognito_user_pool.main.id
    user_pool_arn = aws_cognito_user_pool.main.arn
    user_pool_endpoint = aws_cognito_user_pool.main.endpoint
    user_pool_domain = aws_cognito_user_pool_domain.main.domain
    
    # 客户端信息
    api_client_id = aws_cognito_user_pool_client.api_client.id
    spa_client_id = aws_cognito_user_pool_client.spa_client.id
    
    # 认证URL
    hosted_ui_url = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
    
    # API Gateway Authorizer
    cognito_authorizer_id = aws_api_gateway_authorizer.cognito.id
    lambda_authorizer_id = aws_api_gateway_authorizer.lambda.id
  }
  sensitive = false
}

# WAF和安全信息
output "security_info" {
  description = "WAF和安全配置信息"
  value = {
    # WAF配置
    waf_enabled = var.enable_waf
    waf_web_acl_arn = var.enable_waf ? aws_wafv2_web_acl.main[0].arn : "disabled"
    waf_web_acl_id = var.enable_waf ? aws_wafv2_web_acl.main[0].id : "disabled"
    
    # IP白名单
    admin_whitelist_arn = var.enable_waf ? aws_wafv2_ip_set.admin_whitelist[0].arn : "disabled"
    
    # Shield保护
    shield_protection_enabled = var.environment == "prod"
    
    # 监控告警
    sns_alerts_topic_arn = aws_sns_topic.alerts.arn
    
    # API Gateway安全
    api_stage_arn = aws_api_gateway_stage.main.arn
    api_throttling = {
      rate_limit = var.api_throttle_rate_limit
      burst_limit = var.api_throttle_burst_limit
    }
    
    # 日志配置
    api_access_logs = aws_cloudwatch_log_group.api_gateway_logs.name
    xray_tracing_enabled = var.enable_xray_tracing
  }
}

# 下一步操作指引
output "next_steps" {
  description = "部署后的下一步操作"
  value = {
    instructions = [
      "1. 配置Bedrock模型访问权限",
      "2. 上传测试文档到S3存储桶: aws s3 cp document.pdf s3://${aws_s3_bucket.document_storage.bucket}/",
      "3. 同步Knowledge Base数据源: aws bedrock-agent start-ingestion-job --knowledge-base-id ${aws_bedrockagent_knowledge_base.enterprise_kb.id} --data-source-id ${aws_bedrockagent_data_source.s3_data_source.data_source_id}",
      "4. 部署Lambda函数代码",
      "5. 测试API端点功能",
      "6. 配置监控和告警",
      "7. 设置CI/CD流程"
    ]
    
    # 有用的命令
    useful_commands = {
      test_api = "curl -X POST ${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/query -H 'Content-Type: application/json' -d '{\"question\":\"测试问题\"}'",
      view_logs = "aws logs tail /aws/lambda/${aws_lambda_function.query_handler.function_name} --follow",
      list_s3_files = "aws s3 ls s3://${aws_s3_bucket.document_storage.bucket}/",
      sync_knowledge_base = "aws bedrock-agent start-ingestion-job --knowledge-base-id ${aws_bedrockagent_knowledge_base.enterprise_kb.id} --data-source-id ${aws_bedrockagent_data_source.s3_data_source.data_source_id}",
      check_kb_status = "aws bedrock-agent get-knowledge-base --knowledge-base-id ${aws_bedrockagent_knowledge_base.enterprise_kb.id}"
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