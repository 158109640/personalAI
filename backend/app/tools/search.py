import asyncio
import httpx
from app.core.config import settings

# ---------- 异步搜索逻辑 ----------
async def _search_async(query: str) -> str:
    """真正的异步搜索函数：直接调用 Tavily API"""
    api_key = settings.tvly_api_key
    if not api_key:
        return "未配置 tvly_base_url .env 文件中设置"

    url = f"{settings.tvly_base_url}/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 3,
        "include_answer": True
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 打印请求信息（方便调试）
            print(f"🔍 正在搜索: {query}")
            print(f"📤 请求 URL: {url}")
            print(f"📤 请求参数: {payload}")
            
            resp = await client.post(url, json=payload, headers=headers)
            
            # 打印响应状态
            print(f"📥 响应状态码: {resp.status_code}")
            
            # 如果状态码不是 200，打印错误信息
            if resp.status_code != 200:
                print(f"❌ 响应内容: {resp.text}")
                return f"搜索服务返回错误状态码: {resp.status_code}"
            
            data = resp.json()
            
            # 打印返回数据的前 200 个字符（方便调试）
            print(f"📥 响应数据: {str(data)[:200]}...")
            
            result_parts = []
            if data.get("answer"):
                result_parts.append(f"💡 {data['answer']}")

            if data.get("results"):
                result_parts.append("\n📰 来源：")
                for idx, item in enumerate(data["results"][:3], 1):
                    title = item.get("title", "无标题")
                    content = item.get("content", "")[:150]
                    result_parts.append(f"{idx}. {title}\n   {content}...")

            return "\n".join(result_parts) if result_parts else f"未找到关于「{query}」的信息"

    except httpx.TimeoutException as e:
        print(f"⏰ 超时错误: {e}")
        return "搜索服务超时，请稍后重试"
    except Exception as e:
        print(f"❌ 搜索异常: {type(e).__name__}: {e}")
        return f"搜索失败：{str(e)}"

# ---------- 同步包装器 ----------
def search_web(query: str) -> str:
    """
    联网搜索（同步函数，供 Agent 工具使用）
    """
    try:
        return asyncio.run(_search_async(query))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_search_async(query))
        finally:
            loop.close()
    except Exception as e:
        print(f"❌ 同步包装器异常: {e}")
        return f"搜索失败：{str(e)}"

async def search_web_async(query: str) -> str:
    return await _search_async(query)
