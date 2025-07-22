#!/bin/bash

# ================================
# 一键部署脚本
# 系统二：基于AWS Nova的企业级RAG知识问答系统
# ================================

set -e  # 遇到错误立即退出

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

# 默认配置
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-enterprise-rag}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo -e "\n${PURPLE}=== $1 ===${NC}"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
企业级RAG系统一键部署脚本

用法:
  $0 [选项]

选项:
  -e, --environment ENVIRONMENT    部署环境 (dev/staging/prod) [默认: dev]
  -r, --region REGION             AWS区域 [默认: us-east-1]
  -p, --project-name NAME         项目名称 [默认: enterprise-rag]
  -f, --frontend-only             仅部署前端
  -b, --backend-only              仅部署后端
  -d, --destroy                   销毁基础设施
  -y, --yes                       自动确认所有提示
  -h, --help                      显示此帮助信息

环境变量:
  ENVIRONMENT                     部署环境
  AWS_REGION                      AWS区域
  PROJECT_NAME                    项目名称
  TERRAFORM_BACKEND_BUCKET        Terraform状态存储桶

示例:
  $0                              # 部署到dev环境
  $0 -e prod -r us-west-2         # 部署到prod环境，us-west-2区域
  $0 --frontend-only              # 仅部署前端
  $0 --destroy -y                 # 销毁基础设施（自动确认）
EOF
}

# 解析命令行参数
parse_arguments() {
    FRONTEND_ONLY=false
    BACKEND_ONLY=false
    DESTROY=false
    AUTO_APPROVE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -r|--region)
                AWS_REGION="$2"
                shift 2
                ;;
            -p|--project-name)
                PROJECT_NAME="$2"
                shift 2
                ;;
            -f|--frontend-only)
                FRONTEND_ONLY=true
                shift
                ;;
            -b|--backend-only)
                BACKEND_ONLY=true
                shift
                ;;
            -d|--destroy)
                DESTROY=true
                shift
                ;;
            -y|--yes)
                AUTO_APPROVE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 验证环境参数
    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "无效的环境: $ENVIRONMENT. 必须是 dev, staging, 或 prod"
        exit 1
    fi
}

# 显示部署配置
show_configuration() {
    log_section "部署配置"
    echo "  项目名称: $PROJECT_NAME"
    echo "  环境: $ENVIRONMENT"
    echo "  AWS区域: $AWS_REGION"
    echo "  Terraform目录: $TERRAFORM_DIR"
    echo "  仅前端: $FRONTEND_ONLY"
    echo "  仅后端: $BACKEND_ONLY"
    echo "  销毁模式: $DESTROY"
    echo "  自动确认: $AUTO_APPROVE"
}

# 检查必要工具
check_prerequisites() {
    log_section "检查必要工具"
    
    local missing_tools=()
    
    # 检查AWS CLI
    if ! command -v aws &> /dev/null; then
        missing_tools+=("aws-cli")
    else
        log_success "AWS CLI: $(aws --version)"
    fi
    
    # 检查Terraform
    if ! command -v terraform &> /dev/null; then
        missing_tools+=("terraform")
    else
        local tf_version=$(terraform version -json | jq -r '.terraform_version' 2>/dev/null || terraform version)
        log_success "Terraform: $tf_version"
    fi
    
    # 检查Node.js（如果需要部署前端）
    if [[ "$FRONTEND_ONLY" == "true" || "$BACKEND_ONLY" == "false" ]]; then
        if ! command -v node &> /dev/null; then
            missing_tools+=("node.js")
        else
            log_success "Node.js: $(node --version)"
        fi
        
        if ! command -v npm &> /dev/null; then
            missing_tools+=("npm")
        else
            log_success "npm: $(npm --version)"
        fi
    fi
    
    # 检查Python（如果需要部署后端）
    if [[ "$BACKEND_ONLY" == "true" || "$FRONTEND_ONLY" == "false" ]]; then
        if ! command -v python3 &> /dev/null; then
            missing_tools+=("python3")
        else
            log_success "Python: $(python3 --version)"
        fi
    fi
    
    # 检查jq
    if ! command -v jq &> /dev/null; then
        log_warning "jq未安装（推荐安装以获得更好的体验）"
    else
        log_success "jq: $(jq --version)"
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "缺少必要工具: ${missing_tools[*]}"
        log_info "请安装缺少的工具后再次运行脚本"
        exit 1
    fi
}

# 验证AWS凭证
validate_aws_credentials() {
    log_section "验证AWS凭证"
    
    if ! aws sts get-caller-identity --region "$AWS_REGION" &> /dev/null; then
        log_error "AWS凭证验证失败"
        log_info "请运行: aws configure"
        exit 1
    fi
    
    local aws_identity=$(aws sts get-caller-identity --region "$AWS_REGION" --query '{Account:Account,Arn:Arn}' --output table 2>/dev/null || echo "获取失败")
    log_success "AWS凭证验证成功"
    echo "$aws_identity"
}

# 检查Bedrock模型访问权限
check_bedrock_access() {
    log_section "检查Bedrock模型访问权限"
    
    log_info "检查Bedrock服务可用性..."
    if aws bedrock list-foundation-models --region "$AWS_REGION" &> /dev/null; then
        log_success "Bedrock服务可用"
        
        # 检查Nova模型
        local nova_models=$(aws bedrock list-foundation-models --region "$AWS_REGION" --query 'modelSummaries[?contains(modelId, `nova`)]' --output text 2>/dev/null | wc -l)
        if [ "$nova_models" -gt 0 ]; then
            log_success "Nova模型可用 ($nova_models 个模型)"
        else
            log_warning "Nova模型可能不可用，请检查模型访问权限"
        fi
    else
        log_warning "无法访问Bedrock服务，请检查权限"
    fi
}

# 初始化Terraform
initialize_terraform() {
    log_section "初始化Terraform"
    
    cd "$TERRAFORM_DIR"
    
    log_step "运行 terraform init..."
    terraform init
    
    log_step "验证Terraform配置..."
    terraform validate
    
    log_success "Terraform初始化完成"
}

# 规划部署
plan_deployment() {
    log_section "规划部署"
    
    cd "$TERRAFORM_DIR"
    
    local tfvars_file="environments/${ENVIRONMENT}.tfvars"
    local plan_file="terraform.plan"
    
    # 创建环境配置文件（如果不存在）
    if [ ! -f "$tfvars_file" ]; then
        log_info "创建环境配置文件: $tfvars_file"
        mkdir -p "environments"
        cat > "$tfvars_file" << EOF
# $ENVIRONMENT 环境配置
aws_region = "$AWS_REGION"
environment = "$ENVIRONMENT"
project_name = "$PROJECT_NAME"

# 根据环境调整以下配置
enable_waf = $([ "$ENVIRONMENT" = "prod" ] && echo "true" || echo "false")
enable_detailed_monitoring = $([ "$ENVIRONMENT" = "prod" ] && echo "true" || echo "false")
enable_xray_tracing = true
enable_auto_scaling = true

# Lambda配置
lambda_timeout = $([ "$ENVIRONMENT" = "prod" ] && echo "300" || echo "180")
lambda_memory_size = $([ "$ENVIRONMENT" = "prod" ] && echo "1024" || echo "512")

# 日志保留
log_retention_days = $([ "$ENVIRONMENT" = "prod" ] && echo "90" || echo "30")
EOF
        log_success "环境配置文件已创建"
    fi
    
    log_step "运行 terraform plan..."
    terraform plan -var-file="$tfvars_file" -out="$plan_file"
    
    if [ "$AUTO_APPROVE" = "false" ]; then
        echo
        read -p "是否继续部署？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "部署已取消"
            exit 0
        fi
    fi
}

# 执行部署
execute_deployment() {
    log_section "执行部署"
    
    cd "$TERRAFORM_DIR"
    
    local plan_file="terraform.plan"
    local apply_args=""
    
    if [ "$AUTO_APPROVE" = "true" ]; then
        apply_args="-auto-approve"
    fi
    
    log_step "运行 terraform apply..."
    terraform apply $apply_args "$plan_file"
    
    log_success "基础设施部署完成"
}

# 销毁基础设施
destroy_infrastructure() {
    log_section "销毁基础设施"
    
    cd "$TERRAFORM_DIR"
    
    local tfvars_file="environments/${ENVIRONMENT}.tfvars"
    local destroy_args=""
    
    if [ "$AUTO_APPROVE" = "false" ]; then
        echo
        log_warning "⚠️  这将删除所有资源，包括数据！"
        read -p "确认销毁基础设施？(输入 'destroy' 确认): " confirmation
        if [ "$confirmation" != "destroy" ]; then
            log_info "销毁已取消"
            exit 0
        fi
    else
        destroy_args="-auto-approve"
    fi
    
    log_step "运行 terraform destroy..."
    terraform destroy $destroy_args -var-file="$tfvars_file"
    
    log_success "基础设施已销毁"
}

# 获取部署输出
get_deployment_outputs() {
    log_section "获取部署信息"
    
    cd "$TERRAFORM_DIR"
    
    log_info "获取Terraform输出..."
    
    # 基础信息
    local api_url=$(terraform output -raw api_gateway_url 2>/dev/null || echo "未找到")
    local frontend_url=$(terraform output -raw cloudfront_domain_name 2>/dev/null || echo "未找到")
    local user_pool_id=$(terraform output -raw user_pool_id 2>/dev/null || echo "未找到")
    
    echo
    echo "🎉 部署完成！"
    echo
    echo "📋 系统信息:"
    echo "  API Gateway URL: $api_url"
    echo "  前端URL: https://$frontend_url"
    echo "  用户池ID: $user_pool_id"
    echo
    echo "🔗 有用链接:"
    echo "  AWS控制台: https://$AWS_REGION.console.aws.amazon.com/"
    echo "  CloudWatch Dashboard: https://$AWS_REGION.console.aws.amazon.com/cloudwatch/"
    echo "  Bedrock Console: https://$AWS_REGION.console.aws.amazon.com/bedrock/"
    echo
    echo "📖 下一步:"
    echo "  1. 访问前端URL开始使用系统"
    echo "  2. 上传文档到知识库"
    echo "  3. 查看CloudWatch监控和日志"
    echo
}

# 主函数
main() {
    # 显示标题
    echo -e "${PURPLE}"
    cat << 'EOF'
 ____            _                                _              
|  _ \ __ _  __ _| |    ___  _   _ ___| |_ ___ _ __ (_)_ __   __ _ 
| |_) / _` |/ _` | |   / _ \| | | / __| __/ _ \ '_ \| | '_ \ / _` |
|  _ < (_| | (_| | |  | (_) | |_| \__ \ ||  __/ | | | | | | (_| |
|_| \_\__,_|\__, |_|___\___/ \__, |___/\__\___|_| |_|_|_| |\__, |
            |___/_____|      |___/                        |___/ 
EOF
    echo -e "${NC}"
    echo "🧠 Enterprise RAG System - 智能知识问答系统"
    echo "🚀 AWS + Bedrock + Nova Pro 企业级部署"
    echo
    
    # 解析参数
    parse_arguments "$@"
    
    # 显示配置
    show_configuration
    
    if [ "$DESTROY" = "true" ]; then
        # 销毁模式
        check_prerequisites
        validate_aws_credentials
        initialize_terraform
        destroy_infrastructure
    else
        # 部署模式
        check_prerequisites
        validate_aws_credentials
        check_bedrock_access
        initialize_terraform
        plan_deployment
        execute_deployment
        get_deployment_outputs
    fi
    
    log_success "操作完成！"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi