#!/usr/bin/env python3
"""
Incremental Enhancement Testing Methodology

This script provides a framework for testing enhancements ONE AT A TIME
to prevent quality regressions and identify which specific changes cause problems.

Key Principles:
1. Test baseline first
2. Add ONE enhancement at a time  
3. Validate quality at each step
4. Rollback immediately if quality drops
5. Never proceed to next enhancement until current one is validated

Usage:
    python3 scripts/incremental_enhancement_test.py --baseline
    python3 scripts/incremental_enhancement_test.py --test-enhancement bm25
    python3 scripts/incremental_enhancement_test.py --test-enhancement synonyms
    python3 scripts/incremental_enhancement_test.py --test-enhancement multi-source
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IncrementalTester:
    """Framework for testing enhancements incrementally."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.results_dir = self.base_dir / "tests" / "quality" / "incremental"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Enhancement configurations
        self.enhancements = {
            "baseline": {
                "description": "Basic retrieval system without enhancements",
                "code_changes": [],
                "expected_improvement": 0.0
            },
            "bm25": {
                "description": "Add BM25 scoring to improve relevance ranking",
                "code_changes": ["enable_bm25_scorer"],
                "expected_improvement": 0.1,
                "rollback_threshold": -0.05
            },
            "synonyms": {
                "description": "Add medical synonym expansion",
                "code_changes": ["enable_synonym_expansion"],
                "expected_improvement": 0.15,
                "rollback_threshold": -0.05
            },
            "multi-source": {
                "description": "Enable multi-source retrieval (3-5 sources)",
                "code_changes": ["enable_multi_source_retrieval"],
                "expected_improvement": 0.2,
                "rollback_threshold": -0.1
            },
            "confidence": {
                "description": "Add advanced confidence scoring",
                "code_changes": ["enable_confidence_calculation"],
                "expected_improvement": 0.05,
                "rollback_threshold": -0.05
            }
        }
    
    def run_baseline_test(self) -> Dict:
        """Establish baseline quality metrics."""
        logger.info("🔄 Establishing baseline quality metrics...")
        
        # Ensure we're in baseline mode
        self._ensure_baseline_mode()
        
        # Run quality tests
        results = self._run_quality_tests("baseline")
        
        # Save baseline for future comparisons
        baseline_file = self.results_dir / "baseline_results.json"
        with open(baseline_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"📊 Baseline established: {results['overall_score']:.1%} quality")
        logger.info(f"💾 Baseline saved to: {baseline_file}")
        
        return results
    
    def test_enhancement(self, enhancement_name: str, baseline_file: Optional[str] = None) -> Dict:
        """Test a single enhancement against baseline."""
        if enhancement_name not in self.enhancements:
            raise ValueError(f"Unknown enhancement: {enhancement_name}")
        
        enhancement = self.enhancements[enhancement_name]
        logger.info(f"🧪 Testing enhancement: {enhancement_name}")
        logger.info(f"📝 Description: {enhancement['description']}")
        
        # Load baseline results
        if not baseline_file:
            baseline_file = self.results_dir / "baseline_results.json"
        
        try:
            with open(baseline_file, 'r') as f:
                baseline_results = json.load(f)
            logger.info(f"📈 Baseline quality: {baseline_results['overall_score']:.1%}")
        except FileNotFoundError:
            logger.error("❌ No baseline found. Run --baseline first.")
            sys.exit(1)
        
        # Apply enhancement
        logger.info("🔧 Applying enhancement...")
        self._apply_enhancement(enhancement_name)
        
        # Wait for system to restart
        time.sleep(3)
        
        # Test enhanced system
        logger.info("🧪 Testing enhanced system...")
        enhanced_results = self._run_quality_tests(enhancement_name)
        
        # Compare with baseline
        quality_change = enhanced_results['overall_score'] - baseline_results['overall_score']
        critical_change = enhanced_results['critical_failures'] - baseline_results['critical_failures']
        
        logger.info(f"📊 Quality change: {quality_change:+.1%}")
        logger.info(f"🚨 Critical failures change: {critical_change:+d}")
        
        # Evaluate results
        evaluation = self._evaluate_enhancement_results(
            enhancement_name, baseline_results, enhanced_results
        )
        
        # Save results
        results_file = self.results_dir / f"{enhancement_name}_results.json"
        with open(results_file, 'w') as f:
            json.dump({
                "enhancement": enhancement_name,
                "baseline": baseline_results,
                "enhanced": enhanced_results,
                "evaluation": evaluation,
                "timestamp": time.time()
            }, f, indent=2, default=str)
        
        # Decision making
        if evaluation["recommendation"] == "ROLLBACK":
            logger.error(f"💥 ENHANCEMENT FAILED - Rolling back...")
            self._rollback_enhancement(enhancement_name)
            logger.info("↩️  Rolled back to baseline")
        elif evaluation["recommendation"] == "ACCEPT":
            logger.info(f"✅ ENHANCEMENT SUCCESSFUL - Keeping changes")
        else:
            logger.warning(f"⚠️  ENHANCEMENT MARGINAL - Manual review needed")
        
        return {
            "enhancement": enhancement_name,
            "baseline_score": baseline_results['overall_score'],
            "enhanced_score": enhanced_results['overall_score'],
            "quality_change": quality_change,
            "evaluation": evaluation
        }
    
    def _ensure_baseline_mode(self):
        """Ensure system is in baseline mode without enhancements."""
        retriever_file = self.base_dir / "src" / "pipeline" / "simple_direct_retriever.py"
        
        # Read current file
        with open(retriever_file, 'r') as f:
            content = f.read()
        
        # Check if enhanced mode is disabled
        if "self.enhanced_mode = False" not in content:
            logger.info("🔧 Disabling enhanced mode for baseline...")
            
            # Disable enhanced mode
            updated_content = content.replace(
                "self.enhanced_mode = True",
                "self.enhanced_mode = False  # BASELINE MODE"
            )
            
            with open(retriever_file, 'w') as f:
                f.write(updated_content)
            
            logger.info("✅ Enhanced mode disabled")
    
    def _apply_enhancement(self, enhancement_name: str):
        """Apply a specific enhancement to the codebase."""
        # This is a placeholder - in reality, you'd have specific code changes
        # for each enhancement type that can be applied incrementally
        
        if enhancement_name == "bm25":
            self._enable_bm25_only()
        elif enhancement_name == "synonyms":
            self._enable_synonyms_only()
        elif enhancement_name == "multi-source":
            self._enable_multi_source_only()
        elif enhancement_name == "confidence":
            self._enable_confidence_only()
        else:
            logger.warning(f"No specific implementation for {enhancement_name}")
    
    def _enable_bm25_only(self):
        """Enable ONLY BM25 scoring, keeping other enhancements disabled."""
        # Implementation would modify simple_direct_retriever.py to enable
        # only BM25 scoring while keeping other features disabled
        logger.info("🔧 Enabling BM25 scoring only...")
        pass
    
    def _enable_synonyms_only(self):
        """Enable ONLY synonym expansion."""
        logger.info("🔧 Enabling synonym expansion only...")
        pass
    
    def _enable_multi_source_only(self):
        """Enable ONLY multi-source retrieval."""
        logger.info("🔧 Enabling multi-source retrieval only...")
        pass
    
    def _enable_confidence_only(self):
        """Enable ONLY confidence calculation."""
        logger.info("🔧 Enabling confidence calculation only...")
        pass
    
    def _rollback_enhancement(self, enhancement_name: str):
        """Rollback a specific enhancement."""
        logger.info(f"↩️  Rolling back {enhancement_name}...")
        self._ensure_baseline_mode()
    
    def _run_quality_tests(self, test_name: str) -> Dict:
        """Run the medical relevance quality tests."""
        try:
            # Run the medical relevance test suite
            result = subprocess.run([
                sys.executable, 
                str(self.base_dir / "tests" / "quality" / "test_medical_relevance.py")
            ], capture_output=True, text=True, cwd=self.base_dir)
            
            if result.returncode == 0:
                logger.info(f"✅ Quality tests passed for {test_name}")
            else:
                logger.warning(f"⚠️  Quality tests had issues for {test_name}")
            
            # Parse results from the last line or a results file
            # This is simplified - in reality you'd parse the actual results
            return {
                "overall_score": 0.8,  # Placeholder
                "critical_failures": 0,
                "test_name": test_name,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to run quality tests: {e}")
            return {
                "overall_score": 0.0,
                "critical_failures": 999,
                "error": str(e)
            }
    
    def _evaluate_enhancement_results(self, enhancement_name: str, 
                                    baseline: Dict, enhanced: Dict) -> Dict:
        """Evaluate whether an enhancement should be kept or rolled back."""
        enhancement_config = self.enhancements[enhancement_name]
        
        quality_change = enhanced['overall_score'] - baseline['overall_score']
        critical_change = enhanced['critical_failures'] - baseline['critical_failures']
        
        # Decision logic
        if critical_change > 0:
            recommendation = "ROLLBACK"
            reason = "Introduced critical medical safety issues"
        elif quality_change < enhancement_config.get("rollback_threshold", -0.05):
            recommendation = "ROLLBACK"
            reason = f"Quality degraded by {quality_change:.1%} (below threshold)"
        elif quality_change >= enhancement_config.get("expected_improvement", 0.1):
            recommendation = "ACCEPT"
            reason = f"Quality improved by {quality_change:.1%} as expected"
        elif quality_change >= 0:
            recommendation = "REVIEW"
            reason = f"Marginal improvement {quality_change:.1%}, below expectation"
        else:
            recommendation = "ROLLBACK"
            reason = f"Quality degraded by {quality_change:.1%}"
        
        return {
            "recommendation": recommendation,
            "reason": reason,
            "quality_change": quality_change,
            "critical_change": critical_change,
            "meets_expectations": quality_change >= enhancement_config.get("expected_improvement", 0.0)
        }
    
    def run_full_incremental_suite(self):
        """Run the complete incremental enhancement testing suite."""
        logger.info("🚀 Starting Full Incremental Enhancement Testing")
        logger.info("=" * 60)
        
        # Step 1: Establish baseline
        baseline = self.run_baseline_test()
        
        if baseline['overall_score'] < 0.7:
            logger.error("❌ Baseline quality too low to proceed with enhancements")
            sys.exit(1)
        
        # Step 2: Test enhancements incrementally
        enhancement_order = ["bm25", "synonyms", "multi-source", "confidence"]
        results = []
        
        for enhancement in enhancement_order:
            logger.info(f"\n{'='*20} TESTING {enhancement.upper()} {'='*20}")
            
            result = self.test_enhancement(enhancement)
            results.append(result)
            
            if result["evaluation"]["recommendation"] == "ROLLBACK":
                logger.error(f"❌ {enhancement} failed - stopping incremental testing")
                break
            
            logger.info(f"✅ {enhancement} accepted - proceeding to next enhancement")
        
        # Final summary
        logger.info(f"\n🎯 INCREMENTAL TESTING COMPLETE")
        logger.info(f"Enhancements tested: {len(results)}")
        successful = [r for r in results if r["evaluation"]["recommendation"] == "ACCEPT"]
        logger.info(f"Successful enhancements: {len(successful)}")
        
        return results

def main():
    parser = argparse.ArgumentParser(description="Incremental Enhancement Testing")
    parser.add_argument("--baseline", action="store_true", 
                       help="Establish baseline quality metrics")
    parser.add_argument("--test-enhancement", 
                       choices=["bm25", "synonyms", "multi-source", "confidence"],
                       help="Test a specific enhancement")
    parser.add_argument("--full-suite", action="store_true",
                       help="Run complete incremental testing suite")
    
    args = parser.parse_args()
    
    tester = IncrementalTester()
    
    if args.baseline:
        tester.run_baseline_test()
    elif args.test_enhancement:
        tester.test_enhancement(args.test_enhancement)
    elif args.full_suite:
        tester.run_full_incremental_suite()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()