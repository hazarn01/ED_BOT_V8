#!/usr/bin/env python3
"""
Medical Query Relevance Testing Suite

This comprehensive test suite validates that medical queries return clinically relevant, 
accurate information. It catches quality regressions that technical tests miss.

Key Features:
- Medical domain expertise validation
- Content relevance scoring
- Regression detection against baseline
- Incremental enhancement testing
"""

import json
import logging
import requests
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MedicalTestCase:
    """A medical query test case with expected outcomes."""
    query: str
    query_type: str
    expected_keywords: List[str]  # Must contain these medical terms
    forbidden_keywords: List[str]  # Must NOT contain these terms
    min_response_length: int
    expected_confidence: float
    clinical_context: str  # What medical situation this addresses
    
@dataclass
class RelevanceResult:
    """Results of relevance analysis."""
    relevance_score: float  # 0.0 to 1.0
    keyword_matches: int
    forbidden_matches: int
    response_length: int
    clinical_accuracy: str  # "high", "medium", "low", "dangerous"
    issues_found: List[str]

class MedicalRelevanceTester:
    """Comprehensive medical query relevance testing."""
    
    def __init__(self, api_base_url: str = "http://localhost:8001"):
        self.api_base_url = api_base_url
        self.test_cases = self._load_medical_test_cases()
        self.baseline_results = {}
        
    def _load_medical_test_cases(self) -> List[MedicalTestCase]:
        """Define comprehensive medical test cases."""
        return [
            # PROTOCOL QUERIES - Critical medical procedures
            MedicalTestCase(
                query="what is the STEMI protocol",
                query_type="protocol", 
                expected_keywords=["STEMI", "protocol", "pager", "917", "cath lab", "cardiology"],
                forbidden_keywords=["enhancement", "processor", "development", "implementation"],
                min_response_length=200,
                expected_confidence=0.9,
                clinical_context="Emergency cardiac intervention"
            ),
            
            MedicalTestCase(
                query="ED sepsis pathway",
                query_type="protocol",
                expected_keywords=["sepsis", "lactate", "antibiotics", "severe sepsis", "shock"],
                forbidden_keywords=["pediatric", "triage", "psychiatric", "enhancement"],
                min_response_length=200,
                expected_confidence=0.9,
                clinical_context="Sepsis management in emergency department"
            ),
            
            # FORM QUERIES - Medical documentation
            MedicalTestCase(
                query="blood transfusion form",
                query_type="form",
                expected_keywords=["transfusion", "consent", "blood", "form", "Epic"],
                forbidden_keywords=["sepsis", "pediatric", "triage", "STEMI"],
                min_response_length=100,
                expected_confidence=0.8,
                clinical_context="Blood product administration documentation"
            ),
            
            # CONTACT QUERIES - On-call physicians
            MedicalTestCase(
                query="who is on call for cardiology",
                query_type="contact",
                expected_keywords=["cardiology", "on call", "pager", "917", "STEMI"],
                forbidden_keywords=["sepsis", "form", "protocol", "enhancement"],
                min_response_length=100,
                expected_confidence=0.9,
                clinical_context="Emergency cardiac consultation"
            ),
            
            # DOSAGE QUERIES - Medication information
            MedicalTestCase(
                query="epinephrine dose anaphylaxis",
                query_type="dosage",
                expected_keywords=["epinephrine", "anaphylaxis", "dose", "mg", "IM", "adult"],
                forbidden_keywords=["sepsis", "STEMI", "form", "pediatric"],
                min_response_length=100,
                expected_confidence=0.8,
                clinical_context="Emergency anaphylaxis treatment"
            ),
            
            # CRITERIA QUERIES - Clinical decision support
            MedicalTestCase(
                query="criteria for severe sepsis",
                query_type="criteria",
                expected_keywords=["severe sepsis", "lactate", "criteria", "2", "mmol", "threshold"],
                forbidden_keywords=["triage", "psychiatric", "enhancement", "pediatric"],
                min_response_length=100,
                expected_confidence=0.8,
                clinical_context="Sepsis severity assessment"
            ),
            
            # EDGE CASE QUERIES - Test robustness
            MedicalTestCase(
                query="L&D clearance",
                query_type="summary",
                expected_keywords=["labor", "delivery", "clearance", "obstetric"],
                forbidden_keywords=["dysphagia", "ollama", "enhancement", "sepsis"],
                min_response_length=50,
                expected_confidence=0.5,
                clinical_context="Obstetric consultation clearance"
            ),
            
            MedicalTestCase(
                query="hypoglycemia treatment",
                query_type="dosage",
                expected_keywords=["hypoglycemia", "glucose", "D50", "glucagon", "treatment"],
                forbidden_keywords=["sepsis", "STEMI", "form", "enhancement"],
                min_response_length=100,
                expected_confidence=0.8,
                clinical_context="Emergency glucose management"
            )
        ]
    
    def run_comprehensive_test(self) -> Dict[str, any]:
        """Run all medical relevance tests and return comprehensive results."""
        logger.info("🧪 Starting Comprehensive Medical Relevance Testing")
        logger.info("=" * 60)
        
        results = {
            "timestamp": time.time(),
            "total_tests": len(self.test_cases),
            "passed_tests": 0,
            "failed_tests": 0,
            "critical_failures": 0,
            "overall_score": 0.0,
            "test_results": [],
            "summary": {}
        }
        
        for i, test_case in enumerate(self.test_cases, 1):
            logger.info(f"\n🔍 Test {i}/{len(self.test_cases)}: {test_case.query}")
            
            # Execute query
            response_data = self._execute_query(test_case.query)
            if not response_data:
                results["failed_tests"] += 1
                results["test_results"].append({
                    "test_case": test_case,
                    "status": "FAILED",
                    "error": "API request failed"
                })
                continue
            
            # Analyze relevance
            relevance = self._analyze_relevance(test_case, response_data)
            
            # Determine test outcome
            test_result = self._evaluate_test_result(test_case, relevance, response_data)
            results["test_results"].append(test_result)
            
            if test_result["status"] == "PASSED":
                results["passed_tests"] += 1
            elif test_result["status"] == "CRITICAL_FAILURE":
                results["critical_failures"] += 1
                results["failed_tests"] += 1
            else:
                results["failed_tests"] += 1
            
            # Log result
            status_emoji = "✅" if test_result["status"] == "PASSED" else "❌" if test_result["status"] == "CRITICAL_FAILURE" else "⚠️"
            logger.info(f"{status_emoji} {test_result['status']}: {relevance.relevance_score:.2f} relevance")
            if test_result.get("issues"):
                for issue in test_result["issues"]:
                    logger.warning(f"   ⚠️  {issue}")
        
        # Calculate overall metrics
        results["overall_score"] = results["passed_tests"] / results["total_tests"]
        results["summary"] = self._generate_summary(results)
        
        logger.info(f"\n🎯 TEST SUMMARY")
        logger.info(f"Overall Score: {results['overall_score']:.1%}")
        logger.info(f"Passed: {results['passed_tests']}/{results['total_tests']}")
        logger.info(f"Critical Failures: {results['critical_failures']}")
        
        return results
    
    def _execute_query(self, query: str) -> Optional[Dict]:
        """Execute a query against the medical API."""
        try:
            response = requests.post(
                f"{self.api_base_url}/api/v1/query",
                json={"query": query},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API request failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return None
    
    def _analyze_relevance(self, test_case: MedicalTestCase, response_data: Dict) -> RelevanceResult:
        """Analyze the relevance of a response to the medical query."""
        response_text = response_data.get("response", "").lower()
        
        # Count keyword matches
        expected_matches = sum(1 for kw in test_case.expected_keywords 
                             if kw.lower() in response_text)
        forbidden_matches = sum(1 for kw in test_case.forbidden_keywords 
                              if kw.lower() in response_text)
        
        # Calculate relevance score
        expected_ratio = expected_matches / len(test_case.expected_keywords) if test_case.expected_keywords else 0
        forbidden_penalty = forbidden_matches * 0.2  # Each forbidden word reduces score by 20%
        
        relevance_score = max(0.0, expected_ratio - forbidden_penalty)
        
        # Assess clinical accuracy
        clinical_accuracy = self._assess_clinical_accuracy(
            test_case, response_data, expected_matches, forbidden_matches
        )
        
        # Identify issues
        issues = []
        if expected_matches < len(test_case.expected_keywords) * 0.5:
            issues.append(f"Missing key medical terms: expected {len(test_case.expected_keywords)}, found {expected_matches}")
        
        if forbidden_matches > 0:
            issues.append(f"Contains irrelevant content: {forbidden_matches} forbidden terms found")
        
        response_length = len(response_data.get("response", ""))
        if response_length < test_case.min_response_length:
            issues.append(f"Response too short: {response_length} chars (minimum: {test_case.min_response_length})")
        
        return RelevanceResult(
            relevance_score=relevance_score,
            keyword_matches=expected_matches,
            forbidden_matches=forbidden_matches,
            response_length=response_length,
            clinical_accuracy=clinical_accuracy,
            issues_found=issues
        )
    
    def _assess_clinical_accuracy(self, test_case: MedicalTestCase, response_data: Dict, 
                                expected_matches: int, forbidden_matches: int) -> str:
        """Assess the clinical accuracy level of the response."""
        response = response_data.get("response", "")
        
        # Critical failure conditions
        if forbidden_matches > 2:
            return "dangerous"  # Response contains too much irrelevant medical info
        
        if expected_matches == 0:
            return "dangerous"  # Response has no relevant medical content
        
        # Check for specific dangerous combinations
        if "STEMI" in test_case.query and "sepsis" in response.lower() and "STEMI" not in response:
            return "dangerous"  # Wrong medical protocol could harm patient
        
        # Quality assessment
        confidence = response_data.get("confidence", 0.0)
        query_type_match = response_data.get("query_type", "") == test_case.query_type
        
        if expected_matches >= len(test_case.expected_keywords) * 0.8 and confidence >= 0.8 and query_type_match:
            return "high"
        elif expected_matches >= len(test_case.expected_keywords) * 0.5 and confidence >= 0.6:
            return "medium"
        else:
            return "low"
    
    def _evaluate_test_result(self, test_case: MedicalTestCase, relevance: RelevanceResult, 
                            response_data: Dict) -> Dict[str, any]:
        """Evaluate whether a test passed or failed."""
        result = {
            "test_case": {
                "query": test_case.query,
                "clinical_context": test_case.clinical_context,
                "query_type": test_case.query_type
            },
            "relevance": relevance,
            "response_data": response_data,
            "issues": relevance.issues_found
        }
        
        # Determine status
        if relevance.clinical_accuracy == "dangerous":
            result["status"] = "CRITICAL_FAILURE"
            result["reason"] = "Clinically dangerous response"
        elif relevance.relevance_score >= 0.7 and relevance.clinical_accuracy in ["high", "medium"]:
            result["status"] = "PASSED"
            result["reason"] = "Clinically relevant and accurate"
        elif relevance.relevance_score >= 0.4:
            result["status"] = "WARNING"
            result["reason"] = "Marginally relevant but needs improvement"
        else:
            result["status"] = "FAILED"
            result["reason"] = "Insufficient relevance to medical query"
        
        return result
    
    def _generate_summary(self, results: Dict) -> Dict[str, any]:
        """Generate a summary of test results."""
        critical_failures = [r for r in results["test_results"] if r["status"] == "CRITICAL_FAILURE"]
        warnings = [r for r in results["test_results"] if r["status"] == "WARNING"]
        
        return {
            "quality_assessment": self._assess_overall_quality(results["overall_score"], len(critical_failures)),
            "critical_issues": [r["reason"] for r in critical_failures],
            "improvement_areas": [r["reason"] for r in warnings],
            "recommendation": self._generate_recommendation(results["overall_score"], len(critical_failures))
        }
    
    def _assess_overall_quality(self, score: float, critical_count: int) -> str:
        """Assess overall system quality."""
        if critical_count > 0:
            return "UNSAFE - Contains dangerous medical misinformation"
        elif score >= 0.9:
            return "EXCELLENT - High clinical accuracy"
        elif score >= 0.7:
            return "GOOD - Acceptable for clinical use with monitoring"
        elif score >= 0.5:
            return "POOR - Requires significant improvement"
        else:
            return "FAILING - Not suitable for medical use"
    
    def _generate_recommendation(self, score: float, critical_count: int) -> str:
        """Generate improvement recommendations."""
        if critical_count > 0:
            return "IMMEDIATE ACTION REQUIRED: Disable system until dangerous responses are fixed"
        elif score < 0.7:
            return "System needs improvement before clinical deployment"
        elif score < 0.9:
            return "System acceptable but monitor for quality degradation"
        else:
            return "System performing well, continue monitoring"
    
    def save_results(self, results: Dict, filename: str = None):
        """Save test results to file."""
        if not filename:
            timestamp = int(time.time())
            filename = f"medical_relevance_test_{timestamp}.json"
        
        output_path = Path("tests/quality/results") / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"📊 Results saved to: {output_path}")
    
    def compare_with_baseline(self, current_results: Dict, baseline_file: str = None) -> Dict:
        """Compare current results with baseline to detect regressions."""
        if not baseline_file:
            logger.info("No baseline provided, skipping regression analysis")
            return {}
        
        try:
            with open(baseline_file, 'r') as f:
                baseline = json.load(f)
            
            regression_analysis = {
                "score_change": current_results["overall_score"] - baseline["overall_score"],
                "critical_failures_change": current_results["critical_failures"] - baseline["critical_failures"],
                "regressions": [],
                "improvements": []
            }
            
            # Detailed comparison would go here
            return regression_analysis
            
        except Exception as e:
            logger.error(f"Baseline comparison failed: {e}")
            return {}

def main():
    """Run the comprehensive medical relevance test suite."""
    tester = MedicalRelevanceTester()
    results = tester.run_comprehensive_test()
    tester.save_results(results)
    
    # Print final assessment
    print(f"\n🏥 MEDICAL SYSTEM QUALITY ASSESSMENT")
    print(f"=" * 50)
    print(f"Overall Quality: {results['summary']['quality_assessment']}")
    print(f"Recommendation: {results['summary']['recommendation']}")
    
    if results["critical_failures"] > 0:
        print(f"\n🚨 CRITICAL MEDICAL SAFETY ISSUES FOUND")
        exit(1)
    
    if results["overall_score"] < 0.7:
        print(f"\n⚠️  QUALITY BELOW MEDICAL STANDARDS")
        exit(1)
    
    print(f"\n✅ Medical system quality acceptable")

if __name__ == "__main__":
    main()