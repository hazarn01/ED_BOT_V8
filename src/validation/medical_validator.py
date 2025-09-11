import re
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MedicalValidator:
    """Validate medical responses for safety and completeness."""

    def __init__(self):
        self.drug_safety_ranges = self._load_drug_safety_ranges()
        self.contraindications = self._load_contraindications()
        self.high_alert_medications = self._load_high_alert_medications()

    def validate_dosage_response(
        self, response: str, drug_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate dosage information for safety."""
        validation = {
            "is_safe": True,
            "warnings": [],
            "errors": [],
            "safety_score": 1.0,
            "extracted_dosages": [],
        }

        try:
            # Extract dosage information from response
            dosages = self._extract_dosage_info(response)
            validation["extracted_dosages"] = dosages

            for dosage in dosages:
                # Validate each dosage
                dosage_validation = self._validate_single_dosage(dosage)

                if not dosage_validation["is_safe"]:
                    validation["is_safe"] = False
                    validation["errors"].extend(dosage_validation["errors"])

                validation["warnings"].extend(dosage_validation["warnings"])
                validation["safety_score"] *= dosage_validation["safety_score"]

            # Check for high-alert medications
            if drug_name and drug_name.lower() in self.high_alert_medications:
                validation["warnings"].append(
                    f"{drug_name} is a high-alert medication requiring double-check"
                )

            # Validate completeness
            completeness_check = self._check_dosage_completeness(response)
            validation["warnings"].extend(completeness_check["warnings"])
            validation["safety_score"] *= completeness_check["score"]

        except Exception as e:
            logger.error(f"Dosage validation failed: {e}")
            validation["is_safe"] = False
            validation["errors"].append("Dosage validation system error")
            validation["safety_score"] = 0.1

        return validation

    def validate_dosage(self, dosage_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate dosage data dictionary for safety."""
        validation = {
            "is_safe": True,
            "warnings": [],
            "errors": [],
            "safety_score": 1.0,
        }

        try:
            drug = dosage_data.get("drug", "").lower()
            dose = dosage_data.get("dose", "")
            dosage_data.get("route", "").lower()
            
            # Check against safety ranges if available
            if drug in self.drug_safety_ranges:
                safety_range = self.drug_safety_ranges[drug]
                dose_value = self._extract_numeric_dose(dose)

                if dose_value:
                    if dose_value < safety_range.get("min", 0):
                        validation["warnings"].append(f"{drug} dose below typical range")
                        validation["safety_score"] *= 0.8
                    elif dose_value > safety_range.get("max", float("inf")):
                        validation["errors"].append(f"{drug} dose above maximum safe range")
                        validation["is_safe"] = False
                        validation["safety_score"] *= 0.3

            # Check for high-alert medications
            if drug in self.high_alert_medications:
                validation["warnings"].append(
                    f"{drug} is a high-alert medication requiring double-check"
                )

            # Check contraindications
            contraindications = dosage_data.get("contraindications", [])
            if not contraindications:
                validation["warnings"].append("No contraindications listed")

            # Check monitoring requirements
            monitoring = dosage_data.get("monitoring", [])
            if not monitoring:
                validation["warnings"].append("No monitoring requirements specified")

        except Exception as e:
            logger.error(f"Dosage data validation failed: {e}")
            validation["is_safe"] = False
            validation["errors"].append("Dosage validation system error")
            validation["safety_score"] = 0.1

        return validation

    def validate_protocol_response(self, response: str) -> Dict[str, Any]:
        """Validate protocol response for completeness and safety."""
        validation = {
            "is_safe": True,
            "warnings": [],
            "errors": [],
            "completeness_score": 1.0,
            "extracted_steps": [],
        }

        try:
            # Extract protocol steps
            steps = self._extract_protocol_steps(response)
            validation["extracted_steps"] = steps

            if not steps:
                validation["warnings"].append("No clear protocol steps identified")
                validation["completeness_score"] *= 0.7

            # Check for timing requirements
            timing_check = self._validate_protocol_timing(response)
            validation["warnings"].extend(timing_check["warnings"])
            validation["completeness_score"] *= timing_check["score"]

            # Check for contact information
            if not self._has_contact_info(response):
                validation["warnings"].append("Protocol missing contact information")
                validation["completeness_score"] *= 0.8

            # Check for safety warnings
            safety_check = self._check_protocol_safety(response)
            validation["warnings"].extend(safety_check["warnings"])

        except Exception as e:
            logger.error(f"Protocol validation failed: {e}")
            validation["errors"].append("Protocol validation system error")
            validation["completeness_score"] = 0.1

        return validation

    def validate_contact_response(self, response: str) -> Dict[str, Any]:
        """Validate contact response for accuracy and completeness."""
        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "accuracy_score": 1.0,
            "extracted_contacts": [],
        }

        try:
            # Extract contact information
            contacts = self._extract_contact_info(response)
            validation["extracted_contacts"] = contacts

            if not contacts:
                validation["warnings"].append(
                    "No contact information found in response"
                )
                validation["accuracy_score"] *= 0.5

            # Validate each contact
            for contact in contacts:
                contact_validation = self._validate_single_contact(contact)
                validation["warnings"].extend(contact_validation["warnings"])
                validation["accuracy_score"] *= contact_validation["score"]

            # Check for current information warning
            if not self._has_current_time_warning(response):
                validation["warnings"].append("Missing warning about schedule changes")
                validation["accuracy_score"] *= 0.9

        except Exception as e:
            logger.error(f"Contact validation failed: {e}")
            validation["errors"].append("Contact validation system error")
            validation["accuracy_score"] = 0.1

        return validation

    def validate_form_response(
        self, response: str, pdf_links: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Validate form response for PDF link requirements."""
        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "pdf_compliance": True,
        }

        try:
            # CRITICAL: Check for PDF links
            if not pdf_links:
                validation["is_valid"] = False
                validation["pdf_compliance"] = False
                validation["errors"].append("Form response missing required PDF links")

            # Validate PDF link format
            for link in pdf_links:
                if not self._validate_pdf_link_format(link):
                    validation["warnings"].append(
                        f"Invalid PDF link format for {link.get('display_name', 'unknown')}"
                    )

            # Check response contains PDF references
            if not self._has_pdf_references(response):
                validation["warnings"].append(
                    "Response text missing PDF link references"
                )

        except Exception as e:
            logger.error(f"Form validation failed: {e}")
            validation["errors"].append("Form validation system error")
            validation["is_valid"] = False

        return validation

    def validate_criteria_response(self, response: str) -> Dict[str, Any]:
        """Validate criteria response for clarity and completeness."""
        validation = {
            "is_clear": True,
            "warnings": [],
            "errors": [],
            "clarity_score": 1.0,
        }

        try:
            # Check for decision points
            if not self._has_decision_criteria(response):
                validation["warnings"].append("Response lacks clear decision criteria")
                validation["clarity_score"] *= 0.7

            # Check for thresholds/values
            if not self._has_numerical_criteria(response):
                validation["warnings"].append(
                    "No numerical criteria or thresholds provided"
                )
                validation["clarity_score"] *= 0.8

            # Check for contraindications
            if not self._mentions_contraindications(response):
                validation["warnings"].append(
                    "No contraindications or limitations mentioned"
                )
                validation["clarity_score"] *= 0.9

        except Exception as e:
            logger.error(f"Criteria validation failed: {e}")
            validation["errors"].append("Criteria validation system error")
            validation["clarity_score"] = 0.1

        return validation

    # Helper methods for extraction and validation

    def _extract_dosage_info(self, response: str) -> List[Dict[str, str]]:
        """Extract dosage information from response."""
        dosages = []

        # Pattern for dose, route, frequency
        dosage_pattern = r"(\w+)\s*:?\s*(\d+(?:\.\d+)?)\s*(mg|ml|g|units?|mcg|L|cc)(?:\s*/\s*(\w+))?\s*(?:via\s+)?(\w+)?\s*(?:every\s+(\d+)\s*(hours?|minutes?|h|min))?"

        matches = re.finditer(dosage_pattern, response, re.IGNORECASE)
        for match in matches:
            drug = match.group(1)
            dose_amount = match.group(2)
            dose_unit = match.group(3)
            dose_per = match.group(4)  # e.g., "kg" in "mg/kg"
            route = match.group(5)
            freq_amount = match.group(6)
            freq_unit = match.group(7)

            dosage = {
                "drug": drug,
                "dose": f"{dose_amount} {dose_unit}"
                + (f"/{dose_per}" if dose_per else ""),
                "route": route or "unknown",
                "frequency": f"every {freq_amount} {freq_unit}"
                if freq_amount and freq_unit
                else "unknown",
            }

            dosages.append(dosage)

        return dosages

    def _validate_single_dosage(self, dosage: Dict[str, str]) -> Dict[str, Any]:
        """Validate a single dosage entry."""
        validation = {
            "is_safe": True,
            "warnings": [],
            "errors": [],
            "safety_score": 1.0,
        }

        drug = dosage.get("drug", "").lower()
        dose = dosage.get("dose", "")
        route = dosage.get("route", "unknown").lower()

        # Check against safety ranges if available
        if drug in self.drug_safety_ranges:
            safety_range = self.drug_safety_ranges[drug]
            dose_value = self._extract_numeric_dose(dose)

            if dose_value:
                if dose_value < safety_range.get("min", 0):
                    validation["warnings"].append(f"{drug} dose below typical range")
                    validation["safety_score"] *= 0.8
                elif dose_value > safety_range.get("max", float("inf")):
                    validation["errors"].append(f"{drug} dose above maximum safe range")
                    validation["is_safe"] = False
                    validation["safety_score"] *= 0.3

        # Validate route
        valid_routes = ["iv", "im", "po", "sq", "sublingual", "inhalation", "topical"]
        if route not in ["unknown"] and route not in valid_routes:
            validation["warnings"].append(f"Unusual administration route: {route}")
            validation["safety_score"] *= 0.9

        return validation

    def _extract_protocol_steps(self, response: str) -> List[Dict[str, str]]:
        """Extract numbered protocol steps."""
        steps = []

        # Pattern for numbered steps
        step_pattern = r"(\d+)\.?\s+([^\n]+)"
        matches = re.finditer(step_pattern, response)

        for match in matches:
            step_num = match.group(1)
            step_text = match.group(2).strip()

            steps.append({"number": step_num, "action": step_text})

        return steps

    def _extract_contact_info(self, response: str) -> List[Dict[str, str]]:
        """Extract contact information."""
        contacts = []

        # Pattern for phone numbers with context
        phone_pattern = r"([A-Za-z\s.]+?)(?:phone|tel|call)?:?\s*(\(?(?:\d{3})\)?[\s.-]?\d{3}[\s.-]?\d{4})"
        matches = re.finditer(phone_pattern, response)

        for match in matches:
            name_context = match.group(1).strip()
            phone = match.group(2)

            contacts.append({"context": name_context, "phone": phone})

        return contacts

    def _validate_single_contact(self, contact: Dict[str, str]) -> Dict[str, Any]:
        """Validate a single contact entry."""
        validation = {"warnings": [], "score": 1.0}

        phone = contact.get("phone", "")
        context = contact.get("context", "")

        # Validate phone format
        phone_pattern = r"^\(?(?:\d{3})\)?[\s.-]?\d{3}[\s.-]?\d{4}$"
        if not re.match(phone_pattern, phone):
            validation["warnings"].append(f"Irregular phone format: {phone}")
            validation["score"] *= 0.9

        # Check for role/name context
        if len(context.strip()) < 3:
            validation["warnings"].append("Contact missing name/role context")
            validation["score"] *= 0.8

        return validation

    # Validation helper methods

    def _check_dosage_completeness(self, response: str) -> Dict[str, Any]:
        """Check if dosage response is complete."""
        required_elements = ["dose", "route", "frequency"]
        found_elements = []

        if re.search(r"\d+\s*(mg|ml|g|units?|mcg)", response, re.IGNORECASE):
            found_elements.append("dose")

        if re.search(r"\b(IV|IM|PO|SQ|sublingual)\b", response, re.IGNORECASE):
            found_elements.append("route")

        if re.search(r"every\s+\d+|daily|twice|q\d+h", response, re.IGNORECASE):
            found_elements.append("frequency")

        missing = set(required_elements) - set(found_elements)
        completeness_score = len(found_elements) / len(required_elements)

        return {
            "warnings": [f"Missing dosage information: {', '.join(missing)}"]
            if missing
            else [],
            "score": completeness_score,
        }

    def _validate_protocol_timing(self, response: str) -> Dict[str, Any]:
        """Check for timing requirements in protocol."""
        timing_patterns = [
            r"within\s+\d+\s+(minutes?|hours?)",
            r"immediately",
            r"stat",
            r"<\s*\d+\s*(min|minutes|hours?)",
        ]

        has_timing = any(
            re.search(pattern, response, re.IGNORECASE) for pattern in timing_patterns
        )

        return {
            "warnings": [] if has_timing else ["Protocol missing timing requirements"],
            "score": 1.0 if has_timing else 0.8,
        }

    def _has_contact_info(self, response: str) -> bool:
        """Check if protocol includes contact information."""
        contact_patterns = [
            r"\(?(?:\d{3})\)?[\s.-]?\d{3}[\s.-]?\d{4}",
            r"pager\s*:?\s*\d+",
            r"call\s+\w+",
        ]

        return any(
            re.search(pattern, response, re.IGNORECASE) for pattern in contact_patterns
        )

    def _check_protocol_safety(self, response: str) -> Dict[str, Any]:
        """Check protocol for safety warnings."""
        warnings = []

        # Check for contraindications
        if "contraindication" not in response.lower():
            warnings.append("Protocol missing contraindication information")

        # Check for monitoring requirements
        if not re.search(r"monitor|check|observe|assess", response, re.IGNORECASE):
            warnings.append("Protocol missing monitoring requirements")

        return {"warnings": warnings}

    def _has_current_time_warning(self, response: str) -> bool:
        """Check if contact response includes currency warning."""
        warning_patterns = [
            r"current\s+time",
            r"may\s+change",
            r"verify\s+with",
            r"schedules?\s+may",
        ]

        return any(
            re.search(pattern, response, re.IGNORECASE) for pattern in warning_patterns
        )

    def _validate_pdf_link_format(self, link: Dict[str, str]) -> bool:
        """Validate PDF link format."""
        required_keys = ["filename", "display_name", "url"]
        if not all(key in link for key in required_keys):
            return False

        url = link.get("url", "")
        return url.startswith("/api/v1/documents/pdf/") and url.endswith(".pdf")

    def _has_pdf_references(self, response: str) -> bool:
        """Check if response contains PDF link references."""
        pdf_patterns = [r"\[PDF:.*?\|.*?\]", r"download.*pdf", r"pdf.*link"]

        return any(
            re.search(pattern, response, re.IGNORECASE) for pattern in pdf_patterns
        )

    def _has_decision_criteria(self, response: str) -> bool:
        """Check for decision criteria language."""
        criteria_patterns = [
            r"if\s+.*then",
            r"when\s+.*",
            r"criteria\s+for",
            r"indication\s+for",
        ]

        return any(
            re.search(pattern, response, re.IGNORECASE) for pattern in criteria_patterns
        )

    def _has_numerical_criteria(self, response: str) -> bool:
        """Check for numerical criteria."""
        return bool(
            re.search(
                r"\d+.*(?:mmhg|bpm|mg/dl|%|\s*<\s*|\s*>\s*)", response, re.IGNORECASE
            )
        )

    def _mentions_contraindications(self, response: str) -> bool:
        """Check for contraindication mentions."""
        return bool(
            re.search(
                r"contraindication|avoid|do not|not recommended",
                response,
                re.IGNORECASE,
            )
        )

    def _extract_numeric_dose(self, dose_str: str) -> Optional[float]:
        """Extract numeric dose value."""
        match = re.search(r"(\d+(?:\.\d+)?)", dose_str)
        return float(match.group(1)) if match else None

    # Static data loading methods

    def _load_drug_safety_ranges(self) -> Dict[str, Dict[str, float]]:
        """Load drug safety ranges (would be from database/file in production)."""
        return {
            "epinephrine": {"min": 0.1, "max": 10.0, "unit": "mg"},
            "heparin": {"min": 5000, "max": 40000, "unit": "units"},
            "morphine": {"min": 1, "max": 20, "unit": "mg"},
            "insulin": {"min": 1, "max": 100, "unit": "units"},
        }

    def _load_contraindications(self) -> Dict[str, List[str]]:
        """Load drug contraindications."""
        return {
            "aspirin": [
                "active bleeding",
                "severe asthma",
                "children with viral illness",
            ],
            "morphine": ["respiratory depression", "severe asthma", "paralytic ileus"],
            "heparin": ["active bleeding", "thrombocytopenia", "recent surgery"],
        }

    def _load_high_alert_medications(self) -> List[str]:
        """Load high-alert medication list."""
        return [
            "insulin",
            "heparin",
            "warfarin",
            "chemotherapy",
            "epinephrine",
            "morphine",
            "fentanyl",
            "potassium",
            "magnesium",
            "concentrated electrolytes",
        ]
