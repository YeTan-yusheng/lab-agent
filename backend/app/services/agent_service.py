from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from typing import Any
from collections.abc import AsyncIterator

from app.schemas.ai import ChatRequest
from app.config import settings
from app.models.user import User
from app.services import agent_tools
from app.core.exceptions import BusinessException
from app.core.permissions import get_role_profile

SYSTEM_PROMPT = """你是智能实验室预约系统的 Agent，回答要简洁。
你可以：
1. 使用 search_lab_docs 查询实验室的规则、安全、开放时间等问题
2. 使用 list_open_labs / list_lab_equipments  查询真实的实验室和设备
3. 在用户进行了预约确认后，使用 create_equipment_reservation 预约设备室或 create_lab_reservation 预约实验室来进行真实的预约落库
4. 使用 get_today 来进行日期的换算
## 必须遵守
当用户问你当前的能力时，你必须根据用户所拥有的 tools 来回答，不能瞎编，不能提及用户没有的能力。
当用户要求你进行预约时，你必须先确认用户是否有相应的能力，如果没有，必须拒绝。
当用户提到了 今天、明天、后天 等日期相关的问题，请先调用 get_today 来获取日期，**不要直接返回 我需要确定明天的具体日期**。
在提交预约之前必须向用户复述：实验室ID与名称（或设备ID和名称）、日期、开始时间、结束时间。并得到用户确认再进行实际操作。
用户没说【确认】【确认预约】【就这样预约】等确定性回复之前，不要调用 create_lab_reservation和create_equipment_reservation。
工作流的确认环节里如果缺少了 lab_id，请先 list_open_labs 查到了 lab_id 再创建，不要瞎写。
工作流的确认环节里如果缺少了 equipment_id，请先 list_lab_equipments 查到了 equipment_id 再创建，不要瞎写。
预约成功后状态是待审核，必须管理员确认后实验室（或设备）才能使用。
不要瞎编数据库里没有的实验室或者设备信息。
如果是问开放时间或者实验室规则，优先调用 search_lab_docs，不要凭空回复。
"""

TOOL_LABELS = {
    "search_lab_docs": "检索实验室知识库",
    "list_open_labs": "查询开放实验室",
    "list_lab_equipments": "查询实验室设备",
    "create_equipment_reservation": "预约设备",
    "create_lab_reservation": "预约实验室",
    "get_today": "获取今天日期",
}


def build_agent(db: Session, current_user: User):
    profile = get_role_profile(current_user)
    tools = agent_tools.build_tools(db, current_user, profile)
    llm = ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model_name=settings.llm_model,
        temperature=0,
        streaming=True,
    ).bind_tools(tools)

    async def agent_node(state: MessagesState):
        """langGraph 执行的工作流 的节点"""
        response = await llm.ainvoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()


def _chunk_text(chunk: Any) -> str:
    """从大模型返回的 chunk 中提取文本内容"""
    if chunk is None:
        return ""
    # chunk 可能是 dict、str、list 等类型，尝试从中提取 content
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return str(content) if content is not None else ""


def _tool_output_preview(output: Any, limit: int = 200) -> str:
    """短预览工具调用"""
    if isinstance(output, ToolMessage):
        output = output.content
    text = output if isinstance(output, str) else str(output)
    return text if len(text) <= limit else text[:limit] + "..."


def _build_history(data: ChatRequest) -> list:
    """构建历史消息"""
    history = []
    for message in data.messages:
        if message.role == "user" and message.content.strip():
            history.append(HumanMessage(content=message.content.strip()))
        elif message.role == "assistant" and message.content.strip():
            history.append(AIMessage(content=message.content.strip()))
    if not history:
        raise BusinessException(message="请输入您要对话的内容")
    return history


async def stream_agent(
    db: Session, current_user: User, data: ChatRequest
) -> AsyncIterator[dict]:
    """流式大模型对话"""
    try:
        history = _build_history(data)
        agent = build_agent(db, current_user)
        inputs = {"messages": [SystemMessage(content=SYSTEM_PROMPT), *history]}

        yield {"type": "status", "message": "正在思考..."}

        async for event in agent.astream_events(
            inputs,
            version="v2",
            config={"recursion_limit": 10},
        ):
            kind = event.get("event")
            if kind == "on_tool_start":
                name = event.get("name") or ""
                yield {
                    "type": "tool_start",
                    "name": name,
                    "label": TOOL_LABELS.get(name, name),
                }
            elif kind == "on_tool_end":
                name = event.get("name") or ""
                yield {
                    "type": "tool_end",
                    "name": name,
                    "label": TOOL_LABELS.get(name, name),
                    "preview": _tool_output_preview(
                        (event.get("data") or {}).get("output")
                    ),
                }
            elif kind == "on_chat_model_stream":
                metadata = event.get("metadata") or {}
                if metadata.get("langgraph_node") not in ("agent", None):
                    continue
                text = _chunk_text((event.get("data") or {}).get("chunk"))
                if text:
                    yield {"type": "token", "content": text}
        yield {"type": "done"}
    except BusinessException as exc:
        yield {"type": "error", "message": exc.message}
    except Exception as e:
        print(e)
        yield {"type": "error", "message": "大模型调用失败，请稍后重试"}
