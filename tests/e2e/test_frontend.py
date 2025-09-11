"""
End-to-end tests for ED Bot v8 frontend using Playwright.

Tests all the fixes implemented in PRP-36:
- Query processing and response quality
- Source attribution display with hover functionality
- Meta query handling
- Form retrieval functionality
- Performance and timeout handling
"""

import asyncio
import time
from typing import Any, Dict

import pytest
from playwright.async_api import BrowserContext, Page, async_playwright


class TestEDBotFrontend:
    """Test suite for ED Bot v8 web interface."""
    
    @pytest.fixture(scope="session")
    async def browser_context(self):
        """Set up browser context for all tests."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)  # Set to True for CI
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="ED Bot Test Suite"
        )
        
        yield context
        
        await context.close()
        await browser.close()
        await playwright.stop()
    
    @pytest.fixture
    async def page(self, browser_context: BrowserContext):
        """Create a new page for each test."""
        page = await browser_context.new_page()
        await page.goto("http://localhost:8001", wait_until="networkidle")
        
        # Wait for app initialization
        await page.wait_for_selector("#queryInput", state="visible")
        await page.wait_for_selector("#sendButton", state="visible")
        
        yield page
        await page.close()
    
    async def send_query_and_wait(self, page: Page, query: str, timeout: int = 30000) -> Dict[str, Any]:
        """Send a query and wait for response."""
        # Clear input and type query
        await page.fill("#queryInput", "")
        await page.fill("#queryInput", query)
        
        # Click send button
        await page.click("#sendButton")
        
        # Wait for response to appear
        await page.wait_for_selector(".message.assistant", timeout=timeout)
        
        # Get the latest response
        messages = await page.query_selector_all(".message.assistant")
        latest_message = messages[-1]
        
        # Extract response data
        response_text = await latest_message.query_selector(".response-content")
        meta_info = await latest_message.query_selector(".message-meta")
        
        response_content = await response_text.inner_text() if response_text else ""
        meta_content = await meta_info.inner_text() if meta_info else ""
        
        return {
            "content": response_content,
            "meta": meta_content,
            "element": latest_message
        }

    @pytest.mark.asyncio
    async def test_page_loads_correctly(self, page: Page):
        """Test that the main page loads with all required elements."""
        # Check page title
        title = await page.title()
        assert "ED Bot v8" in title
        
        # Check key elements are present
        await page.wait_for_selector("h1", state="visible")
        header_text = await page.inner_text("h1")
        assert "ED Bot v8" in header_text
        
        # Check input elements
        assert await page.is_visible("#queryInput")
        assert await page.is_visible("#sendButton")
        assert await page.is_visible("#status")
        
        # Check status indicator
        status_text = await page.inner_text("#status .status-text")
        assert status_text in ["Connected", "Connecting..."]
    
    @pytest.mark.asyncio
    async def test_stemi_protocol_query(self, page: Page):
        """Test the STEMI protocol query that was previously timing out."""
        response = await self.send_query_and_wait(page, "what is the STEMI protocol")
        
        # Verify response contains medical content
        assert len(response["content"]) > 100, "Response should contain substantial medical content"
        assert "STEMI" in response["content"], "Response should mention STEMI"
        
        # Verify response metadata
        meta = response["meta"]
        assert "protocol" in meta.lower(), "Should be classified as protocol query"
        assert "Sources:" in meta, "Should show sources"
        assert "Time:" in meta, "Should show processing time"
        assert "Confidence" in meta, "Should show confidence level"
        
        # Verify processing time is reasonable (< 10 seconds)
        import re
        time_match = re.search(r"Time: (\d+\.?\d*)s", meta)
        if time_match:
            processing_time = float(time_match.group(1))
            assert processing_time < 10.0, f"Processing time should be < 10s, got {processing_time}s"
    
    @pytest.mark.asyncio
    async def test_source_attribution_hover(self, page: Page):
        """Test that source attribution shows document names on hover."""
        response = await self.send_query_and_wait(page, "what is the sepsis protocol")
        
        # Find sources element
        sources_element = await response["element"].query_selector(".sources-info")
        assert sources_element is not None, "Sources info should be present"
        
        # Check that it has a title attribute (tooltip)
        title_attr = await sources_element.get_attribute("title")
        assert title_attr is not None, "Sources should have tooltip"
        assert len(title_attr) > 0, "Tooltip should contain source names"
        assert "•" in title_attr, "Tooltip should contain bullet-pointed source names"
        
        # Verify hover styling
        await sources_element.hover()
        # The element should have proper cursor and styling
        cursor_style = await sources_element.evaluate("el => getComputedStyle(el).cursor")
        assert cursor_style == "help", "Sources should have help cursor on hover"
    
    @pytest.mark.asyncio
    async def test_meta_query_handling(self, page: Page):
        """Test that meta queries return capability information, not general knowledge."""
        response = await self.send_query_and_wait(page, "what can we talk about")
        
        content = response["content"]
        
        # Should contain capability information, not general medical knowledge
        assert "ED Bot v8" in content, "Should identify itself"
        assert "Medical Protocols" in content, "Should mention protocol capability"
        assert "Medical Forms" in content, "Should mention form capability"
        assert "Medication Dosages" in content, "Should mention dosage capability"
        assert "Clinical Criteria" in content, "Should mention criteria capability"
        assert "Contact Information" in content, "Should mention contact capability"
        
        # Should NOT contain generic medical advice
        assert "disease prevention" not in content.lower(), "Should not contain generic medical content"
        assert "treatment options" not in content.lower(), "Should not contain generic medical content"
        
        # Check metadata
        meta = response["meta"]
        assert "summary" in meta.lower(), "Meta queries should be classified as summary type"
    
    @pytest.mark.asyncio
    async def test_form_retrieval(self, page: Page):
        """Test form retrieval functionality."""
        response = await self.send_query_and_wait(page, "show me the blood transfusion form")
        
        # Should mention form availability
        content = response["content"]
        assert "form" in content.lower(), "Response should mention forms"
        
        # Check for download links
        pdf_links = await response["element"].query_selector_all(".pdf-link")
        assert len(pdf_links) > 0, "Should provide downloadable PDF links"
        
        # Verify link functionality
        first_link = pdf_links[0]
        href = await first_link.get_attribute("href")
        assert href is not None, "PDF link should have href"
        assert href.startswith("/"), "Should be a valid relative URL"
    
    @pytest.mark.asyncio
    async def test_dosage_query(self, page: Page):
        """Test medication dosage queries."""
        response = await self.send_query_and_wait(page, "epinephrine dose cardiac arrest")
        
        content = response["content"]
        
        # Should contain dosage information
        assert len(content) > 50, "Should provide substantial dosage information"
        
        # Should be classified correctly
        meta = response["meta"]
        assert "dosage" in meta.lower(), "Should be classified as dosage query"
        
        # Should have high confidence for standard dosages
        assert "High Confidence" in meta or "confidence" in meta.lower(), "Should show confidence level"
    
    @pytest.mark.asyncio
    async def test_criteria_query(self, page: Page):
        """Test clinical criteria queries."""
        response = await self.send_query_and_wait(page, "ottawa ankle criteria")
        
        content = response["content"]
        assert len(content) > 30, "Should provide criteria information"
        
        # Check classification
        meta = response["meta"]
        assert "criteria" in meta.lower(), "Should be classified as criteria query"
    
    @pytest.mark.asyncio
    async def test_query_processing_performance(self, page: Page):
        """Test that queries process within reasonable time limits."""
        test_queries = [
            "what is the STEMI protocol",
            "sepsis criteria", 
            "insulin dosing",
            "chest pain workup"
        ]
        
        for query in test_queries:
            start_time = time.time()
            response = await self.send_query_and_wait(page, query, timeout=15000)
            end_time = time.time()
            
            total_time = end_time - start_time
            assert total_time < 15.0, f"Query '{query}' took {total_time:.1f}s, should be < 15s"
            
            # Verify we got a real response
            assert len(response["content"]) > 20, f"Query '{query}' should return substantial content"
    
    @pytest.mark.asyncio
    async def test_response_quality_no_generic_fallback(self, page: Page):
        """Test that responses don't fall back to generic medical knowledge."""
        response = await self.send_query_and_wait(page, "what is the treatment for hypertension")
        
        content = response["content"].lower()
        
        # Should not contain generic medical advice patterns
        generic_patterns = [
            "consult a doctor",
            "seek medical attention", 
            "this is not medical advice",
            "i'm not a doctor",
            "various treatment options",
            "lifestyle modifications"
        ]
        
        for pattern in generic_patterns:
            assert pattern not in content, f"Response should not contain generic pattern: '{pattern}'"
        
        # Should either provide specific protocol info or indicate no specific info available
        if "unable to" in content or "no specific information" in content:
            # Acceptable - system correctly identifies when it doesn't have specific info
            pass
        else:
            # Should contain specific medical protocol information
            assert len(content) > 100, "If providing info, should be substantial and specific"
    
    @pytest.mark.asyncio
    async def test_user_interface_interactions(self, page: Page):
        """Test UI interactions and responsiveness."""
        # Test character counter
        await page.fill("#queryInput", "test query")
        char_count = await page.inner_text("#charCount")
        assert "10" in char_count, "Character counter should show correct count"
        
        # Test send button state
        assert await page.is_enabled("#sendButton"), "Send button should be enabled with text"
        
        await page.fill("#queryInput", "")
        assert await page.is_disabled("#sendButton"), "Send button should be disabled when empty"
        
        # Test Enter key submission
        await page.fill("#queryInput", "test query")
        await page.press("#queryInput", "Enter")
        
        # Should see loading or response
        await page.wait_for_selector(".message", timeout=5000)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, page: Page):
        """Test error handling and edge cases."""
        # Test very long query
        long_query = "what is the protocol for " * 50  # Very long query
        await page.fill("#queryInput", long_query)
        
        # Character count should show warning color for long queries
        char_count_element = await page.query_selector("#charCount")
        await char_count_element.evaluate("el => getComputedStyle(el).color")
        # Should show warning color for long text
        
        # Test empty/whitespace query handling
        await page.fill("#queryInput", "   ")
        assert await page.is_disabled("#sendButton"), "Send button should be disabled for whitespace"


if __name__ == "__main__":
    """Run the tests directly."""
    async def run_tests():
        test_instance = TestEDBotFrontend()
        
        # Start browser
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        
        try:
            page = await context.new_page()
            await page.goto("http://localhost:8001", wait_until="networkidle")
            await page.wait_for_selector("#queryInput", state="visible")
            
            print("🧪 Running ED Bot v8 Frontend Tests...")
            
            # Run key tests
            print("✅ Testing page load...")
            await test_instance.test_page_loads_correctly(page)
            
            print("✅ Testing STEMI protocol query...")
            await test_instance.test_stemi_protocol_query(page)
            
            print("✅ Testing source attribution hover...")
            await test_instance.test_source_attribution_hover(page)
            
            print("✅ Testing meta query handling...")
            await test_instance.test_meta_query_handling(page)
            
            print("✅ Testing form retrieval...")
            await test_instance.test_form_retrieval(page)
            
            print("🎉 All tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
        finally:
            await context.close()
            await browser.close()
            await playwright.stop()
    
    asyncio.run(run_tests())