"""
配置管理模块单元测试
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from utils.config import ConfigManager

class TestConfigManager:
    """配置管理器测试类"""
    
    def test_init_with_default_config_dir(self):
        """测试默认配置目录初始化"""
        config_manager = ConfigManager()
        assert config_manager.config_dir is not None
        assert config_manager.config_dir.name == "config"
    
    def test_init_with_custom_config_dir(self, temp_dir):
        """测试自定义配置目录初始化"""
        custom_dir = temp_dir / "custom_config"
        custom_dir.mkdir()
        
        config_manager = ConfigManager(str(custom_dir))
        assert config_manager.config_dir == custom_dir
    
    def test_load_app_config_success(self, test_config_dir):
        """测试成功加载应用配置"""
        config_manager = ConfigManager(str(test_config_dir))
        config = config_manager.load_app_config()
        
        assert config is not None
        assert "app" in config
        assert config["app"]["name"] == "测试RAG系统"
        assert config["app"]["version"] == "1.0.0"
    
    def test_load_model_config_success(self, test_config_dir):
        """测试成功加载模型配置"""
        config_manager = ConfigManager(str(test_config_dir))
        config = config_manager.load_model_config()
        
        assert config is not None
        assert "llm" in config
        assert config["llm"]["model_name"] == "test-model"
        assert config["embedding"]["dimension"] == 384
    
    def test_load_nonexistent_config_file(self, temp_dir):
        """测试加载不存在的配置文件"""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        
        config_manager = ConfigManager(str(empty_dir))
        config = config_manager.load_app_config()
        
        assert config == {}
    
    def test_get_app_setting_success(self, test_config_dir):
        """测试成功获取应用设置"""
        config_manager = ConfigManager(str(test_config_dir))
        
        # 测试简单键
        app_name = config_manager.get_app_setting("app.name")
        assert app_name == "测试RAG系统"
        
        # 测试嵌套键
        chunk_size = config_manager.get_app_setting("vector_store.chunk_size")
        assert chunk_size == 500
        
        # 测试默认值
        nonexistent = config_manager.get_app_setting("nonexistent.key", "default")
        assert nonexistent == "default"
    
    def test_get_model_setting_success(self, test_config_dir):
        """测试成功获取模型设置"""
        config_manager = ConfigManager(str(test_config_dir))
        
        temperature = config_manager.get_model_setting("llm.temperature")
        assert temperature == 0.1
        
        embedding_dim = config_manager.get_model_setting("embedding.dimension")
        assert embedding_dim == 384
    
    def test_get_nested_value_deep_nesting(self, test_config_dir):
        """测试深层嵌套值获取"""
        config_manager = ConfigManager(str(test_config_dir))
        
        # 添加深层嵌套测试数据
        test_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep_value"
                    }
                }
            }
        }
        
        result = config_manager._get_nested_value(test_data, "level1.level2.level3.value")
        assert result == "deep_value"
        
        # 测试不存在的路径
        result = config_manager._get_nested_value(test_data, "level1.nonexistent.value", "default")
        assert result == "default"
    
    def test_get_data_dir(self, test_config_dir):
        """测试获取数据目录"""
        config_manager = ConfigManager(str(test_config_dir))
        data_dir = config_manager.get_data_dir()
        
        assert data_dir is not None
        assert data_dir.exists()
        assert data_dir.is_dir()
    
    def test_get_log_dir(self, test_config_dir):
        """测试获取日志目录"""
        config_manager = ConfigManager(str(test_config_dir))
        log_dir = config_manager.get_log_dir()
        
        assert log_dir is not None
        assert log_dir.exists()
        assert log_dir.is_dir()
    
    def test_yaml_config_caching(self, test_config_dir):
        """测试配置缓存机制"""
        config_manager = ConfigManager(str(test_config_dir))
        
        # 第一次加载
        config1 = config_manager.load_app_config()
        
        # 第二次加载应该使用缓存
        config2 = config_manager.load_app_config()
        
        assert config1 is config2  # 应该是同一个对象引用
    
    def test_invalid_yaml_file(self, temp_dir):
        """测试无效YAML文件处理"""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        
        # 创建无效的YAML文件
        invalid_yaml = config_dir / "app_config.yaml"
        invalid_yaml.write_text("invalid: yaml: content: [", encoding="utf-8")
        
        config_manager = ConfigManager(str(config_dir))
        config = config_manager.load_app_config()
        
        assert config == {}  # 应该返回空字典而不是抛出异常
    
    def test_setup_logging(self, test_config_dir):
        """测试日志设置"""
        config_manager = ConfigManager(str(test_config_dir))
        
        # 测试不会抛出异常
        try:
            config_manager.setup_logging()
            success = True
        except Exception:
            success = False
        
        assert success
        
        # 检查日志目录是否创建
        log_dir = config_manager.get_log_dir()
        assert log_dir.exists()

@pytest.mark.config
class TestConfigIntegration:
    """配置管理集成测试"""
    
    def test_full_config_workflow(self, test_config_dir):
        """测试完整配置工作流程"""
        config_manager = ConfigManager(str(test_config_dir))
        
        # 1. 加载配置
        app_config = config_manager.load_app_config()
        model_config = config_manager.load_model_config()
        
        assert app_config is not None
        assert model_config is not None
        
        # 2. 获取设置
        app_name = config_manager.get_app_setting("app.name")
        model_name = config_manager.get_model_setting("llm.model_name")
        
        assert app_name == "测试RAG系统"
        assert model_name == "test-model"
        
        # 3. 创建目录
        data_dir = config_manager.get_data_dir()
        log_dir = config_manager.get_log_dir()
        
        assert data_dir.exists()
        assert log_dir.exists()
        
        # 4. 设置日志
        config_manager.setup_logging()
    
    def test_config_error_handling(self, temp_dir):
        """测试配置错误处理"""
        # 创建空的配置目录
        empty_config_dir = temp_dir / "empty_config"
        empty_config_dir.mkdir()
        
        config_manager = ConfigManager(str(empty_config_dir))
        
        # 应该能正常处理缺失的配置文件
        app_config = config_manager.load_app_config()
        model_config = config_manager.load_model_config()
        
        assert app_config == {}
        assert model_config == {}
        
        # 使用默认值应该正常工作
        default_value = config_manager.get_app_setting("nonexistent.key", "default")
        assert default_value == "default"