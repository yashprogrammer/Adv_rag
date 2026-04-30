"""Document upload endpoint — parse, chunk, embed, upsert."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.middleware.auth import User, get_current_user
from app.models import RetrievedChunk
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import embed_texts
from app.services.vector_store import upsert_chunks

router = APIRouter(tags=["documents"])
processor = DocumentProcessor()


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")

    # Save to temp file
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Process
    chunks_meta = processor.process_document(tmp_path)
    chunks = [RetrievedChunk(text=c["text"], source=c["source"]) for c in chunks_meta]
    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)
    upsert_chunks(chunks, embeddings)

    return {"doc_id": file.filename, "chunks_indexed": len(chunks)}
