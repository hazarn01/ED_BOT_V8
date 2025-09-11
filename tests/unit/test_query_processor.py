"""
Unit tests for QueryProcessor - the main orchestrator.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ai.gpt_oss_client import GPTOSSClient
from models.query_types import QueryType
from models.schemas import QueryResponse
from pipeline.query_processor import QueryProcessor
from services.contact_service import ContactService


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = Mock()
    redis_mock.setex = Mock()
    redis_mock.get = Mock(return_value=None)
    return redis_mock


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    return Mock(spec=GPTOSSClient)


@pytest.fixture
def mock_contact_service():
    """Mock contact service."""
    return Mock(spec=ContactService)


@pytest.fixture
def query_processor(mock_db, mock_redis, mock_llm_client, mock_contact_service):
    """QueryProcessor instance with mocked dependencies."""
    return QueryProcessor(
        db=mock_db,
        redis=mock_redis,
        llm_client=mock_llm_client,
        contact_service=mock_contact_service,
    )


class TestQueryProcessor:
    """Test QueryProcessor functionality."""

    @pytest.mark.asyncio
    async def test_process_query_contact_type(self, query_processor):
        """Test processing a CONTACT query."""
        # Mock classifier to return CONTACT type
        with patch.object(query_processor.classifier, "classify") as mock_classify:
            mock_classify.return_value = Mock(
                query_type=QueryType.CONTACT, confidence=0.95
            )

            # Mock validator to return valid
            with patch.object(
                query_processor.validator, "validate_query"
            ) as mock_validate:
                mock_validate.return_value = Mock(is_valid=True, warnings=None)

                # Mock router response
                with patch.object(query_processor.router, "route_query") as mock_route:
                    mock_route.return_value = {
                        "response": "Dr. Sarah Johnson is on-call for cardiology. Phone: 555-123-4567",
                        "sources": ["amion_schedule"],
                        "contact_info": {
                            "name": "Dr. Sarah Johnson",
                            "phone": "555-123-4567",
                        },
                    }

                    # Execute
                    result = await query_processor.process_query(
                        "who is on call for cardiology"
                    )

                    # Verify
                    assert isinstance(result, QueryResponse)
                    assert result.query_type == QueryType.CONTACT.value
                    assert result.confidence == 0.95
                    assert "Dr. Sarah Johnson" in result.response
                    assert "amion_schedule" in result.sources

    @pytest.mark.asyncio
    async def test_process_query_form_type(self, query_processor):
        """Test processing a FORM query."""
        with patch.object(query_processor.classifier, "classify") as mock_classify:
            mock_classify.return_value = Mock(
                query_type=QueryType.FORM, confidence=0.92
            )

            with patch.object(
                query_processor.validator, "validate_query"
            ) as mock_validate:
                mock_validate.return_value = Mock(is_valid=True, warnings=None)

                with patch.object(query_processor.router, "route_query") as mock_route:
                    mock_route.return_value = {
                        "response": "Found the Blood Transfusion Consent Form. Click the link below to download.",
                        "sources": ["blood_transfusion_consent.pdf"],
                        "pdf_links": [
                            {
                                "filename": "blood_transfusion_consent.pdf",
                                "display_name": "Blood Transfusion Consent Form",
                                "url": "/api/v1/documents/123/download",
                            }
                        ],
                    }

                    result = await query_processor.process_query(
                        "show me the blood transfusion form"
                    )

                    assert result.query_type == QueryType.FORM.value
                    assert result.pdf_links is not None
                    assert len(result.pdf_links) == 1
                    assert "blood_transfusion_consent.pdf" in result.sources

    @pytest.mark.asyncio
    async def test_process_query_invalid_safety(self, query_processor):
        """Test processing a query that fails safety validation."""
        with patch.object(query_processor.classifier, "classify") as mock_classify:
            mock_classify.return_value = Mock(
                query_type=QueryType.DOSAGE, confidence=0.85
            )

            with patch.object(
                query_processor.validator, "validate_query"
            ) as mock_validate:
                mock_validate.return_value = Mock(
                    is_valid=False,
                    warnings=["Query contains unsafe medical advice request"],
                )

                result = await query_processor.process_query("dangerous medical query")

                assert result.confidence == 0.0
                assert "safety concerns" in result.response.lower()
                assert result.warnings == [
                    "Query contains unsafe medical advice request"
                ]

    @pytest.mark.asyncio
    async def test_process_query_system_error(self, query_processor):
        """Test processing when system error occurs."""
        with patch.object(query_processor.classifier, "classify") as mock_classify:
            mock_classify.side_effect = Exception("System error")

            result = await query_processor.process_query("test query")

            assert result.query_type == "unknown"
            assert result.confidence == 0.0
            assert "error" in result.response.lower()
            assert result.warnings == ["System error occurred"]

    @pytest.mark.asyncio
    async def test_caching_behavior_form_query(self, query_processor, mock_redis):
        """Test that FORM queries are not cached."""
        with patch.object(query_processor.classifier, "classify") as mock_classify:
            mock_classify.return_value = Mock(
                query_type=QueryType.FORM, confidence=0.95
            )

            with patch.object(
                query_processor.validator, "validate_query"
            ) as mock_validate:
                mock_validate.return_value = Mock(is_valid=True, warnings=None)

                with patch.object(query_processor.router, "route_query") as mock_route:
                    mock_route.return_value = {"response": "Form found", "sources": []}

                    await query_processor.process_query("form query")

                    # Verify no caching attempted for FORM queries
                    mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_caching_behavior_protocol_query(self, query_processor, mock_redis):
        """Test that PROTOCOL queries are cached with appropriate TTL."""
        with patch.object(query_processor.classifier, "classify") as mock_classify:
            mock_classify.return_value = Mock(
                query_type=QueryType.PROTOCOL, confidence=0.95
            )

            with patch.object(
                query_processor.validator, "validate_query"
            ) as mock_validate:
                mock_validate.return_value = Mock(is_valid=True, warnings=None)

                with patch.object(query_processor.router, "route_query") as mock_route:
                    mock_route.return_value = {
                        "response": "Protocol found",
                        "sources": [],
                    }

                    await query_processor.process_query("protocol query")

                    # Verify caching with 1 hour TTL for protocols
                    mock_redis.setex.assert_called_once()
                    call_args = mock_redis.setex.call_args
                    assert call_args[0][1] == 3600  # 1 hour TTL

    @pytest.mark.asyncio
    async def test_get_on_call_contact_success(
        self, query_processor, mock_contact_service
    ):
        """Test successful contact lookup."""
        from models.schemas import ContactInfo, ContactResponse

        expected_response = ContactResponse(
            specialty="cardiology",
            contacts=[
                ContactInfo(
                    name="Dr. Sarah Johnson",
                    role="Attending Cardiologist",
                    phone="555-123-4567",
                    pager="555-987-6543",
                    coverage="on-call",
                    department="Cardiology",
                )
            ],
            updated_at=datetime.utcnow(),
            source="amion",
        )

        mock_contact_service.get_on_call.return_value = expected_response

        result = await query_processor.get_on_call_contact("cardiology")

        assert result == expected_response
        mock_contact_service.get_on_call.assert_called_once_with("cardiology")

    @pytest.mark.asyncio
    async def test_get_on_call_contact_failure(
        self, query_processor, mock_contact_service
    ):
        """Test contact lookup failure."""
        mock_contact_service.get_on_call.side_effect = Exception(
            "Contact service error"
        )

        with pytest.raises(Exception, match="Contact service error"):
            await query_processor.get_on_call_contact("cardiology")

    @pytest.mark.asyncio
    async def test_validate_query(self, query_processor):
        """Test query validation."""
        with patch.object(query_processor.validator, "validate_query") as mock_validate:
            mock_validate.return_value = Mock(
                is_valid=True, warnings=None, confidence=0.95
            )

            result = await query_processor.validate_query("safe medical query")

            assert result.is_valid is True
            assert result.confidence == 0.95
            mock_validate.assert_called_once_with("safe medical query")


if __name__ == "__main__":
    pytest.main([__file__])
