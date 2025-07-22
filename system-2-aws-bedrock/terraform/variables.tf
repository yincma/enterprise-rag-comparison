# 系统二：AWS Bedrock企业级RAG系统
# Terraform变量定义

variable "aws_region" {
  description = "AWS部署区域"
  type        = string
  default     = "us-east-1"
  
  validation {
    condition = can(regex("^[a-z0-9-]+$", var.aws_region))
    error_message = "AWS区域格式无效。"
  }
}

variable "environment" {
  description = "部署环境（dev, staging, prod）"
  type        = string
  default     = "dev"
  
  validation {
    condition = contains(["dev", "staging", "prod"], var.environment)
    error_message = "环境必须是 dev, staging, 或 prod 之一。"
  }
}

variable "project_name" {
  description = "项目名称"
  type        = string
  default     = "enterprise-rag"
  
  validation {
    condition = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "项目名称只能包含小写字母、数字和短横线。"
  }
}

# Bedrock配置
variable "bedrock_model_id" {
  description = "Bedrock大语言模型ID"
  type        = string
  default     = "amazon.nova-pro-v1:0"
}

variable "bedrock_embedding_model_id" {
  description = "Bedrock嵌入模型ID"
  type        = string
  default     = "amazon.titan-embed-text-v1"
}

variable "bedrock_knowledge_base_name" {
  description = "Bedrock知识库名称"
  type        = string
  default     = "enterprise-knowledge-base"
}

# Lambda配置
variable "lambda_timeout" {
  description = "Lambda函数超时时间（秒）"
  type        = number
  default     = 300
  
  validation {
    condition = var.lambda_timeout >= 30 && var.lambda_timeout <= 900
    error_message = "Lambda超时时间必须在30-900秒之间。"
  }
}

variable "lambda_memory_size" {
  description = "Lambda函数内存大小（MB）"
  type        = number
  default     = 512
  
  validation {
    condition = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Lambda内存大小必须在128-10240MB之间。"
  }
}

# 日志配置
variable "log_retention_days" {
  description = "CloudWatch日志保留天数"
  type        = number
  default     = 30
  
  validation {
    condition = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "日志保留天数必须是AWS支持的值。"
  }
}

# 网络配置
variable "vpc_cidr" {
  description = "VPC CIDR块"
  type        = string
  default     = "10.0.0.0/16"
  
  validation {
    condition = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR必须是有效的CIDR格式。"
  }
}

variable "availability_zones" {
  description = "可用区列表"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "private_subnet_cidrs" {
  description = "私有子网CIDR列表"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "public_subnet_cidrs" {
  description = "公有子网CIDR列表"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

# API Gateway配置
variable "api_throttle_rate_limit" {
  description = "API Gateway节流速率限制"
  type        = number
  default     = 1000
}

variable "api_throttle_burst_limit" {
  description = "API Gateway节流突发限制"
  type        = number
  default     = 2000
}

# 安全配置
variable "enable_waf" {
  description = "是否启用AWS WAF"
  type        = bool
  default     = false
}

variable "allowed_origins" {
  description = "CORS允许的源域名列表"
  type        = list(string)
  default     = ["*"]
}

# 监控配置
variable "enable_xray_tracing" {
  description = "是否启用X-Ray分布式跟踪"
  type        = bool
  default     = true
}

variable "enable_detailed_monitoring" {
  description = "是否启用详细监控"
  type        = bool
  default     = false
}

# 成本控制
variable "enable_auto_scaling" {
  description = "是否启用自动扩缩容"
  type        = bool
  default     = true
}

variable "min_capacity" {
  description = "最小容量"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "最大容量"
  type        = number
  default     = 10
}

# 备份配置
variable "enable_backup" {
  description = "是否启用自动备份"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "备份保留天数"
  type        = number
  default     = 7
}

# 标签配置
variable "additional_tags" {
  description = "额外的资源标签"
  type        = map(string)
  default     = {}
}

# 文档处理配置
variable "max_document_size_mb" {
  description = "最大文档大小（MB）"
  type        = number
  default     = 100
}

variable "supported_document_types" {
  description = "支持的文档类型列表"
  type        = list(string)
  default     = [".pdf", ".docx", ".txt", ".md"]
}

# 性能配置
variable "knowledge_base_chunk_size" {
  description = "知识库文档分块大小"
  type        = number
  default     = 1000
}

variable "knowledge_base_chunk_overlap" {
  description = "知识库文档分块重叠"
  type        = number
  default     = 200
}

variable "retrieval_top_k" {
  description = "默认检索文档数量"
  type        = number
  default     = 5
  
  validation {
    condition = var.retrieval_top_k >= 1 && var.retrieval_top_k <= 20
    error_message = "检索文档数量必须在1-20之间。"
  }
}

# 开发配置
variable "enable_debug_mode" {
  description = "是否启用调试模式"
  type        = bool
  default     = false
}

variable "local_development" {
  description = "是否为本地开发环境"
  type        = bool
  default     = false
}

# Lambda@Edge配置
variable "enable_lambda_edge" {
  description = "是否启用Lambda@Edge功能"
  type        = bool
  default     = false
}

# Lambda预留并发配置
variable "enable_provisioned_concurrency" {
  description = "是否启用Lambda预留并发"
  type        = bool
  default     = false
}

variable "provisioned_concurrency_count" {
  description = "预留并发数量"
  type        = number
  default     = 5
  
  validation {
    condition = var.provisioned_concurrency_count >= 1 && var.provisioned_concurrency_count <= 100
    error_message = "预留并发数量必须在1-100之间。"
  }
}

# 前端部署配置
variable "frontend_domain_name" {
  description = "前端自定义域名（可选）"
  type        = string
  default     = ""
}

variable "ssl_certificate_arn" {
  description = "SSL证书ARN（用于自定义域名）"
  type        = string
  default     = ""
}

# 部署配置
variable "enable_blue_green_deployment" {
  description = "是否启用蓝绿部署"
  type        = bool
  default     = false
}

variable "enable_canary_deployment" {
  description = "是否启用金丝雀部署"
  type        = bool
  default     = false
}

# 数据源同步配置
variable "auto_sync_knowledge_base" {
  description = "是否自动同步知识库"
  type        = bool
  default     = true
}

variable "sync_schedule_expression" {
  description = "同步计划表达式（cron格式）"
  type        = string
  default     = "rate(1 hour)"
}