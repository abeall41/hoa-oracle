import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.orchestrator.router import route_query

router = APIRouter()

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
async def handle_query(request: QueryRequest) -> dict:
    try:
        clean_query = sanitize_query(request.query)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await route_query(
        query=clean_query,
        query_source=request.query_source,
        community_tier_id=request.community_id,
        session_id=request.session_id,
    )
