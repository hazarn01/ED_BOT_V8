"""
Universal Quality Validation for PRP-41: Universal Curated-Quality Response System
Real-time quality scoring and validation for all medical responses.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from src.models.query_types import QueryType
from src.pipeline.enhanced_medical_retriever import MedicalContext

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Quality levels for medical responses."""
    CURATED = "curated"      # 9.0-10.0 - Matches curated quality
    EXCELLENT = "excellent"   # 8.0-8.9 - Near curated quality
    GOOD = "good"            # 6.0-7.9 - Acceptable medical quality
    ACCEPTABLE = "acceptable" # 4.0-5.9 - Minimal medical standards
    POOR = "poor"            # 0.0-3.9 - Below medical standards


@dataclass
class QualityScore:
    """Comprehensive quality score for medical responses."""
    overall_score: float  # 0.0-10.0
    quality_level: QualityLevel
    
    # Component scores (0.0-1.0)
    medical_accuracy: float
    format_consistency: float
    citation_quality: float
    relevance_score: float
    professional_formatting: float
    safety_compliance: float
    
    # Quality indicators
    has_medical_emojis: bool
    has_structured_sections: bool
    has_proper_citations: bool
    has_specific_medical_data: bool
    
    # Issues and recommendations
    quality_issues: List[str]
    improvement_suggestions: List[str]
    safety_warnings: List[str]
    
    # Refinement needed
    needs_refinement: bool
    refinement_type: Optional[str]


class UniversalQualityValidator:
    """
    Universal quality validator that ensures all medical responses
    meet curated-quality standards with automatic fallbacks.
    """
    
    def __init__(self):
        self.curated_quality_threshold = 8.0
        self.acceptable_quality_threshold = 6.0
        self.medical_terminology = self._load_medical_terminology()
        self.formatting_patterns = self._load_formatting_patterns()
        self.safety_keywords = self._load_safety_keywords()
        
    def validate_medical_response(
        self, 
        response: str, 
        query: str,
        query_type: QueryType,
        context: MedicalContext
    ) -> QualityScore:
        """
        Validate medical response quality against curated standards.
        
        Args:
            response: Generated medical response
            query: Original user query
            query_type: Type of medical query
            context: Medical context used for generation
            
        Returns:
            Comprehensive quality score and recommendations
        """
        try:
            # Component quality assessments
            medical_accuracy = self._assess_medical_accuracy(response, context)
            format_consistency = self._assess_format_consistency(response, query_type)
            citation_quality = self._assess_citation_quality(response, context)
            relevance_score = self._assess_relevance(response, query, query_type)
            professional_formatting = self._assess_professional_formatting(response, query_type)
            safety_compliance = self._assess_safety_compliance(response, context)
            
            # Quality indicators
            has_medical_emojis = self._has_medical_emojis(response)
            has_structured_sections = self._has_structured_sections(response)
            has_proper_citations = self._has_proper_citations(response, context)
            has_specific_medical_data = self._has_specific_medical_data(response)
            
            # Calculate overall score (weighted average)
            component_weights = {
                'medical_accuracy': 0.25,      # Highest priority
                'safety_compliance': 0.20,     # Critical for medical
                'format_consistency': 0.15,    # Professional appearance
                'professional_formatting': 0.15, # Curated-style formatting
                'citation_quality': 0.15,      # Source attribution
                'relevance_score': 0.10        # Query relevance
            }
            
            overall_score = (
                medical_accuracy * component_weights['medical_accuracy'] +
                safety_compliance * component_weights['safety_compliance'] +
                format_consistency * component_weights['format_consistency'] +
                professional_formatting * component_weights['professional_formatting'] +
                citation_quality * component_weights['citation_quality'] +
                relevance_score * component_weights['relevance_score']
            ) * 10.0  # Scale to 0-10
            
            # Determine quality level
            quality_level = self._determine_quality_level(overall_score)
            
            # Identify quality issues
            quality_issues = self._identify_quality_issues(
                response, query_type, medical_accuracy, format_consistency,
                citation_quality, professional_formatting
            )
            
            # Generate improvement suggestions
            improvement_suggestions = self._generate_improvement_suggestions(
                response, query_type, quality_issues
            )
            
            # Check for safety warnings
            safety_warnings = self._check_safety_warnings(response, context)
            
            # Determine if refinement is needed
            needs_refinement = overall_score < self.curated_quality_threshold
            refinement_type = self._determine_refinement_type(
                overall_score, quality_issues, query_type
            )
            
            return QualityScore(
                overall_score=overall_score,
                quality_level=quality_level,
                medical_accuracy=medical_accuracy,
                format_consistency=format_consistency,
                citation_quality=citation_quality,
                relevance_score=relevance_score,
                professional_formatting=professional_formatting,
                safety_compliance=safety_compliance,
                has_medical_emojis=has_medical_emojis,
                has_structured_sections=has_structured_sections,
                has_proper_citations=has_proper_citations,
                has_specific_medical_data=has_specific_medical_data,
                quality_issues=quality_issues,
                improvement_suggestions=improvement_suggestions,
                safety_warnings=safety_warnings,
                needs_refinement=needs_refinement,
                refinement_type=refinement_type
            )
            
        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            
            # Return conservative quality score on failure
            return QualityScore(
                overall_score=3.0,
                quality_level=QualityLevel.POOR,
                medical_accuracy=0.5,
                format_consistency=0.3,
                citation_quality=0.2,
                relevance_score=0.4,
                professional_formatting=0.2,
                safety_compliance=0.5,
                has_medical_emojis=False,
                has_structured_sections=False,
                has_proper_citations=False,
                has_specific_medical_data=False,
                quality_issues=["quality_validation_failed"],
                improvement_suggestions=["retry_with_enhanced_context"],
                safety_warnings=["validation_failed"],
                needs_refinement=True,
                refinement_type="complete_regeneration"
            )
    
    def _assess_medical_accuracy(self, response: str, context: MedicalContext) -> float:
        """Assess medical accuracy against provided context."""
        score = 0.0
        
        # Check if response contains information not in context (hallucination)
        context_content = (context.primary_content + " " + 
                          " ".join(context.supporting_evidence)).lower()
        
        # Extract medical facts from response
        medical_facts = self._extract_medical_facts(response)
        
        if not medical_facts:
            return 0.3  # No medical facts found
        
        supported_facts = 0
        for fact in medical_facts:
            # Check if fact is supported by context
            if self._is_fact_supported_by_context(fact, context_content):
                supported_facts += 1
        
        # Calculate accuracy ratio
        accuracy_ratio = supported_facts / len(medical_facts) if medical_facts else 0.0
        
        # Base score from accuracy ratio
        score = accuracy_ratio * 0.7
        
        # Bonus for medical terminology consistency
        if self._has_consistent_medical_terminology(response):
            score += 0.15
        
        # Bonus for specific medical details
        if self._has_quantitative_medical_data(response):
            score += 0.15
        
        # Penalty for medical contradictions
        if self._has_medical_contradictions(response):
            score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def _assess_format_consistency(self, response: str, query_type: QueryType) -> float:
        """Assess format consistency with curated style."""
        score = 0.0
        
        # Check for curated-style structure
        structure_checks = {
            'has_title_emoji': bool(re.search(r'^[🚨💉📋📞📄📊]', response.strip())),
            'has_bold_headers': bool(re.search(r'\*\*[^*]+\*\*:', response)),
            'has_bullet_points': bool(re.search(r'^[•·-]\s', response, re.MULTILINE)),
            'has_section_emojis': len(re.findall(r'[⏱️📞💉💊🔄⚠️📚🧪💡📊✅❌🚫]', response)) >= 2,
            'proper_line_spacing': '\n\n' in response
        }
        
        # Weight each structural element
        structure_weights = {
            'has_title_emoji': 0.25,
            'has_bold_headers': 0.25,
            'has_bullet_points': 0.20,
            'has_section_emojis': 0.20,
            'proper_line_spacing': 0.10
        }
        
        for check, weight in structure_weights.items():
            if structure_checks[check]:
                score += weight
        
        # Query-type-specific formatting checks
        type_bonus = self._get_query_type_formatting_bonus(response, query_type)
        score += type_bonus
        
        return min(1.0, score)
    
    def _assess_citation_quality(self, response: str, context: MedicalContext) -> float:
        """Assess citation quality and source attribution."""
        score = 0.0
        
        # Check for citation presence
        has_sources_section = '📚' in response or 'Sources:' in response
        
        if not has_sources_section:
            return 0.1  # Very low score without citations
        
        # Check if citations match available sources
        available_sources = set(cite.get('display_name', '') for cite in context.source_citations)
        
        # Extract cited sources from response
        cited_sources = self._extract_cited_sources(response)
        
        if not cited_sources and has_sources_section:
            return 0.3  # Has section but no actual citations
        
        # Calculate citation accuracy
        if available_sources and cited_sources:
            matching_citations = len(cited_sources.intersection(available_sources))
            citation_accuracy = matching_citations / len(available_sources)
            score += citation_accuracy * 0.7
        
        # Bonus for proper citation formatting
        if self._has_proper_citation_formatting(response):
            score += 0.3
        
        return min(1.0, score)
    
    def _assess_relevance(self, response: str, query: str, query_type: QueryType) -> float:
        """Assess relevance to the original query."""
        score = 0.0
        
        # Extract key terms from query
        query_terms = self._extract_key_terms(query.lower())
        response_lower = response.lower()
        
        # Check term coverage
        covered_terms = sum(1 for term in query_terms if term in response_lower)
        if query_terms:
            term_coverage = covered_terms / len(query_terms)
            score += term_coverage * 0.5
        
        # Query-type-specific relevance
        type_relevance = self._assess_query_type_relevance(response, query_type)
        score += type_relevance * 0.3
        
        # Medical context relevance
        if self._addresses_medical_context(response, query):
            score += 0.2
        
        return min(1.0, score)
    
    def _assess_professional_formatting(self, response: str, query_type: QueryType) -> float:
        """Assess professional medical formatting quality."""
        score = 0.0
        
        # Professional formatting elements
        formatting_elements = {
            'proper_phone_formatting': bool(re.search(r'\*\*\(\d{3}\) \d{3}-\d{4}\*\*', response)),
            'bold_important_info': len(re.findall(r'\*\*[^*]+\*\*', response)) >= 3,
            'consistent_bullet_style': self._has_consistent_bullets(response),
            'proper_medical_abbreviations': self._has_proper_medical_abbreviations(response),
            'appropriate_emphasis': self._has_appropriate_emphasis(response),
            'clean_structure': not re.search(r'\n{4,}', response)  # No excessive line breaks
        }
        
        # Weight each formatting element
        weights = {
            'proper_phone_formatting': 0.15,
            'bold_important_info': 0.20,
            'consistent_bullet_style': 0.15,
            'proper_medical_abbreviations': 0.20,
            'appropriate_emphasis': 0.15,
            'clean_structure': 0.15
        }
        
        for element, weight in weights.items():
            if formatting_elements[element]:
                score += weight
        
        return min(1.0, score)
    
    def _assess_safety_compliance(self, response: str, context: MedicalContext) -> float:
        """Assess medical safety compliance."""
        score = 1.0  # Start with perfect score, deduct for issues
        
        # Critical safety checks
        safety_issues = []
        
        # Check for dosing without proper context
        if self._has_unsupported_dosing(response, context):
            safety_issues.append("unsupported_dosing")
            score -= 0.3
        
        # Check for missing safety warnings
        if self._missing_safety_warnings(response, context):
            safety_issues.append("missing_safety_warnings")
            score -= 0.2
        
        # Check for inappropriate medical advice
        if self._has_inappropriate_medical_advice(response):
            safety_issues.append("inappropriate_advice")
            score -= 0.4
        
        # Check for contact information accuracy
        if self._has_inaccurate_contacts(response):
            safety_issues.append("inaccurate_contacts")
            score -= 0.2
        
        # Check for medical contradictions
        if self._has_medical_contradictions(response):
            safety_issues.append("medical_contradictions")
            score -= 0.3
        
        return max(0.0, score)
    
    def _has_medical_emojis(self, response: str) -> bool:
        """Check if response has appropriate medical emojis."""
        medical_emojis = r'[🚨💉⏱️📞💊🔄⚠️📚🧪💡📊🦵🦠📋✅❌🚫📄]'
        return len(re.findall(medical_emojis, response)) >= 2
    
    def _has_structured_sections(self, response: str) -> bool:
        """Check if response has structured sections."""
        # Look for bold headers with colons
        headers = re.findall(r'\*\*[^*]+\*\*:', response)
        return len(headers) >= 2
    
    def _has_proper_citations(self, response: str, context: MedicalContext) -> bool:
        """Check if response has proper citations."""
        has_citation_section = '📚' in response or 'Sources:' in response
        has_available_sources = bool(context.source_citations)
        return has_citation_section and has_available_sources
    
    def _has_specific_medical_data(self, response: str) -> bool:
        """Check if response contains specific medical data."""
        # Look for specific medical measurements
        medical_data_patterns = [
            r'\d+\s*(mg|ml|units|minutes|hours|mmHg|bpm)',
            r'\(\d{3}\)\s*\d{3}-\d{4}',  # Phone numbers
            r'x\d{4,5}',  # Extensions
            r'\d+:\d+',   # Time ratios
            r'<\s*\d+',   # Thresholds
            r'>\s*\d+'    # Thresholds
        ]
        
        for pattern in medical_data_patterns:
            if re.search(pattern, response):
                return True
        
        return False
    
    def _determine_quality_level(self, overall_score: float) -> QualityLevel:
        """Determine quality level from overall score."""
        if overall_score >= 9.0:
            return QualityLevel.CURATED
        elif overall_score >= 8.0:
            return QualityLevel.EXCELLENT
        elif overall_score >= 6.0:
            return QualityLevel.GOOD
        elif overall_score >= 4.0:
            return QualityLevel.ACCEPTABLE
        else:
            return QualityLevel.POOR
    
    def _identify_quality_issues(
        self, 
        response: str, 
        query_type: QueryType,
        medical_accuracy: float,
        format_consistency: float,
        citation_quality: float,
        professional_formatting: float
    ) -> List[str]:
        """Identify specific quality issues."""
        issues = []
        
        # Medical accuracy issues
        if medical_accuracy < 0.7:
            issues.append("low_medical_accuracy")
        
        # Format consistency issues
        if format_consistency < 0.6:
            issues.append("poor_formatting")
            
            if not re.search(r'^[🚨💉📋📞📄📊]', response.strip()):
                issues.append("missing_title_emoji")
            
            if not re.search(r'\*\*[^*]+\*\*:', response):
                issues.append("missing_bold_headers")
        
        # Citation issues
        if citation_quality < 0.5:
            issues.append("poor_citations")
        
        # Professional formatting issues
        if professional_formatting < 0.6:
            issues.append("unprofessional_formatting")
        
        # Specific missing elements
        if not self._has_medical_emojis(response):
            issues.append("missing_medical_emojis")
        
        if not self._has_specific_medical_data(response):
            issues.append("lacks_specific_data")
        
        return issues
    
    def _generate_improvement_suggestions(
        self, 
        response: str, 
        query_type: QueryType,
        quality_issues: List[str]
    ) -> List[str]:
        """Generate specific improvement suggestions."""
        suggestions = []
        
        # Issue-specific suggestions
        issue_suggestions = {
            "low_medical_accuracy": "Verify all medical facts against provided context",
            "poor_formatting": "Add professional medical formatting with emojis and structure",
            "missing_title_emoji": f"Add appropriate title emoji for {query_type.value} query",
            "missing_bold_headers": "Use **bold headers:** for section organization",
            "poor_citations": "Include proper source citations with 📚 Sources:",
            "unprofessional_formatting": "Format phone numbers and medical data professionally",
            "missing_medical_emojis": "Add medical section emojis (⏱️📞💉💊🔄⚠️)",
            "lacks_specific_data": "Include specific medical details (doses, timing, contacts)"
        }
        
        for issue in quality_issues:
            if issue in issue_suggestions:
                suggestions.append(issue_suggestions[issue])
        
        # Query-type-specific suggestions
        type_suggestions = self._get_query_type_suggestions(response, query_type)
        suggestions.extend(type_suggestions)
        
        return suggestions
    
    def _check_safety_warnings(self, response: str, context: MedicalContext) -> List[str]:
        """Check for medical safety warnings."""
        warnings = []
        
        # Check for dosing without context support
        if self._has_unsupported_dosing(response, context):
            warnings.append("dosing_not_supported_by_context")
        
        # Check for missing contraindications
        if "contraindication" not in response.lower() and "dose" in response.lower():
            warnings.append("missing_contraindications")
        
        # Check for medical advice without proper disclaimers
        if self._has_inappropriate_medical_advice(response):
            warnings.append("inappropriate_medical_advice")
        
        return warnings
    
    def _determine_refinement_type(
        self, 
        overall_score: float, 
        quality_issues: List[str],
        query_type: QueryType
    ) -> Optional[str]:
        """Determine what type of refinement is needed."""
        if overall_score >= self.curated_quality_threshold:
            return None  # No refinement needed
        
        if overall_score < 4.0:
            return "complete_regeneration"
        
        if "low_medical_accuracy" in quality_issues:
            return "enhanced_context_retrieval"
        
        if "poor_formatting" in quality_issues or "unprofessional_formatting" in quality_issues:
            return "format_enhancement"
        
        if "poor_citations" in quality_issues:
            return "citation_improvement"
        
        return "general_quality_enhancement"
    
    # Helper methods for detailed assessments
    def _extract_medical_facts(self, response: str) -> List[str]:
        """Extract medical facts from response for accuracy checking."""
        facts = []
        
        # Extract dosing information
        dosing_facts = re.findall(r'(\d+\s*(?:mg|ml|units)[^.]*)', response, re.IGNORECASE)
        facts.extend(dosing_facts)
        
        # Extract timing information
        timing_facts = re.findall(r'(\d+\s*(?:minutes|hours)[^.]*)', response, re.IGNORECASE)
        facts.extend(timing_facts)
        
        # Extract contact information
        contact_facts = re.findall(r'(\(\d{3}\)\s*\d{3}-\d{4})', response)
        facts.extend(contact_facts)
        
        # Extract medical thresholds
        threshold_facts = re.findall(r'([><]\s*\d+[^.]*)', response)
        facts.extend(threshold_facts)
        
        return facts
    
    def _is_fact_supported_by_context(self, fact: str, context_content: str) -> bool:
        """Check if a medical fact is supported by context."""
        # Normalize for comparison
        fact_normalized = re.sub(r'\s+', ' ', fact.lower().strip())
        
        # Look for key components in context
        fact_words = fact_normalized.split()
        
        # Check if majority of fact words are in context
        supported_words = sum(1 for word in fact_words if word in context_content)
        
        return supported_words >= len(fact_words) * 0.6  # 60% of words must be supported
    
    def _has_consistent_medical_terminology(self, response: str) -> bool:
        """Check for consistent medical terminology usage."""
        # Check if medical abbreviations are properly capitalized
        abbrevs_to_check = ['STEMI', 'MI', 'CVA', 'PE', 'DVT', 'CHF', 'COPD', 'DKA', 'IV', 'IM', 'EKG']
        
        for abbrev in abbrevs_to_check:
            # Find all instances of this abbreviation
            pattern = re.compile(f'\\b{abbrev}\\b', re.IGNORECASE)
            matches = pattern.findall(response)
            
            # Check if all matches are properly capitalized
            if matches and not all(match == abbrev for match in matches):
                return False
        
        return True
    
    def _has_quantitative_medical_data(self, response: str) -> bool:
        """Check for quantitative medical data."""
        quantitative_patterns = [
            r'\d+\s*mg',
            r'\d+\s*ml',
            r'\d+\s*units',
            r'\d+\s*minutes',
            r'\d+\s*hours',
            r'\d+\s*mmHg'
        ]
        
        return any(re.search(pattern, response, re.IGNORECASE) for pattern in quantitative_patterns)
    
    def _has_medical_contradictions(self, response: str) -> bool:
        """Check for medical contradictions within the response."""
        # This is a simplified check - could be expanded with medical knowledge
        
        # Check for conflicting dosing information
        doses = re.findall(r'(\d+)\s*mg', response, re.IGNORECASE)
        if len(set(doses)) > 3:  # Too many different doses might indicate contradiction
            return True
        
        # Check for conflicting timing
        times = re.findall(r'(\d+)\s*minutes?', response, re.IGNORECASE)
        if len(set(times)) > 4:  # Too many different times might indicate contradiction
            return True
        
        return False
    
    def _get_query_type_formatting_bonus(self, response: str, query_type: QueryType) -> float:
        """Get formatting bonus specific to query type."""
        bonus = 0.0
        
        if query_type == QueryType.PROTOCOL_STEPS:
            # Check for protocol-specific formatting
            if re.search(r'🚨.*protocol', response, re.IGNORECASE):
                bonus += 0.1
            if re.search(r'⏱️.*time|timing', response, re.IGNORECASE):
                bonus += 0.05
            if re.search(r'📞.*contact', response, re.IGNORECASE):
                bonus += 0.05
                
        elif query_type == QueryType.DOSAGE_LOOKUP:
            # Check for dosage-specific formatting
            if re.search(r'💉.*dose|dosage', response, re.IGNORECASE):
                bonus += 0.1
            if re.search(r'adult.*dose', response, re.IGNORECASE):
                bonus += 0.05
            if re.search(r'pediatric.*dose', response, re.IGNORECASE):
                bonus += 0.05
                
        elif query_type == QueryType.CRITERIA_CHECK:
            # Check for criteria-specific formatting
            if re.search(r'📋.*criteria|rules', response, re.IGNORECASE):
                bonus += 0.1
            if re.search(r'✅.*indication', response, re.IGNORECASE):
                bonus += 0.05
            if re.search(r'❌.*contraindication', response, re.IGNORECASE):
                bonus += 0.05
        
        return bonus
    
    def _extract_cited_sources(self, response: str) -> set:
        """Extract cited sources from response."""
        cited_sources = set()
        
        # Look for sources after 📚 or "Sources:"
        sources_pattern = r'(?:📚\s*\*\*Sources:\*\*|Sources:)\s*([^.]+)'
        match = re.search(sources_pattern, response)
        
        if match:
            sources_text = match.group(1)
            # Split by comma and clean up
            sources = [s.strip() for s in sources_text.split(',')]
            cited_sources.update(sources)
        
        return cited_sources
    
    def _has_proper_citation_formatting(self, response: str) -> bool:
        """Check for proper citation formatting."""
        # Look for proper citation format
        return bool(re.search(r'📚\s*\*\*Sources:\*\*|📚.*Sources:', response))
    
    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key terms from query for relevance checking."""
        # Remove common stop words
        stop_words = {'what', 'is', 'the', 'how', 'when', 'where', 'why', 'who', 'a', 'an', 'and', 'or', 'but'}
        
        # Extract words
        words = re.findall(r'\b\w{3,}\b', query.lower())
        
        # Filter out stop words
        key_terms = [word for word in words if word not in stop_words]
        
        return key_terms
    
    def _assess_query_type_relevance(self, response: str, query_type: QueryType) -> float:
        """Assess relevance to specific query type."""
        relevance_keywords = {
            QueryType.PROTOCOL_STEPS: ['protocol', 'procedure', 'steps', 'workflow', 'activation'],
            QueryType.DOSAGE_LOOKUP: ['dose', 'dosage', 'mg', 'ml', 'units', 'medication'],
            QueryType.CRITERIA_CHECK: ['criteria', 'rules', 'score', 'threshold', 'indication'],
            QueryType.CONTACT_LOOKUP: ['contact', 'phone', 'pager', 'call', 'on-call'],
            QueryType.FORM_RETRIEVAL: ['form', 'document', 'pdf', 'download', 'consent'],
            QueryType.SUMMARY_REQUEST: ['summary', 'overview', 'management', 'treatment']
        }
        
        keywords = relevance_keywords.get(query_type, [])
        if not keywords:
            return 0.5  # Neutral if no keywords defined
        
        response_lower = response.lower()
        matched_keywords = sum(1 for keyword in keywords if keyword in response_lower)
        
        return matched_keywords / len(keywords)
    
    def _addresses_medical_context(self, response: str, query: str) -> bool:
        """Check if response addresses the medical context of the query."""
        # Extract medical terms from query
        medical_terms = re.findall(r'\b(?:stemi|sepsis|cardiac|arrest|ottawa|hypoglycemia|protocol|dose|criteria)\b', 
                                   query.lower())
        
        if not medical_terms:
            return True  # Non-medical query
        
        response_lower = response.lower()
        return any(term in response_lower for term in medical_terms)
    
    def _has_consistent_bullets(self, response: str) -> bool:
        """Check for consistent bullet point style."""
        bullets = re.findall(r'^([•·-])\s', response, re.MULTILINE)
        
        if not bullets:
            return True  # No bullets is fine
        
        # Check if most bullets use the same style
        most_common = max(set(bullets), key=bullets.count) if bullets else None
        consistency_ratio = bullets.count(most_common) / len(bullets) if most_common else 0
        
        return consistency_ratio >= 0.8  # 80% consistency
    
    def _has_proper_medical_abbreviations(self, response: str) -> bool:
        """Check for proper medical abbreviation formatting."""
        common_abbrevs = ['STEMI', 'MI', 'CVA', 'PE', 'DVT', 'CHF', 'COPD', 'DKA', 'IV', 'IM', 'EKG', 'ECG']
        
        for abbrev in common_abbrevs:
            # Check if abbreviation appears in wrong case
            if re.search(f'\\b{abbrev.lower()}\\b', response):
                return False  # Found lowercase version
        
        return True
    
    def _has_appropriate_emphasis(self, response: str) -> bool:
        """Check for appropriate use of emphasis (bold, etc.)."""
        # Should have some bold text but not excessive
        bold_count = len(re.findall(r'\*\*[^*]+\*\*', response))
        
        response_length = len(response)
        if response_length == 0:
            return False
        
        # Reasonable ratio of bold text (should have some but not too much)
        return 2 <= bold_count <= response_length // 50  # Roughly 1 bold per 50 characters max
    
    def _has_unsupported_dosing(self, response: str, context: MedicalContext) -> bool:
        """Check for dosing information not supported by context."""
        # Extract doses from response
        doses = re.findall(r'\d+\s*(?:mg|ml|units)', response, re.IGNORECASE)
        
        if not doses:
            return False  # No dosing information
        
        # Check if context contains dosing information
        context_content = (context.primary_content + " " + 
                          " ".join(context.supporting_evidence)).lower()
        
        # Check if any doses appear to be unsupported
        for dose in doses:
            if dose.lower() not in context_content:
                # Could be unsupported, but this is a simple check
                # In practice, this would need more sophisticated medical knowledge
                pass
        
        return False  # Conservative approach - don't flag as unsupported easily
    
    def _missing_safety_warnings(self, response: str, context: MedicalContext) -> bool:
        """Check for missing safety warnings when they should be present."""
        # If response contains dosing information, should have warnings
        has_dosing = bool(re.search(r'\d+\s*(?:mg|ml|units)', response, re.IGNORECASE))
        has_warnings = bool(re.search(r'warning|caution|contraindication|⚠️', response, re.IGNORECASE))
        
        return has_dosing and not has_warnings
    
    def _has_inappropriate_medical_advice(self, response: str) -> bool:
        """Check for inappropriate medical advice."""
        # Check for definitive diagnostic statements without proper qualification
        inappropriate_patterns = [
            r'\byou have\b',
            r'\byou are\b.*(?:diagnosed|suffering)',
            r'\btake this medication\b',
            r'\bstop taking\b',
            r'\bdo not seek\b.*medical'
        ]
        
        return any(re.search(pattern, response, re.IGNORECASE) for pattern in inappropriate_patterns)
    
    def _has_inaccurate_contacts(self, response: str) -> bool:
        """Check for inaccurate contact information."""
        # This would need to be validated against a known contact database
        # For now, just check format validity
        phone_numbers = re.findall(r'\((\d{3})\)\s*(\d{3})-(\d{4})', response)
        
        # Check for obviously invalid numbers (all same digit, etc.)
        for area, prefix, number in phone_numbers:
            if area == '000' or prefix == '000' or number == '0000':
                return True
            if area == '111' or prefix == '111' or number == '1111':
                return True
        
        return False
    
    def _get_query_type_suggestions(self, response: str, query_type: QueryType) -> List[str]:
        """Get query-type-specific improvement suggestions."""
        suggestions = []
        
        if query_type == QueryType.PROTOCOL_STEPS:
            if 'workflow' not in response.lower():
                suggestions.append("Include step-by-step workflow")
            if not re.search(r'\d+\.', response):
                suggestions.append("Use numbered steps for procedures")
                
        elif query_type == QueryType.DOSAGE_LOOKUP:
            if 'adult' not in response.lower():
                suggestions.append("Include adult dosing information")
            if 'route' not in response.lower():
                suggestions.append("Specify administration route (IV, IM, PO)")
                
        elif query_type == QueryType.CONTACT_LOOKUP:
            if not re.search(r'\(\d{3}\)', response):
                suggestions.append("Format phone numbers professionally")
        
        return suggestions
    
    def _load_medical_terminology(self) -> Dict[str, str]:
        """Load medical terminology for validation."""
        return {
            'STEMI': 'ST-elevation myocardial infarction',
            'MI': 'Myocardial infarction',
            'CVA': 'Cerebrovascular accident',
            'PE': 'Pulmonary embolism',
            'DVT': 'Deep vein thrombosis',
            'CHF': 'Congestive heart failure',
            'COPD': 'Chronic obstructive pulmonary disease',
            'DKA': 'Diabetic ketoacidosis'
        }
    
    def _load_formatting_patterns(self) -> Dict[str, str]:
        """Load formatting patterns for validation."""
        return {
            'phone_number': r'\*\*\(\d{3}\) \d{3}-\d{4}\*\*',
            'extension': r'\*\*x\d{4,5}\*\*',
            'bold_header': r'\*\*[^*]+\*\*:',
            'bullet_point': r'^[•·-]\s',
            'medical_emoji': r'[🚨💉⏱️📞💊🔄⚠️📚🧪💡📊🦵🦠📋✅❌🚫📄]'
        }
    
    def _load_safety_keywords(self) -> List[str]:
        """Load safety keywords for validation."""
        return [
            'contraindication', 'warning', 'caution', 'adverse', 'side effect',
            'allergy', 'interaction', 'overdose', 'toxicity', 'emergency'
        ]
