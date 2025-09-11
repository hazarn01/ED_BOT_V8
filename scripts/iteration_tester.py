#!/usr/bin/env python3
"""
Iteration Testing Framework for ED Bot v8
Supports continuous improvement through automated testing cycles.
"""

import json
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import argparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class IterationResult:
    """Result of a single iteration test cycle."""
    iteration: int
    timestamp: str
    groundtruth_score: float
    setup_tests_passed: bool
    performance_ms_avg: float
    critical_failures: List[str]
    regressions: List[str]
    improvements: List[str]
    commit_hash: Optional[str] = None


class IterationTester:
    """Manages iterative testing cycles for continuous improvement."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results_dir = self.project_root / "iteration_results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Load baseline if exists
        self.baseline_file = self.results_dir / "baseline_metrics.json"
        self.baseline = self._load_baseline()
        
    def _load_baseline(self) -> Optional[Dict[str, Any]]:
        """Load baseline metrics for comparison."""
        if self.baseline_file.exists():
            with open(self.baseline_file) as f:
                return json.load(f)
        return None
    
    def _save_baseline(self, metrics: Dict[str, Any]):
        """Save new baseline metrics."""
        with open(self.baseline_file, "w") as f:
            json.dump(metrics, f, indent=2)
    
    def _get_commit_hash(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None
    
    def run_setup_tests(self) -> bool:
        """Run setup validation tests."""
        print("\n🔧 Running setup tests...")
        
        try:
            # Run comprehensive setup test
            result = subprocess.run(
                [sys.executable, "tests/test_setup.py"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            success = result.returncode == 0
            if success:
                print("  ✅ All setup tests passed")
            else:
                print("  ❌ Setup tests failed")
                print(f"     {result.stderr[:200]}...")
                
            return success
            
        except Exception as e:
            print(f"  ❌ Setup test error: {e}")
            return False
    
    def run_groundtruth_validation(self) -> Dict[str, Any]:
        """Run groundtruth validation and return metrics."""
        print("\n🧪 Running groundtruth validation...")
        
        try:
            # Run groundtruth validator
            result = subprocess.run(
                [sys.executable, "tests/groundtruth/groundtruth_validator.py"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Try to find the most recent report
            report_files = list((self.project_root / "tests" / "groundtruth").glob("groundtruth_report_*.json"))
            if report_files:
                latest_report = max(report_files, key=lambda f: f.stat().st_mtime)
                with open(latest_report) as f:
                    report_data = json.load(f)
                
                print(f"  📊 Overall accuracy: {report_data['overall_accuracy']:.1%}")
                print(f"  🎯 Critical failures: {len(report_data['critical_failures'])}")
                
                return {
                    "overall_accuracy": report_data["overall_accuracy"],
                    "critical_failures": report_data["critical_failures"],
                    "regression_issues": report_data["regression_issues"],
                    "category_scores": report_data["category_scores"],
                    "avg_response_time": self._calculate_avg_response_time(report_data["results"]),
                    "success": result.returncode == 0
                }
            else:
                print("  ❌ No groundtruth report generated")
                return {"success": False, "overall_accuracy": 0.0}
                
        except Exception as e:
            print(f"  ❌ Groundtruth validation error: {e}")
            return {"success": False, "overall_accuracy": 0.0}
    
    def _calculate_avg_response_time(self, results: List[Dict[str, Any]]) -> float:
        """Calculate average response time from results."""
        times = [r.get("execution_time_ms", 0) for r in results if r.get("execution_time_ms")]
        return sum(times) / len(times) if times else 0.0
    
    def compare_with_baseline(self, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current metrics with baseline."""
        if not self.baseline:
            return {"improvements": ["First baseline established"], "regressions": []}
        
        improvements = []
        regressions = []
        
        # Compare overall accuracy
        current_acc = current_metrics.get("overall_accuracy", 0.0)
        baseline_acc = self.baseline.get("overall_accuracy", 0.0)
        
        if current_acc > baseline_acc + 0.02:  # 2% improvement threshold
            improvements.append(f"Accuracy improved: {baseline_acc:.1%} → {current_acc:.1%}")
        elif current_acc < baseline_acc - 0.02:  # 2% regression threshold
            regressions.append(f"Accuracy decreased: {baseline_acc:.1%} → {current_acc:.1%}")
        
        # Compare response time
        current_time = current_metrics.get("avg_response_time", 0.0)
        baseline_time = self.baseline.get("avg_response_time", 0.0)
        
        if baseline_time > 0:
            time_change = (current_time - baseline_time) / baseline_time
            if time_change < -0.1:  # 10% faster
                improvements.append(f"Response time improved: {baseline_time:.0f}ms → {current_time:.0f}ms")
            elif time_change > 0.2:  # 20% slower
                regressions.append(f"Response time degraded: {baseline_time:.0f}ms → {current_time:.0f}ms")
        
        # Compare critical failures
        current_failures = len(current_metrics.get("critical_failures", []))
        baseline_failures = len(self.baseline.get("critical_failures", []))
        
        if current_failures < baseline_failures:
            improvements.append(f"Critical failures reduced: {baseline_failures} → {current_failures}")
        elif current_failures > baseline_failures:
            regressions.append(f"Critical failures increased: {baseline_failures} → {current_failures}")
        
        return {"improvements": improvements, "regressions": regressions}
    
    def run_iteration(self, iteration: int) -> IterationResult:
        """Run a complete iteration test cycle."""
        print(f"\n🔄 ITERATION {iteration}")
        print("=" * 50)
        
        timestamp = datetime.now().isoformat()
        commit_hash = self._get_commit_hash()
        
        if commit_hash:
            print(f"📝 Testing commit: {commit_hash}")
        
        # 1. Run setup tests
        setup_passed = self.run_setup_tests()
        
        # 2. Run groundtruth validation
        gt_metrics = self.run_groundtruth_validation()
        
        if not gt_metrics.get("success", False):
            print("❌ Iteration failed - groundtruth validation failed")
            return IterationResult(
                iteration=iteration,
                timestamp=timestamp,
                groundtruth_score=0.0,
                setup_tests_passed=setup_passed,
                performance_ms_avg=0.0,
                critical_failures=["Groundtruth validation failed"],
                regressions=["Validation system failure"],
                improvements=[],
                commit_hash=commit_hash
            )
        
        # 3. Compare with baseline
        comparison = self.compare_with_baseline(gt_metrics)
        
        # Create result
        result = IterationResult(
            iteration=iteration,
            timestamp=timestamp,
            groundtruth_score=gt_metrics.get("overall_accuracy", 0.0),
            setup_tests_passed=setup_passed,
            performance_ms_avg=gt_metrics.get("avg_response_time", 0.0),
            critical_failures=gt_metrics.get("critical_failures", []),
            regressions=gt_metrics.get("regression_issues", []) + comparison["regressions"],
            improvements=comparison["improvements"],
            commit_hash=commit_hash
        )
        
        # Save result
        self._save_iteration_result(result)
        
        # Update baseline if this is better
        if result.groundtruth_score > self.baseline.get("overall_accuracy", 0.0) if self.baseline else True:
            print("📈 New baseline established!")
            self._save_baseline({
                "overall_accuracy": result.groundtruth_score,
                "avg_response_time": result.performance_ms_avg,
                "critical_failures": result.critical_failures,
                "timestamp": timestamp,
                "commit_hash": commit_hash
            })
        
        return result
    
    def _save_iteration_result(self, result: IterationResult):
        """Save iteration result to file."""
        result_file = self.results_dir / f"iteration_{result.iteration}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        result_dict = {
            "iteration": result.iteration,
            "timestamp": result.timestamp,
            "groundtruth_score": result.groundtruth_score,
            "setup_tests_passed": result.setup_tests_passed,
            "performance_ms_avg": result.performance_ms_avg,
            "critical_failures": result.critical_failures,
            "regressions": result.regressions,
            "improvements": result.improvements,
            "commit_hash": result.commit_hash
        }
        
        with open(result_file, "w") as f:
            json.dump(result_dict, f, indent=2)
        
        logger.info(f"Iteration result saved to: {result_file}")
    
    def print_iteration_summary(self, result: IterationResult):
        """Print iteration summary."""
        print(f"\n📊 ITERATION {result.iteration} SUMMARY")
        print("=" * 50)
        
        print(f"🎯 Groundtruth Score: {result.groundtruth_score:.1%}")
        print(f"🔧 Setup Tests: {'✅ PASSED' if result.setup_tests_passed else '❌ FAILED'}")
        print(f"⚡ Avg Response Time: {result.performance_ms_avg:.0f}ms")
        
        if result.critical_failures:
            print(f"\n🚨 Critical Failures ({len(result.critical_failures)}):")
            for failure in result.critical_failures:
                print(f"  • {failure}")
        
        if result.improvements:
            print(f"\n📈 Improvements ({len(result.improvements)}):")
            for improvement in result.improvements:
                print(f"  • {improvement}")
        
        if result.regressions:
            print(f"\n📉 Regressions ({len(result.regressions)}):")
            for regression in result.regressions:
                print(f"  • {regression}")
        
        # Overall assessment
        if result.groundtruth_score >= 0.95 and result.setup_tests_passed and not result.critical_failures:
            print("\n✅ ITERATION PASSED - Production ready")
        elif result.groundtruth_score >= 0.8 and result.setup_tests_passed:
            print("\n⚠️  ITERATION PARTIAL - Needs improvement")
        else:
            print("\n❌ ITERATION FAILED - Major issues")
    
    def run_continuous_testing(self, max_iterations: int = 10, interval_minutes: int = 60):
        """Run continuous testing cycles."""
        print(f"\n🔄 CONTINUOUS ITERATION TESTING")
        print(f"Max iterations: {max_iterations}")
        print(f"Interval: {interval_minutes} minutes")
        print("=" * 50)
        
        for i in range(1, max_iterations + 1):
            result = self.run_iteration(i)
            self.print_iteration_summary(result)
            
            if i < max_iterations:
                print(f"\n⏸️  Waiting {interval_minutes} minutes until next iteration...")
                time.sleep(interval_minutes * 60)
    
    def generate_trend_report(self) -> Dict[str, Any]:
        """Generate trend analysis from historical iterations."""
        iteration_files = list(self.results_dir.glob("iteration_*.json"))
        
        if not iteration_files:
            return {"error": "No iteration history found"}
        
        results = []
        for file in sorted(iteration_files):
            with open(file) as f:
                results.append(json.load(f))
        
        # Calculate trends
        scores = [r["groundtruth_score"] for r in results]
        times = [r["performance_ms_avg"] for r in results]
        
        trend_report = {
            "total_iterations": len(results),
            "score_trend": {
                "first": scores[0] if scores else 0,
                "latest": scores[-1] if scores else 0,
                "best": max(scores) if scores else 0,
                "improvement": scores[-1] - scores[0] if len(scores) > 1 else 0
            },
            "performance_trend": {
                "first_ms": times[0] if times else 0,
                "latest_ms": times[-1] if times else 0,
                "best_ms": min(t for t in times if t > 0) if times else 0
            },
            "recent_regressions": sum(1 for r in results[-5:] if r.get("regressions")),
            "recent_improvements": sum(1 for r in results[-5:] if r.get("improvements"))
        }
        
        return trend_report


def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(description="ED Bot v8 Iteration Tester")
    parser.add_argument("--iterations", "-i", type=int, default=1, 
                       help="Number of iterations to run")
    parser.add_argument("--continuous", "-c", action="store_true",
                       help="Run continuous testing")
    parser.add_argument("--interval", type=int, default=60,
                       help="Interval between iterations in minutes (continuous mode)")
    parser.add_argument("--trend", "-t", action="store_true",
                       help="Generate trend report")
    
    args = parser.parse_args()
    
    tester = IterationTester()
    
    if args.trend:
        print("\n📈 ITERATION TREND REPORT")
        print("=" * 50)
        trend = tester.generate_trend_report()
        if "error" in trend:
            print(f"❌ {trend['error']}")
        else:
            print(f"Total Iterations: {trend['total_iterations']}")
            print(f"Score: {trend['score_trend']['first']:.1%} → {trend['score_trend']['latest']:.1%} (best: {trend['score_trend']['best']:.1%})")
            print(f"Performance: {trend['performance_trend']['first_ms']:.0f}ms → {trend['performance_trend']['latest_ms']:.0f}ms")
            print(f"Recent Improvements: {trend['recent_improvements']}")
            print(f"Recent Regressions: {trend['recent_regressions']}")
    
    elif args.continuous:
        tester.run_continuous_testing(args.iterations, args.interval)
    
    else:
        for i in range(1, args.iterations + 1):
            result = tester.run_iteration(i)
            tester.print_iteration_summary(result)


if __name__ == "__main__":
    main()