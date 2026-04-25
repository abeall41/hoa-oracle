from fastapi import FastAPI

from app.api import documents, ingest, query

app = FastAPI(title="HOA Oracle API", version="0.1.0")

app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(query.router, prefix="/query", tags=["query"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
