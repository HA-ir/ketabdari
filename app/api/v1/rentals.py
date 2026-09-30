from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, status

from ...schemas.rental import RentalCreate, RentalRead
from ...services.rental_service import RentalService
from ..deps import get_rental_service

router = APIRouter(prefix="/rentals", tags=["rentals"])


@router.post("", response_model=RentalRead, status_code=status.HTTP_201_CREATED)
async def create_rental(
    payload: RentalCreate,
    service: RentalService = Depends(get_rental_service),
) -> RentalRead:
    return await service.create_rental(payload)


@router.get("/overdue", response_model=list[RentalRead])
async def list_overdue(
    limit: Optional[int] = Query(default=None, ge=1, le=10000),
    service: RentalService = Depends(get_rental_service),
) -> list[RentalRead]:
    return await service.list_overdue(limit=limit)


@router.get("", response_model=list[RentalRead])
async def list_rentals(
    limit: int = Query(default=100, ge=1, le=10000),
    service: RentalService = Depends(get_rental_service),
) -> list[RentalRead]:
    return await service.list_rentals(limit=limit)


@router.get("/{rental_id}", response_model=RentalRead)
async def get_rental(
    rental_id: int = Path(..., gt=0),
    service: RentalService = Depends(get_rental_service),
) -> RentalRead:
    return await service.get_rental(rental_id)


@router.post("/{rental_id}/return", response_model=RentalRead)
async def return_rental(
    rental_id: int = Path(..., gt=0),
    service: RentalService = Depends(get_rental_service),
) -> RentalRead:
    return await service.return_rental(rental_id)
