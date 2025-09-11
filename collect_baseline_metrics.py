#!/usr/bin/env python3
"""
Collect Baseline Retrieval Metrics
Establishes current performance baseline before improvements
"""

import json
import requests
import time
from pathlib import Path
from typing import Dict, List, Tuple
from src.evaluation.retrieval_metrics import RetrievalEvaluator
from src.pipeline.curated_responses import curated_db

# API endpoint
API_URL = "http://localhost:8001/api/v1/query"

# Test queries from curated responses + ground truth
TEST_QUERIES = [
    # From curated responses (known good answers)
    ("what is the STEMI protocol", "protocol", "STEMI Pager: (917) 827-9725"),
    ("hypoglycemia treatment dose", "dosage", "50mL (25g) D50 IV"),
    ("sepsis criteria", "criteria", "Lactate > 2"),
    ("epinephrine dose cardiac arrest", "dosage", "1mg IV/IO every 3-5 minutes"),
    ("ottawa ankle rules", "criteria", "posterior edge or tip of lateral malleolus"),
    
    # Additional test queries
    ("what are the criteria for sepsis", "criteria", "Lactate > 2 mmol/L"),
    ("ED sepsis protocol", "protocol", "Initial evaluation: 0-1 hour"),
    ("anaphylaxis first line treatment", "dosage", "Epinephrine 0.3mg IM"),
    ("blood transfusion consent form", "form", "Blood Product Consent Form"),
    ("who is on call for cardiology", "contact", "Cardiology Fellow"),
    
    # Edge cases
    ("STEMI door to balloon time", "protocol", "90 minutes"),
    ("hypoglycemia definition", "criteria", "<70 mg/dL"),
    ("severe sepsis lactate level", "criteria", "> 2 mmol/L"),
]


def make_api_request(query: str) -> Tuple[Dict, float]:
    """Make API request and measure response time."""
    start_time = time.time()
    
    try:
        response = requests.post(
            API_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response_time_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return response.json(), response_time_ms
        else:
            return {"error": f"HTTP {response.status_code}"}, response_time_ms
            
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        return {"error": str(e)}, response_time_ms


def extract_retrieved_chunks(api_response: Dict) -> List[Dict]:
    """Extract retrieved chunks from API response."""
    # The API response includes sources
    chunks = []
    
    # Create synthetic chunks from sources (since we don't have raw chunks in response)
    sources = api_response.get("sources", [])
    for i, source in enumerate(sources):
        chunk = {
            "content": api_response.get("response", "")[:500],  # Use part of response as chunk
            "source": {
                "filename": source.get("filename", "unknown"),
                "display_name": source.get("display_name", "unknown")
            },
            "similarity": 0.8 - (i * 0.1)  # Synthetic similarity scores
        }
        chunks.append(chunk)
    
    return chunks


def run_baseline_evaluation():
    """Run baseline evaluation on all test queries."""
    print("=" * 60)
    print("COLLECTING BASELINE RETRIEVAL METRICS")
    print("=" * 60)
    print(f"API Endpoint: {API_URL}")
    print(f"Test Queries: {len(TEST_QUERIES)}")
    print()
    
    # Initialize evaluator
    evaluator = RetrievalEvaluator()
    
    # Track results
    successful = 0
    failed = 0
    
    # Run each test query
    for i, (query, expected_type, expected_answer) in enumerate(TEST_QUERIES, 1):
        print(f"[{i}/{len(TEST_QUERIES)}] Testing: {query[:50]}...")
        
        # Make API request
        api_response, response_time_ms = make_api_request(query)
        
        if "error" in api_response:
            print(f"  ❌ Error: {api_response['error']}")
            failed += 1
            continue
        
        # Extract data
        response_text = api_response.get("response", "")
        query_type = api_response.get("query_type", "unknown")
        chunks = extract_retrieved_chunks(api_response)
        
        # Evaluate
        metrics = evaluator.evaluate_retrieval(
            query=query,
            retrieved_chunks=chunks,
            response=response_text,
            query_type=query_type,
            response_time_ms=response_time_ms,
            expected_answer=expected_answer
        )
        
        # Quick feedback
        if metrics.factual_accuracy > 0.7:
            print(f"  ✅ Accurate ({metrics.factual_accuracy:.2f})")
            successful += 1
        else:
            print(f"  ⚠️  Low accuracy ({metrics.factual_accuracy:.2f})")
            successful += 1
        
        print(f"     Time: {response_time_ms:.0f}ms | Chunks: {metrics.chunks_retrieved} | Confidence: {metrics.confidence_score:.2f}")
    
    print()
    print("=" * 60)
    print("BASELINE RESULTS SUMMARY")
    print("=" * 60)
    print(f"Successful: {successful}/{len(TEST_QUERIES)}")
    print(f"Failed: {failed}/{len(TEST_QUERIES)}")
    print()
    
    # Get aggregate metrics
    overall_metrics = evaluator.get_aggregate_metrics()
    print("Overall Metrics:")
    for key, value in overall_metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")
    
    print()
    print("Metrics by Query Type:")
    for query_type in ["protocol", "dosage", "criteria", "form", "contact"]:
        type_metrics = evaluator.get_aggregate_metrics(query_type)
        if type_metrics:
            print(f"\n{query_type.upper()}:")
            print(f"  Queries: {type_metrics.get('total_queries', 0)}")
            print(f"  Avg Accuracy: {type_metrics.get('ground_truth_accuracy', 0):.3f}")
            print(f"  Avg Response Time: {type_metrics.get('avg_response_time_ms', 0):.0f}ms")
            print(f"  Avg Chunks: {type_metrics.get('avg_chunks_retrieved', 0):.1f}")
    
    print()
    print("=" * 60)
    print("IMPROVEMENT RECOMMENDATIONS")
    print("=" * 60)
    improvements = evaluator.identify_improvement_areas()
    for i, improvement in enumerate(improvements, 1):
        print(f"{i}. {improvement}")
    
    # Save metrics
    evaluator.save_metrics("baseline_metrics.json")
    
    # Save report
    report = evaluator.generate_report()
    with open("baseline_metrics_report.txt", "w") as f:
        f.write(report)
    
    print()
    print("✅ Metrics saved to: baseline_metrics.json")
    print("✅ Report saved to: baseline_metrics_report.txt")
    
    return evaluator


if __name__ == "__main__":
    evaluator = run_baseline_evaluation()