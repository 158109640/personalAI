# Tools 目录说明：同步包装器与异步实现

## 为什么需要这种设计？

LangChain 的 `@tool` 装饰器要求被装饰的函数是**同步的**（即普通 `def` 函数）。但我们的工具需要调用外部 API（如高德天气、Tavily 搜索），这些是 **I/O 密集型操作**，使用异步 `async/await` 能更高效地利用系统资源。

为了解决这个矛盾，我们采用了“**同步包装器 + 异步实现**”的两层结构。

---

## 两层结构的职责

| 层次 | 函数命名 | 职责 | 调用者 |
| :--- | :--- | :--- | :--- |
| **同步包装器** | `def search_web(query: str) -> str` | 提供同步入口，供 LangChain 的 `@tool` 调用 | `agent_service.py` |
| **异步实现** | `async def _search_async(query: str) -> str` | 真正执行网络请求 (I/O 密集) | 被同步包装器调用 |

---

## 代码模板

```python
import asyncio
import httpx
from app.core.config import settings

# ---------- 1. 异步实现（真正干活的部分） ----------
async def _search_async(query: str) -> str:
    \"\"\"异步函数：执行实际的网络请求\"\"\"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 调用外部 API
            resp = await client.get("https://api.example.com/search", params={"q": query})
            data = resp.json()
            return format_result(data)
    except Exception as e:
        return f"搜索失败: {str(e)}"

# ---------- 2. 同步包装器（适配 LangChain） ----------
def search_web(query: str) -> str:
    \"\"\"同步包装器：供 LangChain Agent 调用\"\"\"
    try:
        # 方式一：直接用 asyncio.run
        return asyncio.run(_search_async(query))
    except RuntimeError:
        # 方式二：如果已有事件循环（如在 Jupyter 中），用新循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_search_async(query))
        finally:
            loop.close()
    except Exception as e:
        return f"操作失败：{str(e)}"

#关键点说明

asyncio.run() 的作用
在同步函数内部“驱动”一个异步函数，等待其执行完毕并返回结果。
为什么要处理 RuntimeError？
如果当前环境已经有一个运行中的事件循环（例如在 Jupyter Notebook 或某些异步框架中），asyncio.run() 会报错。这时需要创建一个新的事件循环来执行任务。
httpx.AsyncClient 的作用
异步 HTTP 客户端，比同步的 requests 库性能更好，尤其适合并发请求场景。       