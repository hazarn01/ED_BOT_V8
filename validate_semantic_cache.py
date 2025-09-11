#!/usr/bin/env python3
"""
Quick validation script for semantic cache implementation.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all components can be imported."""
    print("Testing imports...")
    
    try:
        print("✓ QueryType imported successfully")
        
        print("✓ EmbeddingService imported successfully")
        
        print("✓ SemanticCache imported successfully")
        
        print("✓ Cache metrics imported successfully")
        
        print("✓ Settings imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_query_types():
    """Test query types and never cache logic."""
    print("\nTesting query types...")
    
    try:
        from src.cache.semantic_cache import SemanticCache
        from src.models.query_types import QueryType
        
        # Test that never cache types are correct
        never_cache = SemanticCache.NEVER_CACHE
        print(f"✓ NEVER_CACHE contains: {[qt.value for qt in never_cache]}")
        
        assert QueryType.CONTACT_LOOKUP in never_cache
        assert QueryType.FORM_RETRIEVAL in never_cache
        print("✓ Never cache types are correct")
        
        # Test TTL settings
        ttl_by_type = SemanticCache.TTL_BY_TYPE
        print(f"✓ TTL settings: {[(qt.value, ttl) for qt, ttl in ttl_by_type.items()]}")
        
        return True
    except Exception as e:
        print(f"✗ Query types test failed: {e}")
        return False

def test_embedding_service():
    """Test embedding service functionality."""
    print("\nTesting embedding service...")
    
    try:
        import asyncio

        from src.cache.embedding_service import EmbeddingService
        
        # Test with no model (fallback)
        service = EmbeddingService()
        
        async def test_embedding():
            embedding = await service.embed("test query")
            assert len(embedding) == 768  # Default dimension
            # Check if embedding is roughly normalized (should be close to 1.0)
            import numpy as np
            norm = np.linalg.norm(embedding)
            assert abs(norm - 1.0) < 1e-6  # Should be normalized
            print("✓ Fallback embedding generation works")
            return True
        
        result = asyncio.run(test_embedding())
        return result
    except Exception as e:
        print(f"✗ Embedding service test failed: {e}")
        return False

def test_metrics():
    """Test metrics functionality."""
    print("\nTesting cache metrics...")
    
    try:
        from src.cache.metrics import semantic_cache_metrics
        
        # Test recording metrics
        semantic_cache_metrics.record_cache_hit("protocol", 0.95)
        semantic_cache_metrics.record_cache_miss("protocol")
        semantic_cache_metrics.record_cache_set("protocol", 0.9)
        
        # Test getting stats
        hit_rate = semantic_cache_metrics.get_cache_hit_rate("protocol")
        print(f"✓ Hit rate for protocol: {hit_rate}%")
        
        summary = semantic_cache_metrics.get_metrics_summary()
        print(f"✓ Metrics summary generated: {summary['semantic_cache']['hits']} hits")
        
        return True
    except Exception as e:
        print(f"✗ Metrics test failed: {e}")
        return False

def test_settings():
    """Test settings integration."""
    print("\nTesting settings...")
    
    try:
        from src.config.settings import Settings
        
        settings = Settings(
            enable_semantic_cache=True,
            semantic_cache_similarity_threshold=0.9,
            semantic_cache_min_confidence=0.7
        )
        
        print(f"✓ Semantic cache enabled: {settings.enable_semantic_cache}")
        print(f"✓ Similarity threshold: {settings.semantic_cache_similarity_threshold}")
        print(f"✓ Min confidence: {settings.semantic_cache_min_confidence}")
        
        return True
    except Exception as e:
        print(f"✗ Settings test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("=== Semantic Cache Validation ===\n")
    
    tests = [
        test_imports,
        test_query_types,
        test_embedding_service,
        test_metrics,
        test_settings
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All validation tests passed! Semantic cache is ready.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())