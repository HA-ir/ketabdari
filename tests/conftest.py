import asyncio
import datetime
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel

# Set test database URL before importing app components
os.environ["DATABASE_URL"] = "postgresql+asyncpg://library:library@localhost:5433/library_test"

from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Book, Rental, User  # noqa: E402


def future_date(days: int = 14) -> str:
    d = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def past_date(days: int = 3) -> str:
    d = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    # Fresh schema per test
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(client: AsyncClient) -> dict[str, list[int]]:
    """Seed 2 users and 3 books, return their IDs."""
    u1 = await client.post("/api/v1/users", json={"name": "Hossein", "email": "h@x.com"})
    u2 = await client.post("/api/v1/users", json={"name": "Sara", "email": "s@x.com"})
    b1 = await client.post("/api/v1/books", json={"title": "Pragmatic Programmer", "author": "Hunt", "quantity": 1})
    b2 = await client.post("/api/v1/books", json={"title": "Clean Code", "author": "Martin", "quantity": 1})
    b3 = await client.post("/api/v1/books", json={"title": "Clean Architecture", "author": "Martin", "quantity": 1})
    assert all(r.status_code == 201 for r in (u1, u2, b1, b2, b3))
    return {
        "users": [u1.json()["id"], u2.json()["id"]],
        "books": [b1.json()["id"], b2.json()["id"], b3.json()["id"]],
    }
