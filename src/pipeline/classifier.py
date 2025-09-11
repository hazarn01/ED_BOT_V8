import re
from typing import Any, Dict, Optional, Tuple

from src.ai.azure_fallback_client import AzureOpenAIClient
from src.ai.gpt_oss_client import GPTOSSClient
from src.ai.prompts import PROMPTS
from src.models.classification import ClassificationResult
from src.models.query_types import QueryType
from src.utils.logging import get_logger
from src.utils.observability import metrics, track_latency

logger = get_logger(__name__)


class QueryClassifier:
    """Classify medical queries into 6 types with high accuracy."""

    def __init__(
        self,
        llm_client = None,
        primary_client: Optional[GPTOSSClient] = None,
        fallback_client: Optional[AzureOpenAIClient] = None,
    ):
        # Handle unified client or separate clients
        if llm_client is not None:
            self.primary_client = llm_client
            self.fallback_client = None
        else:
            self.primary_client = primary_client
            self.fallback_client = fallback_client

        # Pre-compiled regex patterns for fast classification
        self._patterns = self._compile_classification_patterns()

        # Deterministic overlay keywords (Task 34 + PRP-40)
        self._overlay_map = {
            QueryType.PROTOCOL_STEPS: {
                "keywords": [
                    "protocol", "stemi", "stroke code", "evd", "sepsis", "workflow", "steps", "ed sepsis"
                ]
            },
            QueryType.CRITERIA_CHECK: {
                "keywords": [
                    "criteria", "rules", "guideline", "ottawa", "wells", "perc", "nexus", "centor"
                ]
            },
            QueryType.DOSAGE_LOOKUP: {
                "keywords": [
                    "dose", "dosing", "mg/kg", "mcg", "dosage"
                ]
            },
            QueryType.FORM_RETRIEVAL: {
                "keywords": [
                    "form", "consent", "request", "checklist"
                ]
            },
        }

        logger.info(
            "QueryClassifier initialized",
            extra_fields={
                "has_primary": self.primary_client is not None,
                "has_fallback": self.fallback_client is not None,
            },
        )

    def _compile_classification_patterns(self) -> Dict[QueryType, list]:
        """Compile regex patterns for quick classification."""
        patterns = {
            QueryType.CONTACT_LOOKUP: [
                re.compile(
                    r"\b(who\s+is\s+on\s+call|on\s+call|contact|phone|pager)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(attending|fellow|resident)\b.*\b(today|tonight|now)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(call|reach|contact)\b.*\b(cardiology|surgery|medicine)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(directory|phone\s+number|pager\s+number)\b", re.IGNORECASE
                ),
            ],
            QueryType.FORM_RETRIEVAL: [
                re.compile(r"\b(show\s+me|find|get|need)\b.*\bform\b", re.IGNORECASE),
                re.compile(r"\b(consent|checklist|template|document)\b", re.IGNORECASE),
                re.compile(
                    r"\b(pdf|download|print)\b.*\b(form|consent)\b", re.IGNORECASE
                ),
                re.compile(
                    r"\b(where\s+is|where\s+can\s+i\s+find)\b.*\b(form|consent)\b",
                    re.IGNORECASE,
                ),
                re.compile(r"\b(ama|autopsy|transfer|pca)\s+(form|departure)\b", re.IGNORECASE),
                re.compile(r"\b(blood\s+transfusion|pathology|clinical\s+debriefing)\b.*\b(form|consent)\b", re.IGNORECASE),
                re.compile(r"\b(bed\s+request|radiology\s+request|downtime)\b.*\bform\b", re.IGNORECASE),
            ],
            QueryType.PROTOCOL_STEPS: [
                re.compile(
                    r"\b(protocol|procedure|how\s+to|steps|algorithm)\b", re.IGNORECASE
                ),
                re.compile(
                    r"\b(what\s+is\s+the.*protocol|.*protocol\s+for)\b", re.IGNORECASE
                ),
                re.compile(r"\b(manage|treatment|workflow|pathway)\b", re.IGNORECASE),
                re.compile(
                    r"\b(stemi|stroke|trauma|sepsis|cardiac\s+arrest)\b.*\b(protocol|management)\b",
                    re.IGNORECASE,
                ),
            ],
            QueryType.CRITERIA_CHECK: [
                re.compile(
                    r"\b(criteria|when\s+to|should\s+i|indication)\b", re.IGNORECASE
                ),
                re.compile(
                    r"\b(what\s+are\s+the\s+criteria|criteria\s+for)\b", re.IGNORECASE
                ),
                re.compile(
                    r"\b(activate|call|consult|transfer)\b.*\b(when|criteria)\b",
                    re.IGNORECASE,
                ),
                re.compile(r"\b(threshold|cutoff|limit|range)\b", re.IGNORECASE),
                re.compile(
                    r"\b(contraindication|exclusion|eligibility)\b", re.IGNORECASE
                ),
                re.compile(
                    r"\b(ottawa|wells|centor|nexus|perc|pecarn)\b.*\b(rules?|score|criteria)\b", re.IGNORECASE
                ),
                re.compile(
                    r"\b(rules?|score)\b.*\b(ottawa|wells|centor|nexus|perc|pecarn)\b", re.IGNORECASE
                ),
            ],
            QueryType.DOSAGE_LOOKUP: [
                re.compile(r"\b(dose|dosage|dosing|how\s+much)\b", re.IGNORECASE),
                re.compile(
                    r"\b(mg|ml|units|mcg|g)\b.*\b(give|administer|dose)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(medication|drug|medicine)\b.*\b(dose|amount)\b", re.IGNORECASE
                ),
                re.compile(
                    r"\b(epinephrine|heparin|morphine|insulin|antibiotics)\b.*\b(dose|dosing|dosage)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(epinephrine|heparin|morphine|insulin|antibiotics)\s+(dose|dosing|dosage)\b",
                    re.IGNORECASE,
                ),
            ],
            QueryType.SUMMARY_REQUEST: [
                re.compile(
                    r"\b(tell\s+me\s+about|overview|summary|general|information)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(what\s+is|explain|describe)\b(?!.*\b(protocol|dose|form|criteria|contact)\b)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(workup|evaluation|assessment|diagnosis)\b", re.IGNORECASE
                ),
                re.compile(r"\b(guidelines|recommendations|approach)\b", re.IGNORECASE),
            ],
        }

        return patterns

    async def classify_query(self, query: str) -> ClassificationResult:
        """Classify query using rule-based + LLM approach."""
        query = query.strip()

        logger.info("Classifying query", extra_fields={"query_length": len(query)})

        try:
            with track_latency("query_classification"):
                # 0. Deterministic pre-classifier overlay (Task 34)
                overlay = self._apply_deterministic_overlay(query)
                if overlay is not None:
                    result = ClassificationResult(
                        query_type=overlay,
                        confidence=0.6,
                        method="overlay"
                    )
                    metrics.record_query_type(result.query_type.value)
                    return result

                # 1. Try rule-based classification first (fast)
                rule_result = self._classify_with_rules(query)
                if rule_result[1] > 0.5:  # Use rule-based result if any confidence
                    result = ClassificationResult(
                        query_type=rule_result[0],
                        confidence=rule_result[1],
                        method="rules"
                    )
                    logger.info(
                        "Rule-based classification",
                        extra_fields={
                            "query_type": result.query_type.value,
                            "confidence": result.confidence,
                            "method": "rules",
                        },
                    )
                    metrics.record_query_type(result.query_type.value)
                    return result

                # 2. Use LLM for ambiguous cases
                llm_result = await self._classify_with_llm(query)

                # 3. Combine results for final decision
                final_tuple = self._combine_classifications(rule_result, llm_result)
                result = ClassificationResult(
                    query_type=final_tuple[0],
                    confidence=final_tuple[1],
                    method="hybrid"
                )

                logger.info(
                    "Query classified",
                    extra_fields={
                        "query_type": result.query_type.value,
                        "confidence": result.confidence,
                        "method": "hybrid",
                    },
                )

                metrics.record_query_type(result.query_type.value)
                return result

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            # Fallback to SUMMARY with low confidence
            return ClassificationResult(
                query_type=QueryType.SUMMARY_REQUEST,
                confidence=0.3,
                method="fallback"
            )

    def _apply_deterministic_overlay(self, query: str) -> Optional[QueryType]:
        """Lightweight pre-classifier overlay using keyword anchors (Task 34)."""
        q = query.lower()

        # Normalize protocol phrasing like "what is the X protocol"
        normalized = q.replace("what is the", " ").replace("what are the", " ")
        normalized = normalized.replace("protocol", " protocol ").replace("  ", " ")

        for qtype, cfg in self._overlay_map.items():
            for kw in cfg.get("keywords", []):
                if kw in normalized:
                    return qtype
        return None

    def _classify_with_rules(self, query: str) -> Tuple[QueryType, float]:
        """Fast rule-based classification using regex patterns."""
        scores = {}

        for query_type, patterns in self._patterns.items():
            score = 0.0
            for pattern in patterns:
                if pattern.search(query):
                    score += 0.4  # Each pattern match adds confidence

            if score > 0:
                scores[query_type] = min(score, 1.0)

        if not scores:
            # No clear pattern match - return SUMMARY with low confidence
            return QueryType.SUMMARY_REQUEST, 0.2

        # Return the highest scoring type
        best_type = max(scores.keys(), key=lambda x: scores[x])
        confidence = scores[best_type]

        # Boost confidence if query length and specificity suggest certainty
        if len(query.split()) < 10 and confidence > 0.5:
            confidence = min(confidence + 0.3, 1.0)

        return best_type, confidence

    async def _classify_with_llm(self, query: str) -> Tuple[QueryType, float]:
        """LLM-based classification for complex queries."""
        try:
            # Prepare classification prompt
            prompt = PROMPTS.get_classification_prompt(query)

            # Try primary client first
            response = None
            if self.primary_client:
                try:
                    response = await self.primary_client.generate(
                        prompt=prompt,
                        temperature=0.0,
                        top_p=0.1,
                        max_tokens=10,
                        stop=["\n", "."],
                    )
                except Exception as e:
                    logger.warning(f"Primary LLM failed: {e}")

            # Try fallback client if primary failed
            if not response and self.fallback_client:
                try:
                    response = await self.fallback_client.generate(
                        prompt=prompt,
                        temperature=0.0,
                        top_p=0.1,
                        max_tokens=10,
                        stop=["\n", "."],
                    )
                except Exception as e:
                    logger.warning(f"Fallback LLM failed: {e}")

            if not response:
                raise Exception("No LLM available for classification")

            # Parse LLM response
            content = getattr(response, 'content', str(response))
            return self._parse_llm_response(content.strip().upper())

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return QueryType.SUMMARY_REQUEST, 0.4

    def _parse_llm_response(self, response: str) -> Tuple[QueryType, float]:
        """Parse LLM response into query type and confidence."""
        # Map LLM response to QueryType
        type_mapping = {
            "CONTACT": QueryType.CONTACT_LOOKUP,
            "FORM": QueryType.FORM_RETRIEVAL,
            "PROTOCOL": QueryType.PROTOCOL_STEPS,
            "CRITERIA": QueryType.CRITERIA_CHECK,
            "DOSAGE": QueryType.DOSAGE_LOOKUP,
            "SUMMARY": QueryType.SUMMARY_REQUEST,
        }

        # Clean response and find best match
        clean_response = re.sub(r"[^A-Z]", "", response)

        for key, query_type in type_mapping.items():
            if key in clean_response:
                return query_type, 0.85  # LLM confidence

        # If no exact match, try partial matching
        for key, query_type in type_mapping.items():
            if any(word in clean_response for word in key.split()):
                return query_type, 0.7

        # Default fallback
        return QueryType.SUMMARY_REQUEST, 0.5

    def _combine_classifications(
        self, rule_result: Tuple[QueryType, float], llm_result: Tuple[QueryType, float]
    ) -> Tuple[QueryType, float]:
        """Combine rule-based and LLM results for final classification."""
        rule_type, rule_conf = rule_result
        llm_type, llm_conf = llm_result

        # If both agree, increase confidence
        if rule_type == llm_type:
            combined_conf = min(rule_conf + llm_conf * 0.3, 1.0)
            return rule_type, combined_conf

        # If they disagree, use the one with higher confidence
        if rule_conf > llm_conf:
            return (
                rule_type,
                rule_conf * 0.9,
            )  # Slight confidence penalty for disagreement
        else:
            return llm_type, llm_conf * 0.9

    def get_classification_explanation(
        self, query: str, result: ClassificationResult
    ) -> Dict[str, Any]:
        """Get explanation of classification decision for debugging."""
        # Check which patterns matched
        matched_patterns = []
        for pattern in self._patterns.get(result.query_type, []):
            if pattern.search(query):
                matched_patterns.append(pattern.pattern)

        return {
            "query": query,
            "classified_as": result.query_type.value,
            "confidence": result.confidence,
            "method": result.method,
            "matched_patterns": matched_patterns,
            "query_length": len(query),
            "word_count": len(query.split()),
        }
