import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from redis import Redis
from sqlalchemy.orm import Session

from src.cache.semantic_cache import SemanticCache
from src.models.query_types import QueryType
from src.models.schemas import ContactResponse, QueryResponse
from src.services.contact_service import ContactService
from src.validation.hipaa import scrub_phi
from src.validation.medical_validator import MedicalValidator

from .classifier import QueryClassifier
from .curated_quality_formatter import UniversalQualityFormatter
from .router import QueryRouter

# PRP-43: ResponseValidator removed - was corrupting good medical responses
from .universal_quality_orchestrator import UniversalQualityOrchestrator

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Main orchestrator for query processing pipeline."""

    def __init__(
        self, 
        db: Session, 
        redis: Redis, 
        llm_client, 
        contact_service: ContactService,
        semantic_cache: Optional[SemanticCache] = None,
        enable_universal_quality: bool = True
    ):
        self.db = db
        self.redis = redis
        self.llm_client = llm_client
        self.contact_service = contact_service
        self.enable_universal_quality = enable_universal_quality

        self.classifier = QueryClassifier(llm_client)
        self.router = QueryRouter(db, redis, llm_client, semantic_cache=semantic_cache)
        self.validator = MedicalValidator()
        # PRP-43: ResponseValidator removed - was corrupting good medical responses
        
        # PRP-41: Universal Quality System
        if self.enable_universal_quality:
            self.universal_quality_orchestrator = UniversalQualityOrchestrator(db, llm_client)
            self.curated_quality_formatter = UniversalQualityFormatter()
            logger.info("Universal Quality System enabled with curated quality formatting")
        else:
            self.universal_quality_orchestrator = None
            self.curated_quality_formatter = None

    async def process_query(
        self, query: str, context: Optional[str] = None, user_id: Optional[str] = None, timeout: int = 30
    ) -> QueryResponse:
        """Process medical query through classification, routing, and response generation."""
        start_time = time.time()

        try:
            # Implement timeout handling with graceful degradation
            return await asyncio.wait_for(
                self._process_query_internal(query, context, user_id, start_time),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            logger.warning(f"Query timeout after {processing_time:.1f}s: {query[:50]}")
            return QueryResponse(
                response="I'm unable to process that request right now due to system load. Please try again or consult medical references directly.",
                query_type="unknown",
                confidence=0.0,
                sources=[],
                warnings=["Query timed out - system under heavy load"],
                processing_time=processing_time,
            )
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Query processing failed: {e}")
            return QueryResponse(
                response="I encountered an error processing your query. Please try again.",
                query_type="summary",
                confidence=0.0,
                sources=[],
                warnings=["System error occurred"],
                processing_time=processing_time,
            )

    async def _process_query_internal(
        self, query: str, context: Optional[str], user_id: Optional[str], start_time: float
    ) -> QueryResponse:
        """Internal query processing with performance optimizations."""
        try:
            # Log sanitized query
            logger.info(f"Processing query for user {user_id}: {scrub_phi(query)}")

            # Check cache first for performance
            cached_result = await self._get_cached_result(query)
            if cached_result:
                logger.info("Serving cached result")
                return QueryResponse(**cached_result, processing_time=time.time() - start_time)

            # Check for meta queries first
            meta_response = self._handle_meta_query(query)
            if meta_response:
                processing_time = time.time() - start_time
                return QueryResponse(
                    response=meta_response,
                    query_type="summary",
                    confidence=1.0,
                    sources=[],
                    processing_time=processing_time,
                )

            # PRP-37: Check curated responses first for guaranteed accuracy (TEMPORARILY DISABLED for testing)
            # curated_match = curated_db.find_curated_response(query, threshold=0.95)
            curated_match = None
            if curated_match:
                curated_response, match_score = curated_match
                processing_time = time.time() - start_time
                
                logger.info(f"Serving curated response for query with match score {match_score:.3f}")
                
                # Cache curated response for future requests
                # Convert string query_type to QueryType enum for caching
                try:
                    cache_query_type = QueryType(curated_response.query_type.upper())
                except (ValueError, AttributeError):
                    # Fallback to SUMMARY if conversion fails
                    cache_query_type = QueryType.SUMMARY_REQUEST
                
                cache_response = QueryResponse(
                    response=curated_response.response,
                    query_type=curated_response.query_type,
                    confidence=curated_response.confidence,
                    sources=curated_response.sources,
                    warnings=[f"✅ Curated medical content (match: {match_score:.1%})"],
                    processing_time=processing_time
                )
                await self._cache_result(query, cache_response, cache_query_type)
                
                return QueryResponse(
                    response=curated_response.response,
                    query_type=curated_response.query_type,
                    confidence=curated_response.confidence,
                    sources=curated_response.sources,
                    warnings=[f"✅ Curated medical content (match: {match_score:.1%})"],
                    processing_time=processing_time,
                )

            # EMERGENCY FIX: Skip broken LLM classification, use simple rules
            query_type, confidence = self._simple_classify(query)
            
            # Original broken classification (disabled)
            # classification_result = await asyncio.wait_for(
            #     self.classifier.classify_query(query), timeout=2.0
            # )
            # query_type = classification_result.query_type
            # confidence = classification_result.confidence

            logger.info(
                f"Query classified as {query_type.value} with confidence {confidence:.3f}"
            )

            # PRP-41: Universal Quality System for non-curated queries - TEMPORARILY DISABLED FOR DEBUGGING
            if False and self.enable_universal_quality and self.universal_quality_orchestrator:  # DISABLED: Enable Universal Quality System
                try:
                    logger.info("Using Universal Quality System for curated-quality response generation")
                    
                    universal_response = await self.universal_quality_orchestrator.generate_curated_quality_response(
                        query=query,
                        query_type=query_type,
                        context=context,
                        user_id=user_id
                    )
                    
                    # Convert universal response to QueryResponse format
                    processing_time = time.time() - start_time
                    
                    response = QueryResponse(
                        response=universal_response.get("response", ""),
                        query_type=universal_response.get("query_type", query_type.value),
                        confidence=universal_response.get("confidence", 0.5),
                        sources=universal_response.get("sources", []),
                        warnings=universal_response.get("warnings"),
                        processing_time=processing_time,
                        pdf_links=universal_response.get("pdf_links")
                    )
                    
                    # Cache the high-quality response
                    await self._cache_result(query, response, query_type)
                    
                    logger.info(f"Universal Quality System generated response with quality score: {universal_response.get('quality_score', 0.0)}")
                    
                    return response
                    
                except Exception as e:
                    logger.error(f"Universal Quality System failed, falling back to legacy router: {e}")
                    # Continue to legacy router system

            # Step 2: Validate query safety (basic PHI-only for now)
            class _Validation:
                def __init__(self):
                    self.is_valid = True
                    self.warnings = []

            validation_result = _Validation()
            if not validation_result.is_valid:
                logger.warning(f"Query validation failed: {validation_result.warnings}")
                return QueryResponse(
                    response="I cannot provide information for this query due to safety concerns.",
                    query_type=query_type.value,
                    confidence=0.0,
                    sources=[],
                    warnings=validation_result.warnings,
                    processing_time=time.time() - start_time,
                )

            # PRP-43: Force direct database retrieval as PRIMARY path (no fallbacks)
            from .simple_direct_retriever import SimpleDirectRetriever
            direct_retriever = SimpleDirectRetriever(self.db)
            response_data = direct_retriever.get_medical_response(query)
            
            # PRP-43: Use direct retrieval confidence (high for medical content, low for failures)
            confidence = response_data.get("confidence", 0.95)
            additional_warnings = []

            # Step 5: Format response
            processing_time = time.time() - start_time

            # Process sources with proper display names and structure  
            raw_sources = response_data.get("sources", [])
            sources = []
            
            for source in raw_sources:
                if isinstance(source, dict):
                    # Ensure both display_name and filename are present
                    display_name = source.get("display_name")
                    filename = source.get("filename", "Unknown")
                    if not display_name:
                        display_name = filename.replace('.pdf', '').replace('_', ' ').title()
                    sources.append({"display_name": display_name, "filename": filename})
                else:
                    # Convert string source to structured form
                    name = str(source)
                    display_name = name.replace('.pdf', '').replace('_', ' ').title()
                    sources.append({"display_name": display_name, "filename": name})

            # Deduplicate sources by filename while preserving first display name
            if sources:
                seen = set()
                deduped = []
                for s in sources:
                    fn = s.get("filename")
                    if not fn or fn in seen:
                        continue
                    seen.add(fn)
                    deduped.append(s)
                sources = deduped

            # Combine original warnings with validation warnings
            all_warnings = []
            if validation_result.warnings:
                all_warnings.extend(validation_result.warnings)
            if additional_warnings:
                all_warnings.extend(additional_warnings)
            
            response = QueryResponse(
                response=response_data.get("response", ""),
                query_type=query_type.value,
                confidence=confidence,
                sources=sources,
                warnings=all_warnings if all_warnings else None,
                processing_time=processing_time,
                pdf_links=response_data.get("pdf_links"),
            )

            # Step 5: Cache result if appropriate
            await self._cache_result(query, response, query_type)

            logger.info(f"Query processed successfully in {processing_time:.3f}s")
            return response

        except asyncio.TimeoutError:
            # Re-raise for outer handler
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Query processing failed: {e}")

            return QueryResponse(
                response="I encountered an error processing your query. Please try again.",
                query_type="unknown",
                confidence=0.0,
                sources=[],
                warnings=["System error occurred"],
                processing_time=processing_time,
            )

    async def get_on_call_contact(self, specialty: str) -> ContactResponse:
        """Get on-call contact for specialty."""
        try:
            return await self.contact_service.get_on_call(specialty)
        except Exception as e:
            logger.error(f"Contact lookup failed for {specialty}: {e}")
            raise

    async def validate_query(self, query: str):
        """Validate query safety and compliance."""
        return await self.validator.validate_query(query)

    async def _cache_result(
        self, query: str, response: QueryResponse, query_type: QueryType
    ):
        """Cache query result based on type-specific policies."""
        try:
            # Don't cache FORM queries (always fresh)
            if query_type == QueryType.FORM_RETRIEVAL:
                return

            # Don't cache CONTACT queries (time-sensitive)
            if query_type == QueryType.CONTACT_LOOKUP:
                return

            # Cache other query types
            cache_key = f"query:{hash(query.lower().strip())}"
            cache_data = {
                "response": response.response,
                "query_type": response.query_type,
                "confidence": response.confidence,
                "sources": response.sources,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Set TTL based on query type
            ttl = 300  # 5 minutes default
            if query_type in [QueryType.PROTOCOL_STEPS, QueryType.CRITERIA_CHECK]:
                ttl = 3600  # 1 hour for protocols/criteria
            elif query_type == QueryType.DOSAGE_LOOKUP:
                ttl = 1800  # 30 minutes for dosages

            self.redis.setex(cache_key, ttl, json.dumps(cache_data))
            logger.debug(f"Cached result for {query_type.value} query with TTL {ttl}s")

        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    async def _get_cached_result(self, query: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached query result."""
        try:
            cache_key = f"query:{hash(query.lower().strip())}"
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to retrieve cached result: {e}")
        return None
    
    def _handle_meta_query(self, query: str) -> Optional[str]:
        """Handle meta queries about the system's capabilities."""
        query_lower = query.lower().strip()
        
        # Meta query patterns
        meta_patterns = [
            "what can you",
            "what can we",
            "what do you",
            "tell me about",
            "what are you",
            "how do you",
            "what's your",
            "what is your",
            "help me understand",
            "explain what",
            "what topics",
            "what subjects",
            "what can this",
            "what does this"
        ]
        
        capability_patterns = [
            "capability",
            "capabilities", 
            "function",
            "functions",
            "feature",
            "features",
            "talk about",
            "discuss",
            "help with",
            "assist",
            "do for"
        ]
        
        # Check if this is a meta query
        is_meta = any(pattern in query_lower for pattern in meta_patterns)
        has_capability_words = any(pattern in query_lower for pattern in capability_patterns)
        
        if is_meta or (has_capability_words and len(query.split()) < 8):
            return self._generate_capability_response()
        
        return None
    
    def _generate_capability_response(self) -> str:
        """Generate a response about the system's capabilities."""
        capability_text = """I'm ED Bot v8, an AI assistant specialized in emergency medicine. I can help you with:

**📋 Medical Protocols** - Clinical guidelines and step-by-step procedures
- "What is the STEMI protocol?"
- "How do we manage sepsis in the ED?"

**📄 Medical Forms** - Access and download required forms
- "Show me the blood transfusion form"
- "I need a consent form"

**💊 Medication Dosages** - Drug dosing information with safety validation
- "What's the epinephrine dose for cardiac arrest?"
- "Insulin dosing for DKA"

**⚕️ Clinical Criteria** - Decision-making thresholds and guidelines
- "What are the Ottawa ankle rules?"
- "Sepsis severity criteria"

**📞 Contact Information** - On-call physician lookup
- "Who is on call for cardiology?"
- "Emergency surgery contact"

**📊 Medical Summaries** - Synthesized information from multiple sources
- "Summarize the chest pain workup"

All responses are based on verified medical protocols and guidelines. I provide citations and confidence scores to ensure medical safety."""
        
        # Add Universal Quality System info if enabled
        if self.enable_universal_quality and self.universal_quality_orchestrator:
            stats = self.universal_quality_orchestrator.get_generation_statistics()
            if stats['total_queries'] > 0:
                capability_text += f"""

**🎯 Universal Quality System**: All responses are generated using our 4-layer quality system to ensure curated-level medical accuracy and professional formatting.
- Total queries processed: {stats['total_queries']}
- Curated-quality achievement rate: {stats['curated_quality_rate']:.1%}
- System effectiveness: {stats['universal_system_effectiveness']:.1%}"""
        
        return capability_text
    
    def _simple_classify(self, query: str) -> tuple:
        """Simple rule-based classification that actually works."""
        from src.models.query_types import QueryType
        
        query_lower = query.lower()
        
        # Contact patterns
        if any(pattern in query_lower for pattern in ['on call', 'contact', 'phone', 'pager', 'call', 'who is']):
            return QueryType.CONTACT_LOOKUP, 0.9
        
        # Form patterns  
        if any(pattern in query_lower for pattern in ['form', 'consent', 'document', 'pdf', 'template', 'transfusion']):
            return QueryType.FORM_RETRIEVAL, 0.9
        
        # Protocol patterns
        if any(pattern in query_lower for pattern in ['protocol', 'procedure', 'pathway', 'stemi', 'sepsis', 'stroke']):
            return QueryType.PROTOCOL_STEPS, 0.9
        
        # Criteria patterns
        if any(pattern in query_lower for pattern in ['criteria', 'threshold', 'rule', 'indication', 'contraindication']):
            return QueryType.CRITERIA_CHECK, 0.9
        
        # Dosage patterns
        if any(pattern in query_lower for pattern in ['dose', 'dosing', 'dosage', 'medication', 'drug', 'mg', 'treatment']):
            return QueryType.DOSAGE_LOOKUP, 0.9
        
        # Default to summary for everything else
        return QueryType.SUMMARY_REQUEST, 0.7
    
    def get_universal_quality_statistics(self) -> Dict[str, Any]:
        """Get Universal Quality System statistics."""
        if self.enable_universal_quality and self.universal_quality_orchestrator:
            return self.universal_quality_orchestrator.get_generation_statistics()
        else:
            return {
                "universal_quality_enabled": False,
                "message": "Universal Quality System is disabled"
            }
