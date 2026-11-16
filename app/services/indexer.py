#入库：qdrant + mysql 登记
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance,PointStruct


async def ensure_collection(qdrant: AsyncQdrantClient, name="rag_kb", dim=1024):
    if not await qdrant.collection_exists(name):
        await qdrant.create_collection(name, vectors_config=VectorParams(size=dim,distance=Distance.COSINE))

async def upsert_chunks(qdrant:AsyncQdrantClient,doc_id:str,source:str,chunks:list[str],vectors:list[list[float]],name="rag_kb"):
    points = [PointStruct(id=str(uuid.uuid4()),
                          vector = v,
                          payload={"doc_id":doc_id,"chunk_id":f"{doc_id}-{i}",
                                   "text":t,"source":source,"chunk_index":i,"section":""},
                          ) for i ,(t,v) in enumerate(zip(chunks,vectors))]
    await qdrant.upsert(collection_name=name,points=points)