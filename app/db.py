import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://library:library@localhost:5433/library",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # Pool sized for concurrent request handling; pre-opened to avoid
    # cold-connection latency on first requests after a burst.
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async session."""
    async with SessionLocal() as session:
        yield session
