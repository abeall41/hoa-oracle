from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.logging_config import configure_logging

configure_logging()

from app.api import documents, ingest, query  # noqa: E402 — after logging init

app = FastAPI(title="HOA Oracle API", version="0.1.0")

app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(query.router, prefix="/query", tags=["query"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
