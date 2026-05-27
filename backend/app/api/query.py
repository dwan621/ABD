from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.dataset import QueryRequest, QueryResult
from app.services.spark_bridge import execute_sql

router = APIRouter(prefix="/query", tags=["query"])

FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "TRUNCATE", "ALTER", "UPDATE", "INSERT", "MERGE", "CREATE", "REPLACE"]


def validate_sql(sql: str) -> None:
    upper = sql.upper().strip()
    for keyword in FORBIDDEN_KEYWORDS:
        if upper.startswith(keyword) or f" {keyword} " in upper:
            raise HTTPException(status_code=400, detail=f"FORBIDDEN: '{keyword}' statements are not allowed")


@router.post("/", response_model=QueryResult)
async def run_query(
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
):
    validate_sql(body.sql)
    try:
        result = execute_sql(body.sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")
    return QueryResult(**result)
