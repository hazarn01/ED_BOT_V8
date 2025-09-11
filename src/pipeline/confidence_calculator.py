"""
Confidence Scoring System for Medical Query Responses
Multi-factor confidence scoring with medical safety integration.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.models.query_types import QueryType
from src.observability import medical_metrics

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceFactors:
    """Individual factors contributing to confidence score."""
    source_reliability: float
    content_specificity: float
    medical_terminology_match: float
    query_type_alignment: float
    information_completeness: float
    medical_authority_indicators: float
    uncertainty_markers: float


@dataclass
class ConfidenceScore:
    """Complete confidence assessment for medical response."""
    overall_confidence: float
    confidence_level: str  # "high", "medium", "low"
    factors: ConfidenceFactors
    medical_safety_flags: List[str]
    recommendation: str
    metadata: Dict[str, Any]


class ConfidenceCalculator:
    """
    Medical-aware confidence scoring for query responses.
    Provides multi-factor confidence assessment with safety integration.
    """
    
    def __init__(self):
        # Medical authority indicators
        self.authority_indicators = self._load_authority_indicators()
        self.uncertainty_markers = self._load_uncertainty_markers()
        self.medical_terminology = self._load_medical_terminology()
        
        # Confidence thresholds
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.0
        }
        
    def calculate_confidence(
        self,
        query: str,
        query_type: QueryType,
        search_results: List[Dict[str, Any]],
        response_text: Optional[str] = None
    ) -> ConfidenceScore:
        """
        Calculate comprehensive confidence score for medical query response.
        
        Args:
            query: Original user query
            query_type: Classified query type
            search_results: Retrieved search results
            response_text: Generated response text (optional)
            
        Returns:
            Complete confidence assessment
        """
        try:
            # Track confidence calculation in medical metrics
            with medical_metrics.clinical_confidence_distribution.time():
                # Calculate individual confidence factors
                factors = self._calculate_confidence_factors(
                    query, query_type, search_results, response_text
                )
                
                # Calculate weighted overall confidence
                overall_confidence = self._calculate_weighted_confidence(factors, query_type)
                
                # Determine confidence level
                confidence_level = self._determine_confidence_level(overall_confidence)
                
                # Check for medical safety flags
                safety_flags = self._assess_medical_safety_flags(
                    search_results, response_text, overall_confidence
                )
                
                # Generate recommendation
                recommendation = self._generate_recommendation(
                    confidence_level, safety_flags, query_type
                )
                
                # Create metadata
                metadata = {
                    "calculation_method": "multi_factor_medical",
                    "source_count": len(search_results),
                    "query_complexity": self._assess_query_complexity(query),
                    "medical_context": self._get_medical_context(query_type)
                }
                
                # Update medical metrics (with error handling)
                try:
                    medical_metrics.clinical_confidence_distribution.observe(overall_confidence)
                except Exception as e:
                    logger.warning(f"Confidence metrics tracking failed: {e}")
                
                try:
                    if safety_flags:
                        medical_metrics.safety_alerts.inc()
                except Exception as e:
                    logger.warning(f"Safety alert metrics tracking failed: {e}")
                
                result = ConfidenceScore(
                    overall_confidence=overall_confidence,
                    confidence_level=confidence_level,
                    factors=factors,
                    medical_safety_flags=safety_flags,
                    recommendation=recommendation,
                    metadata=metadata
                )
                
                logger.info(f"Calculated confidence: {overall_confidence:.2f} ({confidence_level}) "
                          f"with {len(safety_flags)} safety flags")
                
                return result
                
        except Exception as e:
            logger.error(f"Confidence calculation failed: {e}")
            
            # Return conservative confidence score on failure
            return ConfidenceScore(
                overall_confidence=0.3,
                confidence_level="low",
                factors=ConfidenceFactors(0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.7),
                medical_safety_flags=["calculation_error"],
                recommendation="Use with extreme caution - confidence calculation failed",
                metadata={"error": str(e)}
            )
    
    def _calculate_confidence_factors(
        self,
        query: str,
        query_type: QueryType,
        search_results: List[Dict[str, Any]],
        response_text: Optional[str]
    ) -> ConfidenceFactors:
        """Calculate individual confidence factors."""
        
        # 1. Source Reliability (based on document types and quality)
        source_reliability = self._calculate_source_reliability(search_results)
        
        # 2. Content Specificity (how specific/detailed the content is)
        content_specificity = self._calculate_content_specificity(search_results, query)
        
        # 3. Medical Terminology Match (alignment with medical terminology)
        terminology_match = self._calculate_terminology_match(query, search_results)
        
        # 4. Query Type Alignment (how well results match query type)
        type_alignment = self._calculate_query_type_alignment(query_type, search_results)
        
        # 5. Information Completeness (coverage of the query)
        completeness = self._calculate_information_completeness(query, search_results)
        
        # 6. Medical Authority Indicators (presence of authoritative markers)
        authority_indicators = self._calculate_authority_indicators(search_results)
        
        # 7. Uncertainty Markers (presence of uncertainty language)
        uncertainty = self._calculate_uncertainty_markers(search_results, response_text)
        
        return ConfidenceFactors(
            source_reliability=source_reliability,
            content_specificity=content_specificity,
            medical_terminology_match=terminology_match,
            query_type_alignment=type_alignment,
            information_completeness=completeness,
            medical_authority_indicators=authority_indicators,
            uncertainty_markers=uncertainty
        )
    
    def _calculate_source_reliability(self, search_results: List[Dict[str, Any]]) -> float:
        """Calculate reliability score based on source types."""
        if not search_results:
            return 0.0
        
        reliability_scores = []
        
        for result in search_results:
            source = result.get("source", {})
            content_type = source.get("content_type", "").lower()
            filename = source.get("filename", "").lower()
            category = source.get("category", "").lower()
            
            # Score based on content type
            if content_type in ["protocol", "guideline", "criteria"]:
                score = 0.95
            elif content_type in ["medication", "dosage"]:
                score = 0.9
            elif content_type in ["form", "document"]:
                score = 0.8
            elif "protocol" in filename or "guideline" in filename:
                score = 0.85
            elif category in ["protocol", "criteria", "dosage"]:
                score = 0.8
            else:
                score = 0.6
            
            # Boost for medical institutions or official sources
            if any(term in filename for term in ["clinical", "medical", "hospital", "acls", "aha"]):
                score = min(1.0, score + 0.1)
            
            reliability_scores.append(score)
        
        return sum(reliability_scores) / len(reliability_scores)
    
    def _calculate_content_specificity(
        self, 
        search_results: List[Dict[str, Any]], 
        query: str
    ) -> float:
        """Calculate specificity score based on content detail."""
        if not search_results:
            return 0.0
        
        specificity_scores = []
        
        for result in search_results:
            content = result.get("content", "")
            score = 0.5  # Base score
            
            # Boost for specific medical details
            if re.search(r'\d+\s*(mg|ml|units|minutes|hours)', content):
                score += 0.2  # Quantitative data
            
            if re.search(r'(protocol|procedure|step \d+)', content, re.IGNORECASE):
                score += 0.2  # Procedural detail
            
            if re.search(r'(contact|phone|pager|\d{3}-\d{3}-\d{4})', content, re.IGNORECASE):
                score += 0.15  # Contact specificity
            
            if re.search(r'(criteria|indication|contraindication)', content, re.IGNORECASE):
                score += 0.15  # Clinical criteria
            
            # Penalty for vague language
            if re.search(r'(may|might|consider|possibly|usually)', content, re.IGNORECASE):
                score -= 0.1
            
            specificity_scores.append(min(1.0, score))
        
        return sum(specificity_scores) / len(specificity_scores)
    
    def _calculate_terminology_match(
        self, 
        query: str, 
        search_results: List[Dict[str, Any]]
    ) -> float:
        """Calculate medical terminology alignment score."""
        if not search_results:
            return 0.0
        
        query_terms = set(re.findall(r'\b[A-Z]{2,}\b', query))  # Medical abbreviations
        query_terms.update(word.lower() for word in self.medical_terminology if word.lower() in query.lower())
        
        if not query_terms:
            return 0.5  # Neutral if no medical terms detected
        
        match_scores = []
        
        for result in search_results:
            content = result.get("content", "")
            content_terms = set(re.findall(r'\b[A-Z]{2,}\b', content))
            content_terms.update(word.lower() for word in self.medical_terminology if word.lower() in content.lower())
            
            if query_terms and content_terms:
                overlap = len(query_terms.intersection(content_terms))
                match_score = overlap / len(query_terms)
                match_scores.append(match_score)
            else:
                match_scores.append(0.3)
        
        return sum(match_scores) / len(match_scores) if match_scores else 0.3
    
    def _calculate_query_type_alignment(
        self, 
        query_type: QueryType, 
        search_results: List[Dict[str, Any]]
    ) -> float:
        """Calculate alignment with query type expectations."""
        if not search_results:
            return 0.0
        
        alignment_scores = []
        
        # Define query type indicators
        type_indicators = {
            QueryType.CONTACT_LOOKUP: ["contact", "phone", "pager", "call", "on-call", "extension"],
            QueryType.FORM_RETRIEVAL: ["form", "document", "consent", "template", "pdf"],
            QueryType.PROTOCOL_STEPS: ["protocol", "procedure", "step", "workflow", "activation"],
            QueryType.CRITERIA_CHECK: ["criteria", "rule", "score", "assessment", "indication"],
            QueryType.DOSAGE_LOOKUP: ["dose", "dosage", "mg", "ml", "units", "administration"],
            QueryType.SUMMARY_REQUEST: ["overview", "summary", "management", "treatment", "approach"]
        }
        
        indicators = type_indicators.get(query_type, [])
        
        for result in search_results:
            content = result.get("content", "").lower()
            source = result.get("source", {})
            
            # Count indicator matches
            indicator_matches = sum(1 for indicator in indicators if indicator in content)
            base_score = min(1.0, indicator_matches / len(indicators) if indicators else 0.5)
            
            # Boost for source type alignment
            content_type = source.get("content_type", "").lower()
            if query_type == QueryType.PROTOCOL_STEPS and content_type in ["protocol", "guideline"]:
                base_score = min(1.0, base_score + 0.2)
            elif query_type == QueryType.DOSAGE_LOOKUP and content_type == "medication":
                base_score = min(1.0, base_score + 0.2)
            elif query_type == QueryType.FORM_RETRIEVAL and "form" in source.get("filename", "").lower():
                base_score = min(1.0, base_score + 0.2)
            
            alignment_scores.append(base_score)
        
        return sum(alignment_scores) / len(alignment_scores)
    
    def _calculate_information_completeness(
        self, 
        query: str, 
        search_results: List[Dict[str, Any]]
    ) -> float:
        """Calculate information completeness score."""
        if not search_results:
            return 0.0
        
        # Extract key concepts from query
        query_concepts = set(re.findall(r'\b\w{4,}\b', query.lower()))
        query_concepts -= {"what", "show", "tell", "give", "protocol", "form"}  # Filter common words
        
        if not query_concepts:
            return 0.7  # Neutral for simple queries
        
        completeness_scores = []
        
        for result in search_results:
            content = result.get("content", "").lower()
            
            # Count concept coverage
            covered_concepts = sum(1 for concept in query_concepts if concept in content)
            if query_concepts:
                coverage_ratio = covered_concepts / len(query_concepts)
            else:
                coverage_ratio = 0.5
            
            # Boost for comprehensive content (longer content often more complete)
            content_length_boost = min(0.2, len(content) / 1000)
            
            completeness_score = min(1.0, coverage_ratio + content_length_boost)
            completeness_scores.append(completeness_score)
        
        return sum(completeness_scores) / len(completeness_scores)
    
    def _calculate_authority_indicators(self, search_results: List[Dict[str, Any]]) -> float:
        """Calculate medical authority indicators score."""
        if not search_results:
            return 0.0
        
        authority_scores = []
        
        for result in search_results:
            content = result.get("content", "").lower()
            source = result.get("source", {})
            filename = source.get("filename", "").lower()
            
            score = 0.4  # Base score
            
            # Check for authority indicators
            authority_count = sum(1 for indicator in self.authority_indicators 
                                if indicator.lower() in content)
            score += min(0.4, authority_count * 0.1)
            
            # Check filename for authority markers
            if any(marker in filename for marker in ["acls", "aha", "clinical", "guideline", "protocol"]):
                score += 0.2
            
            authority_scores.append(min(1.0, score))
        
        return sum(authority_scores) / len(authority_scores)
    
    def _calculate_uncertainty_markers(
        self, 
        search_results: List[Dict[str, Any]], 
        response_text: Optional[str]
    ) -> float:
        """Calculate uncertainty markers (lower is better for confidence)."""
        uncertainty_count = 0
        total_content = ""
        
        # Check search results
        for result in search_results:
            total_content += result.get("content", "") + " "
        
        # Add response text if available
        if response_text:
            total_content += response_text
        
        # Count uncertainty markers
        for marker in self.uncertainty_markers:
            uncertainty_count += len(re.findall(r'\b' + re.escape(marker.lower()) + r'\b', 
                                              total_content.lower()))
        
        # Convert to score (lower uncertainty = higher confidence)
        if len(total_content) > 0:
            uncertainty_density = uncertainty_count / (len(total_content) / 100)
            uncertainty_score = max(0.0, 1.0 - (uncertainty_density * 0.2))
        else:
            uncertainty_score = 1.0
        
        return uncertainty_score
    
    def _calculate_weighted_confidence(self, factors: ConfidenceFactors, query_type: QueryType) -> float:
        """Calculate weighted overall confidence based on query type."""
        
        # Base weights
        weights = {
            "source_reliability": 0.25,
            "content_specificity": 0.20,
            "medical_terminology_match": 0.15,
            "query_type_alignment": 0.15,
            "information_completeness": 0.10,
            "medical_authority_indicators": 0.10,
            "uncertainty_markers": 0.05
        }
        
        # Adjust weights based on query type
        if query_type == QueryType.DOSAGE_LOOKUP:
            weights["content_specificity"] = 0.30  # More important for dosages
            weights["medical_authority_indicators"] = 0.15
        elif query_type == QueryType.CONTACT_LOOKUP:
            weights["query_type_alignment"] = 0.25  # Contact specificity critical
            weights["content_specificity"] = 0.25
        elif query_type == QueryType.PROTOCOL_STEPS:
            weights["source_reliability"] = 0.30  # Protocol authority critical
            weights["medical_authority_indicators"] = 0.15
        
        # Calculate weighted score
        weighted_score = (
            factors.source_reliability * weights["source_reliability"] +
            factors.content_specificity * weights["content_specificity"] +
            factors.medical_terminology_match * weights["medical_terminology_match"] +
            factors.query_type_alignment * weights["query_type_alignment"] +
            factors.information_completeness * weights["information_completeness"] +
            factors.medical_authority_indicators * weights["medical_authority_indicators"] +
            factors.uncertainty_markers * weights["uncertainty_markers"]
        )
        
        return min(1.0, max(0.0, weighted_score))
    
    def _determine_confidence_level(self, overall_confidence: float) -> str:
        """Determine confidence level from numeric score."""
        if overall_confidence >= self.confidence_thresholds["high"]:
            return "high"
        elif overall_confidence >= self.confidence_thresholds["medium"]:
            return "medium"
        else:
            return "low"
    
    def _assess_medical_safety_flags(
        self,
        search_results: List[Dict[str, Any]],
        response_text: Optional[str],
        confidence: float
    ) -> List[str]:
        """Assess medical safety flags for the response."""
        flags = []
        
        # Low confidence flag
        if confidence < 0.5:
            flags.append("low_confidence")
        
        # No source flag
        if not search_results:
            flags.append("no_sources")
        
        # Outdated information flag (basic heuristic)
        for result in search_results:
            content = result.get("content", "")
            if re.search(r'(under review|deprecated|obsolete)', content, re.IGNORECASE):
                flags.append("potentially_outdated")
                break
        
        # Conflicting information flag
        if len(search_results) > 1:
            # Simple check for conflicting dosage information
            dosage_info = []
            for result in search_results:
                content = result.get("content", "")
                dosages = re.findall(r'\d+\s*(?:mg|ml|units)', content)
                if dosages:
                    dosage_info.extend(dosages)
            
            if len(set(dosage_info)) > 1:
                flags.append("multiple_dosage_recommendations")
        
        return flags
    
    def _generate_recommendation(
        self,
        confidence_level: str,
        safety_flags: List[str],
        query_type: QueryType
    ) -> str:
        """Generate usage recommendation based on confidence and safety."""
        if safety_flags:
            return "Exercise caution - medical safety flags detected. Verify information independently."
        
        if confidence_level == "high":
            return "High confidence response - information appears reliable and complete."
        elif confidence_level == "medium":
            return "Medium confidence response - verify critical details before clinical use."
        else:
            return "Low confidence response - use with extreme caution and seek additional verification."
    
    def _assess_query_complexity(self, query: str) -> str:
        """Assess query complexity for metadata."""
        word_count = len(query.split())
        medical_terms = len(re.findall(r'\b[A-Z]{2,}\b', query))
        
        if word_count <= 5 and medical_terms <= 1:
            return "simple"
        elif word_count <= 10 and medical_terms <= 2:
            return "moderate"
        else:
            return "complex"
    
    def _get_medical_context(self, query_type: QueryType) -> str:
        """Get medical context for metadata."""
        context_map = {
            QueryType.CONTACT_LOOKUP: "emergency_contacts",
            QueryType.FORM_RETRIEVAL: "documentation",
            QueryType.PROTOCOL_STEPS: "clinical_procedures",
            QueryType.CRITERIA_CHECK: "clinical_decision_support",
            QueryType.DOSAGE_LOOKUP: "medication_management",
            QueryType.SUMMARY_REQUEST: "clinical_overview"
        }
        return context_map.get(query_type, "general_medical")
    
    def _load_authority_indicators(self) -> List[str]:
        """Load medical authority indicators."""
        return [
            "protocol", "guideline", "standard", "recommended", "evidence-based",
            "clinical trial", "peer-reviewed", "FDA approved", "AHA", "ACLS",
            "American Heart Association", "emergency medicine", "intensive care",
            "critical care", "hospital policy", "medical center", "clinical pathway"
        ]
    
    def _load_uncertainty_markers(self) -> List[str]:
        """Load uncertainty language markers."""
        return [
            "may", "might", "possibly", "potentially", "likely", "probably",
            "consider", "suggest", "recommend", "usually", "typically", "generally",
            "in most cases", "often", "sometimes", "variable", "depends on"
        ]
    
    def _load_medical_terminology(self) -> List[str]:
        """Load key medical terminology for matching."""
        return [
            "protocol", "dose", "dosage", "treatment", "medication", "procedure",
            "criteria", "indication", "contraindication", "emergency", "urgent",
            "cardiac", "respiratory", "neurological", "sepsis", "shock", "trauma",
            "anaphylaxis", "hypoglycemia", "seizure", "stroke", "myocardial",
            "infarction", "arrhythmia", "bradycardia", "tachycardia", "hypertension"
        ]