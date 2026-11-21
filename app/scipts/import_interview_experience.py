"""面经结构化入库（阶段 F1）。

输入：rag_kb 里某份面经文档的全文（默认 test001.docx）
流程：切题 → LLM 打标（维度 / 考察意图 / 追问链）→ 写 MySQL + experience_kb
输出：interview_experiences N 条、experience_kb N 个点

幂等：id 由 uuid5(NAMESPACE, "source#seq") 决定，重跑是覆盖不是追加。
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOURCE = "test001.docx"
RAG_COLLECTION = "rag_kb"
EXPERIENCE_COLLECTION = "experience_kb"

# 固定命名空间：换机器、换时间跑出来的 id 都一样
NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

TAG_SYSTEM = """你在给一份技术面经打标，产出供模拟面试系统选用的结构化题型。

对每道题给四个字段：
1. dimension：主考维度，只能取 正确性/深度/条理/表达
   - 考"事实对不对、知不知道"→ 正确性
   - 考"为什么这么做、取舍、边界"→ 深度
   - 考"整体设计是否分得清主次"→ 条理
   - 考"表达是否清楚"→ 表达
2. intent：这道题真正想考察什么，一句话，不超过 40 字
3. followup_chain：候选人答得好时，往下追问的 2–3 个递进问题（越往后越具体）
4. tags：涉及的技术标签，2–4 个

只输出 JSON，不要解释：
{"records":[{"seq":1,"dimension":"深度","intent":"...","followup_chain":["...","..."],"tags":["RAG"]}]}
必须覆盖全部题目，seq 与输入编号一致，不能漏题。
"""