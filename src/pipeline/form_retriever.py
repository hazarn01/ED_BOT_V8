"""
Dedicated Form Retrieval System
Maps form queries to actual PDF files and provides download links.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

logger = logging.getLogger(__name__)

class FormRetriever:
    """Dedicated system for retrieving medical forms and documents."""
    
    def __init__(self, docs_path: str = None):
        self.docs_path = docs_path or self._find_docs_path()
        
        # Form mapping - maps query terms to actual PDF files
        self.form_mappings = {
            # Blood transfusion forms
            'blood transfusion': [
                'MSHS_Consent_for_Elective_Blood_Transfusion.pdf',
                'TransfusionConsentFormSpanish.pdf',
                'RETU Transfusion Pathway.pdf',
                'EMS blood transfusion during transport Nursing Practice Alert v17.pdf'
            ],
            'transfusion': [
                'MSHS_Consent_for_Elective_Blood_Transfusion.pdf',
                'RETU Transfusion Pathway.pdf',
                'Pediatric Massive Transfusion Protocol.pdf'
            ],
            'blood consent': [
                'MSHS_Consent_for_Elective_Blood_Transfusion.pdf',
                'TransfusionConsentFormSpanish.pdf'
            ],
            
            # Consent forms
            'consent': [
                'MSHS_Consent_for_Elective_Blood_Transfusion.pdf',
                'CT_Consent_SMARTEM.pdf',
                'MSH ED TRANSFER WITHIN MOUNT SINAI HEALTH SYSTEM CHECKLIST AND CONSENT FORM-- 2020.pdf',
                'TransfusionConsentFormSpanish.pdf'
            ],
            
            # Transfer forms
            'transfer': [
                'MSH ED TRANSFER WITHIN MOUNT SINAI HEALTH SYSTEM CHECKLIST AND CONSENT FORM-- 2020.pdf'
            ],
            
            # Autopsy forms
            'autopsy': [
                'AUTOPSY CONSENT FORM 2-2-16.pdf'
            ],
            
            # E-consent
            'e-consent': [
                'E-Consent Tip Sheet.pdf'
            ],
            
            # Blood culture
            'blood culture': [
                'MSH_MSQ ED Blood Culture Policy.pdf'
            ]
        }
        
        # Form query patterns that should trigger form retrieval
        self.form_query_patterns = [
            r'show me.*form',
            r'.*form.*',
            r'.*consent.*',
            r'.*document.*',
            r'i need.*form',
            r'where.*form',
            r'get.*form'
        ]
    
    def _find_docs_path(self) -> str:
        """Find docs directory in the project."""
        current_dir = Path(__file__).parent
        for _ in range(5):
            docs_dir = current_dir / "docs"
            if docs_dir.exists():
                return str(docs_dir)
            current_dir = current_dir.parent
        return "/Users/nimayh/Desktop/NH/V8/edbot-v8-fix-prp-44-comprehensive-code-quality/docs"
    
    def is_form_query(self, query: str) -> bool:
        """Determine if query is asking for a form."""
        query_lower = query.lower()
        
        # Check for form indicators
        form_indicators = ['form', 'consent', 'document', 'show me', 'i need', 'paperwork']
        has_form_indicator = any(indicator in query_lower for indicator in form_indicators)
        
        # Check for form patterns
        has_form_pattern = any(re.search(pattern, query_lower) for pattern in self.form_query_patterns)
        
        return has_form_indicator or has_form_pattern
    
    def get_form_response(self, query: str) -> Optional[Dict[str, Any]]:
        """Get form response with actual PDF links."""
        if not self.is_form_query(query):
            return None
        
        query_lower = query.lower()
        
        # Find matching forms
        matched_forms = []
        for form_term, form_files in self.form_mappings.items():
            if form_term in query_lower:
                matched_forms.extend(form_files)
        
        # If no specific match, try general form detection
        if not matched_forms:
            matched_forms = self._find_forms_by_keywords(query_lower)
        
        if not matched_forms:
            return self._get_generic_form_response()
        
        # Remove duplicates while preserving order
        unique_forms = []
        seen = set()
        for form in matched_forms:
            if form not in seen:
                unique_forms.append(form)
                seen.add(form)
        
        # Verify forms exist
        existing_forms = []
        for form in unique_forms:
            form_path = os.path.join(self.docs_path, form)
            if os.path.exists(form_path):
                existing_forms.append(form)
            else:
                logger.warning(f"Form not found: {form_path}")
        
        if not existing_forms:
            return self._get_form_not_found_response(query)
        
        # Format response
        response = self._format_form_response(query_lower, existing_forms)
        
        # Create sources with PDF links
        sources = []
        for form in existing_forms[:5]:  # Limit to top 5 forms
            display_name = self._format_display_name(form)
            sources.append({
                'display_name': display_name,
                'filename': form,
                'pdf_path': form
            })
        
        return {
            'response': response,
            'sources': sources,
            'confidence': 0.95,  # High confidence for form retrieval
            'query_type': 'form',
            'has_real_content': True,
            'form_retrieval': True,
            'pdf_links': [form for form in existing_forms]
        }
    
    def _find_forms_by_keywords(self, query: str) -> List[str]:
        """Find forms based on keywords in the query."""
        all_forms = []
        
        # Get all PDF files from docs directory
        try:
            for file in os.listdir(self.docs_path):
                if file.lower().endswith('.pdf'):
                    # Check if any query words match the filename
                    query_words = query.split()
                    file_lower = file.lower()
                    
                    for word in query_words:
                        if len(word) > 3 and word in file_lower:  # Avoid short words
                            all_forms.append(file)
                            break
        except Exception as e:
            logger.error(f"Error scanning docs directory: {e}")
        
        return all_forms
    
    def _format_form_response(self, query: str, forms: List[str]) -> str:
        """Format the form response with proper medical context."""
        
        if 'blood' in query or 'transfusion' in query:
            header = "🩸 **Blood Transfusion Forms**\n\n"
        elif 'consent' in query:
            header = "📝 **Consent Forms**\n\n"
        elif 'transfer' in query:
            header = "🚑 **Transfer Forms**\n\n"
        else:
            header = "📄 **Medical Forms**\n\n"
        
        if len(forms) == 1:
            primary_form = forms[0]
            display_name = self._format_display_name(primary_form)
            response = f"{header}**Form Available:**\n• {display_name}\n\n"
            response += f"📋 **File:** {primary_form}\n"
            response += f"💾 **Download:** Available via PDF download link"
        else:
            response = f"{header}**Available Forms:**\n"
            for i, form in enumerate(forms[:5], 1):  # Limit to 5 forms
                display_name = self._format_display_name(form)
                response += f"{i}. {display_name}\n"
            
            response += f"\n📋 **Total:** {len(forms)} form(s) found\n"
            response += f"💾 **Download:** All forms available via PDF download links"
        
        return response
    
    def _format_display_name(self, filename: str) -> str:
        """Format filename to display name."""
        # Remove .pdf extension
        name = filename.replace('.pdf', '')
        
        # Handle special cases
        if 'MSHS_Consent_for_Elective_Blood_Transfusion' in name:
            return "MSHS Blood Transfusion Consent Form"
        elif 'TransfusionConsentFormSpanish' in name:
            return "Blood Transfusion Consent Form (Spanish)"
        elif 'RETU Transfusion Pathway' in name:
            return "RETU Transfusion Pathway"
        elif 'CT_Consent_SMARTEM' in name:
            return "CT Consent Form (SMARTEM)"
        elif 'AUTOPSY CONSENT FORM' in name:
            return "Autopsy Consent Form"
        else:
            # Generic formatting: replace underscores and title case
            return name.replace('_', ' ').replace('-', ' ').title()
    
    def _get_generic_form_response(self) -> Dict[str, Any]:
        """Generic response when no specific forms found."""
        response = """📄 **Medical Forms Directory**

Common ED forms are available including:
• Blood transfusion consent forms
• Transfer documentation
• Procedure consent forms
• Patient assessment forms

Please specify which form you need for direct access."""
        
        return {
            'response': response,
            'sources': [{'display_name': 'Forms Directory', 'filename': 'forms_directory.md'}],
            'confidence': 0.6,
            'query_type': 'form',
            'has_real_content': True,
            'form_retrieval': True
        }
    
    def _get_form_not_found_response(self, query: str) -> Dict[str, Any]:
        """Response when requested forms are not found."""
        response = f"""📄 **Form Search Results**

No forms found matching your request: "{query}"

Available form categories:
• Blood transfusion and consent forms
• Transfer and admission forms  
• Procedure and treatment consent forms

Please try a different search term or contact the forms administrator."""
        
        return {
            'response': response,
            'sources': [],
            'confidence': 0.3,
            'query_type': 'form',
            'has_real_content': False,
            'form_retrieval': True,
            'form_not_found': True
        }


# Convenience function for easy integration
def get_form_response(query: str) -> Optional[Dict[str, Any]]:
    """Get form response for any query."""
    retriever = FormRetriever()
    return retriever.get_form_response(query)