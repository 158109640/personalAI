"""
核心框架 - 统一导出
文件位置: backend/app/core/__init__.py
"""
from .exceptions import (
    AgentError,
    ErrorType,
    ToolExecutionError,
    NetworkError,
    RateLimitError,
    NotFoundError
)
from .retry import RetryHandler, RetryConfig
from .fallback import (
    FallbackManager,
    StaticFallback,
    CacheFallback,
    AlternativeToolFallback,
    ChainFallback
)
from .decorators import (
    with_error_handling,
    retry_on_failure,
    timeout
)

__all__ = [
    # 异常
    'AgentError',
    'ErrorType',
    'ToolExecutionError',
    'NetworkError',
    'RateLimitError',
    'NotFoundError',
    
    # 重试
    'RetryHandler',
    'RetryConfig',
    
    # 降级
    'FallbackManager',
    'StaticFallback',
    'CacheFallback',
    'AlternativeToolFallback',
    'ChainFallback',
    
    # 装饰器
    'with_error_handling',
    'retry_on_failure',
    'timeout',
]