"""
LLM管理模块
基于Ollama实现本地大语言模型管理和调用
"""

import logging
from typing import Dict, Any, List, Optional, Union, Generator
import json
import time

# Ollama Python客户端
import ollama
from ollama import Client

# 本地模块
from .utils.config import config_manager
from .utils.helpers import measure_performance, Timer, retry_on_failure

logger = logging.getLogger(__name__)

class LLMManager:
    """LLM管理器"""
    
    def __init__(self):
        """初始化LLM管理器"""
        self.config = config_manager.load_model_config()
        self.llm_config = self.config.get('llm', {})
        
        # Ollama配置
        self.base_url = self.llm_config.get('base_url', 'http://localhost:11434')
        self.model_name = self.llm_config.get('model_name', 'llama3.1:8b')
        self.timeout = self.llm_config.get('timeout', 300)
        
        # 生成参数
        self.generation_params = {
            'temperature': self.llm_config.get('temperature', 0.1),
            'top_p': self.llm_config.get('top_p', 0.9),
            'top_k': self.llm_config.get('top_k', 40),
            'max_tokens': self.llm_config.get('max_tokens', 2000),
            'repeat_penalty': self.llm_config.get('repeat_penalty', 1.1),
            'stop': self.llm_config.get('stop_sequences', [])
        }
        
        # 系统提示词
        self.system_prompt = self.llm_config.get('system_prompt', self._get_default_system_prompt())
        
        # 初始化Ollama客户端
        self._init_ollama_client()
        
        # 验证模型可用性
        self._validate_model()
        
        logger.info(f"LLM管理器初始化完成，模型: {self.model_name}")
    
    def _init_ollama_client(self):
        """初始化Ollama客户端"""
        try:
            self.client = Client(host=self.base_url)
            logger.info(f"Ollama客户端初始化成功: {self.base_url}")
        except Exception as e:
            logger.error(f"Ollama客户端初始化失败: {e}")
            raise
    
    def _validate_model(self):
        """验证模型是否可用"""
        try:
            # 检查模型是否已下载
            models = self.list_available_models()
            model_names = [model['name'] for model in models]
            
            if self.model_name not in model_names:
                logger.warning(f"模型 {self.model_name} 未找到，可用模型: {model_names}")
                
                # 尝试拉取模型
                logger.info(f"尝试下载模型: {self.model_name}")
                self.pull_model(self.model_name)
            
            # 进行简单测试
            test_response = self.generate_response("Hello, are you working?", max_tokens=10)
            if test_response:
                logger.info("模型验证成功")
            else:
                logger.warning("模型验证失败，但继续运行")
                
        except Exception as e:
            logger.error(f"模型验证失败: {e}")
            # 不抛出异常，允许系统继续运行
    
    @measure_performance
    @retry_on_failure(max_retries=3)
    def generate_response(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Union[str, Generator[str, None, None]]:
        """
        生成回应
        
        Args:
            prompt: 用户提示词
            context: 上下文信息
            temperature: 温度参数
            max_tokens: 最大生成长度
            stream: 是否流式输出
            
        Returns:
            生成的回应文本或生成器
        """
        try:
            # 构建完整的提示词
            full_prompt = self._build_prompt(prompt, context)
            
            # 准备生成参数
            generation_options = self.generation_params.copy()
            if temperature is not None:
                generation_options['temperature'] = temperature
            if max_tokens is not None:
                generation_options['num_predict'] = max_tokens
            
            with Timer("LLM推理"):
                if stream:
                    return self._generate_streaming(full_prompt, generation_options)
                else:
                    return self._generate_non_streaming(full_prompt, generation_options)
        
        except Exception as e:
            logger.error(f"生成回应失败: {e}")
            return "抱歉，我无法处理您的请求。请稍后再试。"
    
    def _generate_non_streaming(self, prompt: str, options: Dict[str, Any]) -> str:
        """非流式生成"""
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                system=self.system_prompt,
                options=options,
                stream=False
            )
            
            generated_text = response.get('response', '').strip()
            
            # 记录生成统计信息
            if 'eval_count' in response:
                tokens_generated = response.get('eval_count', 0)
                eval_duration = response.get('eval_duration', 0)
                if eval_duration > 0:
                    tokens_per_second = tokens_generated / (eval_duration / 1e9)
                    logger.info(f"生成统计: {tokens_generated} tokens, {tokens_per_second:.2f} tokens/秒")
            
            return generated_text
        
        except Exception as e:
            logger.error(f"非流式生成失败: {e}")
            raise
    
    def _generate_streaming(self, prompt: str, options: Dict[str, Any]) -> Generator[str, None, None]:
        """流式生成"""
        try:
            stream = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                system=self.system_prompt,
                options=options,
                stream=True
            )
            
            for chunk in stream:
                if 'response' in chunk:
                    yield chunk['response']
        
        except Exception as e:
            logger.error(f"流式生成失败: {e}")
            yield "生成过程中出现错误"
    
    def _build_prompt(self, user_prompt: str, context: Optional[str] = None) -> str:
        """
        构建完整提示词
        
        Args:
            user_prompt: 用户提示词
            context: 上下文信息
            
        Returns:
            完整提示词
        """
        # 获取提示词模板配置
        prompts_config = self.config.get('prompts', {})
        
        if context:
            # 使用问答模板
            template = prompts_config.get('qa_template', '''基于以下上下文信息，回答用户的问题。如果上下文中没有相关信息，请明确说明无法从提供的文档中找到答案。

上下文信息：
{context}

用户问题：{question}

请提供准确、详细的答案：''')
            
            return template.format(context=context, question=user_prompt)
        else:
            # 直接使用用户提示词
            return user_prompt
    
    @measure_performance
    def chat_with_history(
        self, 
        messages: List[Dict[str, str]], 
        context: Optional[str] = None
    ) -> str:
        """
        带历史记录的对话
        
        Args:
            messages: 历史消息列表 [{"role": "user/assistant", "content": "..."}]
            context: 文档上下文
            
        Returns:
            助手回应
        """
        try:
            # 构建对话历史
            chat_history = self._format_chat_history(messages)
            
            # 获取最新的用户问题
            latest_message = messages[-1]['content'] if messages else ""
            
            # 构建完整提示词
            prompts_config = self.config.get('prompts', {})
            template = prompts_config.get('chat_template', '''你是一个专业的企业知识助手。以下是历史对话和相关文档上下文。

历史对话：
{chat_history}

相关文档：
{context}

当前问题：{question}

请基于上下文和历史对话提供有帮助的回答：''')
            
            full_prompt = template.format(
                chat_history=chat_history,
                context=context or "无相关文档",
                question=latest_message
            )
            
            return self.generate_response(full_prompt)
        
        except Exception as e:
            logger.error(f"历史对话生成失败: {e}")
            return "对话处理出现错误，请稍后再试。"
    
    def _format_chat_history(self, messages: List[Dict[str, str]]) -> str:
        """格式化对话历史"""
        formatted_history = []
        
        for message in messages[:-1]:  # 排除最新消息
            role = message.get('role', 'user')
            content = message.get('content', '').strip()
            
            if role == 'user':
                formatted_history.append(f"用户：{content}")
            elif role == 'assistant':
                formatted_history.append(f"助手：{content}")
        
        return "\n".join(formatted_history) if formatted_history else "无历史对话"
    
    def summarize_text(self, text: str, max_length: Optional[int] = None) -> str:
        """
        文本摘要
        
        Args:
            text: 要摘要的文本
            max_length: 最大摘要长度
            
        Returns:
            摘要文本
        """
        try:
            prompts_config = self.config.get('prompts', {})
            template = prompts_config.get('summarize_template', '''请对以下文档内容进行简洁的总结：

文档内容：
{text}

总结要点：''')
            
            prompt = template.format(text=text)
            
            # 调整生成参数以适合摘要任务
            return self.generate_response(
                prompt,
                temperature=0.3,  # 较低的温度以提高一致性
                max_tokens=max_length or 500
            )
        
        except Exception as e:
            logger.error(f"文本摘要失败: {e}")
            return "摘要生成失败"
    
    def list_available_models(self) -> List[Dict[str, Any]]:
        """
        列出可用模型
        
        Returns:
            模型列表
        """
        try:
            models_response = self.client.list()
            models = models_response.get('models', [])
            
            formatted_models = []
            for model in models:
                formatted_models.append({
                    'name': model.get('name', ''),
                    'size': model.get('size', 0),
                    'modified_at': model.get('modified_at', ''),
                    'digest': model.get('digest', ''),
                    'family': model.get('details', {}).get('family', ''),
                    'format': model.get('details', {}).get('format', ''),
                    'parameter_size': model.get('details', {}).get('parameter_size', '')
                })
            
            return formatted_models
        
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []
    
    def pull_model(self, model_name: str) -> bool:
        """
        下载模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            是否下载成功
        """
        try:
            logger.info(f"开始下载模型: {model_name}")
            
            # 流式下载，显示进度
            stream = self.client.pull(model_name, stream=True)
            
            for chunk in stream:
                if 'status' in chunk:
                    status = chunk['status']
                    if 'completed' in chunk and 'total' in chunk:
                        completed = chunk['completed']
                        total = chunk['total']
                        percentage = (completed / total) * 100
                        logger.info(f"下载进度: {status} {percentage:.1f}%")
                    else:
                        logger.info(f"下载状态: {status}")
            
            logger.info(f"模型下载完成: {model_name}")
            return True
        
        except Exception as e:
            logger.error(f"模型下载失败: {model_name}, 错误: {e}")
            return False
    
    def delete_model(self, model_name: str) -> bool:
        """
        删除模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            是否删除成功
        """
        try:
            self.client.delete(model_name)
            logger.info(f"模型删除成功: {model_name}")
            return True
        
        except Exception as e:
            logger.error(f"模型删除失败: {model_name}, 错误: {e}")
            return False
    
    def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取模型信息
        
        Args:
            model_name: 模型名称，默认使用当前模型
            
        Returns:
            模型信息字典
        """
        target_model = model_name or self.model_name
        
        try:
            response = self.client.show(target_model)
            return {
                'name': target_model,
                'modelfile': response.get('modelfile', ''),
                'parameters': response.get('parameters', ''),
                'template': response.get('template', ''),
                'details': response.get('details', {}),
                'model_info': response.get('model_info', {})
            }
        
        except Exception as e:
            logger.error(f"获取模型信息失败: {target_model}, 错误: {e}")
            return {'error': str(e)}
    
    def update_model_config(
        self, 
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        更新模型配置
        
        Args:
            model_name: 新的模型名称
            temperature: 新的温度参数
            max_tokens: 新的最大生成长度
            **kwargs: 其他参数
        """
        if model_name:
            self.model_name = model_name
            logger.info(f"模型已切换为: {model_name}")
        
        if temperature is not None:
            self.generation_params['temperature'] = temperature
            logger.info(f"温度参数已更新为: {temperature}")
        
        if max_tokens is not None:
            self.generation_params['max_tokens'] = max_tokens
            logger.info(f"最大生成长度已更新为: {max_tokens}")
        
        # 更新其他参数
        for key, value in kwargs.items():
            if key in self.generation_params:
                self.generation_params[key] = value
                logger.info(f"参数 {key} 已更新为: {value}")
    
    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词"""
        return """你是一个专业的企业知识助手，基于提供的文档内容回答用户问题。
请遵循以下原则：
1. 只基于提供的上下文信息回答问题
2. 如果文档中没有相关信息，请明确说明
3. 回答要准确、简洁、有条理
4. 使用中文回答
5. 可以适当引用文档中的具体内容"""


# 全局LLM管理器实例
llm_manager = LLMManager()