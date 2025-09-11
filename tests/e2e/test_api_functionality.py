"""
API-based tests for ED Bot v8 functionality.
Tests the fixes implemented in PRP-36 without requiring browser automation.
"""

import asyncio
import time
from typing import Any, Dict

import aiohttp


class TestEDBotAPI:
    """Test suite for ED Bot v8 API functionality."""
    
    BASE_URL = "http://localhost:8001"
    
    async def make_request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
        """Make HTTP request to the API."""
        url = f"{self.BASE_URL}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url) as response:
                    return await response.json()
            elif method == "POST":
                headers = {"Content-Type": "application/json"}
                async with session.post(url, json=data, headers=headers) as response:
                    return await response.json()
    
    async def test_health_check(self):
        """Test that the API is running and healthy."""
        print("🔍 Testing API health...")
        response = await self.make_request("/health")
        assert response["status"] == "healthy"
        assert response["service"] == "ed-bot-v8"
        print("✅ API health check passed")
    
    async def test_stemi_protocol_query(self):
        """Test the STEMI protocol query that was previously timing out."""
        print("🔍 Testing STEMI protocol query...")
        
        start_time = time.time()
        response = await self.make_request("/api/v1/query", "POST", {
            "query": "what is the STEMI protocol"
        })
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Verify response structure
        assert "response" in response
        assert "query_type" in response
        assert "confidence" in response
        assert "sources" in response
        assert "processing_time" in response
        
        # Verify content quality
        content = response["response"]
        assert len(content) > 100, "Response should contain substantial medical content"
        assert "STEMI" in content, "Response should mention STEMI"
        
        # Verify classification
        assert response["query_type"].lower() == "protocol", "Should be classified as protocol"
        
        # Verify performance
        assert processing_time < 15.0, f"Query took {processing_time:.1f}s, should be < 15s"
        
        # Verify sources are provided
        sources = response.get("sources", [])
        assert len(sources) > 0, "Should provide source attribution"
        
        print(f"✅ STEMI query test passed - {processing_time:.1f}s, {len(sources)} sources")
    
    async def test_meta_query_handling(self):
        """Test that meta queries return capability information."""
        print("🔍 Testing meta query handling...")
        
        response = await self.make_request("/api/v1/query", "POST", {
            "query": "what can we talk about"
        })
        
        content = response["response"]
        
        # Should contain capability information
        capability_keywords = [
            "ED Bot v8",
            "Medical Protocols", 
            "Medical Forms",
            "Medication Dosages",
            "Clinical Criteria",
            "Contact Information"
        ]
        
        found_keywords = [kw for kw in capability_keywords if kw in content]
        assert len(found_keywords) >= 4, f"Should mention key capabilities, found: {found_keywords}"
        
        # Should NOT contain generic medical advice
        generic_patterns = ["disease prevention", "treatment options", "surgical techniques"]
        for pattern in generic_patterns:
            assert pattern.lower() not in content.lower(), f"Should not contain generic pattern: {pattern}"
        
        print("✅ Meta query handling test passed")
    
    async def test_form_retrieval(self):
        """Test form retrieval functionality."""
        print("🔍 Testing form retrieval...")
        
        response = await self.make_request("/api/v1/query", "POST", {
            "query": "show me the blood transfusion form"
        })
        
        # Should be classified as form query
        assert response["query_type"].lower() == "form", "Should be classified as form"
        
        # Should provide form information
        content = response["response"]
        assert "form" in content.lower(), "Response should mention forms"
        
        # Check if PDF links are provided
        pdf_links = response.get("pdf_links", [])
        if len(pdf_links) > 0:
            # Verify PDF link structure
            first_link = pdf_links[0]
            assert "url" in first_link, "PDF link should have URL"
            assert "display_name" in first_link, "PDF link should have display name"
        
        print("✅ Form retrieval test passed")
    
    async def test_dosage_query(self):
        """Test medication dosage queries."""
        print("🔍 Testing dosage query...")
        
        response = await self.make_request("/api/v1/query", "POST", {
            "query": "epinephrine dose cardiac arrest"
        })
        
        # Should be classified as dosage
        assert response["query_type"].lower() == "dosage", "Should be classified as dosage"
        
        # Should provide dosage information
        content = response["response"]
        assert len(content) > 30, "Should provide dosage information"
        
        # Should have confidence information
        confidence = response.get("confidence", 0)
        assert confidence > 0, "Should have confidence score"
        
        print("✅ Dosage query test passed")
    
    async def test_criteria_query(self):
        """Test clinical criteria queries."""
        print("🔍 Testing criteria query...")
        
        response = await self.make_request("/api/v1/query", "POST", {
            "query": "ottawa ankle criteria"
        })
        
        # Should be classified as criteria
        assert response["query_type"].lower() == "criteria", "Should be classified as criteria"
        
        # Should provide criteria information
        content = response["response"]
        assert len(content) > 20, "Should provide criteria information"
        
        print("✅ Criteria query test passed")
    
    async def test_source_attribution(self):
        """Test that sources are properly attributed."""
        print("🔍 Testing source attribution...")
        
        response = await self.make_request("/api/v1/query", "POST", {
            "query": "what is the sepsis protocol"
        })
        
        sources = response.get("sources", [])
        assert len(sources) > 0, "Should provide sources"
        
        # Sources should be document names, not generic references
        for source in sources:
            assert isinstance(source, str), "Source should be string"
            assert len(source) > 5, "Source name should be meaningful"
            assert "Source:" not in source, "Should not contain generic 'Source:' prefix"
        
        print(f"✅ Source attribution test passed - {len(sources)} sources found")
    
    async def test_query_performance_batch(self):
        """Test performance across multiple query types."""
        print("🔍 Testing batch query performance...")
        
        test_queries = [
            ("what is the STEMI protocol", "protocol"),
            ("sepsis criteria", "criteria"),
            ("insulin dosing DKA", "dosage"),
            ("chest pain workup", "summary"),
            ("blood transfusion form", "form")
        ]
        
        results = []
        
        for query, expected_type in test_queries:
            start_time = time.time()
            try:
                response = await self.make_request("/api/v1/query", "POST", {"query": query})
                end_time = time.time()
                processing_time = end_time - start_time
                
                results.append({
                    "query": query,
                    "expected_type": expected_type,
                    "actual_type": response.get("query_type", "unknown").lower(),
                    "processing_time": processing_time,
                    "response_length": len(response.get("response", "")),
                    "sources_count": len(response.get("sources", [])),
                    "confidence": response.get("confidence", 0)
                })
                
            except Exception as e:
                print(f"❌ Query failed: {query} - {e}")
                results.append({
                    "query": query,
                    "error": str(e),
                    "processing_time": time.time() - start_time
                })
        
        # Analyze results
        successful_queries = [r for r in results if "error" not in r]
        avg_processing_time = sum(r["processing_time"] for r in successful_queries) / len(successful_queries)
        
        print("✅ Batch performance test:")
        print(f"   - Successful queries: {len(successful_queries)}/{len(test_queries)}")
        print(f"   - Average processing time: {avg_processing_time:.1f}s")
        
        for result in successful_queries:
            classification_correct = result["actual_type"] == result["expected_type"]
            status = "✅" if classification_correct else "⚠️"
            print(f"   {status} {result['query'][:30]:<30} | {result['processing_time']:.1f}s | {result['sources_count']} sources")
        
        # Assertions
        assert len(successful_queries) >= len(test_queries) * 0.8, "At least 80% of queries should succeed"
        assert avg_processing_time < 10.0, f"Average processing time should be < 10s, got {avg_processing_time:.1f}s"
    
    async def test_response_quality_validation(self):
        """Test that responses meet quality standards."""
        print("🔍 Testing response quality validation...")
        
        test_cases = [
            {
                "query": "hypoglycemia treatment",
                "should_contain": ["glucose", "hypoglycemia"],
                "should_not_contain": ["consult a doctor", "this is not medical advice"]
            },
            {
                "query": "STEMI activation",
                "should_contain": ["STEMI"],
                "should_not_contain": ["i don't know", "seek immediate medical attention"]
            }
        ]
        
        for test_case in test_cases:
            response = await self.make_request("/api/v1/query", "POST", {
                "query": test_case["query"]
            })
            
            content = response["response"].lower()
            
            # Check required content
            for required in test_case["should_contain"]:
                assert required.lower() in content, f"Response should contain '{required}'"
            
            # Check prohibited content
            for prohibited in test_case["should_not_contain"]:
                assert prohibited.lower() not in content, f"Response should not contain '{prohibited}'"
        
        print("✅ Response quality validation passed")


async def run_all_tests():
    """Run all API tests."""
    print("🚀 Starting ED Bot v8 API Test Suite")
    print("=" * 50)
    
    tester = TestEDBotAPI()
    
    try:
        # Run tests in sequence
        await tester.test_health_check()
        await tester.test_stemi_protocol_query()
        await tester.test_meta_query_handling()
        await tester.test_form_retrieval()
        await tester.test_dosage_query()
        await tester.test_criteria_query()
        await tester.test_source_attribution()
        await tester.test_query_performance_batch()
        await tester.test_response_quality_validation()
        
        print("=" * 50)
        print("🎉 All tests passed! PRP-36 fixes are working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())