"""
Retrieval Quality Testing Framework - Validate actual document content retrieval
PRP-48: Ensure responses use real document content, not templates
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
import json
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from src.models.database import get_db_session
from src.pipeline.simple_direct_retriever import SimpleDirectRetriever

class RetrievalQualityTester:
    """Test retrieval quality against known documents."""
    
    def __init__(self):
        self.test_cases = self._load_test_cases()
        self.results = []
        
    def _load_test_cases(self) -> List[Dict]:
        """Load test cases based on actual documents we know exist."""
        return [
            {
                "query": "standard levophed dosing",
                "expected_document": "Standard IV Infusion - Norepinephrine (Levophed).pdf",
                "must_contain": ["norepinephrine", "mcg/min", "infusion", "dose"],
                "must_not_contain": ["tip sheet", "referral", "one epic"],
                "category": "medication"
            },
            {
                "query": "pediatric epinephrine dose",
                "expected_document": "Anaphylaxis_Guideline_Final_6_6_24.pdf",
                "must_contain": ["epinephrine", "0.01", "mg/kg", "pediatric"],
                "must_not_contain": ["tip sheet", "referral"],
                "category": "medication"
            },
            {
                "query": "blood transfusion consent form",
                "expected_document": "Blood_Transfusion_Consent_Form.pdf",
                "must_contain": ["consent", "blood", "transfusion"],
                "must_not_contain": ["tip sheet", "pathway"],
                "category": "form"
            },
            {
                "query": "STEMI activation protocol",
                "expected_document": "STEMI_Activation.pdf",
                "must_contain": ["STEMI", "cath lab", "door", "balloon", "90"],
                "must_not_contain": ["tip sheet"],
                "category": "protocol"
            },
            {
                "query": "sepsis lactate criteria",
                "expected_document": "ED_Sepsis_Pathway.pdf",
                "must_contain": ["sepsis", "lactate", "2", "4", "shock"],
                "must_not_contain": ["tip sheet"],
                "category": "criteria"
            },
            {
                "query": "RETU chest pain pathway",
                "expected_document": "RETU Chest Pain Pathway.pdf",
                "must_contain": ["RETU", "chest", "pain", "pathway"],
                "must_not_contain": ["tip sheet"],
                "category": "pathway"
            },
            {
                "query": "hypoglycemia treatment protocol",
                "expected_document": "Hypoglycemia_EBP_Final_10_2024.pdf",
                "must_contain": ["hypoglycemia", "glucose", "D50", "70"],
                "must_not_contain": ["tip sheet"],
                "category": "protocol"
            }
        ]
    
    def test_direct_database_retrieval(self, test_case: Dict) -> Dict:
        """Test if we can find the right document directly in database."""
        with get_db_session() as session:
            # Try exact document search
            exact_query = text("""
                SELECT d.filename, dc.chunk_text
                FROM documents d
                JOIN document_chunks dc ON d.id = dc.document_id
                WHERE d.filename = :filename
                ORDER BY LENGTH(dc.chunk_text) DESC
                LIMIT 1
            """)
            
            exact_result = session.execute(
                exact_query, 
                {"filename": test_case["expected_document"]}
            ).fetchone()
            
            # Try keyword search
            keyword_search = text("""
                SELECT d.filename, dc.chunk_text, COUNT(*) as matches
                FROM documents d
                JOIN document_chunks dc ON d.id = dc.document_id
                WHERE dc.chunk_text ILIKE :keyword1
                   OR dc.chunk_text ILIKE :keyword2
                GROUP BY d.filename, dc.chunk_text
                ORDER BY matches DESC, LENGTH(dc.chunk_text) DESC
                LIMIT 3
            """)
            
            keywords = test_case["query"].split()[:2]
            keyword_results = session.execute(
                keyword_search,
                {
                    "keyword1": f"%{keywords[0]}%",
                    "keyword2": f"%{keywords[1] if len(keywords) > 1 else keywords[0]}%"
                }
            ).fetchall()
            
            return {
                "exact_found": exact_result is not None,
                "exact_content": exact_result[1][:500] if exact_result else None,
                "keyword_matches": len(keyword_results),
                "keyword_files": [r[0] for r in keyword_results],
                "keyword_content": keyword_results[0][1][:500] if keyword_results else None
            }
    
    def test_simple_retriever(self, test_case: Dict) -> Dict:
        """Test the SimpleDirectRetriever response."""
        with get_db_session() as session:
            retriever = SimpleDirectRetriever(session)
            response = retriever.get_medical_response(test_case["query"])
            
            # Check response quality
            response_text = response.get("response", "").lower()
            sources = response.get("sources", [])
            
            # Validate content presence
            contains_required = all(
                term.lower() in response_text 
                for term in test_case["must_contain"]
            )
            
            contains_forbidden = any(
                term.lower() in response_text 
                for term in test_case["must_not_contain"]
            )
            
            # Check if correct document was used
            correct_document = any(
                test_case["expected_document"] in source.get("filename", "")
                for source in sources
            )
            
            # Check if response is template or real content
            is_template = any(phrase in response_text for phrase in [
                "available in epic",
                "at nursing station",
                "contact through operator",
                "most forms available"
            ])
            
            return {
                "response_length": len(response_text),
                "sources_count": len(sources),
                "source_files": [s.get("filename") for s in sources],
                "contains_required": contains_required,
                "contains_forbidden": contains_forbidden,
                "correct_document": correct_document,
                "is_template": is_template,
                "confidence": response.get("confidence", 0),
                "has_real_content": response.get("has_real_content", False)
            }
    
    def extract_actual_content(self, document_name: str) -> str:
        """Extract actual content from a specific document."""
        with get_db_session() as session:
            query = text("""
                SELECT dc.chunk_text
                FROM documents d
                JOIN document_chunks dc ON d.id = dc.document_id
                WHERE d.filename = :filename
                ORDER BY dc.chunk_index
            """)
            
            results = session.execute(query, {"filename": document_name}).fetchall()
            
            if results:
                # Combine chunks to get full content
                full_content = "\n".join(r[0] for r in results)
                return full_content
            return ""
    
    def run_all_tests(self) -> Dict:
        """Run all retrieval quality tests."""
        print("\n" + "=" * 80)
        print("🧪 RETRIEVAL QUALITY TESTING")
        print("=" * 80)
        
        for test_case in self.test_cases:
            print(f"\n📝 Testing: {test_case['query']}")
            print(f"   Expected: {test_case['expected_document']}")
            
            # Test direct database access
            db_result = self.test_direct_database_retrieval(test_case)
            print(f"   Database: {'✅ Found' if db_result['exact_found'] else '❌ Not found'}")
            if db_result['keyword_matches'] > 0:
                print(f"   Keyword matches: {db_result['keyword_matches']} documents")
                print(f"   Files: {db_result['keyword_files'][0]}")
            
            # Test retriever
            retriever_result = self.test_simple_retriever(test_case)
            
            # Determine pass/fail
            passed = (
                retriever_result['contains_required'] and
                not retriever_result['contains_forbidden'] and
                not retriever_result['is_template'] and
                retriever_result['has_real_content']
            )
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   Retriever: {status}")
            
            if not passed:
                print(f"     - Contains required terms: {retriever_result['contains_required']}")
                print(f"     - Avoids forbidden terms: {not retriever_result['contains_forbidden']}")
                print(f"     - Uses real content: {not retriever_result['is_template']}")
                print(f"     - Correct document: {retriever_result['correct_document']}")
                print(f"     - Sources: {retriever_result['source_files']}")
            
            # Store result
            self.results.append({
                "query": test_case["query"],
                "expected_document": test_case["expected_document"],
                "passed": passed,
                "db_result": db_result,
                "retriever_result": retriever_result
            })
        
        # Summary
        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        
        print("\n" + "=" * 80)
        print(f"📊 RESULTS: {passed_count}/{total_count} tests passed")
        print("=" * 80)
        
        # Detailed failure analysis
        if passed_count < total_count:
            print("\n⚠️ FAILURE ANALYSIS:")
            for result in self.results:
                if not result["passed"]:
                    print(f"\n❌ {result['query']}")
                    ret = result['retriever_result']
                    
                    if not ret['has_real_content']:
                        print("   Problem: No real content (using templates)")
                    if ret['is_template']:
                        print("   Problem: Template response detected")
                    if not ret['contains_required']:
                        print("   Problem: Missing required medical terms")
                    if ret['contains_forbidden']:
                        print("   Problem: Contains forbidden terms (wrong document)")
                    if not ret['correct_document']:
                        print(f"   Problem: Wrong document (got {ret['source_files']})")
        
        return {
            "passed": passed_count,
            "total": total_count,
            "percentage": (passed_count / total_count * 100) if total_count > 0 else 0,
            "results": self.results
        }
    
    def generate_fix_recommendations(self):
        """Generate specific recommendations based on test failures."""
        print("\n🔧 RECOMMENDED FIXES:")
        
        # Analyze failure patterns
        template_responses = sum(1 for r in self.results if r['retriever_result']['is_template'])
        wrong_documents = sum(1 for r in self.results if not r['retriever_result']['correct_document'])
        missing_content = sum(1 for r in self.results if not r['retriever_result']['has_real_content'])
        
        if template_responses > 0:
            print(f"\n1. TEMPLATE RESPONSES ({template_responses} cases):")
            print("   • SimpleDirectRetriever is returning hardcoded templates")
            print("   • FIX: Replace template responses with actual database content")
            print("   • Use extract_actual_content() method to get real text")
        
        if wrong_documents > 0:
            print(f"\n2. WRONG DOCUMENT RETRIEVAL ({wrong_documents} cases):")
            print("   • Search is not finding the most relevant document")
            print("   • FIX: Improve search query with better keyword matching")
            print("   • Consider document filename in relevance scoring")
        
        if missing_content > 0:
            print(f"\n3. MISSING REAL CONTENT ({missing_content} cases):")
            print("   • Response doesn't include actual document text")
            print("   • FIX: Extract and return actual chunk_text from database")
            print("   • Stop using placeholder text")

def main():
    """Run retrieval quality tests."""
    tester = RetrievalQualityTester()
    results = tester.run_all_tests()
    tester.generate_fix_recommendations()
    
    # Save results
    with open('retrieval_quality_report.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n📄 Full report saved to retrieval_quality_report.json")
    
    return results

if __name__ == "__main__":
    main()