#!/usr/bin/env python3
"""
Groundtruth Validation Framework for ED Bot v8
Validates medical response accuracy against known correct answers.
"""

import json
import re
import time
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import difflib
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a single test case."""
    test_id: str
    query: str
    category: str
    passed: bool
    score: float
    issues: List[str]
    response_data: Dict[str, Any]
    execution_time_ms: int
    confidence: float
    critical_values_correct: bool


@dataclass
class GroundtruthReport:
    """Complete groundtruth validation report."""
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    overall_accuracy: float
    category_scores: Dict[str, float]
    critical_failures: List[str]
    regression_issues: List[str]
    performance_issues: List[str]
    results: List[ValidationResult]


class GroundtruthValidator:
    """Validates ED Bot responses against groundtruth dataset."""
    
    def __init__(self, api_url: str = "http://localhost:8001/api/v1/query"):
        self.api_url = api_url
        self.project_root = Path(__file__).parent.parent.parent
        self.dataset_file = Path(__file__).parent / "groundtruth_dataset.json"
        self.dataset = self._load_dataset()
        
    def _load_dataset(self) -> Dict[str, Any]:
        """Load the groundtruth dataset."""
        if not self.dataset_file.exists():
            raise FileNotFoundError(f"Groundtruth dataset not found: {self.dataset_file}")
            
        with open(self.dataset_file) as f:
            return json.load(f)
    
    def validate_single_test(self, test_case: Dict[str, Any]) -> ValidationResult:
        """Validate a single test case against the API."""
        test_id = test_case["id"]
        query = test_case["query"]
        category = test_case["category"]
        expected = test_case["expected_response"]
        
        logger.info(f"Testing {test_id}: {query}")
        
        # Execute query
        start_time = time.time()
        
        try:
            response = requests.post(
                self.api_url,
                json={"query": query},
                timeout=10
            )
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                return ValidationResult(
                    test_id=test_id,
                    query=query,
                    category=category,
                    passed=False,
                    score=0.0,
                    issues=[f"API error: {response.status_code}"],
                    response_data={},
                    execution_time_ms=execution_time_ms,
                    confidence=0.0,
                    critical_values_correct=False
                )
                
            response_data = response.json()
            response_text = response_data.get("response", "").lower()
            confidence = response_data.get("confidence", 0.0)
            
        except Exception as e:
            return ValidationResult(
                test_id=test_id,
                query=query,
                category=category,
                passed=False,
                score=0.0,
                issues=[f"Request failed: {str(e)}"],
                response_data={},
                execution_time_ms=int((time.time() - start_time) * 1000),
                confidence=0.0,
                critical_values_correct=False
            )
        
        # Validate response
        issues = []
        score_components = []
        
        # 1. Check required content
        must_contain = expected.get("must_contain", [])
        contained_count = 0
        for required_text in must_contain:
            if required_text.lower() in response_text:
                contained_count += 1
            else:
                issues.append(f"Missing required text: '{required_text}'")
        
        content_score = contained_count / len(must_contain) if must_contain else 1.0
        score_components.append(("content", content_score, 0.4))
        
        # 2. Validate critical values
        critical_values_correct = True
        critical_values = expected.get("critical_values", {})
        if critical_values:
            correct_values = 0
            for key, expected_value in critical_values.items():
                if self._validate_critical_value(response_text, key, expected_value):
                    correct_values += 1
                else:
                    issues.append(f"Incorrect critical value for {key}: expected '{expected_value}'")
                    critical_values_correct = False
            
            critical_score = correct_values / len(critical_values)
            score_components.append(("critical", critical_score, 0.3))
        else:
            score_components.append(("critical", 1.0, 0.3))
        
        # 3. Check confidence threshold
        min_confidence = expected.get("confidence_min", 0.7)
        confidence_score = 1.0 if confidence >= min_confidence else confidence / min_confidence
        if confidence < min_confidence:
            issues.append(f"Low confidence: {confidence:.2f} < {min_confidence}")
        
        score_components.append(("confidence", confidence_score, 0.2))
        
        # 4. Check medications if specified
        medications = expected.get("medications", [])
        if medications:
            med_found = sum(1 for med in medications if med.lower() in response_text)
            med_score = med_found / len(medications)
            score_components.append(("medications", med_score, 0.1))
            
            if med_found < len(medications):
                missing_meds = [med for med in medications if med.lower() not in response_text]
                issues.append(f"Missing medications: {missing_meds}")
        else:
            score_components.append(("medications", 1.0, 0.1))
        
        # Calculate overall score
        overall_score = sum(score * weight for _, score, weight in score_components)
        
        # Determine if test passed
        passed = overall_score >= 0.8 and critical_values_correct and confidence >= min_confidence
        
        return ValidationResult(
            test_id=test_id,
            query=query,
            category=category,
            passed=passed,
            score=overall_score,
            issues=issues,
            response_data=response_data,
            execution_time_ms=execution_time_ms,
            confidence=confidence,
            critical_values_correct=critical_values_correct
        )
    
    def _validate_critical_value(self, response_text: str, key: str, expected_value: str) -> bool:
        """Validate a critical value exists in the response."""
        expected_clean = expected_value.lower().strip()
        
        # Handle different types of critical values
        if "pager" in key.lower() or "phone" in key.lower():
            # Extract phone numbers from response
            phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            phones = re.findall(phone_pattern, response_text)
            return any(expected_clean.replace("(", "").replace(")", "").replace("-", "") in 
                      phone.replace("(", "").replace(")", "").replace("-", "").replace(".", "").replace(" ", "") 
                      for phone in phones)
        
        elif "dose" in key.lower():
            # Check for dosage values
            return expected_clean in response_text or expected_clean.replace(" ", "") in response_text.replace(" ", "")
        
        elif "time" in key.lower():
            # Check for time values
            return expected_clean in response_text
        
        else:
            # General text matching
            return expected_clean in response_text
    
    def validate_all(self) -> GroundtruthReport:
        """Run validation on all test cases."""
        test_cases = self.dataset["test_cases"]
        results = []
        
        print(f"\n🧪 GROUNDTRUTH VALIDATION - {len(test_cases)} test cases")
        print("=" * 60)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"[{i:2d}/{len(test_cases)}] {test_case['id']: <8} {test_case['category']: <10} ", end="")
            
            result = self.validate_single_test(test_case)
            results.append(result)
            
            if result.passed:
                print(f"✅ {result.score:.2f}")
            else:
                print(f"❌ {result.score:.2f}")
                for issue in result.issues[:2]:  # Show first 2 issues
                    print(f"         └─ {issue}")
        
        # Generate report
        return self._generate_report(results)
    
    def _generate_report(self, results: List[ValidationResult]) -> GroundtruthReport:
        """Generate comprehensive validation report."""
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.passed)
        failed_tests = total_tests - passed_tests
        overall_accuracy = passed_tests / total_tests if total_tests > 0 else 0.0
        
        # Category breakdown
        category_scores = {}
        for category in set(r.category for r in results):
            cat_results = [r for r in results if r.category == category]
            cat_passed = sum(1 for r in cat_results if r.passed)
            category_scores[category] = cat_passed / len(cat_results) if cat_results else 0.0
        
        # Critical failures
        critical_failures = [
            f"{r.test_id}: {r.query}" 
            for r in results 
            if not r.critical_values_correct
        ]
        
        # Performance issues
        performance_issues = [
            f"{r.test_id}: {r.execution_time_ms}ms"
            for r in results
            if r.execution_time_ms > self.dataset.get("evaluation_metrics", {}).get("response_time_max_ms", 1500)
        ]
        
        # Regression check
        regression_issues = self._check_regressions(results)
        
        return GroundtruthReport(
            timestamp=datetime.now().isoformat(),
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            overall_accuracy=overall_accuracy,
            category_scores=category_scores,
            critical_failures=critical_failures,
            regression_issues=regression_issues,
            performance_issues=performance_issues,
            results=results
        )
    
    def _check_regressions(self, results: List[ValidationResult]) -> List[str]:
        """Check for regressions against known critical values."""
        regression_tests = self.dataset.get("regression_tests", [])
        regressions = []
        
        for reg_test in regression_tests:
            test_name = reg_test["test"]
            expected = reg_test["expected"].lower()
            is_critical = reg_test.get("critical", False)
            
            # Find matching results
            matching_results = []
            for result in results:
                if any(keyword in result.query.lower() for keyword in test_name.lower().split()):
                    if expected not in result.response_data.get("response", "").lower():
                        if is_critical:
                            regressions.append(f"CRITICAL: {test_name} - Expected '{expected}' not found")
                        else:
                            regressions.append(f"WARNING: {test_name} - Expected '{expected}' not found")
        
        return regressions
    
    def print_report(self, report: GroundtruthReport):
        """Print detailed validation report."""
        print("\n" + "=" * 60)
        print("📊 GROUNDTRUTH VALIDATION REPORT")
        print("=" * 60)
        
        # Overall metrics
        print(f"\n📈 OVERALL RESULTS:")
        print(f"  Tests Run: {report.total_tests}")
        print(f"  Passed: {report.passed_tests} ({report.overall_accuracy:.1%})")
        print(f"  Failed: {report.failed_tests}")
        
        # Category breakdown
        print(f"\n📋 CATEGORY BREAKDOWN:")
        for category, score in report.category_scores.items():
            icon = "✅" if score >= 0.8 else "⚠️" if score >= 0.6 else "❌"
            print(f"  {icon} {category: <12} {score:.1%}")
        
        # Critical failures
        if report.critical_failures:
            print(f"\n🚨 CRITICAL FAILURES ({len(report.critical_failures)}):")
            for failure in report.critical_failures:
                print(f"  • {failure}")
        
        # Regressions
        if report.regression_issues:
            print(f"\n⚠️  REGRESSIONS ({len(report.regression_issues)}):")
            for regression in report.regression_issues:
                print(f"  • {regression}")
        
        # Performance issues
        if report.performance_issues:
            print(f"\n🐌 PERFORMANCE ISSUES ({len(report.performance_issues)}):")
            for issue in report.performance_issues:
                print(f"  • {issue}")
        
        # Failed tests detail
        failed_results = [r for r in report.results if not r.passed]
        if failed_results:
            print(f"\n❌ FAILED TESTS DETAIL:")
            for result in failed_results:
                print(f"\n  {result.test_id} - {result.query}")
                print(f"    Score: {result.score:.2f}")
                print(f"    Confidence: {result.confidence:.2f}")
                for issue in result.issues:
                    print(f"    • {issue}")
        
        # Final assessment
        print("\n" + "=" * 60)
        if report.overall_accuracy >= 0.95:
            print("🎯 EXCELLENT: System meets production quality standards")
        elif report.overall_accuracy >= 0.8:
            print("👍 GOOD: System meets minimum accuracy requirements")
        elif report.overall_accuracy >= 0.6:
            print("⚠️  WARNING: System needs improvement before deployment")
        else:
            print("❌ CRITICAL: System not ready for deployment")
        
        print(f"📝 Report saved with timestamp: {report.timestamp}")
    
    def save_report(self, report: GroundtruthReport, filename: Optional[str] = None):
        """Save validation report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"groundtruth_report_{timestamp}.json"
        
        report_file = Path(__file__).parent / filename
        
        # Convert dataclass to dict for JSON serialization
        report_dict = {
            "timestamp": report.timestamp,
            "total_tests": report.total_tests,
            "passed_tests": report.passed_tests,
            "failed_tests": report.failed_tests,
            "overall_accuracy": report.overall_accuracy,
            "category_scores": report.category_scores,
            "critical_failures": report.critical_failures,
            "regression_issues": report.regression_issues,
            "performance_issues": report.performance_issues,
            "results": [
                {
                    "test_id": r.test_id,
                    "query": r.query,
                    "category": r.category,
                    "passed": r.passed,
                    "score": r.score,
                    "issues": r.issues,
                    "execution_time_ms": r.execution_time_ms,
                    "confidence": r.confidence,
                    "critical_values_correct": r.critical_values_correct
                }
                for r in report.results
            ]
        }
        
        with open(report_file, "w") as f:
            json.dump(report_dict, f, indent=2)
        
        return report_file


def main():
    """Run groundtruth validation."""
    print("\n🏥 ED BOT v8 - GROUNDTRUTH VALIDATOR")
    print("Validating medical response accuracy...")
    
    validator = GroundtruthValidator()
    
    try:
        report = validator.validate_all()
        validator.print_report(report)
        
        # Save report
        report_file = validator.save_report(report)
        print(f"\n📄 Full report saved to: {report_file}")
        
        # Exit code based on results
        if report.overall_accuracy >= 0.8 and not report.critical_failures:
            exit(0)  # Success
        else:
            exit(1)  # Failure
            
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()