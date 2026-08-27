from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db import get_db
from ..models import Rental, User
from ..schemas import RentalOut, UserCreate, UserOut

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
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, session: AsyncSession = Depends(get_db)) -> User:
    return await get_user_or_404(user_id, session)


@router.get("/{user_id}/rentals", response_model=list[RentalOut])
async def user_rentals(
    user_id: int, session: AsyncSession = Depends(get_db)
) -> list[Rental]:
    await get_user_or_404(user_id, session)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.book), selectinload(Rental.user))
        .where(Rental.user_id == user_id)
        .order_by(Rental.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())