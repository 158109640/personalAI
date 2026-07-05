from openai import OpenAI
from app.core.config import settings

class AIService:
  def __init__(self):
    # 初始化 DeepSeek 客户端（兼容 OpenAI 接口）
    self.client = OpenAI(
      api_key=settings.deepseek_api_key,
      base_url=settings.deepseek_base_url
    )
    self.model = settings.deepseek_model

  def get_response(self, messages: list) -> str:
    """发送消息给 DeepSeek，返回回复内容"""
    try:
      response = self.client.chat.completions.create(
        model=self.model,
        messages=messages,
        temperature=0.7,
        max_tokens=2048
      )
      return response.choices[0].message.content
    except Exception as e:
      print(f"AI 服务调用失败: {e}")
      return f"抱歉，我现在无法回答你的问题。错误信息：{str(e)}"

# 单例模式，全局共享一个实例
ai_service = AIService()
