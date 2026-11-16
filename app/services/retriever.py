#检索层

import httpx
from qdrant_client import AsyncQdrantClient

from app.services.embedder import embed_texts


async def retrieve(question: str,*,client: httpx.AsyncClient,qdrant: AsyncQdrantClient,top_k: int = 5):
    vector = (await embed_texts([question], client=client))[0]
    resp = await qdrant.query_points(
        collection_name = "rag_kb",
        query = vector,
        limit = top_k,
        with_payload = True,
    )
    return [{"score":p.score,**p.payload} for p in resp.points]
