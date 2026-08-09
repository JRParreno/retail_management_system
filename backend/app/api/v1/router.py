from fastapi import APIRouter

from app.api.v1 import (
    auth,
    branches,
    mechanics,
    notifications,
    products,
    reports,
    return_voids,
    shifts,
    shop_settings,
    transactions,
    transfers,
    uploads,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(branches.router)
api_router.include_router(mechanics.router)
api_router.include_router(products.router)
api_router.include_router(shifts.router)
api_router.include_router(uploads.router)
api_router.include_router(transactions.router)
api_router.include_router(transfers.router)
api_router.include_router(return_voids.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
api_router.include_router(shop_settings.router)
