"""
Pytest configuration and fixtures for ED Bot v8 tests.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_database_session():
    """Mock database session for testing."""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    session.query = Mock()
    return session


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    redis = Mock()
    redis.ping = Mock(return_value=True)
    redis.get = Mock(return_value=None)
    redis.set = Mock(return_value=True)
    redis.setex = Mock(return_value=True)
    redis.delete = Mock(return_value=1)
    return redis


@pytest.fixture
def sample_document():
    """Sample document entity for testing."""
    from models.entities import Document

    return Document(
        id="test_doc_123",
        filename="test_document.pdf",
        title="Test Medical Document",
        content="Sample medical document content for testing",
        content_type="application/pdf",
        file_type="pdf",
        doc_type="protocol",
        category="emergency",
        file_path="/app/data/protocols/test_document.pdf",
        created_at=datetime.utcnow(),
        metadata={"source": "test", "version": "1.0"},
    )


@pytest.fixture
def sample_extracted_entity():
    """Sample extracted entity for testing."""
    from models.entities import ExtractedEntity

    return ExtractedEntity(
        id="test_entity_456",
        document_id="test_doc_123",
        entity_type="protocol",
        payload={
            "name": "Test Protocol",
            "steps": [
                {"action": "Step 1", "timing": "immediate"},
                {"action": "Step 2", "timing": "within 5 minutes"},
            ],
            "critical_timing": "Must complete within 30 minutes",
        },
        confidence=0.95,
        evidence_text="Test protocol evidence text",
        page_no=1,
        span={"start": 100, "end": 200},
    )


@pytest.fixture
def sample_query_request():
    """Sample query request for testing."""
    from models.schemas import QueryRequest

    return QueryRequest(
        query="who is on call for cardiology",
        session_id="test_session_123",
        context="Emergency department query",
        user_id="test_user_456",
    )


@pytest.fixture
def sample_query_response():
    """Sample query response for testing."""
    from models.schemas import QueryResponse

    return QueryResponse(
        response="Dr. Sarah Johnson is on-call for cardiology. Phone: 555-123-4567",
        query_type="contact",
        confidence=0.95,
        sources=["amion_schedule"],
        warnings=None,
        processing_time=0.45,
    )


@pytest.fixture
def sample_contact_info():
    """Sample contact info for testing."""
    from models.schemas import ContactInfo

    return ContactInfo(
        name="Dr. Sarah Johnson",
        role="Attending Cardiologist",
        phone="555-123-4567",
        pager="555-987-6543",
        coverage="on-call",
        department="Cardiology",
    )


@pytest.fixture
def medical_abbreviations():
    """Sample medical abbreviations for testing."""
    return {
        "ECG": "Electrocardiogram",
        "MI": "Myocardial Infarction",
        "STEMI": "ST-Elevation Myocardial Infarction",
        "PE": "Pulmonary Embolism",
        "DVT": "Deep Vein Thrombosis",
        "CHF": "Congestive Heart Failure",
        "COPD": "Chronic Obstructive Pulmonary Disease",
        "ED": "Emergency Department",
        "ICU": "Intensive Care Unit",
        "OR": "Operating Room",
    }


@pytest.fixture
def sample_protocol_data():
    """Sample protocol data for testing."""
    return {
        "name": "STEMI Protocol",
        "steps": [
            {
                "step_number": 1,
                "action": "Obtain 12-lead ECG",
                "timing": "within 10 minutes",
                "critical": True,
            },
            {
                "step_number": 2,
                "action": "Activate cardiac catheterization lab",
                "timing": "immediate",
                "critical": True,
            },
            {
                "step_number": 3,
                "action": "Administer aspirin 325mg",
                "timing": "immediate",
                "critical": False,
            },
        ],
        "critical_timing": "Door-to-balloon time must be <90 minutes",
        "contraindications": ["Active bleeding", "Recent surgery"],
        "monitoring": ["Vital signs", "ECG changes", "Bleeding"],
    }


@pytest.fixture
def sample_dosage_data():
    """Sample dosage data for testing."""
    return {
        "drug": "Epinephrine",
        "indication": "Cardiac arrest",
        "dose": "1mg (1:10,000)",
        "route": "IV/IO",
        "frequency": "every 3-5 minutes",
        "max_dose": "No maximum in cardiac arrest",
        "contraindications": ["None in cardiac arrest"],
        "monitoring": ["Heart rhythm", "Blood pressure", "Return of circulation"],
        "preparation": "1mg in 10mL prefilled syringe",
        "administration": "Push rapidly followed by 20mL normal saline flush",
    }


@pytest.fixture
def sample_criteria_data():
    """Sample clinical criteria data for testing."""
    return {
        "name": "Ottawa Ankle Rules",
        "purpose": "Determine need for ankle radiography",
        "criteria": [
            "Pain in malleolar zone AND bone tenderness at posterior edge of lateral malleolus",
            "Pain in malleolar zone AND bone tenderness at posterior edge of medial malleolus",
            "Pain in midfoot zone AND bone tenderness at base of 5th metatarsal",
            "Pain in midfoot zone AND bone tenderness at navicular",
            "Inability to bear weight both immediately and in ED",
        ],
        "sensitivity": "97-99%",
        "specificity": "40-79%",
        "interpretation": "If none of the criteria are met, fracture is unlikely",
    }


# Configure pytest to handle async tests
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as an async test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
