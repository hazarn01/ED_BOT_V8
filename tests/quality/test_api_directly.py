"""
Direct API Testing - Test actual API responses to validate quality
PRP-48: Test the real system end-to-end
"""

import requests
import json
from typing import Dict, Any
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

API_URL = "http://localhost:8001/api/v1/query"

def test_query(query: str) -> Dict[str, Any]:
    """Test a single query against the API."""
    response = requests.post(
        API_URL,
        json={"query": query},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"HTTP {response.status_code}: {response.text}"}

def analyze_response(query: str, response: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the quality of a response."""
    analysis = {
        "query": query,
        "has_response": bool(response.get("response")),
        "response_length": len(response.get("response", "")),
        "has_sources": len(response.get("sources", [])) > 0,
        "source_count": len(response.get("sources", [])),
        "confidence": response.get("confidence", 0),
        "query_type": response.get("query_type", "unknown"),
        "has_real_content": response.get("has_real_content", False)
    }
    
    # Check for template responses
    template_phrases = [
        "Available in Epic",
        "At nursing station",
        "Contact through operator",
        "Most forms available"
    ]
    
    response_text = response.get("response", "").lower()
    analysis["is_template"] = any(phrase.lower() in response_text for phrase in template_phrases)
    
    # Check for real medical content
    medical_indicators = ["mg", "ml", "dose", "protocol", "lactate", "mcg", "units"]
    analysis["has_medical_terms"] = any(term in response_text for term in medical_indicators)
    
    # Overall quality score
    quality_score = 0
    if analysis["has_response"]:
        quality_score += 20
    if analysis["response_length"] > 200:
        quality_score += 20
    if analysis["has_sources"]:
        quality_score += 20
    if not analysis["is_template"]:
        quality_score += 20
    if analysis["has_medical_terms"]:
        quality_score += 20
    
    analysis["quality_score"] = quality_score
    
    return analysis

def main():
    """Test key queries against the API."""
    
    test_queries = [
        "what is the STEMI protocol",
        "standard levophed dosing",
        "pediatric epinephrine dose",
        "blood transfusion form",
        "sepsis lactate criteria",
        "RETU chest pain pathway",
        "hypoglycemia treatment"
    ]
    
    print("=" * 80)
    print("🔍 DIRECT API TESTING")
    print("=" * 80)
    print(f"Testing API at: {API_URL}\n")
    
    results = []
    for query in test_queries:
        print(f"Testing: {query}")
        
        # Get response from API
        response = test_query(query)
        
        if "error" in response:
            print(f"  ❌ Error: {response['error']}")
            continue
        
        # Analyze response
        analysis = analyze_response(query, response)
        results.append(analysis)
        
        # Print summary
        status = "✅" if analysis["quality_score"] >= 60 else "❌"
        print(f"  {status} Quality: {analysis['quality_score']}/100")
        print(f"     Type: {analysis['query_type']}")
        print(f"     Sources: {analysis['source_count']}")
        print(f"     Length: {analysis['response_length']} chars")
        print(f"     Template: {'Yes' if analysis['is_template'] else 'No'}")
        print(f"     Medical: {'Yes' if analysis['has_medical_terms'] else 'No'}")
        
        # Show response preview
        response_text = response.get("response", "")[:200]
        if response_text:
            print(f"     Preview: {response_text}...")
        print()
    
    # Overall summary
    passing = sum(1 for r in results if r["quality_score"] >= 60)
    total = len(results)
    
    print("=" * 80)
    print(f"📊 OVERALL: {passing}/{total} queries with acceptable quality")
    print("=" * 80)
    
    # Detailed issues
    if passing < total:
        print("\n⚠️ QUALITY ISSUES:")
        for result in results:
            if result["quality_score"] < 60:
                print(f"\n❌ {result['query']} (Score: {result['quality_score']}/100)")
                if result["is_template"]:
                    print("   - Using template response instead of real content")
                if not result["has_medical_terms"]:
                    print("   - Missing medical terminology")
                if result["response_length"] < 200:
                    print("   - Response too short")
                if not result["has_sources"]:
                    print("   - No sources provided")
    
    # Save detailed report
    with open("api_quality_report.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n📄 Detailed report saved to api_quality_report.json")

if __name__ == "__main__":
    main()