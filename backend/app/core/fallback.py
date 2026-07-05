"""
错误处理 - 降级机制
文件位置: backend/app/core/fallback.py
"""
from typing import Any, Dict, Callable, Awaitable, Optional, Union
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class FallbackStrategy(ABC):
    """降级策略基类"""
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Any:
        """执行降级逻辑"""
        pass


class StaticFallback(FallbackStrategy):
    """静态值降级：返回预设的默认值"""
    
    def __init__(self, default_value: Any):
        self.default_value = default_value
    
    async def execute(self, context: Dict[str, Any]) -> Any:
        logger.info(f"[降级] 返回静态默认值: {self.default_value}")
        return self.default_value


class CacheFallback(FallbackStrategy):
    """缓存降级：使用缓存中的数据"""
    
    def __init__(self, cache_key: str, cache_client: Any):
        self.cache_key = cache_key
        self.cache_client = cache_client
    
    async def execute(self, context: Dict[str, Any]) -> Any:
        logger.info(f"[降级] 从缓存读取: {self.cache_key}")
        # 假设缓存客户端有 get 方法
        if hasattr(self.cache_client, 'get'):
            return await self.cache_client.get(self.cache_key)
        return None


class AlternativeToolFallback(FallbackStrategy):
    """备用工具降级：使用备用工具"""
    
    def __init__(self, alternative_tool: Callable, tool_name: str):
        self.alternative_tool = alternative_tool
        self.tool_name = tool_name
    
    async def execute(self, context: Dict[str, Any]) -> Any:
        logger.info(f"[降级] 使用备用工具: {self.tool_name}")
        try:
            # 从上下文中提取参数
            result = await self.alternative_tool(**context)
            return result
        except Exception as e:
            logger.error(f"[降级] 备用工具执行失败: {str(e)}")
            raise


class ChainFallback(FallbackStrategy):
    """链式降级：依次尝试多个降级策略"""
    
    def __init__(self, strategies: list[FallbackStrategy]):
        self.strategies = strategies
    
    async def execute(self, context: Dict[str, Any]) -> Any:
        last_error = None
        
        for idx, strategy in enumerate(self.strategies):
            try:
                logger.info(f"[链式降级] 尝试第 {idx + 1} 个策略: {strategy.__class__.__name__}")
                return await strategy.execute(context)
            except Exception as e:
                last_error = e
                logger.warning(f"[链式降级] 第 {idx + 1} 个策略失败: {str(e)}")
                continue
        
        if last_error:
            raise last_error
        raise Exception("所有降级策略都失败了")


class FallbackManager:
    """降级管理器"""
    
    def __init__(self):
        self._fallback_map: Dict[str, FallbackStrategy] = {}
        self._default_fallback: Optional[FallbackStrategy] = None
    
    def register_fallback(self, tool_name: str, strategy: FallbackStrategy):
        """注册某个工具的降级策略"""
        self._fallback_map[tool_name] = strategy
        logger.info(f"[注册降级] {tool_name} -> {strategy.__class__.__name__}")
    
    def register_default(self, strategy: FallbackStrategy):
        """注册默认降级策略"""
        self._default_fallback = strategy
        logger.info(f"[注册默认降级] {strategy.__class__.__name__}")
    
    def get_fallback(self, tool_name: str) -> Optional[FallbackStrategy]:
        """获取某个工具的降级策略"""
        return self._fallback_map.get(tool_name, self._default_fallback)
    
    async def execute_with_fallback(
        self,
        tool_name: str,
        func: Callable[..., Awaitable[Any]],
        context: Dict[str, Any],
        *args,
        **kwargs
    ) -> Any:
        """带降级的执行"""
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            strategy = self.get_fallback(tool_name)
            if strategy:
                logger.warning(f"[触发降级] 工具 '{tool_name}' 执行失败，原因: {str(e)}")
                try:
                    result = await strategy.execute(context)
                    logger.info(f"[降级成功] 工具 '{tool_name}' 降级成功")
                    return result
                except Exception as fallback_error:
                    logger.error(f"[降级失败] 工具 '{tool_name}' 降级也失败: {fallback_error}")
                    raise
            # 没有降级策略则重新抛出
            raise