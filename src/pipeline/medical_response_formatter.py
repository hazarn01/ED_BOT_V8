"""
Medical Response Templates for PRP-41: Universal Curated-Quality Response System
Dynamic templates that generate curated-style medical responses with professional formatting.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from jinja2 import BaseLoader, Environment

from src.models.query_types import QueryType

from .enhanced_medical_retriever import MedicalContext

logger = logging.getLogger(__name__)


@dataclass
class FormattedResponse:
    """Formatted medical response with metadata."""
    content: str
    formatting_confidence: float
    template_used: str
    medical_sections: List[str]
    emoji_count: int
    citation_quality: str


class MedicalTemplateLoader(BaseLoader):
    """Custom template loader for medical response templates."""
    
    def __init__(self, templates: Dict[str, str]):
        self.templates = templates
    
    def get_source(self, environment: Environment, template: str):
        if template in self.templates:
            source = self.templates[template]
            return source, None, lambda: True
        raise FileNotFoundError(f"Template {template} not found")


class MedicalResponseFormatter:
    """
    Dynamic medical response formatter that generates curated-quality responses
    using professional medical templates with emojis and structured formatting.
    """
    
    def __init__(self):
        self.templates = self._load_medical_templates()
        self.jinja_env = Environment(loader=MedicalTemplateLoader(self.templates))
        self.medical_emojis = self._load_medical_emoji_map()
        
    def format_response(
        self, 
        context: MedicalContext, 
        query_type: QueryType,
        raw_response: str = "",
        query: str = ""
    ) -> FormattedResponse:
        """
        Format response using medical templates to match curated quality.
        
        Args:
            context: Enhanced medical context from retriever
            query_type: Type of medical query
            raw_response: Raw LLM response (optional)
            query: Original query (optional)
            
        Returns:
            Professionally formatted medical response
        """
        try:
            # Select appropriate template
            template_name = self._select_template(query_type, context)
            template = self.jinja_env.get_template(template_name)
            
            # Prepare template variables
            template_vars = self._prepare_template_variables(
                context, query_type, raw_response, query
            )
            
            # Render response with medical formatting
            formatted_content = template.render(**template_vars)
            
            # Post-process for medical formatting consistency
            final_content = self._post_process_medical_formatting(
                formatted_content, query_type, context
            )
            
            # Calculate formatting metrics
            formatting_confidence = self._calculate_formatting_confidence(
                final_content, context, query_type
            )
            
            medical_sections = self._extract_medical_sections(final_content)
            emoji_count = self._count_medical_emojis(final_content)
            citation_quality = self._assess_citation_quality(final_content, context)
            
            return FormattedResponse(
                content=final_content,
                formatting_confidence=formatting_confidence,
                template_used=template_name,
                medical_sections=medical_sections,
                emoji_count=emoji_count,
                citation_quality=citation_quality
            )
            
        except Exception as e:
            logger.error(f"Medical response formatting failed: {e}")
            
            # Fallback to basic formatting
            return self._fallback_formatting(context, raw_response, query_type)
    
    def _load_medical_templates(self) -> Dict[str, str]:
        """Load medical response templates for each query type."""
        return {
            "protocol_template": """🚨 **{{ protocol_name }}**

{% if timing_requirements %}
⏱️ **Time Critical:**
{% for timing in timing_requirements %}
• {{ timing }}
{% endfor %}
{% endif %}

{% if critical_contacts %}
📞 **Critical Contacts:**
{% for contact in critical_contacts %}
• {{ contact }}
{% endfor %}
{% endif %}

{% if clinical_actions %}
💉 **{{ action_header }}:**
{% for action in clinical_actions %}
• {{ action }}
{% endfor %}
{% endif %}

{% if medications %}
💊 **Medications:**
{% for medication in medications %}
• {{ medication }}
{% endfor %}
{% endif %}

{% if workflow_steps %}
🔄 **Workflow:**
{% for step in workflow_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
{% endif %}

{% if warnings %}
⚠️ **Critical Notes:**
{% for warning in warnings %}
• {{ warning }}
{% endfor %}
{% endif %}

{% if sources %}
📚 **Sources:** {% for source in sources %}{{ source.display_name }}{% if not loop.last %}, {% endif %}{% endfor %}
{% endif %}""",

            "dosage_template": """💉 **{{ medication_name }}**

{% if adult_dose %}
**Adult Dose:**
{% for dose in adult_dose %}
• {{ dose }}
{% endfor %}
{% endif %}

{% if pediatric_dose %}
**Pediatric Dose:**
{% for dose in pediatric_dose %}
• {{ dose }}
{% endfor %}
{% endif %}

{% if preparation %}
🧪 **Preparation:**
{% for prep in preparation %}
• {{ prep }}
{% endfor %}
{% endif %}

{% if administration %}
💉 **Administration:**
{% for admin in administration %}
• {{ admin }}
{% endfor %}
{% endif %}

{% if timing %}
⏱️ **Timing:**
{% for time in timing %}
• {{ time }}
{% endfor %}
{% endif %}

{% if contraindications %}
🚫 **Contraindications:**
{% for contra in contraindications %}
• {{ contra }}
{% endfor %}
{% endif %}

{% if warnings %}
⚠️ **Critical Warnings:**
{% for warning in warnings %}
• {{ warning }}
{% endfor %}
{% endif %}

{% if sources %}
📚 **Sources:** {% for source in sources %}{{ source.display_name }}{% if not loop.last %}, {% endif %}{% endfor %}
{% endif %}""",

            "criteria_template": """📋 **{{ criteria_name }}**

{% if definition %}
**Definition:**
{{ definition }}
{% endif %}

{% if scoring %}
📊 **Scoring/Thresholds:**
{% for score in scoring %}
• {{ score }}
{% endfor %}
{% endif %}

{% if criteria_list %}
**Criteria:**
{% for criterion in criteria_list %}
• {{ criterion }}
{% endfor %}
{% endif %}

{% if indications %}
✅ **Indications:**
{% for indication in indications %}
• {{ indication }}
{% endfor %}
{% endif %}

{% if contraindications %}
❌ **Contraindications:**
{% for contra in contraindications %}
• {{ contra }}
{% endfor %}
{% endif %}

{% if clinical_pearls %}
💡 **Clinical Pearls:**
{% for pearl in clinical_pearls %}
• {{ pearl }}
{% endfor %}
{% endif %}

{% if sources %}
📚 **Sources:** {% for source in sources %}{{ source.display_name }}{% if not loop.last %}, {% endif %}{% endfor %}
{% endif %}""",

            "contact_template": """📞 **{{ contact_header }}**

{% if primary_contacts %}
**Primary Contacts:**
{% for contact in primary_contacts %}
• {{ contact }}
{% endfor %}
{% endif %}

{% if backup_contacts %}
**Backup/Alternative:**
{% for contact in backup_contacts %}
• {{ contact }}
{% endfor %}
{% endif %}

{% if emergency_contacts %}
🚨 **Emergency Escalation:**
{% for contact in emergency_contacts %}
• {{ contact }}
{% endfor %}
{% endif %}

{% if contact_notes %}
📋 **Notes:**
{% for note in contact_notes %}
• {{ note }}
{% endfor %}
{% endif %}

{% if availability %}
🕒 **Availability:**
{{ availability }}
{% endif %}

{% if sources %}
📚 **Sources:** {% for source in sources %}{{ source.display_name }}{% if not loop.last %}, {% endif %}{% endfor %}
{% endif %}""",

            "form_template": """📄 **{{ form_header }}**

{% if available_forms %}
**Available Forms:**
{% for form in available_forms %}
• {{ form }}
{% endfor %}
{% endif %}

{% if download_instructions %}
💾 **Download Instructions:**
{% for instruction in download_instructions %}
• {{ instruction }}
{% endfor %}
{% endif %}

{% if form_notes %}
📋 **Usage Notes:**
{% for note in form_notes %}
• {{ note }}
{% endfor %}
{% endif %}

{% if sources %}
📚 **Sources:** {% for source in sources %}{{ source.display_name }}{% if not loop.last %}, {% endif %}{% endfor %}
{% endif %}""",

            "summary_template": """📊 **{{ summary_header }}**

{% if overview %}
**Overview:**
{{ overview }}
{% endif %}

{% if key_points %}
🔑 **Key Points:**
{% for point in key_points %}
• {{ point }}
{% endfor %}
{% endif %}

{% if clinical_approach %}
⚕️ **Clinical Approach:**
{% for approach in clinical_approach %}
• {{ approach }}
{% endfor %}
{% endif %}

{% if management %}
💉 **Management:**
{% for mgmt in management %}
• {{ mgmt }}
{% endfor %}
{% endif %}

{% if monitoring %}
📈 **Monitoring/Follow-up:**
{% for monitor in monitoring %}
• {{ monitor }}
{% endfor %}
{% endif %}

{% if complications %}
⚠️ **Complications to Watch:**
{% for comp in complications %}
• {{ comp }}
{% endfor %}
{% endif %}

{% if sources %}
📚 **Sources:** {% for source in sources %}{{ source.display_name }}{% if not loop.last %}, {% endif %}{% endfor %}
{% endif %}"""
        }
    
    def _select_template(self, query_type: QueryType, context: MedicalContext) -> str:
        """Select appropriate template based on query type and context."""
        template_map = {
            QueryType.PROTOCOL_STEPS: "protocol_template",
            QueryType.DOSAGE_LOOKUP: "dosage_template", 
            QueryType.CRITERIA_CHECK: "criteria_template",
            QueryType.CONTACT_LOOKUP: "contact_template",
            QueryType.FORM_RETRIEVAL: "form_template",
            QueryType.SUMMARY_REQUEST: "summary_template"
        }
        
        return template_map.get(query_type, "summary_template")
    
    def _prepare_template_variables(
        self, 
        context: MedicalContext, 
        query_type: QueryType,
        raw_response: str,
        query: str
    ) -> Dict[str, Any]:
        """Prepare variables for template rendering based on query type."""
        
        # Extract base variables
        base_vars = {
            "sources": context.source_citations,
            "confidence_level": context.medical_certainty_level,
            "clinical_relevance": context.clinical_relevance_score
        }
        
        # Query-type-specific variable preparation
        if query_type == QueryType.PROTOCOL_STEPS:
            return {**base_vars, **self._prepare_protocol_variables(context, raw_response, query)}
        elif query_type == QueryType.DOSAGE_LOOKUP:
            return {**base_vars, **self._prepare_dosage_variables(context, raw_response, query)}
        elif query_type == QueryType.CRITERIA_CHECK:
            return {**base_vars, **self._prepare_criteria_variables(context, raw_response, query)}
        elif query_type == QueryType.CONTACT_LOOKUP:
            return {**base_vars, **self._prepare_contact_variables(context, raw_response, query)}
        elif query_type == QueryType.FORM_RETRIEVAL:
            return {**base_vars, **self._prepare_form_variables(context, raw_response, query)}
        else:  # SUMMARY_REQUEST
            return {**base_vars, **self._prepare_summary_variables(context, raw_response, query)}
    
    def _prepare_protocol_variables(
        self, 
        context: MedicalContext, 
        raw_response: str, 
        query: str
    ) -> Dict[str, Any]:
        """Prepare variables for protocol template."""
        context.primary_content.lower()
        
        # Extract protocol name
        protocol_name = self._extract_protocol_name(query, context.primary_content)
        
        # Extract timing requirements
        timing_requirements = self._extract_timing_info(context.primary_content)
        
        # Extract contacts
        critical_contacts = self._extract_contacts(context.primary_content)
        
        # Extract clinical actions
        clinical_actions = self._extract_clinical_actions(context.primary_content)
        
        # Extract medications
        medications = self._extract_medications(context.primary_content)
        
        # Extract workflow steps
        workflow_steps = self._extract_workflow_steps(context.primary_content)
        
        # Extract warnings
        warnings = self._extract_warnings(context.primary_content)
        
        return {
            "protocol_name": protocol_name,
            "timing_requirements": timing_requirements,
            "critical_contacts": critical_contacts,
            "clinical_actions": clinical_actions,
            "medications": medications,
            "workflow_steps": workflow_steps,
            "warnings": warnings,
            "action_header": self._get_action_header(protocol_name)
        }
    
    def _prepare_dosage_variables(
        self, 
        context: MedicalContext, 
        raw_response: str, 
        query: str
    ) -> Dict[str, Any]:
        """Prepare variables for dosage template."""
        # Extract medication name
        medication_name = self._extract_medication_name(query, context.primary_content)
        
        # Extract adult dosing
        adult_dose = self._extract_adult_dosing(context.primary_content)
        
        # Extract pediatric dosing
        pediatric_dose = self._extract_pediatric_dosing(context.primary_content)
        
        # Extract preparation info
        preparation = self._extract_preparation_info(context.primary_content)
        
        # Extract administration details
        administration = self._extract_administration_details(context.primary_content)
        
        # Extract timing
        timing = self._extract_dosing_timing(context.primary_content)
        
        # Extract contraindications
        contraindications = self._extract_contraindications(context.primary_content)
        
        # Extract warnings
        warnings = self._extract_drug_warnings(context.primary_content)
        
        return {
            "medication_name": medication_name,
            "adult_dose": adult_dose,
            "pediatric_dose": pediatric_dose,
            "preparation": preparation,
            "administration": administration,
            "timing": timing,
            "contraindications": contraindications,
            "warnings": warnings
        }
    
    def _prepare_criteria_variables(
        self, 
        context: MedicalContext, 
        raw_response: str, 
        query: str
    ) -> Dict[str, Any]:
        """Prepare variables for criteria template."""
        # Extract criteria name
        criteria_name = self._extract_criteria_name(query, context.primary_content)
        
        # Extract definition
        definition = self._extract_definition(context.primary_content)
        
        # Extract scoring/thresholds
        scoring = self._extract_scoring_thresholds(context.primary_content)
        
        # Extract criteria list
        criteria_list = self._extract_criteria_list(context.primary_content)
        
        # Extract indications
        indications = self._extract_indications(context.primary_content)
        
        # Extract contraindications
        contraindications = self._extract_contraindications(context.primary_content)
        
        # Extract clinical pearls
        clinical_pearls = self._extract_clinical_pearls(context.primary_content)
        
        return {
            "criteria_name": criteria_name,
            "definition": definition,
            "scoring": scoring,
            "criteria_list": criteria_list,
            "indications": indications,
            "contraindications": contraindications,
            "clinical_pearls": clinical_pearls
        }
    
    def _prepare_contact_variables(
        self, 
        context: MedicalContext, 
        raw_response: str, 
        query: str
    ) -> Dict[str, Any]:
        """Prepare variables for contact template."""
        # Extract contact header
        contact_header = self._extract_contact_header(query)
        
        # Extract primary contacts
        primary_contacts = self._extract_primary_contacts(context.primary_content)
        
        # Extract backup contacts
        backup_contacts = self._extract_backup_contacts(context.primary_content)
        
        # Extract emergency contacts
        emergency_contacts = self._extract_emergency_contacts(context.primary_content)
        
        # Extract contact notes
        contact_notes = self._extract_contact_notes(context.primary_content)
        
        # Extract availability info
        availability = self._extract_availability(context.primary_content)
        
        return {
            "contact_header": contact_header,
            "primary_contacts": primary_contacts,
            "backup_contacts": backup_contacts,
            "emergency_contacts": emergency_contacts,
            "contact_notes": contact_notes,
            "availability": availability
        }
    
    def _prepare_form_variables(
        self, 
        context: MedicalContext, 
        raw_response: str, 
        query: str
    ) -> Dict[str, Any]:
        """Prepare variables for form template."""
        # Extract form header
        form_header = self._extract_form_header(query)
        
        # Extract available forms
        available_forms = self._extract_available_forms(context.primary_content, raw_response)
        
        # Extract download instructions
        download_instructions = self._extract_download_instructions(raw_response)
        
        # Extract form notes
        form_notes = self._extract_form_notes(context.primary_content)
        
        return {
            "form_header": form_header,
            "available_forms": available_forms,
            "download_instructions": download_instructions,
            "form_notes": form_notes
        }
    
    def _prepare_summary_variables(
        self, 
        context: MedicalContext, 
        raw_response: str, 
        query: str
    ) -> Dict[str, Any]:
        """Prepare variables for summary template."""
        # Extract summary header
        summary_header = self._extract_summary_header(query)
        
        # Extract overview
        overview = self._extract_overview(context.primary_content, raw_response)
        
        # Extract key points
        key_points = self._extract_key_points(context.primary_content)
        
        # Extract clinical approach
        clinical_approach = self._extract_clinical_approach(context.primary_content)
        
        # Extract management
        management = self._extract_management_points(context.primary_content)
        
        # Extract monitoring
        monitoring = self._extract_monitoring_points(context.primary_content)
        
        # Extract complications
        complications = self._extract_complications(context.primary_content)
        
        return {
            "summary_header": summary_header,
            "overview": overview,
            "key_points": key_points,
            "clinical_approach": clinical_approach,
            "management": management,
            "monitoring": monitoring,
            "complications": complications
        }
    
    # Extraction helper methods
    def _extract_protocol_name(self, query: str, content: str) -> str:
        """Extract protocol name from query and content."""
        query_lower = query.lower()
        
        # Common protocol patterns
        if 'stemi' in query_lower:
            return "STEMI Activation Protocol"
        elif 'sepsis' in query_lower:
            return "ED Sepsis Pathway"
        elif 'stroke' in query_lower:
            return "Stroke Protocol"
        elif 'trauma' in query_lower:
            return "Trauma Activation"
        else:
            # Extract from content or use generic
            protocol_match = re.search(r'([A-Z][^.]*?protocol)', content, re.IGNORECASE)
            return protocol_match.group(1) if protocol_match else "Medical Protocol"
    
    def _extract_timing_info(self, content: str) -> List[str]:
        """Extract timing requirements from content."""
        timing = []
        
        # Pattern for timing requirements
        timing_patterns = [
            r'(\d+)\s*minute[s]?',
            r'door.{0,10}balloon.{0,10}(\d+)',
            r'within\s*(\d+)',
            r'goal[:\s]*(\d+)',
            r'<\s*(\d+)\s*minute[s]?'
        ]
        
        for pattern in timing_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                timing.append(f"Goal: {match} minutes")
        
        # Common timing phrases
        timing_phrases = [
            'door-to-balloon',
            'ekg within',
            'activate within',
            'time critical'
        ]
        
        for phrase in timing_phrases:
            if phrase.lower() in content.lower():
                # Find sentence containing the phrase
                sentences = content.split('.')
                for sentence in sentences:
                    if phrase.lower() in sentence.lower():
                        timing.append(sentence.strip())
                        break
        
        return timing[:3]  # Limit to top 3 timing requirements
    
    def _extract_contacts(self, content: str) -> List[str]:
        """Extract contact information from content."""
        contacts = []
        
        # Phone number patterns
        phone_patterns = [
            r'\((\d{3})\)\s*(\d{3})-(\d{4})',
            r'(\d{3})-(\d{3})-(\d{4})',
            r'x(\d{4,5})',
            r'ext[^:]*(\d{4,5})'
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 3 and all(match):  # Full phone number
                        contacts.append(f"Phone: ({match[0]}) {match[1]}-{match[2]}")
                    elif len(match) == 1:  # Extension
                        contacts.append(f"Extension: x{match[0]}")
        
        # Pager patterns
        pager_matches = re.findall(r'pager[^:]*(\d{3}-\d{3}-\d{4})', content, re.IGNORECASE)
        for match in pager_matches:
            contacts.append(f"Pager: {match}")
        
        return contacts[:5]  # Limit to top 5 contacts
    
    def _extract_clinical_actions(self, content: str) -> List[str]:
        """Extract clinical actions from content."""
        actions = []
        
        # Look for bullet points or numbered lists
        bullet_matches = re.findall(r'[•·-]\s*([^•·-\n]+)', content)
        for match in bullet_matches[:5]:
            action = match.strip()
            if len(action) > 10:  # Filter out very short items
                actions.append(action)
        
        # Look for action verbs
        action_patterns = [
            r'(give|administer|obtain|check|monitor|assess|evaluate)[^.]+',
            r'(start|begin|initiate|activate)[^.]+',
            r'(call|contact|notify)[^.]+'
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:3]:
                if isinstance(match, tuple):
                    match = match[0] + match[1] if len(match) > 1 else match[0]
                actions.append(match.strip().capitalize())
        
        return actions[:5]  # Limit to top 5 actions
    
    def _extract_medications(self, content: str) -> List[str]:
        """Extract medications from content."""
        medications = []
        
        # Common medication patterns
        med_patterns = [
            r'([A-Za-z]+)\s*(\d+)\s*(mg|ml|units)',
            r'(ASA|aspirin)\s*(\d+)',
            r'(heparin|epinephrine|atropine)[^.]*'
        ]
        
        for pattern in med_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 3:  # drug dose unit
                        medications.append(f"{match[0]} {match[1]}{match[2]}")
                    else:
                        medications.append(" ".join(match).strip())
                else:
                    medications.append(match)
        
        return medications[:5]  # Limit to top 5 medications
    
    def _extract_workflow_steps(self, content: str) -> List[str]:
        """Extract workflow steps from content."""
        steps = []
        
        # Look for numbered steps
        numbered_steps = re.findall(r'(\d+)[.)]\s*([^.]+)', content)
        for number, step in numbered_steps:
            steps.append(step.strip())
        
        # If no numbered steps, look for sequential actions
        if not steps:
            sequential_patterns = [
                r'(first|second|third|then|next|finally)[^.]+',
                r'step\s*\d*[^.]*'
            ]
            
            for pattern in sequential_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    steps.append(match.strip().capitalize())
        
        return steps[:6]  # Limit to top 6 steps
    
    def _extract_warnings(self, content: str) -> List[str]:
        """Extract warnings and critical notes from content."""
        warnings = []
        
        # Warning keywords
        warning_patterns = [
            r'(never|do not|avoid|contraindication)[^.]+',
            r'(warning|caution|critical|important)[^.]+',
            r'(must|should not|cannot)[^.]+'
        ]
        
        for pattern in warning_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                warning = match.strip().capitalize()
                if len(warning) > 10:
                    warnings.append(warning)
        
        return warnings[:3]  # Limit to top 3 warnings
    
    # Additional extraction methods for other query types...
    def _extract_medication_name(self, query: str, content: str) -> str:
        """Extract medication name from query and content."""
        common_meds = ['epinephrine', 'atropine', 'adenosine', 'amiodarone', 'dopamine', 'norepinephrine']
        
        for med in common_meds:
            if med.lower() in query.lower():
                return med.capitalize()
        
        # Extract from content
        med_match = re.search(r'([A-Za-z]+)\s*dose', content, re.IGNORECASE)
        return med_match.group(1).capitalize() if med_match else "Medication Dosing"
    
    def _extract_adult_dosing(self, content: str) -> List[str]:
        """Extract adult dosing information."""
        dosing = []
        
        adult_patterns = [
            r'adult[^:]*:\s*([^.]+)',
            r'(\d+\s*mg[^.]*)',
            r'(\d+\s*ml[^.]*)',
            r'(\d+\s*units[^.]*)'
        ]
        
        for pattern in adult_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                dosing.append(match.strip())
        
        return dosing[:3]
    
    def _extract_pediatric_dosing(self, content: str) -> List[str]:
        """Extract pediatric dosing information."""
        dosing = []
        
        ped_patterns = [
            r'pediatric[^:]*:\s*([^.]+)',
            r'child[^:]*:\s*([^.]+)',
            r'(\d+[\d.]*\s*mg/kg[^.]*)',
            r'(\d+[\d.]*\s*ml/kg[^.]*)'
        ]
        
        for pattern in ped_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                dosing.append(match.strip())
        
        return dosing[:3]
    
    # Continue with remaining extraction methods...
    def _extract_preparation_info(self, content: str) -> List[str]:
        """Extract preparation information."""
        preparation = []
        
        prep_keywords = ['concentration', 'dilute', 'mix', 'prepare', 'solution']
        for keyword in prep_keywords:
            if keyword.lower() in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        preparation.append(sentence.strip())
                        break
        
        return preparation[:3]
    
    def _post_process_medical_formatting(
        self, 
        content: str, 
        query_type: QueryType, 
        context: MedicalContext
    ) -> str:
        """Post-process content for medical formatting consistency."""
        
        # Ensure proper emoji usage
        content = self._ensure_medical_emojis(content, query_type)
        
        # Format medical abbreviations correctly
        content = self._format_medical_abbreviations(content)
        
        # Ensure proper bolding of headers
        content = self._ensure_header_formatting(content)
        
        # Format phone numbers consistently
        content = self._format_phone_numbers(content)
        
        # Clean up extra whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()
    
    def _ensure_medical_emojis(self, content: str, query_type: QueryType) -> str:
        """Ensure proper medical emoji usage."""
        # If content lacks emojis, add appropriate ones based on context
        if not re.search(r'[🚨💉⏱️📞💊🔄⚠️📚🧪💡📊🦵🦠📋✅❌]', content):
            
            # Add title emoji if missing
            lines = content.split('\n')
            if lines and '**' in lines[0]:
                emoji_map = {
                    QueryType.PROTOCOL_STEPS: '🚨',
                    QueryType.DOSAGE_LOOKUP: '💉',
                    QueryType.CRITERIA_CHECK: '📋',
                    QueryType.CONTACT_LOOKUP: '📞',
                    QueryType.FORM_RETRIEVAL: '📄',
                    QueryType.SUMMARY_REQUEST: '📊'
                }
                
                emoji = emoji_map.get(query_type, '📋')
                lines[0] = f"{emoji} {lines[0]}"
                content = '\n'.join(lines)
        
        return content
    
    def _format_medical_abbreviations(self, content: str) -> str:
        """Format medical abbreviations consistently."""
        abbrevs = {
            'stemi': 'STEMI',
            'mi': 'MI',
            'cva': 'CVA',
            'pe': 'PE',
            'dvt': 'DVT',
            'chf': 'CHF',
            'copd': 'COPD',
            'dka': 'DKA',
            'acls': 'ACLS',
            'bls': 'BLS',
            'iv': 'IV',
            'im': 'IM',
            'ekg': 'EKG',
            'ecg': 'ECG'
        }
        
        for abbrev, correct in abbrevs.items():
            # Replace standalone abbreviations (word boundaries)
            content = re.sub(f'\\b{abbrev}\\b', correct, content, flags=re.IGNORECASE)
        
        return content
    
    def _ensure_header_formatting(self, content: str) -> str:
        """Ensure proper header formatting with bolding."""
        # Find headers that should be bolded
        headers = [
            'Adult Dose', 'Pediatric Dose', 'Preparation', 'Administration',
            'Timing', 'Contraindications', 'Critical Warnings', 'Key Points',
            'Clinical Approach', 'Management', 'Monitoring', 'Definition',
            'Scoring', 'Criteria', 'Indications', 'Clinical Pearls',
            'Primary Contacts', 'Backup', 'Emergency Escalation',
            'Available Forms', 'Usage Notes', 'Overview'
        ]
        
        for header in headers:
            # Bold headers that aren't already bolded
            pattern = f'^{header}:?$'
            replacement = f'**{header}:**'
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.IGNORECASE)
        
        return content
    
    def _format_phone_numbers(self, content: str) -> str:
        """Format phone numbers consistently."""
        # Format (xxx) xxx-xxxx pattern
        content = re.sub(r'\((\d{3})\)\s*(\d{3})-(\d{4})', r'**(\1) \2-\3**', content)
        
        # Format extensions
        content = re.sub(r'x(\d{4,5})', r'**x\1**', content)
        
        return content
    
    def _calculate_formatting_confidence(
        self, 
        content: str, 
        context: MedicalContext, 
        query_type: QueryType
    ) -> float:
        """Calculate formatting confidence score."""
        score = 0.0
        
        # Check for emojis (0.2)
        if re.search(r'[🚨💉⏱️📞💊🔄⚠️📚🧪💡📊🦵🦠📋✅❌]', content):
            score += 0.2
        
        # Check for proper headers (0.2)
        if re.search(r'\*\*[^*]+\*\*:', content):
            score += 0.2
        
        # Check for bullet points (0.2)
        if re.search(r'^[•·-]\s', content, re.MULTILINE):
            score += 0.2
        
        # Check for medical formatting (0.2)
        if re.search(r'(\d+\s*(mg|ml|units|minutes))', content, re.IGNORECASE):
            score += 0.2
        
        # Check for citations (0.2)
        if 'Sources:' in content or '📚' in content:
            score += 0.2
        
        return min(1.0, score)
    
    def _extract_medical_sections(self, content: str) -> List[str]:
        """Extract medical sections from formatted content."""
        sections = []
        
        # Find all bolded headers
        headers = re.findall(r'\*\*([^*]+)\*\*:', content)
        sections.extend(headers)
        
        # Find emoji sections
        emoji_sections = re.findall(r'([🚨💉⏱️📞💊🔄⚠️📚🧪💡📊🦵🦠📋✅❌])\s*\*\*([^*]+)\*\*', content)
        sections.extend([section[1] for section in emoji_sections])
        
        return list(set(sections))  # Remove duplicates
    
    def _count_medical_emojis(self, content: str) -> int:
        """Count medical emojis in content."""
        medical_emojis = re.findall(r'[🚨💉⏱️📞💊🔄⚠️📚🧪💡📊🦵🦠📋✅❌🧪💾🚫]', content)
        return len(medical_emojis)
    
    def _assess_citation_quality(self, content: str, context: MedicalContext) -> str:
        """Assess the quality of citations in the formatted response."""
        if not context.source_citations:
            return "no_sources"
        
        if 'Sources:' in content or '📚' in content:
            if len(context.source_citations) >= 2:
                return "high"
            else:
                return "medium"
        else:
            return "low"
    
    def _fallback_formatting(
        self, 
        context: MedicalContext, 
        raw_response: str, 
        query_type: QueryType
    ) -> FormattedResponse:
        """Fallback formatting when template rendering fails."""
        
        # Basic formatting with emoji
        emoji_map = {
            QueryType.PROTOCOL_STEPS: '🚨',
            QueryType.DOSAGE_LOOKUP: '💉',
            QueryType.CRITERIA_CHECK: '📋',
            QueryType.CONTACT_LOOKUP: '📞',
            QueryType.FORM_RETRIEVAL: '📄',
            QueryType.SUMMARY_REQUEST: '📊'
        }
        
        emoji = emoji_map.get(query_type, '📋')
        
        content = f"{emoji} **Medical Information**\n\n"
        
        if context.primary_content:
            content += context.primary_content
        elif raw_response:
            content += raw_response
        else:
            content += "Medical information not available."
        
        # Add sources if available
        if context.source_citations:
            content += "\n\n📚 **Sources:** "
            content += ", ".join([s.get("display_name", "Unknown") for s in context.source_citations])
        
        return FormattedResponse(
            content=content,
            formatting_confidence=0.3,
            template_used="fallback",
            medical_sections=["Medical Information"],
            emoji_count=1,
            citation_quality="basic"
        )
    
    def _load_medical_emoji_map(self) -> Dict[str, str]:
        """Load medical emoji mappings."""
        return {
            'protocol': '🚨',
            'emergency': '🚨',
            'urgent': '🚨',
            'dose': '💉',
            'medication': '💊',
            'drug': '💊',
            'time': '⏱️',
            'timing': '⏱️',
            'contact': '📞',
            'phone': '📞',
            'call': '📞',
            'warning': '⚠️',
            'caution': '⚠️',
            'critical': '⚠️',
            'workflow': '🔄',
            'steps': '🔄',
            'procedure': '🔄',
            'sources': '📚',
            'reference': '📚',
            'criteria': '📋',
            'rules': '📋',
            'form': '📄',
            'document': '📄',
            'summary': '📊',
            'overview': '📊'
        }
    
    # Additional helper methods for remaining extraction functions
    def _extract_criteria_name(self, query: str, content: str) -> str:
        """Extract criteria name from query and content."""
        query_lower = query.lower()
        
        if 'ottawa' in query_lower:
            return "Ottawa Ankle Rules"
        elif 'sepsis' in query_lower:
            return "Sepsis Criteria"
        elif 'glasgow' in query_lower:
            return "Glasgow Coma Scale"
        else:
            criteria_match = re.search(r'([A-Z][^.]*?criteria)', content, re.IGNORECASE)
            return criteria_match.group(1) if criteria_match else "Clinical Criteria"
    
    def _extract_definition(self, content: str) -> str:
        """Extract definition from content."""
        # Look for definition patterns
        def_patterns = [
            r'definition[^:]*:\s*([^.]+)',
            r'defined as[^:]*:\s*([^.]+)',
            r'is defined as\s*([^.]+)'
        ]
        
        for pattern in def_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_scoring_thresholds(self, content: str) -> List[str]:
        """Extract scoring and threshold information."""
        scoring = []
        
        # Look for numerical thresholds
        threshold_patterns = [
            r'(>\s*\d+[^.]*)',
            r'(<\s*\d+[^.]*)',
            r'(\d+\s*points?[^.]*)',
            r'(score[^.]*\d+[^.]*)'
        ]
        
        for pattern in threshold_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                scoring.append(match.strip())
        
        return scoring[:3]
    
    def _extract_criteria_list(self, content: str) -> List[str]:
        """Extract list of criteria from content."""
        criteria = []
        
        # Look for bullet points or numbered criteria
        bullet_matches = re.findall(r'[•·-]\s*([^•·-\n]+)', content)
        for match in bullet_matches:
            criterion = match.strip()
            if len(criterion) > 5:
                criteria.append(criterion)
        
        return criteria[:5]
    
    def _extract_indications(self, content: str) -> List[str]:
        """Extract indications from content."""
        indications = []
        
        indication_patterns = [
            r'indication[s]?[^:]*:\s*([^.]+)',
            r'use when[^:]*([^.]+)',
            r'indicated for[^:]*([^.]+)'
        ]
        
        for pattern in indication_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                indications.append(match.strip())
        
        return indications[:3]
    
    def _extract_contraindications(self, content: str) -> List[str]:
        """Extract contraindications from content."""
        contras = []
        
        contra_patterns = [
            r'contraindication[s]?[^:]*:\s*([^.]+)',
            r'do not use[^:]*([^.]+)',
            r'avoid[^:]*([^.]+)'
        ]
        
        for pattern in contra_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                contras.append(match.strip())
        
        return contras[:3]
    
    def _extract_clinical_pearls(self, content: str) -> List[str]:
        """Extract clinical pearls from content."""
        pearls = []
        
        pearl_keywords = ['pearl', 'tip', 'remember', 'note', 'important']
        for keyword in pearl_keywords:
            if keyword.lower() in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        pearl = sentence.strip()
                        if len(pearl) > 10:
                            pearls.append(pearl)
                        break
        
        return pearls[:3]
    
    def _extract_contact_header(self, query: str) -> str:
        """Extract contact header from query."""
        query_lower = query.lower()
        
        if 'cardiology' in query_lower:
            return "Cardiology Contacts"
        elif 'surgery' in query_lower:
            return "Surgery Contacts"
        elif 'anesthesia' in query_lower:
            return "Anesthesia Contacts"
        else:
            return "Medical Contacts"
    
    def _extract_primary_contacts(self, content: str) -> List[str]:
        """Extract primary contact information."""
        return self._extract_contacts(content)  # Reuse existing method
    
    def _extract_backup_contacts(self, content: str) -> List[str]:
        """Extract backup contact information."""
        backups = []
        
        backup_keywords = ['backup', 'alternative', 'secondary']
        for keyword in backup_keywords:
            if keyword.lower() in content.lower():
                # Find sentences with backup info
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        backups.append(sentence.strip())
        
        return backups[:3]
    
    def _extract_emergency_contacts(self, content: str) -> List[str]:
        """Extract emergency contact information."""
        emergency = []
        
        emergency_keywords = ['emergency', 'urgent', 'stat', 'escalation']
        for keyword in emergency_keywords:
            if keyword.lower() in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        emergency.append(sentence.strip())
        
        return emergency[:2]
    
    def _extract_contact_notes(self, content: str) -> List[str]:
        """Extract contact notes and instructions."""
        notes = []
        
        note_patterns = [
            r'note[s]?[^:]*:\s*([^.]+)',
            r'hours[^:]*([^.]+)',
            r'availability[^:]*([^.]+)'
        ]
        
        for pattern in note_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                notes.append(match.strip())
        
        return notes[:3]
    
    def _extract_availability(self, content: str) -> str:
        """Extract availability information."""
        avail_patterns = [
            r'available[^.]*(\d+[^.]*)',
            r'hours[^:]*([^.]+)',
            r'(\d+/\d+[^.]*)'
        ]
        
        for pattern in avail_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return "Contact for current availability"
    
    def _extract_form_header(self, query: str) -> str:
        """Extract form header from query."""
        query_lower = query.lower()
        
        if 'transfusion' in query_lower:
            return "Blood Transfusion Forms"
        elif 'consent' in query_lower:
            return "Consent Forms"
        elif 'discharge' in query_lower:
            return "Discharge Forms"
        else:
            return "Medical Forms"
    
    def _extract_available_forms(self, content: str, raw_response: str) -> List[str]:
        """Extract available forms from content and raw response."""
        forms = []
        
        # Look for PDF links in raw response
        pdf_matches = re.findall(r'\[PDF:([^|]+)\|([^\]]+)\]', raw_response)
        for path, name in pdf_matches:
            forms.append(f"[PDF:{path}|{name}]")
        
        # Look for form names in content
        form_patterns = [
            r'([^.]*form[s]?[^.]*)',
            r'([^.]*consent[^.]*)',
            r'([^.]*template[s]?[^.]*)'
        ]
        
        for pattern in form_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:3]:
                if len(match.strip()) > 5:
                    forms.append(match.strip())
        
        return forms[:5]
    
    def _extract_download_instructions(self, raw_response: str) -> List[str]:
        """Extract download instructions from raw response."""
        instructions = []
        
        if 'PDF:' in raw_response:
            instructions.append("Click the PDF links above to download forms")
            instructions.append("Forms will open in a new window")
            instructions.append("Right-click and 'Save As' to save locally")
        else:
            instructions.append("Contact medical records for form access")
        
        return instructions
    
    def _extract_form_notes(self, content: str) -> List[str]:
        """Extract form usage notes."""
        notes = []
        
        note_keywords = ['complete', 'required', 'signature', 'witness']
        for keyword in note_keywords:
            if keyword.lower() in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        notes.append(sentence.strip())
                        break
        
        return notes[:3]
    
    def _extract_summary_header(self, query: str) -> str:
        """Extract summary header from query."""
        query_lower = query.lower()
        
        if 'chest pain' in query_lower:
            return "Chest Pain Management"
        elif 'heart failure' in query_lower:
            return "Heart Failure Management"
        elif 'sepsis' in query_lower:
            return "Sepsis Management"
        else:
            return "Medical Summary"
    
    def _extract_overview(self, content: str, raw_response: str) -> str:
        """Extract overview from content or raw response."""
        # Use first paragraph of content as overview
        paragraphs = content.split('\n\n')
        if paragraphs:
            overview = paragraphs[0].strip()
            if len(overview) > 20:
                return overview
        
        # Fallback to raw response
        if raw_response:
            return raw_response[:200] + "..." if len(raw_response) > 200 else raw_response
        
        return "Medical information available from referenced sources."
    
    def _extract_key_points(self, content: str) -> List[str]:
        """Extract key points from content."""
        points = []
        
        # Look for bullet points
        bullet_matches = re.findall(r'[•·-]\s*([^•·-\n]+)', content)
        for match in bullet_matches[:5]:
            point = match.strip()
            if len(point) > 10:
                points.append(point)
        
        # If no bullets, extract important sentences
        if not points:
            sentences = content.split('.')
            for sentence in sentences[:5]:
                if any(word in sentence.lower() for word in ['important', 'key', 'critical', 'essential']):
                    points.append(sentence.strip())
        
        return points[:5]
    
    def _extract_clinical_approach(self, content: str) -> List[str]:
        """Extract clinical approach information."""
        approach = []
        
        approach_keywords = ['approach', 'method', 'strategy', 'management', 'treatment']
        for keyword in approach_keywords:
            if keyword.lower() in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        approach.append(sentence.strip())
                        break
        
        return approach[:3]
    
    def _extract_management_points(self, content: str) -> List[str]:
        """Extract management points from content."""
        mgmt = []
        
        mgmt_patterns = [
            r'manage[ment]*[^.]*([^.]+)',
            r'treat[ment]*[^.]*([^.]+)',
            r'therapy[^.]*([^.]+)'
        ]
        
        for pattern in mgmt_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                mgmt.append(match.strip())
        
        return mgmt[:3]
    
    def _extract_monitoring_points(self, content: str) -> List[str]:
        """Extract monitoring and follow-up information."""
        monitoring = []
        
        monitor_keywords = ['monitor', 'follow', 'assess', 'evaluate', 'track']
        for keyword in monitor_keywords:
            if keyword.lower() in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        monitoring.append(sentence.strip())
                        break
        
        return monitoring[:3]
    
    def _extract_complications(self, content: str) -> List[str]:
        """Extract complications to watch for."""
        complications = []
        
        comp_keywords = ['complication', 'adverse', 'risk', 'watch', 'monitor for']
        for keyword in comp_keywords:
            if keyword.lower() in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        complications.append(sentence.strip())
                        break
        
        return complications[:3]
    
    def _get_action_header(self, protocol_name: str) -> str:
        """Get appropriate action header for protocol."""
        if 'STEMI' in protocol_name:
            return "Actions"
        elif 'sepsis' in protocol_name.lower():
            return "Initial Actions"
        else:
            return "Clinical Actions"
    
    def _extract_administration_details(self, content: str) -> List[str]:
        """Extract medication administration details."""
        admin = []
        
        admin_patterns = [
            r'(IV|IM|PO|SQ)[^.]*',
            r'administer[^.]*',
            r'give[^.]*'
        ]
        
        for pattern in admin_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                admin.append(match.strip())
        
        return admin[:3]
    
    def _extract_dosing_timing(self, content: str) -> List[str]:
        """Extract dosing timing information."""
        timing = []
        
        timing_patterns = [
            r'every\s*\d+[^.]*',
            r'q\d+[^.]*',
            r'repeat[^.]*',
            r'interval[^.]*'
        ]
        
        for pattern in timing_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                timing.append(match.strip())
        
        return timing[:3]
    
    def _extract_drug_warnings(self, content: str) -> List[str]:
        """Extract drug-specific warnings."""
        return self._extract_warnings(content)  # Reuse existing method
