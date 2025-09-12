"""
Response Validation Layer
Validates responses to ensure they match query expectations and are medically safe.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ValidationResult(Enum):
    VALID = "valid"
    INVALID = "invalid" 
    NEEDS_REVIEW = "needs_review"

@dataclass
class ValidationReport:
    result: ValidationResult
    confidence: float
    issues: List[str]
    corrections: List[str]
    safety_flags: List[str]

class ResponseValidator:
    """Validates responses to ensure accuracy and safety."""
    
    def __init__(self):
        # Common mismatched responses to detect
        self.mismatch_patterns = [
            {
                'query_pattern': r'.*transfusion.*form.*',
                'wrong_content': ['allergic reaction', 'retu allergic', 'pathway'],
                'issue': 'Form query returning protocol content'
            },
            {
                'query_pattern': r'.*aspirin.*dosage.*',
                'wrong_content': ['tia pathway', 'abcd score'],
                'issue': 'Dosage query returning pathway content'
            }
        ]
    
    def validate_response(self, query: str, response_data: Dict[str, Any]) -> ValidationReport:
        """Validate a response against the query."""
        
        query_lower = query.lower()
        response_text = response_data.get('response', '').lower()
        
        issues = []
        corrections = []
        safety_flags = []
        
        # Check for query-response mismatch
        mismatch_issues = self._check_query_response_mismatch(query_lower, response_text)
        issues.extend(mismatch_issues)
        
        # Form-specific validation
        if self._is_form_query(query_lower):
            form_issues = self._validate_form_response(query, response_data)
            issues.extend(form_issues)
        
        # Determine overall validation result
        if len(issues) == 0:
            result = ValidationResult.VALID
            confidence = 0.95
        elif len(issues) > 2:
            result = ValidationResult.INVALID
            confidence = 0.2
        else:
            result = ValidationResult.NEEDS_REVIEW
            confidence = 0.6
        
        return ValidationReport(
            result=result,
            confidence=confidence,
            issues=issues,
            corrections=corrections,
            safety_flags=safety_flags
        )
    
    def _check_query_response_mismatch(self, query: str, response: str) -> List[str]:
        """Check for obvious query-response mismatches."""
        issues = []
        
        for pattern_config in self.mismatch_patterns:
            query_pattern = pattern_config['query_pattern']
            wrong_content = pattern_config['wrong_content']
            issue_description = pattern_config['issue']
            
            if re.search(query_pattern, query):
                for wrong_term in wrong_content:
                    if wrong_term in response:
                        issues.append(f"{issue_description}: Contains '{wrong_term}'")
                        logger.warning(f"🚨 Mismatch detected: {issue_description}")
        
        return issues
    
    def _validate_form_response(self, query: str, response_data: Dict) -> List[str]:
        """Validate form-specific response requirements."""
        issues = []
        
        response_text = response_data.get('response', '').lower()
        
        # Should not contain protocol/pathway content for form queries
        protocol_indicators = ['retu allergic', 'pathway', 'protocol steps', 'criteria']
        has_protocol_content = any(indicator in response_text for indicator in protocol_indicators)
        
        if has_protocol_content:
            issues.append("Form query response contains protocol/pathway content")
        
        return issues
    
    def _is_form_query(self, query: str) -> bool:
        """Check if query is asking for forms."""
        form_indicators = ['show me', 'form', 'consent', 'document', 'paperwork']
        return any(indicator in query for indicator in form_indicators)


def validate_response(query: str, response_data: Dict[str, Any]) -> ValidationReport:
    """Convenience function to validate a response."""
    validator = ResponseValidator()
    return validator.validate_response(query, response_data)