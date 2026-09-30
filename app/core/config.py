import os
from typing import Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    PROJECT_NAME: str = "Ketabdari"
    API_V1_PREFIX: str = "/api/v1"
    DEFAULT_DATABASE_URL: str = "postgresql+asyncpg://library:library@localhost:5433/library"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", self.DEFAULT_DATABASE_URL)


settings = Settings()
