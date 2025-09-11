"""
Medical-Specific LLM Prompts for PRP-41: Universal Curated-Quality Response System
Query-type-specific prompts that generate curated-quality medical responses.
"""

from typing import Dict

from src.models.query_types import QueryType
from src.pipeline.enhanced_medical_retriever import MedicalContext


class UniversalMedicalPrompts:
    """
    Medical prompts that generate curated-quality responses
    with professional formatting and medical accuracy.
    """
    
    def __init__(self):
        self.curated_examples = self._load_curated_examples()
    
    def get_universal_medical_prompt(
        self, 
        query_type: QueryType, 
        query: str, 
        context: MedicalContext
    ) -> str:
        """
        Get medical prompt that generates curated-quality responses.
        
        Args:
            query_type: Type of medical query
            query: User's original query
            context: Enhanced medical context
            
        Returns:
            Prompt optimized for curated-quality response generation
        """
        
        # Select appropriate curated-quality prompt
        prompt_generators = {
            QueryType.PROTOCOL_STEPS: self._get_protocol_curated_prompt,
            QueryType.DOSAGE_LOOKUP: self._get_dosage_curated_prompt,
            QueryType.CRITERIA_CHECK: self._get_criteria_curated_prompt,
            QueryType.CONTACT_LOOKUP: self._get_contact_curated_prompt,
            QueryType.FORM_RETRIEVAL: self._get_form_curated_prompt,
            QueryType.SUMMARY_REQUEST: self._get_summary_curated_prompt
        }
        
        generator = prompt_generators.get(query_type, self._get_summary_curated_prompt)
        return generator(query, context)
    
    def _get_protocol_curated_prompt(self, query: str, context: MedicalContext) -> str:
        """Generate curated-quality protocol response prompt."""
        
        protocol_example = self.curated_examples["protocol_example"]
        
        return f"""You are an Emergency Department protocol specialist. Generate a PROFESSIONAL, CURATED-QUALITY medical protocol response.

CRITICAL FORMATTING REQUIREMENTS:
1. Use EXACTLY this professional medical format with emojis
2. Follow the structure of curated medical protocols
3. Include specific medical details from context
4. Maintain emergency medicine professionalism
5. Never generate generic or vague responses

CURATED EXAMPLE FORMAT (follow this exact structure):
{protocol_example}

USER QUERY: "{query}"

MEDICAL CONTEXT PROVIDED:
{self._format_context_for_prompt(context)}

RESPONSE GENERATION RULES:
1. Start with protocol emoji and bold protocol name
2. Use medical section emojis (⏱️ 📞 💉 💊 🔄 ⚠️)
3. Include specific timing, contacts, medications from context
4. Use bullet points with specific medical details
5. Include numbered workflow steps
6. Add critical warnings from context
7. End with proper source citations using 📚

MEDICAL ACCURACY REQUIREMENTS:
- Only use information explicitly provided in context
- Include specific doses, timing, contact numbers
- Maintain medical terminology precision
- Add appropriate safety warnings
- Cite sources accurately

Generate response following the EXACT curated format above:"""
    
    def _get_dosage_curated_prompt(self, query: str, context: MedicalContext) -> str:
        """Generate curated-quality dosage response prompt."""
        
        dosage_example = self.curated_examples["dosage_example"]
        
        return f"""You are an Emergency Department pharmacist. Generate a PROFESSIONAL, CURATED-QUALITY medication dosing response.

CRITICAL FORMATTING REQUIREMENTS:
1. Use EXACTLY this professional medical format with emojis
2. Follow curated dosing response structure
3. Include specific dosing from context
4. Maintain pharmaceutical precision
5. Never approximate or guess dosages

CURATED EXAMPLE FORMAT (follow this exact structure):
{dosage_example}

USER QUERY: "{query}"

MEDICAL CONTEXT PROVIDED:
{self._format_context_for_prompt(context)}

RESPONSE GENERATION RULES:
1. Start with medication emoji 💉 and bold medication name
2. Use dosing section emojis (🧪 💉 ⏱️ 🚫 ⚠️)
3. Separate adult and pediatric dosing clearly
4. Include preparation and administration details
5. Add timing/frequency information
6. Include contraindications and warnings
7. End with proper source citations using 📚

PHARMACEUTICAL SAFETY REQUIREMENTS:
- Only use dosages explicitly stated in context
- Include units (mg, ml, units) precisely
- Specify administration routes (IV, IM, PO)
- Add critical timing intervals
- Include safety warnings and contraindications
- Never calculate or convert doses

Generate response following the EXACT curated format above:"""
    
    def _get_criteria_curated_prompt(self, query: str, context: MedicalContext) -> str:
        """Generate curated-quality criteria response prompt."""
        
        criteria_example = self.curated_examples["criteria_example"]
        
        return f"""You are an Emergency Department clinical expert. Generate a PROFESSIONAL, CURATED-QUALITY clinical criteria response.

CRITICAL FORMATTING REQUIREMENTS:
1. Use EXACTLY this professional medical format with emojis
2. Follow curated criteria response structure
3. Include specific thresholds from context
4. Maintain clinical decision-making precision
5. Never provide unclear or vague criteria

CURATED EXAMPLE FORMAT (follow this exact structure):
{criteria_example}

USER QUERY: "{query}"

MEDICAL CONTEXT PROVIDED:
{self._format_context_for_prompt(context)}

RESPONSE GENERATION RULES:
1. Start with criteria emoji 📋 and bold criteria name
2. Use clinical section emojis (📊 ✅ ❌ 💡)
3. Include specific numerical thresholds
4. List clear inclusion/exclusion criteria
5. Add clinical decision points
6. Include clinical pearls and important notes
7. End with proper source citations using 📚

CLINICAL ACCURACY REQUIREMENTS:
- Only use criteria explicitly stated in context
- Include specific numerical values and thresholds
- Specify scoring systems accurately
- Add sensitivity/specificity data if available
- Include age restrictions and limitations
- Cite validation studies if mentioned

Generate response following the EXACT curated format above:"""
    
    def _get_contact_curated_prompt(self, query: str, context: MedicalContext) -> str:
        """Generate curated-quality contact response prompt."""
        
        return f"""You are an Emergency Department contact directory specialist. Generate a PROFESSIONAL, CURATED-QUALITY contact response.

CRITICAL FORMATTING REQUIREMENTS:
1. Use professional medical contact format with emojis
2. Format phone numbers as **(xxx) xxx-xxxx**
3. Bold all phone numbers and extensions
4. Include specialty and role information
5. Never provide generic contact information

USER QUERY: "{query}"

MEDICAL CONTEXT PROVIDED:
{self._format_context_for_prompt(context)}

RESPONSE GENERATION RULES:
1. Start with contact emoji 📞 and bold contact header
2. Use contact section organization
3. Bold all phone numbers and pager numbers
4. Include department and specialty
5. Add backup/alternative contacts if available
6. Include availability hours if provided
7. End with proper source citations using 📚

CONTACT ACCURACY REQUIREMENTS:
- Only provide contact information from context
- Format numbers consistently and professionally
- Include role/specialty identifiers
- Add emergency escalation contacts
- Specify availability/hours when known
- Bold all contact numbers for visibility

Generate professional contact response:"""
    
    def _get_form_curated_prompt(self, query: str, context: MedicalContext) -> str:
        """Generate curated-quality form response prompt."""
        
        return f"""You are an Emergency Department forms specialist. Generate a PROFESSIONAL, CURATED-QUALITY medical forms response.

CRITICAL FORMATTING REQUIREMENTS:
1. Use professional medical forms format with emojis
2. Include actual PDF download links in format: [PDF:/path/file.pdf|Display Name]
3. Never describe forms without providing download links
4. Include brief usage instructions
5. Organize forms by category or type

USER QUERY: "{query}"

MEDICAL CONTEXT PROVIDED:
{self._format_context_for_prompt(context)}

RESPONSE GENERATION RULES:
1. Start with forms emoji 📄 and bold forms header
2. List each form with PDF download link
3. Include brief description of form purpose
4. Add completion instructions if relevant
5. Include required signatures/witnesses
6. Add form submission instructions
7. End with proper source citations using 📚

FORMS ACCESS REQUIREMENTS:
- Provide actual PDF download links when available
- Include form names and descriptions
- Add completion and submission instructions
- Specify required signatures or witnesses
- Include contact for form assistance
- Never describe forms without providing access

Generate professional forms response:"""
    
    def _get_summary_curated_prompt(self, query: str, context: MedicalContext) -> str:
        """Generate curated-quality summary response prompt."""
        
        return f"""You are an Emergency Department medical expert. Generate a PROFESSIONAL, CURATED-QUALITY medical summary response.

CRITICAL FORMATTING REQUIREMENTS:
1. Use professional medical summary format with emojis
2. Create structured sections with appropriate emojis
3. Include key clinical points and management
4. Maintain medical professionalism throughout
5. Synthesize information from multiple sources

USER QUERY: "{query}"

MEDICAL CONTEXT PROVIDED:
{self._format_context_for_prompt(context)}

RESPONSE GENERATION RULES:
1. Start with summary emoji 📊 and bold summary header
2. Use medical section emojis (🔑 ⚕️ 💉 📈 ⚠️)
3. Include key clinical points
4. Add clinical approach and management
5. Include monitoring and follow-up
6. Add complications to watch for
7. End with proper source citations using 📚

MEDICAL SYNTHESIS REQUIREMENTS:
- Synthesize information from all provided context
- Include key clinical decision points
- Add management and treatment approaches
- Include monitoring and complications
- Maintain medical accuracy throughout
- Cite all sources comprehensively

Generate comprehensive medical summary:"""
    
    def _format_context_for_prompt(self, context: MedicalContext) -> str:
        """Format medical context for prompt inclusion."""
        
        context_sections = []
        
        # Primary content
        if context.primary_content:
            context_sections.append(f"PRIMARY MEDICAL CONTENT:\n{context.primary_content}")
        
        # Supporting evidence
        if context.supporting_evidence:
            context_sections.append("SUPPORTING EVIDENCE:\n" + "\n".join(context.supporting_evidence))
        
        # Medical terminology
        if context.medical_terminology:
            terminology_str = "\n".join([f"- {abbrev}: {meaning}" for abbrev, meaning in context.medical_terminology.items()])
            context_sections.append(f"MEDICAL TERMINOLOGY:\n{terminology_str}")
        
        # Source citations
        if context.source_citations:
            citations_str = "\n".join([f"- {cite.get('display_name', 'Unknown')}" for cite in context.source_citations])
            context_sections.append(f"SOURCE DOCUMENTS:\n{citations_str}")
        
        # Clinical metadata
        metadata = []
        metadata.append(f"Clinical Relevance Score: {context.clinical_relevance_score:.2f}")
        metadata.append(f"Medical Certainty Level: {context.medical_certainty_level}")
        metadata.append(f"Query Type Alignment: {context.query_type_alignment:.2f}")
        
        if context.confidence_indicators:
            metadata.append(f"Confidence Indicators: {', '.join(context.confidence_indicators)}")
        
        context_sections.append("CLINICAL METADATA:\n" + "\n".join(metadata))
        
        return "\n\n".join(context_sections)
    
    def _load_curated_examples(self) -> Dict[str, str]:
        """Load curated response examples for prompt formatting."""
        return {
            "protocol_example": """🚨 **STEMI Activation Protocol**

📞 **CRITICAL CONTACTS:**
• STEMI Pager: **(917) 827-9725**
• Cath Lab Direct: **x40935**

⏱️ **TIMING REQUIREMENTS:**
• Door-to-balloon goal: **90 minutes**
• EKG within **10 minutes** of arrival
• Activate within **2 minutes** of EKG confirmation

💊 **STEMI Pack Medications:**
• ASA 324mg (chewed)
• Brillinta 180mg
• Crestor 80mg  
• Heparin 4000 units IV bolus

🔄 **Workflow:**
1. EKG at triage for chest pain patients
2. MD review within 2 minutes
3. STEMI activation if criteria met → Call (917) 827-9725
4. Cath lab team activation → Call x40935
5. Transport by Cardiac Fellow

⚠️ **Critical Notes:**
• Never delay activation for additional testing
• Prepare patient for immediate transport

📚 **Sources:** STEMI Activation Protocol 2024""",
            
            "dosage_example": """💉 **Epinephrine for Cardiac Arrest**

**Adult Dose:**
• **1mg IV/IO every 3-5 minutes** during CPR
• Continue until ROSC or termination of efforts

**Pediatric Dose:**
• **0.01 mg/kg IV/IO (0.1 mL/kg of 1:10,000)** every 3-5 minutes
• Maximum single dose: 1mg

🧪 **Preparation:**
• Use 1:10,000 concentration (1mg/10mL)
• Pre-filled syringes preferred
• Can be given via ET tube if no IV/IO access

💉 **Administration:**
• Give after 2 minutes of CPR (after initial defibrillation attempts)
• Continue every 3-5 minutes throughout resuscitation

⚠️ **Critical Warnings:**
• Never delay CPR or defibrillation to give epinephrine
• Do not use 1:1,000 concentration for IV administration

📚 **Sources:** ACLS Guidelines 2024, Cardiac Arrest Protocol""",
            
            "criteria_example": """📋 **Ottawa Ankle Rules**

**Definition:**
Clinical decision rule to determine need for ankle X-rays in acute injuries.

📊 **X-ray Required if ANY of the following:**

**Malleolar Zone:**
• Bone tenderness at posterior edge or tip of lateral malleolus
• Bone tenderness at posterior edge or tip of medial malleolus

**Midfoot Zone:**
• Bone tenderness at base of 5th metatarsal
• Bone tenderness at navicular bone

✅ **Functional Criteria:**
• Unable to bear weight both immediately after injury AND in ED
• Unable to walk 4 steps (limping is okay)

❌ **Limitations:**
• Rules apply to patients age 18-55 years
• Not validated in children or elderly

💡 **Clinical Pearls:**
• **Sensitivity:** 97-100% for detecting fractures
• **Purpose:** Reduce unnecessary ankle X-rays by ~30-40%

📚 **Sources:** Ottawa Rules Clinical Decision Guide"""
        }
    
    def get_quality_enhancement_prompt(
        self, 
        base_response: str, 
        query_type: QueryType,
        context: MedicalContext
    ) -> str:
        """
        Get prompt for enhancing response quality to curated standards.
        
        Args:
            base_response: Initial LLM response
            query_type: Type of query
            context: Medical context
            
        Returns:
            Prompt for quality enhancement
        """
        
        return f"""You are a medical response quality expert. Transform this basic response into CURATED-QUALITY medical content.

CURRENT RESPONSE (needs improvement):
{base_response}

QUALITY REQUIREMENTS:
1. Professional medical formatting with appropriate emojis
2. Structured sections with bold headers
3. Specific medical details from context
4. Proper source citations
5. Emergency medicine professionalism

MEDICAL CONTEXT:
{self._format_context_for_prompt(context)}

TRANSFORMATION INSTRUCTIONS:
1. Add professional medical emojis and formatting
2. Structure into clear sections with bold headers
3. Include specific medical details (doses, timing, contacts)
4. Add proper source citations at the end
5. Ensure emergency medicine appropriateness
6. Remove any generic or vague language
7. Add critical warnings and safety information

Transform the response to match curated medical quality standards:"""
    
    def get_safety_validation_prompt(
        self, 
        query: str, 
        response: str, 
        context: MedicalContext
    ) -> str:
        """Get prompt for medical safety validation."""
        
        return f"""You are a medical safety validator. Assess this medical response for safety and accuracy.

ORIGINAL QUERY: "{query}"

MEDICAL RESPONSE TO VALIDATE:
{response}

AVAILABLE CONTEXT:
{self._format_context_for_prompt(context)}

SAFETY ASSESSMENT CRITERIA:
1. Medical Accuracy - All facts supported by context
2. Dosing Safety - Accurate doses, routes, frequencies
3. Contact Accuracy - Correct phone numbers and extensions
4. Warning Completeness - Appropriate safety warnings included
5. Source Compliance - Proper citations and attributions

VALIDATION CHECKLIST:
□ All medical facts are supported by provided context
□ Dosages include correct units and administration routes
□ Contact information is accurate and properly formatted
□ Critical warnings and contraindications are included
□ Sources are properly cited and attributable
□ Emergency medicine appropriateness maintained
□ No hallucinated or unsupported medical information

Provide validation assessment with specific safety score (1-10) and any concerns:"""
    
    def get_citation_quality_prompt(self, response: str, context: MedicalContext) -> str:
        """Get prompt for citation quality assessment."""
        
        return f"""Assess the citation quality in this medical response.

MEDICAL RESPONSE:
{response}

AVAILABLE SOURCES:
{', '.join([cite.get('display_name', 'Unknown') for cite in context.source_citations])}

CITATION QUALITY CRITERIA:
1. All sources properly referenced
2. Citations match actual source documents
3. Medical facts are attributable to sources
4. Source formatting is professional
5. No missing or incorrect citations

Assessment:"""
    
    def get_medical_formatting_prompt(self, content: str, query_type: QueryType) -> str:
        """Get prompt for medical formatting enhancement."""
        
        return f"""Enhance the medical formatting of this content to match curated standards.

CONTENT TO FORMAT:
{content}

QUERY TYPE: {query_type.value}

FORMATTING REQUIREMENTS:
1. Add appropriate medical emojis for sections
2. Bold all headers and important information
3. Use bullet points for lists
4. Format phone numbers as **(xxx) xxx-xxxx**
5. Ensure professional medical structure
6. Add section emojis based on content type

Enhanced formatted version:"""
