from typing import Optional

from ..core.exceptions import ConflictError, NotFoundError
from ..models.user import User
from ..repositories.user_repo import UserRepository
from ..schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, payload: UserCreate) -> User:
        user = User(**payload.model_dump())
        return await self.user_repo.create(user)

    async def get_user(self, user_id: int) -> User:
        user = await self.user_repo.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def list_users(self, page: int = 1, size: int = 100) -> list[User]:
        page = max(page, 1)
        size = max(min(size, 500), 1)
        offset = (page - 1) * size
        return await self.user_repo.list_paginated(offset=offset, limit=size)

    async def update_user(self, user_id: int, payload: UserUpdate) -> User:
        user = await self.get_user(user_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        return await self.user_repo.update(user)

    async def delete_user(self, user_id: int) -> None:
        user = await self.get_user(user_id)
        rental_count = await self.user_repo.count_rentals(user_id)
        if rental_count > 0:
            raise ConflictError(
                f"User {user_id} has {rental_count} rental record(s) and cannot be deleted"
            )
        await self.user_repo.delete(user)
