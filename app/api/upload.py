"""Document upload endpoint — parse, chunk, embed, upsert."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.middleware.auth import User, get_current_user
from app.models import RetrievedChunk
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import embed_texts
from app.services.pdf_ingestion import PDFIngestionError, cleanup_temp_file, ingest_pdf_upload
from app.services.vector_store import upsert_chunks

router = APIRouter(tags=["documents"])
processor = DocumentProcessor()


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
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

    try:
        chunks_meta = processor.process_document(ingested.temp_path)
        chunks = [RetrievedChunk(text=c["text"], source=c["source"]) for c in chunks_meta]
        texts = [c.text for c in chunks]
        embeddings = embed_texts(texts)
        upsert_chunks(chunks, embeddings)
    finally:
        cleanup_temp_file(ingested.temp_path)

    return {"doc_id": file.filename or ingested.safe_filename, "chunks_indexed": len(chunks)}
