from typing import Any, Optional
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.book import Book
from ..models.rental import Rental
from .base import BaseRepository


class BookRepository(BaseRepository[Book]):
    def __init__(self, session: AsyncSession):
        super().__init__(Book, session)

    async def get_with_for_update(self, book_id: int) -> Optional[Book]:
        stmt = select(Book).where(Book.id == book_id).with_for_update()
        result = await self.session.exec(stmt)
        return result.first()

    async def count_rentals(self, book_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Rental)
            .where(Rental.book_id == book_id)
        )
        result = await self.session.exec(stmt)
        return int(result.one())

    async def list_search_and_sort(
        self,
        search: Optional[str],
        sort_col: Any,
        ascending: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[Book], int]:
        stmt = select(Book)
        if search:
            like = f"%{search}%"
            stmt = stmt.where((Book.title.ilike(like)) | (Book.author.ilike(like)))

        total = int(
            (
                await self.session.exec(
                    select(func.count()).select_from(stmt.subquery())
                )
            ).one()
        )

        if ascending:
            order_expr = [sort_col.asc(), Book.id.asc()]
        else:
            order_expr = [sort_col.desc(), Book.id.desc()]

        items_result = await self.session.exec(
            stmt.order_by(*order_expr).offset(offset).limit(limit)
        )
        items = list(items_result.all())
        return items, total
