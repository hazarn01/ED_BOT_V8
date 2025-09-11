#!/usr/bin/env python3
"""
Deployment validation script for ED Bot v8.
Validates that all system components are working correctly.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeploymentValidator:
    """Validates ED Bot v8 deployment."""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.test_results = []
    
    def run_validation(self) -> bool:
        """Run complete deployment validation."""
        logger.info("🚀 Starting ED Bot v8 deployment validation...")
        
        tests = [
            ("Health Check", self.test_health_endpoint),
            ("Metrics Endpoint", self.test_metrics_endpoint),
            ("Contact Query", self.test_contact_query),
            ("Form Query", self.test_form_query), 
            ("Protocol Query", self.test_protocol_query),
            ("Dosage Query", self.test_dosage_query),
            ("Document List", self.test_document_list),
            ("Contact Lookup", self.test_contact_lookup),
            ("Document Search", self.test_document_search),
            ("Query Validation", self.test_query_validation),
            ("Error Handling", self.test_error_handling),
            ("Response Timing", self.test_response_timing)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                logger.info(f"Running test: {test_name}")
                success, message = test_func()
                
                if success:
                    logger.info(f"✅ {test_name}: PASSED - {message}")
                    passed += 1
                else:
                    logger.error(f"❌ {test_name}: FAILED - {message}")
                
                self.test_results.append({
                    "test": test_name,
                    "passed": success,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error(f"❌ {test_name}: ERROR - {str(e)}")
                self.test_results.append({
                    "test": test_name,
                    "passed": False,
                    "message": f"Exception: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        # Summary
        logger.info(f"\n📊 Validation Summary: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 All validation tests passed! Deployment is healthy.")
        else:
            logger.warning(f"⚠️ {total - passed} tests failed. Review deployment.")
        
        # Save results
        self.save_validation_report()
        
        return passed == total
    
    def test_health_endpoint(self) -> Tuple[bool, str]:
        """Test health endpoint."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    return True, f"API healthy, service: {data.get('service', 'unknown')}"
                else:
                    return False, f"API unhealthy: {data.get('status')}"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def test_metrics_endpoint(self) -> Tuple[bool, str]:
        """Test metrics endpoint."""
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "queries_processed" in data and "uptime" in data:
                    return True, f"Metrics available: {len(data)} fields"
                else:
                    return False, "Missing required metrics fields"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Request failed: {str(e)}"
    
    def test_contact_query(self) -> Tuple[bool, str]:
        """Test contact query processing."""
        try:
            payload = {
                "query": "who is on call for cardiology",
                "user_id": "validation_test"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/query",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["response", "query_type", "confidence", "sources", "processing_time"]
                
                if all(field in data for field in required_fields):
                    return True, f"Query type: {data['query_type']}, confidence: {data['confidence']:.2f}"
                else:
                    missing = [f for f in required_fields if f not in data]
                    return False, f"Missing fields: {missing}"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Query failed: {str(e)}"
    
    def test_form_query(self) -> Tuple[bool, str]:
        """Test form query processing."""
        try:
            payload = {
                "query": "show me the blood transfusion form",
                "user_id": "validation_test"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/query",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "pdf_links" in data and data.get("query_type") in ["form", "unknown"]:
                    return True, f"Form query processed, links: {len(data.get('pdf_links', []))}"
                else:
                    return True, f"Form query processed (type: {data.get('query_type')})"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Query failed: {str(e)}"
    
    def test_protocol_query(self) -> Tuple[bool, str]:
        """Test protocol query processing."""
        try:
            payload = {
                "query": "what is the STEMI protocol",
                "user_id": "validation_test"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/query",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return True, f"Protocol query processed (type: {data.get('query_type')})"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Query failed: {str(e)}"
    
    def test_dosage_query(self) -> Tuple[bool, str]:
        """Test dosage query processing."""
        try:
            payload = {
                "query": "epinephrine dosage for cardiac arrest",
                "user_id": "validation_test"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/query",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return True, f"Dosage query processed (type: {data.get('query_type')})"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Query failed: {str(e)}"
    
    def test_document_list(self) -> Tuple[bool, str]:
        """Test document listing endpoint."""
        try:
            response = requests.get(f"{self.base_url}/api/v1/documents", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return True, f"Found {len(data)} documents"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Request failed: {str(e)}"
    
    def test_contact_lookup(self) -> Tuple[bool, str]:
        """Test contact lookup endpoint."""
        try:
            response = requests.get(f"{self.base_url}/api/v1/contacts/cardiology", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "contacts" in data and "specialty" in data:
                    return True, f"Contact lookup successful for {data['specialty']}"
                else:
                    return False, "Missing required contact fields"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Request failed: {str(e)}"
    
    def test_document_search(self) -> Tuple[bool, str]:
        """Test document search endpoint."""
        try:
            response = requests.get(f"{self.base_url}/api/v1/search?q=protocol", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return True, f"Search returned {len(data)} results"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Search failed: {str(e)}"
    
    def test_query_validation(self) -> Tuple[bool, str]:
        """Test query validation endpoint."""
        try:
            payload = {"query": "test medical query"}
            
            response = requests.post(
                f"{self.base_url}/api/v1/validate",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if "is_valid" in data and "confidence" in data:
                    return True, f"Validation working, valid: {data['is_valid']}"
                else:
                    return False, "Missing validation fields"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Validation failed: {str(e)}"
    
    def test_error_handling(self) -> Tuple[bool, str]:
        """Test error handling."""
        try:
            # Test invalid endpoint
            response = requests.get(f"{self.base_url}/api/v1/nonexistent", timeout=5)
            
            if response.status_code == 404:
                return True, "404 errors handled correctly"
            else:
                return False, f"Expected 404, got {response.status_code}"
                
        except Exception as e:
            return False, f"Error test failed: {str(e)}"
    
    def test_response_timing(self) -> Tuple[bool, str]:
        """Test response timing requirements."""
        try:
            import time
            
            start_time = time.time()
            
            payload = {"query": "quick test query", "user_id": "timing_test"}
            response = requests.post(
                f"{self.base_url}/api/v1/query",
                json=payload,
                timeout=5
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            if response.status_code == 200:
                if response_time < 2.0:  # Under 2 seconds is good
                    return True, f"Response time: {response_time:.2f}s"
                else:
                    return False, f"Response too slow: {response_time:.2f}s"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Timing test failed: {str(e)}"
    
    def save_validation_report(self):
        """Save validation report to file."""
        try:
            report = {
                "validation_timestamp": datetime.utcnow().isoformat(),
                "base_url": self.base_url,
                "total_tests": len(self.test_results),
                "passed_tests": len([r for r in self.test_results if r["passed"]]),
                "failed_tests": len([r for r in self.test_results if not r["passed"]]),
                "results": self.test_results
            }
            
            report_path = Path(__file__).parent.parent / "validation_report.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"📝 Validation report saved to: {report_path}")
            
        except Exception as e:
            logger.warning(f"Failed to save validation report: {e}")

def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ED Bot v8 Deployment Validator")
    parser.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Base URL of the API to validate"
    )
    
    args = parser.parse_args()
    
    validator = DeploymentValidator(args.url)
    success = validator.run_validation()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())