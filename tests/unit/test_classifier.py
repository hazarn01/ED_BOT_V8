"""
Unit tests for QueryClassifier.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.ai.gpt_oss_client import GPTOSSClient
from src.models.query_types import QueryType
from src.pipeline.classifier import QueryClassifier


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    return Mock(spec=GPTOSSClient)


@pytest.fixture
def classifier(mock_llm_client):
    """QueryClassifier instance with mocked LLM client."""
    return QueryClassifier(llm_client=mock_llm_client)


class TestQueryClassifier:
    """Test QueryClassifier functionality."""

    @pytest.mark.asyncio
    async def test_classify_contact_query(self, classifier, mock_llm_client):
        """Test classification of contact queries."""
        # Mock LLM response for contact query
        mock_response = Mock()
        mock_response.content = "CONTACT"
        mock_llm_client.generate = AsyncMock(return_value=mock_response)

        queries = [
            "who is on call for cardiology",
            "who is the on call cardiologist",
            "cardiology on call physician",
            "who should I call for cardiology consult",
        ]

        for query in queries:
            result = await classifier.classify_query(query)
            assert result.query_type == QueryType.CONTACT_LOOKUP
            assert result.confidence >= 0.6

    @pytest.mark.asyncio
    async def test_classify_form_query(self, classifier, mock_llm_client):
        """Test classification of form queries."""
        mock_response = Mock()
        mock_response.content = "FORM"
        mock_llm_client.generate = AsyncMock(return_value=mock_response)

        queries = [
            "show me the blood transfusion form",
            "I need the discharge instructions form",
            "consent form for procedure",
            "admission orders form",
        ]

        for query in queries:
            result = await classifier.classify_query(query)
            assert result.query_type == QueryType.FORM_RETRIEVAL
            assert result.confidence >= 0.6

    @pytest.mark.asyncio
    async def test_classify_protocol_query(self, classifier, mock_llm_client):
        """Test classification of protocol queries."""
        mock_response = Mock()
        mock_response.content = "PROTOCOL"
        mock_llm_client.generate = AsyncMock(return_value=mock_response)

        queries = [
            "what is the STEMI protocol",
            "stroke protocol steps",
            "sepsis management protocol",
            "trauma activation protocol",
        ]

        for query in queries:
            result = await classifier.classify_query(query)
            assert result.query_type == QueryType.PROTOCOL_STEPS
            assert result.confidence >= 0.6

    @pytest.mark.asyncio
    async def test_classify_criteria_query(self, classifier, mock_llm_client):
        """Test classification of criteria queries."""
        mock_response = Mock()
        mock_response.content = "CRITERIA"
        mock_llm_client.generate = AsyncMock(return_value=mock_response)

        queries = [
            "Ottawa ankle rules",
            "Wells score for PE",
            "Centor criteria for strep",
            "when to order head CT",
        ]

        for query in queries:
            result = await classifier.classify_query(query)
            assert result.query_type == QueryType.CRITERIA_CHECK
            assert result.confidence >= 0.6

    @pytest.mark.asyncio
    async def test_classify_dosage_query(self, classifier, mock_llm_client):
        """Test classification of dosage queries."""
        mock_response = Mock()
        mock_response.content = "DOSAGE"
        mock_llm_client.generate = AsyncMock(return_value=mock_response)

        queries = [
            "epinephrine dosage for cardiac arrest",
            "how much amiodarone to give",
            "pediatric acetaminophen dose",
            "insulin drip protocol dosing",
        ]

        for query in queries:
            result = await classifier.classify_query(query)
            assert result.query_type == QueryType.DOSAGE_LOOKUP
            assert result.confidence >= 0.6

    @pytest.mark.asyncio
    async def test_classify_summary_query(self, classifier, mock_llm_client):
        """Test classification of summary queries."""
        mock_response = Mock()
        mock_response.content = "SUMMARY"
        mock_llm_client.generate = AsyncMock(return_value=mock_response)

        queries = [
            "summarize chest pain workup",
            "overview of heart failure management",
            "what are the key points about pneumonia treatment",
        ]

        for query in queries:
            result = await classifier.classify_query(query)
            assert result.query_type == QueryType.SUMMARY_REQUEST
            assert result.confidence >= 0.6

    @pytest.mark.asyncio
    async def test_classify_low_confidence(self, classifier, mock_llm_client):
        """Test handling of low confidence classifications."""
        mock_response = Mock()
        mock_response.content = "UNKNOWN"
        mock_llm_client.generate = AsyncMock(return_value=mock_response)

        result = await classifier.classify_query("ambiguous unclear query")

        # Should default to SUMMARY for low confidence
        assert result.query_type == QueryType.SUMMARY_REQUEST
        assert result.confidence <= 0.5  # Will be adjusted based on implementation

    @pytest.mark.asyncio
    async def test_classify_llm_error(self, classifier, mock_llm_client):
        """Test handling of LLM errors."""
        mock_llm_client.generate = AsyncMock(side_effect=Exception("LLM error"))

        result = await classifier.classify_query("test query")

        assert result.query_type == QueryType.SUMMARY_REQUEST  # Default fallback
        assert result.confidence <= 0.5  # Will be adjusted based on fallback implementation

    @pytest.mark.asyncio
    async def test_classify_invalid_response(self, classifier, mock_llm_client):
        """Test handling of invalid LLM responses."""
        mock_response = Mock()
        mock_response.content = "INVALID_TYPE"
        mock_llm_client.generate = AsyncMock(return_value=mock_response)

        result = await classifier.classify_query("test query")

        assert result.query_type == QueryType.SUMMARY_REQUEST  # Default fallback
        assert result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_rule_based_classification(self, classifier):
        """Test that rule-based classification works for high-confidence patterns."""
        # High confidence contact query that should trigger rule-based classification
        result = await classifier.classify_query("who is on call for cardiology")
        
        assert result.query_type == QueryType.CONTACT_LOOKUP
        assert result.confidence > 0.8
        assert result.method in ["rules", "hybrid"]


if __name__ == "__main__":
    pytest.main([__file__])
