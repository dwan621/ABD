import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user
from app.api.query import validate_sql
from app.core.database import get_db
from app.models.dataset import Dataset
from app.models.user import User
from app.services.llm_service import build_schema_context, generate_sql
from app.services.spark_bridge import execute_sql

router = APIRouter(prefix="/ai", tags=["ai"])


class TextToSQLRequest(BaseModel):
    question: str


@router.post("/text-to-sql")
async def text_to_sql(
    body: TextToSQLRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    result = await db.execute(select(Dataset))
    datasets = result.scalars().all()
    schema_context = build_schema_context([
        {"table_name": d.table_name, "schema_json": d.schema_json}
        for d in datasets
    ])

    try:
        sql = generate_sql(question, schema_context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"LLM service error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="LLM service unavailable")

    validate_sql(sql)

    try:
        result = execute_sql(sql)
    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Query execution failed")

    return {
        "sql": sql,
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "execution_time_ms": result["execution_time_ms"],
    }
