#!/bin/bash

# ================================
# AWS Lambda 自动化构建脚本
# 系统二：基于AWS Nova的企业级RAG知识问答系统
# ================================

set -e  # 遇到错误立即退出

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BUILD_DIR="$PROJECT_ROOT/.build"
SRC_DIR="$PROJECT_ROOT/src"
LAMBDA_DIR="$SRC_DIR/lambda"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# 检查必要工具
check_dependencies() {
    log_info "检查构建依赖..."
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3未找到，请安装Python 3.9+)"
        exit 1
    fi
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3未找到，请安装pip"
        exit 1
    fi
    
    # 检查zip
    if ! command -v zip &> /dev/null; then
        log_error "zip命令未找到，请安装zip工具"
        exit 1
    fi
    
    log_success "所有依赖检查通过"
}

# 清理并创建构建目录
setup_build_dir() {
    log_info "设置构建目录..."
    
    # 清理旧的构建文件
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
    fi
    
    # 创建构建目录结构
    mkdir -p "$BUILD_DIR"/{query_handler,authorizer,document_processor,common_layer}
    
    log_success "构建目录创建完成: $BUILD_DIR"
}

# 安装Python依赖
install_dependencies() {
    local target_dir=$1
    local requirements_file=$2
    
    log_info "安装Python依赖到: $target_dir"
    
    # 检查requirements文件是否存在
    if [ ! -f "$requirements_file" ]; then
        log_warning "Requirements文件不存在: $requirements_file"
        return 0
    fi
    
    # 安装依赖
    pip3 install \
        --requirement "$requirements_file" \
        --target "$target_dir" \
        --upgrade \
        --no-cache-dir \
        --platform linux_x86_64 \
        --implementation cp \
        --python-version 3.11 \
        --only-binary=:all: \
        --quiet
    
    # 清理不必要的文件
    find "$target_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$target_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$target_dir" -type f -name "*.pyo" -delete 2>/dev/null || true
    find "$target_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
    find "$target_dir" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    
    log_success "依赖安装完成"
}

# 构建特定Lambda函数
build_lambda_function() {
    local function_name=$1
    local source_dir="$LAMBDA_DIR/$function_name"
    local build_target="$BUILD_DIR/$function_name"
    
    log_info "构建Lambda函数: $function_name"
    
    # 检查源代码目录
    if [ ! -d "$source_dir" ]; then
        log_error "Lambda函数源代码目录不存在: $source_dir"
        return 1
    fi
    
    # 安装函数特定的依赖
    local function_requirements="$source_dir/requirements.txt"
    if [ -f "$function_requirements" ]; then
        install_dependencies "$build_target" "$function_requirements"
    else
        # 使用通用依赖
        install_dependencies "$build_target" "$PROJECT_ROOT/requirements.txt"
    fi
    
    # 复制函数源代码
    log_info "复制源代码: $function_name"
    cp -r "$source_dir"/* "$build_target/"
    
    # 复制公共工具
    if [ -d "$SRC_DIR/utils" ]; then
        cp -r "$SRC_DIR/utils" "$build_target/"
    fi
    
    log_success "Lambda函数构建完成: $function_name"
}

# 构建公共依赖层
build_common_layer() {
    log_info "构建公共依赖层..."
    
    local layer_dir="$BUILD_DIR/common_layer/python"
    mkdir -p "$layer_dir"
    
    # 安装公共依赖
    install_dependencies "$layer_dir" "$PROJECT_ROOT/requirements.txt"
    
    # 创建层ZIP包
    cd "$BUILD_DIR/common_layer"
    zip -r "../common_layer.zip" python/ > /dev/null
    cd - > /dev/null
    
    log_success "公共依赖层构建完成"
}

# 优化ZIP包
optimize_packages() {
    log_info "优化构建包..."
    
    for function_dir in "$BUILD_DIR"/{query_handler,authorizer,document_processor}; do
        if [ -d "$function_dir" ]; then
            # 删除测试文件
            find "$function_dir" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
            find "$function_dir" -type f -name "*test*.py" -delete 2>/dev/null || true
            
            # 删除文档文件
            find "$function_dir" -type f \( -name "*.md" -o -name "*.rst" -o -name "*.txt" \) -delete 2>/dev/null || true
            
            # 删除示例文件
            find "$function_dir" -type d -name "examples" -exec rm -rf {} + 2>/dev/null || true
            find "$function_dir" -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true
        fi
    done
    
    log_success "包优化完成"
}

# 生成构建报告
generate_build_report() {
    log_info "生成构建报告..."
    
    local report_file="$BUILD_DIR/build_report.txt"
    
    cat > "$report_file" << EOF
# Lambda函数构建报告
构建时间: $(date)
项目路径: $PROJECT_ROOT
构建路径: $BUILD_DIR

## 构建的函数:
EOF
    
    for function_dir in "$BUILD_DIR"/{query_handler,authorizer,document_processor}; do
        if [ -d "$function_dir" ]; then
            local function_name=$(basename "$function_dir")
            local size=$(du -sh "$function_dir" | cut -f1)
            local file_count=$(find "$function_dir" -type f | wc -l)
            
            echo "- $function_name: $size ($file_count 文件)" >> "$report_file"
        fi
    done
    
    echo "" >> "$report_file"
    echo "## 公共依赖层:" >> "$report_file"
    if [ -f "$BUILD_DIR/common_layer.zip" ]; then
        local layer_size=$(du -sh "$BUILD_DIR/common_layer.zip" | cut -f1)
        echo "- common_layer.zip: $layer_size" >> "$report_file"
    fi
    
    log_success "构建报告已生成: $report_file"
}

# 验证构建结果
validate_build() {
    log_info "验证构建结果..."
    
    local errors=0
    
    # 检查Lambda函数构建
    for function_name in query_handler authorizer document_processor; do
        local function_dir="$BUILD_DIR/$function_name"
        if [ ! -d "$function_dir" ]; then
            log_error "Lambda函数构建失败: $function_name"
            ((errors++))
        else
            # 检查主要文件
            local main_files=(
                "*.py"
            )
            
            local found_files=false
            for pattern in "${main_files[@]}"; do
                if ls "$function_dir"/$pattern 1> /dev/null 2>&1; then
                    found_files=true
                    break
                fi
            done
            
            if [ "$found_files" = false ]; then
                log_error "Lambda函数缺少主要文件: $function_name"
                ((errors++))
            fi
        fi
    done
    
    # 检查公共层
    if [ ! -f "$BUILD_DIR/common_layer.zip" ]; then
        log_warning "公共依赖层构建失败"
    fi
    
    if [ $errors -eq 0 ]; then
        log_success "构建验证通过"
        return 0
    else
        log_error "构建验证失败，发现 $errors 个错误"
        return 1
    fi
}

# 主函数
main() {
    log_info "开始Lambda函数自动化构建..."
    log_info "项目根目录: $PROJECT_ROOT"
    
    # 执行构建步骤
    check_dependencies
    setup_build_dir
    
    # 构建各个Lambda函数
    build_lambda_function "query_handler"
    build_lambda_function "authorizer"
    
    # 创建document_processor函数（如果不存在）
    if [ ! -d "$LAMBDA_DIR/document_processor" ]; then
        log_warning "document_processor函数不存在，创建基础版本"
        mkdir -p "$LAMBDA_DIR/document_processor"
        cat > "$LAMBDA_DIR/document_processor/handler.py" << 'EOF'
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Document Processor Lambda函数
    处理S3上传的文档
    """
    logger.info(f"收到事件: {json.dumps(event, default=str)}")
    
    # TODO: 实现文档处理逻辑
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Document processed successfully',
            'event': event
        })
    }
EOF
    fi
    
    build_lambda_function "document_processor"
    
    # 构建公共层
    build_common_layer
    
    # 优化和验证
    optimize_packages
    validate_build
    generate_build_report
    
    log_success "Lambda函数构建完成！"
    log_info "构建文件位置: $BUILD_DIR"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi