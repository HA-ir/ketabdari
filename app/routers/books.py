import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db import get_db
from ..models import Book
from ..schemas import BookCreate, BookOut, PaginatedBooks

router = APIRouter(prefix="/books", tags=["books"])


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


@router.get("", response_model=PaginatedBooks)
async def list_books(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="فیلتر روی عنوان/نویسنده"),
    session: AsyncSession = Depends(get_db),
) -> PaginatedBooks:
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

    items_result = await session.execute(
        stmt.order_by(Book.id).offset((page - 1) * size).limit(size)
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
    from fastapi import HTTPException

    book = await session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    return book