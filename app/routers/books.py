import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db import get_db
from ..models import Book, Rental
from ..schemas import BookCreate, BookOut, BookUpdate, PaginatedBooks

router = APIRouter(prefix="/books", tags=["books"])


async def get_book_or_404(book_id: int, session: AsyncSession) -> Book:
    book = await session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    return book


@router.post("", response_model=BookOut, status_code=201)
async def create_book(
    payload: BookCreate,
    session: AsyncSession = Depends(get_db),
) -> Book:
    book = Book(**payload.model_dump())
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return book


ALLOWED_SORT_FIELDS = {
    "id": Book.id,
    "created_at": Book.created_at,
    "title": Book.title,
    "name": Book.title,
    "quantity": Book.quantity,
    "author": Book.author,
}


@router.get("", response_model=PaginatedBooks)
async def list_books(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="فیلتر روی عنوان/نویسنده"),
    sort_by: str = Query(default="id", description="Field to sort by: id, created_at, title, name, quantity"),
    order: str | None = Query(default=None, description="Sort direction: asc or desc"),
    sort_dir: str | None = Query(default=None, description="Alias for order: asc or desc"),
    session: AsyncSession = Depends(get_db),
) -> PaginatedBooks:
    field_key = sort_by.strip().lower()
    if field_key not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by field '{sort_by}'. Allowed fields: {', '.join(sorted(ALLOWED_SORT_FIELDS.keys()))}",
        )

    direction = (order or sort_dir or "asc").strip().lower()
    if direction not in ("asc", "desc"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort order '{direction}'. Allowed values: 'asc', 'desc'",
        )

    stmt = select(Book)
    if search:
        like = f"%{search}%"
        stmt = stmt.where((Book.title.ilike(like)) | (Book.author.ilike(like)))

    total = int(
        (
            await session.execute(
                select(func.count()).select_from(stmt.subquery())
            )
        ).scalar_one()
    )

    sort_col = ALLOWED_SORT_FIELDS[field_key]
    if direction == "desc":
        order_expr = [sort_col.desc(), Book.id.desc()]
    else:
        order_expr = [sort_col.asc(), Book.id.asc()]

    items_result = await session.execute(
        stmt.order_by(*order_expr).offset((page - 1) * size).limit(size)
    )
    items = list(items_result.scalars().all())
    return PaginatedBooks(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=max(1, math.ceil(total / size)),
    )


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: int, session: AsyncSession = Depends(get_db)) -> Book:
    return await get_book_or_404(book_id, session)


@router.patch("/{book_id}", response_model=BookOut)
async def update_book(
    book_id: int,
    payload: BookUpdate,
    session: AsyncSession = Depends(get_db),
) -> Book:
    book = await get_book_or_404(book_id, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return book


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    book = await get_book_or_404(book_id, session)
    rental_count = int(
        (
            await session.execute(
                select(func.count()).select_from(Rental).where(Rental.book_id == book.id)
            )
        ).scalar_one()
    )
    if rental_count:
        raise HTTPException(
            status_code=409,
            detail=f"Book {book_id} has {rental_count} rental record(s) and cannot be deleted",
        )
    await session.delete(book)
    await session.commit()
