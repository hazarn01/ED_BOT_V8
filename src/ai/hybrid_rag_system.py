"""
Hybrid RAG System: Encoder-Decoder + Decoder-Only for Medical Queries
Combines T5-based fact extraction with Azure OpenAI response generation
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer

from .azure_fallback_client import AzureOpenAIClient
from ..config.enhanced_settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFact:
    """Structured medical fact with source attribution"""
    fact: str
    source: str
    confidence: float
    category: str  # protocol, dosage, contact, criteria, etc.
    

@dataclass
class HybridResponse:
    """Response from hybrid RAG system"""
    response: str
    extracted_facts: List[ExtractedFact]
    sources: List[Dict[str, str]]
    confidence: float
    processing_time: float
    method_used: str
    cost_breakdown: Dict[str, float]


class MedicalFactExtractor:
    """Encoder-decoder model for precise medical fact extraction"""
    
    def __init__(self, model_name: str = "google/flan-t5-large"):
        self.model_name = model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.tokenizer = None
        self.loaded = False
        
        logger.info(f"Initializing MedicalFactExtractor with {model_name} on {self.device}")
    
    async def load_model(self):
        """Load T5 model for fact extraction"""
        if self.loaded:
            return
            
        try:
            logger.info(f"Loading {self.model_name}...")
            self.tokenizer = T5Tokenizer.from_pretrained(self.model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
                device_map="auto" if self.device.type == "cuda" else None
            )
            
            if self.device.type == "cpu":
                self.model = self.model.to(self.device)
            
            self.loaded = True
            logger.info(f"✅ {self.model_name} loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load {self.model_name}: {e}")
            raise
    
    async def extract_medical_facts(self, query: str, documents: List[str]) -> List[ExtractedFact]:
        """Extract structured medical facts from documents using T5"""
        if not self.loaded:
            await self.load_model()
        
        extracted_facts = []
        
        for i, doc in enumerate(documents[:3]):  # Limit to 3 docs for performance
            try:
                # Create T5 prompt for medical fact extraction
                prompt = self._create_extraction_prompt(query, doc)
                
                # Generate facts
                facts_text = await self._generate_facts(prompt)
                
                # Parse and structure facts
                facts = self._parse_extracted_facts(facts_text, f"document_{i}")
                extracted_facts.extend(facts)
                
            except Exception as e:
                logger.error(f"Error extracting from document {i}: {e}")
                continue
        
        return extracted_facts
    
    def _create_extraction_prompt(self, query: str, document: str) -> str:
        """Create specialized prompt for medical fact extraction"""
        # Categorize query type for specialized extraction
        query_lower = query.lower()
        
        if any(term in query_lower for term in ['dose', 'dosage', 'mg', 'ml']):
            extraction_type = "medication dosages and administration details"
        elif any(term in query_lower for term in ['protocol', 'procedure', 'steps']):
            extraction_type = "protocol steps and procedures"
        elif any(term in query_lower for term in ['contact', 'phone', 'pager', 'call']):
            extraction_type = "contact information and phone numbers"
        elif any(term in query_lower for term in ['criteria', 'score', 'threshold']):
            extraction_type = "clinical criteria and thresholds"
        else:
            extraction_type = "relevant medical information"
        
        prompt = f"""Extract {extraction_type} from the following medical document that answers this query: "{query}"

Document: {document[:2000]}

Instructions:
1. Extract only factual information directly from the document
2. Include exact dosages, phone numbers, and specific details
3. Preserve medical abbreviations and their expansions
4. Format as numbered facts
5. Include source citations

Extracted facts:"""
        
        return prompt
    
    async def _generate_facts(self, prompt: str) -> str:
        """Generate facts using T5 model"""
        try:
            # Tokenize input
            inputs = self.tokenizer.encode(
                prompt, 
                return_tensors="pt", 
                max_length=1024, 
                truncation=True
            ).to(self.device)
            
            # Generate with controlled parameters
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_length=512,
                    num_beams=4,
                    temperature=0.1,  # Low temperature for factual extraction
                    do_sample=False,
                    early_stopping=True,
                    pad_token_id=self.tokenizer.pad_token_id
                )
            
            # Decode response
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return generated_text
            
        except Exception as e:
            logger.error(f"T5 generation error: {e}")
            return ""
    
    def _parse_extracted_facts(self, facts_text: str, source: str) -> List[ExtractedFact]:
        """Parse T5 output into structured facts"""
        facts = []
        
        # Split by numbered facts
        lines = facts_text.split('\n')
        current_fact = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line starts with number (fact separator)
            if line[0].isdigit() and (line[1] == '.' or line[1] == ')'):
                # Save previous fact
                if current_fact:
                    fact = self._create_extracted_fact(current_fact, source)
                    if fact:
                        facts.append(fact)
                
                # Start new fact
                current_fact = line[2:].strip()
            else:
                # Continue current fact
                if current_fact:
                    current_fact += " " + line
        
        # Add final fact
        if current_fact:
            fact = self._create_extracted_fact(current_fact, source)
            if fact:
                facts.append(fact)
        
        return facts
    
    def _create_extracted_fact(self, fact_text: str, source: str) -> Optional[ExtractedFact]:
        """Create structured fact from text"""
        if len(fact_text) < 10:  # Skip very short facts
            return None
        
        # Categorize fact
        fact_lower = fact_text.lower()
        if any(term in fact_lower for term in ['mg', 'ml', 'dose', 'administer']):
            category = "dosage"
        elif any(term in fact_lower for term in ['phone', 'pager', 'contact', 'call']):
            category = "contact"
        elif any(term in fact_lower for term in ['step', 'procedure', 'protocol']):
            category = "protocol"
        elif any(term in fact_lower for term in ['criteria', 'score', 'threshold']):
            category = "criteria"
        else:
            category = "general"
        
        # Estimate confidence based on specificity
        confidence = 0.8  # Base confidence
        if any(char.isdigit() for char in fact_text):  # Contains numbers
            confidence += 0.1
        if len(fact_text) > 50:  # Detailed fact
            confidence += 0.05
        if any(term in fact_lower for term in ['mg', 'ml', 'minutes', 'hours']):  # Specific units
            confidence += 0.05
        
        confidence = min(confidence, 1.0)
        
        return ExtractedFact(
            fact=fact_text,
            source=source,
            confidence=confidence,
            category=category
        )


class HybridMedicalRAG:
    """Hybrid system combining encoder-decoder fact extraction with decoder-only generation"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Initialize components
        self.fact_extractor = MedicalFactExtractor("google/flan-t5-large")
        self.response_generator = AzureOpenAIClient(
            endpoint=self.settings.azure_openai_endpoint,
            api_key=self.settings.azure_openai_api_key,
            deployment=self.settings.azure_openai_deployment
        )
        
        # Cost tracking
        self.t5_compute_cost = 0.0001  # Estimated cost per inference
        self.azure_cost_per_token = 0.0001  # Azure OpenAI pricing
        
        logger.info("HybridMedicalRAG initialized")
    
    async def process_medical_query(
        self, 
        query: str, 
        documents: List[str],
        use_hybrid: bool = True
    ) -> HybridResponse:
        """Process medical query using hybrid approach"""
        start_time = time.time()
        cost_breakdown = {"t5_inference": 0.0, "azure_tokens": 0.0, "total": 0.0}
        
        try:
            if use_hybrid:
                # Phase 1: Extract facts with T5 (encoder-decoder)
                logger.info(f"🔍 Extracting facts with T5 for query: {query[:50]}...")
                extracted_facts = await self.fact_extractor.extract_medical_facts(query, documents)
                cost_breakdown["t5_inference"] = len(documents) * self.t5_compute_cost
                
                # Phase 2: Generate response with Azure OpenAI (decoder-only)
                logger.info(f"🤖 Generating response with Azure OpenAI...")
                response = await self._generate_hybrid_response(query, extracted_facts)
                
                # Estimate Azure costs (rough)
                estimated_tokens = len(response.split()) * 1.3  # Rough token estimate
                cost_breakdown["azure_tokens"] = estimated_tokens * self.azure_cost_per_token
                
                method_used = "hybrid_t5_azure"
                
            else:
                # Fallback to current Azure-only approach
                logger.info(f"🔄 Using Azure-only approach...")
                response = await self._generate_azure_only_response(query, documents)
                extracted_facts = []
                
                estimated_tokens = len(response.split()) * 1.3
                cost_breakdown["azure_tokens"] = estimated_tokens * self.azure_cost_per_token
                
                method_used = "azure_only"
            
            cost_breakdown["total"] = cost_breakdown["t5_inference"] + cost_breakdown["azure_tokens"]
            processing_time = time.time() - start_time
            
            # Extract sources
            sources = self._extract_sources(extracted_facts)
            
            # Calculate overall confidence
            confidence = self._calculate_overall_confidence(extracted_facts, response)
            
            return HybridResponse(
                response=response,
                extracted_facts=extracted_facts,
                sources=sources,
                confidence=confidence,
                processing_time=processing_time,
                method_used=method_used,
                cost_breakdown=cost_breakdown
            )
            
        except Exception as e:
            logger.error(f"Hybrid processing error: {e}")
            
            # Fallback to Azure-only
            response = await self._generate_azure_only_response(query, documents)
            processing_time = time.time() - start_time
            
            return HybridResponse(
                response=response,
                extracted_facts=[],
                sources=[],
                confidence=0.5,
                processing_time=processing_time,
                method_used="azure_fallback",
                cost_breakdown=cost_breakdown
            )
    
    async def _generate_hybrid_response(self, query: str, facts: List[ExtractedFact]) -> str:
        """Generate response using extracted facts and Azure OpenAI"""
        
        # Organize facts by category
        facts_by_category = {}
        for fact in facts:
            if fact.category not in facts_by_category:
                facts_by_category[fact.category] = []
            facts_by_category[fact.category].append(fact)
        
        # Create structured context from extracted facts
        structured_context = self._format_facts_for_prompt(facts_by_category)
        
        # Create hybrid prompt
        hybrid_prompt = f"""You are a medical AI assistant. Use the extracted facts below to answer the medical query accurately.

EXTRACTED MEDICAL FACTS:
{structured_context}

MEDICAL QUERY: {query}

INSTRUCTIONS:
1. Base your response ONLY on the extracted facts above
2. Preserve all citations and source references
3. Include specific dosages, phone numbers, and procedures exactly as extracted
4. If information is missing from facts, state "Not found in provided sources"
5. Maintain medical accuracy and include confidence indicators

RESPONSE:"""
        
        try:
            # Generate with Azure OpenAI
            response = await self.response_generator.generate_with_chat(
                messages=[{"role": "user", "content": hybrid_prompt}],
                temperature=0.0,  # Deterministic for medical accuracy
                max_tokens=800
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Azure response generation error: {e}")
            return f"Error generating response: {str(e)}"
    
    async def _generate_azure_only_response(self, query: str, documents: List[str]) -> str:
        """Generate response using only Azure OpenAI (current approach)"""
        
        # Combine documents for context
        context = "\n\n".join(documents[:3])[:3000]  # Limit context size
        
        azure_prompt = f"""You are a medical AI assistant. Answer the medical query using the provided context.

CONTEXT:
{context}

MEDICAL QUERY: {query}

RESPONSE:"""
        
        try:
            response = await self.response_generator.generate_with_chat(
                messages=[{"role": "user", "content": azure_prompt}],
                temperature=0.0,
                max_tokens=800
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Azure-only response error: {e}")
            return f"Error generating response: {str(e)}"
    
    def _format_facts_for_prompt(self, facts_by_category: Dict[str, List[ExtractedFact]]) -> str:
        """Format extracted facts for prompt"""
        formatted_sections = []
        
        for category, facts in facts_by_category.items():
            if not facts:
                continue
                
            section = f"\n{category.upper()} INFORMATION:\n"
            for i, fact in enumerate(facts, 1):
                section += f"{i}. {fact.fact} (Confidence: {fact.confidence:.2f}, Source: {fact.source})\n"
            
            formatted_sections.append(section)
        
        return "\n".join(formatted_sections)
    
    def _extract_sources(self, facts: List[ExtractedFact]) -> List[Dict[str, str]]:
        """Extract unique sources from facts"""
        sources = set()
        for fact in facts:
            sources.add(fact.source)
        
        return [{"display_name": source, "filename": source} for source in sources]
    
    def _calculate_overall_confidence(self, facts: List[ExtractedFact], response: str) -> float:
        """Calculate overall confidence score"""
        if not facts:
            return 0.6  # Default confidence for Azure-only
        
        # Average fact confidence
        avg_fact_confidence = sum(fact.confidence for fact in facts) / len(facts)
        
        # Response quality indicators
        response_quality = 0.7  # Base quality
        if "not found" in response.lower():
            response_quality += 0.1  # Bonus for acknowledging limitations
        if any(char.isdigit() for char in response):
            response_quality += 0.1  # Bonus for specific details
        
        overall_confidence = (avg_fact_confidence * 0.7) + (response_quality * 0.3)
        return min(overall_confidence, 1.0)


class HybridRAGTester:
    """Testing framework for hybrid RAG system"""
    
    def __init__(self):
        self.hybrid_rag = HybridMedicalRAG()
        self.test_queries = [
            {
                "query": "What is the STEMI protocol?",
                "expected_facts": ["protocol", "contact"],
                "documents": ["STEMI protocol document content..."]
            },
            {
                "query": "What is the dosage for epinephrine in anaphylaxis?",
                "expected_facts": ["dosage"],
                "documents": ["Anaphylaxis treatment guidelines..."]
            },
            {
                "query": "Who is on call for cardiology?",
                "expected_facts": ["contact"],
                "documents": ["Emergency contacts directory..."]
            }
        ]
    
    async def run_comparison_test(self) -> Dict[str, Any]:
        """Run A/B test comparing hybrid vs Azure-only"""
        results = {
            "hybrid_results": [],
            "azure_only_results": [],
            "performance_comparison": {},
            "cost_comparison": {}
        }
        
        for test_case in self.test_queries:
            query = test_case["query"]
            documents = test_case["documents"]
            
            # Test hybrid approach
            hybrid_result = await self.hybrid_rag.process_medical_query(
                query, documents, use_hybrid=True
            )
            results["hybrid_results"].append({
                "query": query,
                "response": hybrid_result.response,
                "facts_extracted": len(hybrid_result.extracted_facts),
                "confidence": hybrid_result.confidence,
                "processing_time": hybrid_result.processing_time,
                "cost": hybrid_result.cost_breakdown["total"]
            })
            
            # Test Azure-only approach
            azure_result = await self.hybrid_rag.process_medical_query(
                query, documents, use_hybrid=False
            )
            results["azure_only_results"].append({
                "query": query,
                "response": azure_result.response,
                "facts_extracted": 0,
                "confidence": azure_result.confidence,
                "processing_time": azure_result.processing_time,
                "cost": azure_result.cost_breakdown["total"]
            })
        
        # Calculate performance metrics
        results["performance_comparison"] = self._calculate_performance_metrics(
            results["hybrid_results"], 
            results["azure_only_results"]
        )
        
        return results
    
    def _calculate_performance_metrics(self, hybrid_results: List, azure_results: List) -> Dict:
        """Calculate performance comparison metrics"""
        hybrid_avg_confidence = sum(r["confidence"] for r in hybrid_results) / len(hybrid_results)
        azure_avg_confidence = sum(r["confidence"] for r in azure_results) / len(azure_results)
        
        hybrid_avg_time = sum(r["processing_time"] for r in hybrid_results) / len(hybrid_results)
        azure_avg_time = sum(r["processing_time"] for r in azure_results) / len(azure_results)
        
        hybrid_avg_cost = sum(r["cost"] for r in hybrid_results) / len(hybrid_results)
        azure_avg_cost = sum(r["cost"] for r in azure_results) / len(azure_results)
        
        return {
            "confidence_improvement": ((hybrid_avg_confidence - azure_avg_confidence) / azure_avg_confidence) * 100,
            "time_overhead": ((hybrid_avg_time - azure_avg_time) / azure_avg_time) * 100,
            "cost_increase": ((hybrid_avg_cost - azure_avg_cost) / azure_avg_cost) * 100,
            "hybrid_avg_confidence": hybrid_avg_confidence,
            "azure_avg_confidence": azure_avg_confidence,
            "hybrid_avg_time": hybrid_avg_time,
            "azure_avg_time": azure_avg_time,
            "hybrid_avg_cost": hybrid_avg_cost,
            "azure_avg_cost": azure_avg_cost
        }


# Example usage and testing
async def main():
    """Example usage of hybrid RAG system"""
    
    # Initialize hybrid system
    hybrid_rag = HybridMedicalRAG()
    
    # Example medical query
    query = "What is the STEMI protocol and who should I call?"
    documents = [
        "STEMI Activation Protocol: Call STEMI pager (917) 827-9725 immediately...",
        "Door-to-balloon time goal is 90 minutes. Contact Cath Lab x40935...",
    ]
    
    # Process with hybrid approach
    result = await hybrid_rag.process_medical_query(query, documents, use_hybrid=True)
    
    print(f"Query: {query}")
    print(f"Response: {result.response}")
    print(f"Facts extracted: {len(result.extracted_facts)}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Processing time: {result.processing_time:.2f}s")
    print(f"Total cost: ${result.cost_breakdown['total']:.4f}")
    print(f"Method: {result.method_used}")


if __name__ == "__main__":
    asyncio.run(main())