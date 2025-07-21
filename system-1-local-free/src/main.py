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
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag_pipeline import rag_pipeline
from utils.config import config_manager
from utils.helpers import format_file_size, get_system_info

# 配置页面
st.set_page_config(
    page_title="企业RAG知识问答系统",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None  # 移除所有菜单项，包括部署图标
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
        /* 彻底隐藏所有Deploy相关元素 */
        .stDeployButton {
            display: none !important;
        }
        
        [data-testid="stToolbar"] {
            display: none !important;
        }
        
        [data-testid="stDecoration"] {
            display: none !important;
        }
        
        .stActionButton {
            display: none !important;
        }
        
        /* 隐藏应用工具栏 */
        .stAppToolbar {
            display: none !important;
        }
        
        [data-testid="stAppViewContainer"] > .main > .block-container > .stToolbar {
            display: none !important;
        }
        
        /* 隐藏所有工具栏相关元素 */
        .toolbar {
            display: none !important;
        }
        
        /* 隐藏右上角的所有按钮 */
        .stApp > header {
            display: none !important;
        }
        
        /* 隐藏Streamlit标识和品牌 */
        .stApp > .stAppHeader {
            display: none !important;
        }
        
        /* 隐藏右上角菜单按钮 */
        #MainMenu {
            visibility: hidden !important;
            display: none !important;
        }
        
        /* 隐藏页脚 */
        footer {
            visibility: hidden !important;
            display: none !important;
        }
        
        /* 隐藏Streamlit水印 */
        .viewerBadge_container__1QSob {
            display: none !important;
        }
        
        /* 隐藏右上角设置按钮 */
        [data-testid="stSettingsButton"] {
            display: none !important;
        }
        
        /* 隐藏右上角部署相关的所有元素 */
        [aria-label*="Deploy"] {
            display: none !important;
        }
        
        /* 隐藏应用顶部栏 */
        .stApp > .stAppHeader,
        .stApp > header,
        .stAppHeader {
            display: none !important;
        }
        
        /* 确保主内容占满整个视窗 */
        .stApp {
            top: 0 !important;
            padding-top: 0 !important;
        }
        
        /* 隐藏任何可能的浮动工具栏 */
        .stFloatingActionButton {
            display: none !important;
        }
        
        /* 隐藏GitHub图标和Fork按钮 */
        .stApp [data-testid="stImage"] img[alt="GitHub"] {
            display: none !important;
        }
        
        /* 隐藏"Made with Streamlit"文字 */
        .stApp > footer,
        .stApp [class*="footer"] {
            display: none !important;
        }
        
        /* 隐藏任何带有"deploy"文字的元素 */
        *[class*="deploy"],
        *[id*="deploy"] {
            display: none !important;
        }
        
        /* 清理页面边距，让内容更紧凑 */
        .stApp > .main {
            padding-top: 1rem !important;
        }
        
        /* 隐藏可能的应用图标 */
        .stApp [data-testid="stAppViewBlockContainer"] header {
            display: none !important;
        }
        
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
            # 显示Loading界面
            loading_placeholder = st.empty()
            with loading_placeholder.container():
                st.markdown("""
                <div style="text-align: center; padding: 20px;">
                    <div style="font-size: 32px; margin-bottom: 15px;">🔄</div>
                    <div style="font-size: 18px; font-weight: bold; color: #1f77b4;">Loading...</div>
                    <div style="font-size: 14px; margin-top: 8px; color: #666;">正在检查系统状态...</div>
                </div>
                """, unsafe_allow_html=True)
            
            # 执行健康检查
            st.session_state.system_health = self.rag.health_check()
            
            # 清除Loading界面
            loading_placeholder.empty()
        
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
        
        # 获取知识库统计信息
        if st.button("刷新文档列表", key="refresh_doc_list"):
            with st.spinner("正在加载文档列表..."):
                result = self.rag.get_knowledge_base_stats()
                if result["success"]:
                    st.session_state.doc_browser_stats = result["statistics"]
        
        # 显示知识库概览
        if hasattr(st.session_state, 'doc_browser_stats') and st.session_state.doc_browser_stats:
            stats = st.session_state.doc_browser_stats
            
            # 统计信息展示
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 文档总数", stats.get("unique_documents", 0))
            with col2:
                st.metric("📝 文档块数", stats.get("total_chunks", 0))
            with col3:
                st.metric("🗂️ 集合名称", stats.get("collection_name", "N/A"))
            with col4:
                if stats.get("total_chunks", 0) > 0:
                    avg_chunks = stats.get("total_chunks", 0) / max(stats.get("unique_documents", 1), 1)
                    st.metric("📊 平均块数", f"{avg_chunks:.1f}")
                else:
                    st.metric("📊 平均块数", "0")
            
            st.markdown("---")
            
            # 文件类型分布
            if "file_types" in stats and stats["file_types"]:
                st.markdown("### 📂 文件类型分布")
                file_types = stats["file_types"]
                
                # 创建文件类型展示
                type_cols = st.columns(min(len(file_types), 4))
                for i, (file_type, count) in enumerate(file_types.items()):
                    with type_cols[i % len(type_cols)]:
                        # 根据文件类型显示不同图标
                        icon = "📄"
                        if file_type.lower() == "pdf":
                            icon = "📕"
                        elif file_type.lower() in ["doc", "docx"]:
                            icon = "📘"
                        elif file_type.lower() == "txt":
                            icon = "📄"
                        elif file_type.lower() == "md":
                            icon = "📝"
                        
                        st.metric(f"{icon} {file_type.upper()}", f"{count} 个")
                
                st.markdown("---")
            
            # 文档操作区域
            st.markdown("### 🛠️ 文档管理操作")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 检索测试", key="test_retrieval"):
                    st.session_state.show_retrieval_test = True
            
            with col2:
                if st.button("📊 详细统计", key="detailed_stats"):
                    st.session_state.show_detailed_stats = True
            
            # 检索测试功能
            if hasattr(st.session_state, 'show_retrieval_test') and st.session_state.show_retrieval_test:
                st.markdown("#### 🔍 文档检索测试")
                test_query = st.text_input("输入测试查询：", placeholder="例如：企业管理制度")
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("开始检索", key="start_retrieval"):
                        if test_query:
                            with st.spinner("正在检索相关文档..."):
                                # 调用RAG的检索功能
                                result = self.rag.query_knowledge_base(test_query, include_source_info=True)
                                if result["success"] and result.get("retrieved_documents"):
                                    st.success(f"找到 {len(result['retrieved_documents'])} 个相关文档块")
                                    
                                    for i, doc in enumerate(result["retrieved_documents"], 1):
                                        with st.expander(f"文档片段 {i} (相似度: {doc['similarity_score']:.3f})"):
                                            st.markdown(f"**文件名**: {doc['source']['filename']}")
                                            st.markdown(f"**内容预览**:")
                                            st.text(doc['content'][:300] + "..." if len(doc['content']) > 300 else doc['content'])
                                else:
                                    st.warning("未找到相关文档")
                        else:
                            st.warning("请输入查询内容")
                
                with col2:
                    if st.button("关闭测试", key="close_retrieval_test"):
                        st.session_state.show_retrieval_test = False
                        st.rerun()
            
            # 详细统计信息
            if hasattr(st.session_state, 'show_detailed_stats') and st.session_state.show_detailed_stats:
                st.markdown("#### 📊 详细统计信息")
                
                # 显示完整的统计信息
                st.json(stats)
                
                if st.button("关闭详细统计", key="close_detailed_stats"):
                    st.session_state.show_detailed_stats = False
                    st.rerun()
            
        else:
            # 首次访问或无数据时的界面
            st.info("💡 点击\"刷新文档列表\"查看已上传的文档")
            
            # 显示简单的知识库状态
            if st.button("查看知识库状态", key="view_kb_status_simple"):
                with st.spinner("正在检查知识库状态..."):
                    result = self.rag.get_knowledge_base_stats()
                    if result["success"]:
                        stats = result["statistics"]
                        if stats.get("total_chunks", 0) > 0:
                            st.success(f"知识库中有 {stats.get('unique_documents', 0)} 个文档，共 {stats.get('total_chunks', 0)} 个文档块")
                        else:
                            st.warning("知识库为空，请先上传文档")
                    else:
                        st.error("无法获取知识库状态")
    
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
        
        # 处理文件 - 添加详细的Loading界面
        # 创建进度容器
        progress_container = st.container()
        
        with progress_container:
            # 显示Loading动画
            st.markdown("""
            <div style="text-align: center; padding: 30px;">
                <div style="font-size: 48px; margin-bottom: 20px;">⏳</div>
                <div style="font-size: 24px; font-weight: bold; color: #1f77b4;">Loading...</div>
                <div style="font-size: 16px; margin-top: 10px; color: #666;">正在处理文档并添加到知识库，请耐心等待...</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 进度条
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 更新进度
            status_text.text("🔄 正在初始化处理流程...")
            progress_bar.progress(10)
            time.sleep(0.5)
            
            status_text.text("📄 正在提取文档内容...")
            progress_bar.progress(30)
            time.sleep(0.5)
            
            status_text.text("🧠 正在生成向量嵌入...")
            progress_bar.progress(60)
            
            # 执行实际处理
            result = self.rag.add_documents_to_knowledge_base(file_paths)
            
            status_text.text("💾 正在保存到向量数据库...")
            progress_bar.progress(90)
            time.sleep(0.5)
            
            status_text.text("✅ 处理完成!")
            progress_bar.progress(100)
            time.sleep(0.5)
            
            # 清除进度显示
            progress_container.empty()
        
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