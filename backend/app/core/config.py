from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
  # 应用配置
  app_name: str = "AI 研发助理"
  debug: bool = True

  # 上传配置
  UPLOAD_DIR: str = "uploads"
  BASE_URL: str = "http://121.89.90.145:8000"
  MAX_FILE_SIZE: int = 1024 * 1024 * 10  # 10MB
  
  # 数据库配置
  database_url: str = "sqlite+aiosqlite:///./app.db"
  
  # JWT 配置
  secret_key: str = "your-secret-key-change-in-production"
  algorithm: str = "HS256"
  access_token_expire_minutes: int = 60 * 24 * 7  # 7 天

  # DeepSeek API 配置
  deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
  deepseek_base_url: str = "https://api.deepseek.com/v1"
  deepseek_model: str = "deepseek-chat"

  # RAG API 配置
  rag_api_key: str = os.getenv("RAG_API_KEY", "")

  # 高德地图 API 配置
  gaode_map_key: str = os.getenv("GAODE_MAP_KEY", "")
  tvly_api_key: str = os.getenv("TVLY_API_KEY", "")

  # 多模态模型配置（新增）
  vl_api_key: str = os.getenv("VL_API_KEY", "")
  vl_base_url: str = os.getenv("VL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
  vl_model: str = os.getenv("VL_MODEL", "qwen-vl-plus")

  # TVLY API 配置
  tvly_base_url: str = "https://api.tavily.com"

  # 邮箱 API 配置
  email_api_key: str = os.getenv("EMAIL_API_KEY", "")

  # 邮箱 API 配置
  email_base_url: str = "https://api.resend.com/emails"
  
  # Redis 配置（新增）
  redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

  # 语音识别 API 配置
  voice_api_key: str = os.getenv("VOICE_API_KEY", "")
  voice_api_id: str = os.getenv("VOICE_API_ID", "")
  voice_secret_key: str = os.getenv("VOICE_SECRET_KEY", "")

  class Config:
    env_file = ".env"
    env_file_encoding = "utf-8"

# 创建全局 settings 实例
settings = Settings()