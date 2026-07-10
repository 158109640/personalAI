from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.core.config import settings
from app.tools import search_web, get_weather, send_email
from app.services.rag_service import rag_service
from app.models.document import Document
from app.core.database import get_db
from sqlalchemy import select
from app.services.tts_service import text_to_speech

# ===== 定义状态 =====
class AgentState(TypedDict):
    query: str                       # 用户问题
    messages: List[Dict[str, str]]   # 对话历史
    research_result: str             # 研究结果
    final_answer: str                # 最终答案
    next_step: str                   # 下一步动作
    user_id: int                     # 用户 ID
    reply_type: str                  # 回复类型 (text/audio)
    current_status: str              # 当前状态
    audio_url: str                   # 语音回复 URL

# ===== 初始化模型 =====
model = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.7,
    openai_api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url
)


# ============================================================
# 1. 主管 Agent：判断任务并分配工具
# ============================================================
def supervisor(state: AgentState) -> AgentState:
    user_id = state.get('user_id', 1)
    query = state['query']
    
    # 1.1 检查用户是否有文档
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
    
    # 1.2 如果有文档，尝试 RAG 检索
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
            state["rag_chunks"] = chunks
            return state
    
    # 1.3 构建对话上下文
    context = ""
    messages = state.get('messages', {})
    if isinstance(messages, dict):
        messages_list = messages.get('data', [])
    elif isinstance(messages, list):
        messages_list = messages
    else:
        messages_list = []
    
    for msg in messages_list[-5:]:
        role = "用户" if msg.get('role') == 'user' else "助手"
        context += f"{role}: {msg.get('content', '')}\n"
    
    # 1.4 调用大模型决策
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


# ============================================================
# 2. 搜索员 Agent：执行搜索
# ============================================================
def searcher(state: AgentState) -> AgentState:
    print(f"🔍 搜索员正在搜索: {state['query']}")
    result = search_web(state['query'])
    state['research_result'] = result
    return state


# ============================================================
# 3. 天气 Agent：查询天气
# ============================================================
def weather_agent(state: AgentState) -> AgentState:
    print(f"🌤️ 天气员正在查询天气")
    
    context = ""
    messages = state.get('messages', {})
    if isinstance(messages, dict):
        messages_list = messages.get('data', [])
    elif isinstance(messages, list):
        messages_list = messages
    else:
        messages_list = []
    
    for msg in messages_list[-3:]:
        role = "用户" if msg.get('role') == 'user' else "助手"
        context += f"{role}: {msg.get('content', '')}\n"
    
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


# ============================================================
# 4. 邮件 Agent：发送邮件
# ============================================================
def email_agent(state: AgentState) -> AgentState:
    print(f"📧 邮件员正在准备发送邮件")
    import re
    query = state['query']
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', query)
    if not email_match:
        state['research_result'] = "未找到有效的邮箱地址，请提供收件人邮箱"
        return state
    
    to = email_match.group(0)
    subject = "来自 AI 助手的邮件"
    body = f"用户请求：{query}"
    
    result = send_email(to, subject, body)
    state["current_status"] = "📧 发送邮件中..."
    state['research_result'] = result
    return state


# ============================================================
# 5. RAG 研究员 Agent
# ============================================================
async def rag_researcher(state: AgentState) -> AgentState:
    print(f"📚 RAG 研究员正在检索文档: {state['query']}")
    user_id = state.get('user_id', 1)
    
    from app.models.document import Document
    from app.core.database import get_db
    from sqlalchemy import select
    
    async for db in get_db():
        stmt = select(Document).where(
            Document.owner_id == user_id,
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


# ============================================================
# 6. 回复类型决策 Agent（在 answerer 之前执行）
# ============================================================
def reply_type_decision(state: AgentState) -> AgentState:
    """判断用户问题应该用文字还是语音回复"""
    query = state['query']
    context = ""
    messages = state.get('messages', {})
    if isinstance(messages, dict):
        messages_list = messages.get('data', [])
    elif isinstance(messages, list):
        messages_list = messages
    else:
        messages_list = []
    
    for msg in messages_list[-3:]:
        role = "用户" if msg.get('role') == 'user' else "助手"
        context += f"{role}: {msg.get('content', '')}\n"
    
    prompt = f"""你是回复类型决策专家，判断用户问题应该用文字还是语音回复。

对话历史：
{context if context else "（无历史对话）"}

用户当前问题：{query}

判断规则：
1. 如果用户要求唱歌、讲故事、说相声、诗歌朗诵、讲笑话等创意/娱乐内容 → 返回 audio
2. 如果用户要求模仿某个角色说话、配音等 → 返回 audio
3. 如果用户要求用语音回复 → 返回 audio
4. 如果用户上一条回复是语音，且当前问题与上一条问题相关或类似(例如：继续唱歌、继续讲故事等，那...呢？)  → 返回 audio
5. 其他情况（知识问答、天气查询、搜索、闲聊等）→ 返回 text

只返回 text 或 audio 中的一个单词，不要有其他内容。"""
    
    response = model.invoke([HumanMessage(content=prompt)])
    decision = response.content.strip().lower().replace('"', '').replace("'", "").strip()
    
    if decision not in ["text", "audio"]:
        print(f"⚠️ 未知回复类型: {decision}，默认使用 text")
        decision = "text"
    
    print(f"🔊 回复类型决策: {decision}")
    state["reply_type"] = decision
    return state


# ============================================================
# 7. 回答者 Agent：生成最终答案
# ============================================================
def answerer(state: AgentState) -> AgentState:
    """
    根据 state['reply_type'] 生成对应格式的回复
    """
    reply_type = state.get("reply_type", "text")
    print(f"回复类型: {reply_type}")
    
    # 7.1 生成内容（文字）
    if state.get('research_result'):
        prompt = f"""基于以下信息回答用户问题。

信息：
{state['research_result']}

用户问题：{state['query']}

请基于信息给出准确、简洁的回答。"""
    else:
        context = ""
        messages = state.get('messages', {})
        if isinstance(messages, dict):
            messages_list = messages.get('data', [])
        elif isinstance(messages, list):
            messages_list = messages
        else:
            messages_list = []
        
        for msg in messages_list[-3:]:
            role = "用户" if msg.get('role') == 'user' else "助手"
            context += f"{role}: {msg.get('content', '')}\n"
        
        prompt = f"""对话历史：
{context if context else "（无历史对话）"}

用户当前问题：{state['query']}

请根据对话历史理解上下文，回答用户问题。"""
    
    response = model.invoke([HumanMessage(content=prompt)])
    content = response.content
    
    # ===== 7.2 根据回复类型处理 =====
    if reply_type == "audio":
        # 第一步：转换为口语化文本
        audio_prompt = f"""将以下回答转换为适合语音朗读的版本：
- 口语化，自然流畅
- 适当增加停顿和语气词
- 去掉不适合语音的格式（如表格、列表等）
- 保持信息完整

原始回答：{content}

只返回转换后的语音文本，不要有其他内容。"""
        
        audio_response = model.invoke([HumanMessage(content=audio_prompt)])
        voice_text = audio_response.content
        state['final_answer'] = voice_text
        
        # ===== 第二步：百度 TTS 合成 =====
        try:
            audio_url = text_to_speech(voice_text) 
            if audio_url:
                state['audio_url'] = audio_url
                print(f"🔊 TTS 合成成功: {audio_url}")
            else:
                # TTS 失败，降级为文字回复
                print("❌ TTS 合成失败，降级为文字回复")
                state['reply_type'] = "text"
                state['audio_url'] = None
        except Exception as e:
            print(f"❌ TTS 异常: {e}，降级为文字回复")
            state['reply_type'] = "text"
            state['audio_url'] = None
    else:
        state['final_answer'] = content
        state['audio_url'] = None
    
    state["current_status"] = "✍️ 生成回答中..."
    return state

# ============================================================
# 8. 流式执行 Multi-Agent
# ============================================================
async def stream_multi_agent(
    query: str,
    messages: List[Dict[str, str]],
    user_id: int
):
    """流式执行 Multi-Agent"""
    import asyncio
    
    # 8.1 发送开始状态
    yield {"type": "status", "content": "🧠 正在分析问题..."}
    
    # 8.2 初始化状态
    state = {
        "query": query,
        "messages": messages,
        "research_result": "",
        "final_answer": "",
        "next_step": "",
        "user_id": user_id,
        "reply_type": "text",
        "audio_url": ""
    }
    
    # 8.3 执行 supervisor
    state = await asyncio.to_thread(supervisor, state)
    decision = state["next_step"]
    
    status_map = {
        "need_rag": "📚 正在检索文档...",
        "need_search": "🔍 正在联网搜索...",
        "need_weather": "🌤️ 正在查询天气...",
        "need_email": "📧 正在准备发送邮件...",
        "direct_answer": "✍️ 正在生成回答..."
    }
    yield {"type": "status", "content": status_map.get(decision, "⏳ 处理中...")}
    
    # 8.4 执行对应的工具 Agent
    if decision == "need_rag":
        state = await rag_researcher(state)
    elif decision == "need_search":
        state = await asyncio.to_thread(searcher, state)
    elif decision == "need_weather":
        state = await asyncio.to_thread(weather_agent, state)
    elif decision == "need_email":
        state = await asyncio.to_thread(email_agent, state)
    
    # 8.5 执行回复类型决策
    state = await asyncio.to_thread(reply_type_decision, state)
    yield {"type": "status", "content": f"🔊 正在准备{'语音' if state['reply_type'] == 'audio' else '文字'}回复..."}
    
    # 8.6 执行回答者 Agent
    state = await asyncio.to_thread(answerer, state)

    # 8.7 流式输出
    reply_type = state.get("reply_type", "text")
    if reply_type == "audio" and state.get('audio_url'):
        # 语音回复：直接返回音频 URL 和文字
        yield {"type": "reply_type", "content": "audio"}
        yield {"type": "audio", "content": state['audio_url']}  # ← 确认这行执行了
        yield {"type": "done"}
    else:
        # 文字回复：逐字输出
        yield {"type": "reply_type", "content": "text"}
        content = state['final_answer']
        for char in content:
            yield {"type": "content", "content": char}
            await asyncio.sleep(0.01)
        yield {"type": "done"}


# ============================================================
# 9. 构建 Multi-Agent 图
# ============================================================
def build_multi_agent():
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("rag_researcher", rag_researcher)
    workflow.add_node("searcher", searcher)
    workflow.add_node("weather_agent", weather_agent)
    workflow.add_node("email_agent", email_agent)
    workflow.add_node("reply_type_decision", reply_type_decision)
    workflow.add_node("answerer", answerer)
    
    # 设置入口
    workflow.set_entry_point("supervisor")
    
    # 条件边：supervisor → 各个工具
    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state["next_step"],
        {
            "need_rag": "rag_researcher",
            "need_search": "searcher",
            "need_weather": "weather_agent",
            "need_email": "email_agent",
            "direct_answer": "reply_type_decision"  # 直接进入回复类型决策
        }
    )
    
    # 工具执行后 → 回复类型决策
    workflow.add_edge("rag_researcher", "reply_type_decision")
    workflow.add_edge("searcher", "reply_type_decision")
    workflow.add_edge("weather_agent", "reply_type_decision")
    workflow.add_edge("email_agent", "reply_type_decision")
    
    # 回复类型决策 → 回答者
    workflow.add_edge("reply_type_decision", "answerer")
    
    # 回答者 → 结束
    workflow.add_edge("answerer", END)
    
    return workflow.compile()


# ============================================================
# 10. 实例化
# ============================================================
multi_agent = build_multi_agent()