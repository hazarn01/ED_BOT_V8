"""Unit tests for table extraction functionality (PRP 19)."""

from unittest.mock import Mock

import pytest

from src.config.settings import Settings
from src.ingestion.table_extractor import TableExtractor
from src.models.entities import Document, ExtractedTable
from src.pipeline.table_retriever import TableRetriever


class TestTableExtractor:
    """Test TableExtractor functionality."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Mock(spec=Settings)
        settings.enable_table_extraction = True
        settings.table_extraction_confidence_threshold = 0.7
        settings.max_tables_per_document = 10
        return settings

    @pytest.fixture
    def settings_disabled(self):
        """Create test settings with table extraction disabled."""
        settings = Mock(spec=Settings)
        settings.enable_table_extraction = False
        return settings

    @pytest.fixture
    def table_extractor(self, settings):
        """Create TableExtractor instance."""
        return TableExtractor(settings)

    @pytest.fixture
    def table_extractor_disabled(self, settings_disabled):
        """Create TableExtractor instance with extraction disabled."""
        return TableExtractor(settings_disabled)

    def test_table_extractor_initialization(self, table_extractor):
        """Test TableExtractor initialization."""
        assert table_extractor.enabled is True
        assert table_extractor.settings is not None

    def test_table_extractor_disabled(self, table_extractor_disabled):
        """Test TableExtractor when disabled."""
        assert table_extractor_disabled.enabled is False

    @pytest.mark.asyncio
    async def test_extract_tables_disabled(self, table_extractor_disabled):
        """Test that extraction returns empty list when disabled."""
        tables = await table_extractor_disabled.extract_tables("test.pdf", "pdf")
        assert tables == []

    @pytest.mark.asyncio
    async def test_extract_tables_unsupported_format(self, table_extractor):
        """Test extraction with unsupported file format."""
        tables = await table_extractor.extract_tables("test.txt", "txt")
        assert tables == []

    @pytest.mark.asyncio
    async def test_parse_html_table(self, table_extractor):
        """Test HTML table parsing."""
        table_html = """
        <table>
            <tr><th>Medication</th><th>Dose</th><th>Route</th></tr>
            <tr><td>Aspirin</td><td>325mg</td><td>PO</td></tr>
            <tr><td>Heparin</td><td>5000 units</td><td>SubQ</td></tr>
        </table>
        """
        
        result = await table_extractor._parse_html_table(table_html)
        
        assert result is not None
        assert result["headers"] == ["Medication", "Dose", "Route"]
        assert len(result["rows"]) == 2
        assert result["rows"][0] == ["Aspirin", "325mg", "PO"]
        assert result["rows"][1] == ["Heparin", "5000 units", "SubQ"]

    @pytest.mark.asyncio
    async def test_parse_text_table(self, table_extractor):
        """Test text table parsing."""
        text = """Drug	Dose	Route
Metoprolol	25mg	PO
Lisinopril	10mg	PO"""
        
        result = await table_extractor._parse_text_table(text)
        
        assert result is not None
        assert result["headers"] == ["Drug", "Dose", "Route"]
        assert len(result["rows"]) == 2
        assert result["rows"][0] == ["Metoprolol", "25mg", "PO"]

    def test_classify_table_type_dosage(self, table_extractor):
        """Test table type classification for dosage tables."""
        table_data = {
            "headers": ["Drug", "Dose", "Frequency"],
            "rows": [["Metoprolol", "25mg", "BID"]]
        }
        
        table_type = table_extractor._classify_table_type(table_data)
        assert table_type == "dosage"

    def test_classify_table_type_protocol(self, table_extractor):
        """Test table type classification for protocol tables."""
        table_data = {
            "headers": ["Step", "Action", "Time"],
            "rows": [["1", "Assess patient", "0 min"]]
        }
        
        table_type = table_extractor._classify_table_type(table_data)
        assert table_type == "protocol"

    def test_classify_table_type_contact(self, table_extractor):
        """Test table type classification for contact tables."""
        table_data = {
            "headers": ["Name", "Department", "Phone"],
            "rows": [["Dr. Smith", "Cardiology", "555-1234"]]
        }
        
        table_type = table_extractor._classify_table_type(table_data)
        assert table_type == "contact"

    def test_flatten_table(self, table_extractor):
        """Test table flattening for search."""
        table_data = {
            "headers": ["Drug", "Dose"],
            "rows": [["Aspirin", "325mg"], ["Heparin", "5000 units"]]
        }
        
        flattened = table_extractor._flatten_table(table_data)
        expected = "Drug | Dose\nAspirin | 325mg\nHeparin | 5000 units"
        assert flattened == expected

    def test_extract_units(self, table_extractor):
        """Test unit extraction from headers and data."""
        headers = ["Drug", "Dose (mg)", "Volume"]
        rows = [["Aspirin", "325", "10ml"], ["Heparin", "5000", "5ml"]]
        
        units = table_extractor._extract_units(headers, rows)
        
        assert "Dose" in units
        assert units["Dose"] == "mg"
        assert "Volume" in units
        assert units["Volume"] == "ml"


class TestTableRetriever:
    """Test TableRetriever functionality."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return Mock()

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Mock(spec=Settings)
        settings.enable_table_extraction = True
        return settings

    @pytest.fixture
    def settings_disabled(self):
        """Create test settings with table extraction disabled."""
        settings = Mock(spec=Settings)
        settings.enable_table_extraction = False
        return settings

    @pytest.fixture
    def table_retriever(self, mock_db_session, settings):
        """Create TableRetriever instance."""
        return TableRetriever(mock_db_session, settings)

    @pytest.fixture
    def table_retriever_disabled(self, mock_db_session, settings_disabled):
        """Create TableRetriever instance with extraction disabled."""
        return TableRetriever(mock_db_session, settings_disabled)

    def test_table_retriever_initialization(self, table_retriever):
        """Test TableRetriever initialization."""
        assert table_retriever.enabled is True
        assert table_retriever.settings is not None
        assert table_retriever.db is not None

    def test_table_retriever_disabled(self, table_retriever_disabled):
        """Test TableRetriever when disabled."""
        assert table_retriever_disabled.enabled is False

    @pytest.mark.asyncio
    async def test_retrieve_tables_disabled(self, table_retriever_disabled):
        """Test that retrieval returns empty list when disabled."""
        from src.models.query_types import QueryType
        
        tables = await table_retriever_disabled.retrieve_tables(
            "aspirin dose", QueryType.DOSAGE_LOOKUP
        )
        assert tables == []

    @pytest.mark.asyncio
    async def test_retrieve_tables_by_medication_disabled(self, table_retriever_disabled):
        """Test medication table retrieval when disabled."""
        tables = await table_retriever_disabled.retrieve_tables_by_medication("aspirin")
        assert tables == []

    def test_format_table_response(self, table_retriever):
        """Test table response formatting."""
        # Create mock table
        mock_table = Mock(spec=ExtractedTable)
        mock_table.title = "Dosage Table"
        mock_table.headers = ["Drug", "Dose", "Route"]
        mock_table.rows = [["Aspirin", "325mg", "PO"], ["Heparin", "5000 units", "SubQ"]]
        mock_table.table_type = "dosage"
        mock_table.page_number = 1
        mock_table.table_index = 0
        mock_table.confidence = 0.95
        
        # Mock document relationship
        mock_document = Mock(spec=Document)
        mock_document.filename = "dosage_guidelines.pdf"
        mock_table.document = mock_document
        
        response = table_retriever.format_table_response(mock_table)
        
        assert "**Dosage Table**" in response
        assert "| Drug | Dose | Route |" in response
        assert "| Aspirin | 325mg | PO |" in response
        assert "dosage_guidelines.pdf" in response
        assert "Page 1" in response

    def test_format_table_for_llm(self, table_retriever):
        """Test table formatting for LLM context."""
        # Create mock table
        mock_table = Mock(spec=ExtractedTable)
        mock_table.title = "Medication Dosing"
        mock_table.headers = ["Drug", "Dose"]
        mock_table.rows = [["Aspirin", "325mg"], ["Heparin", "5000 units"]]
        mock_table.page_number = 2
        
        # Mock document relationship
        mock_document = Mock(spec=Document)
        mock_document.filename = "medications.pdf"
        mock_table.document = mock_document
        
        context = table_retriever.format_table_for_llm(mock_table)
        
        assert "medications.pdf" in context
        assert "page 2" in context
        assert "Medication Dosing" in context
        assert "Headers: Drug | Dose" in context
        assert "Row 1: Aspirin | 325mg" in context


class TestTableExtractorIntegration:
    """Integration tests for table extraction."""

    @pytest.fixture
    def sample_dosage_html(self):
        """Sample dosage table HTML."""
        return """
        <table>
            <tr><th>Medication</th><th>Standard Dose</th><th>Max Dose</th><th>Route</th></tr>
            <tr><td>Aspirin</td><td>325mg</td><td>650mg</td><td>PO</td></tr>
            <tr><td>Morphine</td><td>2-4mg</td><td>10mg</td><td>IV</td></tr>
            <tr><td>Heparin</td><td>5000 units</td><td>10000 units</td><td>SubQ</td></tr>
        </table>
        """

    @pytest.fixture
    def sample_protocol_text(self):
        """Sample protocol table text."""
        return """Step	Action	Time Limit	Notes
1	Initial Assessment	0-5 min	Check vitals, obtain IV access
2	12-Lead EKG	Within 10 min	Look for STEMI criteria
3	Lab Draw	Within 15 min	Troponin, CBC, BMP
4	Cardiology Consult	Within 30 min	If STEMI positive"""

    @pytest.mark.asyncio
    async def test_dosage_table_extraction_and_classification(self, sample_dosage_html):
        """Test complete dosage table extraction and classification."""
        settings = Mock(spec=Settings)
        settings.enable_table_extraction = True
        
        extractor = TableExtractor(settings)
        
        # Parse the HTML table
        result = await extractor._parse_html_table(sample_dosage_html)
        
        # Verify structure
        assert result is not None
        assert len(result["headers"]) == 4
        assert len(result["rows"]) == 3
        
        # Test classification
        table_type = extractor._classify_table_type(result)
        assert table_type == "dosage"
        
        # Test flattening
        flattened = extractor._flatten_table(result)
        assert "Medication" in flattened
        assert "Aspirin" in flattened
        assert "325mg" in flattened

    @pytest.mark.asyncio
    async def test_protocol_table_extraction_and_classification(self, sample_protocol_text):
        """Test complete protocol table extraction and classification."""
        settings = Mock(spec=Settings)
        settings.enable_table_extraction = True
        
        extractor = TableExtractor(settings)
        
        # Parse the text table
        result = await extractor._parse_text_table(sample_protocol_text)
        
        # Verify structure
        assert result is not None
        assert len(result["headers"]) == 4
        assert len(result["rows"]) == 4
        
        # Test classification
        table_type = extractor._classify_table_type(result)
        assert table_type == "protocol"
        
        # Verify content
        assert result["headers"][0] == "Step"
        assert result["rows"][0][1] == "Initial Assessment"