#!/bin/bash

# ================================
# React 前端应用自动化构建脚本
# 系统二：基于AWS Nova的企业级RAG知识问答系统
# ================================

set -e  # 遇到错误立即退出

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
FRONTEND_DIR="$PROJECT_ROOT/src/frontend"
BUILD_DIR="$FRONTEND_DIR/build"

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
    
    # 检查Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js未找到，请安装Node.js 16+"
        exit 1
    fi
    
    local node_version=$(node --version | cut -d'v' -f2)
    local node_major=$(echo $node_version | cut -d'.' -f1)
    if [ $node_major -lt 16 ]; then
        log_error "Node.js版本过低，需要16+，当前版本: $node_version"
        exit 1
    fi
    
    # 检查npm
    if ! command -v npm &> /dev/null; then
        log_error "npm未找到，请安装npm"
        exit 1
    fi
    
    log_success "所有依赖检查通过 (Node.js: $node_version)"
}

# 检查前端目录结构
check_frontend_structure() {
    log_info "检查前端项目结构..."
    
    if [ ! -d "$FRONTEND_DIR" ]; then
        log_error "前端目录不存在: $FRONTEND_DIR"
        exit 1
    fi
    
    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        log_error "package.json文件不存在"
        exit 1
    fi
    
    if [ ! -d "$FRONTEND_DIR/src" ]; then
        log_error "src目录不存在"
        exit 1
    fi
    
    if [ ! -f "$FRONTEND_DIR/src/App.tsx" ]; then
        log_warning "App.tsx文件不存在，将创建基础版本"
        create_basic_app_structure
    fi
    
    log_success "前端项目结构检查完成"
}

# 创建基础应用结构（如果不存在）
create_basic_app_structure() {
    log_info "创建基础React应用结构..."
    
    # 创建必要的目录
    mkdir -p "$FRONTEND_DIR/src/"{components,pages,services,utils,context}
    mkdir -p "$FRONTEND_DIR/public"
    
    # 创建基础的index.tsx
    if [ ! -f "$FRONTEND_DIR/src/index.tsx" ]; then
        cat > "$FRONTEND_DIR/src/index.tsx" << 'EOF'
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
EOF
    fi
    
    # 创建基础的index.css
    if [ ! -f "$FRONTEND_DIR/src/index.css" ]; then
        cat > "$FRONTEND_DIR/src/index.css" << 'EOF'
body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New',
    monospace;
}

* {
  box-sizing: border-box;
}
EOF
    fi
    
    # 创建基础的App.css
    if [ ! -f "$FRONTEND_DIR/src/App.css" ]; then
        cat > "$FRONTEND_DIR/src/App.css" << 'EOF'
.App {
  text-align: center;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: calc(10px + 2vmin);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.App-header {
  margin-bottom: 2rem;
}

.App-title {
  font-size: 3rem;
  font-weight: 600;
  margin-bottom: 1rem;
}

.App-subtitle {
  font-size: 1.2rem;
  opacity: 0.9;
  margin-bottom: 2rem;
}

.App-features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  max-width: 800px;
  width: 100%;
  padding: 0 2rem;
}

.feature-card {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 1.5rem;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.feature-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.feature-title {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.feature-description {
  font-size: 0.8rem;
  opacity: 0.8;
  line-height: 1.4;
}
EOF
    fi
    
    log_success "基础应用结构创建完成"
}

# 设置环境变量
setup_environment() {
    log_info "设置构建环境变量..."
    
    # 从环境变量或默认值设置
    export REACT_APP_AWS_REGION="${REACT_APP_AWS_REGION:-us-east-1}"
    export REACT_APP_USER_POOL_ID="${REACT_APP_USER_POOL_ID:-}"
    export REACT_APP_USER_POOL_CLIENT_ID="${REACT_APP_USER_POOL_CLIENT_ID:-}"
    export REACT_APP_API_GATEWAY_URL="${REACT_APP_API_GATEWAY_URL:-}"
    export REACT_APP_VERSION="${REACT_APP_VERSION:-1.0.0}"
    export REACT_APP_ENVIRONMENT="${REACT_APP_ENVIRONMENT:-development}"
    export REACT_APP_ENABLE_ANALYTICS="${REACT_APP_ENABLE_ANALYTICS:-false}"
    export REACT_APP_S3_BUCKET="${REACT_APP_S3_BUCKET:-}"
    
    # 设置构建模式
    export NODE_ENV="production"
    export GENERATE_SOURCEMAP="false"
    export INLINE_RUNTIME_CHUNK="false"
    
    log_info "环境配置:"
    log_info "  AWS Region: $REACT_APP_AWS_REGION"
    log_info "  Environment: $REACT_APP_ENVIRONMENT"
    log_info "  Version: $REACT_APP_VERSION"
    log_info "  API URL: ${REACT_APP_API_GATEWAY_URL:-'Not set'}"
    
    log_success "环境变量设置完成"
}

# 安装依赖
install_dependencies() {
    log_info "安装前端依赖..."
    
    cd "$FRONTEND_DIR"
    
    # 检查package-lock.json是否存在
    if [ -f "package-lock.json" ]; then
        log_info "使用npm ci进行快速安装"
        npm ci --silent
    else
        log_info "使用npm install安装依赖"
        npm install --silent
    fi
    
    log_success "依赖安装完成"
}

# 代码质量检查
run_code_quality_checks() {
    log_info "运行代码质量检查..."
    
    cd "$FRONTEND_DIR"
    
    # TypeScript类型检查
    if command -v tsc &> /dev/null; then
        log_info "运行TypeScript类型检查..."
        npx tsc --noEmit --skipLibCheck || {
            log_warning "TypeScript类型检查发现问题，但继续构建"
        }
    fi
    
    # ESLint检查（如果配置了）
    if [ -f ".eslintrc.js" ] || [ -f ".eslintrc.json" ] || [ -f "package.json" ]; then
        if npm list eslint &> /dev/null; then
            log_info "运行ESLint检查..."
            npx eslint src --ext .ts,.tsx --max-warnings 10 || {
                log_warning "ESLint检查发现问题，但继续构建"
            }
        fi
    fi
    
    log_success "代码质量检查完成"
}

# 构建应用
build_application() {
    log_info "构建React应用..."
    
    cd "$FRONTEND_DIR"
    
    # 清理之前的构建
    if [ -d "$BUILD_DIR" ]; then
        log_info "清理之前的构建文件..."
        rm -rf "$BUILD_DIR"
    fi
    
    # 构建应用
    log_info "开始构建过程..."
    npm run build
    
    # 检查构建结果
    if [ ! -d "$BUILD_DIR" ]; then
        log_error "构建失败：build目录不存在"
        exit 1
    fi
    
    if [ ! -f "$BUILD_DIR/index.html" ]; then
        log_error "构建失败：index.html文件不存在"
        exit 1
    fi
    
    log_success "React应用构建完成"
}

# 优化构建结果
optimize_build() {
    log_info "优化构建结果..."
    
    cd "$BUILD_DIR"
    
    # 计算构建文件大小
    local total_size=$(du -sh . | cut -f1)
    local file_count=$(find . -type f | wc -l)
    
    log_info "构建统计:"
    log_info "  总大小: $total_size"
    log_info "  文件数量: $file_count"
    
    # 列出大文件
    log_info "大文件列表 (>100KB):"
    find . -type f -size +100k -exec du -h {} + | sort -hr | head -10 || true
    
    # 压缩检查
    if command -v gzip &> /dev/null; then
        local js_files=$(find . -name "*.js" -type f | wc -l)
        local css_files=$(find . -name "*.css" -type f | wc -l)
        log_info "JavaScript文件: $js_files 个"
        log_info "CSS文件: $css_files 个"
    fi
    
    log_success "构建优化完成"
}

# 生成构建报告
generate_build_report() {
    log_info "生成构建报告..."
    
    local report_file="$BUILD_DIR/build-report.json"
    
    cat > "$report_file" << EOF
{
  "build_time": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "version": "$REACT_APP_VERSION",
  "environment": "$REACT_APP_ENVIRONMENT",
  "aws_region": "$REACT_APP_AWS_REGION",
  "node_version": "$(node --version)",
  "npm_version": "$(npm --version)",
  "build_size": "$(du -sh $BUILD_DIR | cut -f1)",
  "file_count": $(find $BUILD_DIR -type f | wc -l),
  "config": {
    "api_gateway_url": "$REACT_APP_API_GATEWAY_URL",
    "user_pool_id": "${REACT_APP_USER_POOL_ID:0:10}...",
    "analytics_enabled": "$REACT_APP_ENABLE_ANALYTICS"
  }
}
EOF
    
    log_success "构建报告已生成: $report_file"
}

# 验证构建结果
validate_build() {
    log_info "验证构建结果..."
    
    local errors=0
    
    # 检查必要文件
    local required_files=(
        "index.html"
        "static/js"
        "static/css"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -e "$BUILD_DIR/$file" ]; then
            log_error "缺少必要文件: $file"
            ((errors++))
        fi
    done
    
    # 检查index.html内容
    if [ -f "$BUILD_DIR/index.html" ]; then
        if ! grep -q "Enterprise RAG" "$BUILD_DIR/index.html"; then
            log_warning "index.html可能缺少正确的标题"
        fi
    fi
    
    # 检查静态资源
    local js_files=$(find "$BUILD_DIR/static/js" -name "*.js" 2>/dev/null | wc -l)
    local css_files=$(find "$BUILD_DIR/static/css" -name "*.css" 2>/dev/null | wc -l)
    
    if [ $js_files -eq 0 ]; then
        log_error "未找到JavaScript文件"
        ((errors++))
    fi
    
    if [ $css_files -eq 0 ]; then
        log_warning "未找到CSS文件"
    fi
    
    if [ $errors -eq 0 ]; then
        log_success "构建验证通过"
        return 0
    else
        log_error "构建验证失败，发现 $errors 个错误"
        return 1
    fi
}

# 清理临时文件
cleanup() {
    log_info "清理临时文件..."
    
    cd "$FRONTEND_DIR"
    
    # 清理node_modules中的缓存
    if [ -d "node_modules/.cache" ]; then
        rm -rf "node_modules/.cache"
    fi
    
    log_success "清理完成"
}

# 主函数
main() {
    log_info "开始前端应用构建..."
    log_info "前端目录: $FRONTEND_DIR"
    
    # 执行构建步骤
    check_dependencies
    check_frontend_structure
    setup_environment
    install_dependencies
    run_code_quality_checks
    build_application
    optimize_build
    validate_build
    generate_build_report
    cleanup
    
    log_success "前端应用构建完成！"
    log_info "构建文件位置: $BUILD_DIR"
    
    # 显示下一步提示
    log_info ""
    log_info "下一步："
    log_info "  1. 部署到S3: aws s3 sync $BUILD_DIR s3://your-bucket/"
    log_info "  2. 清除CloudFront缓存: aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION_ID --paths '/*'"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi