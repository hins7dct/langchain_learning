"""
数据库连接层：engine / session 工厂 / 事务边界。

分层约定：
    db.py         连接与事务（全局唯一创建 engine 的地方）
    models.py     表结构 + 纯内存计算属性
    repository.py 查询（构造函数注入 session，内部绝不 commit）
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


# 用 URL.create 而不是 f-string 拼 DSN：密码含 @ / : / % 时不会被解析错位
DATABASE_URL = URL.create(
    "postgresql+psycopg",
    username=settings.pg_user,
    password=settings.pg_password,
    host=settings.pg_host,
    port=settings.pg_port,
    database=settings.pg_database,
)

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # Docker 容器重启后旧连接会失效，取连接前先探活
    echo=False,           # 调 SQL 时临时改 True
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务边界：正常退出提交，异常回滚。

    Repository 内部不要再调 commit()，否则跨 Repository 的操作无法原子提交。
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(*, drop: bool = False) -> None:
    """建表。仅用于空库；已有 schema.sql 建好的表用不到这个函数。"""
    import models  # noqa: F401  把模型注册到 Base.metadata

    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def get_url_safe() -> str:
    """打日志用，密码显示为 ***。"""
    return DATABASE_URL.render_as_string(hide_password=True)