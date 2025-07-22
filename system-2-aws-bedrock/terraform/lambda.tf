# ================================
# Lambda 函数自动化部署配置
# ================================

# Lambda构建脚本
resource "null_resource" "lambda_build" {
  # 触发条件：当Lambda源代码发生变化时重新构建
  triggers = {
    lambda_source_hash = data.archive_file.lambda_zip.output_md5
    requirements_hash  = filemd5("${path.module}/../requirements.txt")
    build_script_hash  = filemd5("${path.module}/../src/scripts/build-lambda.sh")
  }

  # 构建过程
  provisioner "local-exec" {
    command = "${path.module}/../src/scripts/build-lambda.sh"
    working_dir = path.module
  }

  # 清理过程
  provisioner "local-exec" {
    when    = destroy
    command = "rm -rf ${path.module}/../.build"
    working_dir = path.module
  }
}

# Query Handler Lambda ZIP包
data "archive_file" "query_handler_zip" {
  type        = "zip"
  output_path = "${path.module}/../.build/query_handler.zip"
  
  # Lambda函数代码
  source {
    content = templatefile("${path.module}/../src/lambda/query_handler/handler.py", {
      # 可以在这里注入环境特定的配置
    })
    filename = "handler.py"
  }
  
  # 依赖库（构建后）
  source_dir = "${path.module}/../.build/query_handler"
  
  depends_on = [null_resource.lambda_build]
}

# Authorizer Lambda ZIP包
data "archive_file" "authorizer_zip" {
  type        = "zip"
  output_path = "${path.module}/../.build/authorizer.zip"
  
  # Lambda函数代码
  source {
    content = templatefile("${path.module}/../src/lambda/authorizer/authorizer.py", {
      # 可以在这里注入环境特定的配置
    })
    filename = "authorizer.py"
  }
  
  # 依赖库（构建后）
  source_dir = "${path.module}/../.build/authorizer"
  
  depends_on = [null_resource.lambda_build]
}

# Document Processor Lambda ZIP包
data "archive_file" "document_processor_zip" {
  type        = "zip"
  output_path = "${path.module}/../.build/document_processor.zip"
  
  source {
    content = templatefile("${path.module}/../src/lambda/document_processor/handler.py", {
      # 文档处理器配置
    })
    filename = "handler.py"
  }
  
  # 依赖库
  source_dir = "${path.module}/../.build/document_processor"
  
  depends_on = [null_resource.lambda_build]
}

# ================================
# Lambda 函数更新配置
# ================================

# 更新Query Handler Lambda函数
resource "aws_lambda_function" "query_handler" {
  filename         = data.archive_file.query_handler_zip.output_path
  function_name    = "${var.project_name}-query-handler-${var.environment}"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size
  
  # 源代码哈希，用于检测代码变更
  source_code_hash = data.archive_file.query_handler_zip.output_base64sha256
  
  # VPC配置
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  
  # 环境变量
  environment {
    variables = {
      ENVIRONMENT                = var.environment
      AWS_REGION                = var.aws_region
      S3_BUCKET                 = aws_s3_bucket.document_storage.bucket
      BEDROCK_MODEL_ID          = var.bedrock_model_id
      BEDROCK_EMBEDDING_MODEL_ID = var.bedrock_embedding_model_id
      KNOWLEDGE_BASE_ID         = aws_bedrockagent_knowledge_base.enterprise_kb.id
      DATA_SOURCE_ID            = aws_bedrockagent_data_source.s3_data_source.data_source_id
      RETRIEVAL_TOP_K           = var.retrieval_top_k
    }
  }
  
  # 依赖关系
  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_bedrockagent_knowledge_base.enterprise_kb,
    aws_vpc.main,
    data.archive_file.query_handler_zip
  ]
  
  tags = local.common_tags
}

# 更新Authorizer Lambda函数
resource "aws_lambda_function" "authorizer" {
  filename         = data.archive_file.authorizer_zip.output_path
  function_name    = "${var.project_name}-authorizer-${var.environment}"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "authorizer.lambda_handler"
  runtime         = "python3.11"
  timeout         = 30
  memory_size     = 256
  
  # 源代码哈希
  source_code_hash = data.archive_file.authorizer_zip.output_base64sha256
  
  # 环境变量
  environment {
    variables = {
      ENVIRONMENT     = var.environment
      USER_POOL_ID    = aws_cognito_user_pool.main.id
      APP_CLIENT_ID   = aws_cognito_user_pool_client.api_client.id
    }
  }
  
  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    data.archive_file.authorizer_zip
  ]
  
  tags = local.common_tags
}

# Document Processor Lambda函数
resource "aws_lambda_function" "document_processor" {
  filename         = data.archive_file.document_processor_zip.output_path
  function_name    = "${var.project_name}-document-processor-${var.environment}"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size
  
  # 源代码哈希
  source_code_hash = data.archive_file.document_processor_zip.output_base64sha256
  
  # VPC配置
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  
  # 环境变量
  environment {
    variables = {
      ENVIRONMENT                = var.environment
      AWS_REGION                = var.aws_region
      S3_BUCKET                 = aws_s3_bucket.document_storage.bucket
      KNOWLEDGE_BASE_ID         = aws_bedrockagent_knowledge_base.enterprise_kb.id
      DATA_SOURCE_ID            = aws_bedrockagent_data_source.s3_data_source.data_source_id
    }
  }
  
  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_bedrockagent_knowledge_base.enterprise_kb,
    aws_vpc.main,
    data.archive_file.document_processor_zip
  ]
  
  tags = local.common_tags
}

# ================================
# Lambda 触发器配置
# ================================

# S3触发器 - 自动处理上传的文档
resource "aws_s3_bucket_notification" "document_upload" {
  bucket = aws_s3_bucket.document_storage.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.document_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "documents/"
    filter_suffix       = ""
  }

  depends_on = [aws_lambda_permission.s3_invoke_document_processor]
}

# Lambda权限 - S3调用Document Processor
resource "aws_lambda_permission" "s3_invoke_document_processor" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.document_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.document_storage.arn
}

# ================================
# Lambda 层配置（可选 - 用于共享依赖）
# ================================

# 公共依赖层
resource "aws_lambda_layer_version" "common_dependencies" {
  filename         = "${path.module}/../.build/common_layer.zip"
  layer_name       = "${var.project_name}-common-deps-${var.environment}"
  description      = "Common dependencies for Lambda functions"
  
  compatible_runtimes = ["python3.11"]
  
  source_code_hash = filebase64sha256("${path.module}/../.build/common_layer.zip")
  
  depends_on = [null_resource.lambda_build]
}

# ================================
# Lambda 函数版本管理
# ================================

# Query Handler函数版本
resource "aws_lambda_alias" "query_handler_current" {
  name             = "current"
  description      = "Current version of query handler"
  function_name    = aws_lambda_function.query_handler.function_name
  function_version = aws_lambda_function.query_handler.version
}

# 蓝绿部署别名（可选）
resource "aws_lambda_alias" "query_handler_staging" {
  count = var.environment == "prod" ? 1 : 0
  
  name             = "staging"
  description      = "Staging version for blue-green deployment"
  function_name    = aws_lambda_function.query_handler.function_name
  function_version = aws_lambda_function.query_handler.version
}

# ================================
# Lambda 保留并发配置
# ================================

# Query Handler预留并发
resource "aws_lambda_provisioned_concurrency_config" "query_handler" {
  count = var.enable_provisioned_concurrency ? 1 : 0
  
  function_name                     = aws_lambda_function.query_handler.function_name
  provisioned_concurrent_executions = var.provisioned_concurrency_count
  qualifier                         = aws_lambda_alias.query_handler_current.name
}

# ================================
# Lambda 死信队列配置
# ================================

# 死信队列
resource "aws_sqs_queue" "lambda_dlq" {
  name                       = "${var.project_name}-lambda-dlq-${var.environment}"
  message_retention_seconds  = 1209600  # 14 days
  max_receive_count         = 3
  
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.lambda_dlq_deadletter.arn
    maxReceiveCount     = 3
  })
  
  tags = local.common_tags
}

# 死信队列的死信队列
resource "aws_sqs_queue" "lambda_dlq_deadletter" {
  name = "${var.project_name}-lambda-dlq-deadletter-${var.environment}"
  
  tags = local.common_tags
}

# Lambda函数死信队列配置
resource "aws_lambda_function_event_invoke_config" "query_handler" {
  function_name = aws_lambda_function.query_handler.function_name
  
  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }
  
  maximum_retry_attempts = 2
}