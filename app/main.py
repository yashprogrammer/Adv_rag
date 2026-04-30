"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api import admin, auth

app = FastAPI(title="ADV RAG", version="0.1.0")
app.include_router(admin.router)
app.include_router(auth.router)
