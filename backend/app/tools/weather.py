import asyncio
import httpx
from app.core.config import settings

# ---------- 异步天气查询逻辑（Tools 层直接调用高德 API） ----------
async def _get_weather_async(city: str) -> str:
    """异步查询天气，直接调用高德地图 API"""
    amap_key = settings.gaode_map_key
    if not amap_key:
        return "未配置 gaode_map_key，请在 .env 文件中设置高德地图 API Key"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 第一步：城市名转 adcode
            geo_url = "https://restapi.amap.com/v3/geocode/geo"
            geo_resp = await client.get(geo_url, params={
                "key": amap_key,
                "address": city,
                "output": "JSON"
            })
            geo_data = geo_resp.json()

            if geo_data.get("status") != "1" or not geo_data.get("geocodes"):
                return f"未找到城市：{city}"

            adcode = geo_data["geocodes"][0]["adcode"]

            # 第二步：查询天气
            weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
            weather_resp = await client.get(weather_url, params={
                "key": amap_key,
                "city": adcode,
                "extensions": "base"
            })
            weather_data = weather_resp.json()

            if weather_data.get("status") != "1" or not weather_data.get("lives"):
                return f"无法获取 {city} 的天气信息"

            live = weather_data["lives"][0]
            return (
                f"📍 {live['city']}\n"
                f"🌤 天气：{live['weather']}\n"
                f"🌡 温度：{live['temperature']}℃\n"
                f"💨 风向：{live['winddirection']}（{live['windpower']}级）\n"
                f"💧 湿度：{live['humidity']}%"
            )

    except httpx.TimeoutException:
        return "天气服务请求超时，请稍后再试"
    except Exception as e:
        return f"天气查询失败：{str(e)}"

# ---------- 同步包装器（供 LangChain Agent 调用） ----------
def get_weather(city: str) -> str:
    """
    查询指定城市的实时天气（同步函数，供 Agent 工具使用）
    """
    try:
        return asyncio.run(_get_weather_async(city))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_get_weather_async(city))
        finally:
            loop.close()
    except Exception as e:
        return f"天气查询失败：{str(e)}"

 # 新增异步版本
async def get_weather_async(city: str) -> str:
    return await _get_weather_async(city)       