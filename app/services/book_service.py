from typing import Optional

from ..core.exceptions import ConflictError, NotFoundError, ValidationError
from ..models.book import Book
from ..repositories.book_repo import BookRepository
from ..schemas.book import BookCreate, BookRead, BookUpdate
from ..schemas.common import Page

ALLOWED_SORT_FIELDS = {
    "id": Book.id,
    "created_at": Book.created_at,
    "title": Book.title,
    "name": Book.title,
    "quantity": Book.quantity,
    "author": Book.author,
}


class BookService:
    def __init__(self, book_repo: BookRepository):
        self.book_repo = book_repo

    async def create_book(self, payload: BookCreate) -> Book:
        book = Book(**payload.model_dump())
        return await self.book_repo.create(book)

    async def get_book(self, book_id: int) -> Book:
        book = await self.book_repo.get(book_id)
        if book is None:
            raise NotFoundError(f"Book {book_id} not found")
        return book

    async def list_books(
        self,
        page: int = 1,
        size: int = 20,
        search: Optional[str] = None,
        sort_by: str = "id",
        order: Optional[str] = None,
        sort_dir: Optional[str] = None,
    ) -> Page[BookRead]:
        field_key = sort_by.strip().lower()
        if field_key not in ALLOWED_SORT_FIELDS:
            raise ValidationError(
                f"Invalid sort_by field '{sort_by}'. Allowed fields: {', '.join(sorted(ALLOWED_SORT_FIELDS.keys()))}"
            )

        direction = (order or sort_dir or "asc").strip().lower()
        if direction not in ("asc", "desc"):
            raise ValidationError(
                f"Invalid sort order '{direction}'. Allowed values: 'asc', 'desc'"
            )

        offset = (page - 1) * size
        sort_col = ALLOWED_SORT_FIELDS[field_key]
        ascending = direction == "asc"

        items, total = await self.book_repo.list_search_and_sort(
            search=search,
            sort_col=sort_col,
            ascending=ascending,
            offset=offset,
            limit=size,
        )

        read_items = [BookRead.model_validate(b) for b in items]
        return Page[BookRead].create(items=read_items, total=total, page=page, size=size)

    async def update_book(self, book_id: int, payload: BookUpdate) -> Book:
        book = await self.get_book(book_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(book, field, value)
        return await self.book_repo.update(book)

    async def delete_book(self, book_id: int) -> None:
        book = await self.get_book(book_id)
        rental_count = await self.book_repo.count_rentals(book_id)
        if rental_count > 0:
            raise ConflictError(
                f"Book {book_id} has {rental_count} rental record(s) and cannot be deleted"
            )
        await self.book_repo.delete(book)
