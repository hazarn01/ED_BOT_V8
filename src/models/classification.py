from typing import List

from pydantic import BaseModel, Field

from .query_types import QueryType


class ClassificationResult(BaseModel):
    """Result of query classification with confidence score."""
    
    query_type: QueryType = Field(..., description="Classified query type")
    confidence: float = Field(..., ge=0, le=1, description="Classification confidence")
    method: str = Field(..., description="Classification method used")
    keywords: List[str] = Field(default_factory=list, description="Key terms found")
    
    @classmethod
    def from_tuple(cls, query_type: QueryType, confidence: float, method: str = "hybrid") -> "ClassificationResult":
        """Create from legacy tuple return."""
        return cls(query_type=query_type, confidence=confidence, method=method)

    class Config:
        json_schema_extra = {
            "example": {
                "query_type": "contact",
                "confidence": 0.95,
                "method": "rules",
                "keywords": ["on call", "cardiology"]
            }
        }