"""三个角色的节点实现。

约定：
- 节点只做「拼 prompt + 调模型 + 返回 state 增量」，不碰数据库；
  落库由 service 层负责，这样节点可以脱离 DB 单测。
- client 用闭包注入（与项目里其他服务一致：客户端由调用方传入，不用模块级单例）。
"""
import httpx

from Schema.agent import QuestionBatch, FollowUp, ScoreResult
from app.graph.prompts import QUESTIONER_SYSTEM, questioner_user, FOLLOWUP_SYSTEM, followup_user, SCORER_SYSTEM, \
    scorer_user
from app.graph.state import InterviewState, MAX_QUESTIONS, MAX_DEPTH, LOW_SCORE
from app.services.llm import chat_json

QUESTION_TEMPERATURE = 0.8
SCORE_TEMPERATURE = 0.0 #打分要可复现
FOLLOWUP_TEMPERATURE = 0.7

def _mean(score:dict|None)->float:
    if not score:
        return 0.0
    s = score.get("scores") or {}
    return sum(s.get(d,0) for d in ("正确性","深度","条理","表达"))/4

def make_plan_node(client:httpx.AsyncClient):
    async def plan(state:InterviewState)->dict:
        batch = await chat_json(
            [{"role":"system","content":QUESTIONER_SYSTEM},
            {"role":"user","content":questioner_user(state["position"],
                                                     state.get("profile_summary"," "),
                                                     state.get("experience_records")
                                                     )}],
            schema=QuestionBatch,client=client,temperature=QUESTION_TEMPERATURE,
        )
        questions = [q.model_dump() for q in batch.questions][:MAX_QUESTIONS]
        return {
            "questions":questions,"cursor": 0,"asked_count": 0,
            "current_depth": 0,"low_score_streak": 0,
            "downgrade_used": False,"redirect_used": False, "ended":False,
        }
    return  plan

def make_ask_node(client: httpx.AsyncClient):
    async def ask(state: InterviewState) -> dict:
        action = state.get("next_action", "next")

        if action in ("followup", "downgrade", "redirect"):
            cur = state["current_question"]
            score = state.get("current_score") or {}
            fu = await chat_json(
                [{"role": "system", "content": FOLLOWUP_SYSTEM},
                 {"role": "user", "content": followup_user(
                     cur["text"], state.get("current_answer", ""),
                     score.get("comment", ""),
                     state.get("current_depth", 0) + 1, action,
                     "",
                     cur.get("id","Q1"),
                     "",
                 )}],
                schema=FollowUp, client=client, temperature=FOLLOWUP_TEMPERATURE,
            )
            depth = state.get("current_depth", 0) + 1
            return {
                "current_question": {
                    "id": fu.question_id, "dimension": cur["dimension"],
                    "text": fu.text, "source": "project",
                    "parent_id": cur.get("id"), "depth": depth,
                    "template_id": fu.template_id,
                },
                "current_depth": depth,
                "asked_count": state.get("asked_count", 0) + 1,
            }

        # 下一道首问
        cursor = state.get("cursor", 0)
        questions = state.get("questions", [])
        if cursor >= len(questions):
            return {"ended": True, "should_continue": False, "current_question": None,
                    "next_action": "finish"}
        q = questions[cursor]
        return {
            "current_question": {**q, "parent_id": None, "depth": 0, "template_id": None},
            "current_depth": 0,
            "cursor": cursor + 1,
            "asked_count": state.get("asked_count", 0) + 1,
        }
    return ask


def make_score_node(client: httpx.AsyncClient):
    async def score(state: InterviewState) -> dict:
        q = state["current_question"]
        result = await chat_json(
            [{"role": "system", "content": SCORER_SYSTEM},
             {"role": "user", "content": scorer_user(
                 q["text"], state.get("current_answer", ""), state.get("profile_summary", ""),q["dimension"])}],
            schema=ScoreResult, client=client, temperature=SCORE_TEMPERATURE,
        )
        mean = _mean(result.model_dump())
        streak = state.get("low_score_streak", 0) + 1 if mean <= LOW_SCORE else 0
        return {"current_score": result.model_dump(), "low_score_streak": streak}
    return score


def decide(state: InterviewState) -> dict:
    """条件边的判定函数：把文档里的四条退出规则压成一条优先级链。

    顺序不能乱：
    1. 题量封顶最优先——否则会无限问下去
    2. 跑题先处理——跑题的分数天然很低，不能让它落到"低分降级"分支
    3. 深度到顶再换题
    4. 低分降级一次，仍低则换题
    5. 其余情况往深挖
    """
    asked = state.get("asked_count", 0)
    depth = state.get("current_depth", 0)
    score = state.get("current_score") or {}
    mean = _mean(score)
    exhausted = state.get("cursor", 0) >= len(state.get("questions", []))

    def _next():
        if exhausted:
            return {"next_action": "finish", "should_continue": False, "ended": True}
        return {"next_action": "next", "should_continue": True}

    if asked >= MAX_QUESTIONS:
        return {"next_action": "finish", "should_continue": False, "ended": True}

    if not score.get("on_topic", True):
        if not state.get("redirect_used"):
            return {"next_action": "redirect", "redirect_used": True, "should_continue": True}
        return _next()

    if depth >= state.get("max_depth", MAX_DEPTH):
        return _next()

    if mean <= LOW_SCORE:
        if not state.get("downgrade_used"):
            return {"next_action": "downgrade", "downgrade_used": True, "should_continue": True}
        return _next()

    return {"next_action": "followup", "should_continue": True}


def finish(state: InterviewState) -> dict:
    return {"ended": True, "should_continue": False, "current_question": None}