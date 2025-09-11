"""
Universal Quality Orchestrator for PRP-41: Universal Curated-Quality Response System
Orchestrates all 4 layers to generate curated-quality responses for every medical query.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.ai.medical_prompts import UniversalMedicalPrompts
from src.models.query_types import QueryType
from src.validation.universal_quality_validator import (
    QualityScore,
    UniversalQualityValidator,
)

from .curated_responses import curated_db
from .enhanced_medical_retriever import EnhancedMedicalRetriever, MedicalContext
from .medical_response_formatter import FormattedResponse, MedicalResponseFormatter

logger = logging.getLogger(__name__)


class UniversalQualityOrchestrator:
    """
    Orchestrates the 4-layer Universal Quality System to ensure
    ALL medical queries return curated-quality responses.
    """
    
    def __init__(self, db, llm_client):
        self.db = db
        self.llm_client = llm_client
        
        # Initialize all 4 layers
        self.enhanced_retriever = EnhancedMedicalRetriever(db)
        self.response_formatter = MedicalResponseFormatter()
        self.medical_prompts = UniversalMedicalPrompts()
        self.quality_validator = UniversalQualityValidator()
        
        # Quality thresholds
        self.curated_quality_threshold = 8.0
        self.acceptable_quality_threshold = 6.0
        self.max_refinement_attempts = 2
        
        # Performance tracking
        self.generation_stats = {
            'total_queries': 0,
            'curated_quality_achieved': 0,
            'refinement_successful': 0,
            'fallback_to_curated': 0
        }
    
    async def generate_curated_quality_response(
        self, 
        query: str, 
        query_type: QueryType,
        context: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate curated-quality response using the 4-layer system.
        
        Args:
            query: User's medical query
            query_type: Classified query type
            context: Optional additional context
            user_id: Optional user ID
            
        Returns:
            Response data with curated-quality guarantees
        """
        start_time = datetime.utcnow()
        self.generation_stats['total_queries'] += 1
        
        try:
            # Check curated responses first (highest priority) - TEMPORARILY DISABLED for testing
            # curated_match = curated_db.find_curated_response(query, threshold=0.6)
            curated_match = None  # Force disable
            if curated_match:
                curated_response, match_score = curated_match
                logger.info(f"Using curated response with match score {match_score:.3f}")
                
                self.generation_stats['fallback_to_curated'] += 1
                
                return {
                    "response": curated_response.response,
                    "query_type": curated_response.query_type,
                    "confidence": curated_response.confidence,
                    "sources": curated_response.sources,
                    "quality_score": 10.0,
                    "quality_level": "curated",
                    "generation_method": "curated_database",
                    "match_score": match_score,
                    "processing_time": (datetime.utcnow() - start_time).total_seconds(),
                    "warnings": [f"✅ Curated medical content (match: {match_score:.1%})"]
                }
            
            # Generate response using 4-layer system
            response_data = await self._generate_with_quality_layers(
                query, query_type, context, user_id, start_time
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Universal quality generation failed: {e}")
            
            # Emergency fallback to basic response
            return await self._emergency_fallback_response(
                query, query_type, context, start_time
            )
    
    async def _generate_with_quality_layers(
        self, 
        query: str, 
        query_type: QueryType,
        context: Optional[str],
        user_id: Optional[str],
        start_time: datetime
    ) -> Dict[str, Any]:
        """Generate response using all 4 quality layers."""
        
        # Layer 1: Enhanced Medical RAG Retrieval
        logger.info("Layer 1: Enhanced medical retrieval")
        medical_context = self.enhanced_retriever.retrieve_medical_context(
            query, query_type, k=5
        )
        
        # Layer 2: Generate response with medical-specific prompts
        logger.info("Layer 2: Medical-specific LLM generation")
        initial_response = await self._generate_medical_response(
            query, query_type, medical_context
        )
        
        # Layer 3: Format response with medical templates
        logger.info("Layer 3: Medical response formatting")
        formatted_response = self.response_formatter.format_response(
            medical_context, query_type, initial_response, query
        )
        
        # Layer 4: Quality validation and refinement
        logger.info("Layer 4: Quality validation")
        final_response = await self._validate_and_refine_response(
            formatted_response.content, query, query_type, medical_context,
            initial_response, formatted_response
        )
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            **final_response,
            "processing_time": processing_time,
            "generation_method": "universal_quality_system",
            "layers_used": ["enhanced_retrieval", "medical_prompts", "formatting", "validation"]
        }
    
    async def _generate_medical_response(
        self, 
        query: str, 
        query_type: QueryType,
        medical_context: MedicalContext
    ) -> str:
        """Generate medical response using enhanced prompts."""
        try:
            # Get curated-quality prompt
            prompt = self.medical_prompts.get_universal_medical_prompt(
                query_type, query, medical_context
            )
            
            # Generate response with LLM
            response = await self._call_llm_with_prompt(prompt)
            
            return response
            
        except Exception as e:
            logger.error(f"Medical response generation failed: {e}")
            
            # Fallback to basic response generation
            return await self._generate_basic_medical_response(query, medical_context)
    
    async def _validate_and_refine_response(
        self, 
        response: str,
        query: str,
        query_type: QueryType,
        medical_context: MedicalContext,
        initial_response: str,
        formatted_response: FormattedResponse
    ) -> Dict[str, Any]:
        """Validate response quality and refine if needed."""
        
        # Initial quality assessment
        quality_score = self.quality_validator.validate_medical_response(
            response, query, query_type, medical_context
        )
        
        logger.info(f"Initial quality score: {quality_score.overall_score:.1f} ({quality_score.quality_level.value})")
        
        # Check if quality meets curated standards
        if quality_score.overall_score >= self.curated_quality_threshold:
            logger.info("✅ Curated quality achieved on first attempt")
            self.generation_stats['curated_quality_achieved'] += 1
            
            return self._build_response_data(
                response, query_type, medical_context, quality_score,
                generation_method="curated_quality_achieved"
            )
        
        # Attempt refinement if quality is below threshold
        if quality_score.needs_refinement and quality_score.refinement_type:
            logger.info(f"Attempting quality refinement: {quality_score.refinement_type}")
            
            refined_response = await self._refine_response_quality(
                response, query, query_type, medical_context, quality_score
            )
            
            if refined_response:
                self.generation_stats['refinement_successful'] += 1
                return refined_response
        
        # If refinement failed, check if acceptable quality
        if quality_score.overall_score >= self.acceptable_quality_threshold:
            logger.info("Acceptable quality achieved")
            
            return self._build_response_data(
                response, query_type, medical_context, quality_score,
                generation_method="acceptable_quality"
            )
        
        # Last resort: try to find similar curated response - DISABLED FOR TESTING
        logger.warning("Quality below acceptable threshold, but curated fallback disabled for testing")
        
        # curated_fallback = curated_db.find_curated_response(query, threshold=0.4)
        curated_fallback = None  # Force disable fallback
        if curated_fallback:
            curated_response, match_score = curated_fallback
            logger.info(f"Using curated fallback with match score {match_score:.3f}")
            
            return {
                "response": curated_response.response,
                "query_type": curated_response.query_type,
                "confidence": curated_response.confidence,
                "sources": curated_response.sources,
                "quality_score": 9.0,  # Curated responses are high quality
                "quality_level": "curated_fallback",
                "generation_method": "curated_fallback",
                "match_score": match_score,
                "warnings": [f"⚠️ Using similar curated content (match: {match_score:.1%})"]
            }
        
        # Final fallback: return best effort with warnings
        return self._build_response_data(
            response, query_type, medical_context, quality_score,
            generation_method="best_effort",
            additional_warnings=["⚠️ Response quality below optimal standards"]
        )
    
    async def _refine_response_quality(
        self, 
        response: str,
        query: str,
        query_type: QueryType,
        medical_context: MedicalContext,
        quality_score: QualityScore,
        attempt: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Attempt to refine response quality."""
        
        if attempt > self.max_refinement_attempts:
            logger.warning("Max refinement attempts reached")
            return None
        
        try:
            refinement_method = quality_score.refinement_type
            
            if refinement_method == "complete_regeneration":
                # Regenerate completely with enhanced context
                return await self._regenerate_with_enhanced_context(
                    query, query_type, medical_context
                )
            
            elif refinement_method == "format_enhancement":
                # Enhance formatting only
                enhanced_response = self.response_formatter.format_response(
                    medical_context, query_type, response, query
                )
                
                # Re-validate
                new_quality_score = self.quality_validator.validate_medical_response(
                    enhanced_response.content, query, query_type, medical_context
                )
                
                if new_quality_score.overall_score >= self.curated_quality_threshold:
                    return self._build_response_data(
                        enhanced_response.content, query_type, medical_context,
                        new_quality_score, generation_method="format_enhanced"
                    )
            
            elif refinement_method == "enhanced_context_retrieval":
                # Try with more context
                enhanced_context = self.enhanced_retriever.retrieve_medical_context(
                    query, query_type, k=8  # More results
                )
                
                # Regenerate with enhanced context
                return await self._regenerate_with_enhanced_context(
                    query, query_type, enhanced_context
                )
            
            elif refinement_method == "citation_improvement":
                # Improve citations
                improved_response = await self._improve_citations(
                    response, medical_context
                )
                
                new_quality_score = self.quality_validator.validate_medical_response(
                    improved_response, query, query_type, medical_context
                )
                
                if new_quality_score.overall_score >= self.curated_quality_threshold:
                    return self._build_response_data(
                        improved_response, query_type, medical_context,
                        new_quality_score, generation_method="citation_improved"
                    )
            
            else:  # general_quality_enhancement
                # Use quality enhancement prompt
                enhancement_prompt = self.medical_prompts.get_quality_enhancement_prompt(
                    response, query_type, medical_context
                )
                
                enhanced_response = await self._call_llm_with_prompt(enhancement_prompt)
                
                # Re-validate
                new_quality_score = self.quality_validator.validate_medical_response(
                    enhanced_response, query, query_type, medical_context
                )
                
                if new_quality_score.overall_score >= self.curated_quality_threshold:
                    return self._build_response_data(
                        enhanced_response, query_type, medical_context,
                        new_quality_score, generation_method="quality_enhanced"
                    )
            
            # If this attempt didn't work, try again
            return await self._refine_response_quality(
                response, query, query_type, medical_context, quality_score, attempt + 1
            )
            
        except Exception as e:
            logger.error(f"Quality refinement attempt {attempt} failed: {e}")
            return None
    
    async def _regenerate_with_enhanced_context(
        self, 
        query: str, 
        query_type: QueryType,
        medical_context: MedicalContext
    ) -> Dict[str, Any]:
        """Regenerate response with enhanced context."""
        
        # Generate with enhanced prompt
        enhanced_prompt = self.medical_prompts.get_universal_medical_prompt(
            query_type, query, medical_context
        )
        
        new_response = await self._call_llm_with_prompt(enhanced_prompt)
        
        # Format the response
        formatted_response = self.response_formatter.format_response(
            medical_context, query_type, new_response, query
        )
        
        # Validate quality
        quality_score = self.quality_validator.validate_medical_response(
            formatted_response.content, query, query_type, medical_context
        )
        
        return self._build_response_data(
            formatted_response.content, query_type, medical_context, quality_score,
            generation_method="regenerated_enhanced"
        )
    
    async def _improve_citations(
        self, 
        response: str, 
        medical_context: MedicalContext
    ) -> str:
        """Improve citations in the response."""
        
        # If response lacks proper citations, add them
        if '📚' not in response and 'Sources:' not in response:
            if medical_context.source_citations:
                citation_line = "📚 **Sources:** " + ", ".join([
                    cite.get("display_name", "Unknown") 
                    for cite in medical_context.source_citations
                ])
                response = response.rstrip() + "\n\n" + citation_line
        
        return response
    
    async def _call_llm_with_prompt(self, prompt: str) -> str:
        """Call LLM with the given prompt."""
        try:
            if hasattr(self.llm_client, 'generate_response'):
                # Custom LLM client
                response = await self.llm_client.generate_response(prompt)
            elif hasattr(self.llm_client, 'chat'):
                # OpenAI-style client
                response = await self.llm_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="gpt-3.5-turbo",
                    max_tokens=1000,
                    temperature=0.1
                )
                response = response.choices[0].message.content
            else:
                # Fallback for different client types
                response = str(await self.llm_client.generate(prompt))
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    async def _generate_basic_medical_response(
        self, 
        query: str, 
        medical_context: MedicalContext
    ) -> str:
        """Generate basic medical response as fallback."""
        
        if medical_context.primary_content:
            return f"Based on the available medical information:\n\n{medical_context.primary_content}"
        else:
            return "I don't have sufficient medical information to provide a detailed response to this query."
    
    def _build_response_data(
        self, 
        response: str,
        query_type: QueryType,
        medical_context: MedicalContext,
        quality_score: QualityScore,
        generation_method: str,
        additional_warnings: Optional[list] = None
    ) -> Dict[str, Any]:
        """Build standardized response data structure."""
        
        # Extract sources from medical context
        sources = []
        for cite in medical_context.source_citations:
            sources.append({
                "display_name": cite.get("display_name", "Unknown"),
                "filename": cite.get("filename", "unknown")
            })
        
        # Combine warnings
        warnings = []
        if quality_score.safety_warnings:
            warnings.extend([f"⚠️ {warning}" for warning in quality_score.safety_warnings])
        
        if quality_score.overall_score < self.curated_quality_threshold:
            warnings.append(f"📊 Quality score: {quality_score.overall_score:.1f}/10.0")
        
        if additional_warnings:
            warnings.extend(additional_warnings)
        
        return {
            "response": response,
            "query_type": query_type.value,
            "confidence": min(1.0, quality_score.overall_score / 10.0),
            "sources": sources,
            "quality_score": quality_score.overall_score,
            "quality_level": quality_score.quality_level.value,
            "generation_method": generation_method,
            "medical_accuracy": quality_score.medical_accuracy,
            "format_consistency": quality_score.format_consistency,
            "professional_formatting": quality_score.professional_formatting,
            "warnings": warnings if warnings else None,
            "quality_metadata": {
                "has_medical_emojis": quality_score.has_medical_emojis,
                "has_structured_sections": quality_score.has_structured_sections,
                "has_proper_citations": quality_score.has_proper_citations,
                "has_specific_medical_data": quality_score.has_specific_medical_data,
                "clinical_relevance": medical_context.clinical_relevance_score,
                "medical_certainty": medical_context.medical_certainty_level
            }
        }
    
    async def _emergency_fallback_response(
        self, 
        query: str,
        query_type: QueryType,
        context: Optional[str],
        start_time: datetime
    ) -> Dict[str, Any]:
        """Emergency fallback when all systems fail."""
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Try to find any curated response as last resort
        curated_match = curated_db.find_curated_response(query, threshold=0.3)
        if curated_match:
            curated_response, match_score = curated_match
            
            return {
                "response": curated_response.response,
                "query_type": curated_response.query_type,
                "confidence": 0.7,
                "sources": curated_response.sources,
                "quality_score": 7.0,
                "quality_level": "emergency_curated",
                "generation_method": "emergency_fallback",
                "processing_time": processing_time,
                "warnings": [f"🚨 Emergency fallback used (match: {match_score:.1%})"]
            }
        
        # Absolute last resort
        return {
            "response": "I'm unable to provide a detailed response right now. Please consult medical references or contact the appropriate medical team directly.",
            "query_type": query_type.value,
            "confidence": 0.3,
            "sources": [],
            "quality_score": 2.0,
            "quality_level": "emergency_fallback",
            "generation_method": "absolute_fallback",
            "processing_time": processing_time,
            "warnings": ["🚨 System unavailable - emergency fallback response"]
        }
    
    def get_generation_statistics(self) -> Dict[str, Any]:
        """Get generation statistics for monitoring."""
        total = self.generation_stats['total_queries']
        
        if total == 0:
            return {
                "total_queries": 0,
                "curated_quality_rate": 0.0,
                "refinement_success_rate": 0.0,
                "curated_fallback_rate": 0.0
            }
        
        return {
            "total_queries": total,
            "curated_quality_rate": self.generation_stats['curated_quality_achieved'] / total,
            "refinement_success_rate": self.generation_stats['refinement_successful'] / total,
            "curated_fallback_rate": self.generation_stats['fallback_to_curated'] / total,
            "universal_system_effectiveness": (
                self.generation_stats['curated_quality_achieved'] + 
                self.generation_stats['refinement_successful'] +
                self.generation_stats['fallback_to_curated']
            ) / total
        }
