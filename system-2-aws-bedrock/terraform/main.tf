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

# IAM策略 - Bedrock访问策略
resource "aws_iam_policy" "bedrock_access" {
  name        = "${var.project_name}-bedrock-access-${var.environment}"
  description = "Policy for accessing AWS Bedrock services"
  
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
        Resource = "*"
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
  stage_name  = var.environment
  
  lifecycle {
    create_before_destroy = true
  }
}

# CloudWatch日志组 - Lambda函数日志
resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = toset(["query-handler", "document-processor", "chat-handler"])
  
  name              = "/aws/lambda/${var.project_name}-${each.key}-${var.environment}"
  retention_in_days = var.log_retention_days
  
  tags = local.common_tags
}

# Lambda函数 - 查询处理器（占位符）
resource "aws_lambda_function" "query_handler" {
  filename         = "../src/lambda/query_handler.zip"
  function_name    = "${var.project_name}-query-handler-${var.environment}"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 300
  memory_size     = 512
  
  environment {
    variables = {
      ENVIRONMENT        = var.environment
      S3_BUCKET         = aws_s3_bucket.document_storage.bucket
      BEDROCK_MODEL_ID  = var.bedrock_model_id
      REGION            = var.aws_region
    }
  }
  
  depends_on = [aws_cloudwatch_log_group.lambda_logs]
  
  tags = local.common_tags
}

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
  authorization = "NONE"
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
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "upload_integration" {
  rest_api_id = aws_api_gateway_rest_api.rag_api.id
  resource_id = aws_api_gateway_resource.upload.id
  http_method = aws_api_gateway_method.upload_post.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.query_handler.invoke_arn  # 暂时使用同一个函数
}