"""Query endpoints for medical queries."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ...models.schemas import QueryRequest, QueryResponse
from ...pipeline.emergency_processor import EmergencyQueryProcessor
from ...validation.hipaa import scrub_phi
from ..dependencies import get_query_processor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest, processor: EmergencyQueryProcessor = Depends(get_query_processor)
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


@router.get("/health-simple")
async def simple_health():
    """Simple health check for query endpoints"""
    return {"status": "ok", "service": "query-endpoints"}
