from typing import List, Dict, Any, AsyncIterator
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.tools import get_weather_async, search_web_async, send_email_async

class AgentService:
    def __init__(self):
        self.model = ChatOpenAI(
            model=settings.deepseek_model,
            temperature=0.7,
            openai_api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url
        )
        
        @tool
        async def weather_tool(city: str) -> str:
            """查询指定城市的实时天气"""
            return await get_weather_async(city)
        
        @tool
        async def search_tool(query: str) -> str:
            """联网搜索最新信息。当用户问新闻、热点、实时数据时使用。"""
            return await search_web_async(query)

        @tool
        async def email_tool(to: str, subject: str, body: str) -> str:
            """发送电子邮件。当用户要求发送邮件时使用。"""
            return await send_email_async(to, subject, body)

        # 使用 langgraph 创建 Agent
        self.agent = create_react_agent(
            model=self.model,
            tools=[weather_tool, search_tool, email_tool]
        )
    
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """非流式对话"""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        lc_messages = []
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                lc_messages.append(SystemMessage(content=msg["content"]))
        
        result = await self.agent.ainvoke({"messages": lc_messages})
        return result["messages"][-1].content

    async def stream_chat(self, messages: List[Dict[str, str]]):
        """流式对话"""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
            
            lc_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    lc_messages.append(SystemMessage(content=msg["content"]))
            
            async for chunk in self.model.astream(lc_messages):
                if chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            print(f"流式生成出错: {e}")
            yield f"出错: {str(e)}"

agent_service = AgentService()