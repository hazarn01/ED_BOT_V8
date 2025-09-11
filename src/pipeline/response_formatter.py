import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.ai.azure_fallback_client import AzureOpenAIClient
from src.ai.gpt_oss_client import GPTOSSClient
from src.ai.prompts import PROMPTS
from src.config import settings
from src.models.query_types import QueryType
from src.utils.logging import get_logger
from src.utils.observability import track_latency

logger = get_logger(__name__)


class ResponseFormatter:
    """Format responses with citations, PDF links, and medical safety."""

    def __init__(
        self,
        primary_client: Optional[GPTOSSClient] = None,
        fallback_client: Optional[AzureOpenAIClient] = None,
    ):
        self.primary_client = primary_client
        self.fallback_client = fallback_client

    async def format_response(
        self,
        query: str,
        query_type: QueryType,
        retrieved_data: List[Dict[str, Any]],
        confidence: float,
    ) -> Dict[str, Any]:
        """Format complete response with citations and safety checks."""

        logger.info(
            "Formatting response",
            extra_fields={
                "query_type": query_type.value,
                "source_count": len(retrieved_data),
                "confidence": confidence,
            },
        )

        try:
            with track_latency("response_formatting", {"query_type": query_type.value}):
                # Handle each query type differently
                if query_type == QueryType.FORM_RETRIEVAL:
                    response_data = await self._format_form_response(
                        query, retrieved_data
                    )
                elif query_type == QueryType.CONTACT_LOOKUP:
                    response_data = await self._format_contact_response(
                        query, retrieved_data
                    )
                elif query_type == QueryType.PROTOCOL_STEPS:
                    response_data = await self._format_protocol_response(
                        query, retrieved_data
                    )
                elif query_type == QueryType.CRITERIA_CHECK:
                    response_data = await self._format_criteria_response(
                        query, retrieved_data
                    )
                elif query_type == QueryType.DOSAGE_LOOKUP:
                    response_data = await self._format_dosage_response(
                        query, retrieved_data
                    )
                elif query_type == QueryType.SUMMARY_REQUEST:
                    response_data = await self._format_summary_response(
                        query, retrieved_data
                    )
                else:
                    response_data = await self._format_summary_response(
                        query, retrieved_data
                    )

                # Add metadata
                response_data.update(
                    {
                        "query_type": query_type.value,
                        "confidence": confidence,
                        "sources": self._extract_sources(retrieved_data),
                        "processing_time": 0.0,  # Will be set by caller
                        "warnings": [],
                    }
                )

                # Add medical warnings if needed
                warnings = await self._generate_medical_warnings(
                    query, query_type, response_data
                )
                if warnings:
                    response_data["warnings"] = warnings

                # Validate response safety
                safety_check = await self._validate_medical_safety(query, response_data)
                if not safety_check["is_safe"]:
                    response_data["warnings"].extend(safety_check["warnings"])
                    response_data["confidence"] *= (
                        0.7  # Reduce confidence for safety issues
                    )

                logger.info(
                    "Response formatted successfully",
                    extra_fields={
                        "response_length": len(response_data.get("response", "")),
                        "warning_count": len(response_data.get("warnings", [])),
                    },
                )

                return response_data

        except Exception as e:
            logger.error(f"Response formatting failed: {e}")
            return self._generate_fallback_response(query, query_type, retrieved_data)

    async def _format_form_response(
        self, query: str, retrieved_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format form response with PDF links - CRITICAL requirement."""
        response_parts = []
        pdf_links = []

        if not retrieved_data:
            return {
                "response": "I couldn't find any forms matching your request. Please check with staff for available forms.",
                "pdf_links": [],
            }

        # Group forms and create PDF links
        for item in retrieved_data:
            if item.get("type") == "form":
                display_name = item.get(
                    "display_name", item.get("source", "Unknown Form")
                )
                filename = item.get("source", "")

                # CRITICAL: Must include PDF link in specific format
                pdf_url = f"/api/v1/documents/pdf/{filename}"
                pdf_link = f"[PDF:{pdf_url}|{display_name}]"

                response_parts.append(f"• {display_name}: {pdf_link}")

                pdf_links.append(
                    {"filename": filename, "display_name": display_name, "url": pdf_url}
                )

        if response_parts:
            response_text = "Available forms:\n\n" + "\n".join(response_parts)
            response_text += "\n\nClick the PDF links above to download the forms."
        else:
            response_text = "No forms found matching your request."

        return {"response": response_text, "pdf_links": pdf_links}

    async def _format_contact_response(
        self, query: str, retrieved_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format contact response with current information."""
        if not retrieved_data:
            return {
                "response": "I couldn't find contact information for your request. Please check the hospital directory or contact the operator."
            }

        response_parts = []

        for item in retrieved_data:
            if item.get("type") in ["contact", "contact_chunk"]:
                contact_info = item.get("content", "")
                source = item.get("source", "Directory")

                # Clean up and format contact information
                formatted_contact = self._clean_contact_format(contact_info)
                response_parts.append(f"{formatted_contact}")
                # Handle both dict and string sources
                if isinstance(source, dict):
                    source_str = source.get("display_name", source.get("filename", "Unknown"))
                else:
                    source_str = source
                response_parts.append(f"Source: {source_str}")
                response_parts.append("")  # Empty line separator

        response_text = "\n".join(response_parts).strip()

        # Add timestamp for on-call information
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        response_text += f"\n\nCurrent time: {current_time}"
        response_text += (
            "\nNote: On-call schedules may change. Verify with operator if needed."
        )

        return {"response": response_text}

    async def _format_protocol_response(
        self, query: str, retrieved_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format protocol response with steps, timing, and contacts."""
        if not retrieved_data:
            return {
                "response": "I couldn't find the requested protocol. Please consult your department's protocol manual or contact your supervisor."
            }

        # Try to use LLM for better formatting if available
        if self.primary_client or self.fallback_client:
            try:
                context = self._build_context_from_data(retrieved_data)
                llm_response = await self._generate_llm_response(
                    query, QueryType.PROTOCOL_STEPS, context
                )
                if llm_response:
                    return {"response": llm_response}
            except Exception as e:
                logger.warning(f"LLM protocol formatting failed: {e}")

        # Fallback to template-based formatting
        response_parts = []

        for item in retrieved_data:
            if item.get("type") == "protocol":
                content = item.get("content", "")
                source = item.get("source", "Protocol Manual")

                # Handle both dict and string sources
                if isinstance(source, dict):
                    source_str = source.get("display_name", source.get("filename", "Unknown"))
                else:
                    source_str = source
                response_parts.append(f"Protocol from {source_str}:")
                response_parts.append(content)
                response_parts.append("")
            elif item.get("type") == "protocol_chunk":
                content = item.get("content", "")
                response_parts.append(content)
                response_parts.append("")

        response_text = "\n".join(response_parts).strip()

        # Add important safety note
        response_text += "\n\n⚠️ Always follow your institution's specific protocols and consult with attending physicians for complex cases."

        return {"response": response_text}

    async def _format_criteria_response(
        self, query: str, retrieved_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format criteria response with clear decision points."""
        if not retrieved_data:
            return {
                "response": "I couldn't find specific criteria for your request. Please consult clinical guidelines or your attending physician."
            }

        # Try LLM formatting first
        if self.primary_client or self.fallback_client:
            try:
                context = self._build_context_from_data(retrieved_data)
                llm_response = await self._generate_llm_response(
                    query, QueryType.CRITERIA_CHECK, context
                )
                if llm_response:
                    return {"response": llm_response}
            except Exception as e:
                logger.warning(f"LLM criteria formatting failed: {e}")

        # Template formatting
        response_parts = []

        for item in retrieved_data:
            content = item.get("content", "")
            source = item.get("source", "Clinical Guidelines")

            response_parts.append(f"From {source}:")
            response_parts.append(content)
            response_parts.append("")

        response_text = "\n".join(response_parts).strip()
        response_text += "\n\n⚠️ These criteria are for guidance only. Always use clinical judgment and consult with senior staff when uncertain."

        return {"response": response_text}

    async def _format_dosage_response(
        self, query: str, retrieved_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format dosage response with safety warnings - CRITICAL for patient safety."""
        if not retrieved_data:
            return {
                "response": "I couldn't find dosage information for your request. Please consult pharmacy, drug references, or your attending physician.",
                "warnings": ["No dosage information found - consult pharmacy"],
            }

        # Try LLM formatting for comprehensive safety
        if self.primary_client or self.fallback_client:
            try:
                context = self._build_context_from_data(retrieved_data)
                llm_response = await self._generate_llm_response(
                    query, QueryType.DOSAGE_LOOKUP, context
                )
                if llm_response:
                    return {
                        "response": llm_response,
                        "warnings": [
                            "Always verify dosages with pharmacy before administration"
                        ],
                    }
            except Exception as e:
                logger.warning(f"LLM dosage formatting failed: {e}")

        # Template formatting with strict safety
        response_parts = []
        warnings = []

        for item in retrieved_data:
            if item.get("type") == "dosage":
                metadata = item.get("metadata", {})
                drug = metadata.get("drug", "Unknown")
                dose = metadata.get("dose", "Unknown")
                route = metadata.get("route", "Unknown")
                frequency = metadata.get("frequency", "Unknown")

                response_parts.append(f"Drug: {drug}")
                response_parts.append(f"Dose: {dose}")
                response_parts.append(f"Route: {route}")
                if frequency and frequency != "Unknown":
                    response_parts.append(f"Frequency: {frequency}")
                response_parts.append(f"Source: {item.get('source', 'Drug Reference')}")
                response_parts.append("")

                # Add safety warnings
                if not metadata.get("safety_validated", False):
                    warnings.append(
                        f"Dosage for {drug} not safety validated - verify with pharmacy"
                    )

            else:
                content = item.get("content", "")
                response_parts.append(content)
                response_parts.append("")

        response_text = "\n".join(response_parts).strip()

        # CRITICAL safety warnings
        response_text += "\n\n🚨 SAFETY REQUIREMENTS:"
        response_text += "\n• Always verify dosages with pharmacy before administration"
        response_text += "\n• Check patient allergies and contraindications"
        response_text += "\n• Consider renal/hepatic function for dose adjustments"
        response_text += (
            "\n• Follow your institution's medication administration protocols"
        )

        warnings.append("Always verify dosages independently before administration")

        return {"response": response_text, "warnings": warnings}

    async def _format_summary_response(
        self, query: str, retrieved_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format summary response using LLM synthesis."""
        if not retrieved_data:
            return {
                "response": "I couldn't find information to answer your question. Please provide more specific details or consult medical references."
            }

        # Use LLM for synthesis
        if self.primary_client or self.fallback_client:
            try:
                context = self._build_context_from_data(retrieved_data)
                llm_response = await self._generate_llm_response(
                    query, QueryType.SUMMARY_REQUEST, context
                )
                if llm_response:
                    return {"response": llm_response}
            except Exception as e:
                logger.warning(f"LLM summary formatting failed: {e}")

        # Fallback: concatenate sources
        response_parts = []
        sources_used = set()

        for item in retrieved_data:
            content = item.get("content", "")
            source = item.get("source", "Medical Reference")

            if source not in sources_used:
                # Handle both dict and string sources
                if isinstance(source, dict):
                    source_str = source.get("display_name", source.get("filename", "Unknown"))
                else:
                    source_str = source
                response_parts.append(f"From {source_str}:")
                response_parts.append(
                    content[:500] + "..." if len(content) > 500 else content
                )
                response_parts.append("")
                sources_used.add(source)

        response_text = "\n".join(response_parts).strip()

        return {"response": response_text}

    async def _generate_llm_response(
        self, query: str, query_type: QueryType, context: str
    ) -> Optional[str]:
        """Generate response using LLM with medical prompts."""
        try:
            prompt = PROMPTS.get_response_prompt(query_type, query, context)

            # Try primary client
            if self.primary_client:
                response = await self.primary_client.generate(
                    prompt=prompt,
                    temperature=0.0,  # Deterministic for medical responses
                    top_p=0.1,
                    max_tokens=1500,
                )
                if response:
                    return response

            # Try fallback client
            if self.fallback_client and settings.disable_external_calls is False:
                response = await self.fallback_client.generate(
                    prompt=prompt, temperature=0.0, top_p=0.1, max_tokens=1500
                )
                if response:
                    return response

        except Exception as e:
            logger.error(f"LLM response generation failed: {e}")

        return None

    def _build_context_from_data(self, retrieved_data: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved data."""
        context_parts = []

        for item in retrieved_data:
            content = item.get("content", "")
            source = item.get("source", "Unknown")
            
            # Handle both dict and string sources
            if isinstance(source, dict):
                source_str = source.get("display_name", source.get("filename", "Unknown"))
            else:
                source_str = source

            context_parts.append(f"Source: {source_str}")
            context_parts.append(content)
            context_parts.append("---")

        return "\n".join(context_parts)

    def _extract_sources(self, retrieved_data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract source list with display names from retrieved data."""
        sources = []
        seen_filenames = set()

        for item in retrieved_data:
            # Handle both old format (string) and new format (dict)
            source = item.get("source", None)
            
            if source is not None:
                if isinstance(source, dict):
                    # New format with display_name and filename
                    filename = source.get("filename", "unknown")
                    if filename not in seen_filenames:
                        sources.append({
                            "display_name": source.get("display_name", filename),
                            "filename": filename
                        })
                        seen_filenames.add(filename)
                elif isinstance(source, str):
                    # Old format - just filename
                    if source not in seen_filenames:
                        display_name = source.replace('.pdf', '').replace('_', ' ').title()
                        sources.append({
                            "display_name": display_name,
                            "filename": source
                        })
                        seen_filenames.add(source)

        # Handle the sources field in retrieved_data if it exists
        for item in retrieved_data:
            if isinstance(item, dict) and "sources" in item:
                for source_item in item.get("sources", []):
                    if isinstance(source_item, dict):
                        filename = source_item.get("filename", "unknown")
                        if filename not in seen_filenames:
                            sources.append(source_item)
                            seen_filenames.add(filename)
                    elif isinstance(source_item, str):
                        if source_item not in seen_filenames:
                            display_name = source_item.replace('.pdf', '').replace('_', ' ').title()
                            sources.append({
                                "display_name": display_name,
                                "filename": source_item
                            })
                            seen_filenames.add(source_item)

        return sources

    def _clean_contact_format(self, contact_info: str) -> str:
        """Clean and format contact information."""
        # Remove extra whitespace and normalize
        lines = [line.strip() for line in contact_info.split("\n") if line.strip()]

        # Format phone numbers consistently
        formatted_lines = []
        for line in lines:
            # Format phone numbers to (xxx) xxx-xxxx
            phone_pattern = r"(\d{3})[\s.-]?(\d{3})[\s.-]?(\d{4})"
            line = re.sub(phone_pattern, r"(\1) \2-\3", line)
            formatted_lines.append(line)

        return "\n".join(formatted_lines)

    async def _generate_medical_warnings(
        self, query: str, query_type: QueryType, response_data: Dict[str, Any]
    ) -> List[str]:
        """Generate medical warnings based on query type and content."""
        warnings = []

        response_text = response_data.get("response", "").lower()

        # Dosage-specific warnings
        if query_type == QueryType.DOSAGE_LOOKUP:
            warnings.append("Always verify dosages with pharmacy before administration")

            if any(
                drug in response_text
                for drug in ["heparin", "insulin", "warfarin", "chemotherapy"]
            ):
                warnings.append(
                    "High-alert medication - requires independent double-check"
                )

        # Protocol warnings
        elif query_type == QueryType.PROTOCOL_STEPS:
            if any(term in response_text for term in ["emergency", "stat", "critical"]):
                warnings.append(
                    "Time-sensitive protocol - follow institution-specific timing requirements"
                )

        # Contact warnings
        elif query_type == QueryType.CONTACT_LOOKUP:
            warnings.append(
                "Verify on-call schedules as they may change without notice"
            )

        # General medical warnings
        if response_data.get("confidence", 1.0) < 0.7:
            warnings.append(
                "Low confidence response - please verify with additional sources"
            )

        return warnings

    async def _validate_medical_safety(
        self, query: str, response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate response for medical safety."""
        safety_result = {"is_safe": True, "warnings": [], "score": 1.0}

        response_text = response_data.get("response", "").lower()

        # Check for dangerous patterns
        dangerous_patterns = [
            r"i don't know",
            r"i'm not sure",
            r"i cannot provide medical advice",
            r"consult a doctor immediately",
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, response_text):
                safety_result["warnings"].append(
                    f"Response contains uncertain language: {pattern}"
                )
                safety_result["score"] *= 0.8

        # Check for missing required information
        if response_data.get("query_type") == "dosage":
            if not any(term in response_text for term in ["dose", "mg", "ml", "units"]):
                safety_result["warnings"].append(
                    "Dosage response missing specific dose information"
                )
                safety_result["score"] *= 0.6
                safety_result["is_safe"] = False

        # Check confidence threshold
        if response_data.get("confidence", 1.0) < settings.min_confidence_threshold:
            safety_result["warnings"].append(
                "Response confidence below safety threshold"
            )
            safety_result["score"] *= 0.7

        return safety_result

    def _generate_fallback_response(
        self, query: str, query_type: QueryType, retrieved_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate safe fallback response when formatting fails."""
        return {
            "response": (
                "I encountered an error processing your request. "
                "Please consult medical references, pharmacy, or your attending physician. "
                "For emergencies, contact your institution's emergency response team."
            ),
            "query_type": query_type.value,
            "confidence": 0.1,
            "sources": [],
            "warnings": [
                "Response formatting failed - consult additional sources",
                "This is a fallback response - verify information independently",
            ],
            "processing_time": 0.0,
        }
