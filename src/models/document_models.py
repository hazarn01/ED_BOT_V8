from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Document metadata model."""

    title: Optional[str] = None
    author: Optional[str] = None
    department: Optional[str] = None
    version: Optional[str] = None
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    medical_specialties: List[str] = Field(default_factory=list)


class DocumentChunkMetadata(BaseModel):
    """Chunk-specific metadata."""

    section_title: Optional[str] = None
    subsection: Optional[str] = None
    is_table: bool = False
    is_list: bool = False
    has_formula: bool = False
    has_diagram: bool = False


class ParsedDocument(BaseModel):
    """Result of document parsing."""

    filename: str
    content: str
    chunks: List[Dict[str, Any]]
    metadata: DocumentMetadata
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    page_count: int
    parse_warnings: List[str] = Field(default_factory=list)


class RegistryEntry(BaseModel):
    """Document registry entry for quick lookup."""

    document_id: str
    display_name: str
    file_path: str
    keywords: List[str]
    category: str
    priority: int = 0
    quick_access: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
