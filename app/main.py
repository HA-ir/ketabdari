from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .core.exceptions import register_exception_handlers
from .db.session import engine
from .models import Book, Rental, User  # noqa: F401 (ensure models registered on metadata)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from sqlmodel import SQLModel

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ketabdari (کتابداری) — Library Management API",
        description="مدیریت کتابخانه — یوزرها، کتاب‌ها و اجاره (rental)",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/health", tags=["meta"])
    async def health_v1() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
