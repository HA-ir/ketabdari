from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, status

from ...schemas.book import BookCreate, BookRead, BookUpdate
from ...schemas.common import Page
from ...services.book_service import BookService
from ..deps import get_book_service

router = APIRouter(prefix="/books", tags=["books"])


@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(
    payload: BookCreate,
    service: BookService = Depends(get_book_service),
) -> BookRead:
    book = await service.create_book(payload)
    return BookRead.model_validate(book)


@router.get("", response_model=Page[BookRead])
async def list_books(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, description="فیلتر روی عنوان/نویسنده"),
    sort_by: str = Query(default="id", description="Field to sort by: id, created_at, title, name, quantity, author"),
    order: Optional[str] = Query(default=None, description="Sort direction: asc or desc"),
    sort_dir: Optional[str] = Query(default=None, description="Alias for order: asc or desc"),
    service: BookService = Depends(get_book_service),
) -> Page[BookRead]:
    return await service.list_books(
        page=page,
        size=size,
        search=search,
        sort_by=sort_by,
        order=order,
        sort_dir=sort_dir,
    )


@router.get("/{book_id}", response_model=BookRead)
async def get_book(
    book_id: int = Path(..., gt=0),
    service: BookService = Depends(get_book_service),
) -> BookRead:
    book = await service.get_book(book_id)
    return BookRead.model_validate(book)


@router.patch("/{book_id}", response_model=BookRead)
async def update_book(
    payload: BookUpdate,
    book_id: int = Path(..., gt=0),
    service: BookService = Depends(get_book_service),
) -> BookRead:
    book = await service.update_book(book_id, payload)
    return BookRead.model_validate(book)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int = Path(..., gt=0),
    service: BookService = Depends(get_book_service),
) -> None:
    await service.delete_book(book_id)
