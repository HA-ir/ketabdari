from fastapi import APIRouter

from .books import router as books_router
from .rentals import router as rentals_router
from .users import router as users_router

router = APIRouter()
router.include_router(users_router)
router.include_router(books_router)
router.include_router(rentals_router)
