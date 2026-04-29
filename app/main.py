from contextlib import asynccontextmanager

import httpx
import openai
import psycopg2
from fastapi import FastAPI
from loguru import logger

from app.config import settings


def _setup_logging() -> None:
    """Configure loguru — JSON when LOG_JSON=true, plain text otherwise."""
    import sys

    logger.remove()
    if settings.LOG_JSON:
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            serialize=True,
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )


def _check_qdrant() -> bool:
    try:
        import urllib.request

        req = urllib.request.urlopen(f"{settings.QDRANT_URL}/healthz", timeout=5)
        return req.status == 200
    except Exception:
        return False


def _check_postgres() -> bool:
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.close()
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.UPSTASH_REDIS_URL}/ping",
                headers={"Authorization": f"Bearer {settings.UPSTASH_REDIS_TOKEN}"},
            )
            return resp.status_code == 200
    except Exception:
        return False


async def _check_openai() -> bool:
    try:
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        await client.models.list()
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    logger.info("ADV RAG starting up")
    yield
    logger.info("ADV RAG shutting down")


app = FastAPI(title="ADV RAG", lifespan=lifespan)


@app.get("/admin/health")
async def health_check():
    qdrant_ok = _check_qdrant()
    postgres_ok = _check_postgres()
    redis_ok = await _check_redis()
    openai_ok = await _check_openai()

    deps = [qdrant_ok, postgres_ok, redis_ok, openai_ok]
    status = "ok" if all(deps) else "degraded"

    return {
        "status": status,
        "qdrant": qdrant_ok,
        "postgres": postgres_ok,
        "redis": redis_ok,
        "openai": openai_ok,
    }
