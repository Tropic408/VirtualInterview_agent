import httpx

from app.services.llm import chat


async def generate(question: str, hits: list[dict], *, client: httpx.AsyncClient) -> str:
    context = "\n\n".join(f"[{i + 1}]{h['text']}" for i, h in enumerate(hits))

    messages = [
        {
            "role": "system",
            "content": "你是一名知识库问答助手，根据用户提供的资料进行回答，"
                       "资料里没有的信息请说'资料中未提及'，"
                       "回答末尾用[编号]标注引用了哪几条资料",
        },
        {
            "role": "user",
            "content": f"资料：\n{context}\n\n问题：{question}",
        },
    ]
    return await chat(messages, client=client)
