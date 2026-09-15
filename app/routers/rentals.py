from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db import get_db
from ..models import Book, Rental, User
from ..schemas import BookBrief, RentalCreate, RentalOut, UserBrief

router = APIRouter(prefix="/rentals", tags=["rentals"])

_RENTAL_OPTS = (
    selectinload(Rental.user),
    selectinload(Rental.book),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _get_user_or_404(user_id: int, session: AsyncSession) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


async def _get_book_or_404(book_id: int, session: AsyncSession) -> Book:
    book = await session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    return book


async def _get_rental_or_404(rental_id: int, session: AsyncSession) -> Rental:
    stmt = select(Rental).options(*_RENTAL_OPTS).where(Rental.id == rental_id)
    rental = (await session.exec(stmt)).first()
    if rental is None:
        raise HTTPException(status_code=404, detail=f"Rental {rental_id} not found")
    return rental


@router.post("", response_model=RentalOut, status_code=201)
async def create_rental(
    payload: RentalCreate,
    session: AsyncSession = Depends(get_db),
) -> Rental:
    if payload.due_date <= _utcnow():
        raise HTTPException(status_code=400, detail="due_date must be in the future")

    async with session.begin():
        user = await session.get(User, payload.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User {payload.user_id} not found")

        stmt = select(Book).where(Book.id == payload.book_id).with_for_update()
        book = (await session.exec(stmt)).first()
        if book is None:
            raise HTTPException(status_code=404, detail=f"Book {payload.book_id} not found")

        if book.quantity <= 0:
            raise HTTPException(
                status_code=409,
                detail=f"Book {payload.book_id} is not available (out of stock)",
            )

        book.quantity -= 1
        session.add(book)

        rental = Rental(
            user_id=payload.user_id,
            book_id=payload.book_id,
            due_date=payload.due_date,
        )
        session.add(rental)
        await session.flush()
        rental_id = rental.id

    return await _get_rental_or_404(rental_id, session)


def _rental_out(r) -> RentalOut:
    """Build a RentalOut from a joined row tuple."""
    return RentalOut(
        id=r.id, user_id=r.user_id, book_id=r.book_id,
        due_date=r.due_date, returned_at=r.returned_at, created_at=r.created_at,
        user=UserBrief(id=r.user_id, name=r.user_name),
        book=BookBrief(id=r.book_id, title=r.book_title),
    )


@router.get("/overdue", response_model=list[RentalOut])
async def list_overdue(
    limit: int | None = Query(default=None, ge=1, le=10000),
    session: AsyncSession = Depends(get_db),
) -> list[RentalOut]:
    # Fast path: single join query -> row tuples -> pydantic models.
    # No ORM identity-map objects (3 per row), no selectinload round-trips.
    stmt = (
        select(
            Rental.id, Rental.user_id, Rental.book_id,
            Rental.due_date, Rental.returned_at, Rental.created_at,
            User.name.label("user_name"),
            Book.title.label("book_title"),
        )
        .join(User, Rental.user_id == User.id)
        .join(Book, Rental.book_id == Book.id)
        .where(Rental.returned_at.is_(None), Rental.due_date < _utcnow())
        .order_by(Rental.due_date)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = (await session.exec(stmt)).all()
    return [_rental_out(r) for r in rows]


@router.get("", response_model=list[RentalOut])
async def list_rentals(
    limit: int = Query(default=100, ge=1, le=10000),
    session: AsyncSession = Depends(get_db),
) -> list[RentalOut]:
    # Same join fast-path as /overdue: one query, tuples -> pydantic, no ORM objects.
    stmt = (
        select(
            Rental.id, Rental.user_id, Rental.book_id,
            Rental.due_date, Rental.returned_at, Rental.created_at,
            User.name.label("user_name"),
            Book.title.label("book_title"),
        )
        .join(User, Rental.user_id == User.id)
        .join(Book, Rental.book_id == Book.id)
        .order_by(Rental.id)
        .limit(limit)
    )
    rows = (await session.exec(stmt)).all()
    return [_rental_out(r) for r in rows]


@router.get("/{rental_id}", response_model=RentalOut)
async def get_rental(rental_id: int, session: AsyncSession = Depends(get_db)) -> Rental:
    return await _get_rental_or_404(rental_id, session)


@router.post("/{rental_id}/return", response_model=RentalOut)
async def return_rental(
    rental_id: int, session: AsyncSession = Depends(get_db)
) -> Rental:
    async with session.begin():
        stmt = select(Rental).where(Rental.id == rental_id).with_for_update()
        rental = (await session.exec(stmt)).first()
        if rental is None:
            raise HTTPException(status_code=404, detail=f"Rental {rental_id} not found")

        if rental.returned_at is not None:
            raise HTTPException(
                status_code=409, detail=f"Rental {rental_id} was already returned"
            )

        stmt_book = select(Book).where(Book.id == rental.book_id).with_for_update()
        book = (await session.exec(stmt_book)).first()
        if book is not None:
            book.quantity += 1
            session.add(book)

        rental.returned_at = _utcnow()
        session.add(rental)

    return await _get_rental_or_404(rental_id, session)
