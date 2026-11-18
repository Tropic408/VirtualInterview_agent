"""数据库连接与建表。

被三个地方用到：
  main.py 的 lifespan  → 拿 engine 挂到 app.state，供 /health 探针复用
  main.py 的 lifespan  → 调 init_models() 建表
  以后的接口/服务     → get_session() 作为 FastAPI 依赖注入

这里只放「连接」和「建表」，不放业务查询——业务查询属于各自的 service，
否则 db.py 会变成一个什么都往里塞的杂物间。
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import Settings, settings
from app.models.base import Base

engine = create_engine(
    settings.mysql_dsn,pool_pre_ping=True,connect_args={"connect_timeout":2}
)

#   autoflush=False     默认是 True，会在每次查询前自动 flush 掉未提交的改动。
#                       显式控制提交时机会更可预期，也便于排查「为什么多了条 UPDATE」。
#   expire_on_commit=False  commit 后默认会把对象属性标记为过期，下次访问触发额外 SELECT。
#                       关掉它在 Web 场景里更省查询；代价是脏数据可能被读到，
#                       这里的取舍是「少一次查询」优先。
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def init_models()->None:
    # 这行 import 看起来没用，其实是关键：
    # Base.metadata 是「所有表定义的注册表」，但只有 interview.py 被 import 过，
    # 那些类才会注册进来。如果这里不 import，create_all 会安静地什么都不建。
    # noqa 是告诉 flake8「别报我未使用」。
    import app.models.interview  # noqa: F401

    Base.metadata.create_all(engine)

def get_session()->Iterator[Session]:
    """FastAPI 依赖：一个请求一个 Session，请求结束即关。

    用 yield 而不是 return，是因为 FastAPI 依赖支持「后置清理」——
    yield 之后的部分在响应返回后执行，保证连接一定归还连接池。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()