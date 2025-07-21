#!/usr/bin/env python3
"""
RAG API服务器启动脚本
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def main():
    parser = argparse.ArgumentParser(description="RAG API服务器启动脚本")
    parser.add_argument("--host", default="0.0.0.0", help="绑定主机地址")
    parser.add_argument("--port", type=int, default=8000, help="端口号")
    parser.add_argument("--reload", action="store_true", help="开启自动重载")
    parser.add_argument("--test", action="store_true", help="运行API测试")
    
    args = parser.parse_args()
    
    if args.test:
        run_api_tests()
    else:
        start_api_server(args.host, args.port, args.reload)

def start_api_server(host="0.0.0.0", port=8000, reload=False):
    """启动API服务器"""
    try:
        from src.api_server import run_api_server
        print(f"🚀 启动RAG API服务器...")
        print(f"📍 地址: http://{host}:{port}")
        print(f"📚 API文档: http://{host}:{port}/docs")
        print(f"🔄 自动重载: {'启用' if reload else '禁用'}")
        print("按 Ctrl+C 停止服务器")
        print("=" * 50)
        
        run_api_server(host=host, port=port, reload=reload)
    
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装所需依赖：pip install -r requirements.txt")
    except KeyboardInterrupt:
        print("\n👋 API服务器已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")

def run_api_tests():
    """运行API测试"""
    print("🧪 运行API测试...")
    
    try:
        # 运行测试
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/test_api.py", 
            "-v", "--tb=short"
        ], cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print("✅ 所有API测试通过！")
        else:
            print("❌ 部分API测试失败")
    
    except FileNotFoundError:
        print("❌ pytest未安装，请运行: pip install pytest")
    except Exception as e:
        print(f"❌ 测试运行失败: {e}")

if __name__ == "__main__":
    main()