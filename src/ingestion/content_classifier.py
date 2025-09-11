"""
Enhanced document classification logic for mapping medical documents to 6 query types.
Maps documents to CONTACT, FORM, PROTOCOL, CRITERIA, DOSAGE, or SUMMARY categories
with confidence scoring based on comprehensive analysis of filename and content.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from src.models.query_types import QueryType
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentClassification:
    """Result of document classification with metadata."""
    query_type: QueryType
    confidence: float
    method: str  # 'filename' | 'content' | 'hybrid'
    evidence: List[str]  # Keywords/patterns that led to classification
    medical_specialty: Optional[str] = None
    urgency_level: Optional[str] = None
    primary_keywords: List[str] = None
    medical_terms: List[str] = None
    abbreviations: List[str] = None

    def __post_init__(self):
        if self.primary_keywords is None:
            self.primary_keywords = []
        if self.medical_terms is None:
            self.medical_terms = []
        if self.abbreviations is None:
            self.abbreviations = []


class ParsedDocument(NamedTuple):
    """Structure for parsed document content."""
    filename: str
    content: str
    metadata: Dict[str, Any]


class ContentClassifier:
    """Maps medical documents to 6 query types with confidence scoring."""

    def __init__(self):
        # Medical terminology patterns for each query type
        self.query_patterns = self._compile_query_patterns()
        self.medical_specialties = self._compile_specialty_patterns()
        self.urgency_patterns = self._compile_urgency_patterns()
        self.medical_abbreviations = self._load_medical_abbreviations()
        
        logger.info("ContentClassifier initialized with enhanced pattern matching")

    def _compile_query_patterns(self) -> Dict[QueryType, List[re.Pattern]]:
        """Compile regex patterns for each query type classification."""
        return {
            QueryType.FORM_RETRIEVAL: [
                re.compile(r'\b(consent|form|checklist|template|agreement)\b', re.IGNORECASE),
                re.compile(r'\b(admission|discharge|transfusion|procedure\s+consent)\b', re.IGNORECASE),
                re.compile(r'\b(ama|autopsy|transfer|pca)\s+(form|departure)\b', re.IGNORECASE),
                re.compile(r'\b(blood\s+transfusion|pathology|clinical\s+debriefing)\b.*\b(form|consent)\b', re.IGNORECASE),
                re.compile(r'\b(bed\s+request|radiology\s+request|downtime)\b.*\bform\b', re.IGNORECASE),
                re.compile(r'\b(patient\s+identification|medication\s+reconciliation)\b', re.IGNORECASE),
            ],
            
            QueryType.PROTOCOL_STEPS: [
                re.compile(r'\b(protocol|procedure|pathway|algorithm|guideline)\b', re.IGNORECASE),
                re.compile(r'\b(stemi|sepsis|stroke|trauma|cardiac\s+arrest)\b.*\b(protocol|activation|management)\b', re.IGNORECASE),
                re.compile(r'\b(activation|emergency\s+response|code\s+blue|code\s+stroke)\b', re.IGNORECASE),
                re.compile(r'\b(workflow|standard\s+operating|clinical\s+pathway)\b', re.IGNORECASE),
                re.compile(r'\b(tpa|thrombolytic|cath\s+lab|door\s+to\s+balloon)\b', re.IGNORECASE),
                re.compile(r'\b(resuscitation|intubation|airway\s+management)\b', re.IGNORECASE),
            ],

            QueryType.CONTACT_LOOKUP: [
                re.compile(r'\b(on.?call|contact|directory|phone|pager)\b', re.IGNORECASE),
                re.compile(r'\b(attending|fellow|resident|consultant)\b.*\b(contact|phone|pager)\b', re.IGNORECASE),
                re.compile(r'\b(coverage|schedule|roster|staff\s+directory)\b', re.IGNORECASE),
                re.compile(r'\b(cardiology|surgery|medicine|radiology)\b.*\b(contact|call|consult)\b', re.IGNORECASE),
                re.compile(r'\b(emergency\s+contact|after\s+hours|weekend\s+coverage)\b', re.IGNORECASE),
            ],

            QueryType.CRITERIA_CHECK: [
                re.compile(r'\b(criteria|indication|contraindication|threshold|cutoff)\b', re.IGNORECASE),
                re.compile(r'\b(ottawa|wells|centor|nexus|perc|pecarn)\b.*\b(rules?|score|criteria)\b', re.IGNORECASE),
                re.compile(r'\b(rules?|score)\b.*\b(ottawa|wells|centor|nexus|perc|pecarn)\b', re.IGNORECASE),
                re.compile(r'\b(when\s+to|should\s+i|eligibility|exclusion)\b', re.IGNORECASE),
                re.compile(r'\b(activate|call|consult|transfer)\b.*\b(when|criteria|indication)\b', re.IGNORECASE),
                re.compile(r'\b(admission\s+criteria|discharge\s+criteria|decision\s+rule)\b', re.IGNORECASE),
            ],

            QueryType.DOSAGE_LOOKUP: [
                re.compile(r'\b(dose|dosage|dosing|how\s+much|administration)\b', re.IGNORECASE),
                re.compile(r'\b(mg|ml|units|mcg|g|kg|lb)\b.*\b(give|administer|dose)\b', re.IGNORECASE),
                re.compile(r'\b(medication|drug|medicine)\b.*\b(dose|amount|dosing)\b', re.IGNORECASE),
                re.compile(r'\b(epinephrine|heparin|morphine|insulin|antibiotics)\b.*\b(dose|dosing|dosage)\b', re.IGNORECASE),
                re.compile(r'\b(pediatric|adult|weight.based)\b.*\bdos(e|ing|age)\b', re.IGNORECASE),
                re.compile(r'\b(iv|po|im|sq|sublingual)\b.*\b(dose|administration)\b', re.IGNORECASE),
            ],

            QueryType.SUMMARY_REQUEST: [
                re.compile(r'\b(overview|summary|general|information|guide|manual)\b', re.IGNORECASE),
                re.compile(r'\b(handbook|reference|guidelines|recommendations)\b', re.IGNORECASE),
                re.compile(r'\b(workup|evaluation|assessment|approach)\b', re.IGNORECASE),
                re.compile(r'\b(management|treatment|care\s+plan)\b', re.IGNORECASE),
                re.compile(r'\b(introduction|background|review|update)\b', re.IGNORECASE),
                re.compile(r'\b(policy|standard|best\s+practice)\b', re.IGNORECASE),
            ],
        }

    def _compile_specialty_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile patterns for medical specialty identification."""
        return {
            'cardiology': [
                re.compile(r'\b(cardiac|heart|stemi|mi|ecg|ekg|chest\s+pain)\b', re.IGNORECASE),
                re.compile(r'\b(cath\s+lab|angiogram|pci|cabg|arrhythmia)\b', re.IGNORECASE),
            ],
            'emergency': [
                re.compile(r'\b(emergency|ed|er|trauma|resuscitation|code)\b', re.IGNORECASE),
                re.compile(r'\b(triage|acuity|stabilization|critical)\b', re.IGNORECASE),
            ],
            'neurology': [
                re.compile(r'\b(stroke|tpa|neuro|brain|seizure|consciousness)\b', re.IGNORECASE),
                re.compile(r'\b(headache|migraine|neurological)\b', re.IGNORECASE),
            ],
            'infectious_disease': [
                re.compile(r'\b(sepsis|infection|antibiotic|fever|culture)\b', re.IGNORECASE),
                re.compile(r'\b(pneumonia|uti|cellulitis|meningitis)\b', re.IGNORECASE),
            ],
            'pharmacy': [
                re.compile(r'\b(medication|drug|dose|dosage|pharmacy)\b', re.IGNORECASE),
                re.compile(r'\b(prescription|administration|interaction)\b', re.IGNORECASE),
            ],
            'radiology': [
                re.compile(r'\b(ct|mri|xray|ultrasound|imaging)\b', re.IGNORECASE),
                re.compile(r'\b(contrast|scan|radiology|radiologist)\b', re.IGNORECASE),
            ],
        }

    def _compile_urgency_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile patterns for urgency level identification."""
        return {
            'stat': [
                re.compile(r'\b(stat|emergency|urgent|immediate|critical)\b', re.IGNORECASE),
                re.compile(r'\b(code\s+(blue|stroke|stemi)|activation)\b', re.IGNORECASE),
            ],
            'urgent': [
                re.compile(r'\b(urgent|priority|expedite|asap)\b', re.IGNORECASE),
                re.compile(r'\b(time\s+sensitive|rapid|fast\s+track)\b', re.IGNORECASE),
            ],
            'routine': [
                re.compile(r'\b(routine|standard|regular|scheduled)\b', re.IGNORECASE),
                re.compile(r'\b(elective|planned|non.urgent)\b', re.IGNORECASE),
            ],
        }

    def _load_medical_abbreviations(self) -> List[str]:
        """Load common medical abbreviations for extraction."""
        # Common ED/medical abbreviations - in practice, load from medical_abbreviations.json
        return [
            'MI', 'STEMI', 'NSTEMI', 'ACS', 'CHF', 'COPD', 'PE', 'DVT', 'UTI',
            'GI', 'CNS', 'ICU', 'CCU', 'OR', 'ER', 'ED', 'EKG', 'ECG', 'CBC',
            'BMP', 'CMP', 'PT', 'PTT', 'INR', 'BNP', 'CRP', 'ESR', 'WBC', 'RBC',
            'IV', 'PO', 'IM', 'SQ', 'NPO', 'PRN', 'TID', 'BID', 'QID', 'QD'
        ]

    def classify_document(self, parsed_doc: ParsedDocument) -> DocumentClassification:
        """Primary classification method combining multiple signals."""
        logger.info(f"Classifying document: {parsed_doc.filename}")

        # Multi-signal classification
        filename_result = self._classify_by_filename(parsed_doc.filename)
        content_result = self._classify_by_content(parsed_doc.content)
        
        # Weighted scoring: content analysis is more important than filename
        final_classification = self._combine_classifications([
            (content_result, 0.7),    # Content analysis weight
            (filename_result, 0.3),   # Filename analysis weight
        ])

        # Enhance with medical metadata
        medical_specialty = self._extract_medical_specialty(parsed_doc.content)
        urgency_level = self._extract_urgency_level(parsed_doc.content)
        primary_keywords = self._extract_primary_keywords(parsed_doc.content, final_classification.query_type)
        medical_terms = self._extract_medical_terms(parsed_doc.content)
        abbreviations = self._extract_abbreviations(parsed_doc.content)

        result = DocumentClassification(
            query_type=final_classification.query_type,
            confidence=final_classification.confidence,
            method='hybrid',
            evidence=final_classification.evidence,
            medical_specialty=medical_specialty,
            urgency_level=urgency_level,
            primary_keywords=primary_keywords,
            medical_terms=medical_terms,
            abbreviations=abbreviations
        )

        logger.info(
            f"Document classified as {result.query_type.value} "
            f"(confidence: {result.confidence:.2f}, specialty: {medical_specialty})"
        )

        return result

    def _classify_by_filename(self, filename: str) -> DocumentClassification:
        """Filename-based classification using pattern matching."""
        filename.lower()
        scores = {}

        # Score each query type based on filename patterns
        for query_type, patterns in self.query_patterns.items():
            score = 0.0
            evidence = []
            
            for pattern in patterns:
                if pattern.search(filename):
                    score += 0.4
                    # Extract the matched text for evidence
                    match = pattern.search(filename)
                    if match:
                        evidence.append(match.group())

            if score > 0:
                scores[query_type] = (min(score, 1.0), evidence)

        if not scores:
            return DocumentClassification(
                query_type=QueryType.SUMMARY_REQUEST,
                confidence=0.1,
                method='filename',
                evidence=['no_filename_patterns_matched']
            )

        # Get highest scoring type
        best_type = max(scores.keys(), key=lambda x: scores[x][0])
        confidence, evidence = scores[best_type]

        return DocumentClassification(
            query_type=best_type,
            confidence=confidence,
            method='filename',
            evidence=evidence
        )

    def _classify_by_content(self, content: str) -> DocumentClassification:
        """Content-based classification using medical terminology analysis."""
        if not content or len(content.strip()) < 50:
            return DocumentClassification(
                query_type=QueryType.SUMMARY_REQUEST,
                confidence=0.2,
                method='content',
                evidence=['insufficient_content']
            )

        content_lower = content.lower()
        scores = {}

        # Score each query type based on content patterns
        for query_type, patterns in self.query_patterns.items():
            score = 0.0
            evidence = []

            for pattern in patterns:
                matches = pattern.findall(content_lower)
                if matches:
                    # Weight by frequency, but with diminishing returns
                    pattern_score = min(len(matches) * 0.1, 0.4)
                    score += pattern_score
                    evidence.extend(matches[:3])  # Limit evidence to prevent bloat

            if score > 0:
                scores[query_type] = (min(score, 1.0), evidence)

        if not scores:
            return DocumentClassification(
                query_type=QueryType.SUMMARY_REQUEST,
                confidence=0.3,
                method='content',
                evidence=['no_content_patterns_matched']
            )

        # Get highest scoring type
        best_type = max(scores.keys(), key=lambda x: scores[x][0])
        confidence, evidence = scores[best_type]

        # Boost confidence for substantial content with clear indicators
        if len(content.split()) > 100 and confidence > 0.5:
            confidence = min(confidence * 1.2, 1.0)

        return DocumentClassification(
            query_type=best_type,
            confidence=confidence,
            method='content',
            evidence=evidence
        )

    def _combine_classifications(
        self, 
        weighted_results: List[Tuple[DocumentClassification, float]]
    ) -> DocumentClassification:
        """Combine multiple classification results with weighting."""
        
        if not weighted_results:
            return DocumentClassification(
                query_type=QueryType.SUMMARY_REQUEST,
                confidence=0.1,
                method='fallback',
                evidence=['no_classification_results']
            )

        # Calculate weighted scores for each query type
        query_scores = {}
        all_evidence = []

        for classification, weight in weighted_results:
            query_type = classification.query_type
            weighted_score = classification.confidence * weight
            
            if query_type not in query_scores:
                query_scores[query_type] = 0.0
            query_scores[query_type] += weighted_score
            all_evidence.extend(classification.evidence)

        # Find best query type
        best_type = max(query_scores.keys(), key=lambda x: query_scores[x])
        final_confidence = min(query_scores[best_type], 1.0)

        return DocumentClassification(
            query_type=best_type,
            confidence=final_confidence,
            method='combined',
            evidence=list(set(all_evidence))  # Remove duplicates
        )

    def _extract_medical_specialty(self, content: str) -> Optional[str]:
        """Extract medical specialty from content."""
        content_lower = content.lower()
        specialty_scores = {}

        for specialty, patterns in self.medical_specialties.items():
            score = 0
            for pattern in patterns:
                score += len(pattern.findall(content_lower))
            if score > 0:
                specialty_scores[specialty] = score

        if specialty_scores:
            return max(specialty_scores.keys(), key=lambda x: specialty_scores[x])
        return None

    def _extract_urgency_level(self, content: str) -> Optional[str]:
        """Extract urgency level from content."""
        content_lower = content.lower()
        
        for urgency, patterns in self.urgency_patterns.items():
            for pattern in patterns:
                if pattern.search(content_lower):
                    return urgency
        return 'routine'  # Default urgency

    def _extract_primary_keywords(self, content: str, query_type: QueryType) -> List[str]:
        """Extract primary keywords relevant to the query type."""
        keywords = []
        content_lower = content.lower()

        # Get patterns for this query type
        patterns = self.query_patterns.get(query_type, [])
        for pattern in patterns:
            matches = pattern.findall(content_lower)
            keywords.extend(matches)

        # Return unique keywords, limited to prevent bloat
        return list(set(keywords))[:10]

    def _extract_medical_terms(self, content: str) -> List[str]:
        """Extract medical terminology from content."""
        medical_terms = []
        
        # Look for medical terms (this is simplified - in practice, use medical ontology)
        medical_indicators = [
            r'\b\w+itis\b',  # Conditions ending in -itis
            r'\b\w+osis\b',  # Conditions ending in -osis  
            r'\b\w+emia\b',  # Blood conditions
            r'\b\w+gram\b',  # Diagnostic tests
        ]

        for indicator in medical_indicators:
            pattern = re.compile(indicator, re.IGNORECASE)
            matches = pattern.findall(content)
            medical_terms.extend(matches)

        return list(set(medical_terms))[:10]

    def _extract_abbreviations(self, content: str) -> List[str]:
        """Extract medical abbreviations from content."""
        found_abbreviations = []
        
        # Look for known medical abbreviations
        for abbrev in self.medical_abbreviations:
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            if re.search(pattern, content, re.IGNORECASE):
                found_abbreviations.append(abbrev)

        return found_abbreviations[:15]  # Limit to prevent bloat