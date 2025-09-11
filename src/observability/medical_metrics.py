"""
Medical domain-specific metrics for EDBotv8.

Tracks medical safety, clinical accuracy, and specialty-specific patterns.
"""

import datetime as datetime
import logging
import re
from typing import Any, Dict, List, Optional

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)
# Expose safety_alerts at module level so tests can patch it directly
from .metrics import safety_alerts  # noqa: E402

# Medical-specific metrics
medical_queries_by_specialty = Counter(
    'edbot_medical_queries_by_specialty',
    'Queries categorized by medical specialty',
    ['specialty', 'query_type']
)

protocol_adherence = Gauge(
    'edbot_protocol_adherence_score',
    'Protocol adherence score for responses',
    ['protocol_name']
)

medication_dosage_queries = Counter(
    'edbot_medication_queries_total',
    'Medication dosage queries',
    ['medication', 'route', 'query_type']
)

time_sensitive_protocols = Histogram(
    'edbot_time_sensitive_response_seconds',
    'Response time for time-sensitive protocols',
    ['protocol_type'],  # 'STEMI', 'stroke', 'sepsis'
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
)

clinical_confidence_distribution = Histogram(
    'edbot_clinical_confidence',
    'Distribution of clinical response confidence',
    ['clinical_area'],  # 'cardiology', 'emergency', 'pharmacy'
    buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0]
)

# Medical Safety Metrics
dosage_safety_checks = Counter(
    'edbot_dosage_safety_checks_total',
    'Dosage safety validation events',
    ['medication', 'check_type', 'result']  # check_type: 'range', 'interaction', 'allergy'
)

critical_protocol_access = Counter(
    'edbot_critical_protocol_access_total',
    'Access to critical time-sensitive protocols',
    ['protocol', 'time_of_day']  # Track usage patterns for critical protocols
)

medical_abbreviation_usage = Counter(
    'edbot_medical_abbreviation_usage_total',
    'Usage of medical abbreviations in queries',
    ['abbreviation', 'specialty']
)

clinical_decision_support = Counter(
    'edbot_clinical_decision_support_total',
    'Clinical decision support events',
    ['decision_type', 'confidence_level']  # decision_type: 'diagnosis', 'treatment', 'dosage'
)

# Quality Metrics
response_accuracy_feedback = Counter(
    'edbot_response_accuracy_feedback_total',
    'Accuracy feedback from users',
    ['query_type', 'accuracy_rating']  # accuracy_rating: 'correct', 'partial', 'incorrect'
)

source_citation_quality = Histogram(
    'edbot_source_citation_quality',
    'Quality score for source citations',
    ['query_type'],
    buckets=[0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0]
)

# Specialty-specific metrics
emergency_department_metrics = Counter(
    'edbot_emergency_department_queries_total',
    'Emergency department specific queries',
    ['urgency_level', 'query_category']  # urgency: 'critical', 'urgent', 'standard'
)

pharmacy_consultation_metrics = Counter(
    'edbot_pharmacy_consultation_total',
    'Pharmacy-related consultations',
    ['consultation_type', 'medication_class']
)


class MedicalMetricsCollector:
    """Medical domain-specific metrics collection"""
    
    # Medical specialty keywords
    SPECIALTY_KEYWORDS = {
        'cardiology': [
            'heart', 'cardiac', 'MI', 'STEMI', 'NSTEMI', 'angina', 'EKG', 'ECG',
            'troponin', 'arrhythmia', 'bradycardia', 'tachycardia', 'atrial',
            'ventricular', 'coronary', 'chest pain', 'pericarditis'
        ],
        'emergency': [
            'trauma', 'shock', 'CPR', 'code', 'arrest', 'emergency', 'acute',
            'critical', 'resuscitation', 'airway', 'breathing', 'circulation',
            'crash cart', 'defibrillation', 'intubation'
        ],
        'pharmacy': [
            'dosage', 'medication', 'drug', 'mg', 'mcg', 'units', 'ml', 'dose',
            'pharmacology', 'interaction', 'contraindication', 'allergy',
            'side effect', 'adverse reaction', 'prescription'
        ],
        'pulmonology': [
            'respiratory', 'lung', 'pneumonia', 'asthma', 'COPD', 'bronchitis',
            'ventilator', 'oxygen', 'intubation', 'respiratory failure',
            'pulmonary embolism', 'pneumothorax'
        ],
        'neurology': [
            'stroke', 'seizure', 'neurologic', 'brain', 'TPA', 'headache',
            'migraine', 'encephalitis', 'meningitis', 'altered mental status',
            'Glasgow coma scale', 'neurological assessment'
        ],
        'infectious_disease': [
            'infection', 'sepsis', 'antibiotic', 'fever', 'bacteremia',
            'pneumonia', 'UTI', 'cellulitis', 'abscess', 'culture',
            'sensitivity', 'resistance'
        ],
        'gastroenterology': [
            'GI', 'gastrointestinal', 'nausea', 'vomiting', 'diarrhea',
            'abdominal pain', 'bleeding', 'ulcer', 'bowel', 'liver',
            'hepatitis', 'pancreatitis'
        ]
    }
    
    # Time-sensitive protocols (response time critical)
    TIME_SENSITIVE = {
        'STEMI': 90,  # 90 minutes door-to-balloon
        'stroke': 60,  # 60 minutes door-to-needle
        'sepsis': 60,  # 1 hour sepsis bundle
        'trauma': 15,  # 15 minutes trauma activation
        'cardiac_arrest': 2,  # 2 minutes to CPR
        'anaphylaxis': 5,  # 5 minutes to epinephrine
        'respiratory_failure': 10  # 10 minutes to airway
    }
    
    # Critical medications requiring safety checks
    HIGH_RISK_MEDICATIONS = {
        'insulin': ['hypoglycemia', 'dosing_error'],
        'heparin': ['bleeding', 'dosing_error', 'interaction'],
        'warfarin': ['bleeding', 'interaction', 'monitoring'],
        'morphine': ['respiratory_depression', 'addiction'],
        'epinephrine': ['cardiac_arrhythmia', 'hypertension'],
        'digoxin': ['toxicity', 'interaction', 'monitoring'],
        'potassium': ['cardiac_arrhythmia', 'dosing_error']
    }
    
    # Medical abbreviations that may cause confusion
    MEDICAL_ABBREVIATIONS = {
        'MI': 'myocardial infarction',
        'CHF': 'congestive heart failure',
        'COPD': 'chronic obstructive pulmonary disease',
        'UTI': 'urinary tract infection',
        'DVT': 'deep vein thrombosis',
        'PE': 'pulmonary embolism',
        'GI': 'gastrointestinal',
        'IV': 'intravenous',
        'PO': 'by mouth',
        'PRN': 'as needed',
        'NPO': 'nothing by mouth',
        'ICU': 'intensive care unit',
        'ED': 'emergency department',
        'OR': 'operating room'
    }
    
    def __init__(self, settings=None):
        self.settings = settings
        self.enabled = getattr(settings, 'enable_medical_metrics', True) if settings else True
        
    def classify_medical_specialty(self, query: str) -> str:
        """Classify query by medical specialty using word-boundary matching."""
        if not query:
            return 'general'
        query_lower = query.lower()
        import re
        specialty_scores: Dict[str, int] = {}
        for specialty, keywords in self.SPECIALTY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                pattern = re.compile(r"\b" + re.escape(keyword.lower()) + r"\b")
                if pattern.search(query_lower):
                    score += 1
            if score > 0:
                specialty_scores[specialty] = score
        return max(specialty_scores, key=specialty_scores.get) if specialty_scores else 'general'
        
    def extract_medication(self, query: str) -> str:
        """Extract medication name from query (avoid false positives like 'protocol')."""
        query_lower = query.lower()
        import re
        # Explicit names first
        name_patterns = [
            r'\b(aspirin|heparin|insulin|morphine|warfarin|digoxin|epinephrine|metoprolol|lisinopril|atorvastatin)\b',
            r'\b(tylenol|advil|motrin|aleve|benadryl|pepcid|zantac)\b',
            r'\b(acetaminophen|ibuprofen|naproxen|diphenhydramine)\b',
        ]
        for pattern in name_patterns:
            m = re.search(pattern, query_lower)
            if m:
                return m.group(1)
        # Suffix heuristic with exclusions
        exclude = {"protocol", "control", "alcohol"}
        m = re.search(r'\b([a-z]+(?:ol|pril|pine|zide|mycin|cillin|ine|ide|statin))\b', query_lower)
        if m:
            candidate = m.group(1)
            if candidate not in exclude:
                return candidate
        return 'unknown'
    
    def extract_dosage_info(self, query: str) -> Dict[str, str]:
        """Extract dosage and route information"""
        query.upper()
        
        # Extract route
        route = 'unknown'
        route_patterns = {
            'IV': r'\bIV\b|\bintravenous\b',
            'PO': r'\bPO\b|\bby mouth\b|\borally\b',
            'SubQ': r'\bSubQ\b|\bsubcutaneous\b|\bSC\b',
            'IM': r'\bIM\b|\bintramuscular\b',
            'SL': r'\bSL\b|\bsublingual\b',
            'topical': r'\btopical\b|\bcream\b|\bointment\b'
        }
        
        for route_name, pattern in route_patterns.items():
            if re.search(pattern, query, flags=re.IGNORECASE):
                route = route_name
                break
        
        # Extract dose (simplified)
        dose_match = re.search(r'(\d+(?:\.\d+)?)\s*(mg|mcg|g|units?|ml)', query.lower())
        dose = dose_match.group(0) if dose_match else 'unknown'
        
        return {'route': route, 'dose': dose}
        
    def is_time_sensitive(self, query: str) -> Optional[str]:
        """Check if query relates to time-sensitive protocol"""
        query_lower = query.lower()
        
        for protocol, time_limit in self.TIME_SENSITIVE.items():
            if protocol.lower().replace('_', ' ') in query_lower:
                return protocol
                
        # Check for general time-sensitive keywords
        urgent_keywords = ['stat', 'urgent', 'emergency', 'critical', 'asap', 'immediate']
        if any(keyword in query_lower for keyword in urgent_keywords):
            return 'urgent_general'
            
        return None
        
    def get_urgency_level(self, query: str, protocol_type: Optional[str] = None) -> str:
        """Determine urgency level of medical query"""
        query_lower = query.lower()
        
        # Critical keywords
        critical_keywords = ['code', 'arrest', 'critical', 'emergency', 'stat']
        if any(keyword in query_lower for keyword in critical_keywords):
            return 'critical'
            
        # Urgent keywords or time-sensitive protocols
        if protocol_type and protocol_type in self.TIME_SENSITIVE:
            return 'urgent'
            
        urgent_keywords = ['urgent', 'asap', 'immediate', 'rapid']
        if any(keyword in query_lower for keyword in urgent_keywords):
            return 'urgent'
            
        return 'standard'
        
    def detect_medical_abbreviations(self, query: str) -> List[str]:
        """Detect medical abbreviations in query"""
        query_upper = query.upper()
        found_abbreviations = []
        
        for abbr in self.MEDICAL_ABBREVIATIONS:
            # Use word boundaries to avoid partial matches
            if re.search(r'\b' + re.escape(abbr) + r'\b', query_upper):
                found_abbreviations.append(abbr)
                
        return found_abbreviations
        
    def track_medical_query(self, query: str, query_type: str, confidence: float, 
                          response_time: float, response_content: str = ""):
        """Track medical-specific metrics"""
        if not self.enabled:
            return
            
        try:
            # Classify by specialty
            specialty = self.classify_medical_specialty(query)
            medical_queries_by_specialty.labels(
                specialty=specialty,
                query_type=query_type
            ).inc()
            
            # Track clinical confidence by area
            clinical_confidence_distribution.labels(
                clinical_area=specialty
            ).observe(confidence)
            
            # Track time-sensitive protocols
            time_sensitive_protocol = self.is_time_sensitive(query)
            if time_sensitive_protocol:
                time_sensitive_protocols.labels(
                    protocol_type=time_sensitive_protocol
                ).observe(response_time)
                
                # Track critical protocol access
                hour = datetime.datetime.now().hour
                time_period = 'day' if 6 <= hour < 18 else 'night'
                
                critical_protocol_access.labels(
                    protocol=time_sensitive_protocol,
                    time_of_day=time_period
                ).inc()
            
            # Track medication queries
            if query_type == 'DOSAGE_LOOKUP':
                medication = self.extract_medication(query)
                dosage_info = self.extract_dosage_info(query)
                
                medication_dosage_queries.labels(
                    medication=medication,
                    route=dosage_info['route'],
                    query_type=query_type
                ).inc()
                
                # Safety check for high-risk medications
                if medication in self.HIGH_RISK_MEDICATIONS:
                    risks = self.HIGH_RISK_MEDICATIONS[medication]
                    for risk in risks:
                        dosage_safety_checks.labels(
                            medication=medication,
                            check_type=risk,
                            result='checked'  # Would be 'warning' if risk detected
                        ).inc()
            
            # Track medical abbreviations
            abbreviations = self.detect_medical_abbreviations(query)
            for abbr in abbreviations:
                medical_abbreviation_usage.labels(
                    abbreviation=abbr,
                    specialty=specialty
                ).inc()
            
            # Track emergency department metrics
            if specialty == 'emergency':
                urgency = self.get_urgency_level(query, time_sensitive_protocol)
                query_category = self._categorize_ed_query(query)
                
                emergency_department_metrics.labels(
                    urgency_level=urgency,
                    query_category=query_category
                ).inc()
            
            # Track pharmacy consultations
            if specialty == 'pharmacy':
                consultation_type = self._categorize_pharmacy_query(query)
                medication_class = self._get_medication_class(query)
                
                pharmacy_consultation_metrics.labels(
                    consultation_type=consultation_type,
                    medication_class=medication_class
                ).inc()
                
        except Exception as e:
            logger.error(f"Error tracking medical metrics: {e}")
    
    def _categorize_ed_query(self, query: str) -> str:
        """Categorize emergency department query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['form', 'document', 'paperwork']):
            return 'documentation'
        if any(word in query_lower for word in ['protocol', 'procedure', 'guideline']):
            return 'protocol'
        elif any(word in query_lower for word in ['dosage', 'dose', 'medication']):
            return 'medication'
        elif any(word in query_lower for word in ['criteria', 'indication', 'contraindication']):
            return 'criteria'
        else:
            return 'general'
    
    def _categorize_pharmacy_query(self, query: str) -> str:
        """Categorize pharmacy consultation"""
        query_lower = query.lower()
        # Prioritize allergy over adverse effects when both appear
        if any(word in query_lower for word in ['allergy', 'allergic']):
            return 'allergy'
        if any(word in query_lower for word in ['interaction', 'contraindication']):
            return 'drug_interaction'
        if any(word in query_lower for word in ['dosage', 'dose', 'concentration']):
            return 'dosing'
        if any(word in query_lower for word in ['side effect', 'adverse', 'reaction']):
            return 'adverse_effects'
        else:
            return 'general'
    
    def _get_medication_class(self, query: str) -> str:
        """Determine medication class"""
        query_lower = query.lower()
        
        medication_classes = {
            'antibiotic': ['antibiotic', 'penicillin', 'cephalexin', 'azithromycin'],
            'analgesic': ['pain', 'morphine', 'acetaminophen', 'ibuprofen'],
            'cardiac': ['heart', 'cardiac', 'metoprolol', 'lisinopril', 'digoxin'],
            'anticoagulant': ['blood thinner', 'heparin', 'warfarin', 'aspirin'],
            'respiratory': ['albuterol', 'prednisone', 'inhaler', 'nebulizer']
        }
        
        for med_class, keywords in medication_classes.items():
            if any(keyword in query_lower for keyword in keywords):
                return med_class
                
        return 'other'
    
    def track_safety_event(self, event_type: str, severity: str, details: Dict[str, Any]):
        """Track medical safety events"""
        if not self.enabled:
            return
            
        try:
            # Integrate with main safety metrics (patched in tests)
            safety_alerts.labels(
                alert_type=event_type,
                severity=severity
            ).inc()
            
            # Log detailed safety information
            logger.warning(f"Medical safety event: {event_type} ({severity}) - {details}")
            
        except Exception as e:
            logger.error(f"Error tracking safety event: {e}")
    
    def update_protocol_adherence(self, protocol_name: str, adherence_score: float):
        """Update protocol adherence score"""
        if not self.enabled:
            return
            
        protocol_adherence.labels(protocol_name=protocol_name).set(adherence_score)
    
    def track_clinical_decision_support(self, decision_type: str, confidence: float):
        """Track clinical decision support usage"""
        if not self.enabled:
            return
            
        confidence_level = 'high' if confidence >= 0.8 else 'medium' if confidence >= 0.6 else 'low'
        
        clinical_decision_support.labels(
            decision_type=decision_type,
            confidence_level=confidence_level
        ).inc()


# Global medical metrics collector
medical_metrics = MedicalMetricsCollector()


def init_medical_metrics(settings):
    """Initialize medical metrics with settings"""
    global medical_metrics
    medical_metrics.settings = settings
    medical_metrics.enabled = getattr(settings, 'enable_medical_metrics', True)
