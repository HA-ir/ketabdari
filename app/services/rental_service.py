from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from ..models.book import Book
from ..models.rental import Rental
from ..repositories.book_repo import BookRepository
from ..repositories.rental_repo import RentalRepository
from ..repositories.user_repo import UserRepository
from ..schemas.book import BookBrief, BookRead
from ..schemas.common import Page
from ..schemas.rental import RentalCreate, RentalRead, UserRentalRead
from ..schemas.user import UserBrief

ALLOWED_RENTAL_SORT_FIELDS = {
    "created_at": Rental.created_at,
    "rental_date": Rental.created_at,
    "due_date": Rental.due_date,
    "returned_at": Rental.returned_at,
    "id": Rental.id,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_rental_out_from_tuple(r: Any) -> RentalRead:
    return RentalRead(
        id=r.id,
        user_id=r.user_id,
        book_id=r.book_id,
        due_date=r.due_date,
        returned_at=r.returned_at,
        created_at=r.created_at,
        user=UserBrief(id=r.user_id, name=r.user_name),
        book=BookBrief(id=r.book_id, title=r.book_title),
    )


class RentalService:
    def __init__(
        self,
        session: AsyncSession,
        rental_repo: RentalRepository,
        book_repo: BookRepository,
        user_repo: UserRepository,
    ):
        self.session = session
        self.rental_repo = rental_repo
        self.book_repo = book_repo
        self.user_repo = user_repo

    @asynccontextmanager
    async def _transaction(self) -> AsyncGenerator[None, None]:
        if self.session.in_transaction():
            async with self.session.begin_nested():
                yield
        else:
            async with self.session.begin():
                yield

    async def create_rental(self, payload: RentalCreate) -> RentalRead:
        if payload.due_date <= _utcnow():
            raise BusinessRuleError("due_date must be in the future")

        async with self._transaction():
            user = await self.user_repo.get(payload.user_id)
            if user is None:
                raise NotFoundError(f"User {payload.user_id} not found")

            book = await self.book_repo.get_with_for_update(payload.book_id)
            if book is None:
                raise NotFoundError(f"Book {payload.book_id} not found")

            if book.quantity <= 0:
                raise ConflictError(
                    f"Book {payload.book_id} is not available (out of stock)"
                )

            book.quantity -= 1
            self.session.add(book)

            rental = Rental(
                user_id=payload.user_id,
                book_id=payload.book_id,
                due_date=payload.due_date,
            )
            self.session.add(rental)
            await self.session.flush()
            rental_id = rental.id

        full_rental = await self.rental_repo.get_with_relations(rental_id)
        return RentalRead.model_validate(full_rental)

    async def return_rental(self, rental_id: int) -> RentalRead:
        async with self._transaction():
            rental = await self.rental_repo.get_with_for_update(rental_id)
            if rental is None:
                raise NotFoundError(f"Rental {rental_id} not found")

            if rental.returned_at is not None:
                raise ConflictError(f"Rental {rental_id} was already returned")

            book = await self.book_repo.get_with_for_update(rental.book_id)
            if book is not None:
                book.quantity += 1
                self.session.add(book)

            rental.returned_at = _utcnow()
            self.session.add(rental)

        full_rental = await self.rental_repo.get_with_relations(rental_id)
        return RentalRead.model_validate(full_rental)

    async def get_rental(self, rental_id: int) -> RentalRead:
        rental = await self.rental_repo.get_with_relations(rental_id)
        if rental is None:
            raise NotFoundError(f"Rental {rental_id} not found")
        return RentalRead.model_validate(rental)

    async def list_rentals(self, limit: int = 100) -> list[RentalRead]:
        rows = await self.rental_repo.list_rentals_fast(limit=limit)
        return [_build_rental_out_from_tuple(r) for r in rows]

    async def list_overdue(self, limit: Optional[int] = None) -> list[RentalRead]:
        rows = await self.rental_repo.list_overdue_fast(now=_utcnow(), limit=limit)
        return [_build_rental_out_from_tuple(r) for r in rows]

    async def list_user_rentals_legacy(self, user_id: int) -> list[RentalRead]:
        user = await self.user_repo.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        rows = await self.rental_repo.list_by_user_fast(user_id)
        return [_build_rental_out_from_tuple(r) for r in rows]

    async def get_user_rentals_paginated(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
        status_filter: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> Page[UserRentalRead]:
        user = await self.user_repo.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")

        if status_filter is not None:
            norm_status = status_filter.strip().lower()
            if norm_status not in ("active", "returned", "overdue"):
                raise ValidationError(
                    f"Invalid status filter '{status_filter}'. Allowed: 'active', 'returned', 'overdue'"
                )
        else:
            norm_status = None

        sort_key = sort_by.strip().lower()
        if sort_key not in ALLOWED_RENTAL_SORT_FIELDS:
            raise ValidationError(
                f"Invalid sort_by field '{sort_by}'. Allowed fields: {', '.join(sorted(ALLOWED_RENTAL_SORT_FIELDS.keys()))}"
            )
        sort_col = ALLOWED_RENTAL_SORT_FIELDS[sort_key]

        direction = order.strip().lower()
        if direction not in ("asc", "desc"):
            raise ValidationError(
                f"Invalid sort order '{direction}'. Allowed values: 'asc', 'desc'"
            )
        ascending = direction == "asc"

        offset = (page - 1) * size
        now = _utcnow()

        items, total = await self.rental_repo.list_user_rentals_enriched(
            user_id=user_id,
            status_filter=norm_status,
            sort_col=sort_col,
            ascending=ascending,
            offset=offset,
            limit=size,
            now=now,
        )

        result_items: list[UserRentalRead] = []
        for rental, book, u in items:
            if rental.returned_at is not None:
                current_status = "returned"
            elif rental.due_date < now:
                current_status = "overdue"
            else:
                current_status = "active"

            result_items.append(
                UserRentalRead(
                    id=rental.id,
                    rental_id=rental.id,
                    user_id=rental.user_id,
                    book_id=rental.book_id,
                    status=current_status,
                    created_at=rental.created_at,
                    due_date=rental.due_date,
                    returned_at=rental.returned_at,
                    book=BookRead.model_validate(book),
                    user=UserBrief(id=u.id, name=u.name),
                )
            )

        return Page[UserRentalRead].create(
            items=result_items, total=total, page=page, size=size
        )
