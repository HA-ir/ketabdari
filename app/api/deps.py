from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db.session import get_session
from ..repositories.book_repo import BookRepository
from ..repositories.rental_repo import RentalRepository
from ..repositories.user_repo import UserRepository
from ..services.book_service import BookService
from ..services.rental_service import RentalService
from ..services.user_service import UserService


def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepository(session)


def get_book_repository(session: AsyncSession = Depends(get_session)) -> BookRepository:
    return BookRepository(session)


def get_rental_repository(session: AsyncSession = Depends(get_session)) -> RentalRepository:
    return RentalRepository(session)


def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(user_repo)


def get_book_service(
    book_repo: BookRepository = Depends(get_book_repository),
) -> BookService:
    return BookService(book_repo)


def get_rental_service(
    session: AsyncSession = Depends(get_session),
    rental_repo: RentalRepository = Depends(get_rental_repository),
    book_repo: BookRepository = Depends(get_book_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> RentalService:
    return RentalService(
        session=session,
        rental_repo=rental_repo,
        book_repo=book_repo,
        user_repo=user_repo,
    )
