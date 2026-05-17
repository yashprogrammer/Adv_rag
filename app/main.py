"""FastAPI application entry point.

Lesson 0 — bare infra. Only auth + admin endpoints are wired.
The /query, /upload, /chat routers are added in Lesson 1+.
"""

from fastapi import FastAPI

from app.api import admin, auth

app = FastAPI(title="ADV RAG", version="0.1.0-lesson-0")
app.include_router(admin.router)
app.include_router(auth.router)
