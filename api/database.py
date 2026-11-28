import os
from functools import lru_cache
from sqlalchemy import URL
from sqlmodel import Session, create_engine


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "pathfinder"),
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        database=os.getenv("POSTGRES_DB", "pathfinder"),
    )


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(database_url(), pool_pre_ping=True)


def get_session():
    with Session(get_engine()) as session:
        yield session
