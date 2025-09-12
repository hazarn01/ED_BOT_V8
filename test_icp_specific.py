#!/usr/bin/env python3
"""
Test ICP query specifically to ensure it matches the correct ICH Management Protocol.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_icp_query():
    """Test ICP query to verify it matches ICH Management Protocol."""
    
    from src.pipeline.ground_truth_validator import GroundTruthValidator
    
    # Initialize validator
    validator = GroundTruthValidator()
    
    # Test the specific ICP query
    query = "What is the ICP guideline?"
    
    logger.info(f"Testing query: {query}")
    
    # Get ground truth match
    match = validator.validate_query(query)
    
    if match:
        logger.info(f"✅ Found match!")
        logger.info(f"Source: {match.source}")
        logger.info(f"Confidence: {match.confidence:.2%}")
        logger.info(f"Document source: {match.document_source}")
        logger.info(f"Question: {match.question}")
        logger.info(f"Answer preview: {match.answer[:200]}...")
        
        # Check if it's the correct ICH Management Protocol
        if 'ICH_Management_Protocol' in match.source:
            logger.info("🎯 CORRECT: Matched ICH Management Protocol!")
            return True
        else:
            logger.warning(f"❌ INCORRECT: Matched {match.source} instead of ICH Management Protocol")
            return False
            
    else:
        logger.error("❌ No match found")
        return False

def test_specific_ich_matches():
    """Test ICH-specific questions from the ground truth data."""
    
    from src.pipeline.ground_truth_validator import GroundTruthValidator
    
    validator = GroundTruthValidator()
    
    # Test queries that should match ICH Management Protocol
    ich_queries = [
        "What is the target systolic blood pressure for ICH patients?",
        "What is the first-line antihypertensive for ICH?", 
        "What reversal agent is used for warfarin-associated ICH?",
        "How do you activate the acute stroke page for ICH patients?",
        "What are the Mount Sinai Neuro-ICU contact numbers?",
    ]
    
    logger.info("Testing ICH-specific queries...")
    
    success_count = 0
    for query in ich_queries:
        logger.info(f"\nQuery: {query}")
        
        match = validator.validate_query(query)
        if match and 'ICH_Management_Protocol' in match.source:
            logger.info(f"✅ CORRECT: {match.source}")
            success_count += 1
        elif match:
            logger.warning(f"❌ INCORRECT: {match.source}")
        else:
            logger.error("❌ NO MATCH")
    
    logger.info(f"\nICH Protocol Matches: {success_count}/{len(ich_queries)}")
    return success_count == len(ich_queries)

if __name__ == "__main__":
    logger.info("🧪 Testing ICP/ICH specific matching")
    
    # Test general ICP query
    icp_success = test_icp_query()
    
    # Test specific ICH queries
    ich_success = test_specific_ich_matches()
    
    if icp_success and ich_success:
        logger.info("🎉 All ICH/ICP tests passed!")
    else:
        logger.error("❌ Some ICH/ICP tests failed")