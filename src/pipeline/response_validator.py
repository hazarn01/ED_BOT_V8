"""Response quality validation and medical fact-checking module."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of response validation."""
    is_valid: bool
    confidence_score: float
    issues: List[str]
    medical_warnings: List[str]
    hallucination_detected: bool
    source_compliance: bool
    

class ResponseValidator:
    """Validates medical responses for accuracy, hallucination, and compliance."""
    
    def __init__(self):
        # Medical terms that should always have citations
        self.critical_medical_terms = {
            'dose', 'dosage', 'mg', 'ml', 'units', 'frequency', 'route',
            'contact', 'pager', 'phone', 'protocol', 'criteria', 'threshold',
            'contraindication', 'warning', 'adverse', 'interaction'
        }
        
        # Patterns that indicate hallucination or uncertainty
        self.hallucination_patterns = [
            r'i think', r'i believe', r'probably', r'might be', r'could be',
            r'generally', r'typically', r'usually', r'often', r'sometimes',
            r'i\'m not sure', r'i don\'t know', r'unclear', r'uncertain'
        ]
        
        # Patterns for medical disclaimers that indicate system fallback
        self.fallback_patterns = [
            r'consult.{0,20}doctor', r'seek.{0,20}medical.{0,20}attention',
            r'not.{0,10}medical.{0,10}advice', r'consult.{0,20}physician',
            r'emergency.{0,20}contact', r'call.{0,10}911'
        ]
        
    def validate_response(
        self, 
        query: str, 
        response: str, 
        query_type: str,
        retrieved_context: List[Dict[str, Any]],
        expected_sources: List[str]
    ) -> ValidationResult:
        """Comprehensive response validation."""
        
        issues = []
        medical_warnings = []
        confidence_score = 1.0
        
        # 1. Check for hallucination patterns
        hallucination_detected = self._detect_hallucination(response)
        if hallucination_detected:
            issues.append("Response contains uncertainty indicators")
            confidence_score *= 0.6
            
        # 2. Validate source citations
        source_compliance = self._validate_source_citations(response, retrieved_context, expected_sources)
        if not source_compliance:
            issues.append("Missing or incorrect source citations")
            confidence_score *= 0.7
            
        # 3. Check for medical fallback patterns
        fallback_detected = self._detect_medical_fallbacks(response)
        if fallback_detected:
            issues.append("Response contains generic medical disclaimers")
            confidence_score *= 0.5
            
        # 4. Validate context compliance
        context_compliance = self._validate_context_compliance(response, retrieved_context)
        if not context_compliance['is_compliant']:
            issues.extend(context_compliance['violations'])
            confidence_score *= 0.4
            
        # 5. Query-type-specific validation
        type_validation = self._validate_by_query_type(query, response, query_type, retrieved_context)
        if not type_validation['is_valid']:
            issues.extend(type_validation['issues'])
            medical_warnings.extend(type_validation['warnings'])
            confidence_score *= type_validation['confidence_penalty']
            
        # 6. Check for specific medical accuracy issues
        accuracy_issues = self._check_medical_accuracy(response, query_type)
        if accuracy_issues:
            issues.extend(accuracy_issues)
            medical_warnings.append("Medical accuracy concerns detected")
            confidence_score *= 0.3
            
        # Determine overall validity
        is_valid = (
            confidence_score >= 0.7 and 
            not hallucination_detected and 
            source_compliance and
            not fallback_detected
        )
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_score=confidence_score,
            issues=issues,
            medical_warnings=medical_warnings,
            hallucination_detected=hallucination_detected,
            source_compliance=source_compliance
        )
    
    def _detect_hallucination(self, response: str) -> bool:
        """Detect hallucination patterns in response."""
        response_lower = response.lower()
        
        for pattern in self.hallucination_patterns:
            if re.search(pattern, response_lower):
                logger.warning(f"Hallucination pattern detected: {pattern}")
                return True
                
        return False
    
    def _detect_medical_fallbacks(self, response: str) -> bool:
        """Detect generic medical fallback responses."""
        response_lower = response.lower()
        
        for pattern in self.fallback_patterns:
            if re.search(pattern, response_lower):
                logger.warning(f"Medical fallback pattern detected: {pattern}")
                return True
                
        return False
    
    def _validate_source_citations(
        self, 
        response: str, 
        retrieved_context: List[Dict[str, Any]], 
        expected_sources: List[str]
    ) -> bool:
        """Validate that response properly cites sources."""
        
        # Check if response contains source citations
        citation_patterns = [
            r'according to',
            r'source:',
            r'from.*\.pdf',
            r'per.*protocol',
            r'as stated in'
        ]
        
        has_citations = any(re.search(pattern, response.lower()) for pattern in citation_patterns)
        
        if not has_citations and retrieved_context:
            logger.warning("Response lacks proper source citations")
            return False
            
        # Check if critical medical terms have supporting citations
        response_lower = response.lower()
        for term in self.critical_medical_terms:
            if term in response_lower:
                # Look for nearby citations
                term_positions = [m.start() for m in re.finditer(re.escape(term), response_lower)]
                has_nearby_citation = False
                
                for pos in term_positions:
                    # Check 200 characters around the term for citation
                    context_window = response_lower[max(0, pos-200):pos+200]
                    if any(re.search(pattern, context_window) for pattern in citation_patterns):
                        has_nearby_citation = True
                        break
                        
                if not has_nearby_citation:
                    logger.warning(f"Critical medical term '{term}' lacks citation")
                    return False
                    
        return True
    
    def _validate_context_compliance(
        self, 
        response: str, 
        retrieved_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check if response only uses information from provided context."""
        
        violations = []
        
        if not retrieved_context:
            return {'is_compliant': False, 'violations': ['No context provided but response generated']}
        
        # Extract all factual claims from response
        medical_facts = self._extract_medical_facts(response)
        
        # Build context text for comparison
        context_text = ""
        for item in retrieved_context:
            content = item.get('content', '')
            if content:
                context_text += content.lower() + " "
        
        # Check each fact against context
        for fact in medical_facts:
            if not self._is_fact_supported_by_context(fact, context_text):
                violations.append(f"Unsupported medical fact: {fact[:100]}...")
        
        # Check for specific patterns that indicate hallucination
        if "i don't have information" in response.lower() and retrieved_context:
            violations.append("Claims lack of information despite having context")
        
        return {
            'is_compliant': len(violations) == 0,
            'violations': violations
        }
    
    def _validate_by_query_type(
        self, 
        query: str, 
        response: str, 
        query_type: str, 
        retrieved_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Query-type-specific validation."""
        
        issues = []
        warnings = []
        confidence_penalty = 1.0
        
        if query_type.lower() == 'protocol':
            # STEMI protocol should include contact numbers
            if 'stemi' in query.lower():
                if not re.search(r'\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b', response):
                    issues.append("STEMI protocol missing contact numbers")
                    confidence_penalty = 0.3
                    
                if 'door-to-balloon' not in response.lower():
                    issues.append("STEMI protocol missing door-to-balloon timing")
                    confidence_penalty *= 0.7
                    
        elif query_type.lower() == 'dosage':
            # Epinephrine dosing should be specific
            if 'epinephrine' in query.lower():
                # Check for correct epinephrine dosing
                if '50ml' in response or '50 ml' in response:
                    issues.append("Incorrect epinephrine dosing: shows volume instead of mg")
                    warnings.append("CRITICAL: Epinephrine dosing error detected")
                    confidence_penalty = 0.1
                    
                if not re.search(r'1\s*mg', response):
                    issues.append("Epinephrine response missing standard 1mg dose")
                    confidence_penalty *= 0.5
                    
                if not re.search(r'3[-\s]?5\s*min', response):
                    issues.append("Epinephrine response missing 3-5 minute interval")
                    confidence_penalty *= 0.7
                    
        elif query_type.lower() == 'criteria':
            # Ottawa rules should have specific criteria
            if 'ottawa' in query.lower():
                if 'malleolar' not in response.lower():
                    issues.append("Ottawa rules missing malleolar zone criteria")
                    confidence_penalty *= 0.6
                    
                if 'weight' not in response.lower() and 'bear' not in response.lower():
                    issues.append("Ottawa rules missing weight bearing criteria")
                    confidence_penalty *= 0.6
                    
                if len(response) < 100:
                    issues.append("Ottawa rules response too brief - likely incomplete")
                    confidence_penalty *= 0.4
                    
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'confidence_penalty': confidence_penalty
        }
    
    def _check_medical_accuracy(self, response: str, query_type: str) -> List[str]:
        """Check for known medical accuracy issues."""
        
        issues = []
        response_lower = response.lower()
        
        # Check for common medical errors
        medical_error_patterns = [
            (r'50\s*ml.*epinephrine', "Incorrect epinephrine volume measurement"),
            (r'epinephrine.*50\s*ml', "Incorrect epinephrine volume measurement"),
            (r'lactate.*>.*5', "Incorrect sepsis lactate threshold (should be >2 for severe, >4 for shock)"),
            (r'door.*balloon.*120', "Incorrect STEMI timing (should be 90 minutes)")
        ]
        
        for pattern, error_msg in medical_error_patterns:
            if re.search(pattern, response_lower):
                issues.append(error_msg)
                
        # Check for mixing of protocols
        protocols_mentioned = []
        if 'stemi' in response_lower:
            protocols_mentioned.append('stemi')
        if 'sepsis' in response_lower:
            protocols_mentioned.append('sepsis')
        if 'trauma' in response_lower:
            protocols_mentioned.append('trauma')
            
        # If multiple protocols mentioned in a single query response, flag it
        if len(protocols_mentioned) > 1 and len(response) < 500:
            issues.append(f"Multiple protocols mentioned in short response: {protocols_mentioned}")
            
        return issues
    
    def _extract_medical_facts(self, response: str) -> List[str]:
        """Extract factual medical statements from response."""
        
        # Split response into sentences
        sentences = re.split(r'[.!?]+', response)
        
        medical_facts = []
        medical_keywords = [
            'dose', 'dosage', 'mg', 'ml', 'units', 'contact', 'pager', 'phone',
            'protocol', 'criteria', 'threshold', 'minutes', 'hours', 'administration'
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10:  # Ignore very short fragments
                # Check if sentence contains medical information
                sentence_lower = sentence.lower()
                if any(keyword in sentence_lower for keyword in medical_keywords):
                    medical_facts.append(sentence)
                    
        return medical_facts
    
    def _is_fact_supported_by_context(self, fact: str, context_text: str) -> bool:
        """Check if a medical fact is supported by the context."""
        
        fact_lower = fact.lower()
        
        # Extract key terms from the fact
        words = re.findall(r'\b\w{3,}\b', fact_lower)
        
        # Check if most key terms appear in context
        supported_terms = sum(1 for word in words if word in context_text)
        support_ratio = supported_terms / len(words) if words else 0
        
        # Require at least 60% of terms to be in context for complex facts
        return support_ratio >= 0.6
        
    def generate_validation_report(self, validation_result: ValidationResult, query: str) -> str:
        """Generate a human-readable validation report."""
        
        report = [f"Validation Report for Query: '{query}'"]
        report.append("=" * 50)
        
        # Overall status
        status = "✅ VALID" if validation_result.is_valid else "❌ INVALID"
        report.append(f"Status: {status}")
        report.append(f"Confidence Score: {validation_result.confidence_score:.2f}")
        
        # Issues
        if validation_result.issues:
            report.append("\n🔍 Issues Detected:")
            for issue in validation_result.issues:
                report.append(f"  • {issue}")
        
        # Medical warnings
        if validation_result.medical_warnings:
            report.append("\n⚠️ Medical Warnings:")
            for warning in validation_result.medical_warnings:
                report.append(f"  • {warning}")
        
        # Specific detections
        if validation_result.hallucination_detected:
            report.append("\n🚨 Hallucination detected")
            
        if not validation_result.source_compliance:
            report.append("\n📚 Source citation issues")
        
        return "\n".join(report)