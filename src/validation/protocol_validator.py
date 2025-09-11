"""
Protocol Response Validator - PRP-40
Validates protocol search results for relevance and quality to prevent irrelevant responses.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ProtocolResponseValidator:
    """Validates protocol responses for quality and relevance."""
    
    def __init__(self):
        # Define medical protocol keywords by type
        self.protocol_keywords = {
            'sepsis': ['sepsis', 'lactate', 'sirs', 'shock', 'infection', 'antibiotics', 'fluid', 'resuscitation'],
            'stemi': ['stemi', 'myocardial', 'cath', 'pci', 'door-to-balloon', 'ekg', 'troponin'],
            'stroke': ['stroke', 'tpa', 'nihss', 'ct', 'last known well', 'neuro'],
            'trauma': ['trauma', 'activation', 'level', 'gcs', 'fast', 'blood'],
            'cardiac_arrest': ['cardiac arrest', 'cpr', 'acls', 'rosc', 'epinephrine', 'defibrillation']
        }
        
        # Content that indicates irrelevant results
        self.irrelevant_indicators = [
            'chf pathway', 'heart failure admission', 'referral line', 
            'photography', 'context_enhancement', 'test', 'example',
            'phase_', 'development', 'readme'
        ]
        
    def validate_protocol_response(self, query: str, results: List[Dict]) -> bool:
        """
        Validate protocol search results for relevance.
        
        Args:
            query: Original query string
            results: List of search results from RAG
            
        Returns:
            True if results are relevant and high-quality, False otherwise
        """
        if not results:
            return False
            
        query_lower = query.lower()
        
        # Identify which protocol is being asked about
        protocol_type = self._identify_protocol_type(query_lower)
        
        # Check each result for relevance
        relevant_count = 0
        for result in results[:5]:  # Check top 5 results
            if self._is_relevant_result(result, protocol_type, query_lower):
                relevant_count += 1
                
        # Require at least 2 relevant results in top 5 for confidence
        return relevant_count >= 2
    
    def _identify_protocol_type(self, query: str) -> Optional[str]:
        """Identify which protocol type is being asked about."""
        for protocol_type, keywords in self.protocol_keywords.items():
            for keyword in keywords[:3]:  # Check primary keywords
                if keyword in query:
                    return protocol_type
        return None
    
    def _is_relevant_result(self, result: Dict, protocol_type: Optional[str], query: str) -> bool:
        """Check if a single result is relevant."""
        content = result.get('content', '').lower()
        filename = result.get('source', {}).get('filename', '').lower()
        
        # Check for irrelevant content indicators
        for indicator in self.irrelevant_indicators:
            if indicator in content or indicator in filename:
                logger.debug(f"Result rejected due to irrelevant indicator: {indicator}")
                return False
        
        # If we identified a protocol type, check for specific keywords
        if protocol_type and protocol_type in self.protocol_keywords:
            keywords = self.protocol_keywords[protocol_type]
            keyword_matches = sum(1 for keyword in keywords if keyword in content)
            
            # Require at least 2 keyword matches for relevance
            if keyword_matches < 2:
                logger.debug(f"Result rejected - insufficient {protocol_type} keywords: {keyword_matches}")
                return False
                
        # Generic protocol validation if type not identified
        else:
            # Look for general protocol indicators
            protocol_indicators = [
                'protocol', 'pathway', 'management', 'treatment', 
                'procedure', 'steps', 'workflow', 'guideline'
            ]
            
            has_protocol_indicator = any(ind in content for ind in protocol_indicators)
            if not has_protocol_indicator:
                logger.debug("Result rejected - no protocol indicators found")
                return False
        
        return True
    
    def validate_sepsis_response(self, query: str, results: List[Dict]) -> bool:
        """
        Specialized validation for sepsis protocol responses.
        
        Args:
            query: Original query string
            results: List of search results from RAG
            
        Returns:
            True if results contain proper sepsis content
        """
        if not results:
            return False
        
        sepsis_keywords = ['sepsis', 'lactate', 'sirs', 'shock', 'infection', 'antibiotics']
        
        for result in results[:3]:  # Check top 3 results
            content = result.get('content', '').lower()
            
            # Count sepsis-related keywords
            keyword_matches = sum(1 for keyword in sepsis_keywords if keyword in content)
            
            # Reject if content has < 2 sepsis keywords
            if keyword_matches < 2:
                continue
                
            # Reject obvious non-sepsis content
            if any(indicator in content for indicator in ['chf', 'heart failure', 'referral line']):
                continue
                
            # This result is relevant
            return True
            
        return False  # No relevant results found
    
    def get_quality_score(self, query: str, results: List[Dict]) -> float:
        """
        Calculate a quality score for the search results.
        
        Args:
            query: Original query string
            results: List of search results
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        if not results:
            return 0.0
            
        query_lower = query.lower()
        protocol_type = self._identify_protocol_type(query_lower)
        
        total_score = 0.0
        for i, result in enumerate(results[:5]):
            # Higher weight for earlier results
            position_weight = 1.0 - (i * 0.15)
            
            if self._is_relevant_result(result, protocol_type, query_lower):
                # Check similarity/confidence score from the result
                similarity = result.get('similarity', 0.5)
                total_score += similarity * position_weight
                
        # Normalize to 0-1 range
        return min(1.0, total_score / 3.0)  # Divide by expected max score