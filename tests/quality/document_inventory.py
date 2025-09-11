"""
Document Inventory System - Know exactly what medical content is available
PRP-48: Complete document coverage analysis
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import json
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from src.models.database import get_db_session
from src.models.entities import Document, DocumentChunk

class DocumentInventory:
    """Comprehensive inventory of all medical documents and their content."""
    
    def __init__(self):
        self.inventory = {
            "protocols": [],
            "forms": [],
            "guidelines": [],
            "pathways": [],
            "references": [],
            "medications": [],
            "contacts": [],
            "unknown": []
        }
        self.keyword_map = defaultdict(list)  # keyword -> [doc_ids]
        self.coverage_gaps = []
        
    def analyze_database_content(self):
        """Analyze all documents in database and categorize them."""
        with get_db_session() as session:
            # Get all documents
            documents = session.query(Document).all()
            print(f"\n📊 TOTAL DOCUMENTS IN DATABASE: {len(documents)}\n")
            
            for doc in documents:
                # Categorize document
                category = self._categorize_document(doc.filename, doc.content_type)
                
                # Get chunk count for this document
                chunk_count = session.query(DocumentChunk).filter(
                    DocumentChunk.document_id == doc.id
                ).count()
                
                # Extract key medical terms
                medical_terms = self._extract_medical_terms(doc.filename, doc.content)
                
                doc_info = {
                    "id": doc.id,
                    "filename": doc.filename,
                    "content_type": doc.content_type,
                    "chunk_count": chunk_count,
                    "content_length": len(doc.content) if doc.content else 0,
                    "medical_terms": medical_terms,
                    "category": category
                }
                
                self.inventory[category].append(doc_info)
                
                # Build keyword map
                for term in medical_terms:
                    self.keyword_map[term.lower()].append(doc.id)
                    
            return self.inventory
    
    def _categorize_document(self, filename: str, content_type: str) -> str:
        """Categorize document based on filename and type."""
        filename_lower = filename.lower()
        
        if 'protocol' in filename_lower or 'activation' in filename_lower:
            return 'protocols'
        elif 'form' in filename_lower or 'consent' in filename_lower:
            return 'forms'
        elif 'guideline' in filename_lower or 'criteria' in filename_lower:
            return 'guidelines'
        elif 'pathway' in filename_lower or 'retu' in filename_lower:
            return 'pathways'
        elif 'reference' in filename_lower or 'tip' in filename_lower:
            return 'references'
        elif any(med in filename_lower for med in ['medication', 'drug', 'dose', 'dosing', 'infusion']):
            return 'medications'
        elif 'contact' in filename_lower or 'phone' in filename_lower:
            return 'contacts'
        else:
            return 'unknown'
    
    def _extract_medical_terms(self, filename: str, content: str) -> List[str]:
        """Extract key medical terms from document."""
        terms = []
        
        # Extract from filename
        filename_words = re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]+\b', filename)
        terms.extend(filename_words)
        
        # Common medical keywords to look for
        medical_keywords = [
            'STEMI', 'sepsis', 'anaphylaxis', 'hypoglycemia', 'epinephrine',
            'norepinephrine', 'levophed', 'dosing', 'protocol', 'pathway',
            'RETU', 'ICU', 'ED', 'cardiac', 'pediatric', 'transfusion',
            'consent', 'criteria', 'lactate', 'glucose', 'D50'
        ]
        
        for keyword in medical_keywords:
            if content and keyword.lower() in (content[:1000]).lower():
                terms.append(keyword)
                
        return list(set(terms))  # Remove duplicates
    
    def test_specific_queries(self) -> Dict[str, any]:
        """Test specific problematic queries to understand failures."""
        test_queries = [
            ("levophed dosing", "medications"),
            ("pediatric epinephrine", "medications"),
            ("blood transfusion form", "forms"),
            ("STEMI protocol", "protocols"),
            ("sepsis criteria", "guidelines"),
            ("RETU pathways", "pathways"),
            ("L&D clearance", "protocols")
        ]
        
        results = {}
        
        with get_db_session() as session:
            for query, expected_category in test_queries:
                # Search for this query
                search_query = text("""
                    SELECT d.filename, d.content_type, dc.chunk_text
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    WHERE dc.chunk_text ILIKE :search_term
                    ORDER BY LENGTH(dc.chunk_text) DESC
                    LIMIT 3
                """)
                
                matches = session.execute(
                    search_query, 
                    {"search_term": f"%{query.split()[0]}%"}
                ).fetchall()
                
                results[query] = {
                    "expected_category": expected_category,
                    "found_count": len(matches),
                    "found_files": [m[0] for m in matches],
                    "correct_category": any(
                        doc["filename"] == m[0] 
                        for m in matches 
                        for doc in self.inventory.get(expected_category, [])
                    )
                }
                
        return results
    
    def identify_coverage_gaps(self) -> List[str]:
        """Identify what medical content is missing."""
        expected_content = [
            "pediatric dosing guidelines",
            "adult epinephrine dosing", 
            "norepinephrine/levophed dosing",
            "blood transfusion consent form",
            "L&D clearance protocol",
            "cardiac arrest protocol",
            "stroke protocol",
            "trauma activation",
            "code blue procedures"
        ]
        
        gaps = []
        for expected in expected_content:
            found = False
            for category, docs in self.inventory.items():
                for doc in docs:
                    if any(term in expected.lower() for term in doc["medical_terms"]):
                        found = True
                        break
                if found:
                    break
            
            if not found:
                gaps.append(expected)
                
        return gaps
    
    def generate_report(self):
        """Generate comprehensive inventory report."""
        print("=" * 80)
        print("📋 DOCUMENT INVENTORY REPORT")
        print("=" * 80)
        
        # Category breakdown
        print("\n📊 DOCUMENTS BY CATEGORY:")
        for category, docs in self.inventory.items():
            if docs:
                print(f"\n{category.upper()} ({len(docs)} documents):")
                for doc in docs[:5]:  # Show first 5
                    print(f"  • {doc['filename']}")
                    print(f"    Terms: {', '.join(doc['medical_terms'][:5])}")
                if len(docs) > 5:
                    print(f"  ... and {len(docs) - 5} more")
        
        # Test specific queries
        print("\n🔍 QUERY TEST RESULTS:")
        query_results = self.test_specific_queries()
        for query, result in query_results.items():
            status = "✅" if result["found_count"] > 0 and result["correct_category"] else "❌"
            print(f"\n{status} Query: '{query}'")
            print(f"   Expected: {result['expected_category']}")
            print(f"   Found: {result['found_count']} documents")
            if result["found_files"]:
                print(f"   Files: {result['found_files'][0]}")
        
        # Coverage gaps
        print("\n⚠️ COVERAGE GAPS:")
        gaps = self.identify_coverage_gaps()
        if gaps:
            for gap in gaps:
                print(f"  • Missing: {gap}")
        else:
            print("  ✅ All expected content found")
        
        # Keyword coverage
        print(f"\n🔑 KEYWORD INDEX: {len(self.keyword_map)} unique medical terms indexed")
        common_terms = sorted(self.keyword_map.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        print("Top indexed terms:")
        for term, doc_ids in common_terms:
            print(f"  • {term}: appears in {len(doc_ids)} documents")
        
        return {
            "total_documents": sum(len(docs) for docs in self.inventory.values()),
            "categories": {k: len(v) for k, v in self.inventory.items()},
            "coverage_gaps": gaps,
            "query_test_results": query_results
        }

def main():
    """Run document inventory analysis."""
    print("🔍 Starting Document Inventory Analysis...")
    
    inventory = DocumentInventory()
    inventory.analyze_database_content()
    report = inventory.generate_report()
    
    # Save report
    with open('document_inventory_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print("\n✅ Report saved to document_inventory_report.json")
    
    return report

if __name__ == "__main__":
    main()