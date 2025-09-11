from enum import Enum


class QueryType(Enum):
    """Six types of medical queries the ED Bot can handle."""

    CONTACT_LOOKUP = "contact"
    FORM_RETRIEVAL = "form"
    PROTOCOL_STEPS = "protocol"
    CRITERIA_CHECK = "criteria"
    DOSAGE_LOOKUP = "dosage"
    SUMMARY_REQUEST = "summary"

    @classmethod
    def from_string(cls, value: str) -> "QueryType":
        """Convert string to QueryType enum."""
        for query_type in cls:
            if query_type.value == value.lower():
                return query_type
        raise ValueError(f"Unknown query type: {value}")
