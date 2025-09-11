# PRP-41: Universal Curated-Quality Response System

## Problem Statement
**Critical Issue**: Only 10 curated queries return high-quality responses, while all other medical queries fall back to poor RAG retrieval quality. This creates an inconsistent user experience where 99% of queries feel inferior to the curated 1%.

**Current State:**
- ✅ Curated responses: Professional, concise, medically accurate (like STEMI protocol)
- ❌ Non-curated responses: Verbose, generic, often irrelevant content
- ❌ Production viability compromised - can't manually curate every medical query

## Success Criteria
1. **Universal Quality**: All medical queries feel like curated responses
2. **Consistent Format**: Structured, professional medical formatting across all responses
3. **Medical Accuracy**: Proper citations and confidence scoring for all responses
4. **Performance**: <2s response time for non-curated queries
5. **Scalability**: System works for any medical query without manual curation

## Technical Analysis

### Current Pipeline Issues:
1. **RAG Retrieval Quality**: Returns generic text chunks instead of focused medical content
2. **Response Formatting**: No standardized medical response structure
3. **Content Relevance**: Poor ranking of medical relevance vs semantic similarity
4. **LLM Prompting**: Generic prompts instead of medical-specific response generation
5. **Quality Validation**: No quality gates for non-curated responses

## Proposed Solution: 4-Layer Universal Quality System

### Layer 1: Enhanced Medical RAG Retrieval
**File**: `src/pipeline/enhanced_medical_retriever.py`
- Medical-context-aware semantic search
- Clinical relevance scoring beyond similarity
- Multi-document synthesis for comprehensive answers
- Medical abbreviation and terminology normalization

### Layer 2: Medical Response Templates
**File**: `src/pipeline/medical_response_formatter.py`
- Dynamic templates based on query type (Protocol, Criteria, Dosage, etc.)
- Structured medical formatting with emojis and headers
- Automatic citation integration
- Confidence scoring and warnings

### Layer 3: Medical-Specific LLM Prompting
**File**: `src/ai/medical_prompts.py`
- Query-type-specific prompts that mirror curated response quality
- Medical accuracy instructions and formatting requirements
- Context-aware response length and structure guidance
- Safety validation prompts

### Layer 4: Universal Quality Validation
**File**: `src/validation/universal_quality_validator.py`
- Real-time quality scoring for all responses
- Medical content validation (terminology, dosages, protocols)
- Automatic fallback to enhanced retrieval if quality < threshold
- Response refinement loops

## Implementation Strategy

### Phase 1: Enhanced Medical RAG (Core Foundation)
```python
class EnhancedMedicalRetriever:
    def retrieve_medical_context(self, query: str, query_type: QueryType) -> MedicalContext:
        # Medical-aware semantic search
        # Clinical relevance scoring
        # Multi-document synthesis
        # Return structured medical context
        
class MedicalContext:
    primary_content: str
    supporting_evidence: List[str]
    medical_terminology: Dict[str, str]
    confidence_indicators: List[str]
    source_citations: List[Source]
```

### Phase 2: Dynamic Medical Templates
```python
class MedicalResponseFormatter:
    def format_response(self, context: MedicalContext, query_type: QueryType) -> str:
        template = self.get_medical_template(query_type)
        return template.render(
            content=context.primary_content,
            sources=context.source_citations,
            medical_formatting=True
        )
```

### Phase 3: Medical LLM Prompting
```python
MEDICAL_PROMPTS = {
    QueryType.PROTOCOL_STEPS: """
    Generate a medical protocol response following this EXACT format:
    🚨 **[Protocol Name]**
    
    📊 **Key Criteria/Timing:**
    • [Critical information]
    
    💉 **Actions:**
    • [Step-by-step actions]
    
    ⚠️ **Critical Notes:**
    • [Safety considerations]
    
    Use provided context: {context}
    Sources: {sources}
    """
}
```

### Phase 4: Universal Quality Gates
```python
class UniversalQualityValidator:
    def validate_medical_response(self, response: str, query: str) -> QualityScore:
        scores = {
            'medical_accuracy': self._check_medical_accuracy(response),
            'format_consistency': self._check_format(response),
            'citation_quality': self._check_citations(response),
            'relevance_score': self._check_relevance(response, query)
        }
        return QualityScore(scores)
```

## Expected Outcomes

### Before (Current State):
```
Query: "what is the stroke protocol"
Response: "Based on the retrieved documents, stroke protocols typically involve... [generic 200-word response with poor formatting]"
Quality: 3/10
```

### After (Universal Quality):
```
Query: "what is the stroke protocol"
Response: 
🚨 **Stroke Protocol**

⏱️ **Time Critical:**
• EMS notification within 10 minutes
• CT scan within 25 minutes of arrival

🧠 **Assessment:**
• NIHSS score documentation
• Last known well time verification

💉 **Treatment:**
• tPA consideration if <4.5 hours
• Thrombectomy evaluation if indicated

⚠️ **Critical Contacts:**
• Stroke team: x2150
• Neurology on-call: [pager]
```
Quality: 9/10 (curated-level)

## Implementation Plan

### Week 1: Enhanced RAG Foundation
- Implement medical-context-aware retrieval
- Clinical relevance scoring system
- Multi-document synthesis capabilities

### Week 2: Response Templates & Formatting
- Create dynamic medical templates for all 6 query types
- Implement structured medical formatting
- Citation integration system

### Week 3: Medical LLM Prompting
- Develop query-type-specific medical prompts
- Implement context-aware response generation
- Safety validation integration

### Week 4: Quality Validation & Testing
- Universal quality validator implementation
- Comprehensive testing across medical domains
- Performance optimization and caching

## Success Metrics
- **Response Quality**: >8/10 average quality score across all medical queries
- **Consistency**: 95% of responses follow medical formatting standards
- **Performance**: <2s average response time for non-curated queries
- **Medical Accuracy**: 100% of responses include proper citations
- **User Experience**: All queries feel professionally curated

## Risk Mitigation
- **Fallback System**: Always fall back to curated responses when available
- **Quality Gates**: Automatic quality validation prevents poor responses
- **Medical Safety**: Multiple validation layers for medical accuracy
- **Performance**: Async processing and intelligent caching

This PRP transforms the entire RAG system to produce curated-quality responses universally, making every medical query feel professionally crafted without requiring manual curation.