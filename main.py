from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from qdrant_client import AsyncQdrantClient
import redis.asyncio as aioredis

from app.api.routes import health
from app.api.chat import router as chat_router
from app.api.ingest import router as ingest_router

from app.core.config import settings
from app.core.db import engine, init_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 各依赖连接只建一次，注入 app.state，/health 复用（不每次新建）
    app.state.redis = aioredis.from_url(
        settings.redis_url, socket_timeout=2, decode_responses=True
    )
    app.state.qdrant = AsyncQdrantClient(url=settings.qdrant_url, timeout=2)
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(2.0))
    app.state.mysql_engine = engine
    init_models()

    yield

    # 关闭：每个 client 用各自的异步关闭方法
    await app.state.redis.aclose()
    await app.state.qdrant.close()
    await app.state.http_client.aclose()
    app.state.mysql_engine.dispose()

app = FastAPI(title="rag_db",lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


app.include_router(health.router)
app.include_router(chat_router)
app.include_router(ingest_router)