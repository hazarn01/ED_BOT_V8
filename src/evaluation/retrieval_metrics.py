"""
Retrieval Quality Metrics Framework
Measures and tracks retrieval performance for continuous improvement
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from collections import defaultdict

@dataclass
class RetrievalMetrics:
    """Container for retrieval quality metrics."""
    query: str
    query_type: str
    timestamp: datetime
    
    # Retrieval metrics
    chunks_retrieved: int
    retrieval_time_ms: float
    precision_at_k: float  # % of retrieved chunks that are relevant
    recall_at_k: float     # % of relevant chunks that were retrieved
    mrr: float            # Mean Reciprocal Rank (1/rank of first relevant)
    
    # Response metrics
    response_length: int
    response_time_ms: float
    has_sources: bool
    num_sources: int
    confidence_score: float
    
    # Ground truth comparison
    matches_ground_truth: bool
    ground_truth_overlap: float  # % of key facts covered
    factual_accuracy: float
    
    # Error tracking
    has_error: bool = False
    error_type: Optional[str] = None
    

class RetrievalEvaluator:
    """Evaluates retrieval and response quality against ground truth."""
    
    def __init__(self, ground_truth_dir: str = "ground_truth_qa"):
        self.ground_truth_dir = Path(ground_truth_dir)
        self.ground_truth = self._load_ground_truth()
        self.metrics_history = []
        self.aggregated_metrics = defaultdict(list)
        
    def _load_ground_truth(self) -> Dict[str, List[Dict]]:
        """Load all ground truth QA pairs from JSON files."""
        ground_truth = {}
        
        for category in ["guidelines", "protocols", "reference"]:
            category_path = self.ground_truth_dir / category
            if not category_path.exists():
                continue
                
            for json_file in category_path.glob("*.json"):
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    # Store by source document
                    doc_name = json_file.stem
                    if isinstance(data, dict):
                        ground_truth[doc_name] = data.get("qa_pairs", [])
                    elif isinstance(data, list):
                        # Handle case where JSON is directly a list of QA pairs
                        ground_truth[doc_name] = data
                    
        return ground_truth
    
    def evaluate_retrieval(
        self,
        query: str,
        retrieved_chunks: List[Dict],
        response: str,
        query_type: str,
        response_time_ms: float,
        expected_answer: Optional[str] = None
    ) -> RetrievalMetrics:
        """
        Evaluate retrieval quality for a single query.
        
        Args:
            query: The user's query
            retrieved_chunks: List of retrieved document chunks
            response: The generated response
            query_type: Classification of query type
            response_time_ms: Total response time
            expected_answer: Optional ground truth answer
        """
        start_time = time.time()
        
        # Basic retrieval metrics
        chunks_retrieved = len(retrieved_chunks)
        has_sources = chunks_retrieved > 0
        num_sources = len(set(c.get("source", {}).get("filename", "") 
                            for c in retrieved_chunks if c.get("source")))
        
        # Calculate precision and recall if we have expected answer
        precision_at_k = 0.0
        recall_at_k = 0.0
        mrr = 0.0
        
        if expected_answer and retrieved_chunks:
            relevant_chunks = self._identify_relevant_chunks(
                retrieved_chunks, expected_answer
            )
            precision_at_k = len(relevant_chunks) / len(retrieved_chunks)
            
            # For recall, we'd need to know total relevant chunks (harder)
            # Using a simplified version based on coverage
            recall_at_k = min(1.0, len(relevant_chunks) / 3)  # Assume 3 relevant chunks ideal
            
            # Mean Reciprocal Rank
            for i, chunk in enumerate(retrieved_chunks):
                if self._is_chunk_relevant(chunk, expected_answer):
                    mrr = 1.0 / (i + 1)
                    break
        
        # Response quality metrics
        confidence_score = self._calculate_confidence(retrieved_chunks, response)
        
        # Ground truth comparison
        matches_ground_truth = False
        ground_truth_overlap = 0.0
        factual_accuracy = 0.0
        
        if expected_answer:
            matches_ground_truth, ground_truth_overlap = self._compare_to_ground_truth(
                response, expected_answer
            )
            factual_accuracy = self._calculate_factual_accuracy(response, expected_answer)
        
        retrieval_time_ms = (time.time() - start_time) * 1000
        
        metrics = RetrievalMetrics(
            query=query,
            query_type=query_type,
            timestamp=datetime.now(),
            chunks_retrieved=chunks_retrieved,
            retrieval_time_ms=retrieval_time_ms,
            precision_at_k=precision_at_k,
            recall_at_k=recall_at_k,
            mrr=mrr,
            response_length=len(response),
            response_time_ms=response_time_ms,
            has_sources=has_sources,
            num_sources=num_sources,
            confidence_score=confidence_score,
            matches_ground_truth=matches_ground_truth,
            ground_truth_overlap=ground_truth_overlap,
            factual_accuracy=factual_accuracy
        )
        
        # Store metrics
        self.metrics_history.append(metrics)
        self.aggregated_metrics[query_type].append(metrics)
        
        return metrics
    
    def _identify_relevant_chunks(
        self, 
        chunks: List[Dict], 
        expected_answer: str
    ) -> List[Dict]:
        """Identify which retrieved chunks are actually relevant."""
        relevant = []
        expected_lower = expected_answer.lower()
        
        for chunk in chunks:
            content = chunk.get("content", "").lower()
            # Simple relevance: contains key terms from expected answer
            if self._calculate_overlap(content, expected_lower) > 0.3:
                relevant.append(chunk)
                
        return relevant
    
    def _is_chunk_relevant(self, chunk: Dict, expected_answer: str) -> bool:
        """Check if a single chunk is relevant to expected answer."""
        content = chunk.get("content", "").lower()
        expected_lower = expected_answer.lower()
        return self._calculate_overlap(content, expected_lower) > 0.3
    
    def _calculate_confidence(self, chunks: List[Dict], response: str) -> float:
        """Calculate confidence score based on retrieval quality."""
        if not chunks:
            return 0.0
            
        # Factors for confidence
        num_sources = len(set(c.get("source", {}).get("filename", "") 
                            for c in chunks if c.get("source")))
        avg_similarity = np.mean([c.get("similarity", 0.5) for c in chunks])
        
        # More sources and higher similarity = higher confidence
        confidence = min(1.0, (num_sources / 3) * 0.5 + avg_similarity * 0.5)
        return confidence
    
    def _compare_to_ground_truth(
        self, 
        response: str, 
        expected: str
    ) -> Tuple[bool, float]:
        """Compare response to ground truth answer."""
        response_lower = response.lower()
        expected_lower = expected.lower()
        
        # Extract key facts/numbers from both
        response_facts = self._extract_key_facts(response_lower)
        expected_facts = self._extract_key_facts(expected_lower)
        
        if not expected_facts:
            return False, 0.0
            
        # Calculate overlap
        matches = sum(1 for fact in expected_facts if fact in response_lower)
        overlap = matches / len(expected_facts)
        
        # Consider it a match if >70% overlap
        matches_truth = overlap > 0.7
        
        return matches_truth, overlap
    
    def _calculate_factual_accuracy(self, response: str, expected: str) -> float:
        """Calculate factual accuracy score."""
        # Extract numerical values and key medical terms
        response_nums = self._extract_numbers(response)
        expected_nums = self._extract_numbers(expected)
        
        if not expected_nums:
            # No numbers to compare, use term overlap
            return self._calculate_overlap(response.lower(), expected.lower())
        
        # Check if numbers match
        correct_nums = sum(1 for num in expected_nums if num in response_nums)
        accuracy = correct_nums / len(expected_nums) if expected_nums else 0.0
        
        return accuracy
    
    def _extract_key_facts(self, text: str) -> List[str]:
        """Extract key medical facts from text."""
        import re
        facts = []
        
        # Extract dosages (e.g., "1mg", "50ml")
        dosages = re.findall(r'\d+\s*(?:mg|ml|mcg|g|kg|units?)', text)
        facts.extend(dosages)
        
        # Extract times (e.g., "90 minutes", "3 hours")
        times = re.findall(r'\d+\s*(?:hours?|minutes?|mins?|seconds?)', text)
        facts.extend(times)
        
        # Extract thresholds (e.g., ">2", "<70")
        thresholds = re.findall(r'[<>]=?\s*\d+(?:\.\d+)?', text)
        facts.extend(thresholds)
        
        return facts
    
    def _extract_numbers(self, text: str) -> List[str]:
        """Extract numerical values from text."""
        import re
        # Find all numbers with optional units
        numbers = re.findall(r'\d+(?:\.\d+)?(?:\s*\w+)?', text)
        return numbers
    
    def _calculate_overlap(self, text1: str, text2: str) -> float:
        """Calculate word overlap between two texts."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words2:
            return 0.0
            
        intersection = words1 & words2
        return len(intersection) / len(words2)
    
    def get_aggregate_metrics(self, query_type: Optional[str] = None) -> Dict[str, float]:
        """Get aggregated metrics for a query type or all queries."""
        if query_type:
            metrics_list = self.aggregated_metrics.get(query_type, [])
        else:
            metrics_list = self.metrics_history
            
        if not metrics_list:
            return {}
            
        return {
            "total_queries": len(metrics_list),
            "avg_precision": np.mean([m.precision_at_k for m in metrics_list]),
            "avg_recall": np.mean([m.recall_at_k for m in metrics_list]),
            "avg_mrr": np.mean([m.mrr for m in metrics_list]),
            "avg_chunks_retrieved": np.mean([m.chunks_retrieved for m in metrics_list]),
            "avg_response_time_ms": np.mean([m.response_time_ms for m in metrics_list]),
            "avg_confidence": np.mean([m.confidence_score for m in metrics_list]),
            "ground_truth_accuracy": np.mean([m.factual_accuracy for m in metrics_list]),
            "error_rate": sum(1 for m in metrics_list if m.has_error) / len(metrics_list)
        }
    
    def generate_report(self) -> str:
        """Generate a comprehensive metrics report."""
        report = []
        report.append("=" * 60)
        report.append("RETRIEVAL QUALITY METRICS REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Total Queries Evaluated: {len(self.metrics_history)}")
        report.append("")
        
        # Overall metrics
        overall = self.get_aggregate_metrics()
        if overall:
            report.append("OVERALL METRICS:")
            report.append("-" * 40)
            for key, value in overall.items():
                if isinstance(value, float):
                    report.append(f"  {key}: {value:.3f}")
                else:
                    report.append(f"  {key}: {value}")
            report.append("")
        
        # Per query type metrics
        report.append("METRICS BY QUERY TYPE:")
        report.append("-" * 40)
        for query_type in self.aggregated_metrics.keys():
            metrics = self.get_aggregate_metrics(query_type)
            report.append(f"\n{query_type}:")
            for key, value in metrics.items():
                if isinstance(value, float):
                    report.append(f"  {key}: {value:.3f}")
                else:
                    report.append(f"  {key}: {value}")
        
        return "\n".join(report)
    
    def save_metrics(self, filepath: str = "retrieval_metrics.json"):
        """Save metrics history to JSON file."""
        metrics_data = []
        for metric in self.metrics_history:
            metric_dict = asdict(metric)
            metric_dict["timestamp"] = metric_dict["timestamp"].isoformat()
            metrics_data.append(metric_dict)
            
        with open(filepath, 'w') as f:
            json.dump(metrics_data, f, indent=2)
    
    def identify_improvement_areas(self) -> List[str]:
        """Identify areas needing improvement based on metrics."""
        improvements = []
        overall = self.get_aggregate_metrics()
        
        if not overall:
            return ["No metrics collected yet"]
        
        # Check various thresholds
        if overall.get("avg_precision", 0) < 0.7:
            improvements.append("Low precision: Too many irrelevant chunks retrieved")
            
        if overall.get("avg_recall", 0) < 0.6:
            improvements.append("Low recall: Missing relevant chunks")
            
        if overall.get("avg_chunks_retrieved", 0) < 2:
            improvements.append("Too few chunks: Consider retrieving more context")
            
        if overall.get("avg_response_time_ms", 0) > 2000:
            improvements.append("Slow response time: Optimize retrieval pipeline")
            
        if overall.get("ground_truth_accuracy", 0) < 0.8:
            improvements.append("Low accuracy: Responses don't match ground truth well")
            
        if overall.get("error_rate", 0) > 0.1:
            improvements.append("High error rate: Too many failed queries")
            
        return improvements if improvements else ["System performing well!"]


# Convenience function for testing
def create_test_evaluator():
    """Create an evaluator instance for testing."""
    return RetrievalEvaluator()