#!/usr/bin/env python3
"""
Data Quality Testing Suite

Validates the quality of data in the database BEFORE it affects retrieval.
Catches contamination issues like development docs mixed with medical content.

Key Features:
- Document type validation
- Content contamination detection
- Medical terminology coverage
- Data completeness checks
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Set
from pathlib import Path

from sqlalchemy import text
from src.models.database import get_db_session
from src.models.entities import Document, DocumentChunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DataQualityResult:
    """Results of data quality analysis."""
    total_documents: int
    medical_documents: int
    contaminated_documents: int
    development_documents: int
    coverage_gaps: List[str]
    quality_score: float
    issues: List[str]
    recommendations: List[str]

class DataQualityTester:
    """Comprehensive data quality testing for medical database."""
    
    def __init__(self):
        # Development/contamination indicators
        self.dev_indicators = [
            'implementation', 'enhancement', 'processor', 'pipeline',
            'src/', 'import', 'class', 'def ', 'python', 'javascript',
            'TODO', 'FIXME', 'git', 'merge', 'branch', 'commit',
            '__init__', 'self.', 'async def', 'await', 'export',
            'component', 'useState', 'useEffect', 'props'
        ]
        
        # Required medical domains for comprehensive coverage
        self.required_domains = {
            'cardiac': ['STEMI', 'MI', 'cardiac arrest', 'arrhythmia', 'ACS'],
            'respiratory': ['intubation', 'ventilator', 'pneumonia', 'COPD', 'asthma'],
            'sepsis': ['sepsis', 'septic shock', 'antibiotics', 'lactate'],
            'trauma': ['trauma', 'hemorrhage', 'TBI', 'fracture'],
            'stroke': ['stroke', 'CVA', 'TPA', 'thrombectomy'],
            'pediatric': ['pediatric', 'child', 'infant', 'PALS'],
            'obstetric': ['pregnancy', 'labor', 'delivery', 'eclampsia'],
            'toxicology': ['overdose', 'poisoning', 'antidote', 'toxidrome'],
            'procedures': ['intubation', 'central line', 'chest tube', 'lumbar puncture'],
            'medications': ['epinephrine', 'atropine', 'naloxone', 'insulin']
        }
        
        # File type validation
        self.valid_medical_extensions = {'.pdf', '.PDF'}
        self.invalid_extensions = {'.md', '.txt', '.py', '.js', '.json', '.yaml', '.yml'}
    
    def run_comprehensive_test(self) -> DataQualityResult:
        """Run all data quality tests."""
        logger.info("🔍 Starting Comprehensive Data Quality Testing")
        logger.info("=" * 60)
        
        with get_db_session() as session:
            # 1. Document inventory
            all_docs = session.query(Document).all()
            total_docs = len(all_docs)
            
            # 2. File type analysis
            file_type_issues = self._analyze_file_types(all_docs)
            
            # 3. Content contamination check
            contaminated_docs = self._detect_contamination(session)
            
            # 4. Medical coverage analysis
            coverage_gaps = self._analyze_medical_coverage(session)
            
            # 5. Data completeness check
            completeness_issues = self._check_data_completeness(session)
            
            # 6. Duplicate detection
            duplicates = self._detect_duplicates(session)
            
            # Calculate metrics
            medical_docs = total_docs - len(contaminated_docs) - len(file_type_issues['invalid_docs'])
            quality_score = self._calculate_quality_score(
                total_docs, medical_docs, contaminated_docs, coverage_gaps
            )
            
            # Compile issues and recommendations
            issues = []
            recommendations = []
            
            if file_type_issues['invalid_docs']:
                issues.append(f"Found {len(file_type_issues['invalid_docs'])} non-medical file types")
                recommendations.append("Remove all non-PDF files from medical database")
            
            if contaminated_docs:
                issues.append(f"Found {len(contaminated_docs)} documents with development content")
                recommendations.append("Clean contaminated documents immediately")
            
            if coverage_gaps:
                issues.append(f"Missing coverage for: {', '.join(coverage_gaps)}")
                recommendations.append(f"Add medical content for: {', '.join(coverage_gaps)}")
            
            if duplicates:
                issues.append(f"Found {len(duplicates)} duplicate documents")
                recommendations.append("Remove duplicate documents to improve search quality")
            
            # Log results
            self._log_results(quality_score, issues, recommendations)
            
            return DataQualityResult(
                total_documents=total_docs,
                medical_documents=medical_docs,
                contaminated_documents=len(contaminated_docs),
                development_documents=len(file_type_issues['invalid_docs']),
                coverage_gaps=coverage_gaps,
                quality_score=quality_score,
                issues=issues,
                recommendations=recommendations
            )
    
    def _analyze_file_types(self, documents: List[Document]) -> Dict:
        """Analyze document file types for validity."""
        invalid_docs = []
        file_type_stats = {}
        
        for doc in documents:
            ext = Path(doc.filename).suffix.lower()
            file_type_stats[ext] = file_type_stats.get(ext, 0) + 1
            
            if ext in self.invalid_extensions:
                invalid_docs.append(doc.filename)
                logger.warning(f"❌ Invalid file type: {doc.filename}")
            elif ext not in self.valid_medical_extensions:
                logger.warning(f"⚠️  Suspicious file type: {doc.filename} ({ext})")
        
        logger.info(f"📊 File type distribution: {file_type_stats}")
        
        return {
            'invalid_docs': invalid_docs,
            'stats': file_type_stats
        }
    
    def _detect_contamination(self, session) -> List[str]:
        """Detect documents contaminated with development content."""
        contaminated = []
        
        for indicator in self.dev_indicators[:5]:  # Check top indicators
            query = text("""
                SELECT DISTINCT d.filename
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.chunk_text ILIKE :pattern
                LIMIT 10
            """)
            
            results = session.execute(query, {'pattern': f'%{indicator}%'}).fetchall()
            
            for row in results:
                filename = row[0]
                if filename not in contaminated:
                    contaminated.append(filename)
                    logger.warning(f"⚠️  Contaminated: {filename} contains '{indicator}'")
        
        return contaminated
    
    def _analyze_medical_coverage(self, session) -> List[str]:
        """Check coverage of required medical domains."""
        gaps = []
        
        for domain, keywords in self.required_domains.items():
            # Check if any keyword from this domain exists
            found = False
            for keyword in keywords:
                query = text("""
                    SELECT COUNT(*)
                    FROM document_chunks
                    WHERE chunk_text ILIKE :pattern
                    LIMIT 1
                """)
                
                count = session.execute(query, {'pattern': f'%{keyword}%'}).scalar()
                if count > 0:
                    found = True
                    break
            
            if not found:
                gaps.append(domain)
                logger.warning(f"📋 Missing coverage for: {domain}")
        
        return gaps
    
    def _check_data_completeness(self, session) -> List[str]:
        """Check for data completeness issues."""
        issues = []
        
        # Check for documents without chunks
        orphan_docs = session.execute(text("""
            SELECT COUNT(*)
            FROM documents d
            LEFT JOIN document_chunks dc ON d.id = dc.document_id
            WHERE dc.id IS NULL
        """)).scalar()
        
        if orphan_docs > 0:
            issues.append(f"{orphan_docs} documents without chunks")
        
        # Check for empty chunks
        empty_chunks = session.execute(text("""
            SELECT COUNT(*)
            FROM document_chunks
            WHERE LENGTH(chunk_text) < 10
        """)).scalar()
        
        if empty_chunks > 0:
            issues.append(f"{empty_chunks} empty or tiny chunks")
        
        return issues
    
    def _detect_duplicates(self, session) -> List[str]:
        """Detect duplicate documents."""
        query = text("""
            SELECT filename, COUNT(*) as count
            FROM documents
            GROUP BY filename
            HAVING COUNT(*) > 1
        """)
        
        duplicates = []
        results = session.execute(query).fetchall()
        
        for filename, count in results:
            duplicates.append(f"{filename} ({count} copies)")
            logger.warning(f"🔁 Duplicate: {filename} appears {count} times")
        
        return duplicates
    
    def _calculate_quality_score(self, total: int, medical: int, 
                                contaminated: List, gaps: List) -> float:
        """Calculate overall data quality score."""
        if total == 0:
            return 0.0
        
        # Scoring components
        medical_ratio = medical / total if total > 0 else 0
        contamination_penalty = len(contaminated) * 0.05
        coverage_penalty = len(gaps) * 0.03
        
        score = medical_ratio - contamination_penalty - coverage_penalty
        return max(0.0, min(1.0, score))
    
    def _log_results(self, score: float, issues: List[str], 
                    recommendations: List[str]):
        """Log test results."""
        logger.info(f"\n📊 DATA QUALITY SCORE: {score:.1%}")
        
        if score >= 0.9:
            logger.info("✅ EXCELLENT - Data quality is optimal")
        elif score >= 0.7:
            logger.info("👍 GOOD - Data quality is acceptable")
        elif score >= 0.5:
            logger.warning("⚠️  FAIR - Data quality needs improvement")
        else:
            logger.error("❌ POOR - Data quality is unacceptable")
        
        if issues:
            logger.info("\n🔍 Issues Found:")
            for issue in issues:
                logger.warning(f"  • {issue}")
        
        if recommendations:
            logger.info("\n💡 Recommendations:")
            for rec in recommendations:
                logger.info(f"  • {rec}")

def main():
    """Run data quality tests."""
    tester = DataQualityTester()
    result = tester.run_comprehensive_test()
    
    # Exit with error if quality is too low
    if result.quality_score < 0.7:
        logger.error("❌ Data quality below acceptable threshold")
        exit(1)
    
    logger.info("✅ Data quality check passed")

if __name__ == "__main__":
    main()