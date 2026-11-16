from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.generator import generate
from app.services.retriever import retrieve


class ChatRequest(BaseModel):
    question: str

router = APIRouter()


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    hits = await retrieve(
        req.question,
        client=request.app.state.http_client,
        qdrant=request.app.state.qdrant,
    )
    answer = await generate(req.question,hits,client=request.app.state.http_client)
    citations = [{"source":h["source"],
                  "chunk_id":h["chunk_id"],
                  "text":h["text"][:128],
                  "score":round(h["score"],4)
                  }
                 for h in hits
                 ]
    return {"answer":answer,"citations":citations}