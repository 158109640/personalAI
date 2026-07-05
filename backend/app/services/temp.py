from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.core.config import settings
from app.tools import search_web, get_weather, send_email
import json
import re
from app.services.rag_service import rag_service
from app.models.document import Document
from app.core.database import get_db
from sqlalchemy import select

# ===== 定义状态 =====
class AgentState(TypedDict):
    query: str                    # 用户问题
    messages: List[Dict[str, str]]  # 对话历史
    research_result: str          # 研究结果
    final_answer: str             # 最终答案
    next_step: str                # 下一步动作
    user_id: int                  # 用户 ID

# ===== 初始化模型 =====
model = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.7,
    openai_api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url
)

# ===== 1. 主管 Agent：判断任务并分配 =====
def supervisor(state: AgentState) -> AgentState:
    user_id = state.get('user_id', 1)
    query = state['query']
    
    # 1. 先检查用户是否有文档
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def check_docs():
        async for db in get_db():
            stmt = select(Document).where(
                Document.owner_id == user_id,
                Document.status == "processed"
            )
            result = await db.execute(stmt)
            docs = result.scalars().all()
            return docs
        return []

    docs = loop.run_until_complete(check_docs())
    loop.close()
    
    # 2. 如果有文档，尝试 RAG 检索
    if docs:
        from app.services.rag_service import rag_service
        doc_ids = [doc.doc_id for doc in docs]
        chunks = asyncio.run(rag_service.search_all_documents(
            doc_ids=doc_ids,
            query=query,
            top_k_per_doc=3,
            final_top_k=3
        ))
        
        if chunks and chunks[0]["score"] > 0.1:
            print(f"📚 RAG 命中，直接走 need_rag")
            state["next_step"] = "need_rag"
            # 把检索结果保存到 state 中
            state["rag_chunks"] = chunks
            return state    

    context = ""
    for msg in state.get('messages', [])[-5:]:
        role = "用户" if msg['role'] == 'user' else "助手"
        context += f"{role}: {msg['content']}\n"
    
    prompt = f"""你是主编，负责判断用户问题需要调用哪个工具。

    对话历史：
    {context if context else "（无历史对话）"}

    用户当前问题：{state['query']}

    判断规则：
    1. 如果用户问的是文档中的内容、公司内部信息 → 返回 need_rag
    2. 如果用户问的是新闻、实时信息 → 返回 need_search
    3. 如果用户问的是天气、温度 → 返回 need_weather
    4. 如果用户要求发送邮件 → 返回 need_email
    5. 如果用户可以直接回答（闲聊、常识问题）→ 返回 direct_answer

    只返回 need_rag、need_search、need_weather、need_email 或 direct_answer 中的一个，不要有其他内容。"""
    
    response = model.invoke([HumanMessage(content=prompt)])
    decision = response.content.strip().lower()
    decision = decision.replace('"', '').replace("'", "").strip()
    
    valid_decisions = ["need_rag", "need_search", "need_weather", "need_email", "direct_answer"]
    if decision not in valid_decisions:
        print(f"⚠️ 未知决策: {decision}，默认使用 direct_answer")
        decision = "direct_answer"
    
    print(f"📋 主管决策: {decision}")
    # 发送状态到前端（通过回调）
    status_map = {
        "need_rag": "📚 正在检索文档...",
        "need_search": "🔍 正在联网搜索...",
        "need_weather": "🌤️ 正在查询天气...",
        "need_email": "📧 正在准备发送邮件...",
        "direct_answer": "✍️ 正在生成回答..."
    }
    state["current_status"] = status_map.get(decision, "⏳ 处理中...")
    state["next_step"] = decision
    return state

# ===== 2. 搜索员 Agent：执行搜索 =====
def searcher(state: AgentState) -> AgentState:
    print(f"🔍 搜索员正在搜索: {state['query']}")
    result = search_web(state['query'])
    state['research_result'] = result
    return state

# ===== 3. 天气 Agent：查询天气 =====
def weather_agent(state: AgentState) -> AgentState:
    print(f"🌤️ 天气员正在查询天气")
    
    # 构建上下文
    context = ""
    for msg in state.get('messages', [])[-3:]:
        role = "用户" if msg['role'] == 'user' else "助手"
        context += f"{role}: {msg['content']}\n"
    
    prompt = f"""对话历史：
    {context}

    用户当前问题：{state['query']}

    从对话中提取用户想查询天气的城市名称。只返回城市名，不要有其他内容。"""
    
    response = model.invoke([HumanMessage(content=prompt)])
    city = response.content.strip()
    
    print(f"🌤️ 查询城市: {city}")
    result = get_weather(city)
    state["current_status"] = "🌤️ 查询天气中..."
    state['research_result'] = result
    return state

# ===== 4. 回答者 Agent：生成最终答案 =====
def answerer(state: AgentState) -> AgentState:
    if state.get('research_result'):
        prompt = f"""基于以下信息回答用户问题。

        信息：
        {state['research_result']}

        用户问题：{state['query']}

        请基于信息给出准确、简洁的回答。"""
    else:
        prompt = f"""请直接回答用户问题：{state['query']}"""
    
    response = model.invoke([HumanMessage(content=prompt)])
    state["current_status"] = "✍️ 生成回答中..."
    state['final_answer'] = response.content
    return state

# ===== 5. 邮件 Agent：发送邮件 =====
def email_agent(state: AgentState) -> AgentState:
    print(f"📧 邮件员正在准备发送邮件")
    # 简单解析邮箱地址和内容
    import re
    query = state['query']
    
    # 提取邮箱
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', query)
    if not email_match:
        state['research_result'] = "未找到有效的邮箱地址，请提供收件人邮箱"
        return state
    
    to = email_match.group(0)
    
    # 提取主题和内容
    subject = "来自 AI 助手的邮件"
    body = f"用户请求：{query}"
    
    result = send_email(to, subject, body)
    state["current_status"] = "📧 发送邮件中..."
    state['research_result'] = result
    return state

# ===== RAG 研究员 Agent =====
async def rag_researcher(state: AgentState) -> AgentState:
    print(f"📚 RAG 研究员正在检索文档: {state['query']}")

    user_id = state.get('user_id', 1)
    
    # 获取用户的所有文档
    from app.models.document import Document
    from app.core.database import get_db
    from sqlalchemy import select
    
    async for db in get_db():
        stmt = select(Document).where(
            Document.owner_id == user_id,  # 这里需要从 state 获取用户 ID
            Document.status == "processed"
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()
        
        if docs:
            doc_ids = [doc.doc_id for doc in docs]
            chunks = await rag_service.search_all_documents(
                doc_ids=doc_ids,
                query=state['query'],
                top_k_per_doc=3,
                final_top_k=3
            )
            if chunks:
                context = "\n\n".join([chunk["content"] for chunk in chunks])
                state['research_result'] = f"📄 文档检索结果：\n\n{context}"
                return state
        
    state["current_status"] = "📚 检索文档中..."
    state['research_result'] = "未找到相关文档"
    return state   

 # app/services/multi_agent_service.py

async def stream_multi_agent(
    query: str,
    messages: List[Dict[str, str]],
    user_id: int
):
    """流式执行 Multi-Agent"""
    
    # 1. 先发送状态
    yield {"type": "status", "content": "🧠 正在分析问题..."}
    
    # 2. 初始化状态
    state = {
        "query": query,
        "messages": messages,
        "research_result": "",
        "final_answer": "",
        "next_step": "",
        "user_id": user_id
    }
    
    # 3. 执行 supervisor（在异步上下文中处理）
    # 由于 supervisor 是同步函数，我们需要在异步上下文中运行
    import asyncio
    state = await asyncio.to_thread(supervisor, state)
    
    decision = state["next_step"]
    
    # 发送决策状态
    status_map = {
        "need_rag": "📚 正在检索文档...",
        "need_search": "🔍 正在联网搜索...",
        "need_weather": "🌤️ 正在查询天气...",
        "need_email": "📧 正在准备发送邮件...",
        "direct_answer": "✍️ 正在生成回答..."
    }
    yield {"type": "status", "content": status_map.get(decision, "⏳ 处理中...")}
    
    # 4. 执行对应的 Agent
    if decision == "need_rag":
        state = await rag_researcher(state)
    elif decision == "need_search":
        state = await asyncio.to_thread(searcher, state)
    elif decision == "need_weather":
        state = await asyncio.to_thread(weather_agent, state)
    elif decision == "need_email":
        state = await asyncio.to_thread(email_agent, state)
    
    # 5. 回答者 Agent：逐字输出
    if state.get('research_result'):
        prompt = f"""基于以下信息回答用户问题。

信息：
{state['research_result']}

用户问题：{query}

请基于信息给出准确、简洁的回答。"""
    else:
        # 构建对话上下文
        context = ""
        for msg in messages[-3:]:
            role = "用户" if msg['role'] == 'user' else "助手"
            context += f"{role}: {msg['content']}\n"
        
        prompt = f"""对话历史：
{context if context else "（无历史对话）"}

用户当前问题：{query}

请根据对话历史理解上下文，回答用户问题。"""
    
    # 逐字生成回答
    async for chunk in model.astream([HumanMessage(content=prompt)]):
        if chunk.content:
            yield {"type": "content", "content": chunk.content}
    
    yield {"type": "done"}    

# ===== 构建图 =====
def build_multi_agent():
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("rag_researcher", rag_researcher)
    workflow.add_node("searcher", searcher)
    workflow.add_node("weather_agent", weather_agent)
    workflow.add_node("email_agent", email_agent)
    workflow.add_node("answerer", answerer)
    
    # 设置入口
    workflow.set_entry_point("supervisor")
    
    # 条件边
    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state["next_step"],
        {
            "need_rag": "rag_researcher",
            "need_search": "searcher",
            "need_weather": "weather_agent",
            "need_email": "email_agent",
            "direct_answer": "answerer"
        }
    )
    
    # 搜索员/天气员 → 回答者
    workflow.add_edge("searcher", "answerer")
    workflow.add_edge("weather_agent", "answerer")
    workflow.add_edge("email_agent", "answerer")
    workflow.add_edge("rag_researcher", "answerer")
    
    # 回答者 → 结束
    workflow.add_edge("answerer", END)
    
    return workflow.compile()

multi_agent = build_multi_agent()