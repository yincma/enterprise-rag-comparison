"""
配置管理模块
负责加载和管理系统配置
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录路径
        """
        if config_dir is None:
            # 默认配置目录
            self.config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)
        
        self._app_config = None
        self._model_config = None
        
    def load_app_config(self) -> Dict[str, Any]:
        """加载应用配置"""
        if self._app_config is None:
            config_file = self.config_dir / "app_config.yaml"
            self._app_config = self._load_yaml_config(config_file)
        return self._app_config
    
    def load_model_config(self) -> Dict[str, Any]:
        """加载模型配置"""
        if self._model_config is None:
            config_file = self.config_dir / "model_config.yaml"
            self._model_config = self._load_yaml_config(config_file)
        return self._model_config
    
    def _load_yaml_config(self, config_file: Path) -> Dict[str, Any]:
        """
        加载YAML配置文件
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            配置字典
        """
        try:
            if not config_file.exists():
                logger.warning(f"配置文件不存在: {config_file}")
                return {}
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"成功加载配置文件: {config_file}")
                return config or {}
                
        except Exception as e:
            logger.error(f"加载配置文件失败: {config_file}, 错误: {e}")
            return {}
    
    def get_app_setting(self, key_path: str, default: Any = None) -> Any:
        """
        获取应用配置项
        
        Args:
            key_path: 配置项路径，如 'app.name' 或 'ui.theme.primary_color'
            default: 默认值
            
        Returns:
            配置值
        """
        config = self.load_app_config()
        return self._get_nested_value(config, key_path, default)
    
    def get_model_setting(self, key_path: str, default: Any = None) -> Any:
        """
        获取模型配置项
        
        Args:
            key_path: 配置项路径
            default: 默认值
            
        Returns:
            配置值
        """
        config = self.load_model_config()
        return self._get_nested_value(config, key_path, default)
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str, default: Any = None) -> Any:
        """
        获取嵌套字典中的值
        
        Args:
            data: 数据字典
            key_path: 键路径，如 'a.b.c'
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key_path.split('.')
        value = data
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            logger.debug(f"配置项未找到: {key_path}，使用默认值: {default}")
            return default
    
    def get_data_dir(self) -> Path:
        """获取数据目录路径"""
        data_dir = Path(self.get_app_setting('vector_store.persist_directory', './data'))
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    
    def get_log_dir(self) -> Path:
        """获取日志目录路径"""
        log_dir = Path(self.get_app_setting('logging.log_directory', './logs'))
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    
    def setup_logging(self) -> None:
        """设置日志配置"""
        log_config = self.load_app_config().get('logging', {})
        
        # 创建日志目录
        log_dir = self.get_log_dir()
        
        # 设置日志级别
        log_level = log_config.get('log_level', 'INFO')
        
        # 配置日志格式
        log_format = '%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s'
        
        # 配置根日志器
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            handlers=[
                logging.FileHandler(log_dir / log_config.get('log_file', 'app.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logger.info("日志系统初始化完成")


# 全局配置管理器实例
config_manager = ConfigManager()