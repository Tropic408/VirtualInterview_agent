"""面经离线打标的契约。

与 Schema/agent.py 分开的理由：那边定义的是「三个 Agent 的运行时输出」，
这边是「入库前的一次性标注」，生命周期不同——Agent 契约改一次要动 prompt，
打标契约改一次只是重跑脚本。
"""

from pydantic import BaseModel, ConfigDict, Field

from Schema.agent import DimensionScores


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid",str_strip_whitespace=True)

class ExperienceTag(_Strict):
    seq: int=Field(ge=1,description="题目在原文档里的序号")
    dimension: DimensionScores
    intent: str = Field(min_length=1,description="考察意图，一句话")
    followup_chain: list[str] = Field(default_factory=list,description="追问链，递进追问下去")
    tags: list[str] = Field(default_factory=list,description="涉及的技术标签")

class ExperienceTagBatch(_Strict):
    records: list[ExperienceTag] = Field(min_length=1)