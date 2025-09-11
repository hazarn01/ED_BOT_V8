"""
BM25 Scoring System for Enhanced Medical Retrieval
Medical-optimized BM25 relevance scoring with clinical text characteristics.
"""

import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class BM25Score:
    """BM25 scoring result with detailed metrics."""
    score: float
    term_frequencies: Dict[str, float]
    document_length: int
    average_doc_length: float
    idf_scores: Dict[str, float]
    normalized_tf_scores: Dict[str, float]


@dataclass
class BM25Configuration:
    """BM25 parameters optimized for medical text."""
    k1: float = 1.2  # Term frequency saturation point (lower for medical text)
    b: float = 0.75  # Length normalization factor
    medical_boost: float = 1.5  # Boost factor for medical terminology
    min_doc_length: int = 30  # Minimum document length to consider


class BM25Scorer:
    """
    Medical-optimized BM25 scorer for enhanced retrieval quality.
    Implements BM25 algorithm with medical domain awareness.
    """
    
    def __init__(self, db: Session, config: BM25Configuration = None):
        self.db = db
        self.config = config or BM25Configuration()
        
        # Medical terminology for enhanced scoring
        self.medical_terms = self._load_medical_terms()
        self.medical_abbreviations = self._load_medical_abbreviations()
        
        # Document statistics cache
        self._doc_stats_cache = {}
        self._collection_stats = None
        
    def calculate_bm25_scores(
        self, 
        query_terms: List[str], 
        candidate_chunks: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], BM25Score]]:
        """
        Calculate BM25 scores for candidate document chunks.
        
        Args:
            query_terms: Processed query terms
            candidate_chunks: Database results to score
            
        Returns:
            List of (chunk_data, BM25Score) tuples sorted by relevance
        """
        try:
            if not candidate_chunks:
                return []
            
            # Get collection statistics
            if not self._collection_stats:
                self._collection_stats = self._calculate_collection_stats()
            
            scored_results = []
            avg_doc_length = self._collection_stats.get('avg_doc_length', 100.0)
            
            for chunk in candidate_chunks:
                content = chunk.get('chunk_text', '')
                if len(content) < self.config.min_doc_length:
                    continue
                
                # Calculate BM25 score for this chunk
                bm25_score = self._calculate_chunk_bm25(
                    query_terms, content, avg_doc_length
                )
                
                scored_results.append((chunk, bm25_score))
                
            # Sort by BM25 score (descending)
            scored_results.sort(key=lambda x: x[1].score, reverse=True)
            
            logger.info(f"BM25 scoring completed for {len(scored_results)} chunks")
            return scored_results
            
        except Exception as e:
            logger.error(f"BM25 scoring failed: {e}")
            # Return original results with default scores
            return [(chunk, BM25Score(0.0, {}, 0, 0.0, {}, {})) for chunk in candidate_chunks]
    
    def score_sql_results(
        self, 
        query: str, 
        db_results: List[Any], 
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Score SQL database results using BM25 with medical optimizations.
        
        Args:
            query: Original query string
            db_results: SQLAlchemy result objects
            k: Number of top results to return
            
        Returns:
            List of enhanced result dictionaries with BM25 scores
        """
        try:
            # Extract and normalize query terms
            query_terms = self._extract_query_terms(query)
            if not query_terms:
                logger.warning("No valid query terms extracted")
                return self._format_default_results(db_results, k)
            
            # Convert SQL results to dictionaries
            candidate_chunks = []
            for row in db_results:
                chunk_dict = {
                    'id': getattr(row, 'id', ''),
                    'document_id': getattr(row, 'document_id', ''),
                    'chunk_text': getattr(row, 'chunk_text', ''),
                    'chunk_index': getattr(row, 'chunk_index', 0),
                    'metadata': getattr(row, 'metadata', {}),
                    'filename': getattr(row, 'filename', ''),
                    'content_type': getattr(row, 'content_type', ''),
                    'file_type': getattr(row, 'file_type', ''),
                    'display_name': getattr(row, 'display_name', ''),
                    'category': getattr(row, 'category', ''),
                    'original_relevance': getattr(row, 'relevance', 0.0)
                }
                candidate_chunks.append(chunk_dict)
            
            # Calculate BM25 scores
            scored_results = self.calculate_bm25_scores(query_terms, candidate_chunks)
            
            # Format results with enhanced metadata
            enhanced_results = []
            for chunk_data, bm25_score in scored_results[:k]:
                # Combine BM25 score with medical boosting
                medical_boost = self._calculate_medical_boost(
                    chunk_data['chunk_text'], query_terms
                )
                final_score = bm25_score.score * medical_boost
                
                enhanced_result = {
                    **chunk_data,
                    'bm25_score': bm25_score.score,
                    'medical_boost': medical_boost,
                    'final_score': final_score,
                    'relevance': final_score,  # Override original relevance
                    'bm25_metadata': {
                        'term_frequencies': bm25_score.term_frequencies,
                        'idf_scores': bm25_score.idf_scores,
                        'document_length': bm25_score.document_length,
                        'normalized_tf': bm25_score.normalized_tf_scores
                    }
                }
                enhanced_results.append(enhanced_result)
            
            logger.info(f"Enhanced {len(enhanced_results)} results with BM25 scoring")
            return enhanced_results
            
        except Exception as e:
            logger.error(f"BM25 SQL result scoring failed: {e}")
            return self._format_default_results(db_results, k)
    
    def _calculate_chunk_bm25(
        self, 
        query_terms: List[str], 
        content: str, 
        avg_doc_length: float
    ) -> BM25Score:
        """Calculate BM25 score for a single chunk."""
        content_lower = content.lower()
        doc_length = len(content.split())
        
        # Calculate term frequencies
        content_terms = content_lower.split()
        term_frequencies = {}
        idf_scores = {}
        normalized_tf_scores = {}
        
        total_score = 0.0
        
        for term in query_terms:
            term_lower = term.lower()
            
            # Calculate term frequency in document
            tf = content_terms.count(term_lower)
            term_frequencies[term] = tf
            
            if tf > 0:
                # Calculate IDF (using approximation for performance)
                idf = self._calculate_idf_approximation(term_lower)
                idf_scores[term] = idf
                
                # BM25 TF normalization
                tf_normalized = (tf * (self.config.k1 + 1)) / (
                    tf + self.config.k1 * (
                        1 - self.config.b + 
                        self.config.b * (doc_length / avg_doc_length)
                    )
                )
                normalized_tf_scores[term] = tf_normalized
                
                # Add to total BM25 score
                total_score += idf * tf_normalized
        
        return BM25Score(
            score=total_score,
            term_frequencies=term_frequencies,
            document_length=doc_length,
            average_doc_length=avg_doc_length,
            idf_scores=idf_scores,
            normalized_tf_scores=normalized_tf_scores
        )
    
    def _extract_query_terms(self, query: str) -> List[str]:
        """Extract and normalize query terms for BM25 scoring."""
        # Remove punctuation and normalize
        query_clean = re.sub(r'[^\w\s]', ' ', query.lower())
        words = query_clean.split()
        
        # Filter out stop words but keep medical terms
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                     'could', 'should', 'may', 'might', 'can', 'shall'}
        
        # Keep meaningful terms and medical abbreviations
        meaningful_terms = []
        for word in words:
            if len(word) >= 2 and (
                word not in stop_words or 
                word.upper() in self.medical_abbreviations or
                word in self.medical_terms
            ):
                meaningful_terms.append(word)
        
        # Also extract medical abbreviations from original query
        medical_abbrevs = re.findall(r'\b[A-Z]{2,}\b', query)
        for abbrev in medical_abbrevs:
            if abbrev not in [t.upper() for t in meaningful_terms]:
                meaningful_terms.append(abbrev.lower())
        
        return meaningful_terms
    
    def _calculate_idf_approximation(self, term: str) -> float:
        """
        Calculate IDF approximation optimized for medical text.
        Uses statistical approximation to avoid expensive database queries.
        """
        # Medical terms get higher base IDF
        if (term.upper() in self.medical_abbreviations or 
            term in self.medical_terms):
            base_idf = 4.0
        else:
            # Standard terms get moderate IDF
            base_idf = 3.0
        
        # Adjust based on term length and characteristics
        if len(term) <= 2:
            return base_idf * 0.5  # Short terms are common
        elif len(term) >= 8:
            return base_idf * 1.3  # Long terms are more specific
        else:
            return base_idf
    
    def _calculate_medical_boost(self, content: str, query_terms: List[str]) -> float:
        """Calculate medical terminology boost factor."""
        content_lower = content.lower()
        boost_factor = 1.0
        
        # Boost for medical abbreviations
        for term in query_terms:
            if term.upper() in self.medical_abbreviations:
                # Check for exact abbreviation match
                if re.search(r'\b' + re.escape(term.upper()) + r'\b', content):
                    boost_factor += 0.3
                # Check for full form match
                full_form = self.medical_abbreviations.get(term.upper(), '').lower()
                if full_form and full_form in content_lower:
                    boost_factor += 0.2
        
        # Boost for medical context indicators
        medical_indicators = [
            'protocol', 'guideline', 'criteria', 'dose', 'dosage', 
            'mg', 'ml', 'units', 'emergency', 'treatment', 'medication'
        ]
        
        indicator_matches = sum(1 for indicator in medical_indicators 
                              if indicator in content_lower)
        boost_factor += indicator_matches * 0.1
        
        # Cap the boost to prevent excessive weighting
        return min(boost_factor, 2.5)
    
    def _calculate_collection_stats(self) -> Dict[str, float]:
        """Calculate document collection statistics for BM25."""
        try:
            # Try to get statistics if database connection is available
            if self.db and hasattr(self.db, 'execute'):
                stats_query = text("""
                    SELECT 
                        COUNT(*) as total_docs,
                        AVG(LENGTH(chunk_text)) as avg_char_length,
                        AVG(array_length(string_to_array(chunk_text, ' '), 1)) as avg_word_length
                    FROM document_chunks 
                    WHERE LENGTH(chunk_text) >= :min_length
                """)
                
                result = self.db.execute(stats_query, {
                    'min_length': self.config.min_doc_length
                }).fetchone()
                
                if result and result.total_docs:
                    logger.info(f"Retrieved collection stats: {result.total_docs} documents")
                    return {
                        'total_docs': float(result.total_docs or 1000),
                        'avg_char_length': float(result.avg_char_length or 300),
                        'avg_doc_length': float(result.avg_word_length or 75)
                    }
                    
        except Exception as e:
            logger.warning(f"Database collection stats failed, using fallback: {e}")
        
        # Use optimized fallback defaults for medical text
        logger.info("Using fallback collection statistics for BM25")
        return {
            'total_docs': 2000.0,  # Assume reasonable corpus size
            'avg_char_length': 350.0,  # Medical text tends to be longer
            'avg_doc_length': 85.0  # Average words per medical chunk
        }
    
    def _format_default_results(self, db_results: List[Any], k: int) -> List[Dict[str, Any]]:
        """Format default results when BM25 scoring fails."""
        results = []
        for i, row in enumerate(db_results[:k]):
            result_dict = {
                'id': getattr(row, 'id', ''),
                'document_id': getattr(row, 'document_id', ''),
                'chunk_text': getattr(row, 'chunk_text', ''),
                'chunk_index': getattr(row, 'chunk_index', 0),
                'metadata': getattr(row, 'metadata', {}),
                'filename': getattr(row, 'filename', ''),
                'content_type': getattr(row, 'content_type', ''),
                'file_type': getattr(row, 'file_type', ''),
                'display_name': getattr(row, 'display_name', ''),
                'category': getattr(row, 'category', ''),
                'relevance': 1.0 - (i * 0.1),  # Simple decreasing relevance
                'bm25_score': 0.0,
                'medical_boost': 1.0,
                'final_score': 1.0 - (i * 0.1)
            }
            results.append(result_dict)
        return results
    
    def _load_medical_terms(self) -> List[str]:
        """Load medical terms for enhanced BM25 scoring."""
        return [
            'protocol', 'guideline', 'criteria', 'dose', 'dosage', 'treatment',
            'emergency', 'urgent', 'contact', 'pager', 'phone', 'activation',
            'procedure', 'medication', 'contraindication', 'indication',
            'assessment', 'evaluation', 'management', 'therapeutic',
            'cardiac', 'respiratory', 'neurological', 'sepsis', 'shock',
            'anaphylaxis', 'trauma', 'overdose', 'poisoning', 'seizure'
        ]
    
    def _load_medical_abbreviations(self) -> Dict[str, str]:
        """Load medical abbreviations for context-aware scoring."""
        return {
            'STEMI': 'ST-elevation myocardial infarction',
            'NSTEMI': 'Non-ST-elevation myocardial infarction',
            'MI': 'Myocardial infarction',
            'CVA': 'Cerebrovascular accident',
            'PE': 'Pulmonary embolism',
            'DVT': 'Deep vein thrombosis',
            'CHF': 'Congestive heart failure',
            'COPD': 'Chronic obstructive pulmonary disease',
            'DKA': 'Diabetic ketoacidosis',
            'ACLS': 'Advanced cardiac life support',
            'BLS': 'Basic life support',
            'IV': 'Intravenous',
            'IM': 'Intramuscular',
            'SQ': 'Subcutaneous',
            'PO': 'Per os (by mouth)',
            'PRN': 'Pro re nata (as needed)',
            'STAT': 'Immediately',
            'DNR': 'Do not resuscitate',
            'ICU': 'Intensive care unit',
            'ED': 'Emergency department',
            'EKG': 'Electrocardiogram',
            'ECG': 'Electrocardiogram',
            'BP': 'Blood pressure',
            'HR': 'Heart rate',
            'RR': 'Respiratory rate',
            'O2SAT': 'Oxygen saturation'
        }