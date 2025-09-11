"""
PRP-42: Curated-Quality Response Prompts for Llama 3.1 13B
Prompts optimized for Llama 3.1 13B that generate curated-quality responses
using ground truth examples from 338+ medical QA pairs.
"""

from typing import Dict, List, Optional

from ..models.query_types import QueryType


class CuratedQualityPrompts:
    """
    Prompts optimized for Llama 3.1 13B to generate curated-quality responses.
    Uses ground truth examples to ensure consistent professional medical formatting.
    """
    
    def __init__(self):
        self.ground_truth_examples = self._load_ground_truth_examples()
        self.llama_optimization_settings = {
            'temperature': 0.0,  # Deterministic for medical consistency
            'max_tokens': 512,   # Match curated response length
            'top_p': 0.9,
            'frequency_penalty': 0.1
        }
    
    def get_curated_prompt(self, 
                          query_type: QueryType,
                          query: str,
                          medical_context: str,
                          ground_truth_examples: Optional[List[str]] = None) -> str:
        """
        Generate Llama 3.1 13B optimized prompt with ground truth examples.
        
        Args:
            query_type: Type of medical query
            query: Original user query
            medical_context: Retrieved medical context
            ground_truth_examples: Specific examples for this query type
            
        Returns:
            Prompt optimized for Llama 3.1 13B curated-quality generation
        """
        
        # Get query-specific examples
        examples = ground_truth_examples or self.ground_truth_examples.get(query_type.value, [])
        
        # Build Llama 3.1 13B optimized prompt
        base_prompt = self._get_base_medical_prompt()
        query_specific = self._get_query_specific_prompt(query_type, examples)
        context_integration = self._get_context_integration_prompt(medical_context)
        formatting_requirements = self._get_formatting_requirements(query_type)
        
        full_prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{base_prompt}

{query_specific}

{formatting_requirements}

<|eot_id|><|start_header_id|>user<|end_header_id|>

{context_integration}

QUERY: {query}

Generate a curated-quality medical response following the exact format and style of the ground truth examples above.

<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        
        return full_prompt
    
    def _get_base_medical_prompt(self) -> str:
        """Base medical system prompt for Llama 3.1 13B."""
        return """You are an expert Emergency Department physician providing curated-quality medical responses. 

CRITICAL REQUIREMENTS:
- Generate responses that match the EXACT quality and format of ground truth medical examples
- Use precise medical terminology and dosing information
- Follow professional medical formatting with appropriate structure
- Never use uncertain language (avoid "may", "might", "possibly")
- Always provide specific, actionable medical information
- Include exact dosages, timing, and contact information when relevant"""
    
    def _get_query_specific_prompt(self, query_type: QueryType, examples: List[str]) -> str:
        """Get query-type specific prompt with ground truth examples."""
        
        if query_type == QueryType.DOSAGE_LOOKUP:
            return """
MEDICATION DOSAGE RESPONSE FORMAT (Ground Truth Examples):

Example 1: "What is the first-line treatment for anaphylaxis in adults?"
CURATED RESPONSE: "Epinephrine 1mg/mL (1:1000) injection, 0.5mg IM"

Example 2: "What is the pediatric dosing for epinephrine in anaphylaxis?"
CURATED RESPONSE: "0.01mg/kg IM"

PATTERN TO FOLLOW:
- [Drug name] [concentration] ([ratio]) injection, [exact dose] [route]
- For pediatric: [dose per kg] [route]
- Always include specific concentrations and routes
- Use standard abbreviations: IM, IV, PO"""
            
        elif query_type == QueryType.CRITERIA_CHECK:
            return """
MEDICAL CRITERIA RESPONSE FORMAT (Ground Truth Examples):

Example: "What are the two main diagnostic criteria for anaphylaxis?"
CURATED RESPONSE: "1. Acute onset illness with skin/mucosal involvement plus respiratory compromise, reduced BP, or severe GI symptoms. 2. Acute onset hypotension/bronchospasm/laryngeal involvement after known allergen exposure, even without skin involvement"

PATTERN TO FOLLOW:
- Use numbered lists: "1. [criteria one] 2. [criteria two]"
- Be specific about clinical conditions
- Include measurable thresholds when relevant
- Use professional medical terminology"""
            
        elif query_type == QueryType.PROTOCOL_STEPS:
            return """
PROTOCOL RESPONSE FORMAT (Ground Truth Examples):

Example Protocol Structure:
🚨 **[Protocol Name]**

📞 **CRITICAL CONTACTS:**
• [Contact type]: [Phone number]
• [Service]: [Extension]

⏱️ **TIMING REQUIREMENTS:**
• [Goal timing]: [X minutes]
• [Action]: [timeframe]

💊 **MEDICATIONS:**
• [Drug] [dose]
• [Drug] [dose]

PATTERN TO FOLLOW:
- Always start with protocol emoji and bold title
- Include specific contact information
- Specify exact timing requirements
- List concrete actions and medications"""
            
        elif query_type == QueryType.CONTACT_LOOKUP:
            return """
CONTACT INFORMATION FORMAT (Ground Truth Examples):

Example: "STEMI Pager: (917) 827-9725"
Example: "Cath Lab Direct: x40935"

PATTERN TO FOLLOW:
- Format phone numbers as: (XXX) XXX-XXXX
- Format extensions as: xNNNN
- Always bold contact names
- Use 📞 emoji for phone contacts"""
            
        elif query_type == QueryType.SUMMARY_REQUEST:
            return """
SUMMARY RESPONSE FORMAT (Ground Truth Examples):

Structure for summaries:
**Key Points:**
• [Main point 1 with specific details]
• [Main point 2 with specific details]  
• [Main point 3 with specific details]

PATTERN TO FOLLOW:
- Use bullet points for key information
- Include specific medical details
- Keep concise but comprehensive
- Focus on clinically actionable information"""
        
        else:
            return """
GENERAL MEDICAL RESPONSE FORMAT:

PATTERN TO FOLLOW:
- Use professional medical language
- Be specific and actionable
- Include relevant timing, dosing, or contact information
- Structure information clearly
- Avoid uncertain language"""
    
    def _get_context_integration_prompt(self, medical_context: str) -> str:
        """Prompt for integrating medical context."""
        return f"""
MEDICAL CONTEXT TO USE:
{medical_context}

INTEGRATION INSTRUCTIONS:
- Use ONLY the information provided in the medical context
- Extract specific dosages, timing, and procedures mentioned
- Preserve exact contact information and phone numbers
- Maintain medical accuracy from source documents
- If context lacks specific information, focus on what is available"""
    
    def _get_formatting_requirements(self, query_type: QueryType) -> str:
        """Get formatting requirements for specific query types."""
        
        base_formatting = """
FORMATTING REQUIREMENTS FOR LLAMA 3.1 13B:
- Maximum 400 words (curated responses are concise)
- Use bullet points (•) for lists
- Bold important headers with **text**
- Include emojis for medical categories (🚨 💊 📞 ⏱️)
- No uncertain language ("may", "might", "possibly")
- Professional medical tone throughout
"""
        
        if query_type == QueryType.DOSAGE_LOOKUP:
            return base_formatting + """
DOSAGE-SPECIFIC REQUIREMENTS:
- Always include exact concentrations: "1mg/mL (1:1000)"
- Specify route of administration: IM, IV, PO
- Include pediatric vs adult dosing when relevant
- No spaces between numbers and units: "0.5mg" not "0.5 mg"
"""
            
        elif query_type == QueryType.PROTOCOL_STEPS:
            return base_formatting + """
PROTOCOL-SPECIFIC REQUIREMENTS:
- Start with: 🚨 **[Protocol Name]**
- Include timing goals: "Door-to-balloon: 90 minutes"
- List specific contact numbers with proper formatting
- Use structured sections with emoji headers
- End with critical notes if relevant
"""
            
        return base_formatting
    
    def _load_ground_truth_examples(self) -> Dict[str, List[str]]:
        """Load ground truth examples for each query type."""
        return {
            'dosage': [
                'Epinephrine 1mg/mL (1:1000) injection, 0.5mg IM',
                '0.01mg/kg IM',
                'Albuterol nebulization',
                'Sodium Chloride 0.9% injection (IV fluids)',
                '0.1 mcg/kg/min'
            ],
            'criteria': [
                '1. Acute onset illness with skin/mucosal involvement plus respiratory compromise, reduced BP, or severe GI symptoms. 2. Acute onset hypotension/bronchospasm/laryngeal involvement after known allergen exposure',
                'For persistent problems with airway, breathing, circulation despite appropriate epinephrine dosing and symptom-directed medical management',
                'If there is airway involvement (stridor) or significant edema of tongue, oropharynx, or voice alteration'
            ],
            'timing': [
                'Consider monitoring for 4-6 hours',
                'Acute onset (minutes to several hours)',
                'Door-to-balloon goal: 90 minutes',
                'EKG within 10 minutes of arrival'
            ],
            'workflow': [
                '3-day course of prednisone (if received steroids), antihistamine, EpiPen, and referral to allergist',
                'Anaphylaxis orderset (can also be found using search term allergic reaction)',
                'Initial reaction must be treated with two or more doses of IM epinephrine'
            ],
            'contact': [
                'STEMI Pager: (917) 827-9725',
                'Cath Lab Direct: x40935'
            ]
        }

def create_curated_quality_prompts() -> CuratedQualityPrompts:
    """Factory function to create CuratedQualityPrompts instance."""
    return CuratedQualityPrompts()
