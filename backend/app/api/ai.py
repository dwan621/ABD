import logging
from uuid import UUID

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
from app.services.llm_service import build_schema_context, format_sample_data, generate_chat_response, generate_insights, generate_sql
from app.services.spark_bridge import execute_sql
from app.services import chat_service

router = APIRouter(prefix="/ai", tags=["ai"])


class TextToSQLRequest(BaseModel):
    question: str


class InsightItem(BaseModel):
    title: str
    description: str
    type: str
    sql: str | None = None
    result: dict | None = None


class InsightsResponse(BaseModel):
    dataset_id: str
    table_name: str
    row_count: int
    insights: list[InsightItem]


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


@router.post("/insights/{dataset_id}", response_model=InsightsResponse)
async def generate_dataset_insights(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    schema_context = build_schema_context([{
        "table_name": ds.table_name,
        "schema_json": ds.schema_json,
    }])

    try:
        sample_result = execute_sql(f"SELECT * FROM {ds.table_name} LIMIT 20")
    except Exception as e:
        logger.error(f"Failed to sample data from {ds.table_name}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to sample data: {e}")

    sample_data = format_sample_data(sample_result["columns"], sample_result["rows"])

    try:
        raw_insights = generate_insights(ds.table_name, schema_context, sample_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"LLM service error during insight generation: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="LLM service unavailable")

    insights = []
    for raw in raw_insights:
        item = InsightItem(
            title=raw["title"],
            description=raw["description"],
            type=raw["type"],
            sql=raw.get("sql"),
        )
        if item.sql:
            try:
                validate_sql(item.sql)
                query_result = execute_sql(item.sql)
                item.result = {
                    "columns": query_result["columns"],
                    "rows": query_result["rows"],
                    "row_count": query_result["row_count"],
                    "execution_time_ms": query_result["execution_time_ms"],
                }
            except Exception as e:
                logger.warning(f"Verification SQL failed for insight '{item.title}': {e}")
                item.result = {"error": str(e)}
        insights.append(item)

    return InsightsResponse(
        dataset_id=str(dataset_id),
        table_name=ds.table_name,
        row_count=ds.row_count or sample_result.get("row_count", 0),
        insights=insights,
    )


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sql: str | None = None
    result: dict | None = None


@router.post("/chat/sessions")
async def create_chat_session(
    current_user: User = Depends(get_current_user),
):
    session_id = await chat_service.create_session(str(current_user.id))
    return {"session_id": session_id}


@router.get("/chat/sessions/{session_id}")
async def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    messages = await chat_service.get_history(session_id)
    return {"session_id": session_id, "messages": messages}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    result = await db.execute(select(Dataset))
    datasets = result.scalars().all()
    schema_context = build_schema_context([
        {"table_name": d.table_name, "schema_json": d.schema_json}
        for d in datasets
    ])

    history = await chat_service.get_history(body.session_id)
    await chat_service.add_message(body.session_id, "user", message)

    try:
        chat_result = generate_chat_response(message, schema_context, history)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"LLM chat error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="LLM service unavailable")

    answer = chat_result["answer"]
    sql = chat_result.get("sql")
    query_result = None

    if sql:
        try:
            validate_sql(sql)
            query_result = execute_sql(sql)
        except Exception as e:
            logger.warning(f"Chat SQL execution failed: {e}")

    await chat_service.add_message(
        body.session_id, "assistant", answer,
        sql=sql, result=query_result,
    )

    return ChatResponse(
        session_id=body.session_id,
        answer=answer,
        sql=sql,
        result=query_result,
    )
