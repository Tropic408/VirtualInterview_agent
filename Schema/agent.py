"""三个 Agent 的结构化输出契约。

对应项目文档「三、三个 Agent 的职责与固定接口」：所有 Agent 的输出一律是
结构化 JSON，不收自由文本。出题 / 打分 / 追问三类结果在这里定义，
供 LangGraph 节点、API 层、评测脚本共用同一份口径。
"""
from typing import Literal, Annotated

from pydantic import Field, BaseModel, ConfigDict, model_validator
from pydantic_core import PydanticCustomError

#考察维度
Dimension = Literal["正确性","深度","条理","表达"]
DIMENSIONS: tuple[Dimension,...] = ("正确性","深度","条理","表达")

#题目来源：
QuestionSource = Literal["project","interview_experience"]

#会话状态
SessionStatus = Literal["active","completed","abandoned"]

#分项分数
ScoreValue = Annotated[int,Field(ge=1,le=5,description="分项分数，1-5")]

#追问深度上限
MAX_DEPTH = 3

class _StrictModel(BaseModel):
    """
    契约基类：拒绝多余字段
    模型多吐字段时静默通过会让下游拿到意料之外的数据，这里直接判错，
    比事后排查便宜。
    """
    model_config = ConfigDict(extra="forbid",str_strip_whitespace=True)

#出题agent
class QuestionItem(_StrictModel):
    id: str = Field(min_length=1,description="题目编号，如 Q1")
    dimension: Dimension
    text: str = Field(min_length=1,description="题面")
    source: QuestionSource

class QuestionBatch(_StrictModel):
    questions: list[QuestionItem] = Field(min_length=5,max_length=8)

    @model_validator(mode="after")
    def _ids_unique(self) -> "QuestionBatch":
        """
        Pydantic v2 规定 after 型模型校验器必须返回模型实例本身
        -> "QuestionBatch" 用字符串是因为函数定义时类还没创建完——类体正在执行中，
        QuestionBatch 这个名字还不存在于模块命名空间，只能写前向引用。不加引号会 NameError
        :return: 返回self：一个已经构造好的QuestionBatch实例
        """
        ids = [q.id for q in self.questions]
        #dict.fromkeys去重且保持出现顺序：出现次数>1即为重复项
        dup = [i for i in dict.fromkeys(ids) if ids.count(i)>1]
        if dup:
            raise PydanticCustomError(
                "duplicate_question_id",
                "同一批题目的id重复：{ids}",
                {"ids":"，".join(dup)}
            )
        return self

#打分agent
class DimensionScores(_StrictModel):
    """
    分项打分，不给默认值，打分必须强制填写每个字段
    """
    正确性: ScoreValue
    深度: ScoreValue
    条理: ScoreValue
    表达: ScoreValue
    def mean(self)->float:
        """四项平均分，仅展示"""
        return sum(getattr(self,d) for d in DIMENSIONS)/len(DIMENSIONS)

class ScoreResult(_StrictModel):
    question_id: str = Field(min_length=1)
    scores: DimensionScores
    on_topic: bool = Field(default=True,description="答案是否切题；False表示跑题")
    comment: str=Field(min_length=1,description="点评，必须说明扣分点")
    evidence: list[str] = Field(
        default_factory = list,
        description="打正确性时引用的项目材料片段，落实[结论必须引用项目材料]",
    )

#追问agent
class FollowUp(_StrictModel):
    question_id: str = Field(min_length=1,description="被追问的问题 id")
    depth: int = Field(ge=1,le=MAX_DEPTH,description="追问层级，1 为第一次追问")
    template_id: str = Field(default="",description="命中的追问链模板 id")
    text: str = Field(min_length=1,description="追问的话术")