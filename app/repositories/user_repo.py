from typing import Optional
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.rental import Rental
from ..models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def list_paginated(self, offset: int, limit: int) -> list[User]:
        stmt = select(User).order_by(User.id).offset(offset).limit(limit)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def count_rentals(self, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Rental)
            .where(Rental.user_id == user_id)
        )
        result = await self.session.exec(stmt)
        return int(result.one())
