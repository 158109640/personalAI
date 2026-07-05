"""
错误处理 - 重试机制
文件位置: backend/app/core/retry.py
"""
import asyncio
import random
import logging
from typing import Callable, Awaitable, TypeVar, Optional, List, Any
from functools import wraps

from .exceptions import AgentError, ErrorType

logger = logging.getLogger(__name__)
T = TypeVar('T')


class RetryConfig:
    """重试配置"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        retryable_error_types: Optional[List[ErrorType]] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.retryable_error_types = retryable_error_types or [
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.RATE_LIMIT_ERROR,
            ErrorType.CONNECTION_ERROR,
        ]
    
    @classmethod
    def fast(cls):
        """快速重试（适合内部工具）"""
        return cls(max_retries=2, base_delay=0.1, max_delay=1.0)
    
    @classmethod
    def network(cls):
        """网络重试（适合外部API）"""
        return cls(max_retries=3, base_delay=1.0, max_delay=30.0)
    
    @classmethod
    def aggressive(cls):
        """激进重试（适合不稳定服务）"""
        return cls(max_retries=5, base_delay=2.0, max_delay=120.0)
    
    @classmethod
    def no_retry(cls):
        """不重试"""
        return cls(max_retries=0)


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.retry_count = 0
        self.total_retries = 0
        self._retry_logs = []
    
    def calculate_delay(self, attempt: int) -> float:
        """计算退避延迟（含抖动）"""
        delay = self.config.base_delay * (self.config.backoff_multiplier ** attempt)
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            # 添加随机抖动，防止惊群效应
            jitter_range = delay * 0.2
            delay = delay + random.uniform(-jitter_range, jitter_range)
            delay = max(0.1, delay)
        
        return delay
    
    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        agent_name: str = "unknown",
        tool_name: Optional[str] = None,
        *args,
        **kwargs
    ) -> T:
        """带重试的执行函数"""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"[重试成功] {agent_name} 第 {attempt} 次重试成功")
                
                return result
                
            except AgentError as e:
                # 检查是否可重试
                if not e.retryable or e.error_type not in self.config.retryable_error_types:
                    logger.warning(f"[不可重试] {agent_name}: {e.message} (类型: {e.error_type.value})")
                    raise
                
                if attempt >= self.config.max_retries:
                    logger.error(f"[重试耗尽] {agent_name}: 已重试 {attempt} 次，仍然失败")
                    raise
                
                last_exception = e
                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"[重试] {agent_name} 第 {attempt + 1} 次失败，"
                    f"{delay:.2f}s 后重试: {e.message}"
                )
                self.total_retries += 1
                self._retry_logs.append({
                    "attempt": attempt + 1,
                    "error": e.message,
                    "delay": delay
                })
                await asyncio.sleep(delay)
                
            except Exception as e:
                # 非 AgentError 的异常，包装后抛出
                raise AgentError(
                    error_type=ErrorType.UNKNOWN_ERROR,
                    message=f"未知错误: {str(e)}",
                    agent_name=agent_name,
                    tool_name=tool_name,
                    retryable=False,
                    original_exception=e
                )
        
        # 如果所有重试都失败
        if last_exception:
            raise last_exception
        
        raise AgentError(
            error_type=ErrorType.UNKNOWN_ERROR,
            message="执行失败，原因未知",
            agent_name=agent_name,
            tool_name=tool_name
        )
    
    def get_retry_logs(self) -> List[dict]:
        """获取重试日志"""
        return self._retry_logs