from datetime import datetime
from typing import Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.book import Book
from ..models.rental import Rental
from ..models.user import User
from .base import BaseRepository

_RENTAL_OPTS = (
    selectinload(Rental.user),
    selectinload(Rental.book),
)


class RentalRepository(BaseRepository[Rental]):
    def __init__(self, session: AsyncSession):
        super().__init__(Rental, session)

    async def get_with_relations(self, rental_id: int) -> Optional[Rental]:
        stmt = select(Rental).options(*_RENTAL_OPTS).where(Rental.id == rental_id)
        result = await self.session.exec(stmt)
        return result.first()

    async def get_with_for_update(self, rental_id: int) -> Optional[Rental]:
        stmt = select(Rental).where(Rental.id == rental_id).with_for_update()
        result = await self.session.exec(stmt)
        return result.first()

    async def list_rentals_fast(self, limit: int = 100) -> list[Any]:
        stmt = (
            select(
                Rental.id,
                Rental.user_id,
                Rental.book_id,
                Rental.due_date,
                Rental.returned_at,
                Rental.created_at,
                User.name.label("user_name"),
                Book.title.label("book_title"),
            )
            .join(User, Rental.user_id == User.id)
            .join(Book, Rental.book_id == Book.id)
            .order_by(Rental.id)
            .limit(limit)
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def list_overdue_fast(self, now: datetime, limit: Optional[int] = None) -> list[Any]:
        stmt = (
            select(
                Rental.id,
                Rental.user_id,
                Rental.book_id,
                Rental.due_date,
                Rental.returned_at,
                Rental.created_at,
                User.name.label("user_name"),
                Book.title.label("book_title"),
            )
            .join(User, Rental.user_id == User.id)
            .join(Book, Rental.book_id == Book.id)
            .where(Rental.returned_at.is_(None), Rental.due_date < now)
            .order_by(Rental.due_date)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.exec(stmt)
        return list(result.all())

    async def list_by_user_fast(self, user_id: int) -> list[Any]:
        stmt = (
            select(
                Rental.id,
                Rental.user_id,
                Rental.book_id,
                Rental.due_date,
                Rental.returned_at,
                Rental.created_at,
                User.name.label("user_name"),
                Book.title.label("book_title"),
            )
            .join(User, Rental.user_id == User.id)
            .join(Book, Rental.book_id == Book.id)
            .where(Rental.user_id == user_id)
            .order_by(Rental.id.desc())
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def list_user_rentals_enriched(
        self,
        user_id: int,
        status_filter: Optional[str],
        sort_col: Any,
        ascending: bool,
        offset: int,
        limit: int,
        now: datetime,
    ) -> tuple[list[tuple[Rental, Book, User]], int]:
        """Fetch user rentals joined with full book and user details in a single query."""
        base_stmt = (
            select(Rental, Book, User)
            .join(Book, Rental.book_id == Book.id)
            .join(User, Rental.user_id == User.id)
            .where(Rental.user_id == user_id)
        )

        if status_filter:
            norm_status = status_filter.strip().lower()
            if norm_status == "returned":
                base_stmt = base_stmt.where(Rental.returned_at.is_not(None))
            elif norm_status == "overdue":
                base_stmt = base_stmt.where(
                    Rental.returned_at.is_(None), Rental.due_date < now
                )
            elif norm_status == "active":
                base_stmt = base_stmt.where(
                    Rental.returned_at.is_(None), Rental.due_date >= now
                )

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.exec(count_stmt)).one())

        if ascending:
            order_expr = [sort_col.asc(), Rental.id.asc()]
        else:
            order_expr = [sort_col.desc(), Rental.id.desc()]

        items_stmt = base_stmt.order_by(*order_expr).offset(offset).limit(limit)
        items_result = await self.session.exec(items_stmt)
        items = list(items_result.all())
        return items, total
