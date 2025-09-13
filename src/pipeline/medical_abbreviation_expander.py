"""
Bulletproof Medical Abbreviation Expansion System
Fixes critical RAG retrieval failures by mapping medical abbreviations to full terms.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set
import re

logger = logging.getLogger(__name__)

class MedicalAbbreviationExpander:
    """Bulletproof medical abbreviation expansion for accurate RAG retrieval."""
    
    def __init__(self, abbreviations_file: str = None):
        """Initialize with comprehensive medical abbreviations database."""
        self.abbreviations_file = abbreviations_file or self._find_abbreviations_file()
        self.abbreviation_map = self._load_medical_abbreviations()
        self._build_expansion_patterns()
        
        logger.info(f"✅ Loaded {len(self.abbreviation_map)} medical abbreviations for RAG expansion")
    
    def _find_abbreviations_file(self) -> str:
        """Find medical abbreviations JSON file."""
        possible_paths = [
            "medical_abbreviations.json",
            "./medical_abbreviations.json", 
            "../medical_abbreviations.json",
            "../../medical_abbreviations.json"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        logger.warning("Medical abbreviations file not found, using built-in definitions")
        return None
    
    def _load_medical_abbreviations(self) -> Dict[str, List[str]]:
        """Load comprehensive medical abbreviations with expansions."""
        
        # Built-in critical medical abbreviations that MUST work
        critical_abbreviations = {
            # Critical Protocols
            'DKA': ['Diabetic Ketoacidosis', 'diabetic ketoacidosis', 'diabetes ketoacidosis'],
            'STEMI': ['ST-Elevation Myocardial Infarction', 'ST elevation myocardial infarction', 'STEMI protocol'],
            'NSTEMI': ['Non-ST-Elevation Myocardial Infarction', 'non-ST elevation myocardial infarction'],
            'MI': ['Myocardial Infarction', 'myocardial infarction', 'heart attack'],
            'AMI': ['Acute Myocardial Infarction', 'acute myocardial infarction'],
            'CHF': ['Congestive Heart Failure', 'congestive heart failure', 'heart failure'],
            'COPD': ['Chronic Obstructive Pulmonary Disease', 'chronic obstructive pulmonary disease'],
            'PE': ['Pulmonary Embolism', 'pulmonary embolism'],
            'DVT': ['Deep Vein Thrombosis', 'deep vein thrombosis'],
            'CVA': ['Cerebrovascular Accident', 'cerebrovascular accident', 'stroke'],
            'TIA': ['Transient Ischemic Attack', 'transient ischemic attack'],
            'GI': ['Gastrointestinal', 'gastrointestinal'],
            'UTI': ['Urinary Tract Infection', 'urinary tract infection'],
            'SOB': ['Shortness of Breath', 'shortness of breath', 'dyspnea'],
            'CP': ['Chest Pain', 'chest pain'],
            'N/V': ['Nausea and Vomiting', 'nausea vomiting', 'nausea and vomiting'],
            
            # Emergency Medications & Procedures  
            'ASA': ['Aspirin', 'aspirin', 'acetylsalicylic acid'],
            'IV': ['Intravenous', 'intravenous'],
            'IM': ['Intramuscular', 'intramuscular'], 
            'SQ': ['Subcutaneous', 'subcutaneous'],
            'PO': ['Per Os', 'by mouth', 'oral', 'orally'],
            'NPO': ['Nothing by Mouth', 'nothing by mouth'],
            'CPR': ['Cardiopulmonary Resuscitation', 'cardiopulmonary resuscitation'],
            'ACLS': ['Advanced Cardiac Life Support', 'advanced cardiac life support'],
            'BLS': ['Basic Life Support', 'basic life support'],
            'AED': ['Automated External Defibrillator', 'automated external defibrillator'],
            
            # Vital Signs & Measurements
            'BP': ['Blood Pressure', 'blood pressure'],
            'HR': ['Heart Rate', 'heart rate'],
            'RR': ['Respiratory Rate', 'respiratory rate'],
            'O2': ['Oxygen', 'oxygen'],
            'SpO2': ['Oxygen Saturation', 'oxygen saturation'],
            'EKG': ['Electrocardiogram', 'electrocardiogram', 'ECG'],
            'ECG': ['Electrocardiogram', 'electrocardiogram', 'EKG'],
            'CXR': ['Chest X-Ray', 'chest x-ray', 'chest radiograph'],
            'CT': ['Computed Tomography', 'computed tomography', 'CAT scan'],
            'MRI': ['Magnetic Resonance Imaging', 'magnetic resonance imaging'],
            
            # Laboratory Values
            'CBC': ['Complete Blood Count', 'complete blood count'],
            'BMP': ['Basic Metabolic Panel', 'basic metabolic panel'],
            'CMP': ['Comprehensive Metabolic Panel', 'comprehensive metabolic panel'],
            'ABG': ['Arterial Blood Gas', 'arterial blood gas'],
            'VBG': ['Venous Blood Gas', 'venous blood gas'],
            'BNP': ['B-Type Natriuretic Peptide', 'brain natriuretic peptide'],
            'D-dimer': ['D-dimer', 'D dimer'],
            'PT/INR': ['Prothrombin Time/International Normalized Ratio', 'prothrombin time', 'INR'],
            'PTT': ['Partial Thromboplastin Time', 'partial thromboplastin time'],
            
            # Department/Location Abbreviations
            'ED': ['Emergency Department', 'emergency department', 'emergency room', 'ER'],
            'ER': ['Emergency Room', 'emergency room', 'emergency department', 'ED'],
            'ICU': ['Intensive Care Unit', 'intensive care unit'],
            'CCU': ['Cardiac Care Unit', 'cardiac care unit'],
            'MICU': ['Medical Intensive Care Unit', 'medical intensive care unit'],
            'SICU': ['Surgical Intensive Care Unit', 'surgical intensive care unit'],
            'OR': ['Operating Room', 'operating room'],
            'PACU': ['Post-Anesthesia Care Unit', 'post-anesthesia care unit'],
            'L&D': ['Labor and Delivery', 'labor and delivery', 'obstetrics'],
            'NICU': ['Neonatal Intensive Care Unit', 'neonatal intensive care unit'],
            'PICU': ['Pediatric Intensive Care Unit', 'pediatric intensive care unit'],
            
            # Specialty Abbreviations
            'OB/GYN': ['Obstetrics and Gynecology', 'obstetrics gynecology'],
            'ENT': ['Ear Nose Throat', 'ear nose throat', 'otolaryngology'],
            'GU': ['Genitourinary', 'genitourinary'],
            'ORTHO': ['Orthopedics', 'orthopedics', 'orthopedic'],
            'NEURO': ['Neurology', 'neurology', 'neurological'],
            'PSYCH': ['Psychiatry', 'psychiatry', 'psychiatric'],
            'DERM': ['Dermatology', 'dermatology'],
            
            # RETU Specific
            'RETU': ['Return to Emergency Department', 'return emergency', 'readmission'],
            
            # Technology/Systems
            'PACS': ['Picture Archiving Communication System', 'picture archiving', 'medical imaging'],
            'EMR': ['Electronic Medical Record', 'electronic medical record'],
            'EHR': ['Electronic Health Record', 'electronic health record']
        }
        
        # Try to load from file and merge with critical abbreviations
        if self.abbreviations_file:
            try:
                with open(self.abbreviations_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                
                # Convert abbreviation list to expansion map
                if 'abbreviations' in file_data:
                    for abbrev in file_data['abbreviations']:
                        if abbrev not in critical_abbreviations:
                            # Add basic expansion for unknown abbreviations
                            critical_abbreviations[abbrev] = [abbrev.lower()]
                
                logger.info(f"✅ Loaded {len(file_data.get('abbreviations', []))} abbreviations from file")
                            
            except Exception as e:
                logger.error(f"Failed to load abbreviations file: {e}")
        
        return critical_abbreviations
    
    def _build_expansion_patterns(self):
        """Build regex patterns for efficient abbreviation detection."""
        self.abbreviation_patterns = {}
        
        # Create word boundary patterns for each abbreviation
        for abbrev in self.abbreviation_map.keys():
            # Match whole words only, case-insensitive
            pattern = re.compile(rf'\b{re.escape(abbrev)}\b', re.IGNORECASE)
            self.abbreviation_patterns[abbrev] = pattern
    
    def expand_query(self, query: str) -> Dict[str, any]:
        """
        Expand medical abbreviations in query for better RAG retrieval.
        
        Returns:
            {
                'original_query': str,
                'expanded_query': str, 
                'expansions': List[str],
                'detected_abbreviations': List[str]
            }
        """
        original_query = query
        expanded_terms = []
        detected_abbreviations = []
        expanded_query = query
        
        # Find all abbreviations in the query
        for abbrev, expansions in self.abbreviation_map.items():
            pattern = self.abbreviation_patterns.get(abbrev)
            if pattern and pattern.search(query):
                detected_abbreviations.append(abbrev)
                expanded_terms.extend(expansions)
                
                # Replace abbreviation with primary expansion in query
                primary_expansion = expansions[0]
                expanded_query = pattern.sub(primary_expansion, expanded_query)
        
        # Create comprehensive search terms
        all_search_terms = [original_query, expanded_query] + expanded_terms
        # Remove duplicates while preserving order
        unique_terms = []
        seen = set()
        for term in all_search_terms:
            if term.lower() not in seen:
                unique_terms.append(term)
                seen.add(term.lower())
        
        result = {
            'original_query': original_query,
            'expanded_query': expanded_query,
            'expansions': unique_terms[2:],  # All additional terms
            'detected_abbreviations': detected_abbreviations,
            'all_search_terms': unique_terms
        }
        
        if detected_abbreviations:
            logger.info(f"🔍 Expanded abbreviations in '{query}': {detected_abbreviations} → {expansions[:3]}...")
        
        return result
    
    def get_critical_medical_terms(self) -> Set[str]:
        """Get set of all critical medical terms for query classification."""
        critical_terms = set()
        
        for abbrev, expansions in self.abbreviation_map.items():
            critical_terms.add(abbrev.lower())
            for expansion in expansions:
                critical_terms.update(expansion.lower().split())
        
        return critical_terms
    
    def is_medical_query(self, query: str) -> bool:
        """Determine if query contains medical terminology."""
        query_lower = query.lower()
        critical_terms = self.get_critical_medical_terms()
        
        # Check for any medical abbreviation
        for abbrev in self.abbreviation_map:
            if abbrev.lower() in query_lower:
                return True
        
        # Check for medical terms
        query_words = set(query_lower.split())
        return bool(query_words.intersection(critical_terms))


# Global expander instance
_medical_expander = None

def get_medical_expander() -> MedicalAbbreviationExpander:
    """Get singleton medical abbreviation expander."""
    global _medical_expander
    if _medical_expander is None:
        _medical_expander = MedicalAbbreviationExpander()
    return _medical_expander