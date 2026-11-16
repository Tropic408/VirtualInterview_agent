import time

from fastapi import APIRouter, Request
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from datetime import datetime

from app.core.config import settings

router = APIRouter()

async def _probe(name:str, fn):
    """
    单个探针：计时＋兜底，失败只记录结果，不炸整个接口
    """
    start = time.perf_counter()
    try:
        await fn()
        return {"ok":True,"latency_ms":round((time.perf_counter()-start)*1000,1)}
    except Exception as e:
        return {"ok":False,"latency_ms":None,"error":str(e)[:120]}

def _mysql_ping(engine):
    """MySQL探针：最小业务查询，engine是同步的，放线程池执行"""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

async def _model_ping(http,base_url: str,api_key: str,model_name: str):
    payload = {
        "model":model_name,
        "messages":[{"role":"user","content":"ping"}],
        "max_tokens": 1,
        "stream":False
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    r = await http.post(f"{base_url}/chat/completions",json=payload,headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP{r.status_code}")

@router.get("/health")
async def health_check(request: Request):
    st = request.app.state
    checks = {
        "redis": await _probe("redis",lambda :st.redis.ping()),
        "qdrant": await _probe("qdrant",lambda :st.qdrant.get_collections()),
        "mysql": await _probe("mysql",lambda : run_in_threadpool(_mysql_ping,st.mysql_engine)),
        "model": await _probe("model",lambda: _model_ping(st.http_client,settings.llm_base_url,settings.dashscope_api_key,settings.llm_model)),
    }
    ok = sum(1 for c in checks.values() if c["ok"])
    total = len(checks)
    if ok == total:
        status, code = "ok", 200
    elif ok>0:
        status, code = "degraded",200
    else:
        status, code = "unhealthy",503
    return JSONResponse(
        {"status":status,"checks":checks,"timestamp":datetime.now().isoformat(timespec="seconds")},
        status_code=code,
    )