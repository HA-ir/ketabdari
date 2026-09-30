import datetime
import pytest
from sqlmodel import SQLModel

from app.core.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.db.session import SessionLocal, engine
from app.models.book import Book
from app.models.rental import Rental
from app.models.user import User
from app.repositories.book_repo import BookRepository
from app.repositories.rental_repo import RentalRepository
from app.repositories.user_repo import UserRepository
from app.schemas.book import BookCreate
from app.schemas.rental import RentalCreate
from app.schemas.user import UserCreate
from app.services.book_service import BookService
from app.services.rental_service import RentalService
from app.services.user_service import UserService


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


async def test_user_service_not_found():
    async with SessionLocal() as session:
        user_repo = UserRepository(session)
        service = UserService(user_repo)
        with pytest.raises(NotFoundError):
            await service.get_user(9999)


async def test_user_service_delete_with_rentals_raises_conflict():
    async with SessionLocal() as session:
        user = User(name="Test User", email="test@user.com")
        session.add(user)
        book = Book(title="Test Book", quantity=1)
        session.add(book)
        await session.commit()
        await session.refresh(user)
        await session.refresh(book)

        rental = Rental(
            user_id=user.id,
            book_id=book.id,
            due_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        )
        session.add(rental)
        await session.commit()

        user_repo = UserRepository(session)
        service = UserService(user_repo)
        with pytest.raises(ConflictError):
            await service.delete_user(user.id)


async def test_book_service_invalid_sort_raises_validation_error():
    async with SessionLocal() as session:
        book_repo = BookRepository(session)
        service = BookService(book_repo)
        with pytest.raises(ValidationError):
            await service.list_books(sort_by="unknown_column")

        with pytest.raises(ValidationError):
            await service.list_books(order="sideways")


async def test_book_service_delete_with_rentals_raises_conflict():
    async with SessionLocal() as session:
        user = User(name="User A")
        book = Book(title="Book A", quantity=1)
        session.add_all([user, book])
        await session.commit()
        await session.refresh(user)
        await session.refresh(book)

        rental = Rental(
            user_id=user.id,
            book_id=book.id,
            due_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        )
        session.add(rental)
        await session.commit()

        book_repo = BookRepository(session)
        service = BookService(book_repo)
        with pytest.raises(ConflictError):
            await service.delete_book(book.id)


async def test_rental_service_past_due_date_raises_business_rule_error():
    async with SessionLocal() as session:
        rental_repo = RentalRepository(session)
        book_repo = BookRepository(session)
        user_repo = UserRepository(session)
        service = RentalService(session, rental_repo, book_repo, user_repo)

        payload = RentalCreate(
            user_id=1,
            book_id=1,
            due_date=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
        )
        with pytest.raises(BusinessRuleError):
            await service.create_rental(payload)


async def test_rental_service_out_of_stock_raises_conflict():
    async with SessionLocal() as session:
        user = User(name="User B")
        book = Book(title="Book Zero Qty", quantity=0)
        session.add_all([user, book])
        await session.commit()
        await session.refresh(user)
        await session.refresh(book)

        rental_repo = RentalRepository(session)
        book_repo = BookRepository(session)
        user_repo = UserRepository(session)
        service = RentalService(session, rental_repo, book_repo, user_repo)

        payload = RentalCreate(
            user_id=user.id,
            book_id=book.id,
            due_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        )
        with pytest.raises(ConflictError):
            await service.create_rental(payload)


async def test_rental_service_double_return_raises_conflict():
    async with SessionLocal() as session:
        user = User(name="User C")
        book = Book(title="Book C", quantity=1)
        session.add_all([user, book])
        await session.commit()
        await session.refresh(user)
        await session.refresh(book)

        rental_repo = RentalRepository(session)
        book_repo = BookRepository(session)
        user_repo = UserRepository(session)
        service = RentalService(session, rental_repo, book_repo, user_repo)

        payload = RentalCreate(
            user_id=user.id,
            book_id=book.id,
            due_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        )
        rental_out = await service.create_rental(payload)

        # First return succeeds
        await service.return_rental(rental_out.id)

        # Second return raises ConflictError
        with pytest.raises(ConflictError):
            await service.return_rental(rental_out.id)
