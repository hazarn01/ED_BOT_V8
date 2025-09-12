"""
Smart Query Router
Routes queries to optimal retrieval methods based on query type and content.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class QueryCategory(Enum):
    FORM = "form"
    PROTOCOL = "protocol"
    DOSAGE = "dosage"
    CONTACT = "contact"
    CRITERIA = "criteria"
    GENERAL = "general"

@dataclass
class QueryRoute:
    category: QueryCategory
    confidence: float
    primary_method: str
    fallback_methods: List[str]

class SmartQueryRouter:
    """Smart router that determines optimal retrieval method for each query."""
    
    def __init__(self):
        # Query patterns for each category
        self.form_patterns = [
            r'show me.*form',
            r'.*form.*',
            r'.*consent.*',
            r'.*document.*',
            r'i need.*form',
            r'where.*form',
            r'get.*form',
            r'.*paperwork.*'
        ]
        
        self.protocol_patterns = [
            r'.*protocol.*',
            r'.*procedure.*',
            r'.*steps.*',
            r'.*activation.*',
            r'.*guideline.*',
            r'.*pathway.*',
            r'how to.*',
            r'what is the.*protocol'
        ]
        
        self.dosage_patterns = [
            r'.*dosage.*',
            r'.*dose.*',
            r'.*mg.*',
            r'.*ml.*',
            r'.*medication.*',
            r'.*drug.*',
            r'how much.*'
        ]
        
        self.contact_patterns = [
            r'.*contact.*',
            r'.*phone.*',
            r'.*pager.*',
            r'.*call.*',
            r'who.*on call',
            r'.*number.*'
        ]
        
        self.criteria_patterns = [
            r'.*criteria.*',
            r'.*score.*',
            r'.*threshold.*',
            r'.*guidelines.*',
            r'.*rules.*',
            r'when to.*'
        ]
        
        # Priority keywords that boost routing confidence
        self.priority_keywords = {
            QueryCategory.FORM: ['form', 'consent', 'document', 'show me', 'paperwork'],
            QueryCategory.PROTOCOL: ['protocol', 'activation', 'stemi', 'sepsis', 'procedure'],
            QueryCategory.DOSAGE: ['dosage', 'dose', 'mg', 'medication', 'aspirin', 'epi'],
            QueryCategory.CONTACT: ['contact', 'phone', 'pager', 'on call'],
            QueryCategory.CRITERIA: ['criteria', 'score', 'threshold', 'guidelines'],
        }
        
        # Method routing configuration
        self.routing_config = {
            QueryCategory.FORM: {
                'primary': 'form_retriever',
                'fallbacks': ['ground_truth', 'rag', 'database']
            },
            QueryCategory.PROTOCOL: {
                'primary': 'llm_rag',
                'fallbacks': ['ground_truth', 'database', 'emergency_processor']
            },
            QueryCategory.DOSAGE: {
                'primary': 'llm_rag',
                'fallbacks': ['ground_truth', 'emergency_processor', 'database']
            },
            QueryCategory.CONTACT: {
                'primary': 'ground_truth',
                'fallbacks': ['emergency_processor', 'database']
            },
            QueryCategory.CRITERIA: {
                'primary': 'llm_rag',
                'fallbacks': ['ground_truth', 'database']
            },
            QueryCategory.GENERAL: {
                'primary': 'llm_rag',
                'fallbacks': ['ground_truth', 'rag', 'database']
            }
        }
    
    def route_query(self, query: str) -> QueryRoute:
        """Route query to optimal retrieval method."""
        query_lower = query.lower()
        
        # Calculate scores for each category
        category_scores = {}
        
        for category in QueryCategory:
            score = self._calculate_category_score(query_lower, category)
            category_scores[category] = score
        
        # Find best category
        best_category = max(category_scores, key=category_scores.get)
        best_score = category_scores[best_category]
        
        # Get routing configuration
        config = self.routing_config[best_category]
        
        # Create route
        route = QueryRoute(
            category=best_category,
            confidence=min(best_score, 0.95),
            primary_method=config['primary'],
            fallback_methods=config['fallbacks']
        )
        
        logger.info(f"🧭 Query routed to {best_category.value} (confidence: {best_score:.2f}) -> {config['primary']}")
        
        return route
    
    def _calculate_category_score(self, query: str, category: QueryCategory) -> float:
        """Calculate confidence score for a specific category."""
        
        if category == QueryCategory.FORM:
            patterns = self.form_patterns
        elif category == QueryCategory.PROTOCOL:
            patterns = self.protocol_patterns
        elif category == QueryCategory.DOSAGE:
            patterns = self.dosage_patterns
        elif category == QueryCategory.CONTACT:
            patterns = self.contact_patterns
        elif category == QueryCategory.CRITERIA:
            patterns = self.criteria_patterns
        else:
            return 0.3  # Default score for general queries
        
        # Pattern matching score
        pattern_score = 0.0
        for pattern in patterns:
            if re.search(pattern, query):
                pattern_score = 0.7
                break
        
        # Keyword boost
        keyword_boost = 0.0
        if category in self.priority_keywords:
            keywords = self.priority_keywords[category]
            for keyword in keywords:
                if keyword in query:
                    keyword_boost += 0.1
        
        # Combine scores
        total_score = min(pattern_score + keyword_boost, 0.9)
        
        return total_score
    
    def get_execution_plan(self, query: str) -> Dict[str, Any]:
        """Get complete execution plan for query."""
        route = self.route_query(query)
        
        execution_plan = {
            'query': query,
            'category': route.category.value,
            'confidence': route.confidence,
            'primary_method': route.primary_method,
            'fallback_methods': route.fallback_methods,
            'expected_response_type': self._get_expected_response_type(route.category),
            'timeout': self._get_timeout_for_method(route.primary_method),
            'validation_required': self._requires_validation(route.category)
        }
        
        return execution_plan
    
    def _get_expected_response_type(self, category: QueryCategory) -> str:
        """Get expected response type for category."""
        type_mapping = {
            QueryCategory.FORM: 'pdf_links',
            QueryCategory.PROTOCOL: 'structured_text',
            QueryCategory.DOSAGE: 'medical_dosage',
            QueryCategory.CONTACT: 'contact_info',
            QueryCategory.CRITERIA: 'clinical_criteria',
            QueryCategory.GENERAL: 'general_info'
        }
        return type_mapping.get(category, 'general_info')
    
    def _get_timeout_for_method(self, method: str) -> int:
        """Get timeout in seconds for retrieval method."""
        timeout_mapping = {
            'llm_rag': 15,
            'form_retriever': 5,
            'ground_truth': 3,
            'rag': 10,
            'database': 5,
            'emergency_processor': 8
        }
        return timeout_mapping.get(method, 10)
    
    def _requires_validation(self, category: QueryCategory) -> bool:
        """Check if category requires validation."""
        validation_required = {
            QueryCategory.FORM: False,  # Forms are direct file access
            QueryCategory.PROTOCOL: True,  # Medical protocols need validation
            QueryCategory.DOSAGE: True,  # Dosages are critical
            QueryCategory.CONTACT: False,  # Contacts are factual
            QueryCategory.CRITERIA: True,  # Clinical criteria need validation
            QueryCategory.GENERAL: True   # General queries need validation
        }
        return validation_required.get(category, True)


# Global router instance
_smart_router = None

def get_smart_router() -> SmartQueryRouter:
    """Get singleton smart router instance."""
    global _smart_router
    if _smart_router is None:
        _smart_router = SmartQueryRouter()
    return _smart_router

def route_query(query: str) -> QueryRoute:
    """Convenience function to route a query."""
    router = get_smart_router()
    return router.route_query(query)