"""
错误处理 - 异常定义
文件位置: backend/app/core/exceptions.py
"""
from enum import Enum
from typing import Optional, Any


class ErrorType(Enum):
    """错误类型枚举"""
    # 网络相关
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    CONNECTION_ERROR = "connection_error"
    
    # 工具相关
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    TOOL_NOT_FOUND = "tool_not_found"
    
    # 数据处理
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    
    # 限流认证
    RATE_LIMIT_ERROR = "rate_limit_error"
    AUTH_ERROR = "auth_error"
    
    # 业务相关
    BUSINESS_ERROR = "business_error"
    NOT_FOUND = "not_found"
    
    # 系统
    UNKNOWN_ERROR = "unknown_error"


class AgentError(Exception):
    """Agent 自定义异常基类"""
    
    def __init__(
        self,
        error_type: ErrorType,
        message: str,
        agent_name: str = "unknown",
        tool_name: Optional[str] = None,
        retryable: bool = True,
        status_code: int = 500,
        details: Optional[dict] = None,
        original_exception: Optional[Exception] = None
    ):
        self.error_type = error_type
        self.message = message
        self.agent_name = agent_name
        self.tool_name = tool_name
        self.retryable = retryable
        self.status_code = status_code
        self.details = details or {}
        self.original_exception = original_exception
        
        super().__init__(f"[{agent_name}] {message}")
    
    def to_dict(self) -> dict:
        """转换为字典，用于API响应"""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "agent_name": self.agent_name,
            "tool_name": self.tool_name,
            "status_code": self.status_code,
            "details": self.details
        }


class ToolExecutionError(AgentError):
    """工具执行失败"""
    def __init__(self, tool_name: str, message: str, **kwargs):
        super().__init__(
            error_type=ErrorType.TOOL_EXECUTION_ERROR,
            message=message,
            tool_name=tool_name,
            retryable=True,
            status_code=500,
            **kwargs
        )


class NetworkError(AgentError):
    """网络错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            error_type=ErrorType.NETWORK_ERROR,
            message=message,
            retryable=True,
            status_code=503,
            **kwargs
        )


class RateLimitError(AgentError):
    """限流错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            error_type=ErrorType.RATE_LIMIT_ERROR,
            message=message,
            retryable=True,
            status_code=429,
            **kwargs
        )


class NotFoundError(AgentError):
    """资源未找到"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            error_type=ErrorType.NOT_FOUND,
            message=message,
            retryable=False,
            status_code=404,
            **kwargs
        )