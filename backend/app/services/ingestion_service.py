"""CampusMind AI - Ingestion Service.

Coordinates document persistence, text extraction, chunking, embedding, indexing, and cache invalidation.

Responsibilities:
Class IngestionService:
1. IngestionService.__init__(): Initializes database session, extraction, chunking, and indexing services.
2. IngestionService.ingest_file(): Executes the end-to-end ingestion pipeline from uploaded bytes to indexed vector points.
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any, BinaryIO, List
from sqlalchemy.orm import Session

from app.schemas.chunk import ExtractedDocument, Chunk, EmbeddedChunk
from app.services.document_extractor import DocumentExtractor, clean_text
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.retrieval_bm25 import BM25RetrievalService
from app.services.cache_service import RedisCacheService
from app.repositories.database_repository import DocumentRepository

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Manages end-to-end document extraction, chunking, embedding, vector/keyword indexing,
    relational tracking, and cache invalidation.
    """

    def __init__(
        self,
        db_session: Session,
        document_extractor: Optional[DocumentExtractor] = None,
        chunking_service: Optional[ChunkingService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store_service: Optional[VectorStoreService] = None,
        bm25_service: Optional[BM25RetrievalService] = None,
        cache_service: Optional[RedisCacheService] = None,
    ):
        self.db_session = db_session
        self.doc_repo = DocumentRepository(db_session)
        self.extractor = document_extractor or DocumentExtractor()
        self.embedding_service = embedding_service or EmbeddingService()
        self.chunking_service = chunking_service or ChunkingService(embedding_service=self.embedding_service)
        self.vector_store = vector_store_service or VectorStoreService()
        self.bm25_service = bm25_service or BM25RetrievalService()
        self.cache_service = cache_service or RedisCacheService()

    def ingest_file(
        self,
        file_bytes: bytes,
        filename: str,
        uploader_id: Optional[str] = None,
        chunking_method: str = "recursive",
        chunk_size_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
        version: str = "v1",
        storage_dir: Optional[str] = "storage/uploads",
    ) -> Dict[str, Any]:
        """
        Executes end-to-end ingestion pipeline:
        1. Validates and saves file to local storage.
        2. Creates initial 'uploaded' record in MySQL.
        3. Extracts and cleans text using DocumentExtractor.
        4. Chunks text using ChunkingService.
        5. Embeds chunks using EmbeddingService.
        6. Stores vectors and metadata in Qdrant.
        7. Synchronizes BM25 index with new chunks.
        8. Updates MySQL document status to 'indexed' with chunk_count and version.
        9. Invalidates Redis cache by updating KB version or clearing relevant keys.
        """
        doc_id = str(uuid.uuid4())
        saved_file_path = None

        # 1. Save uploaded file to storage directory if provided
        if storage_dir:
            try:
                os.makedirs(storage_dir, exist_ok=True)
                saved_file_path = os.path.join(storage_dir, f"{doc_id}_{filename}")
                with open(saved_file_path, "wb") as f:
                    f.write(file_bytes)
            except Exception as e:
                logger.warning("Could not persist file to disk: %s", e)

        # 2. Create initial document record in MySQL
        doc_record = self.doc_repo.create_document(
            document_id=doc_id,
            filename=filename,
            file_path=saved_file_path,
            uploader_id=uploader_id,
            status="uploaded",
            chunk_count=0,
            version=version,
        )

        try:
            # 3. Extract text
            extracted_doc: ExtractedDocument = self.extractor.extract_document(
                file_input=file_bytes,
                filename=filename,
                document_id=doc_id,
            )

            # 4. Chunk document
            chunks: List[Chunk] = self.chunking_service.chunk_document(
                document=extracted_doc,
                method=chunking_method,
                chunk_size_tokens=chunk_size_tokens,
                chunk_overlap_tokens=chunk_overlap_tokens,
            )

            if not chunks:
                raise ValueError("Document yielded 0 chunks after text extraction and cleaning.")

            # 5. Embed chunks
            self.vector_store.ensure_collection()
            embedded_chunks: List[EmbeddedChunk] = []
            for chk in chunks:
                vec = self.embedding_service.embed_text(chk.content)
                embedded_chunks.append(EmbeddedChunk(chunk=chk, embedding=vec))

            # 6. Store in Qdrant
            self.vector_store.upsert_chunks(embedded_chunks)

            # 7. Synchronize BM25 keyword index
            # Append new chunks to existing BM25 index corpus and rebuild
            existing_chunks = list(self.bm25_service._chunks) if hasattr(self.bm25_service, "_chunks") else []
            all_chunks = existing_chunks + chunks
            self.bm25_service.build_index(all_chunks)

            # 8. Update MySQL status to 'indexed'
            self.doc_repo.update_status(
                document_id=doc_id,
                status="indexed",
                chunk_count=len(chunks),
                version=version,
            )

            # 9. Invalidate Redis knowledge-base cache
            new_kb_version = f"v_{uuid.uuid4().hex[:6]}"
            try:
                self.cache_service.update_kb_version(new_kb_version)
            except Exception as e:
                logger.warning("Cache invalidation error after ingestion: %s", e)

            logger.info("Successfully ingested document '%s' (ID: %s, %d chunks)", filename, doc_id, len(chunks))

            return {
                "document_id": doc_id,
                "filename": filename,
                "status": "indexed",
                "chunk_count": len(chunks),
                "version": version,
                "new_kb_version": new_kb_version,
            }

        except Exception as err:
            logger.error("Ingestion failed for document '%s' (ID: %s): %s", filename, doc_id, err)
            # Rollback / update document status to 'failed' in MySQL so state remains consistent
            self.doc_repo.update_status(document_id=doc_id, status="failed")
            # Cleanup any partially indexed points in Qdrant
            try:
                self.vector_store.delete_document_chunks(doc_id)
            except Exception:
                pass
            raise err

