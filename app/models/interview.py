"""v1 的四张表：会话 / 题目 / 回答打分 / 面经存储箱。

表结构直接对应文档「三、三个 Agent 的固定接口」：
  QuestionItem  → questions
  ScoreResult   → answers（四个分项 + comment + evidence）
  FollowUp      → questions（parent_id + depth + template_id，见下方说明）
  SessionStatus → interview_sessions.status
"""
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Interview(Base):
    """一场面试。断线恢复、历史列表、画像层都从这张表出发。"""

    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36),primary_key=True)
    position: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16),default="active",index=True)
    #用户画像层快照: 存快照而不是实时算，是为了让历史记录可复现
    profile_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime,server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,server_default=func.now(),onupdate=func.now()
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="session",cascade="all,delete-orphan"
    )

class Question(Base):
    """题目。首问和追问共用这一张表。

    depth=0 是首问，depth>=1 是追问；parent_id 指向追问链的上一环。
    这样「Q1 → F1 → F2」就是三行同一张表、parent_id 串起来的树。
    选择复用的核心理由：追问链是递归结构，而 answers 表只需要一个父指针。
    """

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36),primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36),ForeignKey("interview_sessions.id",ondelete="cascade"),index=True
    )

    seq: Mapped[int] = mapped_column(SmallInteger) #会话内第几题
    dimension: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(24)) #project|interview_experience

    # 自引用外键（指向本表的 id）。没有建 ForeignKey 约束，因为追问链删除
    # 一律跟随 session 级联，单独校验父指针意义不大，还能省一次索引维护。
    parent_id: Mapped[str|None] = mapped_column(String(36),index=True)

    depth: Mapped[int] = mapped_column(SmallInteger,default=0)
    template_id: Mapped[str|None] = mapped_column(String(36))

    created_at: Mapped[datetime] = mapped_column(DateTime,server_default=func.now())

    session: Mapped[Interview] = relationship(back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="question",cascade="all,delete-orphan"
    )

class Answer(Base):
     """一次作答及其评分结果。

    刻意不设「总分」列：文档要求绝不直接甩总分。
    需要总分时在查询里算 AVG 或 SUM，保证四个分项是唯一事实来源。
    """
     __tablename__ = "answers"

     id: Mapped[str] = mapped_column(String(36), primary_key=True)
     question_id: Mapped[str] = mapped_column(
         String(36), ForeignKey("questions.id", ondelete="CASCADE"), index=True
     )

     text: Mapped[str] = mapped_column(Text)

     # SmallInteger 范围 ±32767，装 1–5 的分足够，比 Integer 省一半空间。
     # 可空：用户还没作答/还没打分时为 NULL，而不是填 0——
     # 0 会被 AVG 当成真实分数拉低均值，NULL 不会被聚合函数计入。
     score_correctness: Mapped[int | None] = mapped_column(SmallInteger)
     score_depth: Mapped[int | None] = mapped_column(SmallInteger)
     score_structure: Mapped[int | None] = mapped_column(SmallInteger)
     score_expression: Mapped[int | None] = mapped_column(SmallInteger)

     comment: Mapped[str | None] = mapped_column(Text)
     evidence_json: Mapped[str | None] = mapped_column(Text)

     created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

     question: Mapped[Question] = relationship(back_populates="answers")


class ExperienceItem(Base):
    """面经存储箱。

        文档的双结构在这里落地：
          原文块 raw_text   → 走向量库（Qdrant 里的点由 point_id 反查回这一行）
          结构化字段        → 只做元数据，不参与 embedding
        先按标签过滤，再用向量排序
        """

    __tablename__ = "interview_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 指向 Qdrant 里的点 id。建索引是为了「从向量命中反查原文」这个方向的查询。
    point_id: Mapped[str | None] = mapped_column(String(36), index=True)

    raw_text: Mapped[str] = mapped_column(Text)
    dimension: Mapped[str] = mapped_column(String(32))
    followup_template: Mapped[str | None] = mapped_column(Text)
    tags_json: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())