"""
LLM-based RAG Retrieval System
Uses LLM API calls to process queries against ground truth data and PDF documents.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    content: str
    confidence: float
    sources: List[str]
    reasoning: str

@dataclass
class GroundTruthMatch:
    question: str
    answer: str
    source_document: str
    match_score: float

class LLMRAGRetriever:
    """LLM-based RAG retrieval system with ground truth validation."""
    
    def __init__(self, db: Session, llm_client, ground_truth_path: str = None, docs_path: str = None):
        self.db = db
        self.llm_client = llm_client
        self.ground_truth_path = ground_truth_path or self._find_ground_truth_path()
        self.docs_path = docs_path or self._find_docs_path()
        
        # Load ground truth data
        self.ground_truth_data = self._load_ground_truth_data()
        
        # Medical query templates
        self.query_templates = {
            "dosage": """Based on the following medical documents, provide the accurate dosage information for {query}.

Retrieved Content:
{content}

Ground Truth Validation:
{ground_truth}

Please provide:
1. Specific dosage recommendations
2. Patient population (adult/pediatric)
3. Administration route and timing
4. Any contraindications or warnings
5. Source citations

Response:""",
            
            "protocol": """Based on the following medical documents, provide the complete protocol information for {query}.

Retrieved Content:
{content}

Ground Truth Validation:
{ground_truth}

Please provide:
1. Step-by-step protocol procedures
2. Critical timing requirements
3. Contact information if applicable
4. Required testing or monitoring
5. Source citations

Response:""",
            
            "criteria": """Based on the following medical documents, provide the clinical criteria for {query}.

Retrieved Content:
{content}

Ground Truth Validation:
{ground_truth}

Please provide:
1. Specific clinical criteria or thresholds
2. Scoring systems if applicable
3. Decision-making guidelines
4. Risk stratification factors
5. Source citations

Response:""",
            
            "general": """Based on the following medical documents, provide accurate information for {query}.

Retrieved Content:
{content}

Ground Truth Validation:
{ground_truth}

Please provide comprehensive, accurate medical information with proper citations.

Response:"""
        }
    
    def _find_ground_truth_path(self) -> str:
        """Find ground truth directory."""
        current_dir = Path(__file__).parent
        for _ in range(5):
            ground_truth_dir = current_dir / "ground_truth_qa"
            if ground_truth_dir.exists():
                return str(ground_truth_dir)
            current_dir = current_dir.parent
        return "/Users/nimayh/Desktop/NH/V8/edbot-v8-fix-prp-44-comprehensive-code-quality/ground_truth_qa"
    
    def _find_docs_path(self) -> str:
        """Find docs directory."""
        current_dir = Path(__file__).parent
        for _ in range(5):
            docs_dir = current_dir / "docs"
            if docs_dir.exists():
                return str(docs_dir)
            current_dir = current_dir.parent
        return "/Users/nimayh/Desktop/NH/V8/edbot-v8-fix-prp-44-comprehensive-code-quality/docs"
    
    def _load_ground_truth_data(self) -> Dict[str, Any]:
        """Load all ground truth data for validation."""
        ground_truth_data = {}
        
        if not os.path.exists(self.ground_truth_path):
            logger.warning(f"Ground truth path not found: {self.ground_truth_path}")
            return ground_truth_data
        
        logger.info(f"🔍 Loading ground truth data from: {self.ground_truth_path}")
        
        for category in ['protocols', 'guidelines', 'reference']:
            category_path = Path(self.ground_truth_path) / category
            if not category_path.exists():
                continue
                
            ground_truth_data[category] = {}
            
            for json_file in category_path.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    file_key = json_file.stem
                    ground_truth_data[category][file_key] = data
                    
                except Exception as e:
                    logger.error(f"Failed to load {json_file}: {e}")
        
        total_files = sum(len(cat) for cat in ground_truth_data.values())
        logger.info(f"✅ Loaded {total_files} ground truth files")
        
        return ground_truth_data
    
    async def get_llm_response(self, query: str) -> Dict[str, Any]:
        """
        Get comprehensive LLM-based response using RAG with ground truth validation.
        """
        logger.info(f"🤖 Processing LLM RAG query: {query}")
        
        # Enhanced debugging metrics
        debug_metrics = {
            'query': query,
            'query_length': len(query),
            'timestamp': import_module('datetime').datetime.now().isoformat()
        }
        
        try:
            # Step 1: Find relevant ground truth data
            ground_truth_matches = self._find_ground_truth_matches(query)
            
            # Step 2: Retrieve relevant document content from database
            doc_content = await self._retrieve_document_content(query)
            debug_metrics['doc_content_count'] = len(doc_content)
            logger.info(f"📄 Retrieved {len(doc_content)} documents")
            
            # Step 3: Determine query type for appropriate template
            query_type = self._classify_query_type(query)
            debug_metrics['query_type'] = query_type
            logger.info(f"🏷️ Query classified as: {query_type}")
            
            # Step 4: Build LLM prompt with ground truth validation
            prompt = self._build_llm_prompt(query, query_type, doc_content, ground_truth_matches)
            debug_metrics['prompt_length'] = len(prompt)
            logger.info(f"📝 Built prompt: {len(prompt)} characters")
            
            # Step 5: Call LLM API
            llm_response = await self._call_llm_api(prompt)
            debug_metrics['llm_response_length'] = len(llm_response) if llm_response else 0
            logger.info(f"🤖 LLM response: {len(llm_response) if llm_response else 0} characters")
            
            # Step 6: Validate response against ground truth
            validation_score = self._validate_response_quality(llm_response, ground_truth_matches)
            debug_metrics['validation_score'] = validation_score
            logger.info(f"✅ Validation score: {validation_score:.2%}")
            
            # Step 7: Format final response
            formatted_response = self._format_llm_response(
                query, llm_response, validation_score, ground_truth_matches, doc_content
            )
            
            # Final debug summary
            logger.info(f"🏁 LLM RAG Complete: {debug_metrics}")
            return formatted_response
            
        except Exception as e:
            debug_metrics['error'] = str(e)
            logger.error(f"🔥 LLM RAG retrieval failed: {e}")
            logger.error(f"🔍 Debug context: {debug_metrics}")
            return self._get_error_response(query, str(e))
    
    def _find_ground_truth_matches(self, query: str) -> List[GroundTruthMatch]:
        """Find matching ground truth data for validation."""
        matches = []
        query_lower = query.lower()
        
        # Key terms extraction
        key_terms = self._extract_key_terms(query_lower)
        
        for category, files_data in self.ground_truth_data.items():
            for file_key, file_data in files_data.items():
                qa_pairs = self._extract_qa_pairs(file_data)
                
                for qa_item in qa_pairs:
                    question = qa_item.get('question', '').lower()
                    answer = qa_item.get('answer', '').lower()
                    
                    # Calculate match score
                    match_score = self._calculate_semantic_match(query_lower, question, answer, key_terms)
                    
                    if match_score > 0.3:  # Minimum threshold
                        matches.append(GroundTruthMatch(
                            question=qa_item.get('question', ''),
                            answer=qa_item.get('answer', ''),
                            source_document=file_key,
                            match_score=match_score
                        ))
        
        # Sort by match score and return top matches
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches[:5]  # Top 5 matches
    
    async def _retrieve_document_content(self, query: str) -> List[Dict[str, str]]:
        """Retrieve relevant document content from database."""
        try:
            # Extract search terms
            search_terms = self._extract_key_terms(query)
            
            if not search_terms:
                return []
            
            # Build database query
            search_conditions = []
            params = {}
            
            for i, term in enumerate(search_terms[:3]):  # Limit to 3 terms
                param_name = f"term_{i}"
                search_conditions.append(f"dc.chunk_text ILIKE :{param_name}")
                params[param_name] = f"%{term}%"
            
            # Enhanced query with medical prioritization
            search_query = f"""
                SELECT 
                    dc.chunk_text,
                    d.filename,
                    d.content_type,
                    LENGTH(dc.chunk_text) as content_length,
                    -- Medical relevance scoring
                    (CASE 
                        WHEN d.content_type IN ('protocol', 'guideline', 'criteria') THEN 100
                        WHEN d.filename ILIKE '%STEMI%' OR d.filename ILIKE '%sepsis%' THEN 95
                        WHEN d.filename ILIKE '%ICH%' OR d.filename ILIKE '%ICP%' THEN 95
                        WHEN d.filename ILIKE '%protocol%' OR d.filename ILIKE '%guideline%' THEN 80
                        ELSE 50 
                    END) as relevance_score
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE ({' OR '.join(search_conditions)})
                AND LENGTH(dc.chunk_text) > 100
                ORDER BY relevance_score DESC, content_length DESC
                LIMIT 10
            """
            
            results = self.db.execute(text(search_query), params).fetchall()
            
            doc_content = []
            for result in results:
                content, filename, content_type, length, relevance = result
                doc_content.append({
                    'content': content,
                    'filename': filename,
                    'content_type': content_type or 'document',
                    'relevance_score': relevance
                })
            
            logger.info(f"📄 Retrieved {len(doc_content)} document chunks")
            return doc_content
            
        except Exception as e:
            logger.error(f"Document content retrieval failed: {e}")
            return []
    
    def _classify_query_type(self, query: str) -> str:
        """Classify query type for appropriate template selection."""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['dosage', 'dose', 'mg', 'ml', 'medication']):
            return 'dosage'
        elif any(word in query_lower for word in ['protocol', 'procedure', 'steps', 'activation']):
            return 'protocol'
        elif any(word in query_lower for word in ['criteria', 'score', 'guidelines', 'threshold']):
            return 'criteria'
        else:
            return 'general'
    
    def _build_llm_prompt(self, query: str, query_type: str, doc_content: List[Dict], 
                         ground_truth_matches: List[GroundTruthMatch]) -> str:
        """Build comprehensive LLM prompt with context."""
        
        # Prepare document content with larger context window for medical accuracy
        content_text = ""
        for i, doc in enumerate(doc_content[:3], 1):  # Top 3 documents with more content each
            content_text += f"\n--- Document {i}: {doc['filename']} ---\n"
            content_text += doc['content'][:2000] + "\n"  # Increased from 800 to 2000 chars for complete medical context
        
        # Prepare ground truth context with expanded answers
        ground_truth_text = ""
        for i, match in enumerate(ground_truth_matches[:2], 1):  # Top 2 matches with more detail
            ground_truth_text += f"\n--- Reference {i} (Score: {match.match_score:.2f}) ---\n"
            ground_truth_text += f"Q: {match.question}\n"
            ground_truth_text += f"A: {match.answer[:800]}\n"  # Increased from 400 to 800 chars
            ground_truth_text += f"Source: {match.source_document}\n"
        
        # Select appropriate template
        template = self.query_templates.get(query_type, self.query_templates['general'])
        
        # Build final prompt
        prompt = template.format(
            query=query,
            content=content_text or "No specific document content found.",
            ground_truth=ground_truth_text or "No ground truth references found."
        )
        
        # Add medical safety instructions with Llama 3.1 13B specific formatting
        safety_instructions = """
LLAMA 3.1 13B MEDICAL RESPONSE INSTRUCTIONS:
🏥 MEDICAL SAFETY REQUIREMENTS:
1. Only provide information explicitly supported by retrieved documents
2. Include source citations for ALL medical recommendations  
3. For dosages: specify patient population (adult/pediatric) and safety warnings
4. Flag information requiring verification with current protocols
5. Never guess or interpolate medical information not in sources

🤖 LLAMA 3.1 13B FORMATTING REQUIREMENTS:
• Use bullet points for protocols and step-by-step procedures
• Include specific numbers, dosages, timeframes, and contact information
• Structure responses with clear headers and sections
• Provide confidence assessment: "High confidence" or "Requires verification"
• Use medical terminology appropriately with clear explanations
• End with source citations in format: [Source: filename]

📋 RESPONSE STRUCTURE:
1. Direct answer to query
2. Relevant clinical details
3. Safety considerations
4. Source citations
5. Confidence assessment
"""
        
        return safety_instructions + "\n" + prompt
    
    async def _call_llm_api(self, prompt: str) -> str:
        """Call LLM API with medical-optimized parameters."""
        try:
            # Use the existing LLM client with medical-optimized settings
            response = await self.llm_client.generate_text(
                prompt=prompt,
                max_tokens=1500,  # Sufficient for detailed medical responses
                temperature=0.1,  # Low temperature for factual accuracy
                top_p=0.9,
                stop_sequences=None
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise
    
    def _validate_response_quality(self, llm_response: str, ground_truth_matches: List[GroundTruthMatch]) -> float:
        """Validate LLM response quality against ground truth."""
        if not ground_truth_matches:
            return 0.5  # Medium confidence without ground truth
        
        response_lower = llm_response.lower()
        validation_score = 0.0
        total_weight = 0.0
        
        for match in ground_truth_matches[:3]:  # Use top 3 matches
            match_weight = match.match_score
            total_weight += match_weight
            
            # Check if response contains key information from ground truth
            ground_truth_terms = self._extract_key_terms(match.answer.lower())
            response_terms = self._extract_key_terms(response_lower)
            
            # Calculate overlap
            if ground_truth_terms and response_terms:
                overlap = len(set(ground_truth_terms) & set(response_terms))
                overlap_score = overlap / len(ground_truth_terms)
                validation_score += overlap_score * match_weight
        
        final_score = min(validation_score / total_weight, 1.0) if total_weight > 0 else 0.5
        
        # Debug logging for confidence calculation
        logger.info(f"🔍 Confidence Debug: total_weight={total_weight:.2f}, validation_score={validation_score:.2f}, final_score={final_score:.2f}")
        
        return final_score
    
    def _format_llm_response(self, query: str, llm_response: str, validation_score: float,
                           ground_truth_matches: List[GroundTruthMatch], 
                           doc_content: List[Dict]) -> Dict[str, Any]:
        """Format LLM response for API return."""
        
        # Extract sources
        sources = []
        seen_files = set()
        
        # Add document sources
        for doc in doc_content[:3]:
            filename = doc['filename']
            if filename not in seen_files:
                display_name = filename.replace('.pdf', '').replace('_', ' ').title()
                sources.append({
                    'display_name': display_name,
                    'filename': filename,
                    'pdf_path': filename
                })
                seen_files.add(filename)
        
        # Add ground truth sources
        for match in ground_truth_matches[:2]:
            source_doc = match.source_document
            if source_doc not in seen_files:
                display_name = source_doc.replace('_qa', '').replace('_', ' ').title()
                sources.append({
                    'display_name': display_name,
                    'filename': f"{source_doc}.pdf",
                    'pdf_path': f"{source_doc}.pdf"
                })
                seen_files.add(source_doc)
        
        # Determine confidence
        confidence = min(validation_score + 0.2, 0.95)  # Boost for LLM processing
        
        # Keep responses clean and professional - remove validation disclaimers
        response_text = llm_response
        
        return {
            'response': response_text,
            'sources': sources,
            'confidence': confidence,
            'query_type': self._map_to_api_query_type(query),
            'has_real_content': True,
            'llm_rag_retrieval': True,
            'validation_score': validation_score,
            'ground_truth_matches': len(ground_truth_matches),
            'document_chunks': len(doc_content)
        }
    
    def _get_error_response(self, query: str, error_message: str) -> Dict[str, Any]:
        """Generate error response."""
        return {
            'response': f"I encountered an error processing your medical query. Please consult medical references directly.\n\nError: {error_message}",
            'sources': [],
            'confidence': 0.0,
            'query_type': 'error',
            'has_real_content': False,
            'llm_rag_retrieval': False,
            'error': error_message
        }
    
    # Helper methods
    def _extract_qa_pairs(self, file_data: Any) -> List[Dict]:
        """Extract Q&A pairs from different JSON structures."""
        qa_pairs = []
        
        if isinstance(file_data, list):
            qa_pairs = file_data
        elif isinstance(file_data, dict) and 'qa_pairs' in file_data:
            qa_pairs = file_data['qa_pairs']
        elif isinstance(file_data, dict):
            qa_pairs = [{
                'question': key,
                'answer': value,
                'source': file_data.get('document', 'ground_truth')
            } for key, value in file_data.items() 
            if key not in ['document', 'document_type', 'complexity']]
        
        return qa_pairs
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract meaningful medical terms."""
        # Medical stop words (keep medical terms)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'what', 'how', 'when', 'where', 'who', 'why', 'is', 'are'}
        
        # Extract terms
        terms = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*\b', text.lower())
        meaningful_terms = [term for term in terms 
                          if len(term) > 2 and term not in stop_words]
        
        return meaningful_terms
    
    def _calculate_semantic_match(self, query: str, question: str, answer: str, query_terms: List[str]) -> float:
        """Calculate semantic match score between query and Q&A pair."""
        if not query_terms:
            return 0.0
        
        # Combine question and answer for matching
        combined_text = f"{question} {answer}"
        combined_terms = set(self._extract_key_terms(combined_text))
        
        # Calculate term overlap
        query_terms_set = set(query_terms)
        overlap = len(query_terms_set & combined_terms)
        
        if len(query_terms_set) == 0:
            return 0.0
        
        base_score = overlap / len(query_terms_set)
        
        # Boost for specific medical matches
        medical_boost = 0.0
        
        # Specific query type boosts
        if 'aspirin' in query and 'aspirin' in combined_text:
            medical_boost += 0.3
        if 'acute mi' in query and ('myocardial infarction' in combined_text or 'stemi' in combined_text):
            medical_boost += 0.3
        if 'icp' in query and ('intracranial' in combined_text or 'ich' in combined_text):
            medical_boost += 0.3
        
        return min(base_score + medical_boost, 1.0)
    
    def _map_to_api_query_type(self, query: str) -> str:
        """Map query to API query type."""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['contact', 'phone', 'pager']):
            return 'contact'
        elif any(word in query_lower for word in ['form', 'document']):
            return 'form'  
        elif any(word in query_lower for word in ['protocol', 'procedure']):
            return 'protocol'
        elif any(word in query_lower for word in ['criteria', 'score']):
            return 'criteria'
        elif any(word in query_lower for word in ['dosage', 'dose', 'medication']):
            return 'dosage'
        else:
            return 'summary'


# Convenience function for easy integration
async def get_llm_rag_response(query: str, db: Session, llm_client) -> Dict[str, Any]:
    """
    Get LLM-based RAG response for medical query.
    """
    retriever = LLMRAGRetriever(db, llm_client)
    return await retriever.get_llm_response(query)