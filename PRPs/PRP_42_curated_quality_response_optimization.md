# PRP-42: Curated-Quality Response Optimization System

## Goal
Transform all ED Bot query responses to match the quality and format of curated ground truth examples, ensuring every response is a succinct, information-laden blurb that real ED providers can actually use in clinical practice.

## Why
- **Current Problem**: System generates generic, verbose responses that don't match clinical workflow needs
- **Ground Truth Gap**: We have 338 curated QA pairs with perfect clinical formatting, but system doesn't leverage this quality standard
- **Provider Experience**: ED staff need immediate, actionable information in standardized medical format
- **Quality Inconsistency**: Response quality varies wildly between query types and LLM backends

## What
Build a universal response quality system that:
1. **Analyzes ground truth patterns** to extract formatting templates
2. **Applies curated-style formatting** to all query responses
3. **Validates medical accuracy** against clinical standards
4. **Maintains consistent professional tone** with appropriate medical emojis and structure

### Success Criteria
- [ ] All 6 query types generate responses matching ground truth format quality
- [ ] Response length optimized for clinical use (150-400 words)
- [ ] 100% preservation of critical medical information (doses, contacts, timing)
- [ ] Professional medical formatting with consistent emoji usage
- [ ] Measurable improvement in provider satisfaction scores

## All Needed Context

### Documentation & References
```yaml
# Ground Truth Examples - CRITICAL PATTERNS
- file: ground_truth_qa/guidelines/anaphylaxis_guideline_qa.json
  why: Perfect example format - "Epinephrine 1mg/mL (1:1000) injection, 0.5mg IM"
  pattern: Concise, specific dosing with exact concentrations
  
- file: ground_truth_qa/protocols/STEMI_Activation_qa.json  
  why: Protocol format with contacts - "STEMI Pager: (917) 827-9725"
  pattern: Critical contacts prominently displayed with formatting
  
- file: ground_truth_qa/protocols/ED_sepsis_pathway_qa.json
  why: Time-critical protocols with clear steps
  pattern: Numbered workflows with timing requirements

# Current Response System Components  
- file: src/pipeline/curated_responses.py
  why: Existing curated response database with emoji formatting
  critical: Already has STEMI and epinephrine templates to expand on
  
- file: src/pipeline/medical_response_formatter.py
  why: Dynamic template system using Jinja2 - build on this
  pattern: Professional medical templates with structured formatting
  
- file: src/ai/medical_prompts.py
  why: Query-type specific prompts for curated-quality responses
  critical: Contains prompt generators for each QueryType

# LLM Integration (ONLY Llama 3.1 13B)
- file: src/ai/ollama_client.py
  why: Primary LLM backend - must optimize prompts for this model
  critical: Temperature=0 for medical consistency
  
- file: src/pipeline/query_processor.py
  why: Main orchestrator with Universal Quality System flag
  line: 48 - enable_universal_quality parameter controls new system
```

### Ground Truth Quality Patterns Discovered

**Medication Dosing Format:**
```
"Epinephrine 1mg/mL (1:1000) injection, 0.5mg IM"
"0.01mg/kg IM" (pediatric)
```

**Protocol Contact Format:**  
```
"STEMI Pager: (917) 827-9725"
"Cath Lab Direct: x40935"
```

**Clinical Criteria Format:**
```
"1. Acute onset illness with skin/mucosal involvement plus respiratory compromise
2. Acute onset hypotension/bronchospasm after known allergen exposure"
```

**Time-Critical Workflow:**
```
"⏱️ TIMING REQUIREMENTS:
• Door-to-balloon goal: 90 minutes
• EKG within 10 minutes of arrival"
```

## Implementation Blueprint

### Phase 1: Ground Truth Analysis Engine
```python
class GroundTruthAnalyzer:
    """Extract formatting patterns from 338 curated QA pairs."""
    
    def analyze_quality_patterns(self, ground_truth_dir: str) -> Dict[QueryType, FormatTemplate]:
        """Mine ground truth for optimal formatting patterns."""
        
    def extract_medical_templates(self, qa_pairs: List[Dict]) -> MedicalTemplate:
        """Convert ground truth examples into Jinja2 templates."""
```

### Phase 2: Enhanced Template System
```python  
class UniversalQualityFormatter:
    """Apply curated-quality formatting to any response."""
    
    def format_response(self, 
                       raw_response: str, 
                       query_type: QueryType,
                       medical_context: MedicalContext) -> CuratedResponse:
        """Transform any response to curated quality."""
```

### Phase 3: Llama 3.1 13B Optimization
```python
class CuratedQualityPrompts:
    """Prompts optimized for Llama 3.1 13B to generate curated-quality responses."""
    
    def get_curated_prompt(self, 
                          query_type: QueryType,
                          ground_truth_examples: List[str]) -> str:
        """Generate prompt with ground truth examples for consistent quality."""
```

## Task Implementation Order

### Task 1: Ground Truth Pattern Mining
```bash
# Create ground truth analyzer
python3 -c "
from scripts.analyze_ground_truth_patterns import GroundTruthAnalyzer
analyzer = GroundTruthAnalyzer('ground_truth_qa/')
patterns = analyzer.extract_all_patterns()
print(f'Extracted {len(patterns)} quality patterns')
"
```

### Task 2: Template System Enhancement  
```bash
# Test template generation
python3 -c "
from src.pipeline.enhanced_medical_formatter import EnhancedMedicalFormatter
formatter = EnhancedMedicalFormatter()
template = formatter.create_dosage_template(ground_truth_examples)
print('Template quality score:', template.quality_score)
"
```

### Task 3: Llama 3.1 13B Prompt Optimization
```bash  
# Test curated-quality prompt generation
python3 -c "
from src.ai.curated_quality_prompts import CuratedQualityPrompts
prompts = CuratedQualityPrompts()
prompt = prompts.get_protocol_prompt('STEMI protocol', ground_truth_examples)
print('Prompt length:', len(prompt), 'Ground truth examples:', prompt.count('Example:'))
"
```

### Task 4: Response Quality Validation
```bash
# Validate responses match ground truth quality
python3 -c "
from tests.test_curated_quality import test_response_quality_alignment
results = test_response_quality_alignment()
print(f'Quality alignment: {results.average_score:.2f}/10')
"
```

### Task 5: System Integration & Testing
```bash
# End-to-end quality test
python3 -c "
import requests
response = requests.post('http://localhost:8001/api/v1/query', 
                        json={'query': 'What is the first-line treatment for anaphylaxis in adults?'})
data = response.json()
print('Response format quality:', 'Epinephrine' in data['response'] and '0.5mg IM' in data['response'])
"
```

## Validation Gates (Executable)

### Code Quality
```bash
# Syntax and style validation
ruff check src/pipeline/curated_quality_*.py --fix
mypy src/pipeline/curated_quality_*.py
```

### Response Quality Testing
```bash
# Ground truth alignment testing
python3 -m pytest tests/test_curated_quality.py -v
python3 -m pytest tests/test_ground_truth_alignment.py -v

# Medical accuracy validation  
python3 -m pytest tests/test_medical_accuracy.py -v --cov=src/pipeline/curated_quality
```

### Clinical Validation
```bash
# Test all 6 query types against ground truth
python3 scripts/validate_curated_quality.py --ground-truth-dir ground_truth_qa/ --api-url http://localhost:8001
```

## Critical Implementation Notes

### Medical Safety Requirements
- **Never modify medical facts** - only improve formatting and presentation
- **Preserve exact dosages** from ground truth (e.g., "0.5mg IM", "0.01mg/kg")  
- **Maintain contact accuracy** - phone numbers must be exact from source documents
- **Keep timing requirements** precise (e.g., "Door-to-balloon goal: 90 minutes")

### Llama 3.1 13B Optimization
- **Temperature: 0.0** for medical consistency
- **Max tokens: 512** to match curated response length
- **System prompts** must include ground truth examples for pattern learning
- **Prompt engineering** critical - model needs explicit formatting instructions

### Ground Truth Integration
- **338 QA pairs** provide quality benchmark across all medical domains
- **Format consistency** extracted from anaphylaxis, STEMI, sepsis examples
- **Professional tone** with appropriate medical emoji usage (🚨 💉 ⏱️ 📞)
- **Clinical workflow optimization** - responses must fit ED provider needs

---

**PRP Confidence Score: 9/10**

**Rationale**: High confidence due to:
- ✅ Comprehensive ground truth examples already available (338 QA pairs)
- ✅ Existing template system (medical_response_formatter.py) to build on
- ✅ Clear quality patterns identified in research
- ✅ Llama 3.1 13B integration already working
- ✅ Executable validation gates provided
- ⚠️ Only risk: LLM prompt optimization may require iteration for optimal results

**Expected Outcome**: One-pass implementation with ground truth-quality responses for all query types, dramatically improving provider experience and clinical utility.
