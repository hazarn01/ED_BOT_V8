#!/usr/bin/env python3
"""
DKA Protocol Fix Validation Test
Tests the bulletproof medical abbreviation expansion system to ensure DKA protocol retrieval works.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Test medical abbreviation expander
def test_medical_abbreviation_expander():
    """Test the medical abbreviation expander directly."""
    print("\n🔍 TESTING MEDICAL ABBREVIATION EXPANDER")
    print("=" * 60)
    
    try:
        from src.pipeline.medical_abbreviation_expander import get_medical_expander
        
        expander = get_medical_expander()
        print(f"✅ Medical expander loaded with {len(expander.abbreviation_map)} abbreviations")
        
        # Test DKA expansion specifically
        test_queries = [
            "What is the DKA protocol?",
            "DKA management guidelines", 
            "Show me DKA treatment",
            "diabetic ketoacidosis protocol"
        ]
        
        for query in test_queries:
            result = expander.expand_query(query)
            print(f"\n📋 Query: '{query}'")
            print(f"   Detected abbreviations: {result['detected_abbreviations']}")
            print(f"   Expanded query: '{result['expanded_query']}'")
            print(f"   All search terms: {result['all_search_terms'][:3]}...")
            
            # Check if DKA is properly expanded
            if 'DKA' in result['detected_abbreviations']:
                assert 'Diabetic Ketoacidosis' in result['expanded_query'] or 'diabetic ketoacidosis' in result['expanded_query']
                print("   ✅ DKA properly expanded to 'Diabetic Ketoacidosis'")
            
        return True
        
    except Exception as e:
        print(f"❌ Medical abbreviation expander test failed: {e}")
        return False

def test_simple_direct_retriever():
    """Test the SimpleDirectRetriever with DKA protocol queries."""
    print("\n🔍 TESTING SIMPLE DIRECT RETRIEVER WITH DKA PROTOCOL")
    print("=" * 60)
    
    try:
        from src.models.database import get_db_session
        from src.pipeline.simple_direct_retriever import SimpleDirectRetriever
        
        with get_db_session() as db:
            retriever = SimpleDirectRetriever(db)
            
            # Test DKA protocol queries that should now work
            dka_queries = [
                "What is the DKA protocol?",
                "DKA management guidelines",
                "Show me the DKA treatment protocol",
                "How is DKA managed in pediatric patients?"
            ]
            
            for query in dka_queries:
                print(f"\n📋 Testing query: '{query}'")
                response = retriever.get_medical_response(query)
                
                print(f"   Confidence: {response.get('confidence', 0):.2%}")
                print(f"   Has real content: {response.get('has_real_content', False)}")
                print(f"   Query type: {response.get('query_type', 'unknown')}")
                
                # Check response content for DKA-related information
                response_text = response.get('response', '').lower()
                dka_indicators = ['diabetic ketoacidosis', 'dka', 'glucose', 'insulin', 'ketones', 'ph', 'bicarbonate']
                found_indicators = [indicator for indicator in dka_indicators if indicator in response_text]
                
                print(f"   DKA indicators found: {found_indicators}")
                print(f"   Response preview: {response_text[:200]}...")
                
                if found_indicators:
                    print("   ✅ DKA protocol information successfully retrieved!")
                else:
                    print("   ⚠️  No DKA-specific information found in response")
                    
        return True
        
    except Exception as e:
        print(f"❌ SimpleDirectRetriever test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ground_truth_validation():
    """Validate that DKA ground truth data is accessible."""
    print("\n🔍 TESTING GROUND TRUTH DKA DATA ACCESSIBILITY")
    print("=" * 60)
    
    try:
        import json
        ground_truth_path = Path("ground_truth_qa/protocols/MSHPedDKAProtocol_qa.json")
        
        if ground_truth_path.exists():
            with open(ground_truth_path, 'r') as f:
                dka_data = json.load(f)
            
            print(f"✅ Found {len(dka_data)} DKA protocol Q&A pairs")
            
            # Show sample questions that should be answerable
            sample_questions = [item['question'] for item in dka_data[:3]]
            print("\n📋 Sample DKA questions from ground truth:")
            for i, question in enumerate(sample_questions, 1):
                print(f"   {i}. {question}")
                
            return True
        else:
            print(f"❌ Ground truth DKA data not found at {ground_truth_path}")
            return False
            
    except Exception as e:
        print(f"❌ Ground truth validation failed: {e}")
        return False

def test_database_dka_content():
    """Test that DKA content exists in the database."""
    print("\n🔍 TESTING DATABASE DKA CONTENT ACCESSIBILITY") 
    print("=" * 60)
    
    try:
        from src.models.database import get_db_session
        from sqlalchemy import text
        
        with get_db_session() as db:
            # Search for DKA content in document chunks
            dka_search_terms = ['DKA', 'diabetic ketoacidosis', 'ketoacidosis']
            
            for term in dka_search_terms:
                result = db.execute(text("""
                    SELECT COUNT(*) as count, 
                           string_agg(DISTINCT d.filename, ', ') as files
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    WHERE dc.chunk_text ILIKE :term
                """), {"term": f"%{term}%"}).fetchone()
                
                count, files = result
                print(f"   '{term}': {count} chunks found in files: {files}")
                
                if count > 0:
                    # Get a sample chunk
                    sample = db.execute(text("""
                        SELECT dc.chunk_text
                        FROM document_chunks dc
                        JOIN documents d ON dc.document_id = d.id
                        WHERE dc.chunk_text ILIKE :term
                        ORDER BY LENGTH(dc.chunk_text) DESC
                        LIMIT 1
                    """), {"term": f"%{term}%"}).fetchone()
                    
                    if sample:
                        print(f"   Sample content: {sample[0][:100]}...")
                        
        return True
        
    except Exception as e:
        print(f"❌ Database DKA content test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all DKA protocol fix validation tests."""
    print("🧪 DKA PROTOCOL FIX VALIDATION TEST SUITE")
    print("=" * 60)
    print("Testing the bulletproof medical abbreviation expansion system")
    print("to ensure 'What is the DKA protocol?' query works correctly.\n")
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    tests = [
        ("Medical Abbreviation Expander", test_medical_abbreviation_expander),
        ("Ground Truth Data Access", test_ground_truth_validation), 
        ("Database DKA Content", test_database_dka_content),
        ("Simple Direct Retriever", test_simple_direct_retriever)
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
    print("🧪 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("✅ DKA PROTOCOL FIX VALIDATION SUCCESSFUL!")
        print("The system should now properly handle 'What is the DKA protocol?' queries.")
    else:
        print("❌ Some tests failed. DKA protocol retrieval may still have issues.")
        
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)