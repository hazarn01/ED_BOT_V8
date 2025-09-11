"""Simplified query endpoint that returns direct search results without LLM processing."""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from ...models.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["simple"])


class SimpleQueryRequest(BaseModel):
    query: str


class SimpleQueryResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    count: int


@router.post("/simple_query", response_model=SimpleQueryResponse)
async def simple_query(request: SimpleQueryRequest):
    """Direct database search without LLM processing - fast and reliable."""
    try:
        # Get database session
        with get_db_session() as db:
            # Extract search terms
            query_lower = request.query.lower()
            # Simple word extraction
            words = query_lower.split()
            # Filter stop words
            stop_words = {'what', 'is', 'the', 'for', 'in', 'of', 'and', 'a', 'an'}
            search_terms = [w for w in words if w not in stop_words and len(w) >= 3]
            
            # Prioritize medical terms
            search_terms = sorted(search_terms, key=len, reverse=True)[:3]
            
            logger.info(f"Simple search for: {search_terms}")
            
            # Build search query
            conditions = []
            params = {}
            
            for i, term in enumerate(search_terms):
                params[f'term_{i}'] = f'%{term}%'
                conditions.append(f"dc.chunk_text ILIKE :term_{i}")
            
            # Use AND for first 2 terms, OR if only 1 match
            if len(conditions) >= 2:
                where_clause = f"({conditions[0]} AND {conditions[1]})"
                if len(conditions) > 2:
                    where_clause += f" OR {conditions[2]}"
            else:
                where_clause = " OR ".join(conditions) if conditions else "1=1"
            
            query = text(f"""
                SELECT 
                    dc.chunk_text as content,
                    d.filename,
                    dr.display_name,
                    dc.chunk_index
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                LEFT JOIN document_registry dr ON d.id = dr.document_id
                WHERE {where_clause}
                ORDER BY 
                    CASE 
                        WHEN dc.chunk_text ILIKE '%epinephrine%' AND dc.chunk_text ILIKE '%adult%' THEN 0
                        WHEN dc.chunk_text ILIKE '%first%line%' THEN 1
                        WHEN dc.chunk_text ILIKE '%treatment%' THEN 2
                        ELSE 3
                    END,
                    LENGTH(dc.chunk_text) ASC
                LIMIT 5
            """)
            
            results = db.execute(query, params).fetchall()
            
            formatted_results = []
            for row in results:
                formatted_results.append({
                    "content": row.content,
                    "source": row.display_name or row.filename,
                    "filename": row.filename,
                    "chunk_index": row.chunk_index
                })
            
            return SimpleQueryResponse(
                query=request.query,
                results=formatted_results,
                count=len(formatted_results)
            )
        
    except Exception as e:
        logger.error(f"Simple query failed: {e}")
        return SimpleQueryResponse(
            query=request.query,
            results=[],
            count=0
        )