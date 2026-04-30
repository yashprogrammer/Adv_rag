"""Document processor — Docling parse + HybridChunker."""

from pathlib import Path

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from loguru import logger


class DocumentProcessor:
    def __init__(self):
        self.converter = DocumentConverter()
        self.chunker = HybridChunker()

    def process_document(self, file_path: str) -> list[dict]:
        """Parse a document and return chunks with metadata.

        Returns:
            List of dicts with keys: text, source, page_number (optional).
        """
        result = self.converter.convert(file_path)
        doc = result.document
        chunk_iter = self.chunker.chunk(doc)

        chunks = []
        source_name = Path(file_path).name
        for chunk in chunk_iter:
            meta = {"text": chunk.text, "source": source_name}
            if hasattr(chunk, "meta") and hasattr(chunk.meta, "doc_items"):
                items = chunk.meta.doc_items
                if items and hasattr(items[0], "prov") and items[0].prov:
                    meta["page_number"] = items[0].prov[0].page_no
            chunks.append(meta)

        logger.info("Processed {} chunks from {}", len(chunks), file_path)
        return chunks
