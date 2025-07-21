"""
系统弹性和错误恢复模块
提供自动重试、降级、熔断等机制
"""

import logging
import time
import threading
from typing import Dict, Any, Callable, Optional, List, Union
from functools import wraps
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    FAILING = "failing"
    UNAVAILABLE = "unavailable"

class CircuitBreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态

class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: tuple = (Exception,)
    ):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 失败阈值
            timeout: 熔断超时时间（秒）
            expected_exception: 预期异常类型
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self._lock = threading.Lock()
    
    def __call__(self, func):
        """装饰器实现"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self._lock:
                # 检查是否可以执行
                if self.state == CircuitBreakerState.OPEN:
                    if self._should_attempt_reset():
                        self.state = CircuitBreakerState.HALF_OPEN
                    else:
                        raise Exception(f"熔断器开启，服务不可用")
                
                try:
                    result = func(*args, **kwargs)
                    self._on_success()
                    return result
                except self.expected_exception as e:
                    self._on_failure()
                    raise e
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置"""
        return (time.time() - self.last_failure_time) >= self.timeout
    
    def _on_success(self):
        """成功时的处理"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        """失败时的处理"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"熔断器开启，失败次数: {self.failure_count}")

class RetryStrategy:
    """重试策略"""
    
    @staticmethod
    def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """指数退避策略"""
        delay = base_delay * (2 ** attempt)
        return min(delay, max_delay)
    
    @staticmethod
    def linear_backoff(attempt: int, base_delay: float = 1.0, increment: float = 1.0) -> float:
        """线性退避策略"""
        return base_delay + (attempt * increment)
    
    @staticmethod
    def fixed_delay(attempt: int, delay: float = 1.0) -> float:
        """固定延迟策略"""
        return delay

class AdvancedRetry:
    """高级重试装饰器"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay_strategy: Callable[[int], float] = RetryStrategy.exponential_backoff,
        exceptions: tuple = (Exception,),
        on_retry: Optional[Callable] = None,
        on_failure: Optional[Callable] = None,
        jitter: bool = True
    ):
        """
        初始化重试装饰器
        
        Args:
            max_attempts: 最大尝试次数
            delay_strategy: 延迟策略函数
            exceptions: 需要重试的异常类型
            on_retry: 重试时的回调函数
            on_failure: 最终失败时的回调函数
            jitter: 是否添加随机抖动
        """
        self.max_attempts = max_attempts
        self.delay_strategy = delay_strategy
        self.exceptions = exceptions
        self.on_retry = on_retry
        self.on_failure = on_failure
        self.jitter = jitter
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_attempts):
                try:
                    return func(*args, **kwargs)
                except self.exceptions as e:
                    last_exception = e
                    
                    if attempt == self.max_attempts - 1:
                        # 最后一次尝试失败
                        if self.on_failure:
                            self.on_failure(func.__name__, attempt + 1, e)
                        logger.error(f"函数 {func.__name__} 经过 {self.max_attempts} 次尝试后最终失败: {e}")
                        raise e
                    
                    # 计算延迟时间
                    delay = self.delay_strategy(attempt)
                    if self.jitter:
                        import random
                        delay *= (0.5 + random.random())  # 添加50%-150%的随机抖动
                    
                    # 调用重试回调
                    if self.on_retry:
                        self.on_retry(func.__name__, attempt + 1, e, delay)
                    
                    logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，{delay:.2f}秒后重试")
                    time.sleep(delay)
            
            # 这行代码实际不会执行，但为了类型检查
            raise last_exception
        
        return wrapper

class ServiceHealthChecker:
    """服务健康检查器"""
    
    def __init__(self):
        self.service_status: Dict[str, ServiceStatus] = {}
        self.last_check_time: Dict[str, float] = {}
        self.failure_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def register_service(self, service_name: str, health_check_func: Callable[[], bool]):
        """注册服务健康检查"""
        with self._lock:
            self.service_status[service_name] = ServiceStatus.HEALTHY
            self.last_check_time[service_name] = time.time()
            self.failure_counts[service_name] = 0
    
    def check_service_health(self, service_name: str, health_check_func: Callable[[], bool]) -> ServiceStatus:
        """检查服务健康状态"""
        try:
            is_healthy = health_check_func()
            
            with self._lock:
                if is_healthy:
                    self.service_status[service_name] = ServiceStatus.HEALTHY
                    self.failure_counts[service_name] = 0
                else:
                    self._handle_service_failure(service_name)
                
                self.last_check_time[service_name] = time.time()
                return self.service_status[service_name]
        
        except Exception as e:
            logger.error(f"服务 {service_name} 健康检查失败: {e}")
            with self._lock:
                self._handle_service_failure(service_name)
                return self.service_status[service_name]
    
    def _handle_service_failure(self, service_name: str):
        """处理服务失败"""
        self.failure_counts[service_name] += 1
        failure_count = self.failure_counts[service_name]
        
        if failure_count >= 5:
            self.service_status[service_name] = ServiceStatus.UNAVAILABLE
        elif failure_count >= 3:
            self.service_status[service_name] = ServiceStatus.FAILING
        else:
            self.service_status[service_name] = ServiceStatus.DEGRADED
    
    def get_service_status(self, service_name: str) -> ServiceStatus:
        """获取服务状态"""
        with self._lock:
            return self.service_status.get(service_name, ServiceStatus.UNAVAILABLE)
    
    def get_all_services_status(self) -> Dict[str, ServiceStatus]:
        """获取所有服务状态"""
        with self._lock:
            return self.service_status.copy()

class FallbackManager:
    """降级管理器"""
    
    def __init__(self):
        self.fallback_strategies: Dict[str, List[Callable]] = {}
        self.current_strategy_index: Dict[str, int] = {}
    
    def register_fallback(self, service_name: str, strategies: List[Callable]):
        """注册降级策略"""
        self.fallback_strategies[service_name] = strategies
        self.current_strategy_index[service_name] = 0
    
    def execute_with_fallback(self, service_name: str, primary_func: Callable, *args, **kwargs):
        """执行主功能，失败时降级"""
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"主功能 {service_name} 失败: {e}，尝试降级策略")
            return self._try_fallback_strategies(service_name, *args, **kwargs)
    
    def _try_fallback_strategies(self, service_name: str, *args, **kwargs):
        """尝试降级策略"""
        strategies = self.fallback_strategies.get(service_name, [])
        
        for i, strategy in enumerate(strategies):
            try:
                logger.info(f"尝试 {service_name} 的第 {i+1} 个降级策略")
                return strategy(*args, **kwargs)
            except Exception as e:
                logger.warning(f"{service_name} 的第 {i+1} 个降级策略失败: {e}")
                continue
        
        raise Exception(f"所有降级策略都失败，服务 {service_name} 不可用")

class ResilienceManager:
    """弹性管理器 - 统一管理所有弹性机制"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.health_checker = ServiceHealthChecker()
        self.fallback_manager = FallbackManager()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.config = self._load_config(config_path)
        
        logger.info("弹性管理器初始化完成")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置"""
        default_config = {
            "circuit_breaker": {
                "failure_threshold": 5,
                "timeout": 60.0
            },
            "retry": {
                "max_attempts": 3,
                "base_delay": 1.0,
                "max_delay": 60.0
            },
            "health_check": {
                "interval": 30.0
            }
        }
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.warning(f"加载弹性配置失败: {e}，使用默认配置")
        
        return default_config
    
    def create_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """创建熔断器"""
        cb_config = self.config.get("circuit_breaker", {})
        circuit_breaker = CircuitBreaker(
            failure_threshold=cb_config.get("failure_threshold", 5),
            timeout=cb_config.get("timeout", 60.0)
        )
        self.circuit_breakers[service_name] = circuit_breaker
        return circuit_breaker
    
    def create_retry_decorator(self, **kwargs) -> AdvancedRetry:
        """创建重试装饰器"""
        retry_config = self.config.get("retry", {})
        
        # 合并配置
        final_config = {
            "max_attempts": retry_config.get("max_attempts", 3),
            "delay_strategy": lambda attempt: RetryStrategy.exponential_backoff(
                attempt,
                base_delay=retry_config.get("base_delay", 1.0),
                max_delay=retry_config.get("max_delay", 60.0)
            )
        }
        final_config.update(kwargs)
        
        return AdvancedRetry(**final_config)
    
    def get_system_resilience_status(self) -> Dict[str, Any]:
        """获取系统弹性状态"""
        return {
            "services": self.health_checker.get_all_services_status(),
            "circuit_breakers": {
                name: cb.state.value 
                for name, cb in self.circuit_breakers.items()
            },
            "timestamp": time.time()
        }

# 全局弹性管理器实例
resilience_manager = ResilienceManager()

# 便捷装饰器
def resilient_function(
    service_name: str,
    max_attempts: int = 3,
    enable_circuit_breaker: bool = True,
    fallback_strategies: Optional[List[Callable]] = None
):
    """
    弹性函数装饰器 - 集成重试、熔断、降级功能
    
    Args:
        service_name: 服务名称
        max_attempts: 最大重试次数
        enable_circuit_breaker: 是否启用熔断器
        fallback_strategies: 降级策略列表
    """
    def decorator(func):
        # 创建重试装饰器
        retry_decorator = resilience_manager.create_retry_decorator(max_attempts=max_attempts)
        
        # 创建熔断器
        if enable_circuit_breaker:
            circuit_breaker = resilience_manager.create_circuit_breaker(service_name)
            func = circuit_breaker(func)
        
        # 应用重试
        func = retry_decorator(func)
        
        # 注册降级策略
        if fallback_strategies:
            resilience_manager.fallback_manager.register_fallback(service_name, fallback_strategies)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if fallback_strategies:
                return resilience_manager.fallback_manager.execute_with_fallback(
                    service_name, func, *args, **kwargs
                )
            else:
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator