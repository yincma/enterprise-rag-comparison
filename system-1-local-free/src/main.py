"""
Streamlit主应用
企业级本地RAG知识问答系统的Web界面
"""

import streamlit as st
import time
import logging
from pathlib import Path
from typing import List, Dict, Any

# 本地模块
from .rag_pipeline import rag_pipeline
from .utils.config import config_manager
from .utils.helpers import format_file_size, get_system_info

# 配置页面
st.set_page_config(
    page_title="企业RAG知识问答系统",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/enterprise-rag/system-1-local-free',
        'Report a bug': 'https://github.com/enterprise-rag/system-1-local-free/issues',
        'About': """
        # 企业RAG知识问答系统
        
        基于Ollama和ChromaDB的零成本本地化RAG解决方案
        
        **版本**: 1.0.0  
        **作者**: 企业RAG研发团队
        """
    }
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGApp:
    """RAG应用主类"""
    
    def __init__(self):
        """初始化应用"""
        self.config = config_manager.load_app_config()
        self.ui_config = self.config.get('ui', {})
        self.rag = rag_pipeline
        
        # 初始化会话状态
        self._init_session_state()
        
        # 应用自定义样式
        self._apply_custom_styles()
    
    def _init_session_state(self):
        """初始化会话状态"""
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        
        if 'uploaded_files' not in st.session_state:
            st.session_state.uploaded_files = []
        
        if 'knowledge_base_stats' not in st.session_state:
            st.session_state.knowledge_base_stats = None
        
        if 'system_health' not in st.session_state:
            st.session_state.system_health = None
    
    def _apply_custom_styles(self):
        """应用自定义样式"""
        st.markdown("""
        <style>
        .main-header {
            text-align: center;
            padding: 2rem 0;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 2rem;
        }
        
        .metric-card {
            background: #f0f2f6;
            padding: 1rem;
            border-radius: 10px;
            border-left: 4px solid #667eea;
            margin: 1rem 0;
        }
        
        .success-message {
            padding: 1rem;
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            color: #155724;
        }
        
        .error-message {
            padding: 1rem;
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            color: #721c24;
        }
        
        .chat-message {
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 10px;
        }
        
        .user-message {
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
        }
        
        .assistant-message {
            background-color: #f3e5f5;
            border-left: 4px solid #9c27b0;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def run(self):
        """运行主应用"""
        # 主标题
        st.markdown("""
        <div class="main-header">
            <h1>🧠 企业RAG知识问答系统</h1>
            <p>基于Ollama和ChromaDB的零成本本地化解决方案</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 侧边栏
        self._render_sidebar()
        
        # 主内容区域
        self._render_main_content()
    
    def _render_sidebar(self):
        """渲染侧边栏"""
        with st.sidebar:
            st.markdown("## 📋 系统管理")
            
            # 系统状态
            self._render_system_status()
            
            st.markdown("---")
            
            # 文档管理
            self._render_document_management()
            
            st.markdown("---")
            
            # 系统设置
            self._render_system_settings()
            
            st.markdown("---")
            
            # 知识库统计
            self._render_knowledge_base_stats()
    
    def _render_system_status(self):
        """渲染系统状态"""
        st.markdown("### 🔧 系统状态")
        
        if st.button("刷新系统状态", key="refresh_health"):
            with st.spinner("检查系统状态..."):
                st.session_state.system_health = self.rag.health_check()
        
        if st.session_state.system_health:
            health = st.session_state.system_health
            
            overall_status = health.get("overall", "unknown")
            if overall_status == "healthy":
                st.success("🟢 系统运行正常")
            elif overall_status == "degraded":
                st.warning("🟡 系统部分功能异常")
            else:
                st.error("🔴 系统存在问题")
            
            # 组件状态详情
            components = health.get("components", {})
            for comp_name, comp_status in components.items():
                status = comp_status.get("status", "unknown")
                if status == "healthy":
                    st.text(f"✅ {comp_name}: 正常")
                else:
                    st.text(f"❌ {comp_name}: {comp_status.get('error', '异常')}")
    
    def _render_document_management(self):
        """渲染文档管理"""
        st.markdown("### 📄 文档管理")
        
        # 文档上传
        uploaded_files = st.file_uploader(
            "上传文档",
            type=['pdf', 'docx', 'txt', 'md'],
            accept_multiple_files=True,
            key="doc_uploader",
            help="支持PDF、Word、文本和Markdown格式"
        )
        
        if uploaded_files:
            if st.button("添加到知识库", key="add_docs"):
                self._process_uploaded_files(uploaded_files)
        
        # 清空知识库
        st.markdown("#### ⚠️ 危险操作")
        if st.button("清空知识库", key="clear_kb", type="secondary"):
            if st.session_state.get("confirm_clear", False):
                with st.spinner("正在清空知识库..."):
                    result = self.rag.clear_knowledge_base()
                    if result["success"]:
                        st.success("知识库已清空")
                        st.session_state.knowledge_base_stats = None
                    else:
                        st.error(f"清空失败: {result['message']}")
                st.session_state.confirm_clear = False
            else:
                st.session_state.confirm_clear = True
                st.warning("再次点击确认清空知识库")
    
    def _render_system_settings(self):
        """渲染系统设置"""
        st.markdown("### ⚙️ 系统设置")
        
        # 检索参数设置
        st.markdown("#### 检索参数")
        
        top_k = st.slider("检索文档数量", 1, 20, 5, key="top_k_setting")
        similarity_threshold = st.slider("相似度阈值", 0.0, 1.0, 0.7, 0.1, key="similarity_threshold_setting")
        
        if st.button("应用设置", key="apply_settings"):
            self.rag.update_retrieval_params(top_k, similarity_threshold)
            st.success("设置已更新")
        
        # 模型参数设置
        st.markdown("#### 模型参数")
        
        temperature = st.slider("创造性程度", 0.0, 2.0, 0.1, 0.1, key="temperature_setting")
        max_tokens = st.number_input("最大回答长度", 100, 4000, 2000, 100, key="max_tokens_setting")
        
        if st.button("更新模型参数", key="update_model_params"):
            self.rag.llm.update_model_config(temperature=temperature, max_tokens=max_tokens)
            st.success("模型参数已更新")
    
    def _render_knowledge_base_stats(self):
        """渲染知识库统计"""
        st.markdown("### 📊 知识库统计")
        
        if st.button("刷新统计", key="refresh_stats"):
            result = self.rag.get_knowledge_base_stats()
            if result["success"]:
                st.session_state.knowledge_base_stats = result["statistics"]
        
        if st.session_state.knowledge_base_stats:
            stats = st.session_state.knowledge_base_stats
            
            st.metric("文档块数量", stats.get("total_chunks", 0))
            st.metric("文档数量", stats.get("unique_documents", 0))
            
            if "file_types" in stats:
                st.markdown("**文件类型分布:**")
                for file_type, count in stats["file_types"].items():
                    st.text(f"{file_type}: {count} 个")
    
    def _render_main_content(self):
        """渲染主内容区域"""
        # 标签页
        tab1, tab2, tab3 = st.tabs(["💬 智能问答", "📚 文档浏览", "📈 系统监控"])
        
        with tab1:
            self._render_chat_interface()
        
        with tab2:
            self._render_document_browser()
        
        with tab3:
            self._render_system_monitor()
    
    def _render_chat_interface(self):
        """渲染聊天界面"""
        st.markdown("## 💬 智能问答")
        
        # 显示历史消息
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # 显示来源信息
                if message["role"] == "assistant" and "sources" in message:
                    with st.expander("📖 参考来源"):
                        for i, source in enumerate(message["sources"], 1):
                            st.markdown(f"""
                            **来源 {i}**: {source['source']['filename']}  
                            **相似度**: {source['similarity_score']:.3f}  
                            **内容预览**: {source['content'][:200]}...
                            """)
        
        # 聊天输入
        if prompt := st.chat_input("请输入您的问题..."):
            # 添加用户消息
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # 生成助手回复
            with st.chat_message("assistant"):
                with st.spinner("正在思考..."):
                    # 使用对话历史进行查询
                    result = self.rag.chat_with_context(st.session_state.messages)
                
                if result["success"]:
                    response = result["response"]
                    st.markdown(response)
                    
                    # 添加助手消息到历史
                    assistant_message = {
                        "role": "assistant", 
                        "content": response
                    }
                    
                    # 添加来源信息
                    if result.get("retrieved_documents"):
                        assistant_message["sources"] = result["retrieved_documents"]
                        
                        with st.expander("📖 参考来源"):
                            for i, doc in enumerate(result["retrieved_documents"], 1):
                                st.markdown(f"""
                                **来源 {i}**: {doc['source']['filename']}  
                                **相似度**: {doc['similarity_score']:.3f}  
                                **内容**: {doc['content'][:300]}...
                                """)
                    
                    st.session_state.messages.append(assistant_message)
                else:
                    st.error("抱歉，处理您的问题时出现错误。")
        
        # 清空对话按钮
        if st.button("清空对话历史", key="clear_chat"):
            st.session_state.messages = []
            st.rerun()
    
    def _render_document_browser(self):
        """渲染文档浏览器"""
        st.markdown("## 📚 文档浏览")
        
        # 这里可以添加文档浏览功能
        st.info("文档浏览功能正在开发中...")
        
        # 显示当前知识库状态
        if st.button("查看知识库状态", key="view_kb_status"):
            result = self.rag.get_knowledge_base_stats()
            if result["success"]:
                stats = result["statistics"]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("文档块总数", stats.get("total_chunks", 0))
                with col2:
                    st.metric("文档数量", stats.get("unique_documents", 0))
                with col3:
                    st.metric("集合名称", stats.get("collection_name", "N/A"))
    
    def _render_system_monitor(self):
        """渲染系统监控"""
        st.markdown("## 📈 系统监控")
        
        # 系统信息
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 💻 系统资源")
            if st.button("刷新系统信息", key="refresh_system_info"):
                system_info = get_system_info()
                
                st.metric("CPU使用率", f"{system_info['cpu_percent']:.1f}%")
                st.metric("内存使用率", f"{system_info['memory_percent']:.1f}%")
                st.metric("可用内存", f"{system_info['memory_available']:.1f} GB")
                st.metric("磁盘使用率", f"{system_info['disk_usage']['percent']:.1f}%")
        
        with col2:
            st.markdown("### 🔧 系统组件")
            
            # 显示当前配置
            st.markdown("**当前LLM模型**: " + self.rag.llm.model_name)
            st.markdown("**嵌入模型**: " + self.rag.vector_store.embedding_model_name)
            st.markdown("**向量存储**: ChromaDB")
            st.markdown("**持久化目录**: " + str(self.rag.vector_store.persist_directory))
    
    def _process_uploaded_files(self, uploaded_files: List):
        """处理上传的文件"""
        if not uploaded_files:
            return
        
        # 保存上传的文件到临时目录
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        
        file_paths = []
        file_info = []
        
        for uploaded_file in uploaded_files:
            # 保存文件
            file_path = temp_dir / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            file_paths.append(file_path)
            file_info.append({
                "name": uploaded_file.name,
                "size": format_file_size(uploaded_file.size),
                "type": uploaded_file.type
            })
        
        # 显示上传文件信息
        st.markdown("### 📁 待处理文件")
        for info in file_info:
            st.markdown(f"- **{info['name']}** ({info['size']}) - {info['type']}")
        
        # 处理文件
        with st.spinner("正在处理文档并添加到知识库..."):
            result = self.rag.add_documents_to_knowledge_base(file_paths)
        
        # 显示结果
        if result["success"]:
            st.success(f"""
            ✅ 文档添加完成！
            
            - 成功处理：{result['successful_documents']} 个文档
            - 生成文本块：{result['added_chunks']} 个
            - 知识库总大小：{result['collection_size']} 个文本块
            """)
            
            if result.get("failed_documents", 0) > 0:
                st.warning(f"⚠️ {result['failed_documents']} 个文档处理失败")
                if "failed_files" in result:
                    st.text("失败文件列表：")
                    for failed_file in result["failed_files"]:
                        st.text(f"- {failed_file}")
        else:
            st.error(f"❌ 文档添加失败：{result['message']}")
        
        # 清理临时文件
        for file_path in file_paths:
            try:
                file_path.unlink()
            except Exception:
                pass
        
        # 刷新知识库统计
        st.session_state.knowledge_base_stats = None


def main():
    """主函数"""
    try:
        # 设置日志
        config_manager.setup_logging()
        
        # 创建并运行应用
        app = RAGApp()
        app.run()
        
    except Exception as e:
        st.error(f"应用启动失败: {e}")
        logger.error(f"应用启动失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()