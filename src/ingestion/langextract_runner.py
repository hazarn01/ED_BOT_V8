from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import langextract as lx  # noqa: F401

    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False

from src.utils.logging import get_logger
from src.utils.observability import track_latency

logger = get_logger(__name__)


class LangExtractRunner:
    """Structured entity extraction using LangExtract with local models."""

    def __init__(self):
        if not LANGEXTRACT_AVAILABLE:
            logger.warning(
                "LangExtract not available. Install with: pip install langextract"
            )
            self.enabled = False
        else:
            self.enabled = True
            logger.info("LangExtractRunner initialized")

    async def extract_entities(
        self, text: str, document_id: str, page_numbers: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Extract structured entities from document text."""
        if not self.enabled:
            logger.warning("LangExtract not available, skipping extraction")
            return []

        entities = []

        try:
            with track_latency("langextract_extraction", {"document_id": document_id}):
                # Extract different types of medical entities
                contact_entities = await self._extract_contacts(text)
                dosage_entities = await self._extract_dosages(text)
                protocol_entities = await self._extract_protocol_steps(text)
                criteria_entities = await self._extract_criteria(text)
                timing_entities = await self._extract_timing_info(text)

                # Combine all entities
                all_entities = (
                    contact_entities
                    + dosage_entities
                    + protocol_entities
                    + criteria_entities
                    + timing_entities
                )

                # Add metadata to each entity
                for entity in all_entities:
                    entity.update(
                        {
                            "document_id": document_id,
                            "extracted_at": datetime.utcnow().isoformat(),
                            "extractor": "langextract",
                            "confidence": entity.get("confidence", 0.8),
                        }
                    )

                entities.extend(all_entities)

                logger.info(
                    "Entity extraction completed",
                    extra_fields={
                        "document_id": document_id,
                        "total_entities": len(entities),
                        "contacts": len(contact_entities),
                        "dosages": len(dosage_entities),
                        "protocol_steps": len(protocol_entities),
                        "criteria": len(criteria_entities),
                        "timing_info": len(timing_entities),
                    },
                )

        except Exception as e:
            logger.error(
                f"Entity extraction failed: {e}",
                extra_fields={"document_id": document_id},
            )
            # Return empty list on failure rather than crashing
            return []

        return entities

    async def _extract_contacts(self, text: str) -> List[Dict[str, Any]]:
        """Extract contact information (names, roles, phone numbers)."""
        try:
            # Define extraction schema for contacts (commented for future use)
            # contact_schema = {
            #     "description": "Extract contact information including names, roles, phone numbers, and pager numbers",
            #     "examples": [...]
            # }

            # Use mock extraction for now (replace with actual LangExtract call)
            contacts = await self._mock_contact_extraction(text)
            return contacts

        except Exception as e:
            logger.error(f"Contact extraction failed: {e}")
            return []

    async def _extract_dosages(self, text: str) -> List[Dict[str, Any]]:
        """Extract medication dosage information."""
        try:
            # Define extraction schema for dosages (commented for future use)
            # dosage_schema = {
            #     "description": "Extract medication dosages including drug name, dose, route, frequency",
            #     "examples": [...]
            # }

            # Use mock extraction for now
            dosages = await self._mock_dosage_extraction(text)
            return dosages

        except Exception as e:
            logger.error(f"Dosage extraction failed: {e}")
            return []

    async def _extract_protocol_steps(self, text: str) -> List[Dict[str, Any]]:
        """Extract protocol steps with timing and sequence."""
        try:
            # Define extraction schema for protocol steps (commented for future use)
            # protocol_schema = {
            #     "description": "Extract protocol steps with sequence, timing, and actions",
            #     "examples": [...]
            # }

            # Use mock extraction for now
            steps = await self._mock_protocol_extraction(text)
            return steps

        except Exception as e:
            logger.error(f"Protocol extraction failed: {e}")
            return []

    async def _extract_criteria(self, text: str) -> List[Dict[str, Any]]:
        """Extract clinical criteria and thresholds."""
        try:
            criteria = await self._mock_criteria_extraction(text)
            return criteria

        except Exception as e:
            logger.error(f"Criteria extraction failed: {e}")
            return []

    async def _extract_timing_info(self, text: str) -> List[Dict[str, Any]]:
        """Extract timing information and deadlines."""
        try:
            timing = await self._mock_timing_extraction(text)
            return timing

        except Exception as e:
            logger.error(f"Timing extraction failed: {e}")
            return []

    # Mock extraction methods (replace with actual LangExtract calls)

    async def _mock_contact_extraction(self, text: str) -> List[Dict[str, Any]]:
        """Mock contact extraction using regex patterns."""
        import re

        contacts = []

        # Phone number patterns
        phone_pattern = r"(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})"
        # pager_pattern = r'pager:?\s*(\d{4,6})'  # Commented for future use

        # Find phone numbers and try to associate with names/roles
        phone_matches = re.finditer(phone_pattern, text, re.IGNORECASE)

        for i, match in enumerate(phone_matches):
            phone = match.group(1)
            start_pos = max(0, match.start() - 100)
            end_pos = min(len(text), match.end() + 100)
            context = text[start_pos:end_pos]

            # Try to find associated name and role
            name_patterns = [
                r"Dr\.?\s+([A-Z][a-z]+)",
                r"([A-Z][a-z]+)\s+([A-Z][a-z]+)",
            ]

            name = None
            for pattern in name_patterns:
                name_match = re.search(pattern, context)
                if name_match:
                    name = name_match.group(0)
                    break

            # Try to find role
            role_patterns = [
                r"(attending|fellow|resident|nurse|physician)",
                r"(cardiology|emergency|surgery|medicine)\s+(attending|fellow)",
            ]

            role = None
            for pattern in role_patterns:
                role_match = re.search(pattern, context, re.IGNORECASE)
                if role_match:
                    role = role_match.group(0)
                    break

            contact = {
                "entity_type": "contact",
                "payload": {
                    "type": "contact",
                    "phone": phone,
                    "name": name or "Unknown",
                    "role": role or "Unknown",
                    "evidence_text": context.strip(),
                },
                "span": {"start": match.start(), "end": match.end()},
                "confidence": 0.7,
            }

            contacts.append(contact)

        return contacts

    async def _mock_dosage_extraction(self, text: str) -> List[Dict[str, Any]]:
        """Mock dosage extraction using regex patterns."""
        import re

        dosages = []

        # Common dosage patterns
        dosage_patterns = [
            r"(\w+)\s+(\d+(?:\.\d+)?)\s*(mg|ml|g|units?|mcg|L)\s*(IV|IM|PO|SQ)?",
            r"(\w+)\s+(\d+(?:\.\d+)?)\s*(mg/kg|units/kg|ml/kg)",
        ]

        for pattern in dosage_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                drug = match.group(1)
                dose_amount = match.group(2)
                dose_unit = match.group(3)
                route = match.group(4) if len(match.groups()) >= 4 else None

                # Skip if drug name is too generic
                if drug.lower() in ["give", "administer", "use", "take"]:
                    continue

                dosage = {
                    "entity_type": "dosage",
                    "payload": {
                        "type": "dosage",
                        "drug": drug,
                        "dose": f"{dose_amount} {dose_unit}",
                        "route": route,
                        "evidence_text": match.group(0),
                    },
                    "span": {"start": match.start(), "end": match.end()},
                    "confidence": 0.6,
                }

                dosages.append(dosage)

        return dosages

    async def _mock_protocol_extraction(self, text: str) -> List[Dict[str, Any]]:
        """Mock protocol step extraction."""
        import re

        steps = []

        # Look for numbered steps
        step_pattern = r"(\d+)\.?\s+([^.]+(?:\.[^0-9][^.]*)*)"
        matches = re.finditer(step_pattern, text)

        for match in matches:
            step_num = int(match.group(1))
            action_text = match.group(2).strip()

            # Extract timing information from action text
            timing_pattern = r"within\s+(\d+)\s+(minutes?|hours?|seconds?)"
            timing_match = re.search(timing_pattern, action_text, re.IGNORECASE)

            step = {
                "entity_type": "protocol_step",
                "payload": {
                    "type": "protocol_step",
                    "step_number": step_num,
                    "action": action_text,
                    "timing": timing_match.group(0) if timing_match else None,
                    "evidence_text": match.group(0),
                },
                "span": {"start": match.start(), "end": match.end()},
                "confidence": 0.8,
            }

            steps.append(step)

        return steps

    async def _mock_criteria_extraction(self, text: str) -> List[Dict[str, Any]]:
        """Mock criteria extraction."""
        import re

        criteria = []

        # Look for criteria patterns
        criteria_patterns = [
            r"if\s+([^,]+),?\s+then\s+([^.]+)",
            r"when\s+([^,]+),?\s+([^.]+)",
            r"criteria:?\s*([^.]+)",
        ]

        for pattern in criteria_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                criterion = {
                    "entity_type": "criteria",
                    "payload": {
                        "type": "criteria",
                        "condition": match.group(1)
                        if len(match.groups()) >= 2
                        else match.group(1),
                        "action": match.group(2) if len(match.groups()) >= 2 else None,
                        "evidence_text": match.group(0),
                    },
                    "span": {"start": match.start(), "end": match.end()},
                    "confidence": 0.6,
                }

                criteria.append(criterion)

        return criteria

    async def _mock_timing_extraction(self, text: str) -> List[Dict[str, Any]]:
        """Mock timing information extraction."""
        import re

        timing_info = []

        # Timing patterns
        timing_patterns = [
            r"within\s+(\d+)\s+(minutes?|hours?|seconds?)",
            r"every\s+(\d+)\s+(minutes?|hours?)",
            r"(\d+)\s+(minutes?|hours?)\s+after",
        ]

        for pattern in timing_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                timing = {
                    "entity_type": "timing",
                    "payload": {
                        "type": "timing",
                        "timing_text": match.group(0),
                        "value": int(match.group(1)),
                        "unit": match.group(2).rstrip("s"),
                        "evidence_text": match.group(0),
                    },
                    "span": {"start": match.start(), "end": match.end()},
                    "confidence": 0.7,
                }

                timing_info.append(timing)

        return timing_info
