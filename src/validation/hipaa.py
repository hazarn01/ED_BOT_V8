import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PHIScrubber:
    """Advanced PHI detection and scrubbing for HIPAA compliance."""

    def __init__(self):
        self.phi_patterns = self._compile_phi_patterns()
        self.safe_medical_terms = self._load_safe_medical_terms()

    def _compile_phi_patterns(self) -> List[Tuple[re.Pattern, str, str]]:
        """Compile PHI detection patterns with replacement text and classification."""
        # Order matters: match MRN-like patterns before generic digit sequences
        patterns = [
            # Medical Record Numbers (various formats)
            (re.compile(r"\bMR#?\s*:?\s*\d{6,10}\b", re.IGNORECASE), "[MRN]", "mrn"),
            (re.compile(r"\bMRN\s*:?\s*[A-Z0-9]{6,12}\b", re.IGNORECASE), "[MRN]", "mrn"),
            (re.compile(r"\b[A-Z]{2,3}\d{6,10}\b"), "[MRN]", "mrn"),
            # Social Security Numbers
            (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]", "ssn"),
            (re.compile(r"\b\d{3}\d{2}\d{4}\b"), "[SSN]", "ssn"),
            # Phone Numbers
            (
                re.compile(r"\b\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b"),
                "[PHONE]",
                "phone",
            ),
            (re.compile(r"\b\d{3}-\d{3}-\d{4}\b"), "[PHONE]", "phone"),
            # Email Addresses
            (
                re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
                "[EMAIL]",
                "email",
            ),
            # Dates (birth dates, appointment dates)
            (
                re.compile(
                    r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b"
                ),
                "[DATE]",
                "date",
            ),
            (
                re.compile(
                    r"\b(?:19|20)\d{2}-(?:0?[1-9]|1[0-2])-(?:0?[1-9]|[12]\d|3[01])\b"
                ),
                "[DATE]",
                "date",
            ),
            # Account Numbers
            (
                re.compile(r"\bACCT#?\s*:?\s*\d{6,12}\b", re.IGNORECASE),
                "[ACCOUNT]",
                "account",
            ),
            # Insurance ID Numbers
            (re.compile(r"\b[A-Z]{2,4}\d{8,12}\b"), "[INSURANCE_ID]", "insurance"),
            # Addresses (partial - street numbers and zip codes)
            (
                re.compile(
                    r"\b\d{1,5}\s+[A-Z][a-z]+\s+(?:St|Ave|Rd|Dr|Blvd|Ln|Way|Ct|Pl)\.?\b"
                ),
                "[ADDRESS]",
                "address",
            ),
            (re.compile(r"\b\d{5}(?:-\d{4})?\b"), "[ZIP]", "zip"),
            # Names with titles (Dr. FirstName LastName patterns)
            (
                re.compile(r"\bDr\.?\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
                "[PHYSICIAN_NAME]",
                "physician_name",
            ),
            (
                re.compile(r"\b(?:Mr|Ms|Mrs|Miss)\.?\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
                "[PATIENT_NAME]",
                "patient_name",
            ),
            # Generic ID numbers (long sequences that might be IDs)
            (re.compile(r"\b\d{10,15}\b"), "[ID]", "generic_id"),
            # License plate numbers
            (re.compile(r"\b[A-Z]{1,3}\d{1,4}[A-Z]?\b"), "[LICENSE]", "license"),
        ]

        return patterns

    def scrub_text(self, text: str, audit_log: bool = True) -> Dict[str, Any]:
        """
        Scrub PHI from text and return cleaned text with audit information.

        Args:
            text: Text to scrub
            audit_log: Whether to create audit log entry

        Returns:
            Dict with cleaned text and audit information
        """
        if not text:
            return {"scrubbed_text": text, "phi_found": False, "replacements": []}

        scrubbed_text = text
        replacements = []

        # Apply each PHI pattern
        for pattern, replacement, phi_type in self.phi_patterns:
            matches = list(pattern.finditer(scrubbed_text))

            for match in matches:
                original_text = match.group(0)

                # Skip if it's a safe medical term (false positive)
                if self._is_safe_medical_term(original_text):
                    continue

                # Apply replacement
                scrubbed_text = scrubbed_text.replace(original_text, replacement)

                replacements.append(
                    {
                        "original": original_text,
                        "replacement": replacement,
                        "type": phi_type,
                        "position": match.start(),
                    }
                )

        result = {
            "scrubbed_text": scrubbed_text,
            "phi_found": len(replacements) > 0,
            "replacements": replacements,
            "phi_count": len(replacements),
        }

        # Create audit log if PHI was found
        if audit_log and result["phi_found"]:
            self._create_phi_audit_log(result)

        return result

    def validate_phi_free(self, text: str) -> Dict[str, Any]:
        """
        Validate that text contains no PHI.

        Returns:
            Dict with validation results
        """
        scrub_result = self.scrub_text(text, audit_log=False)

        return {
            "is_phi_free": not scrub_result["phi_found"],
            "phi_violations": scrub_result["replacements"],
            "violation_count": scrub_result["phi_count"],
            "risk_score": self._calculate_phi_risk_score(scrub_result["replacements"]),
        }

    def _is_safe_medical_term(self, text: str) -> bool:
        """Check if text is a safe medical term (not PHI)."""
        text_lower = text.lower().strip()

        # Check against safe medical terms
        if text_lower in self.safe_medical_terms:
            return True

        # Special cases for medical abbreviations
        medical_abbreviation_patterns = [
            r"^[a-z]{2,6}$",  # Short medical abbreviations like "mg", "ml", "iv"
            r"^\d+\s*(mg|ml|g|units?|mcg|l|cc)$",  # Medication doses
            r"^\d+\s*bpm$",  # Heart rate
            r"^\d+/\d+\s*mmhg$",  # Blood pressure
        ]

        for pattern in medical_abbreviation_patterns:
            if re.match(pattern, text_lower):
                return True

        return False

    def _calculate_phi_risk_score(self, replacements: List[Dict[str, Any]]) -> float:
        """Calculate risk score based on PHI violations."""
        if not replacements:
            return 0.0

        # Weight different types of PHI violations
        phi_weights = {
            "ssn": 1.0,
            "mrn": 0.9,
            "patient_name": 0.8,
            "email": 0.7,
            "phone": 0.6,
            "date": 0.4,
            "address": 0.7,
            "zip": 0.3,
            "account": 0.5,
            "insurance": 0.6,
            "generic_id": 0.3,
            "physician_name": 0.2,  # Less critical in medical context
            "license": 0.2,
        }

        total_score = 0.0
        for replacement in replacements:
            phi_type = replacement.get("type", "unknown")
            weight = phi_weights.get(phi_type, 0.5)
            total_score += weight

        # Normalize to 0-1 scale
        return min(total_score / len(replacements), 1.0)

    def _create_phi_audit_log(self, scrub_result: Dict[str, Any]) -> None:
        """Create audit log entry for PHI detection."""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "phi_detected",
            "phi_count": scrub_result["phi_count"],
            "phi_types": [r["type"] for r in scrub_result["replacements"]],
            "risk_score": self._calculate_phi_risk_score(scrub_result["replacements"]),
            "action": "scrubbed",
        }

        # Log without including actual PHI
        logger.warning("PHI detected and scrubbed", extra_fields=audit_entry)

    def _load_safe_medical_terms(self) -> set:
        """Load safe medical terms that should not be scrubbed."""
        return {
            # Units
            "mg",
            "ml",
            "g",
            "kg",
            "l",
            "cc",
            "units",
            "mcg",
            "mmol",
            "meq",
            # Routes
            "iv",
            "im",
            "po",
            "sq",
            "pr",
            "sl",
            "ng",
            "nj",
            # Common medical abbreviations
            "bpm",
            "mmhg",
            "°c",
            "°f",
            "h",
            "hr",
            "min",
            "sec",
            "qd",
            "bid",
            "tid",
            "qid",
            "prn",
            "stat",
            "asap",
            # Medical specialties
            "cardiology",
            "neurology",
            "surgery",
            "medicine",
            "emergency",
            "pediatrics",
            "radiology",
            "pathology",
            "anesthesia",
            # Common medical terms
            "patient",
            "doctor",
            "nurse",
            "hospital",
            "clinic",
            "ed",
            "icu",
            "diagnosis",
            "treatment",
            "medication",
            "surgery",
            "procedure",
            # Time periods
            "daily",
            "weekly",
            "monthly",
            "hourly",
            "morning",
            "evening",
            "night",
        }


class HIPAACompliantLogger:
    """Logger wrapper that automatically scrubs PHI."""

    def __init__(self):
        self.scrubber = PHIScrubber()
        self.enabled = settings.log_scrub_phi

    def scrub_log_data(self, data: Any) -> Any:
        """Recursively scrub PHI from log data."""
        if not self.enabled:
            return data

        if isinstance(data, str):
            scrub_result = self.scrubber.scrub_text(data, audit_log=False)
            return scrub_result["scrubbed_text"]

        elif isinstance(data, dict):
            scrubbed_dict = {}
            for key, value in data.items():
                # Skip scrubbing for certain system fields
                if key in ["timestamp", "level", "logger", "function", "line"]:
                    scrubbed_dict[key] = value
                else:
                    scrubbed_dict[key] = self.scrub_log_data(value)
            return scrubbed_dict

        elif isinstance(data, list):
            return [self.scrub_log_data(item) for item in data]

        else:
            return data


# Global instances
phi_scrubber = PHIScrubber()
hipaa_logger = HIPAACompliantLogger()


def setup_hipaa_logging() -> None:
    """Initialize HIPAA logging/scrubbing components.

    Provided for app startup compatibility; globals already initialize
    on import, so this is currently a no-op.
    """
    # Intentionally minimal; globals are ready.
    return None


def hipaa_compliant_log(logger_instance, level: str, message: str, **kwargs):
    """Log with automatic PHI scrubbing."""
    if not settings.log_scrub_phi:
        # If PHI scrubbing is disabled, log normally
        getattr(logger_instance, level.lower())(message, **kwargs)
        return

    # Scrub the message
    scrub_result = phi_scrubber.scrub_text(message, audit_log=False)
    scrubbed_message = scrub_result["scrubbed_text"]

    # Scrub any extra fields
    scrubbed_kwargs = {}
    for key, value in kwargs.items():
        scrubbed_kwargs[key] = hipaa_logger.scrub_log_data(value)

    # Log the scrubbed data
    getattr(logger_instance, level.lower())(scrubbed_message, **scrubbed_kwargs)

    # If PHI was found, create audit entry
    if scrub_result["phi_found"]:
        getattr(logger_instance, "warning")(
            "PHI detected in log message and scrubbed",
            extra_fields={
                "phi_count": scrub_result["phi_count"],
                "phi_types": [r["type"] for r in scrub_result["replacements"]],
            },
        )


def validate_request_phi_compliance(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that incoming request data is PHI-free."""
    validation_result = {
        "is_compliant": True,
        "violations": [],
        "risk_score": 0.0,
        "requires_audit": False,
    }

    # Check query text
    if "query" in request_data:
        query_validation = phi_scrubber.validate_phi_free(request_data["query"])

        if not query_validation["is_phi_free"]:
            validation_result["is_compliant"] = False
            validation_result["violations"].extend(query_validation["phi_violations"])
            validation_result["risk_score"] = max(
                validation_result["risk_score"], query_validation["risk_score"]
            )

    # Check other string fields
    for key, value in request_data.items():
        if isinstance(value, str) and key != "query":
            field_validation = phi_scrubber.validate_phi_free(value)

            if not field_validation["is_phi_free"]:
                validation_result["is_compliant"] = False
                validation_result["violations"].extend(
                    field_validation["phi_violations"]
                )
                validation_result["risk_score"] = max(
                    validation_result["risk_score"], field_validation["risk_score"]
                )

    # Determine if audit is required
    validation_result["requires_audit"] = (
        validation_result["risk_score"] > 0.5
        or len(validation_result["violations"]) > 2
    )

    return validation_result


def sanitize_response_for_logging(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize response data for safe logging."""
    if not settings.log_scrub_phi:
        return response_data

    # Create a copy for scrubbing
    sanitized = response_data.copy()

    # Scrub the response text
    if "response" in sanitized:
        scrub_result = phi_scrubber.scrub_text(sanitized["response"], audit_log=False)
        sanitized["response"] = scrub_result["scrubbed_text"]

    # Scrub source information
    if "sources" in sanitized:
        sanitized["sources"] = [
            source
            if not phi_scrubber.validate_phi_free(source)["phi_violations"]
            else "[REDACTED_SOURCE]"
            for source in sanitized["sources"]
        ]

    return sanitized


# Backwards-compatible helper expected by pipeline
def scrub_phi(text: str) -> str:
    """Return PHI-scrubbed text using the global scrubber.

    This provides a simple function import for modules expecting
    `from src.validation.hipaa import scrub_phi`.
    """
    return phi_scrubber.scrub_text(text, audit_log=False).get("scrubbed_text", text)
