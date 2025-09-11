"""
Integration tests for Streamlit demo application.

Tests connectivity and basic functionality of the Streamlit UI.
"""

import time

import pytest
import requests


class TestStreamlitIntegration:
    """Test Streamlit app integration with API"""
    
    STREAMLIT_URL = "http://localhost:8501"
    API_URL = "http://localhost:8001"
    
    @pytest.fixture(autouse=True)
    def wait_for_services(self):
        """Wait for services to be ready"""
        # Wait for API
        max_retries = 30
        for _ in range(max_retries):
            try:
                response = requests.get(f"{self.API_URL}/health", timeout=1)
                if response.status_code == 200:
                    break
            except (requests.exceptions.RequestException, ConnectionError):
                pass
            time.sleep(1)
        
        # Wait for Streamlit
        for _ in range(max_retries):
            try:
                response = requests.get(f"{self.STREAMLIT_URL}/_stcore/health", timeout=1)
                if response.status_code == 200:
                    break
            except (requests.exceptions.RequestException, ConnectionError):
                pass
            time.sleep(1)
    
    def test_streamlit_health(self):
        """Test that Streamlit app is accessible"""
        try:
            response = requests.get(f"{self.STREAMLIT_URL}/_stcore/health", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("Streamlit not running - run 'make up-ui' first")
    
    def test_streamlit_main_page(self):
        """Test that main page loads"""
        try:
            response = requests.get(self.STREAMLIT_URL, timeout=10)
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
        except requests.exceptions.ConnectionError:
            pytest.skip("Streamlit not running - run 'make up-ui' first")
    
    def test_api_connectivity(self):
        """Test that Streamlit can connect to API"""
        # This tests the API directly, not through Streamlit
        # In a real test, you'd use Selenium or similar to test through UI
        try:
            response = requests.get(f"{self.API_URL}/health", timeout=5)
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running - run 'make up' first")
    
    def test_api_query_endpoint(self):
        """Test that API query endpoint works"""
        try:
            payload = {"query": "What is the STEMI protocol?"}
            response = requests.post(
                f"{self.API_URL}/api/v1/query",
                json=payload,
                timeout=30
            )
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "query_type" in data
            assert "confidence" in data
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running - run 'make up' first")
    
    def test_api_documents_endpoint(self):
        """Test that API documents endpoint works"""
        try:
            response = requests.get(f"{self.API_URL}/api/v1/documents", timeout=10)
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            if data:
                assert "filename" in data[0]
                assert "content_type" in data[0]
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running - run 'make up' first")
    
    def test_cache_stats_endpoint(self):
        """Test that cache stats endpoint works"""
        try:
            response = requests.get(f"{self.API_URL}/api/v1/cache/stats", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert "enabled" in data
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running - run 'make up' first")
    
    def test_cache_config_endpoint(self):
        """Test that cache config endpoint works"""
        try:
            response = requests.get(f"{self.API_URL}/api/v1/cache/config", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert "enabled" in data
            assert "cacheable_types" in data
            assert "never_cache_types" in data
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running - run 'make up' first")


class TestStreamlitFeatures:
    """Test specific Streamlit features"""
    
    STREAMLIT_URL = "http://localhost:8501"
    API_URL = "http://localhost:8001"
    
    def test_sample_queries(self):
        """Test that sample queries work through API"""
        sample_queries = [
            "What is the ED STEMI protocol?",
            "What are the criteria for sepsis?",
            "What is the dosage for metoprolol?",
        ]
        
        for query in sample_queries:
            try:
                payload = {"query": query}
                response = requests.post(
                    f"{self.API_URL}/api/v1/query",
                    json=payload,
                    timeout=30
                )
                assert response.status_code == 200
                data = response.json()
                assert "answer" in data
                assert len(data["answer"]) > 0
            except requests.exceptions.ConnectionError:
                pytest.skip("API not running - run 'make up' first")
    
    def test_query_types(self):
        """Test different query types"""
        query_type_examples = {
            "protocol": "What is the STEMI protocol?",
            "criteria": "What are the criteria for sepsis?",
            "dosage": "What is the dosage for metoprolol?",
            "summary": "Summarize the chest pain workup",
        }
        
        for expected_type, query in query_type_examples.items():
            try:
                payload = {"query": query}
                response = requests.post(
                    f"{self.API_URL}/api/v1/query",
                    json=payload,
                    timeout=30
                )
                assert response.status_code == 200
                data = response.json()
                # Check that query type is one of the expected types
                assert "query_type" in data
                # Note: actual type may differ from expected, this is just a basic test
            except requests.exceptions.ConnectionError:
                pytest.skip("API not running - run 'make up' first")


@pytest.mark.skip(reason="Requires Selenium for full UI testing")
class TestStreamlitUI:
    """Full UI tests using Selenium (requires additional setup)"""
    
    def test_query_submission(self):
        """Test submitting a query through the UI"""
        # This would require Selenium WebDriver setup
        pass
    
    def test_cache_management_page(self):
        """Test cache management page functionality"""
        # This would require Selenium WebDriver setup
        pass
    
    def test_advanced_search_page(self):
        """Test advanced search comparison"""
        # This would require Selenium WebDriver setup
        pass


if __name__ == "__main__":
    # Run basic connectivity tests
    print("Testing Streamlit integration...")
    
    # Check Streamlit health
    try:
        response = requests.get("http://localhost:8501/_stcore/health", timeout=5)
        if response.status_code == 200:
            print("✅ Streamlit is healthy")
        else:
            print("❌ Streamlit health check failed")
    except (requests.exceptions.RequestException, ConnectionError, Exception):
        print("❌ Streamlit is not accessible - run 'make up-ui' first")
    
    # Check API health
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is healthy")
        else:
            print("❌ API health check failed")
    except (requests.exceptions.RequestException, ConnectionError, Exception):
        print("❌ API is not accessible - run 'make up' first")
    
    # Test a sample query
    try:
        payload = {"query": "What is the STEMI protocol?"}
        response = requests.post(
            "http://localhost:8001/api/v1/query",
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            print("✅ Sample query successful")
        else:
            print("❌ Sample query failed")
    except (requests.exceptions.RequestException, ConnectionError, Exception):
        print("❌ Could not execute sample query")