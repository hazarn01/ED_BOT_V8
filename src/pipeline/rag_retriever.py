"""RAG retrieval module for semantic search and document retrieval."""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.entities import Document, DocumentChunk, DocumentRegistry
from src.pipeline.bm25_scorer import BM25Scorer, BM25Configuration
from src.pipeline.medical_synonym_expander import MedicalSynonymExpander

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Handles semantic search and document retrieval for the RAG pipeline."""
    
    def __init__(self, db: Session, embedding_model=None):
        """Initialize the RAG retriever.
        
        Args:
            db: Database session
            embedding_model: Optional embedding model (defaults to system model)
        """
        self.db = db
        self.embedding_model = embedding_model  # Will be None for now, embeddings handled elsewhere
        
        # Initialize enhanced retrieval components
        try:
            self.bm25_scorer = BM25Scorer(db, BM25Configuration(k1=1.2, b=0.75))
            self.synonym_expander = MedicalSynonymExpander()
            logger.info("Enhanced retrieval components initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize enhanced retrieval: {e}")
            self.bm25_scorer = None
            self.synonym_expander = None
        
    def semantic_search(
        self, 
        query: str, 
        k: int = 5,
        content_type: Optional[str] = None,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using vector similarity.
        
        Args:
            query: Search query
            k: Number of results to return
            content_type: Optional filter by content type
            threshold: Minimum similarity threshold
            
        Returns:
            List of search results with document metadata
        """
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query)
            
            # If embedding generation failed, fall back to text search
            if query_embedding is None:
                logger.warning("Embedding generation failed, falling back to text search")
                return self._fallback_text_search(query, content_type, k)
            
            # Build the vector search query
            search_query = """
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.chunk_text,
                    dc.chunk_index,
                    dc.metadata,
                    d.filename,
                    d.content_type,
                    d.file_type,
                    dr.display_name,
                    dr.category,
                    1 - (dc.embedding <=> %(query_embedding)s::vector) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                LEFT JOIN document_registry dr ON d.id = dr.document_id
                WHERE 1=1
            """
            
            params = {"query_embedding": query_embedding.tolist()}
            
            # Add content type filter if specified
            if content_type:
                search_query += " AND d.content_type = %(content_type)s"
                params["content_type"] = content_type
                
            # Add similarity threshold and ordering
            search_query += """
                AND 1 - (dc.embedding <=> %(query_embedding)s::vector) >= %(threshold)s
                ORDER BY similarity DESC
                LIMIT %(k)s
            """
            params["threshold"] = threshold
            params["k"] = k
            
            # Execute search with direct parameter passing
            params = {
                "query_embedding": query_embedding.tolist(),
                "threshold": threshold, 
                "k": k
            }
            if content_type:
                params["content_type"] = content_type
                
            results = self.db.execute(text(search_query), params).fetchall()
            
            # Format results with full metadata
            formatted_results = []
            for row in results:
                result = {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "content": row.chunk_text,
                    "chunk_index": row.chunk_index,
                    "similarity": float(row.similarity),
                    "metadata": row.metadata or {},
                    "source": {
                        "filename": row.filename,
                        "display_name": row.display_name or row.filename,
                        "content_type": row.content_type,
                        "file_type": row.file_type,
                        "category": row.category
                    }
                }
                formatted_results.append(result)
                
            logger.info(f"Semantic search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            # Fall back to text search on vector search failure
            logger.warning("Vector search failed, falling back to text search")
            return self._fallback_text_search(query, content_type, k)

    def _fallback_text_search(self, query: str, content_type: str = None, k: int = 5):
        """Fallback text-based search when vector search fails."""
        try:
            # Extract meaningful search terms from the query
            search_terms = self._extract_search_terms(query)
            
            # Build search query with medical-aware relevance scoring
            search_conditions = []
            params = {}
            relevance_scores = []
            
            for i, term in enumerate(search_terms):
                param_name = f"term_{i}"
                search_conditions.append(f"dc.chunk_text ILIKE :{param_name}")
                params[param_name] = f"%{term}%"
                
                # Add medical-aware relevance scoring
                relevance_scores.append(f"""
                    (CASE WHEN dc.chunk_text ILIKE :{param_name} THEN
                        -- Base term frequency scoring
                        (LENGTH(dc.chunk_text) - LENGTH(REPLACE(UPPER(dc.chunk_text), UPPER('{term}'), ''))) / LENGTH('{term}')
                        + (CASE WHEN UPPER(dc.chunk_text) LIKE UPPER('%{term}%') THEN 2 ELSE 0 END)
                        -- Medical document priority boost
                        + (CASE 
                            WHEN d.content_type IN ('protocol', 'guideline', 'criteria', 'medication') THEN 50
                            WHEN d.filename ILIKE '%protocol%' OR d.filename ILIKE '%guideline%' OR d.filename ILIKE '%clinical%' THEN 25
                            WHEN dr.category IN ('protocol', 'criteria', 'dosage', 'form') THEN 40
                            ELSE 0 
                        END)
                        -- Medical terminology boost
                        + (CASE 
                            WHEN '{term.upper()}' IN ('STEMI', 'SEPSIS', 'HYPOGLYCEMIA', 'OTTAWA', 'EPINEPHRINE', 'CARDIAC', 'ARREST', 'PROTOCOL', 'CRITERIA', 'DOSAGE') THEN 30
                            WHEN dc.chunk_text ILIKE '%mg%' OR dc.chunk_text ILIKE '%ml%' OR dc.chunk_text ILIKE '%dose%' OR dc.chunk_text ILIKE '%units%' THEN 20
                            WHEN dc.chunk_text ILIKE '%contact%' OR dc.chunk_text ILIKE '%pager%' OR dc.chunk_text ILIKE '%phone%' THEN 15
                            ELSE 0
                        END)
                        -- Penalize non-medical content
                        - (CASE 
                            WHEN d.filename ILIKE '%context_enhancement%' OR d.filename ILIKE '%photography%' OR d.filename ILIKE '%guide%' THEN 100
                            WHEN d.content_type = 'general' OR dr.category = 'general' THEN 50
                            ELSE 0
                        END)
                    ELSE 0 END)
                """)
            
            # Combine conditions with OR for broader matching
            where_clause = " OR ".join(search_conditions) if search_conditions else "1=0"
            relevance_calc = " + ".join(relevance_scores) if relevance_scores else "1.0"
            
            search_query = f"""
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.chunk_text,
                    dc.chunk_index,
                    dc.metadata,
                    d.filename,
                    d.content_type,
                    d.file_type,
                    dr.display_name,
                    dr.category,
                    ({relevance_calc}) as relevance
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                LEFT JOIN document_registry dr ON d.id = dr.document_id
                WHERE ({where_clause})
            """
            
            # Add content type filter if specified
            if content_type:
                search_query += " AND d.content_type = :content_type"
                params["content_type"] = content_type
                
            # Add ordering and limit - order by relevance (highest first)
            search_query += " ORDER BY relevance DESC, LENGTH(dc.chunk_text) DESC LIMIT :k"
            params["k"] = k
            
            # Execute search with colon-style parameter binding
            results = self.db.execute(text(search_query), params).fetchall()
            
            # Format results (similar to vector search format)
            formatted_results = []
            for row in results:
                result = {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "content": row.chunk_text,
                    "chunk_index": row.chunk_index,
                    "similarity": float(row.relevance) if row.relevance else 0.0,
                    "metadata": row.metadata or {},
                    "source": {
                        "filename": row.filename,
                        "display_name": row.display_name or row.filename,
                        "content_type": row.content_type,
                        "file_type": row.file_type,
                        "category": row.category
                    }
                }
                formatted_results.append(result)
                
            logger.info(f"Text search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Text search fallback failed: {e}")
            return []
            
    def get_document_context(
        self,
        document_id: str,
        chunk_index: int,
        context_window: int = 2
    ) -> Dict[str, Any]:
        """Retrieve document context around a specific chunk.
        
        Args:
            document_id: Document ID
            chunk_index: Index of the target chunk
            context_window: Number of chunks before/after to include
            
        Returns:
            Document context with surrounding chunks
        """
        try:
            # Get the target chunk and surrounding chunks
            chunks = (
                self.db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .filter(
                    DocumentChunk.chunk_index >= chunk_index - context_window,
                    DocumentChunk.chunk_index <= chunk_index + context_window
                )
                .order_by(DocumentChunk.chunk_index)
                .all()
            )
            
            if not chunks:
                return {}
                
            # Get document metadata
            doc = self.db.query(Document).filter(Document.id == document_id).first()
            registry = (
                self.db.query(DocumentRegistry)
                .filter(DocumentRegistry.document_id == document_id)
                .first()
            )
            
            # Combine chunks into context
            context_text = "\n".join([chunk.chunk_text for chunk in chunks])
            
            return {
                "document_id": document_id,
                "context": context_text,
                "chunks": [
                    {
                        "index": chunk.chunk_index,
                        "text": chunk.chunk_text,
                        "metadata": chunk.metadata
                    }
                    for chunk in chunks
                ],
                "source": {
                    "filename": doc.filename if doc else "unknown",
                    "display_name": registry.display_name if registry else doc.filename if doc else "unknown",
                    "content_type": doc.content_type if doc else None,
                    "category": registry.category if registry else None
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get document context: {e}")
            return {}
            
    def _simple_medical_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Simple, reliable medical text search with enhanced protocol filtering and BM25 scoring."""
        try:
            # Enhanced query expansion with medical synonyms
            expanded_terms = terms = self._extract_search_terms(query)
            if self.synonym_expander:
                try:
                    from src.models.query_types import QueryType
                    expanded_query = self.synonym_expander.expand_query(query, QueryType.PROTOCOL_STEPS)
                    if expanded_query.expanded_terms:
                        expanded_terms = expanded_query.expanded_terms[:5]  # Limit expansion
                        logger.info(f"Query expanded with synonyms: {len(expanded_query.expanded_terms)} terms")
                except Exception as e:
                    logger.warning(f"Synonym expansion failed: {e}")
            
            # Extract key terms from expanded query
            terms = expanded_terms if expanded_terms else self._extract_search_terms(query)
            if not terms:
                terms = [query.strip()]
                
            logger.info(f"Simple search for terms: {terms}")
            
            # Build search conditions - prioritize key medical terms
            conditions = []
            params = {}
            
            # Identify key medical terms (longer words are often more specific)
            important_terms = sorted(terms, key=len, reverse=True)[:2]  # Use top 2 longest terms
            
            # Always use the most important term
            if important_terms:
                params['term_0'] = f"%{important_terms[0]}%"
                conditions.append("dc.chunk_text ILIKE :term_0")
                
                # Add second term if available
                if len(important_terms) > 1:
                    params['term_1'] = f"%{important_terms[1]}%"
                    conditions.append("dc.chunk_text ILIKE :term_1")
            
            # Enhanced relevance calculation for protocols (PRP-40)
            query_lower = query.lower()
            if 'sepsis' in query_lower or 'protocol' in query_lower:
                # Special handling for protocol queries
                relevance_calc = self._get_protocol_relevance_calc(important_terms, query_lower)
            else:
                # Standard relevance calculation
                relevance_calc = " + ".join([
                    f"CASE WHEN dc.chunk_text ILIKE :term_{i} THEN 1 ELSE 0 END"
                    for i in range(len(important_terms))
                ])
            
            search_query = f"""
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.chunk_text,
                    dc.chunk_index,
                    dc.metadata,
                    d.filename,
                    d.content_type,
                    d.file_type,
                    dr.display_name,
                    dr.category,
                    ({relevance_calc}) as relevance
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                LEFT JOIN document_registry dr ON d.id = dr.document_id
                WHERE ({' AND '.join(conditions)})
                AND LENGTH(dc.chunk_text) > 20
                ORDER BY relevance DESC, d.filename, LENGTH(dc.chunk_text) ASC
                LIMIT :k
            """
            
            params['k'] = k
            
            results = self.db.execute(text(search_query), params).fetchall()
            
            # If AND is too restrictive, fall back to OR
            if len(results) < k and len(important_terms) > 1:
                logger.info(f"AND search too restrictive ({len(results)} results), trying OR")
                
                or_query = f"""
                    SELECT 
                        dc.id,
                        dc.document_id,
                        dc.chunk_text,
                        dc.chunk_index,
                        dc.metadata,
                        d.filename,
                        d.content_type,
                        d.file_type,
                        dr.display_name,
                        dr.category,
                        ({relevance_calc}) as relevance
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    LEFT JOIN document_registry dr ON d.id = dr.document_id
                    WHERE ({' OR '.join(conditions)})
                    AND LENGTH(dc.chunk_text) > 20
                    ORDER BY relevance DESC, d.filename, LENGTH(dc.chunk_text) ASC
                    LIMIT :k
                """
                results = self.db.execute(text(or_query), params).fetchall()
            
            logger.info(f"Simple search returned {len(results)} results")
            
            # Format results with BM25 scoring enhancement
            formatted_results = []
            
            # Apply BM25 scoring if available
            if self.bm25_scorer and results:
                try:
                    # Convert results to format expected by BM25 scorer
                    candidate_chunks = []
                    for row in results:
                        chunk_dict = {
                            'id': row.id,
                            'document_id': row.document_id,
                            'chunk_text': row.chunk_text,
                            'chunk_index': row.chunk_index,
                            'metadata': row.metadata or {},
                            'filename': row.filename,
                            'content_type': row.content_type,
                            'file_type': row.file_type,
                            'display_name': row.display_name,
                            'category': row.category,
                            'original_relevance': getattr(row, 'relevance', 0.0)
                        }
                        candidate_chunks.append(chunk_dict)
                    
                    # Apply BM25 scoring
                    enhanced_results = self.bm25_scorer.score_sql_results(query, results, k)
                    
                    # Format enhanced results
                    for enhanced_row in enhanced_results:
                        result = {
                            "chunk_id": enhanced_row['id'],
                            "document_id": enhanced_row['document_id'],
                            "content": enhanced_row['chunk_text'],
                            "chunk_index": enhanced_row['chunk_index'],
                            "similarity": enhanced_row.get('final_score', 1.0),
                            "bm25_score": enhanced_row.get('bm25_score', 0.0),
                            "medical_boost": enhanced_row.get('medical_boost', 1.0),
                            "metadata": enhanced_row['metadata'] or {},
                            "source": {
                                "filename": enhanced_row['filename'],
                                "display_name": enhanced_row['display_name'] or enhanced_row['filename'].replace('.pdf', '').replace('_', ' ').title(),
                                "content_type": enhanced_row['content_type'],
                                "file_type": enhanced_row['file_type'],
                                "category": enhanced_row['category']
                            }
                        }
                        formatted_results.append(result)
                        
                    logger.info(f"Applied BM25 scoring to {len(formatted_results)} results")
                    
                except Exception as e:
                    logger.error(f"BM25 scoring failed, falling back to standard scoring: {e}")
                    # Fallback to standard formatting
                    for row in results:
                        result = {
                            "chunk_id": row.id,
                            "document_id": row.document_id,
                            "content": row.chunk_text,
                            "chunk_index": row.chunk_index,
                            "similarity": 1.0,
                            "metadata": row.metadata or {},
                            "source": {
                                "filename": row.filename,
                                "display_name": row.display_name or row.filename.replace('.pdf', '').replace('_', ' ').title(),
                                "content_type": row.content_type,
                                "file_type": row.file_type,
                                "category": row.category
                            }
                        }
                        formatted_results.append(result)
            else:
                # Fallback to standard formatting when BM25 not available
                for row in results:
                    result = {
                        "chunk_id": row.id,
                        "document_id": row.document_id,
                        "content": row.chunk_text,
                        "chunk_index": row.chunk_index,
                        "similarity": 1.0,
                        "metadata": row.metadata or {},
                        "source": {
                            "filename": row.filename,
                            "display_name": row.display_name or row.filename.replace('.pdf', '').replace('_', ' ').title(),
                            "content_type": row.content_type,
                            "file_type": row.file_type,
                            "category": row.category
                        }
                    }
                    formatted_results.append(result)
                
            return formatted_results
            
        except Exception as e:
            logger.error(f"Simple search failed: {e}")
            return []

    def retrieve_for_query_type(
        self,
        query: str,
        query_type: str,
        k: int = 5
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Retrieve relevant documents based on query type with medical-aware ranking.
        
        Args:
            query: User query
            query_type: Type of query (protocol, criteria, etc.)
            k: Number of results
            
        Returns:
            Tuple of (search results, source citations)
        """
        # Use simple search first
        logger.info(f"Using simple search for query: {query}")
        search_results = self._simple_medical_search(query, k)
        
        if not search_results:
            logger.warning("Simple search returned no results")
            return [], []
        
        # Extract unique source citations with display names
        sources = []
        seen_sources = set()
        
        for result in search_results:
            source_info = result.get("source", {})
            display_name = source_info.get("display_name", source_info.get("filename", "unknown"))
            
            if display_name not in seen_sources:
                sources.append(display_name)
                seen_sources.add(display_name)
                
        return search_results, sources

    def _medical_aware_search(self, query: str, query_type: str, content_type: str = None, k: int = 5):
        """Enhanced text search with medical domain awareness and query-type-specific ranking."""
        try:
            # Extract meaningful search terms from the query
            search_terms = self._extract_search_terms(query)
            
            # Build search query with medical-aware relevance scoring
            search_conditions = []
            params = {}
            relevance_scores = []
            
            for i, term in enumerate(search_terms):
                param_name = f"term_{i}"
                search_conditions.append(f"dc.chunk_text ILIKE :{param_name}")
                params[param_name] = f"%{term}%"
                
                # Query-type-specific scoring
                query_type_boost = self._get_query_type_boost(query_type, term)
                
                # Add comprehensive medical-aware relevance scoring
                relevance_scores.append(f"""
                    (CASE WHEN dc.chunk_text ILIKE :{param_name} THEN
                        -- Base term frequency scoring
                        (LENGTH(dc.chunk_text) - LENGTH(REPLACE(UPPER(dc.chunk_text), UPPER('{term}'), ''))) / LENGTH('{term}') * 2
                        
                        -- Medical document priority boost (highest priority)
                        + (CASE 
                            WHEN d.content_type IN ('protocol', 'guideline', 'criteria', 'medication') THEN 100
                            WHEN d.filename ILIKE '%protocol%' OR d.filename ILIKE '%guideline%' OR d.filename ILIKE '%clinical%' THEN 80
                            WHEN dr.category IN ('protocol', 'criteria', 'dosage', 'form') THEN 90
                            WHEN d.filename ILIKE '%STEMI%' OR d.filename ILIKE '%epinephrine%' OR d.filename ILIKE '%ottawa%' THEN 150
                            ELSE 0 
                        END)
                        
                        -- Medical terminology boost
                        + (CASE 
                            WHEN '{term.upper()}' IN ('STEMI', 'SEPSIS', 'HYPOGLYCEMIA', 'OTTAWA', 'EPINEPHRINE', 'CARDIAC', 'ARREST', 'PROTOCOL', 'CRITERIA', 'DOSAGE') THEN 60
                            WHEN dc.chunk_text ILIKE '%mg%' OR dc.chunk_text ILIKE '%ml%' OR dc.chunk_text ILIKE '%dose%' OR dc.chunk_text ILIKE '%units%' THEN 40
                            WHEN dc.chunk_text ILIKE '%contact%' OR dc.chunk_text ILIKE '%pager%' OR dc.chunk_text ILIKE '%phone%' OR dc.chunk_text ILIKE '%917-%' THEN 50
                            WHEN dc.chunk_text ILIKE '%emergency%' OR dc.chunk_text ILIKE '%urgent%' OR dc.chunk_text ILIKE '%acute%' THEN 30
                            ELSE 0
                        END)
                        
                        -- Query-type specific boost
                        + {query_type_boost}
                        
                        -- Heavily penalize non-medical content (must be negative to truly penalize)
                        - (CASE 
                            WHEN d.filename ILIKE '%context_enhancement%' OR d.filename ILIKE '%photography%' OR d.filename ILIKE '%guide%' OR d.filename ILIKE '%readme%' THEN 200
                            WHEN d.content_type = 'general' OR dr.category = 'general' OR d.filename ILIKE '%test%' THEN 100
                            WHEN d.filename ILIKE '%phase_%' OR d.filename ILIKE '%dev%' OR d.filename ILIKE '%example%' THEN 150
                            ELSE 0
                        END)
                        
                        -- Boost for exact medical matches in content
                        + (CASE 
                            WHEN dc.chunk_text ILIKE '%{term}%' AND dc.chunk_text ILIKE '%protocol%' THEN 25
                            WHEN dc.chunk_text ILIKE '%{term}%' AND dc.chunk_text ILIKE '%treatment%' THEN 20
                            WHEN dc.chunk_text ILIKE '%{term}%' AND dc.chunk_text ILIKE '%dose%' THEN 30
                            ELSE 0
                        END)
                    ELSE 0 END)
                """)
            
            # Combine conditions with OR for broader matching
            where_clause = " OR ".join(search_conditions) if search_conditions else "1=0"
            relevance_calc = " + ".join(relevance_scores) if relevance_scores else "1.0"
            
            search_query = f"""
                SELECT 
                    dc.id,
                    dc.document_id,
                    dc.chunk_text,
                    dc.chunk_index,
                    dc.metadata,
                    d.filename,
                    d.content_type,
                    d.file_type,
                    dr.display_name,
                    dr.category,
                    ({relevance_calc}) as relevance
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                LEFT JOIN document_registry dr ON d.id = dr.document_id
                WHERE ({where_clause})
            """
            
            # Add content type filter if specified
            if content_type:
                search_query += " AND d.content_type = :content_type"
                params["content_type"] = content_type
                
            # Add ordering and limit - order by relevance (highest first), then by length
            search_query += " ORDER BY relevance DESC, LENGTH(dc.chunk_text) DESC LIMIT :k"
            params["k"] = k
            
            # Execute search
            results = self.db.execute(text(search_query), params).fetchall()
            
            # Format results
            formatted_results = []
            for row in results:
                result = {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "content": row.chunk_text,
                    "chunk_index": row.chunk_index,
                    "similarity": float(row.relevance) if row.relevance else 0.0,
                    "metadata": row.metadata or {},
                    "source": {
                        "filename": row.filename,
                        "display_name": row.display_name or row.filename,
                        "content_type": row.content_type,
                        "file_type": row.file_type,
                        "category": row.category
                    }
                }
                formatted_results.append(result)
                
            logger.info(f"Medical-aware search returned {len(formatted_results)} results for query type: {query_type}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Medical-aware search failed: {e}")
            # Fallback to original text search
            return self._fallback_text_search(query, content_type, k)

    def _get_query_type_boost(self, query_type: str, term: str) -> str:
        """Get query-type-specific scoring boost for a search term."""
        # Define query-type-specific term priorities
        query_boosts = {
            "protocol": {
                "high": ["protocol", "procedure", "workflow", "steps", "activation", "timing"],
                "medium": ["contact", "pager", "phone", "team", "notification"],
                "keywords": ["STEMI", "sepsis", "trauma", "stroke"]
            },
            "dosage": {
                "high": ["dose", "dosage", "mg", "ml", "units", "frequency", "interval"],
                "medium": ["administration", "route", "IV", "IM", "oral"],
                "keywords": ["epinephrine", "medication", "drug"]
            },
            "criteria": {
                "high": ["criteria", "rules", "score", "assessment", "evaluation"],
                "medium": ["indication", "contraindication", "risk", "factor"],
                "keywords": ["Ottawa", "Glasgow", "APACHE", "clinical"]
            },
            "contact": {
                "high": ["contact", "phone", "pager", "call", "on-call", "extension"],
                "medium": ["department", "team", "fellow", "attending"],
                "keywords": ["cardiology", "surgery", "anesthesia"]
            },
            "form": {
                "high": ["form", "document", "consent", "checklist", "template"],
                "medium": ["patient", "information", "authorization"],
                "keywords": ["transfusion", "surgery", "discharge"]
            }
        }
        
        boosts = query_boosts.get(query_type.lower(), {})
        term_lower = term.lower()
        
        if term_lower in boosts.get("high", []) or term.upper() in boosts.get("keywords", []):
            return "75"
        elif term_lower in boosts.get("medium", []):
            return "50" 
        elif any(keyword.lower() in term_lower for keyword in boosts.get("keywords", [])):
            return "60"
        else:
            return "0"
    
    def _get_protocol_relevance_calc(self, terms: List[str], query_lower: str) -> str:
        """
        Enhanced relevance calculation for protocol queries (PRP-40).
        Boosts relevant protocol content and penalizes irrelevant results.
        """
        base_relevance = []
        
        # Base term matching
        for i in range(len(terms)):
            base_relevance.append(f"CASE WHEN dc.chunk_text ILIKE :term_{i} THEN 2 ELSE 0 END")
        
        # Boost for protocol-specific content
        protocol_boost = """
            + CASE 
                WHEN d.content_type IN ('protocol', 'guideline', 'criteria') THEN 10
                WHEN d.filename ILIKE '%protocol%' OR d.filename ILIKE '%guideline%' THEN 8
                WHEN dr.category IN ('protocol', 'criteria') THEN 8
                ELSE 0
            END
        """
        
        # Specific boosting for sepsis content
        if 'sepsis' in query_lower:
            sepsis_boost = """
                + CASE 
                    WHEN dc.chunk_text ILIKE '%sepsis%' AND dc.chunk_text ILIKE '%lactate%' THEN 20
                    WHEN dc.chunk_text ILIKE '%sepsis%' AND dc.chunk_text ILIKE '%protocol%' THEN 15
                    WHEN dc.chunk_text ILIKE '%sepsis%' THEN 10
                    WHEN dc.chunk_text ILIKE '%lactate%' AND dc.chunk_text ILIKE '%shock%' THEN 10
                    WHEN dc.chunk_text ILIKE '%sirs%' OR dc.chunk_text ILIKE '%infection%' THEN 5
                    ELSE 0
                END
            """
        else:
            sepsis_boost = ""
        
        # Penalty for irrelevant content
        irrelevant_penalty = """
            - CASE 
                WHEN d.filename ILIKE '%chf%' OR dc.chunk_text ILIKE '%heart failure%' THEN 50
                WHEN d.filename ILIKE '%referral%' OR dc.chunk_text ILIKE '%referral line%' THEN 50
                WHEN d.filename ILIKE '%photography%' OR d.filename ILIKE '%context_enhancement%' THEN 100
                WHEN d.filename ILIKE '%test%' OR d.filename ILIKE '%example%' THEN 75
                ELSE 0
            END
        """
        
        # Combine all components
        relevance_calc = " + ".join(base_relevance) + protocol_boost + sepsis_boost + irrelevant_penalty
        
        return relevance_calc
    
    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from a query."""
        import re
        
        # Common stop words to filter out
        stop_words = {
            'what', 'is', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'among', 'can', 'could', 'should', 'would', 'may', 'might', 'will', 'shall',
            'do', 'does', 'did', 'have', 'has', 'had', 'be', 'am', 'is', 'are', 'was', 'were',
            'how', 'when', 'where', 'why', 'which', 'who', 'whom', 'whose', 'that', 'this', 'these', 'those',
            'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself',
            'show', 'tell', 'give', 'get', 'need', 'want'
        }
        
        # Clean and tokenize the query
        # Replace hyphens with spaces to handle "first-line" -> "first line"
        clean_query = re.sub(r'[^\w\s-]', ' ', query.lower())
        clean_query = clean_query.replace('-', ' ')
        words = clean_query.split()
        
        # Filter out stop words and short words
        meaningful_terms = []
        for word in words:
            word = word.strip()
            if word and len(word) >= 3 and word not in stop_words:
                meaningful_terms.append(word)
        
        # Also try to extract medical abbreviations and compound terms
        # Look for all-caps words (likely medical abbreviations)
        caps_words = re.findall(r'\b[A-Z]{2,}\b', query)
        for caps_word in caps_words:
            if caps_word.lower() not in [term.lower() for term in meaningful_terms]:
                meaningful_terms.append(caps_word)
        
        # If no meaningful terms found, use the original query
        if not meaningful_terms:
            meaningful_terms = [query.strip()]
        
        logger.info(f"Extracted search terms from '{query}': {meaningful_terms}")
        return meaningful_terms
        
    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if no model available
        """
        if not self.embedding_model:
            logger.warning("No embedding model configured, falling back to text search")
            return None
            
        try:
            # Use the configured embedding model
            if hasattr(self.embedding_model, 'encode'):
                # Sentence transformer style
                return self.embedding_model.encode(text)
            elif hasattr(self.embedding_model, 'embeddings'):
                # OpenAI style
                response = self.embedding_model.embeddings.create(
                    input=text,
                    model="text-embedding-ada-002"
                )
                return np.array(response.data[0].embedding)
            else:
                logger.warning("Embedding model has no compatible interface")
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
            
    def get_document_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get document information by filename.
        
        Args:
            filename: Document filename
            
        Returns:
            Document information with display name
        """
        try:
            doc = self.db.query(Document).filter(Document.filename == filename).first()
            if not doc:
                return None
                
            registry = (
                self.db.query(DocumentRegistry)
                .filter(DocumentRegistry.document_id == doc.id)
                .first()
            )
            
            return {
                "id": doc.id,
                "filename": doc.filename,
                "display_name": registry.display_name if registry else doc.filename,
                "content_type": doc.content_type,
                "file_type": doc.file_type,
                "category": registry.category if registry else None,
                "metadata": doc.metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to get document by filename: {e}")
            return None
