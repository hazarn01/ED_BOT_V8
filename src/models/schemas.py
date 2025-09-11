from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    """Request model for query endpoint."""

    query: str = Field(
        ..., min_length=1, max_length=1000, description="User query text"
    )
    session_id: Optional[str] = Field(None, description="Session ID for context")
    context: Optional[str] = Field(None, description="Additional context")
    user_id: Optional[str] = Field(None, description="User ID for audit trail")

    @field_validator("query")
    def clean_query(cls, v):
        """Clean and validate query text."""
        return v.strip()


class HighlightedSourceSchema(BaseModel):
    """Schema for highlighted source (PRP 17)."""
    
    document_id: str = Field(..., description="Source document ID")
    document_name: str = Field(..., description="Source document filename")
    page_number: int = Field(..., description="Page number in document")
    text_snippet: str = Field(..., description="Text snippet with context")
    highlight_spans: List[List[int]] = Field(
        default_factory=list, 
        description="Highlight spans as [start, end] positions"
    )
    bbox: Optional[Dict[str, float]] = Field(
        None, 
        description="Bounding box coordinates {x, y, width, height}"
    )
    confidence: float = Field(
        default=1.0, 
        ge=0, 
        le=1, 
        description="Confidence score for highlight accuracy"
    )


class QueryResponse(BaseModel):
    """Response model for query endpoint."""

    response: str = Field(..., description="Generated response text")
    query_type: str = Field(..., description="Classified query type")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")
    # Change sources from List[str] to List[Dict[str, str]] to include display name and filename (Task 35)
    sources: List[Dict[str, str]] = Field(default_factory=list, description="Source documents with display name and filename")
    warnings: Optional[List[str]] = Field(None, description="Medical warnings if any")
    processing_time: float = Field(..., description="Processing time in seconds")
    pdf_links: Optional[List[Dict[str, str]]] = Field(
        None, description="PDF download links for forms"
    )
    
    # Enhanced source highlighting fields (PRP 17-18)
    highlighted_sources: Optional[List[HighlightedSourceSchema]] = Field(
        None,
        description="Detailed source highlights with page/span info"
    )
    viewer_url: Optional[str] = Field(
        None,
        description="URL to view highlighted sources in PDF viewer"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "response": "The blood transfusion consent form is available.",
                "query_type": "form",
                "confidence": 0.95,
                "sources": [{"display_name": "Blood Transfusion Consent Form", "filename": "blood_transfusion_consent.pdf"}],
                "warnings": None,
                "processing_time": 0.45,
                "pdf_links": [
                    {
                        "filename": "blood_transfusion_consent.pdf",
                        "display_name": "Blood Transfusion Consent Form",
                        "url": "/api/v1/documents/pdf/blood_transfusion_consent.pdf",
                    }
                ],
            }
        }


class DocumentResponse(BaseModel):
    """Response model for document endpoints."""

    id: str
    filename: str
    content_type: str
    file_type: str
    display_name: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, Dict[str, Any]] = Field(
        ..., description="Individual service statuses"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "services": {
                    "database": {"status": "healthy", "latency_ms": 5},
                    "redis": {"status": "healthy", "latency_ms": 2},
                    "llm": {
                        "status": "healthy",
                        "latency_ms": 150,
                        "model": "gpt-oss-20b",
                    },
                },
            }
        }


class DocumentIngestionRequest(BaseModel):
    """Request model for document ingestion."""

    file_path: str = Field(..., description="Path to document file")
    content_type: Optional[str] = Field(None, description="Document content type")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class ExtractedEntityResponse(BaseModel):
    """Response model for extracted entities."""

    id: str
    document_id: str
    entity_type: str
    payload: Dict[str, Any]
    confidence: Optional[float] = None
    evidence_text: Optional[str] = None
    page_no: Optional[int] = None
    span: Optional[Dict[str, int]] = None


class ContactInfo(BaseModel):
    """Contact information model."""

    name: str
    role: str
    phone: Optional[str] = None
    pager: Optional[str] = None
    coverage: Optional[str] = None  # on-call, primary, backup
    department: Optional[str] = None


class ProtocolStep(BaseModel):
    """Protocol step model."""

    step_number: int
    action: str
    timing_min: Optional[int] = None
    timing_max: Optional[int] = None
    critical: bool = False
    notes: Optional[str] = None


class MedicationDosage(BaseModel):
    """Medication dosage model."""

    drug: str
    dose: str
    route: str
    frequency: Optional[str] = None
    duration: Optional[str] = None
    max_dose: Optional[str] = None
    contraindications: List[str] = Field(default_factory=list)
    monitoring: List[str] = Field(default_factory=list)


class ContactResponse(BaseModel):
    """Response model for contact lookup."""

    specialty: str
    contacts: List[ContactInfo]
    updated_at: datetime
    source: str = "amion"

    class Config:
        json_schema_extra = {
            "example": {
                "specialty": "cardiology",
                "contacts": [
                    {
                        "name": "Dr. Sarah Johnson",
                        "role": "Attending Cardiologist",
                        "phone": "555-123-4567",
                        "pager": "555-987-6543",
                        "coverage": "on-call",
                        "department": "Cardiology",
                    }
                ],
                "updated_at": "2024-01-15T08:00:00Z",
                "source": "amion",
            }
        }
