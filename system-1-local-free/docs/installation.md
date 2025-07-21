# 安装指南

## 系统要求

- Python 3.8+
- 至少 8GB 内存
- 10GB+ 可用存储空间
- Ollama (用于本地LLM)

## 安装步骤

### 1. 安装 Python 依赖

```bash
cd system-1-local-free
pip install -r requirements.txt
```

### 2. 安装 Ollama

#### macOS
```bash
brew install ollama
```

#### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 3. 启动 Ollama 服务

```bash
ollama serve
```

### 4. 下载 LLM 模型

```bash
ollama pull llama3.1:8b
```

### 5. 启动应用

```bash
streamlit run src/main.py
```

## 验证安装

访问 http://localhost:8501 查看应用界面。

## 故障排除

详见 README.md 中的故障排除部分。