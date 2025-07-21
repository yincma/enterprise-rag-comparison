# 企业级RAG系统对比项目

## 项目概述

本项目开发两套完整的RAG（Retrieval-Augmented Generation）知识问答系统，用于对比不同技术架构的性能、成本和实用性。

## 系统架构对比

| 特性 | 系统一：本地免费方案 | 系统二：AWS企业方案 |
|------|-------------------|-------------------|
| **成本** | 0美元/月 | 20-100美元/月 |
| **部署** | 本地部署 | 云端托管 |
| **数据安全** | 完全本地化 | 云端加密 |
| **扩展性** | 硬件限制 | 弹性扩展 |
| **响应速度** | 快（本地推理） | 中等（网络延迟） |
| **维护难度** | 低 | 中等 |

## 系统详情

### 🏠 系统一：零成本本地化RAG知识问答系统
- **位置**: `./system-1-local-free/`
- **技术栈**: Ollama + ChromaDB + Streamlit + Python
- **特点**: 完全本地化，零云端费用，保护企业数据隐私
- **适用**: 中小企业、个人开发者、数据敏感场景

### ☁️ 系统二：基于AWS Nova的企业级RAG知识问答系统
- **位置**: `./system-2-aws-bedrock/`
- **技术栈**: AWS Bedrock + Nova + Lambda + React
- **特点**: 企业级可扩展性，托管服务，全球部署
- **适用**: 大型企业、高并发场景、全球化部署

## 项目结构

```
RAG-Comparison-Project/
├── README.md                    # 项目总览（本文件）
├── system-1-local-free/         # 系统一：本地免费方案
│   ├── README.md
│   ├── src/
│   ├── config/
│   ├── tests/
│   └── docs/
├── system-2-aws-bedrock/        # 系统二：AWS企业方案
│   ├── README.md
│   ├── src/
│   ├── terraform/
│   ├── tests/
│   └── docs/
├── comparison/                  # 系统对比分析
│   ├── performance_benchmarks/
│   ├── cost_analysis/
│   └── feature_comparison.md
└── shared/                      # 共享测试资源
    ├── test_documents/
    └── evaluation_scripts/
```

## 开发进度

- [ ] Phase 1: 项目基础搭建
- [ ] Phase 2: 系统一开发（本地免费方案）
- [ ] Phase 3: 系统二开发（AWS企业方案）  
- [ ] Phase 4: 性能对比测试和分析

## 快速开始

### 系统一（本地免费）
```bash
cd system-1-local-free
pip install -r requirements.txt
python src/main.py
```

### 系统二（AWS企业）
```bash
cd system-2-aws-bedrock
pip install -r requirements.txt
# 配置AWS凭证
aws configure
python src/main.py
```

## 贡献指南

本项目用于技术研究和对比分析，欢迎提交Issue和PR。

## 许可证

MIT License

---

**开发时间**: 2025年1月  
**作者**: 企业级RAG系统研发团队  
**目标**: 为企业选择最适合的RAG解决方案提供数据支撑