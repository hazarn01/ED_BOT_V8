"""
Unit tests for enhanced settings and configuration management.
"""

import os
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from src.config.enhanced_settings import (
    CacheConfig,
    EnhancedSettings,
    FeatureFlags,
    HighlightingConfig,
    HybridSearchConfig,
    ObservabilityConfig,
    TableExtractionConfig,
    get_settings,
)


class TestFeatureFlags:
    """Test feature flags configuration"""
    
    def test_feature_flags_defaults(self):
        """Test default feature flag values"""
        flags = FeatureFlags()
        
        # Search backend defaults
        assert flags.search_backend == "pgvector"
        assert flags.enable_hybrid_search is False
        assert flags.enable_elasticsearch is False
        
        # Enhancement defaults
        assert flags.enable_source_highlighting is False
        assert flags.enable_pdf_viewer is False
        assert flags.enable_table_extraction is False
        assert flags.enable_semantic_cache is False
        
        # Safety defaults (always enabled)
        assert flags.enable_phi_scrubbing is True
        assert flags.enable_response_validation is True
        
        # Observability defaults
        assert flags.enable_metrics is True
        assert flags.enable_medical_metrics is True
        
        # UI defaults
        assert flags.enable_streamlit_demo is False
    
    def test_feature_flags_validation(self):
        """Test feature flag validation rules"""
        # Valid configuration
        flags = FeatureFlags(
            search_backend="hybrid",
            enable_hybrid_search=True,
            enable_elasticsearch=True
        )
        assert flags.search_backend == "hybrid"
        
        # Invalid search backend
        with pytest.raises(ValidationError):
            FeatureFlags(search_backend="invalid_backend")
    
    def test_feature_flags_environment_override(self):
        """Test environment variable override of feature flags"""
        with patch.dict(os.environ, {
            'FEATURES__ENABLE_HYBRID_SEARCH': 'true',
            'FEATURES__ENABLE_ELASTICSEARCH': 'true',
            'FEATURES__SEARCH_BACKEND': 'hybrid'
        }):
            flags = FeatureFlags()
            assert flags.enable_hybrid_search is True
            assert flags.enable_elasticsearch is True
            assert flags.search_backend == "hybrid"


class TestHybridSearchConfig:
    """Test hybrid search configuration"""
    
    def test_hybrid_search_defaults(self):
        """Test default hybrid search configuration"""
        config = HybridSearchConfig()
        
        assert config.elasticsearch_url == "http://elasticsearch:9200"
        assert config.elasticsearch_index_prefix == "edbot"
        assert config.elasticsearch_timeout == 30
        assert config.keyword_weight == 0.3
        assert config.semantic_weight == 0.7
        assert config.max_results_per_source == 50
    
    def test_hybrid_search_weights_validation(self):
        """Test that weights sum to approximately 1.0"""
        # Valid weights
        config = HybridSearchConfig(keyword_weight=0.4, semantic_weight=0.6)
        assert abs((config.keyword_weight + config.semantic_weight) - 1.0) < 0.01
        
        # Invalid weights (don't sum to 1.0)
        with pytest.raises(ValidationError):
            HybridSearchConfig(keyword_weight=0.5, semantic_weight=0.6)
    
    def test_hybrid_search_environment_override(self):
        """Test environment variable override"""
        with patch.dict(os.environ, {
            'HYBRID_SEARCH__ELASTICSEARCH_URL': 'http://custom:9200',
            'HYBRID_SEARCH__KEYWORD_WEIGHT': '0.5',
            'HYBRID_SEARCH__SEMANTIC_WEIGHT': '0.5'
        }):
            config = HybridSearchConfig()
            assert config.elasticsearch_url == "http://custom:9200"
            assert config.keyword_weight == 0.5
            assert config.semantic_weight == 0.5


class TestCacheConfig:
    """Test cache configuration"""
    
    def test_cache_defaults(self):
        """Test default cache configuration"""
        config = CacheConfig()
        
        assert config.ttl_seconds == 300
        assert config.max_entries == 10000
        assert config.min_confidence_to_cache == 0.7
        assert config.similarity_threshold == 0.9
        assert config.enable_form_caching is False  # Never cache forms
    
    def test_cache_validation(self):
        """Test cache configuration validation"""
        # Valid configuration
        config = CacheConfig(
            ttl_seconds=600,
            min_confidence_to_cache=0.8,
            similarity_threshold=0.95
        )
        assert config.ttl_seconds == 600
        
        # Invalid confidence threshold (> 1.0)
        with pytest.raises(ValidationError):
            CacheConfig(min_confidence_to_cache=1.5)
        
        # Invalid similarity threshold (< 0.0)
        with pytest.raises(ValidationError):
            CacheConfig(similarity_threshold=-0.1)


class TestTableExtractionConfig:
    """Test table extraction configuration"""
    
    def test_table_extraction_defaults(self):
        """Test default table extraction configuration"""
        config = TableExtractionConfig()
        
        assert config.extraction_strategy == "unstructured"
        assert config.table_confidence_threshold == 0.6
        assert config.max_table_size == 1000
        assert config.classify_tables is True
        assert config.extract_table_metadata is True
    
    def test_table_extraction_validation(self):
        """Test table extraction validation"""
        # Valid strategy
        config = TableExtractionConfig(extraction_strategy="pdfplumber")
        assert config.extraction_strategy == "pdfplumber"
        
        # Invalid strategy
        with pytest.raises(ValidationError):
            TableExtractionConfig(extraction_strategy="invalid_strategy")
        
        # Invalid confidence threshold
        with pytest.raises(ValidationError):
            TableExtractionConfig(table_confidence_threshold=1.5)


class TestHighlightingConfig:
    """Test highlighting configuration"""
    
    def test_highlighting_defaults(self):
        """Test default highlighting configuration"""
        config = HighlightingConfig()
        
        assert config.min_highlight_length == 20
        assert config.context_chars == 50
        assert config.max_highlights_per_response == 10
        assert config.bbox_extraction is True
        assert config.highlight_confidence_threshold == 0.7
    
    def test_highlighting_validation(self):
        """Test highlighting validation"""
        # Valid configuration
        config = HighlightingConfig(
            min_highlight_length=30,
            max_highlights_per_response=5
        )
        assert config.min_highlight_length == 30
        assert config.max_highlights_per_response == 5
        
        # Invalid highlight length (too short)
        with pytest.raises(ValidationError):
            HighlightingConfig(min_highlight_length=0)
        
        # Invalid max highlights (too many)
        with pytest.raises(ValidationError):
            HighlightingConfig(max_highlights_per_response=100)


class TestObservabilityConfig:
    """Test observability configuration"""
    
    def test_observability_defaults(self):
        """Test default observability configuration"""
        config = ObservabilityConfig()
        
        assert config.metrics_port == 9090
        assert config.health_check_interval == 30
        assert config.performance_alert_threshold == 2.0
        assert config.log_query_metrics is True
        assert config.enable_tracing is False
    
    def test_observability_validation(self):
        """Test observability validation"""
        # Valid configuration
        config = ObservabilityConfig(
            metrics_port=8080,
            health_check_interval=60,
            performance_alert_threshold=1.5
        )
        assert config.metrics_port == 8080
        assert config.health_check_interval == 60
        assert config.performance_alert_threshold == 1.5
        
        # Invalid port (too low)
        with pytest.raises(ValidationError):
            ObservabilityConfig(metrics_port=80)
        
        # Invalid health check interval (too short)
        with pytest.raises(ValidationError):
            ObservabilityConfig(health_check_interval=5)


class TestEnhancedSettings:
    """Test enhanced settings integration"""
    
    def test_enhanced_settings_defaults(self):
        """Test default enhanced settings"""
        with patch.dict(os.environ, {}, clear=True):
            settings = EnhancedSettings()
            
            # Core settings
            assert settings.app_name == "EDBotv8"
            assert settings.environment == "development"
            assert settings.debug is False
            
            # Feature flags should use defaults
            assert settings.features.enable_hybrid_search is False
            assert settings.features.enable_phi_scrubbing is True
            
            # Config sections should exist
            assert settings.hybrid_search is not None
            assert settings.cache_config is not None
            assert settings.table_extraction is not None
            assert settings.highlighting is not None
            assert settings.observability is not None
    
    def test_enhanced_settings_production_safety(self):
        """Test production safety enforcement"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            settings = EnhancedSettings()
            
            assert settings.environment == "production"
            assert settings.is_production is True
            
            # Production safety features must be enabled
            assert settings.features.enable_phi_scrubbing is True
            assert settings.features.enable_response_validation is True
            
            # Experimental features should be disabled by default
            assert settings.features.enable_streamlit_demo is False
            assert settings.features.enable_pdf_viewer is False
    
    def test_enhanced_settings_validation_errors(self):
        """Test enhanced settings validation"""
        # Test with invalid LLM backend
        with patch.dict(os.environ, {'LLM_BACKEND': 'invalid_backend'}):
            with pytest.raises(ValidationError):
                EnhancedSettings()
    
    def test_enhanced_settings_environment_loading(self):
        """Test environment variable loading"""
        test_env = {
            'APP_NAME': 'TestBot',
            'ENVIRONMENT': 'staging',
            'DEBUG': 'true',
            'LLM_BACKEND': 'gpt-oss',
            'FEATURES__ENABLE_HYBRID_SEARCH': 'true',
            'FEATURES__SEARCH_BACKEND': 'hybrid',
            'CACHE_CONFIG__TTL_SECONDS': '600',
            'OBSERVABILITY__METRICS_PORT': '8080'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = EnhancedSettings()
            
            assert settings.app_name == "TestBot"
            assert settings.environment == "staging"
            assert settings.debug is True
            assert settings.llm_backend == "gpt-oss"
            assert settings.features.enable_hybrid_search is True
            assert settings.features.search_backend == "hybrid"
            assert settings.cache_config.ttl_seconds == 600
            assert settings.observability.metrics_port == 8080
    
    def test_enhanced_settings_nested_validation(self):
        """Test nested configuration validation"""
        test_env = {
            'HYBRID_SEARCH__KEYWORD_WEIGHT': '0.8',
            'HYBRID_SEARCH__SEMANTIC_WEIGHT': '0.1'  # These don't sum to 1.0
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                EnhancedSettings()
            
            # Should fail validation due to weights not summing to 1.0
            assert "keyword_weight + semantic_weight" in str(exc_info.value)
    
    @patch('src.config.enhanced_settings.redis.Redis')
    def test_enhanced_settings_external_dependencies(self, mock_redis):
        """Test settings with external dependencies"""
        # Mock Redis connection for feature flags
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        settings = EnhancedSettings()
        
        # Should create settings successfully even with Redis dependency
        assert settings is not None
        assert settings.features is not None


class TestGetSettings:
    """Test settings singleton"""
    
    @patch('src.config.enhanced_settings._settings', None)
    def test_get_settings_singleton(self):
        """Test that get_settings returns singleton"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should be the same instance
        assert settings1 is settings2
    
    @patch('src.config.enhanced_settings._settings', None)
    def test_get_settings_reload(self):
        """Test settings reload functionality"""
        # Get initial settings
        settings1 = get_settings()
        initial_app_name = settings1.app_name
        
        # Reload with different environment
        with patch.dict(os.environ, {'APP_NAME': 'ReloadedBot'}):
            settings2 = get_settings(reload=True)
            
            assert settings2.app_name == "ReloadedBot"
            assert settings2.app_name != initial_app_name
    
    def test_get_settings_environment_specific(self):
        """Test environment-specific settings loading"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            settings = get_settings(reload=True)
            
            assert settings.environment == "production"
            assert settings.is_production is True
            
            # Production safety checks
            assert settings.features.enable_phi_scrubbing is True
            assert settings.features.enable_response_validation is True


class TestSettingsIntegration:
    """Integration tests for settings system"""
    
    def test_settings_with_all_features_enabled(self):
        """Test settings with comprehensive feature enablement"""
        test_env = {
            'ENVIRONMENT': 'staging',
            'FEATURES__SEARCH_BACKEND': 'hybrid',
            'FEATURES__ENABLE_HYBRID_SEARCH': 'true',
            'FEATURES__ENABLE_ELASTICSEARCH': 'true',
            'FEATURES__ENABLE_SOURCE_HIGHLIGHTING': 'true',
            'FEATURES__ENABLE_TABLE_EXTRACTION': 'true',
            'FEATURES__ENABLE_SEMANTIC_CACHE': 'true',
            'FEATURES__ENABLE_METRICS': 'true',
            'FEATURES__ENABLE_MEDICAL_METRICS': 'true'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = get_settings(reload=True)
            
            # All features should be enabled
            assert settings.features.search_backend == "hybrid"
            assert settings.features.enable_hybrid_search is True
            assert settings.features.enable_elasticsearch is True
            assert settings.features.enable_source_highlighting is True
            assert settings.features.enable_table_extraction is True
            assert settings.features.enable_semantic_cache is True
            assert settings.features.enable_metrics is True
            assert settings.features.enable_medical_metrics is True
            
            # Safety features should remain enabled
            assert settings.features.enable_phi_scrubbing is True
            assert settings.features.enable_response_validation is True
    
    def test_settings_production_constraints(self):
        """Test production environment constraints"""
        test_env = {
            'ENVIRONMENT': 'production',
            'FEATURES__ENABLE_STREAMLIT_DEMO': 'true',  # Should be ignored
            'FEATURES__ENABLE_PDF_VIEWER': 'true',      # Should be ignored
            'FEATURES__ENABLE_PHI_SCRUBBING': 'false'   # Should be overridden
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = get_settings(reload=True)
            
            assert settings.environment == "production"
            
            # Production safety overrides
            assert settings.features.enable_phi_scrubbing is True  # Must be True
            assert settings.features.enable_response_validation is True  # Must be True
            
            # Experimental features should be disabled in production
            assert settings.features.enable_streamlit_demo is False
            assert settings.features.enable_pdf_viewer is False
    
    def test_settings_configuration_summary(self):
        """Test configuration summary generation"""
        settings = get_settings()
        
        # Should have all required attributes for summary
        assert hasattr(settings, 'features')
        assert hasattr(settings, 'environment')
        assert hasattr(settings, 'llm_backend')
        assert hasattr(settings, 'hybrid_search')
        assert hasattr(settings, 'cache_config')
        assert hasattr(settings, 'observability')
        
        # Test that we can generate a summary without errors
        summary_fields = [
            settings.app_name,
            settings.environment,
            settings.llm_backend,
            settings.features.search_backend
        ]
        
        for field in summary_fields:
            assert field is not None
            assert isinstance(field, str)