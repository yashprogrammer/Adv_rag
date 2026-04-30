"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api import admin, auth, chat

app = FastAPI(title="ADV RAG", version="0.1.0")
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(chat.router)
