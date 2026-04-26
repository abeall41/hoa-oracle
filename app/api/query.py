import logging
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.query_log import QueryLog
from app.orchestrator.router import route_query

router = APIRouter()
logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    r"ignore (previous|prior|all) instructions",
    r"you are now",
    r"disregard (your|the) (system|previous)",
    r"<\|.*?\|>",
]


def sanitize_query(query: str) -> str:
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            raise ValueError("Query contains disallowed content")
    return query.strip()[:2000]


class QueryRequest(BaseModel):
    query: str
    query_source: str   # 'board' | 'homeowner'
    community_id: int
    session_id: str = ""


@router.post("/")
async def handle_query(request: QueryRequest, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        clean_query = sanitize_query(request.query)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "Query received",
        extra={
            "query": clean_query[:120],
            "query_source": request.query_source,
            "community_id": request.community_id,
        },
    )

    start = time.monotonic()
    log_entry = QueryLog(
        session_id=request.session_id or None,
        tier_id=request.community_id,
        query_source=request.query_source,
        query_text=clean_query,
    )
    db.add(log_entry)

    try:
        result = await route_query(
            query=clean_query,
            query_source=request.query_source,
            community_tier_id=request.community_id,
            session_id=request.session_id,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        from app.config import settings
        log_entry.response_text = result.get("response_text", "")
        log_entry.model_used = (
            settings.claude_model if settings.llm_provider == "claude" else settings.ollama_model
        )
        log_entry.latency_ms = latency_ms
        log_entry.success = True
        await db.commit()

        logger.info(
            "Query completed in %dms", latency_ms,
            extra={"latency_ms": latency_ms, "query_source": request.query_source},
        )
        return result

    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        log_entry.success = False
        log_entry.error = str(exc)
        log_entry.latency_ms = latency_ms
        await db.commit()
        logger.exception("Query failed after %dms: %s", latency_ms, exc)
        raise HTTPException(status_code=500, detail=str(exc))
