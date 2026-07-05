"""
错误处理 - 装饰器
文件位置: backend/app/core/decorators.py
"""
from functools import wraps
from typing import Optional, Callable, Any
import logging
import asyncio
import time

from .retry import RetryHandler, RetryConfig
from .fallback import FallbackManager
from .exceptions import AgentError

logger = logging.getLogger(__name__)


def with_error_handling(
    agent_name: str = "unknown",
    retry_config: Optional[RetryConfig] = None,
    fallback_manager: Optional[FallbackManager] = None,
    tool_name: Optional[str] = None,
    log_level: str = "INFO"
):
    """
    Agent 错误处理装饰器
    
    用法:
        @with_error_handling(agent_name="weather_agent")
        async def get_weather(city: str):
            ...
    
    参数:
        agent_name: Agent名称
        retry_config: 重试配置
        fallback_manager: 降级管理器
        tool_name: 工具名称（用于降级匹配）
        log_level: 日志级别
    """
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            handler_name = agent_name or func.__name__
            
            # 初始化重试处理器
            retry_handler = RetryHandler(retry_config or RetryConfig())
            
            try:
                # 执行带重试的函数
                result = await retry_handler.execute_with_retry(
                    func=func,
                    agent_name=handler_name,
                    tool_name=tool_name,
                    *args,
                    **kwargs
                )
                
                elapsed = time.time() - start_time
                logger.info(f"[{handler_name}] 执行成功，耗时: {elapsed:.2f}s")
                
                # 如果有重试记录，添加到结果中（可选）
                if retry_handler.get_retry_logs():
                    if isinstance(result, dict):
                        result['_retry_info'] = {
                            'retry_count': len(retry_handler.get_retry_logs()),
                            'retry_logs': retry_handler.get_retry_logs()
                        }
                
                return result
                
            except AgentError as e:
                # 如果配置了降级策略，尝试降级
                if fallback_manager and tool_name:
                    try:
                        logger.warning(f"[{handler_name}] 尝试降级: {tool_name}")
                        # 构建上下文
                        context = {**kwargs}
                        if args:
                            # 尝试从args提取参数名（需要函数签名支持）
                            import inspect
                            sig = inspect.signature(func)
                            param_names = list(sig.parameters.keys())
                            for idx, arg in enumerate(args):
                                if idx < len(param_names):
                                    context[param_names[idx]] = arg
                        
                        fallback_result = await fallback_manager.execute_with_fallback(
                            tool_name=tool_name,
                            func=func,
                            context=context,
                            *args,
                            **kwargs
                        )
                        logger.info(f"[{handler_name}] 降级成功")
                        return fallback_result
                    except Exception as fallback_error:
                        logger.error(f"[{handler_name}] 降级失败: {fallback_error}")
                        # 降级失败，继续抛出原始错误
                
                elapsed = time.time() - start_time
                logger.error(
                    f"[{handler_name}] 执行失败，耗时: {elapsed:.2f}s, "
                    f"错误: {e.message} (类型: {e.error_type.value})"
                )
                raise
                
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"[{handler_name}] 未处理异常，耗时: {elapsed:.2f}s, "
                    f"错误: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    简单的重试装饰器（不依赖AgentError）
    
    用法:
        @retry_on_failure(max_retries=3)
        async def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt >= max_retries:
                        raise
                    
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(
                        f"[{func.__name__}] 第 {attempt + 1} 次失败，"
                        f"{wait_time:.2f}s 后重试: {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
            
            raise last_exception
        
        return wrapper
    return decorator


def timeout(seconds: int):
    """超时装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                raise AgentError(
                    error_type=ErrorType.TIMEOUT_ERROR,
                    message=f"执行超时 ({seconds}s)",
                    agent_name=func.__name__,
                    retryable=True
                )
        return wrapper
    return decorator