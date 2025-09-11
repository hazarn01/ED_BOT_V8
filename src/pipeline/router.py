import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from redis import Redis
from sqlalchemy.orm import Session

from ..cache.metrics import semantic_cache_metrics
from ..cache.semantic_cache import SemanticCache
from ..config.settings import Settings
from ..models.entities import (
    Document,
    DocumentChunk,
    DocumentRegistry,
    ExtractedEntity,
    QueryResponseCache,
)
from ..models.query_types import QueryType
from ..observability import qa_metrics
from ..search.elasticsearch_client import ElasticsearchClient

# from ..ai.gpt_oss_client import GPTOSSClient  # Remove tight coupling
from ..validation.medical_validator import MedicalValidator
from ..validation.protocol_validator import ProtocolResponseValidator
from .hybrid_retriever import HybridRetriever
from .qa_index import QAIndex
from .rag_retriever import RAGRetriever
from .source_highlighter import SourceHighlighter
from .table_retriever import TableRetriever

logger = logging.getLogger(__name__)


class QueryRouter:
    """Routes queries to appropriate handlers based on classification."""

    def __init__(
        self,
        db: Session,
        redis: Redis,
        llm_client,
        settings: Optional[Settings] = None,
        semantic_cache: Optional[SemanticCache] = None
    ):
        self.db = db
        self.redis = redis
        self.llm_client = llm_client
        self.validator = MedicalValidator()
        self.settings = settings
        self.semantic_cache = semantic_cache

        # Initialize source highlighter (PRP 17)
        self.highlighter = SourceHighlighter(settings) if settings else None

        # Initialize table retriever (PRP 19)
        self.table_retriever = TableRetriever(
            db, settings) if settings else None

        # Initialize retriever based on configuration
        self.rag_retriever = RAGRetriever(db)

        if settings and settings.search_backend == "hybrid":
            # Initialize hybrid retriever
            es_client = ElasticsearchClient(settings)
            self.retriever = HybridRetriever(
                self.rag_retriever, es_client, settings)
            logger.info("Initialized HybridRetriever for search backend")
        else:
            # Use RAG retriever directly
            self.retriever = self.rag_retriever
            logger.info("Using RAGRetriever as search backend")

        # Ground-truth QA fallback
        self.qa_index = QAIndex.load()

    async def route_query(
        self,
        query: str,
        query_type: QueryType,
        context: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Route query to appropriate handler based on type."""

        # Check semantic cache first
        if self.semantic_cache:
            cached_response = await self.semantic_cache.get(query, query_type)
            if cached_response:
                # Record cache hit metric
                semantic_cache_metrics.record_cache_hit(
                    query_type.value,
                    cached_response.similarity
                )

                logger.info(f"Semantic cache hit for {query_type.value} query")

                # Return cached response with cache metadata
                response = cached_response.response.copy()
                response["metadata"] = response.get("metadata", {})
                response["metadata"]["cache_hit"] = True
                response["metadata"]["similarity"] = cached_response.similarity
                response["metadata"]["cached_at"] = cached_response.created_at.isoformat()

                return response

        # Record cache miss if cache is enabled
        if self.semantic_cache:
            semantic_cache_metrics.record_cache_miss(query_type.value)

        # Router safety check (Task 34): if classified as SUMMARY but QA strongly suggests a curated type,
        # re-route to that type to avoid generic summaries.
        suggested = self._suggest_query_type_from_qa(query)
        if query_type == QueryType.SUMMARY_REQUEST and suggested in (
            QueryType.PROTOCOL_STEPS,
            QueryType.CRITERIA_CHECK,
            QueryType.DOSAGE_LOOKUP,
        ):
            logger.info(
                f"Router safety override: SUMMARY -> {suggested.value} based on QA suggestion"
            )
            query_type = suggested

        handlers = {
            QueryType.CONTACT_LOOKUP: self._handle_contact_query,
            QueryType.FORM_RETRIEVAL: self._handle_form_query,
            QueryType.PROTOCOL_STEPS: self._handle_protocol_query,
            QueryType.CRITERIA_CHECK: self._handle_criteria_query,
            QueryType.DOSAGE_LOOKUP: self._handle_dosage_query,
            QueryType.SUMMARY_REQUEST: self._handle_summary_query,
        }

        handler = handlers.get(query_type, self._handle_unknown_query)
        result = await handler(query, context, user_id)

        # Cache the response if semantic cache is enabled
        if self.semantic_cache and result:
            await self._cache_response(query, query_type, result)

        # Add source highlighting and viewer URL if enabled (PRP 17-18)
        if self.highlighter and self.settings:
            result = await self._add_highlighting_to_response(result, query, query_type)

        return result

    def _qa_fallback(self, query: str, qtype: QueryType) -> Optional[Dict[str, Any]]:
        logger.info(
            f"DEBUG: QA fallback called with query='{query}', qtype={qtype}")

        # Map QueryType to QA data types
        type_mapping = {
            'protocol': ['protocol_steps', 'workflow', 'protocol'],
            'contact': ['contact'],
            'criteria': ['criteria', 'criteria_check'],
            'dosage': ['dosage_lookup', 'medication'],
            'form': ['form'],
            'summary': ['summary']
        }

        expected = qtype.value.lower() if hasattr(
            qtype, 'value') else str(qtype).lower()
        possible_types = type_mapping.get(expected, [expected])
        logger.info(
            f"DEBUG: Expected type='{expected}', possible_types={possible_types}")

        # Try each possible type
        best_match = None
        for qa_type in possible_types:
            match = self.qa_index.find_best(query, expected_type=qa_type)
            if match:
                entry, score = match
                logger.info(
                    f"DEBUG: Type '{qa_type}' found match: score={score:.3f}, question='{entry.question[:50]}...'")
                if not best_match or score > best_match[1]:
                    best_match = match
            else:
                logger.info(f"DEBUG: Type '{qa_type}' found no match")

        # If no type-specific match, try without type restriction
        if not best_match:
            logger.info(
                "DEBUG: No type-specific match, trying without type restriction")
            best_match = self.qa_index.find_best(query, expected_type=None)
            if best_match:
                entry, score = best_match
                logger.info(
                    f"DEBUG: No-type match found: score={score:.3f}, question='{entry.question[:50]}...'")
            else:
                logger.info(
                    "DEBUG: No match found even without type restriction")

        if not best_match:
            logger.info(f"DEBUG: QA fallback returning None - no match found")
            qa_metrics.record_miss(qtype.value)
            return None

        match = best_match
        entry, score = match
        response = entry.answer
        sources = [entry.source_dict()]
        qa_metrics.record_hit(qtype.value, score)
        return {
            "response": response,
            "sources": sources,
            "confidence": min(1.0, 0.6 + score * 0.4),
            "metadata": {
                "qa_fallback": True,
                "qa_score": score,
                "query_type": expected,
            }
        }

    def _suggest_query_type_from_qa(self, query: str) -> Optional[QueryType]:
        """Suggest a query type using QA index when classification is ambiguous (Task 34)."""
        try:
            match = self.qa_index.find_best(query, expected_type=None)
            if not match:
                return None
            entry, score = match
            # Map entry.query_type (may be 'protocol_steps' etc.) to base QueryType
            qt = (entry.query_type or "").lower()
            mapping = {
                "protocol_steps": QueryType.PROTOCOL_STEPS,
                "protocol": QueryType.PROTOCOL_STEPS,
                "criteria_check": QueryType.CRITERIA_CHECK,
                "criteria": QueryType.CRITERIA_CHECK,
                "dosage_lookup": QueryType.DOSAGE_LOOKUP,
                "dosage": QueryType.DOSAGE_LOOKUP,
                "form_retrieval": QueryType.FORM_RETRIEVAL,
                "form": QueryType.FORM_RETRIEVAL,
                "contact": QueryType.CONTACT_LOOKUP,
                "contact_lookup": QueryType.CONTACT_LOOKUP,
            }
            return mapping.get(qt)
        except Exception:
            return None

    async def _retrieve_documents(
        self,
        query: str,
        query_type: QueryType,
        k: int = 5
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Unified retrieval method that works with both RAG and Hybrid retrievers.

        Args:
            query: Search query
            query_type: Type of query for hybrid fusion
            k: Number of results

        Returns:
            Tuple of (search results, source citations)
        """
        try:
            if isinstance(self.retriever, HybridRetriever):
                # Use hybrid retrieval
                retrieval_results = await self.retriever.retrieve(
                    query=query,
                    query_type=query_type,
                    top_k=k,
                    filters=self._get_content_type_filter(query_type)
                )

                # Convert to format expected by existing handlers
                search_results = []
                sources = []

                for result in retrieval_results:
                    # Build result in format expected by handlers
                    search_result = {
                        "chunk_id": result.chunk_id,
                        "document_id": result.document_id,
                        "content": result.content,
                        "similarity": result.score,
                        "metadata": result.metadata,
                        "source": {
                            "display_name": result.metadata.get("display_name", "Unknown"),
                            "filename": result.metadata.get("filename", "unknown"),
                            "content_type": result.metadata.get("content_type"),
                            "category": result.metadata.get("category")
                        }
                    }
                    search_results.append(search_result)

                    # Add source info
                    source_info = {
                        "display_name": result.metadata.get("display_name", "Unknown"),
                        "filename": result.metadata.get("filename", "unknown")
                    }
                    if source_info not in sources:
                        sources.append(source_info)

                return search_results, sources

            else:
                # Use traditional RAG retrieval
                return self.rag_retriever.retrieve_for_query_type(
                    query=query,
                    query_type=query_type.value.lower(),
                    k=k
                )

        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return [], []

    def _get_content_type_filter(self, query_type: QueryType) -> Optional[Dict[str, str]]:
        """Get content type filter for query type."""
        content_type_map = {
            QueryType.PROTOCOL_STEPS: "protocol",
            QueryType.CRITERIA_CHECK: "criteria",
            QueryType.DOSAGE_LOOKUP: "medication",
            QueryType.FORM_RETRIEVAL: "form",
            QueryType.SUMMARY_REQUEST: None  # Search all types
        }

        content_type = content_type_map.get(query_type)
        return {"content_type": content_type} if content_type else None

    async def _handle_contact_query(
        self, query: str, context: Optional[str], user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle CONTACT queries - on-call physician lookup."""
        try:
            # Extract specialty from query
            specialty = self._extract_specialty(query)

            # Mock contact data - in production would integrate with Amion
            contact_data = {
                "cardiology": {
                    "name": "Dr. Sarah Johnson",
                    "phone": "555-123-4567",
                    "pager": "555-987-6543",
                },
                "surgery": {
                    "name": "Dr. Michael Chen",
                    "phone": "555-234-5678",
                    "pager": "555-876-5432",
                },
            }

            contact = contact_data.get(
                specialty.lower(),
                {
                    "name": "On-call physician",
                    "phone": "555-000-0000",
                    "pager": "555-000-0001",
                },
            )

            response = (
                f"The on-call {specialty} physician is {contact['name']}. "
                f"Phone: {contact['phone']}, Pager: {contact['pager']}"
            )

            return {
                "response": response,
                "sources": [{"display_name": "Amion On-Call Schedule", "filename": "amion_schedule"}],
                "contact_info": contact,
            }

        except Exception as e:
            logger.error(f"Contact query failed: {e}")
            return {
                "response": "Unable to retrieve contact information at this time.",
                "sources": [],
                "warnings": ["Contact lookup failed"],
            }

    async def _handle_form_query(
        self, query: str, context: Optional[str], user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle FORM queries - direct PDF retrieval using filename matching."""
        try:
            # Find best matching form using filename patterns
            doc = self._find_best_form_match(query)

            if not doc:
                # Get available forms to suggest
                available_forms = (
                    self.db.query(Document)
                    .filter(Document.content_type == "form")
                    .limit(5)
                    .all()
                )

                suggestions = [form.filename.replace('.pdf', '').replace('_', ' ').title()
                               for form in available_forms]

                return {
                    "response": f"No forms found matching your request. Available forms include: {', '.join(suggestions[:3])}.",
                    "sources": [],
                }

            # Return the matching document
            display_name = self._get_form_display_name(doc)
            pdf_links = [
                {
                    "filename": doc.filename,
                    "display_name": display_name,
                    "url": f"/api/v1/documents/{doc.id}/download",
                }
            ]

            response = f"Found the {display_name}. Click the link below to download."

            # Get display name from registry if available
            registry = (
                self.db.query(DocumentRegistry)
                .filter(DocumentRegistry.document_id == doc.id)
                .first()
            )

            source_info = {
                "display_name": registry.display_name if registry else display_name,
                "filename": doc.filename
            }

            return {
                "response": response,
                "sources": [source_info],
                "pdf_links": pdf_links,
            }

        except Exception as e:
            logger.error(f"Form query failed: {e}")
            return {
                "response": "Unable to retrieve form at this time.",
                "sources": [],
                "warnings": ["Form retrieval failed"],
            }

    async def _handle_protocol_query(
        self, query: str, context: Optional[str], user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle PROTOCOL queries - clinical protocols with steps and timing."""
        try:
            # TEMPORARILY DISABLE curated responses to test QA fallback
            # from .curated_responses import curated_db
            # curated_match = curated_db.find_curated_response(query, threshold=0.6)
            # if curated_match:
            #     curated_response, match_score = curated_match
            #     return {
            #         "response": curated_response.response,
            #         "sources": curated_response.sources,
            #         "confidence": curated_response.confidence,
            #         "warnings": [f"✅ Curated medical protocol (match: {match_score:.1%})"]
            #     }

            # Ground-truth QA fallback
            logger.info(f"DEBUG: Trying QA fallback for query: {query}")
            qa = self._qa_fallback(query, QueryType.PROTOCOL_STEPS)
            logger.info(f"DEBUG: QA fallback result: {qa is not None}")
            if qa:
                logger.info(f"DEBUG: Returning QA fallback response")
                return qa
            # First try table retrieval for structured protocol tables (PRP 19)
            if self.table_retriever and self.table_retriever.enabled:
                protocol_name = self._extract_protocol_name(query)
                protocol_tables = await self.table_retriever.retrieve_protocol_tables(protocol_name)

                if protocol_tables:
                    logger.info(
                        f"Found {len(protocol_tables)} protocol tables")

                    # Use the best matching table
                    best_table = protocol_tables[0]

                    # Format table response
                    table_response = self.table_retriever.format_table_response(
                        best_table)

                    sources = [{"display_name": best_table.document.filename,
                                "filename": best_table.document.filename}]

                    return {
                        "response": table_response,
                        "sources": sources,
                        "table_data": {
                            "table_type": best_table.table_type,
                            "headers": best_table.headers,
                            "rows": best_table.rows,
                            "confidence": best_table.confidence
                        }
                    }

            # Fallback: Use unified retrieval (hybrid or RAG) to find relevant protocol documents
            search_results, source_citations = await self._retrieve_documents(
                query=query,
                query_type=QueryType.PROTOCOL_STEPS,
                k=5
            )

            # Validate result quality to prevent irrelevant responses (PRP-40)
            validator = ProtocolResponseValidator()
            if search_results and not validator.validate_protocol_response(query, search_results):
                logger.warning(
                    f"Protocol query returned low-quality results for: {query}")
                # Check specifically for sepsis queries
                if 'sepsis' in query.lower() and not validator.validate_sepsis_response(query, search_results):
                    return {
                        "response": "I don't have specific sepsis protocol information available in my current medical documents. For ED sepsis management, please consult your institution's clinical protocols, UpToDate, or contact the attending physician.",
                        "sources": [],
                        "confidence": 0.1,
                        "warnings": ["No high-quality protocol content found for this query"]
                    }
                # Generic low-quality response
                return {
                    "response": "I don't have specific protocol information available for this query. Please consult your institution's clinical protocols or medical references.",
                    "sources": [],
                    "confidence": 0.1,
                    "warnings": ["No high-quality protocol content found"]
                }

            if not search_results:
                # Fallback to entity search
                protocol_entities = (
                    self.db.query(ExtractedEntity)
                    .filter(ExtractedEntity.entity_type == "protocol")
                    .all()
                )

                if not protocol_entities:
                    return await self._generate_llm_response(query, "protocol", context, sources=[])

                # Use entity data
                protocol_data = protocol_entities[0].payload
                sources = self._resolve_document_sources_with_display_names(
                    [entity.document_id for entity in protocol_entities]
                )
            else:
                # Build context from RAG results
                context_parts = []
                sources = []

                for result in search_results[:3]:  # Use top 3 results
                    context_parts.append(result["content"])
                    source_info = result.get("source", {})
                    sources.append({
                        "display_name": source_info.get("display_name", "Unknown"),
                        "filename": source_info.get("filename", "unknown")
                    })

                # Generate response using LLM with context
                llm_response = await self._generate_llm_response(
                    query,
                    "protocol",
                    "\n".join(context_parts),
                    sources=sources
                )

                # Preserve source citations
                llm_response["sources"] = sources
                return llm_response

            # Format protocol response
            steps = protocol_data.get("steps", [])
            response = f"**{protocol_data.get('name', 'Clinical Protocol')}**\n\n"

            for i, step in enumerate(steps, 1):
                timing = f" ({step.get('timing', '')})" if step.get(
                    "timing") else ""
                response += f"{i}. {step.get('action', '')}{timing}\n"

            if protocol_data.get("critical_timing"):
                response += f"\n⚠️ **Critical Timing**: {protocol_data['critical_timing']}"

            return {
                "response": response,
                "sources": sources,
                "protocol_data": protocol_data,
            }

        except Exception as e:
            logger.error(f"Protocol query failed: {e}")
            return await self._generate_llm_response(query, "protocol", context, sources=[])

    async def _handle_criteria_query(
        self, query: str, context: Optional[str], user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle CRITERIA queries - clinical decision criteria."""
        try:
            # Ground-truth first
            qa = self._qa_fallback(query, QueryType.CRITERIA_CHECK)
            if qa:
                return qa
            # Use RAG retrieval to find relevant criteria information
            logger.info("Using RAG retrieval for criteria query")
            search_results, raw_sources = await self._retrieve_documents(query, QueryType.CRITERIA_CHECK, k=5)

            if not search_results:
                logger.info(
                    "No criteria content found via RAG, falling back to LLM")
                return await self._generate_llm_response(query, "criteria", context, sources=[])

            # Build context from retrieved results
            context_parts = []
            sources = []

            for result in search_results[:3]:  # Use top 3 results
                context_parts.append(result["content"])
                source_info = result.get("source", {})
                sources.append({
                    "display_name": source_info.get("display_name", "Unknown"),
                    "filename": source_info.get("filename", "unknown")
                })

            context = "\n\n---\n\n".join(context_parts)

            # Generate response using LLM with retrieved context (Task 36 tuned params)
            return await self._generate_llm_response(query, "criteria", context, sources)

        except Exception as e:
            logger.error(f"Criteria query failed: {e}")
            return await self._generate_llm_response(query, "criteria", context, sources=[])

    async def _handle_dosage_query(
        self, query: str, context: Optional[str], user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle DOSAGE queries - medication dosing with safety validation."""
        try:
            # Ground-truth first
            qa = self._qa_fallback(query, QueryType.DOSAGE_LOOKUP)
            if qa:
                return qa
            # Extract medication name
            medication = self._extract_medication(query)
            logger.info(f"Extracted medication: {medication}")

            # First try table retrieval (PRP 19)
            if self.table_retriever and self.table_retriever.enabled:
                dosage_tables = await self.table_retriever.retrieve_tables_by_medication(medication)

                if dosage_tables:
                    logger.info(f"Found {len(dosage_tables)} dosage tables")

                    # Use the best matching table
                    best_table = dosage_tables[0]

                    # Format table response
                    table_response = self.table_retriever.format_table_response(
                        best_table)

                    sources = [{"display_name": best_table.document.filename,
                                "filename": best_table.document.filename}]

                    return {
                        "response": table_response,
                        "sources": sources,
                        "table_data": {
                            "table_type": best_table.table_type,
                            "headers": best_table.headers,
                            "rows": best_table.rows,
                            "confidence": best_table.confidence
                        }
                    }

            # Use RAG retrieval to find relevant dosage information
            logger.info("Using RAG retrieval for dosage query")
            search_results, raw_sources = await self._retrieve_documents(query, QueryType.DOSAGE_LOOKUP, k=5)

            if not search_results:
                logger.info(
                    "No dosage content found via RAG, falling back to LLM")
                return await self._generate_llm_response(query, "dosage", context, sources=[])

            # Build context from retrieved results
            context_parts = []
            sources = []

            for result in search_results[:3]:  # Use top 3 results
                context_parts.append(result["content"])
                source_info = result.get("source", {})
                sources.append({
                    "display_name": source_info.get("display_name", "Unknown"),
                    "filename": source_info.get("filename", "unknown")
                })

            context = "\n\n---\n\n".join(context_parts)

            # Generate response using LLM with retrieved context (Task 36 tuned params)
            return await self._generate_llm_response(query, "dosage", context, sources)

        except Exception as e:
            logger.error(f"Dosage query failed: {e}")
            return await self._generate_llm_response(query, "dosage", context, sources=[])

    async def _handle_summary_query(
        self, query: str, context: Optional[str], user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle SUMMARY queries - multi-source synthesis."""
        try:
            # Use unified retrieval (hybrid or RAG) for summary queries
            search_results, source_citations = await self._retrieve_documents(
                query=query,
                query_type=QueryType.SUMMARY_REQUEST,
                k=10  # Get more results for summary
            )

            # Build context from search results
            context_parts = []
            sources = []

            for result in search_results[:5]:  # Use top 5 results
                context_parts.append(result["content"])
                source_info = result.get("source", {})
                if isinstance(source_info, dict):
                    sources.append(source_info)
                else:
                    sources.append(
                        {"display_name": source_info, "filename": source_info})

            final_context = context or "\n".join(context_parts)
            return await self._generate_llm_response(query, "summary", final_context, sources=sources)
        except Exception as e:
            logger.error(f"Summary query failed: {e}")
            return {
                "response": "Unable to generate summary at this time.",
                "sources": [],
                "warnings": ["Summary generation failed"],
            }

    async def _handle_unknown_query(
        self, query: str, context: Optional[str], user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle unclassified queries."""
        return {
            "response": "I'm not sure how to help with that query. Please try rephrasing or contact support.",
            "sources": [],
            "warnings": ["Query type could not be determined"],
        }

    async def _generate_llm_response(
        self, query: str, query_type: str, context: Optional[str], sources: Optional[list] = None
    ) -> Dict[str, Any]:
        """Generate response using LLM for complex queries with strict document-only mode."""
        try:
            # First check if we have valid context - if not, return appropriate response
            if not context or not context.strip():
                return {
                    "response": "I don't have specific information about this in my medical documents. Please consult medical references, pharmacy, or your attending physician for accurate information.",
                    "sources": sources or [],
                    "retrieved_context": [],
                    "warnings": ["No relevant medical documents found for this query"]
                }

            # Build strict document-only prompt
            prompt = f"""You are a medical AI assistant for emergency department staff. Answer this {query_type} query based ONLY on the provided medical documents.

CRITICAL REQUIREMENTS:
1. Use ONLY information from the provided context - do not add general medical knowledge
2. Include specific numerical values, dosages, and protocols exactly as written
3. Cite sources using exact document names: [Source: Document Name]
4. If the context doesn't contain enough information, say "The available documents don't contain sufficient information for this query"
5. Be specific and detailed - include timing, dosages, contact numbers when available

Query: {query}
            
Context from medical documents:
{context}"""

            # Add source list for proper citation
            if sources:
                source_names = []
                for source in sources:
                    if isinstance(source, dict):
                        source_names.append(source.get(
                            "display_name", source.get("filename", "Unknown")))
                    else:
                        source_names.append(str(source))
                prompt += f"\n\nDocument sources to cite: {', '.join(source_names)}"

            # Task 36: Tune parameters per query type
            temp = 0.0
            top_p = 0.1
            max_tokens = 800 if query_type in (
                "protocol", "criteria", "dosage") else 400

            text = await self.llm_client.generate(
                prompt=prompt,
                temperature=temp,
                top_p=top_p,
                max_tokens=max_tokens,
            )

            # Default to provided sources or empty list
            response_sources = sources if sources else [
                {"display_name": "Medical Knowledge Base", "filename": "llm_generated"}]

            return {
                "response": text,
                "sources": response_sources,
            }
        except Exception as e:
            logger.error(f"LLM response generation failed: {e}")
            return {
                "response": "I'm unable to process that request right now.",
                "sources": [],
                "warnings": ["LLM generation failed"],
            }

    def _extract_specialty(self, query: str) -> str:
        """Extract medical specialty from contact query."""
        specialties = [
            "cardiology",
            "surgery",
            "neurology",
            "orthopedics",
            "radiology",
            "pathology",
            "emergency",
            "internal medicine",
        ]

        query_lower = query.lower()
        for specialty in specialties:
            if specialty in query_lower:
                return specialty

        return "general"

    def _extract_form_keywords(self, query: str) -> str:
        """Extract form keywords from query."""
        # Simple keyword extraction - can be enhanced
        form_terms = ["consent", "transfusion",
                      "discharge", "admission", "procedure"]

        for term in form_terms:
            if term in query.lower():
                return term

        return query.split()[-1] if query.split() else ""

    def _extract_medication(self, query: str) -> str:
        """Extract medication name from dosage query."""
        # Simple extraction - in production would use NER
        words = query.split()
        for word in words:
            if len(word) > 3 and word.isalpha():
                return word
        return "medication"

    def _extract_medical_terms(self, query: str) -> str:
        """Extract relevant medical terms from query."""
        # Simplified term extraction
        return " ".join([word for word in query.split() if len(word) > 3])

    def _resolve_document_sources(self, document_ids: list) -> list:
        """Resolve document IDs to actual PDF filenames."""
        try:
            if not document_ids:
                return []

            # Query documents by their IDs
            documents = (
                self.db.query(Document)
                .filter(Document.id.in_(document_ids))
                .all()
            )

            # Return list of actual filenames from the docs folder
            sources = []
            for doc in documents:
                # Use the actual filename from the database
                # This ensures we're showing real PDF files, not hallucinated titles
                sources.append(doc.filename)

            return sources

        except Exception as e:
            logger.error(f"Failed to resolve document sources: {e}")
            # Fallback to document IDs if resolution fails
            return [str(doc_id)[:8] + "..." for doc_id in document_ids]

    def _resolve_document_sources_with_display_names(self, document_ids: list) -> list:
        """Resolve document IDs to source information with display names."""
        try:
            if not document_ids:
                return []

            # Query documents and their registry entries
            sources = []
            for doc_id in document_ids:
                doc = self.db.query(Document).filter(
                    Document.id == doc_id).first()
                if doc:
                    # Try to get display name from registry
                    registry = (
                        self.db.query(DocumentRegistry)
                        .filter(DocumentRegistry.document_id == doc_id)
                        .first()
                    )

                    source_info = {
                        "filename": doc.filename,
                        "display_name": registry.display_name if registry else doc.filename.replace('.pdf', '').replace('_', ' ').title()
                    }
                    sources.append(source_info)

            return sources

        except Exception as e:
            logger.error(
                f"Failed to resolve document sources with display names: {e}")
            # Fallback to simple format
            return [{"filename": str(doc_id)[:8] + "...", "display_name": "Document"} for doc_id in document_ids]

    def _find_best_form_match(self, query: str):
        """Find best matching form document based on query keywords."""
        query_lower = query.lower()

        # Define form keyword mappings (ordered by specificity - most specific first)
        form_keywords = [
            ('blood transfusion consent', [
             'mshs_consent_for_elective_blood_transfusion']),
            ('transfusion consent', [
             'mshs_consent_for_elective_blood_transfusion', 'transfusionconsentformspanish']),
            ('consent blood', ['mshs_consent_for_elective_blood_transfusion']),
            ('blood consent', ['mshs_consent_for_elective_blood_transfusion']),
            ('autopsy consent', ['autopsy_consent_form']),
            ('ct consent', ['ct_consent_smartem']),
            ('transfer consent', [
             'msh_ed_transfer_within_mount_sinai_health_system_checklist_and_consent_form']),
            ('electronic consent', ['e-consent_tip_sheet']),
            ('e-consent', ['e-consent_tip_sheet']),
            ('ama departure', ['ama_departure_form']),
            ('ama form', ['ama_departure_form']),
            ('transfer form', [
             'msh_ed_transfer_within_mount_sinai_health_system_checklist_and_consent_form']),
            ('pca infusion', ['pca_infusion_form']),
            ('pca form', ['pca_infusion_form']),
            ('surgical pathology', ['surgical_pathology_req_form']),
            ('pathology form', ['surgical_pathology_req_form']),
            ('clinical debriefing', ['clinical_debriefing_form']),
            ('bed request', ['ed_downtime_bed_request_form']),
            ('downtime bed', ['ed_downtime_bed_request_form']),
            ('radiology request', ['ed_downtime_radiology_request_form']),
            ('domestic violence', [
             'information_for_survivors_of_domestic_violence']),
            # Less specific patterns last
            ('consent form', ['mshs_consent_for_elective_blood_transfusion',
             'autopsy_consent_form', 'ct_consent_smartem']),
        ]

        # Find matching keywords (iterate through ordered list)
        for search_term, file_patterns in form_keywords:
            if search_term in query_lower:
                # Try to find document with matching filename pattern
                for pattern in file_patterns:
                    doc = (
                        self.db.query(Document)
                        .filter(
                            Document.content_type == "form",
                            Document.filename.ilike(f"%{pattern}%")
                        )
                        .first()
                    )
                    if doc:
                        return doc

        # Fallback: try partial filename matching
        query_words = [word for word in query_lower.split() if len(word) > 3]
        for word in query_words:
            doc = (
                self.db.query(Document)
                .filter(
                    Document.content_type == "form",
                    Document.filename.ilike(f"%{word}%")
                )
                .first()
            )
            if doc:
                return doc

        return None

    def _get_form_display_name(self, doc):
        """Get user-friendly display name for form."""
        display_names = {
            'MSHS_Consent_for_Elective_Blood_Transfusion.pdf': 'Blood Transfusion Consent Form',
            'TransfusionConsentFormSpanish.pdf': 'Blood Transfusion Consent Form (Spanish)',
            'AUTOPSY CONSENT FORM 2-2-16.pdf': 'Autopsy Consent Form',
            'AMA Departure Form.pdf': 'Against Medical Advice (AMA) Departure Form',
            'CT_Consent_SMARTEM.pdf': 'CT Scan Consent Form',
            'MSH ED TRANSFER WITHIN MOUNT SINAI HEALTH SYSTEM CHECKLIST AND CONSENT FORM-- 2020.pdf': 'Hospital Transfer Consent Form',
            'PCA Infusion Form.pdf': 'Patient-Controlled Analgesia (PCA) Infusion Form',
            'Surgical Pathology Req form.pdf': 'Surgical Pathology Request Form',
            'ED Downtime Bed Request Form.pdf': 'Emergency Department Bed Request Form',
            'ED Downtime Radiology Request Form.pdf': 'Emergency Department Radiology Request Form',
            'Information for Survivors of Domestic Violence.pdf': 'Domestic Violence Resources Form',
            'Clinical Debriefing Form.pdf': 'Clinical Debriefing Form',
            'E-Consent Tip Sheet.pdf': 'Electronic Consent Information Sheet'
        }

        return display_names.get(doc.filename, doc.filename.replace('.pdf', '').replace('_', ' ').title())

    async def _add_highlighting_to_response(
        self,
        result: Dict[str, Any],
        query: str,
        query_type: QueryType
    ) -> Dict[str, Any]:
        """Add source highlighting and viewer URL to response (PRP 17-18)."""
        try:
            # Only add highlights if we have sources and response text
            if not result.get("sources") or not result.get("response"):
                return result

            # Get document chunks from sources
            chunks = await self._get_chunks_from_sources(result["sources"])

            if not chunks:
                return result

            # Generate highlights
            highlighted_sources = self.highlighter.generate_highlights(
                chunks=chunks,
                query=query,
                response_text=result["response"]
            )

            # Only proceed if we have highlights and viewer is enabled
            if not highlighted_sources or not self.settings.enable_pdf_viewer:
                if highlighted_sources:
                    # Add highlights even if viewer is disabled
                    result["highlighted_sources"] = [
                        {
                            "document_id": h.document_id,
                            "document_name": h.document_name,
                            "page_number": h.page_number,
                            "text_snippet": h.text_snippet,
                            "highlight_spans": [[span[0], span[1]] for span in h.highlight_spans],
                            "bbox": h.bbox,
                            "confidence": h.confidence
                        }
                        for h in highlighted_sources
                    ]
                return result

            # Store response in cache for viewer
            response_id = str(uuid.uuid4())

            cache_entry = QueryResponseCache(
                id=response_id,
                query=query,
                response={
                    "answer": result["response"],
                    "sources": result["sources"],
                    "query_type": query_type.value
                },
                highlights=[
                    {
                        "document_id": h.document_id,
                        "document_name": h.document_name,
                        "page_number": h.page_number,
                        "text_snippet": h.text_snippet,
                        "highlight_spans": [[span[0], span[1]] for span in h.highlight_spans],
                        "bbox": h.bbox,
                        "confidence": h.confidence
                    }
                    for h in highlighted_sources
                ],
                expires_at=datetime.utcnow() + timedelta(hours=self.settings.viewer_cache_ttl_hours)
            )

            self.db.add(cache_entry)
            self.db.commit()

            # Add highlighted sources to response
            result["highlighted_sources"] = [
                {
                    "document_id": h.document_id,
                    "document_name": h.document_name,
                    "page_number": h.page_number,
                    "text_snippet": h.text_snippet,
                    "highlight_spans": [[span[0], span[1]] for span in h.highlight_spans],
                    "bbox": h.bbox,
                    "confidence": h.confidence
                }
                for h in highlighted_sources
            ]

            # Generate viewer URL for the first document with highlights
            if highlighted_sources:
                first_doc = highlighted_sources[0]
                result["viewer_url"] = f"/api/v1/viewer/pdf/{first_doc.document_id}?response_id={response_id}&page={first_doc.page_number}"

            logger.info(
                f"Added {len(highlighted_sources)} highlights and viewer URL to response",
                extra_fields={
                    "response_id": response_id,
                    "highlight_count": len(highlighted_sources)
                }
            )

            return result

        except Exception as e:
            logger.error(f"Failed to add highlighting to response: {e}")
            # Return original result if highlighting fails
            return result

    async def _get_chunks_from_sources(self, sources: List[Dict[str, Any]]) -> List[DocumentChunk]:
        """Get document chunks from source information."""
        try:
            chunks = []

            for source in sources:
                filename = source.get("filename")
                if not filename:
                    continue

                # Find document by filename
                document = self.db.query(Document).filter(
                    Document.filename == filename
                ).first()

                if not document:
                    continue

                # Get chunks for this document
                doc_chunks = self.db.query(DocumentChunk).filter(
                    DocumentChunk.document_id == document.id
                ).all()

                chunks.extend(doc_chunks)

            return chunks

        except Exception as e:
            logger.error(f"Failed to get chunks from sources: {e}")
            return []

    def _extract_protocol_name(self, query: str) -> str:
        """Extract protocol name from query for table retrieval."""
        # Remove common query words
        query_lower = query.lower()
        remove_words = ["what", "is", "the", "show",
                        "me", "protocol", "procedure", "steps"]

        words = query_lower.split()
        protocol_words = [
            word for word in words if word not in remove_words and len(word) > 2]

        # Join remaining words or use the whole query
        if protocol_words:
            return " ".join(protocol_words)
        else:
            return query

    async def _cache_response(
        self,
        query: str,
        query_type: QueryType,
        result: Dict[str, Any]
    ):
        """Cache response using semantic cache.

        Args:
            query: Original query
            query_type: Type of query
            result: Query result to cache
        """
        try:
            # Extract confidence score
            confidence = result.get("confidence", 0.8)

            # Extract sources
            sources = []
            if "sources" in result:
                sources = [
                    source.get("filename", "unknown")
                    for source in result["sources"]
                    if isinstance(source, dict)
                ]

            # Cache the response
            success = await self.semantic_cache.set(
                query=query,
                response=result,
                query_type=query_type,
                sources=sources,
                confidence=confidence
            )

            if success:
                # Record cache set metric
                semantic_cache_metrics.record_cache_set(
                    query_type.value, confidence)
                logger.debug(f"Cached response for {query_type.value} query")
            else:
                logger.debug(
                    f"Response not cached for {query_type.value} query")

        except Exception as e:
            logger.error(f"Failed to cache response: {e}")
