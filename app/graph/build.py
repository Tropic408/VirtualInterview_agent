"""两条子图的组装。

为什么拆成两张图而不是一张：
用户答一题是一次 HTTP 请求，图不跨请求存活，状态以 MySQL 为准。
于是「开场」和「答题回合」天然是两个入口，拆开后每条路径都短、都能单测。
"""
import httpx
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    decide, finish, make_ask_node, make_plan_node, make_score_node,
)
from app.graph.state import InterviewState

# decide 返回的 next_action → 目标节点
_ROUTE = {
    "followup": "ask",
    "downgrade": "ask",
    "redirect": "ask",
    "next": "ask",
    "finish": "finish",
}


def build_start_graph(client: httpx.AsyncClient):
    """开场：出题 → 提问第一道。"""
    g = StateGraph(InterviewState)
    g.add_node("plan", make_plan_node(client))
    g.add_node("ask", make_ask_node(client))
    g.add_edge(START, "plan")
    g.add_edge("plan", "ask")
    g.add_edge("ask", END)
    return g.compile()


def build_answer_graph(client: httpx.AsyncClient):
    """答题回合：打分 → 决策 → 追问/下一题/收尾。"""
    g = StateGraph(InterviewState)
    g.add_node("score", make_score_node(client))
    g.add_node("decide", decide)
    g.add_node("ask", make_ask_node(client))
    g.add_node("finish", finish)

    g.add_edge(START, "score")
    g.add_edge("score", "decide")
    g.add_conditional_edges("decide", lambda s: s["next_action"], _ROUTE)
    g.add_edge("ask", END)
    g.add_edge("finish", END)
    return g.compile()