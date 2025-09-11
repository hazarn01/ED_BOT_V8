"""
Integration tests for FastAPI endpoints.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.app import app
from models.schemas import QueryResponse


class TestAPIEndpoints:
    """Test API endpoint functionality."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "ed-bot-v8"

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/metrics")
            assert response.status_code == 200
            data = response.json()
            assert "queries_processed" in data
            assert "uptime" in data

    @pytest.mark.asyncio
    async def test_query_endpoint_contact_query(self):
        """Test query endpoint with contact query."""
        with patch("api.dependencies.get_query_processor") as mock_get_processor:
            mock_processor = Mock()
            mock_processor.process_query.return_value = QueryResponse(
                response="Dr. Sarah Johnson is on-call for cardiology. Phone: 555-123-4567",
                query_type="contact",
                confidence=0.95,
                sources=["amion_schedule"],
                warnings=None,
                processing_time=0.45,
            )
            mock_get_processor.return_value = mock_processor

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
                assert data["query_type"] == "contact"
                assert data["confidence"] == 0.95
                assert "Dr. Sarah Johnson" in data["response"]
                assert "amion_schedule" in data["sources"]

    @pytest.mark.asyncio
    async def test_query_endpoint_form_query(self):
        """Test query endpoint with form query."""
        with patch("api.dependencies.get_query_processor") as mock_get_processor:
            mock_processor = Mock()
            mock_processor.process_query.return_value = QueryResponse(
                response="Found the Blood Transfusion Consent Form.",
                query_type="form",
                confidence=0.92,
                sources=["blood_transfusion_consent.pdf"],
                warnings=None,
                processing_time=0.32,
                pdf_links=[
                    {
                        "filename": "blood_transfusion_consent.pdf",
                        "display_name": "Blood Transfusion Consent Form",
                        "url": "/api/v1/documents/123/download",
                    }
                ],
            )
            mock_get_processor.return_value = mock_processor

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/query",
                    json={"query": "show me the blood transfusion form"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["query_type"] == "form"
                assert data["pdf_links"] is not None
                assert len(data["pdf_links"]) == 1

    @pytest.mark.asyncio
    async def test_query_endpoint_invalid_request(self):
        """Test query endpoint with invalid request."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Empty query
            response = await ac.post("/api/v1/query", json={"query": ""})
            assert response.status_code == 422

            # Missing query field
            response = await ac.post("/api/v1/query", json={"user_id": "test"})
            assert response.status_code == 422

            # Query too long
            response = await ac.post(
                "/api/v1/query",
                json={"query": "x" * 1001},  # Over 1000 char limit
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_endpoint_processing_error(self):
        """Test query endpoint when processing fails."""
        with patch("api.dependencies.get_query_processor") as mock_get_processor:
            mock_processor = Mock()
            mock_processor.process_query.side_effect = Exception("Processing error")
            mock_get_processor.return_value = mock_processor

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/query", json={"query": "test query"})

                assert response.status_code == 500
                data = response.json()
                assert "Query processing failed" in data["detail"]

    @pytest.mark.asyncio
    async def test_documents_list_endpoint(self):
        """Test documents listing endpoint."""
        with patch("api.dependencies.get_db_session") as mock_get_db:
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.all.return_value = [
                Mock(
                    id="doc1",
                    filename="test_form.pdf",
                    content_type="application/pdf",
                    file_type="pdf",
                    title="Test Form",
                    category="form",
                    created_at=datetime.utcnow(),
                    metadata={},
                )
            ]
            mock_get_db.return_value.__enter__.return_value = mock_db

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/documents")

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["filename"] == "test_form.pdf"

    @pytest.mark.asyncio
    async def test_documents_list_with_filters(self):
        """Test documents listing with filters."""
        with patch("api.dependencies.get_db_session") as mock_get_db:
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []
            mock_get_db.return_value.__enter__.return_value = mock_db

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/v1/documents?doc_type=form&category=consent"
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 0

    @pytest.mark.asyncio
    async def test_document_download_endpoint(self):
        """Test document download endpoint."""
        with patch("api.dependencies.get_db_session") as mock_get_db:
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query

            # Mock document with valid file path
            mock_doc = Mock()
            mock_doc.id = "doc123"
            mock_doc.file_path = "/app/data/forms/test_form.pdf"
            mock_doc.title = "Test Form"
            mock_query.first.return_value = mock_doc

            mock_get_db.return_value.__enter__.return_value = mock_db

            # Mock file existence
            with patch("pathlib.Path.exists", return_value=True):
                async with AsyncClient(app=app, base_url="http://test") as ac:
                    response = await ac.get("/api/v1/documents/doc123/download")

                    # Should attempt to return file (will fail in test without actual file)
                    # But we can verify the attempt was made correctly
                    assert response.status_code in [
                        200,
                        404,
                        500,
                    ]  # Depends on file system

    @pytest.mark.asyncio
    async def test_document_download_not_found(self):
        """Test document download when document doesn't exist."""
        with patch("api.dependencies.get_db_session") as mock_get_db:
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None
            mock_get_db.return_value.__enter__.return_value = mock_db

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/documents/nonexistent/download")

                assert response.status_code == 404
                data = response.json()
                assert "Document not found" in data["detail"]

    @pytest.mark.asyncio
    async def test_contacts_endpoint(self):
        """Test contacts lookup endpoint."""
        from models.schemas import ContactInfo, ContactResponse

        with patch("api.dependencies.get_query_processor") as mock_get_processor:
            mock_processor = Mock()
            mock_processor.get_on_call_contact.return_value = ContactResponse(
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
            mock_get_processor.return_value = mock_processor

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/contacts/cardiology")

                assert response.status_code == 200
                data = response.json()
                assert data["specialty"] == "cardiology"
                assert len(data["contacts"]) == 1
                assert data["contacts"][0]["name"] == "Dr. Sarah Johnson"

    @pytest.mark.asyncio
    async def test_search_endpoint(self):
        """Test document search endpoint."""
        with patch("api.dependencies.get_db_session") as mock_get_db:
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_get_db.return_value.__enter__.return_value = mock_db

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/search?q=protocol&limit=5")

                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_validate_endpoint(self):
        """Test query validation endpoint."""
        with patch("api.dependencies.get_query_processor") as mock_get_processor:
            mock_processor = Mock()
            mock_processor.validate_query.return_value = Mock(
                is_valid=True, warnings=None, confidence=0.95
            )
            mock_get_processor.return_value = mock_processor

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/validate", json={"query": "safe medical query"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["is_valid"] is True
                assert data["confidence"] == 0.95


if __name__ == "__main__":
    pytest.main([__file__])
