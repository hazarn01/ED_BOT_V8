#!/usr/bin/env python3
"""
Regression Detection System for ED Bot v8
Automatically detects performance and accuracy regressions.
"""

import json
import requests
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import argparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RegressionAlert:
    """Represents a detected regression."""
    type: str  # 'accuracy', 'performance', 'critical_failure', 'availability'
    severity: str  # 'critical', 'major', 'minor'
    description: str
    current_value: Any
    expected_value: Any
    threshold_exceeded: float
    detected_at: str


@dataclass
class RegressionReport:
    """Complete regression detection report."""
    timestamp: str
    alerts: List[RegressionAlert]
    system_healthy: bool
    regression_score: float  # 0-100, lower is worse
    recommendations: List[str]


class RegressionDetector:
    """Detects regressions in system performance and accuracy."""
    
    def __init__(self, api_url: str = "http://localhost:8001/api/v1/query"):
        self.api_url = api_url
        self.project_root = Path(__file__).parent.parent
        self.baseline_file = self.project_root / "iteration_results" / "baseline_metrics.json"
        self.results_dir = self.project_root / "iteration_results"
        
        # Regression thresholds
        self.thresholds = {
            "accuracy_major": 0.05,      # 5% accuracy drop = major
            "accuracy_critical": 0.10,   # 10% accuracy drop = critical
            "performance_major": 0.20,   # 20% slowdown = major
            "performance_critical": 0.50, # 50% slowdown = critical
            "response_timeout": 5000,    # 5s response = critical
            "availability_critical": 0.80 # 80% success rate = critical
        }
        
        # Load baseline
        self.baseline = self._load_baseline()
        
        # Critical medical queries that must always work
        self.critical_queries = [
            "what is the STEMI protocol",
            "pediatric epinephrine dose",
            "sepsis lactate criteria",
            "who is on call for cardiology"
        ]
    
    def _load_baseline(self) -> Optional[Dict[str, Any]]:
        """Load baseline metrics."""
        if self.baseline_file.exists():
            with open(self.baseline_file) as f:
                return json.load(f)
        return None
    
    def detect_accuracy_regressions(self) -> List[RegressionAlert]:
        """Detect accuracy regressions using groundtruth validation."""
        alerts = []
        
        if not self.baseline:
            return [RegressionAlert(
                type="accuracy",
                severity="major",
                description="No baseline available for comparison",
                current_value="unknown",
                expected_value="baseline",
                threshold_exceeded=0.0,
                detected_at=datetime.now().isoformat()
            )]
        
        print("🎯 Checking accuracy regressions...")
        
        try:
            # Get latest groundtruth results
            report_files = list((self.project_root / "tests" / "groundtruth").glob("groundtruth_report_*.json"))
            if not report_files:
                return [RegressionAlert(
                    type="accuracy",
                    severity="critical",
                    description="No recent groundtruth validation results found",
                    current_value="missing",
                    expected_value="validation report",
                    threshold_exceeded=1.0,
                    detected_at=datetime.now().isoformat()
                )]
            
            latest_report = max(report_files, key=lambda f: f.stat().st_mtime)
            with open(latest_report) as f:
                current_results = json.load(f)
            
            baseline_accuracy = self.baseline.get("accuracy", {}).get("overall_accuracy", 0.0)
            current_accuracy = current_results.get("overall_accuracy", 0.0)
            
            accuracy_drop = baseline_accuracy - current_accuracy
            
            if accuracy_drop >= self.thresholds["accuracy_critical"]:
                alerts.append(RegressionAlert(
                    type="accuracy",
                    severity="critical",
                    description=f"Critical accuracy regression: {baseline_accuracy:.1%} → {current_accuracy:.1%}",
                    current_value=current_accuracy,
                    expected_value=baseline_accuracy,
                    threshold_exceeded=accuracy_drop,
                    detected_at=datetime.now().isoformat()
                ))
            elif accuracy_drop >= self.thresholds["accuracy_major"]:
                alerts.append(RegressionAlert(
                    type="accuracy",
                    severity="major",
                    description=f"Major accuracy regression: {baseline_accuracy:.1%} → {current_accuracy:.1%}",
                    current_value=current_accuracy,
                    expected_value=baseline_accuracy,
                    threshold_exceeded=accuracy_drop,
                    detected_at=datetime.now().isoformat()
                ))
            
            # Check for new critical failures
            current_failures = len(current_results.get("critical_failures", []))
            baseline_failures = len(self.baseline.get("accuracy", {}).get("critical_failures", []))
            
            if current_failures > baseline_failures:
                alerts.append(RegressionAlert(
                    type="critical_failure",
                    severity="critical" if current_failures > baseline_failures + 2 else "major",
                    description=f"New critical failures: {baseline_failures} → {current_failures}",
                    current_value=current_failures,
                    expected_value=baseline_failures,
                    threshold_exceeded=current_failures - baseline_failures,
                    detected_at=datetime.now().isoformat()
                ))
            
            print(f"  ✅ Accuracy check: {current_accuracy:.1%} (baseline: {baseline_accuracy:.1%})")
            
        except Exception as e:
            alerts.append(RegressionAlert(
                type="accuracy",
                severity="major",
                description=f"Failed to check accuracy regressions: {e}",
                current_value="error",
                expected_value="successful check",
                threshold_exceeded=1.0,
                detected_at=datetime.now().isoformat()
            ))
        
        return alerts
    
    def detect_performance_regressions(self) -> List[RegressionAlert]:
        """Detect performance regressions."""
        alerts = []
        
        if not self.baseline:
            return alerts
        
        print("⚡ Checking performance regressions...")
        
        baseline_avg_time = self.baseline.get("avg_response_time_ms", 0)
        if baseline_avg_time == 0:
            return alerts
        
        # Test current performance
        current_times = []
        test_queries = [
            "what is the STEMI protocol",
            "standard levophed dosing",
            "sepsis lactate criteria"
        ]
        
        for query in test_queries:
            try:
                start_time = time.time()
                response = requests.post(
                    self.api_url,
                    json={"query": query},
                    timeout=10
                )
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000  # ms
                
                if response.status_code == 200:
                    current_times.append(response_time)
                    
                    # Check for timeout regression
                    if response_time > self.thresholds["response_timeout"]:
                        alerts.append(RegressionAlert(
                            type="performance",
                            severity="critical",
                            description=f"Query timeout: {response_time:.0f}ms > {self.thresholds['response_timeout']}ms",
                            current_value=response_time,
                            expected_value=self.thresholds["response_timeout"],
                            threshold_exceeded=(response_time - self.thresholds["response_timeout"]) / self.thresholds["response_timeout"],
                            detected_at=datetime.now().isoformat()
                        ))
                
            except Exception as e:
                alerts.append(RegressionAlert(
                    type="availability",
                    severity="critical",
                    description=f"Query failed: {query[:50]} - {e}",
                    current_value="failed",
                    expected_value="success",
                    threshold_exceeded=1.0,
                    detected_at=datetime.now().isoformat()
                ))
        
        if current_times:
            current_avg_time = sum(current_times) / len(current_times)
            slowdown_ratio = (current_avg_time - baseline_avg_time) / baseline_avg_time
            
            if slowdown_ratio >= self.thresholds["performance_critical"]:
                alerts.append(RegressionAlert(
                    type="performance",
                    severity="critical",
                    description=f"Critical performance regression: {baseline_avg_time:.0f}ms → {current_avg_time:.0f}ms ({slowdown_ratio:.1%} slower)",
                    current_value=current_avg_time,
                    expected_value=baseline_avg_time,
                    threshold_exceeded=slowdown_ratio,
                    detected_at=datetime.now().isoformat()
                ))
            elif slowdown_ratio >= self.thresholds["performance_major"]:
                alerts.append(RegressionAlert(
                    type="performance",
                    severity="major",
                    description=f"Major performance regression: {baseline_avg_time:.0f}ms → {current_avg_time:.0f}ms ({slowdown_ratio:.1%} slower)",
                    current_value=current_avg_time,
                    expected_value=baseline_avg_time,
                    threshold_exceeded=slowdown_ratio,
                    detected_at=datetime.now().isoformat()
                ))
            
            print(f"  ✅ Performance check: {current_avg_time:.0f}ms (baseline: {baseline_avg_time:.0f}ms)")
        else:
            alerts.append(RegressionAlert(
                type="availability",
                severity="critical",
                description="All test queries failed - system may be down",
                current_value=0,
                expected_value=len(test_queries),
                threshold_exceeded=1.0,
                detected_at=datetime.now().isoformat()
            ))
        
        return alerts
    
    def detect_critical_query_regressions(self) -> List[RegressionAlert]:
        """Test critical medical queries that must always work."""
        alerts = []
        
        print("🚨 Checking critical medical queries...")
        
        failed_critical = []
        
        for query in self.critical_queries:
            try:
                response = requests.post(
                    self.api_url,
                    json={"query": query},
                    timeout=10
                )
                
                if response.status_code != 200:
                    failed_critical.append(query)
                else:
                    response_data = response.json()
                    
                    # Check if response has actual content
                    response_text = response_data.get("response", "")
                    confidence = response_data.get("confidence", 0.0)
                    
                    if len(response_text.strip()) < 10:
                        failed_critical.append(f"{query} - empty response")
                    elif confidence < 0.3:
                        failed_critical.append(f"{query} - very low confidence ({confidence:.2f})")
                    
                    # Specific validations for critical queries
                    if "STEMI" in query and "917-827-9725" not in response_text:
                        failed_critical.append(f"{query} - missing critical STEMI pager")
                    elif "epinephrine" in query and "0.01" not in response_text:
                        failed_critical.append(f"{query} - missing pediatric dose")
                    elif "sepsis" in query and "lactate" not in response_text.lower():
                        failed_critical.append(f"{query} - missing lactate criteria")
                
            except Exception as e:
                failed_critical.append(f"{query} - request failed: {e}")
        
        if failed_critical:
            alerts.append(RegressionAlert(
                type="critical_failure",
                severity="critical",
                description=f"Critical medical queries failing: {len(failed_critical)}/{len(self.critical_queries)}",
                current_value=failed_critical,
                expected_value="all queries working",
                threshold_exceeded=len(failed_critical) / len(self.critical_queries),
                detected_at=datetime.now().isoformat()
            ))
        else:
            print(f"  ✅ All {len(self.critical_queries)} critical queries working")
        
        return alerts
    
    def detect_system_health_regressions(self) -> List[RegressionAlert]:
        """Check overall system health."""
        alerts = []
        
        print("🏥 Checking system health...")
        
        try:
            # Check API health endpoint
            response = requests.get(f"{self.api_url.replace('/query', '/health')}", timeout=5)
            if response.status_code != 200:
                alerts.append(RegressionAlert(
                    type="availability",
                    severity="critical",
                    description=f"Health endpoint not responding: HTTP {response.status_code}",
                    current_value=response.status_code,
                    expected_value=200,
                    threshold_exceeded=1.0,
                    detected_at=datetime.now().isoformat()
                ))
            else:
                health_data = response.json()
                status = health_data.get("status", "unknown")
                if status != "healthy":
                    alerts.append(RegressionAlert(
                        type="availability",
                        severity="major",
                        description=f"System reports unhealthy status: {status}",
                        current_value=status,
                        expected_value="healthy",
                        threshold_exceeded=0.5,
                        detected_at=datetime.now().isoformat()
                    ))
        
        except Exception as e:
            alerts.append(RegressionAlert(
                type="availability",
                severity="critical",
                description=f"Cannot reach health endpoint: {e}",
                current_value="unreachable",
                expected_value="responsive",
                threshold_exceeded=1.0,
                detected_at=datetime.now().isoformat()
            ))
        
        return alerts
    
    def run_detection(self) -> RegressionReport:
        """Run complete regression detection."""
        print("\n🔍 REGRESSION DETECTION")
        print("=" * 40)
        
        all_alerts = []
        
        # Run all detection methods
        all_alerts.extend(self.detect_system_health_regressions())
        all_alerts.extend(self.detect_critical_query_regressions())
        all_alerts.extend(self.detect_performance_regressions())
        all_alerts.extend(self.detect_accuracy_regressions())
        
        # Calculate regression score
        regression_score = self._calculate_regression_score(all_alerts)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(all_alerts)
        
        # Determine system health
        system_healthy = not any(alert.severity == "critical" for alert in all_alerts)
        
        return RegressionReport(
            timestamp=datetime.now().isoformat(),
            alerts=all_alerts,
            system_healthy=system_healthy,
            regression_score=regression_score,
            recommendations=recommendations
        )
    
    def _calculate_regression_score(self, alerts: List[RegressionAlert]) -> float:
        """Calculate overall regression score (100 = perfect, 0 = broken)."""
        if not alerts:
            return 100.0
        
        penalty = 0.0
        for alert in alerts:
            if alert.severity == "critical":
                penalty += 30.0
            elif alert.severity == "major":
                penalty += 15.0
            elif alert.severity == "minor":
                penalty += 5.0
        
        return max(0.0, 100.0 - penalty)
    
    def _generate_recommendations(self, alerts: List[RegressionAlert]) -> List[str]:
        """Generate recommendations based on alerts."""
        recommendations = []
        
        critical_count = sum(1 for alert in alerts if alert.severity == "critical")
        major_count = sum(1 for alert in alerts if alert.severity == "major")
        
        if critical_count > 0:
            recommendations.append(f"🚨 URGENT: Fix {critical_count} critical issues before deployment")
        
        if any(alert.type == "availability" for alert in alerts):
            recommendations.append("🔄 Restart services: make down && make up")
        
        if any(alert.type == "performance" for alert in alerts):
            recommendations.append("⚡ Check system resources and optimize slow queries")
        
        if any(alert.type == "accuracy" for alert in alerts):
            recommendations.append("🎯 Review recent code changes affecting medical accuracy")
            recommendations.append("📊 Run full groundtruth validation: python tests/groundtruth/groundtruth_validator.py")
        
        if any(alert.type == "critical_failure" for alert in alerts):
            recommendations.append("🏥 Verify medical protocol data and document seeding")
        
        if not recommendations:
            recommendations.append("✅ System operating normally - no action needed")
        
        return recommendations
    
    def print_report(self, report: RegressionReport):
        """Print regression detection report."""
        print("\n📊 REGRESSION DETECTION REPORT")
        print("=" * 40)
        
        # Overall status
        status_icon = "✅" if report.system_healthy else "❌"
        print(f"{status_icon} System Health: {'HEALTHY' if report.system_healthy else 'UNHEALTHY'}")
        print(f"📈 Regression Score: {report.regression_score:.1f}/100")
        
        # Alerts by severity
        critical_alerts = [a for a in report.alerts if a.severity == "critical"]
        major_alerts = [a for a in report.alerts if a.severity == "major"]
        minor_alerts = [a for a in report.alerts if a.severity == "minor"]
        
        if critical_alerts:
            print(f"\n🚨 CRITICAL REGRESSIONS ({len(critical_alerts)}):")
            for alert in critical_alerts:
                print(f"  • {alert.description}")
        
        if major_alerts:
            print(f"\n⚠️  MAJOR REGRESSIONS ({len(major_alerts)}):")
            for alert in major_alerts:
                print(f"  • {alert.description}")
        
        if minor_alerts:
            print(f"\n🔍 MINOR ISSUES ({len(minor_alerts)}):")
            for alert in minor_alerts:
                print(f"  • {alert.description}")
        
        # Recommendations
        if report.recommendations:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in report.recommendations:
                print(f"  {rec}")
        
        print("\n" + "=" * 40)
        
        if report.regression_score >= 90:
            print("🎯 EXCELLENT: No significant regressions detected")
        elif report.regression_score >= 70:
            print("👍 GOOD: Minor issues detected, monitoring recommended")
        elif report.regression_score >= 50:
            print("⚠️  WARNING: Significant regressions detected")
        else:
            print("🚨 CRITICAL: Major regressions detected - immediate action required")
    
    def save_report(self, report: RegressionReport):
        """Save regression report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.results_dir / f"regression_report_{timestamp}.json"
        
        # Convert to dict
        report_dict = {
            "timestamp": report.timestamp,
            "alerts": [
                {
                    "type": alert.type,
                    "severity": alert.severity,
                    "description": alert.description,
                    "current_value": str(alert.current_value),
                    "expected_value": str(alert.expected_value),
                    "threshold_exceeded": alert.threshold_exceeded,
                    "detected_at": alert.detected_at
                }
                for alert in report.alerts
            ],
            "system_healthy": report.system_healthy,
            "regression_score": report.regression_score,
            "recommendations": report.recommendations
        }
        
        with open(report_file, "w") as f:
            json.dump(report_dict, f, indent=2)
        
        print(f"\n📝 Report saved: {report_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="ED Bot v8 Regression Detector")
    parser.add_argument("--continuous", "-c", action="store_true",
                       help="Run continuous regression monitoring")
    parser.add_argument("--interval", type=int, default=30,
                       help="Check interval in minutes (continuous mode)")
    
    args = parser.parse_args()
    
    detector = RegressionDetector()
    
    if args.continuous:
        print(f"🔄 Starting continuous regression monitoring (every {args.interval} minutes)")
        while True:
            report = detector.run_detection()
            detector.print_report(report)
            detector.save_report(report)
            
            if not report.system_healthy:
                print("🚨 SYSTEM UNHEALTHY - Check alerts above!")
            
            print(f"\n💤 Waiting {args.interval} minutes...")
            time.sleep(args.interval * 60)
    else:
        report = detector.run_detection()
        detector.print_report(report)
        detector.save_report(report)
        
        # Exit code based on health
        sys.exit(0 if report.system_healthy else 1)


if __name__ == "__main__":
    main()