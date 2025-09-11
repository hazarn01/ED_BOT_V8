#!/usr/bin/env python3
"""
Continuous Quality Monitor - Prevent regressions through real-time API testing
PRP-48 Implementation: Close the integration gap with continuous monitoring
"""

import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/quality_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ContinuousQualityMonitor:
    """Monitor API quality continuously to catch regressions within minutes."""
    
    def __init__(self, api_url: str = "http://localhost:8001/api/v1/query"):
        self.api_url = api_url
        self.critical_queries = [
            "what is the STEMI protocol",
            "standard levophed dosing", 
            "pediatric epinephrine dose",
            "sepsis lactate criteria",
            "RETU chest pain pathway",
            "hypoglycemia treatment"
        ]
        
        # Quality thresholds
        self.quality_threshold = 80  # Minimum acceptable quality score
        self.failure_threshold = 3   # Alert after 3 consecutive failures
        self.consecutive_failures = 0
        
        # Monitoring history
        self.quality_history = []
        self.last_alert_time = 0
        self.alert_cooldown = 300  # 5 minutes between alerts
    
    def test_query_quality(self, query: str) -> Dict[str, Any]:
        """Test a single query and return quality analysis."""
        try:
            response = requests.post(
                self.api_url,
                json={"query": query},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code != 200:
                return {
                    "query": query,
                    "error": f"HTTP {response.status_code}",
                    "quality_score": 0,
                    "timestamp": datetime.now().isoformat()
                }
            
            data = response.json()
            
            # Analyze response quality using same metrics as test_api_directly.py
            analysis = {
                "query": query,
                "has_response": bool(data.get("response")),
                "response_length": len(data.get("response", "")),
                "has_sources": len(data.get("sources", [])) > 0,
                "source_count": len(data.get("sources", [])),
                "confidence": data.get("confidence", 0),
                "query_type": data.get("query_type", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
            
            # Check for template responses (major quality issue)
            response_text = data.get("response", "").lower()
            template_phrases = [
                "available in epic",
                "at nursing station", 
                "contact through operator",
                "most forms available",
                "database lookup failed"
            ]
            analysis["is_template"] = any(phrase in response_text for phrase in template_phrases)
            
            # Check for medical content
            medical_indicators = ["mg", "ml", "dose", "protocol", "lactate", "mcg", "units", "pager"]
            analysis["has_medical_terms"] = any(term in response_text for term in medical_indicators)
            
            # Calculate quality score (0-100)
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
            
        except Exception as e:
            logger.error(f"Query test failed for '{query}': {e}")
            return {
                "query": query,
                "error": str(e),
                "quality_score": 0,
                "timestamp": datetime.now().isoformat()
            }
    
    def run_quality_check(self) -> Dict[str, Any]:
        """Run full quality check on all critical queries."""
        logger.info("🔍 Starting quality check...")
        
        results = []
        total_score = 0
        failed_queries = []
        
        for query in self.critical_queries:
            analysis = self.test_query_quality(query)
            results.append(analysis)
            
            quality = analysis.get("quality_score", 0)
            total_score += quality
            
            if quality < self.quality_threshold:
                failed_queries.append(query)
                logger.warning(f"❌ QUALITY ISSUE: '{query}' scored {quality}/100")
            else:
                logger.info(f"✅ '{query}' scored {quality}/100")
        
        # Calculate overall metrics
        average_quality = total_score / len(self.critical_queries) if self.critical_queries else 0
        failure_count = len(failed_queries)
        
        check_result = {
            "timestamp": datetime.now().isoformat(),
            "average_quality": average_quality,
            "failed_queries": failed_queries,
            "failure_count": failure_count,
            "total_queries": len(self.critical_queries),
            "success_rate": (len(self.critical_queries) - failure_count) / len(self.critical_queries) * 100,
            "results": results
        }
        
        # Track consecutive failures for alerting
        if failure_count > 0:
            self.consecutive_failures += 1
            logger.warning(f"⚠️ Consecutive failures: {self.consecutive_failures}")
        else:
            self.consecutive_failures = 0
            logger.info("✅ All queries passing quality check")
        
        # Store in history
        self.quality_history.append(check_result)
        
        # Keep only last 24 hours of history
        cutoff_time = time.time() - (24 * 3600)
        self.quality_history = [
            h for h in self.quality_history 
            if datetime.fromisoformat(h["timestamp"]).timestamp() > cutoff_time
        ]
        
        return check_result
    
    def should_send_alert(self, check_result: Dict[str, Any]) -> bool:
        """Determine if an alert should be sent."""
        current_time = time.time()
        
        # Alert conditions:
        # 1. Multiple consecutive failures
        # 2. Average quality drops below threshold
        # 3. Not in cooldown period
        
        if current_time - self.last_alert_time < self.alert_cooldown:
            return False  # Still in cooldown
        
        if self.consecutive_failures >= self.failure_threshold:
            return True
        
        if check_result["average_quality"] < self.quality_threshold:
            return True
            
        return False
    
    def send_alert(self, check_result: Dict[str, Any]):
        """Send quality degradation alert."""
        alert_message = f"""
🚨 ED Bot v8 Quality Alert 🚨

Time: {check_result['timestamp']}
Average Quality: {check_result['average_quality']:.1f}/100
Failed Queries: {check_result['failure_count']}/{check_result['total_queries']}
Success Rate: {check_result['success_rate']:.1f}%

Failed Queries:
{chr(10).join(f"• {query}" for query in check_result['failed_queries'])}

Consecutive Failures: {self.consecutive_failures}

Action Required: Check system status and investigate quality degradation.
"""
        
        # Log alert
        logger.critical("🚨 QUALITY ALERT TRIGGERED")
        logger.critical(alert_message)
        
        # Save alert to file for external monitoring
        alert_file = "/tmp/quality_alert.json"
        with open(alert_file, "w") as f:
            json.dump({
                "alert_time": check_result["timestamp"],
                "alert_message": alert_message,
                "check_result": check_result
            }, f, indent=2)
        
        logger.info(f"💾 Alert saved to {alert_file}")
        self.last_alert_time = time.time()
    
    def run_continuous_monitoring(self, check_interval: int = 300):
        """Run continuous monitoring with specified interval (seconds)."""
        logger.info(f"🚀 Starting continuous quality monitoring (every {check_interval}s)")
        logger.info(f"📊 Quality threshold: {self.quality_threshold}/100")
        logger.info(f"🔔 Alert after {self.failure_threshold} consecutive failures")
        logger.info(f"🎯 Monitoring {len(self.critical_queries)} critical queries")
        
        while True:
            try:
                # Run quality check
                check_result = self.run_quality_check()
                
                # Check if alert needed
                if self.should_send_alert(check_result):
                    self.send_alert(check_result)
                
                # Save monitoring data
                self.save_monitoring_data()
                
                # Wait for next check
                logger.info(f"⏱️ Next check in {check_interval} seconds...")
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("👋 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Monitoring error: {e}")
                logger.info("⏱️ Retrying in 60 seconds...")
                time.sleep(60)
    
    def save_monitoring_data(self):
        """Save monitoring data for analysis."""
        data_file = "/tmp/quality_monitoring_data.json"
        
        monitoring_data = {
            "last_updated": datetime.now().isoformat(),
            "consecutive_failures": self.consecutive_failures,
            "quality_history": self.quality_history[-50:]  # Last 50 checks
        }
        
        with open(data_file, "w") as f:
            json.dump(monitoring_data, f, indent=2)
    
    def run_single_check(self) -> Dict[str, Any]:
        """Run a single quality check and return results."""
        check_result = self.run_quality_check()
        
        # Print summary
        print("\n" + "="*60)
        print("📊 QUALITY CHECK SUMMARY")
        print("="*60)
        print(f"Average Quality: {check_result['average_quality']:.1f}/100")
        print(f"Success Rate: {check_result['success_rate']:.1f}%")
        print(f"Failed Queries: {check_result['failure_count']}")
        
        if check_result["failed_queries"]:
            print("\n❌ FAILING QUERIES:")
            for query in check_result["failed_queries"]:
                print(f"  • {query}")
        else:
            print("\n✅ ALL QUERIES PASSING!")
        
        return check_result

def main():
    """Main function with command line options."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ED Bot v8 Continuous Quality Monitor")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds (default: 300)")
    parser.add_argument("--threshold", type=int, default=80, help="Quality threshold (default: 80)")
    parser.add_argument("--api-url", default="http://localhost:8001/api/v1/query", help="API URL to monitor")
    
    args = parser.parse_args()
    
    monitor = ContinuousQualityMonitor(api_url=args.api_url)
    monitor.quality_threshold = args.threshold
    
    if args.continuous:
        monitor.run_continuous_monitoring(args.interval)
    else:
        # Single check
        monitor.run_single_check()

if __name__ == "__main__":
    main()