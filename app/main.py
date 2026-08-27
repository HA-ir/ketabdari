from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import engine
from .models import Book, Rental, User  # noqa: F401  (register models)
from .routers import books, rentals, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (simple; use Alembic for production migrations)
    from sqlmodel import SQLModel

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Library Management API",
    description="مدیریت کتابخانه — یوزرها، کتاب‌ها و اجاره (rental)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(books.router)
app.include_router(rentals.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}