from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db import get_db
from ..models import Book, Rental, User
from ..schemas import RentalOut, UserCreate, UserOut, UserUpdate
from .rentals import _rental_out

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    session: AsyncSession = Depends(get_db),
) -> User:
    user = User(**payload.model_dump())
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("", response_model=list[UserOut])
async def list_users(
    page: int = 1, size: int = 100,
    session: AsyncSession = Depends(get_db),
) -> list[User]:
    page = max(page, 1)
    size = max(min(size, 500), 1)
    result = await session.execute(
        select(User).order_by(User.id).offset((page - 1) * size).limit(size)
    )
    return list(result.scalars().all())


async def get_user_or_404(user_id: int, session: AsyncSession) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, session: AsyncSession = Depends(get_db)) -> User:
    return await get_user_or_404(user_id, session)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_db),
) -> User:
    user = await get_user_or_404(user_id, session)
    # exclude_unset: only touch fields the client actually sent
    # (sending email: null really clears it; omitting it leaves it alone)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    user = await get_user_or_404(user_id, session)
    rental_count = int(
        (
            await session.execute(
                select(func.count()).select_from(Rental).where(Rental.user_id == user.id)
            )
        ).scalar_one()
    )
    if rental_count:
        raise HTTPException(
            status_code=409,
            detail=f"User {user_id} has {rental_count} rental record(s) and cannot be deleted",
        )
    await session.delete(user)
    await session.commit()


@router.get("/{user_id}/rentals", response_model=list[RentalOut])
async def user_rentals(
    user_id: int, session: AsyncSession = Depends(get_db)
) -> list[RentalOut]:
    await get_user_or_404(user_id, session)
    # Join fast-path: one query, no ORM identity objects, no lazy loads.
    stmt = (
        select(
            Rental.id, Rental.user_id, Rental.book_id,
            Rental.due_date, Rental.returned_at, Rental.created_at,
            User.name.label("user_name"),
            Book.title.label("book_title"),
        )
        .join(User, Rental.user_id == User.id)
        .join(Book, Rental.book_id == Book.id)
        .where(Rental.user_id == user_id)
        .order_by(Rental.id.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [_rental_out(r) for r in rows]