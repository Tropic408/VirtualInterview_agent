"""LangGraph 会话状态与状态机常量。

为什么用 TypedDict 而不是 Pydantic：
LangGraph 的 state 只要求是「可合并的映射」，节点返回的 dict 会被浅合并进 state。
用 Pydantic 的话每个节点都要 model_dump() 再合并，多一层无收益的转换。
total=False 表示所有字段都可选——第一次调用时 state 里只有 session_id 和 position。
"""

from typing import TypedDict

#---状态机阈值（文档【追问四条退出规则】的落地参数）
MAX_DEPTH = 3
MAX_QUESTIONS = 6
LOW_SCORE = 2

class InterviewState(TypedDict,total=False):
    #---会话---
    session_id: str
    position: str
    profile_summary: str
    experience_records: list|None
    evidence: list|None
    max_depth: int
    #---题池---
    questions: list[dict] #QuestionItem序列化后的全部首问
    cursor: int #下一道首问的下标
    asked_count: int #已提问总数（含追问），用于封顶
    #---当前回合---
    current_question: dict|None
    current_answer: str
    current_score: dict|None
    current_depth: int #0首问，1...3 追问层
    #---决策---
    next_action: str # followup | downgrade | redirect | next | finish
    low_score_streak: int
    downgrade_used: bool # 降级换角度是否已用过
    redirect_used: bool   # 跑题拉回是否已用过
    should_continue: bool
    ended: bool