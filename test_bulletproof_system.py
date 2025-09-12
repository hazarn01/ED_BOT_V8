#!/usr/bin/env python3
"""
Test the new bulletproof retrieval system with critical medical queries.
Focus on resolving the ICP guideline bug identified in the benchmark report.
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_bulletproof_system():
    """Test the bulletproof retrieval system with critical medical queries."""
    
    logger.info("🧪 Starting bulletproof system validation tests")
    
    # Import required components
    from src.models.database import get_db_session
    from src.pipeline.bulletproof_retriever import BulletproofRetriever
    
    # Test queries - focus on the critical ICP bug
    test_queries = [
        # Critical bug from benchmark report
        "What is the ICP guideline?",
        "What is the ICH management protocol?",
        "How do you manage intracranial pressure?",
        
        # Other critical medical queries  
        "What is the ED STEMI protocol?",
        "What are the criteria for sepsis?",
        "What is the heparin dosage for adults?",
        "epi dosage in children",
        "What is the Asthma guideline?",
        
        # EVD placement query
        "What is the EVD placement protocol?",
        "When should external ventricular drain be placed?"
    ]
    
    # Get database session
    try:
        from src.models.database import SessionLocal
        db_session = SessionLocal()
        retriever = BulletproofRetriever(db_session)
        
        logger.info("✅ Database connection established")
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return
    
    # Test each query
    results = []
    
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Test {i}/{len(test_queries)}: {query}")
        logger.info('='*60)
        
        try:
            response = retriever.get_medical_response(query)
            
            # Analyze response quality
            confidence = response.get('confidence', 0.0)
            has_content = response.get('has_real_content', False)
            validation_method = response.get('validation_method', 'unknown')
            
            logger.info(f"Response confidence: {confidence:.2%}")
            logger.info(f"Has real content: {has_content}")
            logger.info(f"Validation method: {validation_method}")
            
            # Check for critical ICP bug resolution
            if 'icp' in query.lower():
                response_text = response.get('response', '').lower()
                
                if 'consult trackboard' in response_text:
                    logger.error("🔴 CRITICAL BUG STILL PRESENT: ICP query returns consult trackboard info!")
                    results.append({
                        'query': query,
                        'status': 'FAILED - BUG PRESENT',
                        'confidence': confidence,
                        'method': validation_method
                    })
                elif any(term in response_text for term in ['intracranial pressure', 'ich management', 'evd', 'blood pressure']):
                    logger.info("✅ ICP BUG RESOLVED: Returns relevant ICP/ICH content")
                    results.append({
                        'query': query, 
                        'status': 'SUCCESS - BUG FIXED',
                        'confidence': confidence,
                        'method': validation_method
                    })
                else:
                    logger.warning("⚠️ ICP query returns unrelated content")
                    results.append({
                        'query': query,
                        'status': 'PARTIAL - NEEDS REVIEW',
                        'confidence': confidence,
                        'method': validation_method
                    })
            else:
                # For non-ICP queries, check general quality
                if confidence >= 0.7 and has_content:
                    logger.info("✅ HIGH QUALITY RESPONSE")
                    status = 'SUCCESS'
                elif confidence >= 0.5 and has_content:
                    logger.info("⚠️ MEDIUM QUALITY RESPONSE")
                    status = 'PARTIAL'
                else:
                    logger.warning("❌ LOW QUALITY RESPONSE")
                    status = 'FAILED'
                    
                results.append({
                    'query': query,
                    'status': status,
                    'confidence': confidence,
                    'method': validation_method
                })
            
            # Log response preview
            response_preview = response.get('response', '')[:200]
            logger.info(f"Response preview: {response_preview}...")
            
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            results.append({
                'query': query,
                'status': 'ERROR',
                'confidence': 0.0,
                'method': 'error'
            })
    
    # Summary report
    logger.info(f"\n{'='*80}")
    logger.info("🏆 BULLETPROOF SYSTEM TEST RESULTS")
    logger.info('='*80)
    
    success_count = len([r for r in results if r['status'].startswith('SUCCESS')])
    partial_count = len([r for r in results if r['status'].startswith('PARTIAL')])
    failed_count = len([r for r in results if r['status'].startswith('FAILED')])
    error_count = len([r for r in results if r['status'] == 'ERROR'])
    
    logger.info(f"✅ SUCCESS: {success_count}/{len(results)}")
    logger.info(f"⚠️ PARTIAL: {partial_count}/{len(results)}")
    logger.info(f"❌ FAILED: {failed_count}/{len(results)}")
    logger.info(f"💥 ERROR: {error_count}/{len(results)}")
    
    # Critical ICP bug status
    icp_results = [r for r in results if 'icp' in r['query'].lower()]
    icp_fixed = len([r for r in icp_results if 'BUG FIXED' in r['status']])
    
    if icp_fixed > 0:
        logger.info(f"🎉 ICP BUG STATUS: FIXED ({icp_fixed}/{len(icp_results)} ICP queries working)")
    else:
        logger.error(f"🔴 ICP BUG STATUS: STILL PRESENT ({len(icp_results)} ICP queries failing)")
    
    # Validation method breakdown
    logger.info("\n📊 VALIDATION METHODS USED:")
    method_counts = {}
    for result in results:
        method = result['method']
        method_counts[method] = method_counts.get(method, 0) + 1
    
    for method, count in method_counts.items():
        logger.info(f"• {method}: {count} queries")
    
    # Average confidence
    avg_confidence = sum(r['confidence'] for r in results) / len(results)
    logger.info(f"\n📈 Average confidence: {avg_confidence:.2%}")
    
    # Close database connection
    db_session.close()
    
    return results

if __name__ == "__main__":
    # Run the test
    import asyncio
    asyncio.run(test_bulletproof_system())