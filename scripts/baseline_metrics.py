#!/usr/bin/env python3
"""
Baseline Metrics Establishment for ED Bot v8
Creates initial performance and accuracy baselines for comparison.
"""

import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import subprocess
import sys


class BaselineMetricsCollector:
    """Collects baseline performance and accuracy metrics."""
    
    def __init__(self, api_url: str = "http://localhost:8001/api/v1/query"):
        self.api_url = api_url
        self.project_root = Path(__file__).parent.parent
        self.baseline_file = self.project_root / "iteration_results" / "baseline_metrics.json"
        self.baseline_file.parent.mkdir(exist_ok=True)
        
        # Core test queries for baseline
        self.baseline_queries = [
            # Critical medical protocols
            "what is the STEMI protocol",
            "standard levophed dosing",
            "pediatric epinephrine dose",
            "sepsis lactate criteria",
            "hypoglycemia treatment protocol",
            
            # Emergency contacts
            "who is on call for cardiology",
            "STEMI pager number",
            
            # Forms and documentation
            "show me the blood transfusion form",
            
            # Clinical criteria
            "stroke thrombolysis window",
            "trauma activation criteria",
            
            # Dosing information
            "adult anaphylaxis epinephrine dose",
            "heparin dosing for STEMI",
            "insulin drip protocol",
            
            # Count queries
            "how many RETU protocols are there",
            
            # General information
            "what can we talk about"
        ]
    
    def measure_response_times(self, iterations: int = 5) -> Dict[str, float]:
        """Measure average response times for baseline queries."""
        print("\n⏱️  Measuring response times...")
        
        response_times = {}
        
        for query in self.baseline_queries:
            times = []
            print(f"  Testing: {query[:50]}...")
            
            for i in range(iterations):
                try:
                    start_time = time.time()
                    response = requests.post(
                        self.api_url,
                        json={"query": query},
                        timeout=10
                    )
                    end_time = time.time()
                    
                    if response.status_code == 200:
                        times.append((end_time - start_time) * 1000)  # Convert to ms
                    
                except Exception as e:
                    print(f"    ❌ Error on iteration {i+1}: {e}")
            
            if times:
                avg_time = sum(times) / len(times)
                response_times[query] = avg_time
                print(f"    ✅ Avg: {avg_time:.0f}ms")
            else:
                response_times[query] = 0.0
                print(f"    ❌ Failed all attempts")
        
        return response_times
    
    def measure_accuracy_baseline(self) -> Dict[str, Any]:
        """Measure accuracy baseline using groundtruth validation."""
        print("\n🎯 Measuring accuracy baseline...")
        
        try:
            # Run groundtruth validation
            result = subprocess.run(
                [sys.executable, "tests/groundtruth/groundtruth_validator.py"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Find the latest groundtruth report
                report_files = list((self.project_root / "tests" / "groundtruth").glob("groundtruth_report_*.json"))
                if report_files:
                    latest_report = max(report_files, key=lambda f: f.stat().st_mtime)
                    with open(latest_report) as f:
                        report_data = json.load(f)
                    
                    accuracy_metrics = {
                        "overall_accuracy": report_data["overall_accuracy"],
                        "category_scores": report_data["category_scores"],
                        "critical_failures_count": len(report_data["critical_failures"]),
                        "total_tests": report_data["total_tests"],
                        "passed_tests": report_data["passed_tests"],
                        "validation_successful": True
                    }
                    
                    print(f"  ✅ Overall accuracy: {accuracy_metrics['overall_accuracy']:.1%}")
                    print(f"  ✅ Tests passed: {accuracy_metrics['passed_tests']}/{accuracy_metrics['total_tests']}")
                    
                    return accuracy_metrics
                else:
                    print("  ❌ No groundtruth report found")
                    return {"validation_successful": False, "error": "No report generated"}
            else:
                print(f"  ❌ Groundtruth validation failed: {result.stderr}")
                return {"validation_successful": False, "error": result.stderr}
                
        except Exception as e:
            print(f"  ❌ Accuracy measurement failed: {e}")
            return {"validation_successful": False, "error": str(e)}
    
    def measure_system_health(self) -> Dict[str, Any]:
        """Measure system health metrics."""
        print("\n🏥 Measuring system health...")
        
        health_metrics = {}
        
        # Check API health
        try:
            response = requests.get(f"{self.api_url.replace('/query', '/health')}", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                health_metrics["api_healthy"] = health_data.get("status") == "healthy"
                health_metrics["components"] = health_data.get("components", {})
                print("  ✅ API health check passed")
            else:
                health_metrics["api_healthy"] = False
                print("  ❌ API health check failed")
        except Exception as e:
            health_metrics["api_healthy"] = False
            print(f"  ❌ API health check error: {e}")
        
        # Check database connection (via API)
        try:
            response = requests.post(
                self.api_url,
                json={"query": "how many RETU protocols are there"},
                timeout=10
            )
            health_metrics["database_responsive"] = response.status_code == 200
            if response.status_code == 200:
                print("  ✅ Database connection working")
            else:
                print("  ❌ Database connection issues")
        except Exception as e:
            health_metrics["database_responsive"] = False
            print(f"  ❌ Database test failed: {e}")
        
        return health_metrics
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        print("\n💻 Collecting system information...")
        
        system_info = {
            "timestamp": datetime.now().isoformat(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
        
        # Get git commit
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                system_info["commit_hash"] = result.stdout.strip()
                print(f"  ✅ Git commit: {system_info['commit_hash'][:8]}")
        except Exception:
            system_info["commit_hash"] = None
            print("  ⚠️  Git commit not available")
        
        # Get branch
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                system_info["git_branch"] = result.stdout.strip()
                print(f"  ✅ Git branch: {system_info['git_branch']}")
        except Exception:
            system_info["git_branch"] = None
        
        return system_info
    
    def establish_baseline(self) -> Dict[str, Any]:
        """Establish comprehensive baseline metrics."""
        print("\n📏 ESTABLISHING BASELINE METRICS")
        print("=" * 50)
        
        baseline = {}
        
        # System information
        baseline["system_info"] = self.get_system_info()
        
        # Performance metrics
        baseline["performance"] = self.measure_response_times()
        avg_response_time = sum(baseline["performance"].values()) / len(baseline["performance"])
        baseline["avg_response_time_ms"] = avg_response_time
        
        # Accuracy metrics
        baseline["accuracy"] = self.measure_accuracy_baseline()
        
        # System health
        baseline["system_health"] = self.measure_system_health()
        
        # Calculate overall score
        baseline["overall_score"] = self._calculate_overall_score(baseline)
        
        return baseline
    
    def _calculate_overall_score(self, baseline: Dict[str, Any]) -> float:
        """Calculate overall baseline score (0-100)."""
        score = 0.0
        
        # Accuracy weight: 50%
        accuracy_data = baseline.get("accuracy", {})
        if accuracy_data.get("validation_successful", False):
            accuracy = accuracy_data.get("overall_accuracy", 0.0)
            score += accuracy * 50
        
        # Performance weight: 30%
        avg_time = baseline.get("avg_response_time_ms", 0)
        if avg_time > 0:
            # Score based on response time (1500ms = 100%, 3000ms = 50%, 6000ms+ = 0%)
            perf_score = max(0, min(1, (6000 - avg_time) / 4500))
            score += perf_score * 30
        
        # System health weight: 20%
        health = baseline.get("system_health", {})
        if health.get("api_healthy", False):
            score += 10
        if health.get("database_responsive", False):
            score += 10
        
        return score
    
    def save_baseline(self, baseline: Dict[str, Any]):
        """Save baseline metrics to file."""
        with open(self.baseline_file, "w") as f:
            json.dump(baseline, f, indent=2)
        
        print(f"\n💾 Baseline saved to: {self.baseline_file}")
    
    def print_baseline_summary(self, baseline: Dict[str, Any]):
        """Print baseline summary."""
        print("\n📊 BASELINE METRICS SUMMARY")
        print("=" * 50)
        
        # Overall score
        overall_score = baseline.get("overall_score", 0)
        print(f"🎯 Overall Score: {overall_score:.1f}/100")
        
        # Accuracy
        accuracy_data = baseline.get("accuracy", {})
        if accuracy_data.get("validation_successful", False):
            acc = accuracy_data.get("overall_accuracy", 0)
            print(f"📈 Accuracy: {acc:.1%}")
            print(f"   Tests: {accuracy_data.get('passed_tests', 0)}/{accuracy_data.get('total_tests', 0)}")
            
            if accuracy_data.get("category_scores"):
                print("   By category:")
                for cat, score in accuracy_data["category_scores"].items():
                    print(f"     {cat}: {score:.1%}")
        else:
            print("📈 Accuracy: ❌ Validation failed")
        
        # Performance
        avg_time = baseline.get("avg_response_time_ms", 0)
        print(f"⚡ Avg Response Time: {avg_time:.0f}ms")
        
        fastest_query = min(baseline.get("performance", {}).items(), key=lambda x: x[1], default=("None", 0))
        slowest_query = max(baseline.get("performance", {}).items(), key=lambda x: x[1], default=("None", 0))
        
        if fastest_query[1] > 0:
            print(f"   Fastest: {fastest_query[1]:.0f}ms ({fastest_query[0][:30]}...)")
        if slowest_query[1] > 0:
            print(f"   Slowest: {slowest_query[1]:.0f}ms ({slowest_query[0][:30]}...)")
        
        # System health
        health = baseline.get("system_health", {})
        api_status = "✅" if health.get("api_healthy", False) else "❌"
        db_status = "✅" if health.get("database_responsive", False) else "❌"
        print(f"🏥 System Health: API {api_status} | Database {db_status}")
        
        # System info
        system_info = baseline.get("system_info", {})
        commit = system_info.get("commit_hash", "unknown")[:8]
        branch = system_info.get("git_branch", "unknown")
        print(f"💻 System: {branch}@{commit}")
        
        print("\n" + "=" * 50)
        
        if overall_score >= 80:
            print("✅ BASELINE ESTABLISHED - System ready for production")
        elif overall_score >= 60:
            print("⚠️  BASELINE ESTABLISHED - System needs improvement")
        else:
            print("❌ BASELINE POOR - Major issues need addressing")


def main():
    """Main function."""
    print("\n📏 ED BOT v8 - BASELINE METRICS COLLECTOR")
    
    collector = BaselineMetricsCollector()
    
    try:
        # Check if API is available
        response = requests.get(collector.api_url.replace('/query', '/health'), timeout=5)
        if response.status_code != 200:
            print("❌ API server not available. Start the API server first.")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to API server: {e}")
        print("   Make sure to run: make up")
        sys.exit(1)
    
    # Establish baseline
    baseline = collector.establish_baseline()
    
    # Print summary
    collector.print_baseline_summary(baseline)
    
    # Save baseline
    collector.save_baseline(baseline)
    
    print("\n🚀 Baseline established! Use this for iteration testing:")
    print("   python scripts/iteration_tester.py")
    print("   python scripts/iteration_tester.py --trend")


if __name__ == "__main__":
    main()