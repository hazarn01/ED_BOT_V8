"""
Mock Medical LLM Client for Development
Provides realistic medical responses when the real LLM backend is unavailable
"""
import asyncio
from typing import Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MockMedicalClient:
    """Mock LLM client that returns realistic medical responses"""
    
    def __init__(self):
        self.temperature = 0.0
        self.max_tokens = 1024
        
        # Pre-defined medical responses for different query types
        self.medical_responses = {
            "stemi": """
STEMI Activation Protocol:

Door-to-Balloon Time Goal: 90 minutes

Immediate Actions:
• EKG within 10 minutes of arrival
• STEMI activation via pager: 917-827-9725
• Cath Lab notification: x40935
• Upgrade patient to RESUS

STEMI Pack Medications:
• ASA 324mg (chewed)
• Brillinta 180mg  
• Crestor 80mg
• Heparin 4000 units IV bolus

Key Contacts:
• STEMI pager: 917-827-9725
• Cath Lab: x40935
• Cardiology Fellow on call

Critical timing: Every minute counts for myocardial salvage.
""",
            "sepsis": """
ED Sepsis Pathway:

Severity Criteria:
• Severe sepsis: Lactate > 2
• Septic shock: Lactate > 4

Initial Actions (0:00-1:00):
• Draw lactate immediately
• Start IVF & antibiotics based on verbal orders
• Use Adult Sepsis Order Set
• Initial Sepsis Note template

Reassessment (3 hours):
• Repeat lactate measurement
• Post-fluid blood pressure assessment
• Focused cardiovascular assessment
• Sepsis Reassessment Note template
• RN + PA/MD huddle

Early recognition and treatment are critical for improved outcomes.
""",
            "hypoglycemia": """
Hypoglycemia Treatment Guidelines:

Definition: Blood glucose <70 mg/dL

Conscious Patients:
• IV access: 50mL (25g) D50 IV over 2-5 minutes
• If POCG remains <100, repeat as needed
• Oral (if not NPO): 15-20g rapid-acting carbs

Unconscious Patients:
• Without IV: Glucagon 1mg IM (can repeat x1)
• Simultaneously obtain IV access
• Once IV: 50mL D50 IV over 2-5 minutes

Special Considerations:
• Malnourished patients: Glucagon may not work
• Add thiamine, don't delay glucose
• Refractory cases: Consider IV glucocorticoid
""",
            "blood_transfusion": """
Blood Transfusion Consent Form:

Required documentation includes:
• Patient identification verification
• Blood type and crossmatch results
• Indication for transfusion
• Risks and benefits discussion
• Alternative treatment options
• Patient consent signature

Pre-transfusion checklist:
• Verify patient identity with two identifiers
• Check blood product compatibility
• Baseline vital signs
• IV access 18-gauge or larger

Contact Blood Bank: x4567 for urgent requests
""",
            "cardiology_oncall": """
Cardiology On-Call Information:

Current Coverage:
• Attending: Dr. Sarah Chen, MD
• Fellow: Dr. Michael Rodriguez, MD
• Pager: 917-555-0123

Consultation Guidelines:
• STEMI: Immediate activation
• NSTEMI: Within 24 hours
• Heart failure: Same day
• Arrhythmias: Based on stability

For urgent consultations, page directly.
Non-urgent consults can be placed through Epic.
""",
            "default": """
I can help you with emergency department protocols, medication dosing, 
decision criteria, and contact information. Please specify your clinical 
question for the most accurate medical guidance.

Common queries:
• STEMI protocol
• Sepsis pathway  
• Hypoglycemia treatment
• Blood transfusion forms
• On-call contacts

All medical information should be verified with current institutional protocols.
"""
        }
    
    async def health_check(self) -> bool:
        """Mock health check - always returns True"""
        return True
    
    async def close(self):
        """Mock close method"""
        pass
    
    def _get_response_for_query(self, query: str) -> str:
        """Determine appropriate medical response based on query content"""
        query_lower = query.lower()
        
        if any(term in query_lower for term in ["stemi", "heart attack", "mi", "cath lab"]):
            return self.medical_responses["stemi"]
        elif any(term in query_lower for term in ["sepsis", "lactate", "infection"]):
            return self.medical_responses["sepsis"]
        elif any(term in query_lower for term in ["hypoglycemia", "glucose", "d50", "glucagon"]):
            return self.medical_responses["hypoglycemia"]
        elif any(term in query_lower for term in ["blood transfusion", "transfusion form", "blood bank"]):
            return self.medical_responses["blood_transfusion"]
        elif any(term in query_lower for term in ["cardiology", "on call", "cardiologist"]):
            return self.medical_responses["cardiology_oncall"]
        else:
            return self.medical_responses["default"]
    
    async def generate_response(
        self,
        prompt: str,
        context: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate mock medical response"""
        # Add a small delay to simulate processing
        await asyncio.sleep(0.5)
        
        logger.info(f"Mock LLM generating response for query: {prompt[:100]}...")
        
        # Extract the actual query from the prompt
        if "Query:" in prompt:
            query_part = prompt.split("Query:")[-1].strip()
            # Remove any additional prompt instructions
            query_part = query_part.split("\n")[0].strip()
        else:
            query_part = prompt
        
        response = self._get_response_for_query(query_part)
        
        # Add context awareness if provided
        if context and len(context.strip()) > 0:
            response += "\n\nBased on available clinical protocols and guidelines."
        
        return response
    
    async def generate_streaming_response(self, prompt: str, **kwargs):
        """Mock streaming response - yields the full response"""
        response = await self.generate_response(prompt, **kwargs)
        
        # Simulate streaming by yielding chunks
        words = response.split()
        for i in range(0, len(words), 5):  # Yield 5 words at a time
            chunk = " ".join(words[i:i+5]) + " "
            yield {"choices": [{"delta": {"content": chunk}}]}
            await asyncio.sleep(0.1)  # Small delay between chunks