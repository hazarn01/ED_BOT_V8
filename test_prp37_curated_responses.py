#!/usr/bin/env python3
"""
PRP-37 Curated Response Testing Script
Tests the new curated medical database for guaranteed accuracy.
"""

import sys
import time

from src.pipeline.curated_responses import curated_db


def test_curated_responses():
    """Test all critical medical queries from PRP-37."""
    
    print("🔍 PRP-37: Testing Curated Medical Response Database")
    print("=" * 60)
    
    # Test queries from PRP-37 that must return correct information
    critical_tests = [
        {
            "query": "what is the STEMI protocol",
            "expected_contacts": ["917-827-9725", "x40935"],
            "description": "STEMI protocol with critical contact numbers"
        },
        {
            "query": "epinephrine dose cardiac arrest",
            "expected_content": ["1mg IV/IO", "3-5 minutes"],
            "description": "Epinephrine dosing for cardiac arrest"
        },
        {
            "query": "Ottawa ankle rules",
            "expected_content": ["malleolar zone", "midfoot zone", "bear weight"],
            "description": "Ottawa ankle rule criteria"
        },
        {
            "query": "sepsis criteria severe",
            "expected_content": ["Lactate > 2", "Lactate > 4"],
            "description": "Sepsis severity criteria"
        },
        {
            "query": "hypoglycemia treatment",
            "expected_content": ["50mL", "D50", "glucagon"],
            "description": "Hypoglycemia treatment protocol"
        },
        {
            "query": "anaphylaxis first line treatment",
            "expected_content": ["0.3mg", "epinephrine", "IM"],
            "description": "Anaphylaxis first-line treatment"
        },
        {
            "query": "blood transfusion form",
            "expected_content": ["consent", "BT-001"],
            "description": "Blood transfusion documentation"
        },
        {
            "query": "who is on call for cardiology",
            "expected_content": ["917-555-0198", "Cardiology Fellow"],
            "description": "Cardiology on-call contacts"
        }
    ]
    
    total_tests = len(critical_tests)
    passed_tests = 0
    failed_tests = []
    
    for i, test in enumerate(critical_tests, 1):
        print(f"\n🧪 Test {i}/{total_tests}: {test['description']}")
        print(f"Query: '{test['query']}'")
        
        # Test the curated database matching
        start_time = time.time()
        match_result = curated_db.find_curated_response(test['query'], threshold=0.6)
        response_time = time.time() - start_time
        
        if match_result:
            curated_response, match_score = match_result
            print(f"✅ Match found! Score: {match_score:.1%} | Time: {response_time*1000:.1f}ms")
            
            # Check if expected content is present
            response_text = curated_response.response.lower()
            
            if 'expected_contacts' in test:
                # More flexible contact matching - check if numbers exist (ignoring all formatting)
                response_text = curated_response.response
                contacts_found = all(
                    contact.replace('(', '').replace(')', '').replace('-', '').replace(' ', '') in 
                    response_text.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
                    for contact in test['expected_contacts']
                )
                if contacts_found:
                    print(f"✅ All expected contacts found: {test['expected_contacts']}")
                    passed_tests += 1
                else:
                    missing_contacts = []
                    for contact in test['expected_contacts']:
                        clean_contact = contact.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
                        clean_response = response_text.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
                        if clean_contact not in clean_response:
                            missing_contacts.append(contact)
                    print(f"❌ Missing expected contacts: {missing_contacts}")
                    failed_tests.append(test['query'])
                    
            elif 'expected_content' in test:
                content_found = all(content.lower() in response_text for content in test['expected_content'])
                if content_found:
                    print(f"✅ All expected content found: {test['expected_content']}")
                    passed_tests += 1
                else:
                    missing = [c for c in test['expected_content'] if c.lower() not in response_text]
                    print(f"❌ Missing expected content: {missing}")
                    failed_tests.append(test['query'])
            
            # Show confidence and sources
            print(f"📊 Confidence: {curated_response.confidence}")
            print(f"📚 Sources: {', '.join(curated_response.sources)}")
            
        else:
            print("❌ No curated match found (threshold 0.6)")
            failed_tests.append(test['query'])
    
    print("\n" + "=" * 60)
    print(f"🎯 TEST RESULTS: {passed_tests}/{total_tests} tests passed")
    print(f"✅ Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests:
        print("❌ Failed queries:")
        for query in failed_tests:
            print(f"   - {query}")
    else:
        print("🎉 ALL TESTS PASSED! PRP-37 curated responses working correctly.")
    
    # Test fuzzy matching capability
    print("\n🔍 Testing fuzzy matching...")
    fuzzy_tests = [
        "STEMI contacts",
        "epi dose",
        "ankle fracture rules",
        "severe sepsis lactate"
    ]
    
    fuzzy_passed = 0
    for query in fuzzy_tests:
        match = curated_db.find_curated_response(query, threshold=0.5)
        if match:
            fuzzy_passed += 1
            print(f"✅ '{query}' → matched with score {match[1]:.1%}")
        else:
            print(f"❌ '{query}' → no match")
    
    print(f"📊 Fuzzy matching: {fuzzy_passed}/{len(fuzzy_tests)} successful")
    
    # Show all available curated queries
    print(f"\n📋 All {len(curated_db.responses)} curated queries:")
    for response in curated_db.responses:
        print(f"   - {response.query} ({response.query_type})")
    
    return passed_tests == total_tests and fuzzy_passed >= len(fuzzy_tests) // 2


if __name__ == "__main__":
    success = test_curated_responses()
    sys.exit(0 if success else 1)