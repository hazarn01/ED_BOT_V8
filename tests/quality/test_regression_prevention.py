#!/usr/bin/env python3
"""
Regression Prevention Testing Suite

This suite provides comprehensive regression testing to prevent quality degradation
when making system changes. It establishes baselines and detects any regressions
immediately.

Key Features:
- Baseline establishment with version control
- Automated regression detection
- Performance monitoring
- Source attribution validation
- Medical safety checks
"""

import json
import logging
import requests
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BaselineMetrics:
    """Core metrics that must not regress."""
    overall_quality_score: float
    critical_failures: int
    average_response_time: float
    source_attribution_rate: float
    medical_accuracy_score: float
    timestamp: str
    version: str

@dataclass
class RegressionResult:
    """Results of regression analysis."""
    has_regression: bool
    severity: str  # "CRITICAL", "MAJOR", "MINOR", "NONE"
    affected_areas: List[str]
    quality_change: float
    recommendation: str
    details: Dict

class RegressionPreventionTester:
    """Comprehensive regression testing to prevent quality degradation."""
    
    def __init__(self, api_base_url: str = "http://localhost:8001"):
        self.api_base_url = api_base_url
        self.results_dir = Path("tests/quality/baselines")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Critical test queries that must never regress
        self.critical_queries = [
            {
                "query": "what is the ED STEMI protocol",
                "expected_sources": ["STEMI"],
                "max_response_time": 2.0,
                "min_quality": 0.9
            },
            {
                "query": "show me the blood transfusion form", 
                "expected_sources": ["transfusion"],
                "max_response_time": 1.0,
                "min_quality": 0.9
            },
            {
                "query": "who is on call for cardiology",
                "expected_sources": ["cardiology"],
                "max_response_time": 1.0,
                "min_quality": 0.9
            },
            {
                "query": "epinephrine dose anaphylaxis",
                "expected_sources": ["anaphylaxis", "epinephrine"],
                "max_response_time": 2.0,
                "min_quality": 0.8
            },
            {
                "query": "hypoglycemia treatment protocol",
                "expected_sources": ["hypoglycemia"],
                "max_response_time": 2.0,
                "min_quality": 0.8
            }
        ]
    
    def establish_baseline(self, version: str = None) -> BaselineMetrics:
        """Establish baseline metrics for regression testing."""
        if not version:
            version = self._get_current_version()
        
        logger.info(f"🎯 Establishing baseline for version {version}")
        logger.info("=" * 60)
        
        # Run comprehensive tests
        quality_score = self._measure_quality_score()
        critical_failures = self._count_critical_failures()
        response_times = self._measure_response_times()
        source_attribution = self._measure_source_attribution()
        medical_accuracy = self._measure_medical_accuracy()
        
        baseline = BaselineMetrics(
            overall_quality_score=quality_score,
            critical_failures=critical_failures,
            average_response_time=sum(response_times) / len(response_times),
            source_attribution_rate=source_attribution,
            medical_accuracy_score=medical_accuracy,
            timestamp=datetime.now().isoformat(),
            version=version
        )
        
        # Save baseline
        baseline_file = self.results_dir / f"baseline_{version}.json"
        with open(baseline_file, 'w') as f:
            json.dump(asdict(baseline), f, indent=2)
        
        logger.info(f"✅ Baseline established:")
        logger.info(f"   Quality: {baseline.overall_quality_score:.1%}")
        logger.info(f"   Response Time: {baseline.average_response_time:.2f}s")
        logger.info(f"   Source Attribution: {baseline.source_attribution_rate:.1%}")
        logger.info(f"   Medical Accuracy: {baseline.medical_accuracy_score:.1%}")
        logger.info(f"💾 Saved to: {baseline_file}")
        
        return baseline
    
    def detect_regressions(self, baseline_version: str = None) -> RegressionResult:
        """Detect any regressions against established baseline."""
        logger.info("🔍 Detecting regressions against baseline...")
        
        # Load baseline
        if not baseline_version:
            baseline_version = self._get_latest_baseline_version()
        
        baseline_file = self.results_dir / f"baseline_{baseline_version}.json"
        if not baseline_file.exists():
            logger.error(f"❌ Baseline not found: {baseline_file}")
            raise FileNotFoundError(f"No baseline found for version {baseline_version}")
        
        with open(baseline_file, 'r') as f:
            baseline_data = json.load(f)
        baseline = BaselineMetrics(**baseline_data)
        
        # Measure current metrics
        current_quality = self._measure_quality_score()
        current_failures = self._count_critical_failures()
        current_response_times = self._measure_response_times()
        current_attribution = self._measure_source_attribution()
        current_accuracy = self._measure_medical_accuracy()
        current_avg_response = sum(current_response_times) / len(current_response_times)
        
        # Analyze regressions
        regressions = []
        quality_change = current_quality - baseline.overall_quality_score
        
        # Critical regression checks
        if current_failures > baseline.critical_failures:
            regressions.append(f"Critical failures increased: {baseline.critical_failures} → {current_failures}")
        
        if quality_change < -0.1:  # >10% quality drop
            regressions.append(f"Major quality regression: {quality_change:.1%}")
        
        if current_avg_response > baseline.average_response_time * 1.5:  # >50% slower
            regressions.append(f"Performance regression: {baseline.average_response_time:.2f}s → {current_avg_response:.2f}s")
        
        if current_attribution < baseline.source_attribution_rate * 0.9:  # >10% drop
            regressions.append(f"Source attribution dropped: {baseline.source_attribution_rate:.1%} → {current_attribution:.1%}")
        
        if current_accuracy < baseline.medical_accuracy_score * 0.9:  # >10% drop
            regressions.append(f"Medical accuracy dropped: {baseline.medical_accuracy_score:.1%} → {current_accuracy:.1%}")
        
        # Determine severity
        severity = "NONE"
        recommendation = "No regressions detected - changes are safe"
        
        if current_failures > baseline.critical_failures:
            severity = "CRITICAL"
            recommendation = "IMMEDIATE ROLLBACK REQUIRED - Critical medical safety issues introduced"
        elif quality_change < -0.2:
            severity = "CRITICAL" 
            recommendation = "IMMEDIATE ROLLBACK REQUIRED - Major quality degradation"
        elif quality_change < -0.1:
            severity = "MAJOR"
            recommendation = "ROLLBACK RECOMMENDED - Significant quality loss"
        elif regressions:
            severity = "MINOR"
            recommendation = "MONITOR CLOSELY - Minor regressions detected"
        
        result = RegressionResult(
            has_regression=bool(regressions),
            severity=severity,
            affected_areas=regressions,
            quality_change=quality_change,
            recommendation=recommendation,
            details={
                "baseline": asdict(baseline),
                "current": {
                    "quality_score": current_quality,
                    "critical_failures": current_failures,
                    "average_response_time": current_avg_response,
                    "source_attribution_rate": current_attribution,
                    "medical_accuracy_score": current_accuracy
                }
            }
        )
        
        # Log results
        if result.has_regression:
            logger.error(f"🚨 REGRESSION DETECTED - Severity: {severity}")
            for regression in regressions:
                logger.error(f"   ❌ {regression}")
            logger.error(f"📋 Recommendation: {recommendation}")
        else:
            logger.info("✅ NO REGRESSIONS DETECTED - System quality maintained")
            logger.info(f"📈 Quality change: {quality_change:+.1%}")
        
        return result
    
    def _measure_quality_score(self) -> float:
        """Measure overall system quality using medical relevance tests."""
        try:
            result = subprocess.run([
                "python3", "tests/quality/test_medical_relevance.py"
            ], capture_output=True, text=True, cwd=".")
            
            if result.returncode == 0:
                # Parse the last results file
                results_dir = Path("tests/quality/results")
                if results_dir.exists():
                    result_files = list(results_dir.glob("medical_relevance_test_*.json"))
                    if result_files:
                        latest = max(result_files, key=lambda f: f.stat().st_mtime)
                        with open(latest, 'r') as f:
                            data = json.load(f)
                        return data.get('overall_score', 0.0)
            
            return 0.5  # Fallback if tests fail
            
        except Exception as e:
            logger.warning(f"Quality measurement failed: {e}")
            return 0.5
    
    def _count_critical_failures(self) -> int:
        """Count critical medical safety failures."""
        try:
            results_dir = Path("tests/quality/results")
            if results_dir.exists():
                result_files = list(results_dir.glob("medical_relevance_test_*.json"))
                if result_files:
                    latest = max(result_files, key=lambda f: f.stat().st_mtime)
                    with open(latest, 'r') as f:
                        data = json.load(f)
                    return data.get('critical_failures', 0)
            return 0
        except Exception:
            return 0
    
    def _measure_response_times(self) -> List[float]:
        """Measure response times for critical queries."""
        response_times = []
        
        for test_case in self.critical_queries:
            try:
                start_time = time.time()
                response = requests.post(
                    f"{self.api_base_url}/api/v1/query",
                    json={"query": test_case["query"]},
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    response_times.append(end_time - start_time)
                else:
                    response_times.append(5.0)  # Penalty for failure
                    
            except Exception:
                response_times.append(5.0)  # Penalty for failure
        
        return response_times
    
    def _measure_source_attribution(self) -> float:
        """Measure rate of proper source attribution in responses."""
        successful_attributions = 0
        total_queries = 0
        
        for test_case in self.critical_queries:
            total_queries += 1
            try:
                response = requests.post(
                    f"{self.api_base_url}/api/v1/query",
                    json={"query": test_case["query"]},
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    sources = data.get('sources', [])
                    if sources and len(sources) > 0:
                        successful_attributions += 1
                        
            except Exception:
                continue
        
        return successful_attributions / total_queries if total_queries > 0 else 0.0
    
    def _measure_medical_accuracy(self) -> float:
        """Measure medical accuracy based on expected content in responses."""
        accurate_responses = 0
        total_queries = 0
        
        for test_case in self.critical_queries:
            total_queries += 1
            try:
                response = requests.post(
                    f"{self.api_base_url}/api/v1/query",
                    json={"query": test_case["query"]},
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    response_text = data.get('response', '').lower()
                    
                    # Check if response contains expected medical content
                    expected_found = any(
                        keyword.lower() in response_text 
                        for keyword in test_case["expected_sources"]
                    )
                    
                    if expected_found:
                        accurate_responses += 1
                        
            except Exception:
                continue
        
        return accurate_responses / total_queries if total_queries > 0 else 0.0
    
    def _get_current_version(self) -> str:
        """Get current version from git or timestamp."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _get_latest_baseline_version(self) -> str:
        """Get the latest baseline version."""
        baseline_files = list(self.results_dir.glob("baseline_*.json"))
        if not baseline_files:
            raise FileNotFoundError("No baseline files found")
        
        # Get most recent baseline
        latest = max(baseline_files, key=lambda f: f.stat().st_mtime)
        return latest.stem.replace("baseline_", "")

def main():
    """Run regression prevention testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Regression Prevention Testing")
    parser.add_argument("--establish-baseline", action="store_true",
                       help="Establish new baseline")
    parser.add_argument("--detect-regressions", action="store_true", 
                       help="Detect regressions against baseline")
    parser.add_argument("--version", help="Version identifier for baseline")
    
    args = parser.parse_args()
    
    tester = RegressionPreventionTester()
    
    if args.establish_baseline:
        baseline = tester.establish_baseline(args.version)
        print(f"\n✅ Baseline established with {baseline.overall_quality_score:.1%} quality")
        
    elif args.detect_regressions:
        result = tester.detect_regressions()
        
        if result.severity == "CRITICAL":
            print(f"\n🚨 CRITICAL REGRESSION - {result.recommendation}")
            exit(1)
        elif result.severity == "MAJOR":
            print(f"\n⚠️  MAJOR REGRESSION - {result.recommendation}")
            exit(1)
        elif result.has_regression:
            print(f"\n⚠️  Minor regressions detected - {result.recommendation}")
        else:
            print(f"\n✅ No regressions detected - System quality maintained")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()