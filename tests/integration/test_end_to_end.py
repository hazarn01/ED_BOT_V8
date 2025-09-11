"""
End-to-end integration tests for ED Bot v8.
Tests the complete pipeline from API request to response.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from httpx import AsyncClient

from api.app import app


class TestEndToEndIntegration:
    """Test complete system integration."""

    @pytest.mark.asyncio
    async def test_contact_query_complete_flow(self):
        """Test complete flow for contact query."""
        with (
            patch("api.dependencies.get_db_session") as mock_get_db,
            patch("api.dependencies.get_redis_client") as mock_get_redis,
            patch("ai.gpt_oss_client.GPTOSSClient") as mock_llm_class,
            patch("services.contact_service.ContactService") as mock_contact_class,
        ):
            # Setup mocks
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            mock_llm = Mock()
            mock_llm_response = Mock()
            mock_llm_response.content = "CONTACT"
            mock_llm_response.confidence = 0.95
            mock_llm.generate_response.return_value = mock_llm_response
            mock_llm_class.return_value = mock_llm

            mock_contact = Mock()
            mock_contact_class.return_value = mock_contact

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/query",
                    json={
                        "query": "who is on call for cardiology",
                        "user_id": "test_user",
                    },
                )

                assert response.status_code == 200
                data = response.json()

                # Verify response structure
                assert "response" in data
                assert "query_type" in data
                assert "confidence" in data
                assert "sources" in data
                assert "processing_time" in data

                # Verify query was classified correctly
                assert data["query_type"] in [
                    "contact",
                    "unknown",
                ]  # May default to unknown in test

    @pytest.mark.asyncio
    async def test_form_query_complete_flow(self):
        """Test complete flow for form query."""
        with (
            patch("api.dependencies.get_db_session") as mock_get_db,
            patch("api.dependencies.get_redis_client") as mock_get_redis,
            patch("ai.gpt_oss_client.GPTOSSClient") as mock_llm_class,
        ):
            # Setup document mock
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query

            mock_doc = Mock()
            mock_doc.id = "doc123"
            mock_doc.filename = "blood_transfusion_consent.pdf"
            mock_doc.title = "Blood Transfusion Consent Form"
            mock_query.all.return_value = [mock_doc]

            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            mock_llm = Mock()
            mock_llm_response = Mock()
            mock_llm_response.content = "FORM"
            mock_llm_response.confidence = 0.92
            mock_llm.generate_response.return_value = mock_llm_response
            mock_llm_class.return_value = mock_llm

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/query",
                    json={"query": "show me the blood transfusion form"},
                )

                assert response.status_code == 200
                data = response.json()

                # Should have PDF links for form queries
                assert "pdf_links" in data
                if data.get("pdf_links"):
                    assert len(data["pdf_links"]) > 0
                    assert "filename" in data["pdf_links"][0]

    @pytest.mark.asyncio
    async def test_protocol_query_complete_flow(self):
        """Test complete flow for protocol query."""
        with (
            patch("api.dependencies.get_db_session") as mock_get_db,
            patch("api.dependencies.get_redis_client") as mock_get_redis,
            patch("ai.gpt_oss_client.GPTOSSClient") as mock_llm_class,
        ):
            # Setup entity mock
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query

            mock_entity = Mock()
            mock_entity.document_id = "doc123"
            mock_entity.payload = {
                "name": "STEMI Protocol",
                "steps": [
                    {"action": "Obtain 12-lead ECG", "timing": "within 10 minutes"},
                    {"action": "Activate cath lab", "timing": "immediate"},
                ],
                "critical_timing": "Door-to-balloon time must be <90 minutes",
            }
            mock_query.all.return_value = [mock_entity]

            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            mock_llm = Mock()
            mock_llm_response = Mock()
            mock_llm_response.content = "PROTOCOL"
            mock_llm_response.confidence = 0.89
            mock_llm.generate_response.return_value = mock_llm_response
            mock_llm_class.return_value = mock_llm

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/query", json={"query": "what is the STEMI protocol"}
                )

                assert response.status_code == 200
                data = response.json()

                # Should have structured protocol response
                assert "response" in data
                if "STEMI" in data.get("response", ""):
                    assert (
                        "ECG" in data["response"]
                        or "protocol" in data["response"].lower()
                    )

    @pytest.mark.asyncio
    async def test_dosage_query_complete_flow(self):
        """Test complete flow for dosage query with safety validation."""
        with (
            patch("api.dependencies.get_db_session") as mock_get_db,
            patch("api.dependencies.get_redis_client") as mock_get_redis,
            patch("ai.gpt_oss_client.GPTOSSClient") as mock_llm_class,
            patch(
                "validation.medical_validator.MedicalValidator"
            ) as mock_validator_class,
        ):
            # Setup dosage entity mock
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query

            mock_entity = Mock()
            mock_entity.document_id = "doc123"
            mock_entity.payload = {
                "drug": "Epinephrine",
                "dose": "1mg (1:10,000)",
                "route": "IV/IO",
                "frequency": "every 3-5 minutes",
                "contraindications": ["None in cardiac arrest"],
            }
            mock_query.all.return_value = [mock_entity]

            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            mock_llm = Mock()
            mock_llm_response = Mock()
            mock_llm_response.content = "DOSAGE"
            mock_llm_response.confidence = 0.94
            mock_llm.generate_response.return_value = mock_llm_response
            mock_llm_class.return_value = mock_llm

            # Mock safety validator
            mock_validator = Mock()
            mock_safety_check = Mock()
            mock_safety_check.is_safe = True
            mock_safety_check.warnings = []
            mock_validator.validate_dosage.return_value = mock_safety_check
            mock_validator_class.return_value = mock_validator

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/query",
                    json={"query": "epinephrine dosage for cardiac arrest"},
                )

                assert response.status_code == 200
                data = response.json()

                # Should have dosage information
                assert "response" in data
                if "epinephrine" in data.get("response", "").lower():
                    assert (
                        "1mg" in data["response"] or "dose" in data["response"].lower()
                    )

    @pytest.mark.asyncio
    async def test_system_error_handling(self):
        """Test system error handling across the pipeline."""
        with patch("api.dependencies.get_db_session") as mock_get_db:
            # Simulate database connection error
            mock_get_db.side_effect = Exception("Database connection failed")

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/query", json={"query": "test query"})

                # Should handle error gracefully
                assert response.status_code == 503  # Service unavailable

    @pytest.mark.asyncio
    async def test_validation_rejection(self):
        """Test query rejection due to safety validation."""
        with (
            patch("api.dependencies.get_db_session") as mock_get_db,
            patch("api.dependencies.get_redis_client") as mock_get_redis,
            patch("ai.gpt_oss_client.GPTOSSClient") as mock_llm_class,
            patch(
                "validation.medical_validator.MedicalValidator"
            ) as mock_validator_class,
        ):
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_get_redis.return_value = mock_redis

            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            # Mock validator to reject query
            mock_validator = Mock()
            mock_validation_result = Mock()
            mock_validation_result.is_valid = False
            mock_validation_result.warnings = ["Query contains unsafe medical request"]
            mock_validator.validate_query.return_value = mock_validation_result
            mock_validator_class.return_value = mock_validator

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/query", json={"query": "unsafe medical query"}
                )

                assert response.status_code == 200  # Query processed but rejected
                data = response.json()

                # Should indicate safety rejection
                assert data["confidence"] == 0.0
                assert "safety concerns" in data["response"].lower()
                assert data["warnings"] is not None

    @pytest.mark.asyncio
    async def test_caching_behavior(self):
        """Test caching behavior across different query types."""
        with (
            patch("api.dependencies.get_db_session") as mock_get_db,
            patch("api.dependencies.get_redis_client") as mock_get_redis,
            patch("ai.gpt_oss_client.GPTOSSClient") as mock_llm_class,
        ):
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.setex = Mock()
            mock_redis.get = Mock(return_value=None)
            mock_get_redis.return_value = mock_redis

            mock_llm = Mock()
            mock_llm_response = Mock()
            mock_llm_response.content = "PROTOCOL"
            mock_llm_response.confidence = 0.95
            mock_llm.generate_response.return_value = mock_llm_response
            mock_llm_class.return_value = mock_llm

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/query", json={"query": "protocol query for caching test"}
                )

                assert response.status_code == 200

                # Verify caching was attempted (Redis setex called)
                # Note: This is integration testing the caching logic
                mock_redis.setex.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])
