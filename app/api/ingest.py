import uuid

from fastapi import APIRouter, Request, UploadFile, File
from starlette.concurrency import run_in_threadpool

from app.services.chunker import chunk_text
from app.services.embedder import embed_texts
from app.services.indexer import ensure_collection, upsert_chunks
from app.services.parser import parse

router = APIRouter()

@router.post("/api/ingest")
async def ingest(request:Request,file: UploadFile=File(...)):
    st = request.app.state

    data = await file.read()
    text = await run_in_threadpool(parse,file.filename,data)
    chunks = chunk_text(text,500,50)
    vectors = await embed_texts(chunks,client=st.http_client)
    doc_id = str(uuid.uuid4())
    await ensure_collection(st.qdrant,"rag_kb")
    await upsert_chunks(st.qdrant,doc_id,file.filename,chunks,vectors)
    return {"doc_id":doc_id,"chunks_count":len(chunks),"status":"ok"}
