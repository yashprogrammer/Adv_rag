"""Document upload endpoint — parse, chunk, embed, upsert.

⚠️ First-time Docling usage:
Docling downloads OCR and layout models (~400 MB) on the very first convert()
call. This can take 1–3 minutes with no visible progress. Subsequent uploads
are much faster (seconds).
"""

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from app.middleware.auth import User, get_current_user, require_admin
from app.models import RetrievedChunk
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import embed_texts
from app.services.pdf_ingestion import PDFIngestionError, cleanup_temp_file, ingest_pdf_upload
from app.services.vector_store import upsert_chunks

router = APIRouter(tags=["documents"])
_processor: DocumentProcessor | None = None


def _get_processor() -> DocumentProcessor:
    """Lazy singleton so model downloads don't block import time."""
    global _processor
    if _processor is None:
        _processor = DocumentProcessor()
    return _processor


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
) -> dict:
    # 1. Ingest PDF (fast I/O)
    try:
        ingested = await ingest_pdf_upload(file)
    except PDFIngestionError as exc:
        detail = str(exc)
        status_code = 400
        if "Only PDF" in detail:
            status_code = 415
        elif "size limit" in detail:
            status_code = 413
        raise HTTPException(status_code=status_code, detail=detail) from exc

    logger.info(
        "Upload accepted: {} ({} bytes, {} pages)",
        ingested.safe_filename,
        ingested.size_bytes,
        ingested.page_count,
    )

    try:
        # 2. Parse + chunk — CPU-bound, may trigger Docling model downloads
        logger.info("[1/3] Parsing & chunking with Docling…")
        processor = _get_processor()
        chunks_meta = await asyncio.to_thread(processor.process_document, ingested.temp_path)
        for chunk in chunks_meta:
            chunk["source"] = ingested.safe_filename
        chunks = [RetrievedChunk(text=c["text"], source=c["source"]) for c in chunks_meta]

        if not chunks:
            logger.warning("No extractable text found in {}", ingested.safe_filename)
            return {
                "doc_id": file.filename or ingested.safe_filename,
                "chunks_indexed": 0,
                "message": "No extractable text found in document",
            }
        logger.info("[1/3] Done — {} chunks extracted", len(chunks))

        # 3. Embed — network-bound
        logger.info("[2/3] Embedding {} chunks via OpenAI…", len(chunks))
        texts = [c.text for c in chunks]
        embeddings = await asyncio.to_thread(embed_texts, texts)
        logger.info("[2/3] Done — {} embeddings created", len(embeddings))

        # 4. Upsert — fast I/O
        logger.info("[3/3] Upserting into Qdrant…")
        await asyncio.to_thread(upsert_chunks, chunks, embeddings)
        logger.info("[3/3] Done — document indexed")
    finally:
        cleanup_temp_file(ingested.temp_path)

    return {
        "doc_id": file.filename or ingested.safe_filename,
        "chunks_indexed": len(chunks),
        "filename": ingested.safe_filename,
        "size_bytes": ingested.size_bytes,
        "page_count": ingested.page_count,
    }
