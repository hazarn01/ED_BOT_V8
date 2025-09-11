"""
Medication Search Fix - Targeted fixes for failing medication queries
PRP-48: Fix levophed, epinephrine, and other medication dosing queries
"""

from typing import Dict, List, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

class MedicationSearchFix:
    """Fix medication-specific search failures."""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Medication search mappings - direct filename targeting
        self.medication_files = {
            'levophed': 'Standard IV Infusion - Norepinephrine (Levophed).pdf',
            'norepinephrine': 'Standard IV Infusion - Norepinephrine (Levophed).pdf',
            'epinephrine': 'Anaphylaxis_Guideline_Final_6_6_24.pdf',
            'epi': 'Anaphylaxis_Guideline_Final_6_6_24.pdf',
            'anaphylaxis': 'Anaphylaxis_Guideline_Final_6_6_24.pdf',
            'isoproterenol': 'Standard IV Infusion - Isoproterenol (Isuprel).pdf',
            'isuprel': 'Standard IV Infusion - Isoproterenol (Isuprel).pdf',
            'phenylephrine': 'Standard IV Infusion - Phenylephrine (Neosynephrine).pdf',
            'neosynephrine': 'Standard IV Infusion - Phenylephrine (Neosynephrine).pdf'
        }
        
        # RETU pathway mappings
        self.retu_pathways = {
            'chest pain': 'RETU Chest Pain Pathway.pdf',
            'abdominal pain': 'RETU abdominal pain - vomiting - diarrhea pathway.pdf',
            'afib': 'RETU AFib Pathway final.pdf',
            'alcohol': 'RETU Alcohol Intox Pathway New.pdf',
            'allergic': 'RETU Allergic Reaction Pathway.pdf',
            'asthma': 'RETU Asthma Pathway.pdf',
            'back pain': 'RETU Back Pain Pathway.pdf',
            'cellulitis': 'RETU Cellulitis Pathway.pdf',
            'chf': 'RETU CHF Pathway.pdf',
            'copd': 'RETU COPD Pathway.pdf',
            'dvt': 'RETU DVT Pathway.pdf',
            'headache': 'RETU Headache Pathway.pdf',
            'hyperglycemia': 'RETU Hyperglycemia Pathway.pdf',
            'hypoglycemia': 'RETU Hypoglycemia Pathway.pdf',
            'pneumonia': 'RETU Pneumonia Pathway.pdf',
            'seizure': 'RETU Seizure Pathway.pdf',
            'stroke': 'RETU Stroke Activation.pdf',
            'syncope': 'RETU Syncope Pathway.pdf'
        }
    
    def should_use_medication_fix(self, query: str) -> bool:
        """Check if this query needs medication-specific handling."""
        query_lower = query.lower()
        
        # Check for medication names
        medication_keywords = list(self.medication_files.keys())
        if any(med in query_lower for med in medication_keywords):
            return True
            
        # Check for RETU keywords
        if 'retu' in query_lower:
            return True
            
        # Check for dosing keywords + common medications
        if any(word in query_lower for word in ['dose', 'dosing', 'dosage']):
            return True
            
        return False
    
    def get_targeted_medication_response(self, query: str) -> Optional[Dict[str, Any]]:
        """Get response using targeted medication search."""
        query_lower = query.lower()
        
        # Find the most relevant medication file
        target_file = None
        matched_medication = None
        
        # Direct medication matching
        for med_name, filename in self.medication_files.items():
            if med_name in query_lower:
                target_file = filename
                matched_medication = med_name
                break
        
        # RETU pathway matching
        if not target_file and 'retu' in query_lower:
            for condition, filename in self.retu_pathways.items():
                if condition in query_lower:
                    target_file = filename
                    matched_medication = f"RETU {condition}"
                    break
        
        if not target_file:
            logger.info(f"No targeted file found for query: {query}")
            return None
        
        # Get content from the specific file
        content = self._get_file_content(target_file)
        if not content:
            logger.warning(f"No content found for file: {target_file}")
            return None
        
        # Format response based on query type
        if 'retu' in query_lower:
            response = self._format_retu_response(content, matched_medication)
        else:
            response = self._format_medication_response(content, matched_medication, query)
        
        return {
            "response": response,
            "sources": [{
                "filename": target_file,
                "display_name": target_file.replace('.pdf', '').replace('_', ' ').title()
            }],
            "confidence": 0.9,
            "query_type": "pathway" if 'retu' in query_lower else "dosage",
            "has_real_content": True,
            "retrieval_method": "targeted_medication_fix"
        }
    
    def _get_file_content(self, filename: str) -> Optional[str]:
        """Get content from a specific file."""
        try:
            query = text("""
                SELECT dc.chunk_text
                FROM documents d
                JOIN document_chunks dc ON d.id = dc.document_id
                WHERE d.filename = :filename
                ORDER BY dc.chunk_index
                LIMIT 3
            """)
            
            results = self.db.execute(query, {"filename": filename}).fetchall()
            
            if results:
                # Combine chunks for comprehensive content
                combined_content = "\n\n".join(result[0] for result in results)
                logger.info(f"Found content for {filename}: {len(combined_content)} chars")
                return combined_content
            else:
                logger.warning(f"No chunks found for {filename}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting content for {filename}: {e}")
            return None
    
    def _format_medication_response(self, content: str, medication: str, query: str) -> str:
        """Format medication dosing response."""
        response = f"💊 **{medication.title()} Dosing Information**\n\n"
        
        # Extract dosing information using common patterns
        import re
        
        # Look for dose amounts
        dose_patterns = [
            r'(\d+\.?\d*)\s*(mg|mcg|g|mL|units?)',
            r'(\d+\.?\d*)\s*(mg|mcg)/kg',
            r'(\d+\.?\d*)-(\d+\.?\d*)\s*(mg|mcg|mL|units?)',
        ]
        
        doses_found = []
        for pattern in dose_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            doses_found.extend(matches)
        
        if doses_found:
            response += "**Key Dosing Information:**\n"
            seen_doses = set()
            for dose in doses_found[:5]:  # Show up to 5 unique doses
                dose_str = ' '.join(str(d) for d in dose if d)
                if dose_str not in seen_doses:
                    response += f"• {dose_str}\n"
                    seen_doses.add(dose_str)
            response += "\n"
        
        # Look for administration routes
        if 'iv' in content.lower() or 'intravenous' in content.lower():
            response += "**Route:** Intravenous (IV)\n\n"
        elif 'im' in content.lower() or 'intramuscular' in content.lower():
            response += "**Route:** Intramuscular (IM)\n\n"
        
        # Add actual content
        response += "**Detailed Information:**\n"
        response += content[:600]  # First 600 chars of actual content
        if len(content) > 600:
            response += "..."
        
        return response
    
    def _format_retu_response(self, content: str, pathway_name: str) -> str:
        """Format RETU pathway response."""
        response = f"🛤️ **{pathway_name.title()} Pathway**\n\n"
        
        # Add RETU-specific information
        if 'criteria' in content.lower():
            response += "**Pathway Criteria:**\n"
            criteria_lines = [line.strip() for line in content.split('\n') if 'criteria' in line.lower()][:3]
            for line in criteria_lines:
                response += f"• {line}\n"
            response += "\n"
        
        # Add actual pathway content
        response += "**Pathway Details:**\n"
        response += content[:700]  # First 700 chars of actual content
        if len(content) > 700:
            response += "..."
        
        return response