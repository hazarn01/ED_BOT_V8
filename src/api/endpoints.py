import logging
import mimetypes
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..models.entities import Document
from ..models.schemas import (
    ContactResponse,
    DocumentResponse,
    QueryRequest,
    QueryResponse,
)
from ..pipeline.query_processor import QueryProcessor
from ..validation.hipaa import scrub_phi
from .dependencies import get_db_session, get_query_processor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest, processor: QueryProcessor = Depends(get_query_processor)
):
    """Process medical query with classification and retrieval"""
    try:
        logger.info(f"Processing query: {scrub_phi(request.query)}")

        response = await processor.process_query(
            query=request.query, context=request.context, user_id=request.user_id
        )

        return response
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query processing failed",
        )


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    doc_type: Optional[str] = Query(
        None, description="Filter by document type (maps to content_type)"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db_session),
):
    """List available documents"""
    try:
        query = db.query(Document)

        if doc_type:
            query = query.filter(Document.content_type == doc_type)
        if category:
            query = query.filter(
                Document.meta["category"].astext == category
            )  # requires PostgreSQL JSONB

        documents = query.all()
        results: List[DocumentResponse] = []
        for doc in documents:
            metadata = (
                getattr(doc, "meta", {})
                if isinstance(getattr(doc, "meta", {}), dict)
                else {}
            )
            results.append(
                DocumentResponse(
                    id=doc.id,
                    filename=doc.filename,
                    content_type=doc.content_type or "",
                    file_type=doc.file_type or "",
                    display_name=metadata.get("title"),
                    category=metadata.get("category"),
                    created_at=doc.created_at,
                    metadata=metadata,
                )
            )
        return results
    except Exception as e:
        logger.error(f"Document listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents",
        )


@router.get("/documents/{document_id}/download")
async def download_document(document_id: str, db: Session = Depends(get_db_session)):
    """Download document PDF"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )

        # Derive file path from docs directory and filename
        file_path = Path(f"/app/docs/{document.filename}")
        if not file_path.exists():
            logger.error(f"Document file not found: {file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not available",
            )

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/pdf"

        return FileResponse(
            path=str(file_path),
            media_type=mime_type,
            filename=(
                getattr(document, "meta", {}).get("title")
                if isinstance(getattr(document, "meta", {}), dict)
                else document.filename
            )
            or document.filename,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document download failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Download failed"
        )


@router.get("/contacts/{specialty}", response_model=ContactResponse)
async def get_contact(
    specialty: str, processor: QueryProcessor = Depends(get_query_processor)
):
    """Get on-call contact for specialty"""
    try:
        contact = await processor.get_on_call_contact(specialty)
        return contact
    except Exception as e:
        logger.error(f"Contact lookup failed for {specialty}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact not found for specialty: {specialty}",
        )


@router.get("/search")
async def search_documents(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum results"),
    db: Session = Depends(get_db_session),
):
    """Search documents by content"""
    try:
        # Simple text search - can be enhanced with vector search
        documents = (
            db.query(Document).filter(Document.content.contains(q)).limit(limit).all()
        )

        return [DocumentResponse.from_orm(doc) for doc in documents]
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Search failed"
        )


@router.post("/validate")
async def validate_query(
    request: QueryRequest, processor: QueryProcessor = Depends(get_query_processor)
):
    """Validate query safety and compliance"""
    try:
        validation_result = await processor.validate_query(request.query)
        return {
            "is_valid": validation_result.is_valid,
            "warnings": validation_result.warnings,
            "confidence": validation_result.confidence,
        }
    except Exception as e:
        logger.error(f"Query validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation failed",
        )
