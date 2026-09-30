from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, status

from ...schemas.common import Page
from ...schemas.rental import UserRentalRead
from ...schemas.user import UserCreate, UserRead, UserUpdate
from ...services.rental_service import RentalService
from ...services.user_service import UserService
from ..deps import get_rental_service, get_user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserRead:
    user = await service.create_user(payload)
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead])
async def list_users(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=100, ge=1, le=100),
    service: UserService = Depends(get_user_service),
) -> list[UserRead]:
    users = await service.list_users(page=page, size=size)
    return [UserRead.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int = Path(..., gt=0),
    service: UserService = Depends(get_user_service),
) -> UserRead:
    user = await service.get_user(user_id)
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    payload: UserUpdate,
    user_id: int = Path(..., gt=0),
    service: UserService = Depends(get_user_service),
) -> UserRead:
    user = await service.update_user(user_id, payload)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int = Path(..., gt=0),
    service: UserService = Depends(get_user_service),
) -> None:
    await service.delete_user(user_id)


@router.get("/{user_id}/rentals", response_model=Page[UserRentalRead])
async def get_user_rentals(
    user_id: int = Path(..., gt=0),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None, description="Filter by status: active, returned, overdue"),
    sort_by: str = Query(default="created_at", description="Field to sort by: created_at, due_date, returned_at, id"),
    order: str = Query(default="desc", description="Sort direction: asc or desc"),
    rental_service: RentalService = Depends(get_rental_service),
) -> Page[UserRentalRead]:
    return await rental_service.get_user_rentals_paginated(
        user_id=user_id,
        page=page,
        size=size,
        status_filter=status,
        sort_by=sort_by,
        order=order,
    )
