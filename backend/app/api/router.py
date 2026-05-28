from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.datasource import router as datasource_router
from app.api.dataset import router as dataset_router
from app.api.column import router as column_router
from app.api.query import router as query_router
from app.api.ai import router as ai_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(datasource_router)
api_router.include_router(dataset_router)
api_router.include_router(column_router)
api_router.include_router(query_router)
api_router.include_router(ai_router)
