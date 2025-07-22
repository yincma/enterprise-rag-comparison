# ================================
# 前端应用部署配置
# S3 + CloudFront + 自动化构建
# ================================

# 前端构建过程
resource "null_resource" "frontend_build" {
  # 触发条件：当前端源代码或构建配置发生变化时重新构建
  triggers = {
    frontend_source_hash = data.archive_file.frontend_source.output_md5
    package_json_hash    = filemd5("${path.module}/../src/frontend/package.json")
    build_script_hash    = filemd5("${path.module}/../src/scripts/build-frontend.sh")
    aws_config_hash      = sha256(jsonencode({
      user_pool_id       = aws_cognito_user_pool.main.id
      user_pool_client_id = aws_cognito_user_pool_client.spa_client.id
      api_gateway_url    = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
      region            = var.aws_region
    }))
  }

  # 构建前端应用
  provisioner "local-exec" {
    command = "${path.module}/../src/scripts/build-frontend.sh"
    working_dir = path.module
    
    environment = {
      REACT_APP_AWS_REGION           = var.aws_region
      REACT_APP_USER_POOL_ID         = aws_cognito_user_pool.main.id
      REACT_APP_USER_POOL_CLIENT_ID  = aws_cognito_user_pool_client.spa_client.id
      REACT_APP_API_GATEWAY_URL      = "https://${aws_api_gateway_rest_api.rag_api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
      REACT_APP_VERSION              = "1.0.0"
      REACT_APP_ENVIRONMENT          = var.environment
      REACT_APP_ENABLE_ANALYTICS     = var.environment == "prod" ? "true" : "false"
      REACT_APP_S3_BUCKET           = aws_s3_bucket.frontend_hosting.bucket
    }
  }

  # 清理构建文件
  provisioner "local-exec" {
    when    = destroy
    command = "rm -rf ${path.module}/../src/frontend/build"
    working_dir = path.module
  }

  depends_on = [
    aws_cognito_user_pool.main,
    aws_cognito_user_pool_client.spa_client,
    aws_api_gateway_rest_api.rag_api
  ]
}

# 前端源代码哈希（用于触发重新构建）
data "archive_file" "frontend_source" {
  type        = "zip"
  output_path = "${path.module}/../.build/frontend_source.zip"
  
  source_dir = "${path.module}/../src/frontend/src"
  
  excludes = [
    "node_modules",
    "build",
    ".git",
    "*.log",
    ".DS_Store"
  ]
}

# ================================
# S3 静态网站托管
# ================================

# 生成随机后缀确保S3桶名唯一
resource "random_id" "frontend_bucket_suffix" {
  byte_length = 4
}

# S3存储桶 - 前端托管
resource "aws_s3_bucket" "frontend_hosting" {
  bucket = "${var.project_name}-frontend-${var.environment}-${random_id.frontend_bucket_suffix.hex}"
  
  tags = merge(local.common_tags, {
    Name = "Frontend Hosting"
    Type = "StaticWebsite"
  })
}

# S3存储桶公共访问配置
resource "aws_s3_bucket_public_access_block" "frontend_hosting" {
  bucket = aws_s3_bucket.frontend_hosting.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3存储桶静态网站配置
resource "aws_s3_bucket_website_configuration" "frontend_hosting" {
  bucket = aws_s3_bucket.frontend_hosting.id
  
  index_document {
    suffix = "index.html"
  }
  
  error_document {
    key = "index.html"  # SPA路由处理
  }
}

# S3存储桶版本控制
resource "aws_s3_bucket_versioning" "frontend_hosting" {
  bucket = aws_s3_bucket.frontend_hosting.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3存储桶加密
resource "aws_s3_bucket_server_side_encryption_configuration" "frontend_hosting" {
  bucket = aws_s3_bucket.frontend_hosting.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ================================
# CloudFront分发配置
# ================================

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project_name}-frontend-oac-${var.environment}"
  description                       = "OAC for frontend S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront分发
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  comment             = "Frontend distribution for ${var.project_name}-${var.environment}"
  
  # 源配置
  origin {
    domain_name              = aws_s3_bucket.frontend_hosting.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
    origin_id                = "S3-${aws_s3_bucket.frontend_hosting.bucket}"
    
    # 自定义源配置
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  
  # 默认缓存行为
  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.frontend_hosting.bucket}"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"
    
    # 缓存策略
    cache_policy_id = data.aws_cloudfront_cache_policy.optimized.id
    
    # 响应头策略
    response_headers_policy_id = aws_cloudfront_response_headers_policy.frontend.id
    
    # Lambda@Edge函数（可选）
    dynamic "lambda_function_association" {
      for_each = var.enable_lambda_edge ? [1] : []
      content {
        event_type   = "origin-request"
        lambda_arn   = aws_lambda_function.edge_function[0].qualified_arn
        include_body = false
      }
    }
  }
  
  # SPA路由处理缓存行为
  ordered_cache_behavior {
    path_pattern           = "/static/*"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.frontend_hosting.bucket}"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"
    
    cache_policy_id = data.aws_cloudfront_cache_policy.caching_optimized.id
    
    # 静态资源长期缓存
    min_ttl     = 31536000  # 1年
    default_ttl = 31536000  # 1年
    max_ttl     = 31536000  # 1年
  }
  
  # 地理限制
  restrictions {
    geo_restriction {
      restriction_type = var.environment == "prod" ? "blacklist" : "none"
      locations        = var.environment == "prod" ? ["CN", "RU", "KP"] : []
    }
  }
  
  # SSL证书配置
  viewer_certificate {
    cloudfront_default_certificate = true
    minimum_protocol_version       = "TLSv1.2_2021"
    ssl_support_method             = "sni-only"
  }
  
  # 自定义错误页面
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 300
  }
  
  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 300
  }
  
  # 价格等级
  price_class = var.environment == "prod" ? "PriceClass_All" : "PriceClass_100"
  
  tags = merge(local.common_tags, {
    Name = "${var.project_name}-frontend-cdn-${var.environment}"
    Type = "CDN"
  })
}

# CloudFront缓存策略数据源
data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

# CloudFront响应头策略
resource "aws_cloudfront_response_headers_policy" "frontend" {
  name    = "${var.project_name}-frontend-headers-${var.environment}"
  comment = "Security headers for frontend application"
  
  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                   = true
    }
    
    content_type_options {
      override = true
    }
    
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
  }
  
  cors_config {
    access_control_allow_credentials = false
    access_control_allow_headers {
      items = ["*"]
    }
    access_control_allow_methods {
      items = ["GET", "POST", "OPTIONS", "PUT", "DELETE"]
    }
    access_control_allow_origins {
      items = ["*"]
    }
    access_control_max_age_sec = 86400
    origin_override           = true
  }
}

# ================================
# S3存储桶策略 - CloudFront访问
# ================================

# S3存储桶策略
resource "aws_s3_bucket_policy" "frontend_hosting" {
  bucket = aws_s3_bucket.frontend_hosting.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend_hosting.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      }
    ]
  })
  
  depends_on = [aws_s3_bucket_public_access_block.frontend_hosting]
}

# ================================
# 前端文件部署
# ================================

# 部署构建后的前端文件到S3
resource "null_resource" "frontend_deploy" {
  # 触发条件：构建完成后
  triggers = {
    build_trigger = null_resource.frontend_build.id
    distribution_id = aws_cloudfront_distribution.frontend.id
  }
  
  # 同步文件到S3
  provisioner "local-exec" {
    command = <<-EOT
      if [ -d "${path.module}/../src/frontend/build" ]; then
        aws s3 sync "${path.module}/../src/frontend/build" "s3://${aws_s3_bucket.frontend_hosting.bucket}" \
          --delete \
          --cache-control "public,max-age=31536000,immutable" \
          --exclude "*.html" \
          --exclude "service-worker.js" \
          --exclude "manifest.json"
        
        # HTML文件特殊处理（不缓存）
        aws s3 sync "${path.module}/../src/frontend/build" "s3://${aws_s3_bucket.frontend_hosting.bucket}" \
          --delete \
          --cache-control "public,max-age=0,must-revalidate" \
          --include "*.html" \
          --include "service-worker.js" \
          --include "manifest.json"
      else
        echo "Frontend build directory not found. Please run frontend build first."
        exit 1
      fi
    EOT
  }
  
  # 清除CloudFront缓存
  provisioner "local-exec" {
    command = <<-EOT
      aws cloudfront create-invalidation \
        --distribution-id ${aws_cloudfront_distribution.frontend.id} \
        --paths "/*" \
        --no-cli-pager
    EOT
  }
  
  depends_on = [
    null_resource.frontend_build,
    aws_s3_bucket_policy.frontend_hosting,
    aws_cloudfront_distribution.frontend
  ]
}

# ================================
# Lambda@Edge函数（可选）
# ================================

# Lambda@Edge函数用于高级路由处理
resource "aws_lambda_function" "edge_function" {
  count = var.enable_lambda_edge ? 1 : 0
  
  filename         = "${path.module}/../.build/edge_function.zip"
  function_name    = "${var.project_name}-edge-function-${var.environment}"
  role            = aws_iam_role.lambda_edge_execution_role[0].arn
  handler         = "index.handler"
  runtime         = "nodejs18.x"
  timeout         = 5
  memory_size     = 128
  publish         = true
  
  tags = local.common_tags
}

# Lambda@Edge执行角色
resource "aws_iam_role" "lambda_edge_execution_role" {
  count = var.enable_lambda_edge ? 1 : 0
  
  name = "${var.project_name}-lambda-edge-execution-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "edgelambda.amazonaws.com"
          ]
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# Lambda@Edge基础执行策略
resource "aws_iam_role_policy_attachment" "lambda_edge_basic_execution" {
  count = var.enable_lambda_edge ? 1 : 0
  
  role       = aws_iam_role.lambda_edge_execution_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}