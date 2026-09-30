from typing import Any, Generic, Optional, Type, TypeVar
from sqlalchemy import func
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, id: Any) -> Optional[ModelType]:
        return await self.session.get(self.model, id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[ModelType]:
        stmt = select(self.model).offset(offset).limit(limit)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def create(self, instance: ModelType) -> ModelType:
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelType) -> ModelType:
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> None:
        await self.session.delete(instance)
        await self.session.commit()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.exec(stmt)
        return int(result.one())
