#!/usr/bin/env python3
"""
Direct DKA Protocol Fix Test
Tests the medical abbreviation expansion in SimpleDirectRetriever directly.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_dka_abbreviation_expansion():
    """Test DKA abbreviation expansion directly."""
    print("🔍 TESTING DKA ABBREVIATION EXPANSION")
    print("=" * 60)
    
    try:
        from src.pipeline.medical_abbreviation_expander import get_medical_expander
        
        expander = get_medical_expander()
        print(f"✅ Medical expander initialized")
        
        # Test DKA expansion
        query = "What is the DKA protocol?"
        result = expander.expand_query(query)
        
        print(f"\nOriginal query: {result['original_query']}")
        print(f"Expanded query: {result['expanded_query']}")
        print(f"Detected abbreviations: {result['detected_abbreviations']}")
        print(f"All search terms: {result['all_search_terms']}")
        
        # Verify DKA was detected and expanded
        assert 'DKA' in result['detected_abbreviations'], "DKA not detected"
        assert 'diabetic ketoacidosis' in result['expanded_query'].lower(), "DKA not expanded"
        
        print("\n✅ DKA ABBREVIATION EXPANSION SUCCESSFUL!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_direct_retriever():
    """Test SimpleDirectRetriever with DKA query."""
    print("\n🔍 TESTING SIMPLE DIRECT RETRIEVER WITH DKA")
    print("=" * 60)
    
    try:
        from src.models.database import get_db_session
        from src.pipeline.simple_direct_retriever import SimpleDirectRetriever
        
        with get_db_session() as db:
            retriever = SimpleDirectRetriever(db)
            
            # Check if medical expander was initialized
            if retriever.medical_expander:
                print("✅ Medical abbreviation expander loaded in retriever")
            else:
                print("⚠️ Medical abbreviation expander NOT loaded")
                
            # Test DKA query
            query = "What is the DKA protocol?"
            print(f"\nTesting query: {query}")
            
            response = retriever.get_medical_response(query)
            
            print(f"Response confidence: {response.get('confidence', 0):.2%}")
            print(f"Has real content: {response.get('has_real_content', False)}")
            print(f"Query type: {response.get('query_type', 'unknown')}")
            
            # Check if response contains DKA-related content
            response_text = response.get('response', '').lower()
            dka_keywords = ['diabetic ketoacidosis', 'dka', 'glucose', 'insulin', 'ketone', 'ph']
            found_keywords = [kw for kw in dka_keywords if kw in response_text]
            
            print(f"DKA keywords found: {found_keywords}")
            print(f"Response preview: {response_text[:300]}...")
            
            if found_keywords:
                print("✅ DKA-RELATED CONTENT FOUND!")
            else:
                print("❌ No DKA-specific content found")
                
            return len(found_keywords) > 0
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run DKA direct tests."""
    print("🧪 DKA PROTOCOL FIX - DIRECT TESTING")
    print("=" * 60)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    tests = [
        ("DKA Abbreviation Expansion", test_dka_abbreviation_expansion),
        ("SimpleDirectRetriever DKA Query", test_simple_direct_retriever)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("🧪 DIRECT TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("✅ DKA PROTOCOL ABBREVIATION FIX IS WORKING!")
        print("The medical abbreviation expander successfully expands DKA → Diabetic Ketoacidosis")
    else:
        print("❌ DKA protocol fix needs additional work.")
        
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)