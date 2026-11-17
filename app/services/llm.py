"""大模型调用收敛层。

把「怎么调百炼」收在这里：base_url / model / api key 一律来自 settings，
上层只关心 messages 和要拿回什么。三个 Agent 与原有的 RAG 生成共用这一个入口。

约定：
- client 由调用方传入（与 embedder / retriever / generator 一致，不用模块级单例）；
- 不吞异常：失败一律抛 LLMError，调用方决定是重试、降级还是报 500；
- JSON 模式用百炼的 response_format，接口要求 messages 里出现 "json" 字样，
  否则直接 400，所以 chat_json 会自己补一句系统提示。
"""
from typing import TypeVar, Any

import httpx
from pydantic import BaseModel
from pydantic import ValidationError

from app.core.config import Settings, settings

ModelT = TypeVar("ModelT", bound=BaseModel)

DEFAULT_TIMEOUT = 120.0

class LLMError(RuntimeError):
    """调用百炼失败：HTTP 非 200、返回结构不符合 OpenAI 兼容格式、JSON 校验不过。"""

#-------------底层------------------

async def _request(
        client: httpx.AsyncClient,
        base_url: str,
        payload: dict[str, Any],
        timeout: float
)->str:
    """发一次/chat/completions,返回content原文"""
    resp = await client.post(
        f"{base_url}/chat/completions",
        headers={"Authorization":f"Bearer {settings.dashscope_api_key}"},
        json=payload,
        timeout=timeout,
    )

    if resp.status_code != 200:
        raise LLMError(f"HTTP {resp.status_code}:{resp.text[:300]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError,KeyError,IndexError,TypeError) as e:
        raise LLMError(f"返回结构异常: {resp.text[:300]}") from e
    if not isinstance(content,str) or not content.strip():
        raise LLMError(f"返回内容为空(可能被安全策略拦截)：{resp.text[:300]}")
    return content

def _resolve(base_url: str|None,model: str|None)->tuple[str,str]:
    return (base_url or settings.llm_base_url).rstrip("/"),model or settings.llm_model

#-----------纯文本--------------------------
async def chat(
        messages: list[dict[str,Any]],
        *,
        client: httpx.AsyncClient,
        base_url: str|None = None,
        model: str|None = None,
        temperature: float|None = None,
        timeout: float = DEFAULT_TIMEOUT,
)->str:
    """普通对话。temperature为None时不传该字段，沿用服务端默认值"""
    base,name = _resolve(base_url,model)
    payload: dict[str,Any] = {"model":name,"messages":messages,"stream":False}
    if temperature is not None:
        payload["temperature"] = temperature
    return await _request(client,base,payload,timeout)

#-----------结构化输出-----------------------
def _ensure_json_hint(messages: list[dict[str,Any]])->list[dict[str,Any]]:
    """百炼json模式要求message里出现json，缺了就补一句系统提示"""
    joined = "".join(str(m.get("content")) for m in messages).lower()
    if "json" in joined:
        return list(messages)
    return [
        {"role":"system","content":"主输出一个JSON对象，不要解释文字，不要Markdown代码块"},
        *messages,
    ]

def _strip_code_fence(text:str)->str:
    """模型偶尔仍会用```json包一层，剥掉再解析"""
    s = text.strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()[1:]
    if lines and lines[-1].strip()=="```":
        lines = lines[:-1]
    return "\\n".join(lines).strip()

def _repair_hint(error:ValidationError|None)->str:
    """把pydantic的错误压成能返回给模型的提示"""
    if error is None:
        return "输出不是合法JSON"
    problems = []
    for err in error.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<根对象>"
        problems.append(f"{loc}:{err['msg']}")
    return "上一次输出不合法："+"；".join(problems)+"请修正后只输出JSON"


async def chat_json(
        messages: list[dict[str,Any]],
        *,
        schema: type[ModelT],
        client: httpx.AsyncClient,
        base_url: str|None = None,
        model: str|None = None,
        temperature: float|None = None,
        max_attempts: int = 2,
        timeout: float = DEFAULT_TIMEOUT,
)->ModelT:
    """要求模型输出符合schema的JSON，校验不过就带着错误信息重试
    重试策略：把上一次的原文和「哪里不合法」追加进对话再问一次，共 max_attempts 次。
    只对「JSON 解析失败 / schema 校验失败」重试；HTTP 错误直接抛，避免对 401 无意义重试
    """
    if max_attempts<1:
        raise ValueError("max_attempts至少为1")

    base,name = _resolve(base_url,model)
    convo = _ensure_json_hint(messages)
    last_error: ValidationError | None = None

    for attempt in range(1,max_attempts+1):
        payload: dict[str,Any] = {
            "model":name,
            "messages":convo,
            "stream":False,
            "response_format":{"type":"json_object"},
        }
        if temperature is not None:
            payload["temperature"] = temperature

        content = await _request(client,base,payload,timeout)
        try:
            return schema.model_validate_json(_strip_code_fence(content))
        except ValidationError as e:
            last_error = e
            if attempt>=max_attempts:
                break
            convo = [
                *convo,
                {"role":"assistant","content":content},
                {"role":"user","content":_repair_hint(e)}
            ]

    raise LLMError(
        f"{schema.__name__}校验失败（已重试{max_attempts}次:{_repair_hint(last_error)}）"
    )from last_error