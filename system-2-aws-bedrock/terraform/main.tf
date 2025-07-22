# 系统二：AWS Bedrock企业级RAG系统
# Terraform基础设施配置

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # 远程状态存储（生产环境推荐）
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "rag-system/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# AWS Provider配置
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      System      = "RAG-Enterprise"
    }
  }
}

# 数据源
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# 本地变量
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# S3存储桶 - 文档存储
resource "aws_s3_bucket" "document_storage" {
  bucket = "${var.project_name}-documents-${var.environment}-${random_id.bucket_suffix.hex}"
  
  tags = merge(local.common_tags, {
    Name = "Document Storage"
    Type = "Storage"
  })
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# S3存储桶配置
resource "aws_s3_bucket_versioning" "document_storage" {
  bucket = aws_s3_bucket.document_storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "document_storage" {
  bucket = aws_s3_bucket.document_storage.id
  
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}

resource "aws_s3_bucket_public_access_block" "document_storage" {
  bucket = aws_s3_bucket.document_storage.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# IAM角色 - Lambda执行角色
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-lambda-execution-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# IAM策略 - Lambda基础执行策略
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# IAM策略 - Lambda VPC执行策略
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# IAM策略 - Lambda Bedrock访问策略
resource "aws_iam_policy" "bedrock_access" {
  name        = "${var.project_name}-lambda-bedrock-access-${var.environment}"
  description = "Policy for Lambda to access AWS Bedrock services"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:RetrieveAndGenerate",
          "bedrock:Retrieve"
        ]
        Resource = [
          aws_bedrockagent_knowledge_base.enterprise_kb.arn,
          "${aws_bedrockagent_knowledge_base.enterprise_kb.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock-agent:RetrieveAndGenerate",
          "bedrock-agent:Retrieve"
        ]
        Resource = [
          aws_bedrockagent_knowledge_base.enterprise_kb.arn,
          "${aws_bedrockagent_knowledge_base.enterprise_kb.arn}/*"
        ]
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_bedrock_access" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.bedrock_access.arn
}

# IAM策略 - S3访问策略
resource "aws_iam_policy" "s3_access" {
  name        = "${var.project_name}-s3-access-${var.environment}"
  description = "Policy for accessing S3 document storage"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.document_storage.arn,
          "${aws_s3_bucket.document_storage.arn}/*"
        ]
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_s3_access" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.s3_access.arn
}

# API Gateway
resource "aws_api_gateway_rest_api" "rag_api" {
  name        = "${var.project_name}-api-${var.environment}"
  description = "RAG System API Gateway"
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }
  
  tags = local.common_tags
}

# API Gateway部署
resource "aws_api_gateway_deployment" "rag_api" {
  depends_on = [
    aws_api_gateway_integration.query_integration,
    aws_api_gateway_integration.upload_integration
  ]
  
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  
  lifecycle {
    create_before_destroy = true
  }
  
  # 当API配置发生变化时强制重新部署
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.query.id,
      aws_api_gateway_method.query_post.id,
      aws_api_gateway_integration.query_integration.id,
      aws_api_gateway_resource.upload.id,
      aws_api_gateway_method.upload_post.id,
      aws_api_gateway_integration.upload_integration.id,
    ]))
  }
}

# CloudWatch日志组 - Lambda函数日志
resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = toset(["query-handler", "document-processor", "chat-handler"])
  
  name              = "/aws/lambda/${var.project_name}-${each.key}-${var.environment}"
  retention_in_days = var.log_retention_days
  
  tags = local.common_tags
}

# Lambda函数定义已移至 lambda.tf 文件

# API Gateway资源和方法（示例）
resource "aws_api_gateway_resource" "query" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  parent_id   = aws_api_gateway_rest_api.rag_api.root_resource_id
  path_part   = "query"
}

resource "aws_api_gateway_method" "query_post" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.query.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
  
  request_parameters = {
    "method.request.header.Authorization" = true
  }
}

resource "aws_api_gateway_integration" "query_integration" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_post.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.query_handler.invoke_arn
}

# Lambda权限 - API Gateway调用
resource "aws_lambda_permission" "api_gateway_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rag_api.execution_arn}/*/*"
}

# 文档上传API资源
resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  parent_id   = aws_api_gateway_rest_api.rag_api.root_resource_id
  path_part   = "upload"
}

resource "aws_api_gateway_method" "upload_post" {
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  resource_id   = aws_api_gateway_resource.upload.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
  
  request_parameters = {
    "method.request.header.Authorization" = true
  }
}

resource "aws_api_gateway_integration" "upload_integration" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.upload.id
  http_method = aws_api_gateway_method.upload_post.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.query_handler.invoke_arn  # 暂时使用同一个函数
}

# ================================
# VPC 网络配置
# ================================

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpc-${var.environment}"
    Type = "Network"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-igw-${var.environment}"
    Type = "Network"
  })
}

# 公有子网
resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs)
  
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-public-subnet-${count.index + 1}-${var.environment}"
    Type = "Public Subnet"
  })
}

# 私有子网
resource "aws_subnet" "private" {
  count = length(var.private_subnet_cidrs)
  
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-private-subnet-${count.index + 1}-${var.environment}"
    Type = "Private Subnet"
  })
}

# Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
  count = length(var.public_subnet_cidrs)
  
  domain = "vpc"
  
  depends_on = [aws_internet_gateway.main]
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-nat-eip-${count.index + 1}-${var.environment}"
    Type = "Network"
  })
}

# NAT Gateways
resource "aws_nat_gateway" "main" {
  count = length(var.public_subnet_cidrs)
  
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  
  depends_on = [aws_internet_gateway.main]
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-nat-${count.index + 1}-${var.environment}"
    Type = "Network"
  })
}

# 公有路由表
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-public-rt-${var.environment}"
    Type = "Route Table"
  })
}

# 私有路由表
resource "aws_route_table" "private" {
  count = length(var.private_subnet_cidrs)
  
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-private-rt-${count.index + 1}-${var.environment}"
    Type = "Route Table"
  })
}

# 公有子网路由表关联
resource "aws_route_table_association" "public" {
  count = length(var.public_subnet_cidrs)
  
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# 私有子网路由表关联
resource "aws_route_table_association" "private" {
  count = length(var.private_subnet_cidrs)
  
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# ================================
# 安全组配置
# ================================

# Lambda安全组
resource "aws_security_group" "lambda" {
  name_prefix = "${var.project_name}-lambda-${var.environment}"
  vpc_id      = aws_vpc.main.id
  description = "Security group for Lambda functions"
  
  # 出站规则 - 允许所有出站流量
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-lambda-sg-${var.environment}"
    Type = "Security Group"
  })
}

# API Gateway安全组（如果需要私有API）
resource "aws_security_group" "api_gateway" {
  name_prefix = "${var.project_name}-api-${var.environment}"
  vpc_id      = aws_vpc.main.id
  description = "Security group for API Gateway"
  
  # 入站规则 - HTTPS流量
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS traffic"
  }
  
  # 入站规则 - HTTP流量（开发环境）
  dynamic "ingress" {
    for_each = var.environment == "dev" ? [1] : []
    content {
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
      description = "HTTP traffic (dev only)"
    }
  }
  
  # 出站规则
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-api-sg-${var.environment}"
    Type = "Security Group"
  })
}

# VPC端点安全组
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.project_name}-vpc-endpoints-${var.environment}"
  vpc_id      = aws_vpc.main.id
  description = "Security group for VPC endpoints"
  
  # 入站规则 - HTTPS流量
  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
    description     = "HTTPS from Lambda"
  }
  
  # 出站规则
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpc-endpoints-sg-${var.environment}"
    Type = "Security Group"
  })
}

# ================================
# VPC端点配置（可选 - 用于私有连接AWS服务）
# ================================

# S3 VPC端点（Gateway端点）
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.aws_region}.s3"
  
  route_table_ids = concat(
    [aws_route_table.public.id],
    aws_route_table.private[*].id
  )
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-s3-endpoint-${var.environment}"
    Type = "VPC Endpoint"
  })
}

# Bedrock VPC端点（Interface端点）
resource "aws_vpc_endpoint" "bedrock" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-bedrock-endpoint-${var.environment}"
    Type = "VPC Endpoint"
  })
}

# Bedrock Runtime VPC端点
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-bedrock-runtime-endpoint-${var.environment}"
    Type = "VPC Endpoint"
  })
}

# ================================
# 认证配置 (Cognito)
# ================================

# Cognito User Pool
resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-user-pool-${var.environment}"
  
  # 用户名配置
  username_configuration {
    case_sensitive = false
  }
  
  # 密码策略
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }
  
  # 账户恢复设置
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  
  # 用户属性
  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }
  
  schema {
    name                = "name"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }
  
  # 验证配置
  auto_verified_attributes = ["email"]
  
  # 邮件配置
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }
  
  # MFA配置
  mfa_configuration = "OPTIONAL"
  
  software_token_mfa_configuration {
    enabled = true
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-user-pool-${var.environment}"
    Type = "Authentication"
  })
}

# Cognito User Pool Domain
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-auth-${var.environment}-${random_id.bucket_suffix.hex}"
  user_pool_id = aws_cognito_user_pool.main.id
}

# Cognito User Pool Client
resource "aws_cognito_user_pool_client" "api_client" {
  name         = "${var.project_name}-api-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
  
  generate_secret = true
  
  # OAuth配置
  allowed_oauth_flows  = ["code", "implicit"]
  allowed_oauth_scopes = ["openid", "profile", "email"]
  
  allowed_oauth_flows_user_pool_client = true
  
  # 支持的身份提供商
  supported_identity_providers = ["COGNITO"]
  
  # 回调和登出URL
  callback_urls = [
    "https://localhost:3000/callback",
    "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/callback"
  ]
  
  logout_urls = [
    "https://localhost:3000/logout"
  ]
  
  # Token有效期
  access_token_validity  = 60    # 60分钟
  id_token_validity      = 60    # 60分钟
  refresh_token_validity = 30    # 30天
  
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  
  # 防止用户存在枚举
  prevent_user_existence_errors = "ENABLED"
}

# Cognito User Pool Client (用于移动端/SPA)
resource "aws_cognito_user_pool_client" "spa_client" {
  name         = "${var.project_name}-spa-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
  
  generate_secret = false  # 公共客户端不使用秘钥
  
  # OAuth配置
  allowed_oauth_flows  = ["code", "implicit"]
  allowed_oauth_scopes = ["openid", "profile", "email"]
  
  allowed_oauth_flows_user_pool_client = true
  
  # 支持的身份提供商
  supported_identity_providers = ["COGNITO"]
  
  # 回调和登出URL
  callback_urls = [
    "https://localhost:3000/callback",
    "http://localhost:3000/callback"
  ]
  
  logout_urls = [
    "https://localhost:3000/logout",
    "http://localhost:3000/logout"
  ]
  
  # Token有效期
  access_token_validity  = 60    # 60分钟
  id_token_validity      = 60    # 60分钟
  refresh_token_validity = 30    # 30天
  
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  
  # 防止用户存在枚举
  prevent_user_existence_errors = "ENABLED"
}

# ================================
# API Gateway 认证配置
# ================================

# API Gateway Cognito Authorizer
resource "aws_api_gateway_authorizer" "cognito" {
  name          = "${var.project_name}-cognito-authorizer-${var.environment}"
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  type          = "COGNITO_USER_POOLS"
  
  provider_arns = [aws_cognito_user_pool.main.arn]
  
  identity_source = "method.request.header.Authorization"
}

# Lambda Authorizer函数定义已移至 lambda.tf 文件

# API Gateway Lambda Authorizer
resource "aws_api_gateway_authorizer" "lambda" {
  name                   = "${var.project_name}-lambda-authorizer-${var.environment}"
  rest_api_id           = aws_api_gateway_rest_api.rag_api.id
  type                  = "TOKEN"
  
  authorizer_uri        = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials = aws_iam_role.api_gateway_invocation_role.arn
  
  identity_source       = "method.request.header.Authorization"
  authorizer_result_ttl_in_seconds = 300
}

# IAM角色 - API Gateway调用Lambda Authorizer
resource "aws_iam_role" "api_gateway_invocation_role" {
  name = "${var.project_name}-api-gateway-invocation-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# IAM策略 - API Gateway调用Lambda
resource "aws_iam_role_policy" "invocation_policy" {
  name = "${var.project_name}-invocation-policy-${var.environment}"
  role = aws_iam_role.api_gateway_invocation_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = "lambda:InvokeFunction"
        Effect   = "Allow"
        Resource = aws_lambda_function.authorizer.arn
      }
    ]
  })
}

# Lambda权限 - API Gateway调用Authorizer
resource "aws_lambda_permission" "api_gateway_authorizer" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rag_api.execution_arn}/authorizers/*"
}

# ================================
# AWS WAF 安全配置
# ================================

# WAF Web ACL
resource "aws_wafv2_web_acl" "main" {
  count = var.enable_waf ? 1 : 0
  
  name  = "${var.project_name}-waf-${var.environment}"
  scope = "REGIONAL"
  
  default_action {
    allow {}
  }
  
  # 规则1: AWS托管规则 - 常见攻击防护
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 1
    
    override_action {
      none {}
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "CommonRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }
  
  # 规则2: 已知恶意输入
  rule {
    name     = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2
    
    override_action {
      none {}
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "KnownBadInputsRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }
  
  # 规则3: Linux操作系统攻击防护
  rule {
    name     = "AWS-AWSManagedRulesLinuxRuleSet"
    priority = 3
    
    override_action {
      none {}
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesLinuxRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "LinuxRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }
  
  # 规则4: SQL注入攻击防护
  rule {
    name     = "AWS-AWSManagedRulesSQLiRuleSet"
    priority = 4
    
    override_action {
      none {}
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "SQLiRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }
  
  # 规则5: 频率限制（防DDoS）
  rule {
    name     = "RateLimitRule"
    priority = 5
    
    action {
      block {}
    }
    
    statement {
      rate_based_statement {
        limit              = 2000  # 每5分钟2000个请求
        aggregate_key_type = "IP"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "RateLimitRule"
      sampled_requests_enabled    = true
    }
  }
  
  # 规则6: 地理位置阻止（可选）
  dynamic "rule" {
    for_each = var.environment == "prod" ? [1] : []
    content {
      name     = "GeoBlockRule"
      priority = 6
      
      action {
        block {}
      }
      
      statement {
        geo_match_statement {
          # 阻止来自高风险国家的请求
          country_codes = ["CN", "RU", "KP", "IR"]
        }
      }
      
      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                 = "GeoBlockRule"
        sampled_requests_enabled    = true
      }
    }
  }
  
  # 规则7: IP白名单（管理员访问）
  rule {
    name     = "AdminWhitelistRule"
    priority = 0  # 最高优先级
    
    action {
      allow {}
    }
    
    statement {
      ip_set_reference_statement {
        arn = aws_wafv2_ip_set.admin_whitelist[0].arn
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "AdminWhitelistRule"
      sampled_requests_enabled    = true
    }
  }
  
  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                 = "${var.project_name}-waf-${var.environment}"
    sampled_requests_enabled    = true
  }
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-waf-${var.environment}"
    Type = "Security"
  })
}

# IP白名单集合
resource "aws_wafv2_ip_set" "admin_whitelist" {
  count = var.enable_waf ? 1 : 0
  
  name               = "${var.project_name}-admin-whitelist-${var.environment}"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"
  
  # 默认包含本地开发IP（需要根据实际情况修改）
  addresses = [
    "127.0.0.1/32",  # 本地回环
    "10.0.0.0/8",    # 私有网络
    "172.16.0.0/12", # 私有网络
    "192.168.0.0/16" # 私有网络
  ]
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-admin-whitelist-${var.environment}"
    Type = "Security"
  })
}

# 将WAF与API Gateway关联
resource "aws_wafv2_web_acl_association" "api_gateway" {
  count = var.enable_waf ? 1 : 0
  
  resource_arn = aws_api_gateway_stage.main.arn
  web_acl_arn  = aws_wafv2_web_acl.main[0].arn
}

# API Gateway Stage（用于WAF关联）
resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.rag_api.id
  rest_api_id   = aws_api_gateway_rest_api.rag_api.id
  stage_name    = var.environment
  
  # 访问日志配置
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$requestId"
      ip            = "$sourceIp"
      requestTime   = "$requestTime"
      httpMethod    = "$httpMethod"
      resourcePath  = "$resourcePath"
      status        = "$status"
      error         = "$error.message"
      responseLength = "$responseLength"
      userAgent     = "$userAgent"
    })
  }
  
  # 详细监控
  xray_tracing_enabled = var.enable_xray_tracing
  
  # 节流配置
  throttle_settings {
    rate_limit  = var.api_throttle_rate_limit
    burst_limit = var.api_throttle_burst_limit
  }
  
  tags = local.common_tags
}

# CloudWatch日志组 - API Gateway访问日志
resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
  
  tags = local.common_tags
}

# ================================
# DDoS 防护配置
# ================================

# Shield Advanced订阅（可选 - 企业级保护）
resource "aws_shield_protection" "api_gateway" {
  count        = var.environment == "prod" ? 1 : 0
  name         = "${var.project_name}-api-gateway-shield-${var.environment}"
  resource_arn = aws_api_gateway_stage.main.arn
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-shield-protection-${var.environment}"
    Type = "Security"
  })
}

# CloudWatch警报 - 高请求率
resource "aws_cloudwatch_metric_alarm" "high_request_rate" {
  alarm_name          = "${var.project_name}-high-request-rate-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Count"
  namespace           = "AWS/ApiGateway"
  period              = "300"  # 5分钟
  statistic           = "Sum"
  threshold           = "10000"  # 5分钟内超过10000个请求
  alarm_description   = "API Gateway请求率过高，可能遭受DDoS攻击"
  
  dimensions = {
    ApiName = aws_api_gateway_rest_api.rag_api.name
    Stage   = var.environment
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = local.common_tags
}

# CloudWatch警报 - 高错误率
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.project_name}-high-error-rate-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "100"  # 5分钟内超过100个4XX错误
  alarm_description   = "API Gateway 4XX错误率过高"
  
  dimensions = {
    ApiName = aws_api_gateway_rest_api.rag_api.name
    Stage   = var.environment
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = local.common_tags
}

# SNS主题 - 安全告警
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-security-alerts-${var.environment}"
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-alerts-${var.environment}"
    Type = "Monitoring"
  })
}

# ================================
# 增强监控配置
# ================================

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-dashboard-${var.environment}"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiName", aws_api_gateway_rest_api.rag_api.name, "Stage", var.environment],
            [".", "Latency", ".", ".", ".", "."],
            [".", "4XXError", ".", ".", ".", "."],
            [".", "5XXError", ".", ".", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "API Gateway Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        
        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.query_handler.function_name],
            [".", "Errors", ".", "."],
            [".", "Invocations", ".", "."],
            [".", "Throttles", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        
        properties = {
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", aws_s3_bucket.document_storage.bucket, "StorageType", "StandardStorage"],
            [".", "NumberOfObjects", ".", ".", ".", "AllStorageTypes"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "S3 Storage Metrics"
          period  = 86400
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 18
        width  = 24
        height = 6
        
        properties = {
          query   = "SOURCE '/aws/lambda/${aws_lambda_function.query_handler.function_name}' | fields @timestamp, @message | sort @timestamp desc | limit 100"
          region  = var.aws_region
          title   = "Recent Lambda Logs"
          view    = "table"
        }
      }
    ]
  })
}

# 额外的CloudWatch警报
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.project_name}-lambda-duration-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "30000"  # 30秒
  alarm_description   = "Lambda函数执行时间过长"
  
  dimensions = {
    FunctionName = aws_lambda_function.query_handler.function_name
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Lambda函数错误率过高"
  
  dimensions = {
    FunctionName = aws_lambda_function.query_handler.function_name
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = local.common_tags
}

# X-Ray Tracing 配置
resource "aws_xray_sampling_rule" "main" {
  rule_name      = "${var.project_name}-sampling-rule-${var.environment}"
  priority       = 9000
  version        = 1
  reservoir_size = 1
  fixed_rate     = 0.1
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"
  
  tags = local.common_tags
}

# Custom Metrics for Bedrock Usage
resource "aws_cloudwatch_log_metric_filter" "bedrock_requests" {
  name           = "${var.project_name}-bedrock-requests-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.lambda_logs["query-handler"].name
  pattern        = "[timestamp, requestId, level=\"INFO\", message=\"Knowledge Base查询完成*\"]"
  
  metric_transformation {
    name      = "BedrockRequests"
    namespace = "${var.project_name}/${var.environment}"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "bedrock_errors" {
  name           = "${var.project_name}-bedrock-errors-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.lambda_logs["query-handler"].name
  pattern        = "[timestamp, requestId, level=\"ERROR\", message=\"Knowledge Base查询失败*\"]"
  
  metric_transformation {
    name      = "BedrockErrors"
    namespace = "${var.project_name}/${var.environment}"
    value     = "1"
  }
}

# Cost Monitoring Alert
resource "aws_cloudwatch_metric_alarm" "cost_alert" {
  count = var.environment == "prod" ? 1 : 0
  
  alarm_name          = "${var.project_name}-cost-alert-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"  # 24小时
  statistic           = "Maximum"
  threshold           = "500"  # $500 USD
  alarm_description   = "AWS月度费用超过阈值"
  treat_missing_data  = "breaching"
  
  dimensions = {
    Currency = "USD"
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = local.common_tags
}

# Performance Insights for Lambda Cold Starts
resource "aws_cloudwatch_log_metric_filter" "lambda_cold_starts" {
  name           = "${var.project_name}-lambda-cold-starts-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.lambda_logs["query-handler"].name
  pattern        = "[timestamp, requestId, level, message=\"INIT_START*\"]"
  
  metric_transformation {
    name      = "ColdStarts"
    namespace = "${var.project_name}/${var.environment}"
    value     = "1"
  }
}

# ================================
# Bedrock Knowledge Base 配置
# ================================

# OpenSearch Serverless 集合（向量数据库）
resource "aws_opensearchserverless_collection" "knowledge_base_collection" {
  name = "${var.project_name}-vectors-${var.environment}"
  type = "VECTORSEARCH"
  
  tags = merge(local.common_tags, {
    Name = "Knowledge Base Vector Collection"
    Type = "VectorDB"
  })
}

# OpenSearch Serverless 网络策略
resource "aws_opensearchserverless_security_policy" "network_policy" {
  name = "${var.project_name}-network-policy-${var.environment}"
  type = "network"
  
  policy = jsonencode([
    {
      Description = "Network policy for ${var.project_name} knowledge base"
      Rules = [
        {
          ResourceType = "collection"
          Resource = ["collection/${aws_opensearchserverless_collection.knowledge_base_collection.name}"]
        }
      ]
      AllowFromPublic = true
    }
  ])
}

# OpenSearch Serverless 加密策略
resource "aws_opensearchserverless_security_policy" "encryption_policy" {
  name = "${var.project_name}-encryption-policy-${var.environment}"
  type = "encryption"
  
  policy = jsonencode({
    Description = "Encryption policy for ${var.project_name} knowledge base"
    Rules = [
      {
        ResourceType = "collection"
        Resource = ["collection/${aws_opensearchserverless_collection.knowledge_base_collection.name}"]
      }
    ]
    AWSOwnedKey = true
  })
}

# OpenSearch Serverless 数据访问策略
resource "aws_opensearchserverless_access_policy" "data_access_policy" {
  name = "${var.project_name}-data-access-policy-${var.environment}"
  type = "data"
  
  policy = jsonencode([
    {
      Description = "Data access policy for ${var.project_name} knowledge base"
      Rules = [
        {
          ResourceType = "collection"
          Resource = ["collection/${aws_opensearchserverless_collection.knowledge_base_collection.name}"]
          Permission = [
            "aoss:CreateCollectionItems",
            "aoss:UpdateCollectionItems",
            "aoss:DescribeCollectionItems"
          ]
        },
        {
          ResourceType = "index"
          Resource = ["index/${aws_opensearchserverless_collection.knowledge_base_collection.name}/*"]
          Permission = [
            "aoss:CreateIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument",
            "aoss:UpdateIndex",
            "aoss:DeleteIndex"
          ]
        }
      ]
      Principal = [aws_iam_role.bedrock_execution_role.arn]
    }
  ])
}

# Bedrock 服务执行角色
resource "aws_iam_role" "bedrock_execution_role" {
  name = "${var.project_name}-bedrock-execution-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# Bedrock Knowledge Base 访问 OpenSearch 策略
resource "aws_iam_policy" "bedrock_opensearch_policy" {
  name        = "${var.project_name}-bedrock-opensearch-${var.environment}"
  description = "Policy for Bedrock to access OpenSearch Serverless"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "aoss:APIAccessAll"
        ]
        Resource = aws_opensearchserverless_collection.knowledge_base_collection.arn
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "bedrock_opensearch_policy" {
  role       = aws_iam_role.bedrock_execution_role.name
  policy_arn = aws_iam_policy.bedrock_opensearch_policy.arn
}

# Bedrock Knowledge Base 访问 S3 策略
resource "aws_iam_policy" "bedrock_s3_policy" {
  name        = "${var.project_name}-bedrock-s3-${var.environment}"
  description = "Policy for Bedrock to access S3 documents"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.document_storage.arn,
          "${aws_s3_bucket.document_storage.arn}/*"
        ]
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "bedrock_s3_policy" {
  role       = aws_iam_role.bedrock_execution_role.name
  policy_arn = aws_iam_policy.bedrock_s3_policy.arn
}

# Bedrock Knowledge Base
resource "aws_bedrockagent_knowledge_base" "enterprise_kb" {
  name     = var.bedrock_knowledge_base_name
  role_arn = aws_iam_role.bedrock_execution_role.arn
  
  knowledge_base_configuration {
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_embedding_model_id}"
    }
    type = "VECTOR"
  }
  
  storage_configuration {
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.knowledge_base_collection.arn
      vector_index_name = "bedrock-knowledge-base-default-index"
      field_mapping {
        vector_field   = "bedrock-knowledge-base-default-vector"
        text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
        metadata_field = "AMAZON_BEDROCK_METADATA"
      }
    }
    type = "OPENSEARCH_SERVERLESS"
  }
  
  tags = merge(local.common_tags, {
    Name = "Enterprise Knowledge Base"
    Type = "KnowledgeBase"
  })
  
  depends_on = [
    aws_opensearchserverless_collection.knowledge_base_collection,
    aws_opensearchserverless_access_policy.data_access_policy
  ]
}

# Bedrock Data Source（连接S3存储桶）
resource "aws_bedrockagent_data_source" "s3_data_source" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.enterprise_kb.id
  name             = "${var.project_name}-s3-datasource-${var.environment}"
  
  data_source_configuration {
    s3_configuration {
      bucket_arn = aws_s3_bucket.document_storage.arn
    }
    type = "S3"
  }
  
  tags = merge(local.common_tags, {
    Name = "S3 Data Source"
    Type = "DataSource"
  })
}