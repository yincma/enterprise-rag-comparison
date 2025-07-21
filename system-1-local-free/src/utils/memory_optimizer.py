"""
内存优化和监控模块
提供内存管理、缓存优化、垃圾回收等功能
"""

import gc
import psutil
import threading
import time
import logging
from typing import Dict, Any, Optional, Callable, Union, List
from functools import wraps, lru_cache
from collections import OrderedDict
import weakref
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self, threshold_mb: int = 2048, check_interval: float = 30.0):
        """
        初始化内存监控器
        
        Args:
            threshold_mb: 内存警告阈值(MB)
            check_interval: 检查间隔(秒)
        """
        self.threshold_mb = threshold_mb
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread = None
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()
        
        logger.info(f"内存监控器初始化：阈值={threshold_mb}MB，检查间隔={check_interval}s")
    
    def start_monitoring(self):
        """开始监控"""
        with self._lock:
            if self.monitoring:
                return
            
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("内存监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        with self._lock:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5.0)
            logger.info("内存监控已停止")
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加内存状态变化回调"""
        self.callbacks.append(callback)
    
    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        process = psutil.Process()
        memory_info = process.memory_info()
        virtual_memory = psutil.virtual_memory()
        
        return {
            "process_memory_mb": memory_info.rss / 1024 / 1024,
            "process_memory_percent": process.memory_percent(),
            "system_memory_total_mb": virtual_memory.total / 1024 / 1024,
            "system_memory_available_mb": virtual_memory.available / 1024 / 1024,
            "system_memory_used_percent": virtual_memory.percent,
            "gc_count": {
                "gen0": gc.get_count()[0],
                "gen1": gc.get_count()[1],  
                "gen2": gc.get_count()[2]
            },
            "gc_stats": gc.get_stats(),
            "timestamp": time.time()
        }
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                memory_info = self.get_memory_info()
                
                # 检查是否超过阈值
                if memory_info["process_memory_mb"] > self.threshold_mb:
                    logger.warning(f"内存使用超过阈值：{memory_info['process_memory_mb']:.1f}MB > {self.threshold_mb}MB")
                    
                    # 触发回调
                    for callback in self.callbacks:
                        try:
                            callback(memory_info)
                        except Exception as e:
                            logger.error(f"内存监控回调失败: {e}")
                
                # 定期记录内存信息
                if int(time.time()) % 300 == 0:  # 每5分钟记录一次
                    logger.info(f"内存状态：进程={memory_info['process_memory_mb']:.1f}MB({memory_info['process_memory_percent']:.1f}%), "
                              f"系统={memory_info['system_memory_used_percent']:.1f}%")
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"内存监控循环错误: {e}")
                time.sleep(self.check_interval)

class LRUCache:
    """改进的LRU缓存实现"""
    
    def __init__(self, max_size: int = 1000, ttl: Optional[float] = None):
        """
        初始化LRU缓存
        
        Args:
            max_size: 最大缓存大小
            ttl: 生存时间(秒)，None表示永不过期
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache = OrderedDict()
        self._timestamps = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        
    def get(self, key: Any) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            # 检查TTL
            if self.ttl and time.time() - self._timestamps[key] > self.ttl:
                self._remove(key)
                self._misses += 1
                return None
            
            # 移动到末尾（最近使用）
            value = self._cache.pop(key)
            self._cache[key] = value
            self._hits += 1
            return value
    
    def put(self, key: Any, value: Any):
        """设置缓存值"""
        with self._lock:
            if key in self._cache:
                # 更新现有键
                self._cache.pop(key)
            elif len(self._cache) >= self.max_size:
                # 删除最久未使用的项
                oldest_key = next(iter(self._cache))
                self._remove(oldest_key)
            
            self._cache[key] = value
            self._timestamps[key] = time.time()
    
    def _remove(self, key: Any):
        """删除键"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "memory_usage_mb": sys.getsizeof(self._cache) / 1024 / 1024
            }

class MemoryPool:
    """内存池管理器"""
    
    def __init__(self, pool_size_mb: int = 100):
        """
        初始化内存池
        
        Args:
            pool_size_mb: 内存池大小(MB)
        """
        self.pool_size_mb = pool_size_mb
        self.allocated_objects: Dict[str, Any] = {}
        self.free_objects: Dict[str, List[Any]] = {}
        self._lock = threading.Lock()
        
        logger.info(f"内存池初始化：大小={pool_size_mb}MB")
    
    def get_object(self, object_type: str, factory: Callable[[], Any]) -> Any:
        """从内存池获取对象"""
        with self._lock:
            if object_type in self.free_objects and self.free_objects[object_type]:
                obj = self.free_objects[object_type].pop()
                logger.debug(f"从内存池复用对象: {object_type}")
                return obj
            else:
                obj = factory()
                logger.debug(f"创建新对象: {object_type}")
                return obj
    
    def return_object(self, object_type: str, obj: Any):
        """将对象返回内存池"""
        with self._lock:
            if object_type not in self.free_objects:
                self.free_objects[object_type] = []
            
            # 检查池大小限制
            current_size = sum(len(objects) for objects in self.free_objects.values())
            if current_size < self.pool_size_mb * 10:  # 简化的大小估算
                self.free_objects[object_type].append(obj)
                logger.debug(f"对象返回内存池: {object_type}")
            else:
                logger.debug(f"内存池已满，释放对象: {object_type}")
    
    def clear_pool(self):
        """清空内存池"""
        with self._lock:
            self.free_objects.clear()
            logger.info("内存池已清空")

class MemoryOptimizer:
    """内存优化器"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
        self.caches: Dict[str, LRUCache] = {}
        self.memory_pool = MemoryPool()
        self._optimization_callbacks: List[Callable[[], None]] = []
        
        # 注册默认优化回调
        self.monitor.add_callback(self._default_memory_optimization)
        
        logger.info("内存优化器初始化完成")
    
    def create_cache(self, name: str, max_size: int = 1000, ttl: Optional[float] = None) -> LRUCache:
        """创建命名缓存"""
        cache = LRUCache(max_size=max_size, ttl=ttl)
        self.caches[name] = cache
        return cache
    
    def get_cache(self, name: str) -> Optional[LRUCache]:
        """获取命名缓存"""
        return self.caches.get(name)
    
    def add_optimization_callback(self, callback: Callable[[], None]):
        """添加优化回调"""
        self._optimization_callbacks.append(callback)
    
    def _default_memory_optimization(self, memory_info: Dict[str, Any]):
        """默认内存优化策略"""
        logger.info("执行内存优化...")
        
        # 1. 强制垃圾回收
        collected = gc.collect()
        logger.info(f"垃圾回收释放了 {collected} 个对象")
        
        # 2. 清理过期缓存
        for name, cache in self.caches.items():
            old_size = cache.get_stats()["size"]
            cache.clear()
            logger.info(f"清理缓存 {name}：{old_size} -> 0")
        
        # 3. 清理内存池
        self.memory_pool.clear_pool()
        
        # 4. 执行自定义优化回调
        for callback in self._optimization_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"优化回调失败: {e}")
        
        # 5. 再次检查内存状态
        new_memory_info = self.monitor.get_memory_info()
        improvement = memory_info["process_memory_mb"] - new_memory_info["process_memory_mb"]
        logger.info(f"内存优化完成，节省了 {improvement:.1f}MB 内存")
    
    def get_memory_report(self) -> Dict[str, Any]:
        """获取内存报告"""
        memory_info = self.monitor.get_memory_info()
        
        cache_stats = {}
        for name, cache in self.caches.items():
            cache_stats[name] = cache.get_stats()
        
        return {
            "memory_info": memory_info,
            "cache_stats": cache_stats,
            "total_caches": len(self.caches),
            "gc_enabled": gc.isenabled(),
            "gc_threshold": gc.get_threshold()
        }

def memory_optimized(cache_name: Optional[str] = None, max_size: int = 1000, ttl: Optional[float] = None):
    """内存优化装饰器"""
    def decorator(func):
        # 为函数创建专用缓存
        if cache_name:
            cache = memory_optimizer.create_cache(cache_name, max_size, ttl)
        else:
            cache = memory_optimizer.create_cache(f"{func.__module__}.{func.__name__}", max_size, ttl)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = str(args) + str(sorted(kwargs.items()))
            
            # 尝试从缓存获取
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache.put(cache_key, result)
            
            return result
        
        # 添加缓存管理方法
        wrapper.cache = cache
        wrapper.clear_cache = cache.clear
        wrapper.get_cache_stats = cache.get_stats
        
        return wrapper
    
    return decorator

def batch_processor(batch_size: int = 100, memory_limit_mb: Optional[int] = None):
    """批处理装饰器，减少内存峰值"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 检查是否为方法调用（第一个参数是self）
            if len(args) >= 2 and hasattr(args[0], '__class__'):
                # 方法调用：self, items, *other_args
                self_arg = args[0]
                items = args[1]
                other_args = args[2:]
            elif len(args) >= 1:
                # 函数调用：items, *other_args
                self_arg = None
                items = args[0]
                other_args = args[1:]
            else:
                raise ValueError("batch_processor装饰器需要至少一个参数（要处理的项目列表）")
            
            if not items:
                return []
            
            results = []
            total_batches = len(items) // batch_size + (1 if len(items) % batch_size else 0)
            
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                batch_num = i // batch_size + 1
                
                logger.debug(f"处理批次 {batch_num}/{total_batches}，大小: {len(batch)}")
                
                # 检查内存限制
                if memory_limit_mb:
                    current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    if current_memory > memory_limit_mb:
                        logger.warning(f"内存使用({current_memory:.1f}MB)超过限制({memory_limit_mb}MB)，执行垃圾回收")
                        gc.collect()
                
                # 重新构建参数
                if self_arg is not None:
                    # 方法调用
                    batch_result = func(self_arg, batch, *other_args, **kwargs)
                else:
                    # 函数调用
                    batch_result = func(batch, *other_args, **kwargs)
                    
                results.extend(batch_result if isinstance(batch_result, list) else [batch_result])
                
                # 批次间垃圾回收
                if batch_num % 10 == 0:
                    gc.collect()
            
            return results
        
        return wrapper
    
    return decorator

# 全局内存优化器
memory_optimizer = MemoryOptimizer()

# 便捷函数
def start_memory_monitoring():
    """启动内存监控"""
    memory_optimizer.monitor.start_monitoring()

def stop_memory_monitoring():
    """停止内存监控"""
    memory_optimizer.monitor.stop_monitoring()

def get_memory_stats() -> Dict[str, Any]:
    """获取内存统计信息"""
    return memory_optimizer.get_memory_report()

def optimize_memory():
    """手动触发内存优化"""
    memory_info = memory_optimizer.monitor.get_memory_info()
    memory_optimizer._default_memory_optimization(memory_info)

def create_memory_efficient_cache(name: str, max_size: int = 1000, ttl: Optional[float] = None) -> LRUCache:
    """创建内存高效缓存"""
    return memory_optimizer.create_cache(name, max_size, ttl)