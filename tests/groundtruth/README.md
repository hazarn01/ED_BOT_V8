# Groundtruth Testing System for ED Bot v8

This directory contains the comprehensive groundtruth testing system for validating medical response accuracy and detecting regressions.

## Files

### `groundtruth_dataset.json`
- **15 medical test cases** covering all query types
- Expected responses with critical values validation
- Confidence thresholds and performance metrics
- Regression test definitions for critical medical data

### `groundtruth_validator.py` 
- Validates API responses against groundtruth dataset
- Measures accuracy, confidence, and response times
- Generates detailed validation reports
- Exit codes for CI/CD integration

## Usage

### Basic Validation
```bash
# Run all groundtruth tests
python tests/groundtruth/groundtruth_validator.py

# Check specific test results
ls tests/groundtruth/groundtruth_report_*.json
```

### Integration with CI/CD
```bash
# Returns exit code 0 if ≥80% accuracy with no critical failures
python tests/groundtruth/groundtruth_validator.py
echo $?  # 0 = success, 1 = failure
```

### Understanding Results
- **Overall Accuracy**: Percentage of tests passed
- **Category Scores**: Accuracy by query type (PROTOCOL, DOSAGE, etc.)
- **Critical Failures**: Tests with incorrect vital medical information
- **Performance Issues**: Responses slower than 1.5 seconds

## Test Categories

### PROTOCOL (4 tests)
- STEMI activation protocol
- Sepsis treatment pathway
- Anaphylaxis management
- Hypoglycemia treatment

### DOSAGE (5 tests) 
- Levophed (norepinephrine) dosing
- Pediatric epinephrine dose
- Adult anaphylaxis epinephrine
- Heparin for STEMI
- Insulin drip protocol

### CRITERIA (3 tests)
- Sepsis lactate thresholds
- RETU chest pain criteria
- Stroke thrombolysis window

### CONTACT (1 test)
- Cardiology on-call information

### FORM (1 test)
- Blood transfusion form access

### SUMMARY (1 test)
- Protocol count queries

## Critical Values Validation

The system validates specific medical values that are critical for patient safety:

- **STEMI Pager**: (917) 827-9725
- **Pediatric Epi Dose**: 0.01 mg/kg
- **Sepsis Lactate**: > 2.0 mmol/L (severe), > 4.0 mmol/L (shock)
- **Door-to-Balloon Time**: 90 minutes
- **Adult Epi Dose**: 0.5mg IM

## Regression Detection

The system automatically detects regressions in:

1. **Medical Accuracy**: Phone numbers, dosages, timing
2. **Response Quality**: Confidence scores, completeness
3. **Performance**: Response times, availability
4. **Critical Failures**: Life-critical medical information

## Report Format

```json
{
  "timestamp": "2025-01-10T...",
  "total_tests": 15,
  "passed_tests": 14,
  "overall_accuracy": 0.933,
  "category_scores": {
    "PROTOCOL": 1.0,
    "DOSAGE": 0.8,
    "CRITERIA": 1.0
  },
  "critical_failures": [],
  "regression_issues": [],
  "performance_issues": []
}
```

## Quality Standards

- **Minimum Accuracy**: 80% overall
- **Critical Accuracy**: 95% for life-critical queries
- **Maximum Response Time**: 1500ms
- **Minimum Confidence**: 70%

## Continuous Integration

Add to your CI pipeline:

```yaml
- name: Validate Medical Accuracy
  run: |
    python tests/groundtruth/groundtruth_validator.py
    if [ $? -ne 0 ]; then
      echo "Medical accuracy validation failed!"
      exit 1
    fi
```

## Adding New Test Cases

1. Add test case to `groundtruth_dataset.json`
2. Include expected critical values
3. Set appropriate confidence thresholds
4. Run validation to verify

Example:
```json
{
  "id": "GT-016",
  "category": "DOSAGE",
  "query": "morphine dosing for chest pain",
  "expected_response": {
    "must_contain": ["morphine", "mg", "IV", "chest pain"],
    "critical_values": {
      "dose": "2-4mg IV",
      "frequency": "every 5-15 minutes"
    },
    "confidence_min": 0.85
  }
}
```

This groundtruth system ensures ED Bot v8 maintains medical accuracy standards and catches regressions before they reach production.