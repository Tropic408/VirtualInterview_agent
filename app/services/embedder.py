import httpx

from app.core.config import settings


async def embed_texts(
    texts: list[str],
    *,
    client: httpx.AsyncClient,
    base_url: str | None = None,
    model: str | None = None,
    batch_size: int = 10,
) -> list[list[float]]:
    base_url = base_url or settings.llm_base_url
    model = model or settings.embedding_model
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = await client.post(
            f"{base_url}/embeddings",
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
            json={"model": model, "input": batch, "dimensions": 1024, "encoding_format": "float"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        if len(data) != len(batch):
            raise RuntimeError("百炼返回向量数量与输入不匹配")
        data.sort(key=lambda d: d["index"])
        all_vectors.extend(d["embedding"] for d in data)
    return all_vectors
