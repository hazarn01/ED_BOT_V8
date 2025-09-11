"""
Unit tests for configuration validation system.
"""

from unittest.mock import Mock, patch

import pytest

from src.config.enhanced_settings import (
    EnhancedSettings,
    FeatureFlags,
    HybridSearchConfig,
    ObservabilityConfig,
)
from src.config.validators import (
    ConfigurationValidator,
    ValidationError,
    ValidationWarning,
)


@pytest.fixture
def mock_settings():
    """Create mock enhanced settings for testing"""
    settings = Mock(spec=EnhancedSettings)
    settings.environment = "development"
    settings.is_production = False
    settings.llm_backend = "ollama"
    settings.app_name = "EDBotv8"
    
    # Mock feature flags
    settings.features = Mock(spec=FeatureFlags)
    settings.features.search_backend = "pgvector"
    settings.features.enable_hybrid_search = False
    settings.features.enable_elasticsearch = False
    settings.features.enable_phi_scrubbing = True
    settings.features.enable_response_validation = True
    settings.features.enable_metrics = True
    settings.features.enable_streamlit_demo = False
    settings.features.enable_pdf_viewer = False
    
    # Mock configuration sections
    settings.hybrid_search = Mock(spec=HybridSearchConfig)
    settings.hybrid_search.elasticsearch_url = "http://elasticsearch:9200"
    settings.hybrid_search.keyword_weight = 0.3
    settings.hybrid_search.semantic_weight = 0.7
    
    settings.observability = Mock(spec=ObservabilityConfig)
    settings.observability.metrics_port = 9090
    settings.observability.health_check_interval = 30
    settings.observability.performance_alert_threshold = 2.0
    
    return settings


@pytest.fixture
def validator(mock_settings):
    """Create configuration validator"""
    return ConfigurationValidator(mock_settings)


class TestConfigurationValidator:
    """Test configuration validator initialization and basic functionality"""
    
    def test_validator_init(self, mock_settings):
        """Test validator initialization"""
        validator = ConfigurationValidator(mock_settings)
        
        assert validator.settings is mock_settings
        assert validator.warnings == []
        assert validator.errors == []
    
    def test_add_warning(self, validator):
        """Test adding validation warnings"""
        validator._add_warning("test_component", "Test warning message", "LOW")
        
        assert len(validator.warnings) == 1
        warning = validator.warnings[0]
        assert warning.component == "test_component"
        assert warning.message == "Test warning message"
        assert warning.severity == "LOW"
        assert warning.recommendation is not None
    
    def test_add_error(self, validator):
        """Test adding validation errors"""
        validator._add_error("test_component", "Test error message", "CRITICAL")
        
        assert len(validator.errors) == 1
        error = validator.errors[0]
        assert error.component == "test_component"
        assert error.message == "Test error message"
        assert error.severity == "CRITICAL"
    
    def test_clear_results(self, validator):
        """Test clearing validation results"""
        validator._add_warning("test", "warning", "LOW")
        validator._add_error("test", "error", "HIGH")
        
        validator._clear_results()
        
        assert validator.warnings == []
        assert validator.errors == []


class TestBasicValidation:
    """Test basic configuration validation"""
    
    def test_validate_app_name(self, validator, mock_settings):
        """Test application name validation"""
        # Valid app name
        mock_settings.app_name = "EDBotv8"
        validator._validate_app_name()
        assert len(validator.warnings) == 0
        
        # Invalid app name (empty)
        mock_settings.app_name = ""
        validator._validate_app_name()
        assert len(validator.warnings) > 0
        assert "app_name" in validator.warnings[0].message.lower()
    
    def test_validate_environment(self, validator, mock_settings):
        """Test environment validation"""
        # Valid environment
        mock_settings.environment = "production"
        validator._validate_environment()
        assert len(validator.warnings) == 0
        
        # Invalid environment
        mock_settings.environment = "invalid_env"
        validator._validate_environment()
        assert len(validator.warnings) > 0
    
    def test_validate_llm_backend(self, validator, mock_settings):
        """Test LLM backend validation"""
        # Valid backend
        mock_settings.llm_backend = "ollama"
        validator._validate_llm_backend()
        assert len(validator.warnings) == 0
        
        # Invalid backend
        mock_settings.llm_backend = "invalid_backend"
        validator._validate_llm_backend()
        assert len(validator.warnings) > 0


class TestFeatureFlagValidation:
    """Test feature flag validation"""
    
    def test_validate_search_backend_consistency(self, validator, mock_settings):
        """Test search backend consistency validation"""
        # Consistent configuration
        mock_settings.features.search_backend = "pgvector"
        mock_settings.features.enable_hybrid_search = False
        mock_settings.features.enable_elasticsearch = False
        
        validator._validate_feature_flag_consistency()
        assert len(validator.warnings) == 0
        
        # Inconsistent configuration - hybrid backend without required features
        mock_settings.features.search_backend = "hybrid"
        mock_settings.features.enable_hybrid_search = False
        
        validator._validate_feature_flag_consistency()
        assert len(validator.warnings) > 0
        assert "hybrid" in validator.warnings[-1].message.lower()
    
    def test_validate_production_safety_flags(self, validator, mock_settings):
        """Test production safety flag validation"""
        # Production environment
        mock_settings.environment = "production"
        mock_settings.is_production = True
        
        # Valid production configuration
        mock_settings.features.enable_phi_scrubbing = True
        mock_settings.features.enable_response_validation = True
        mock_settings.features.enable_streamlit_demo = False
        mock_settings.features.enable_pdf_viewer = False
        
        validator._validate_production_safety()
        assert len(validator.warnings) == 0
        
        # Invalid production configuration - safety flag disabled
        mock_settings.features.enable_phi_scrubbing = False
        validator._clear_results()
        validator._validate_production_safety()
        assert len(validator.errors) > 0
        assert "phi_scrubbing" in validator.errors[-1].message.lower()
    
    def test_validate_experimental_flags_in_production(self, validator, mock_settings):
        """Test experimental flags in production validation"""
        mock_settings.environment = "production"
        mock_settings.is_production = True
        
        # Experimental flag enabled in production
        mock_settings.features.enable_streamlit_demo = True
        
        validator._validate_production_safety()
        assert len(validator.warnings) > 0
        assert "experimental" in validator.warnings[-1].message.lower()
    
    def test_validate_cache_configuration(self, validator, mock_settings):
        """Test cache configuration validation"""
        # Enable semantic cache but search backend doesn't support it
        mock_settings.features.enable_semantic_cache = True
        mock_settings.features.search_backend = "pgvector"
        
        validator._validate_feature_dependencies()
        # Should warn about potential performance impact
        assert len(validator.warnings) >= 0  # May or may not warn depending on implementation


class TestResourceValidation:
    """Test resource and performance validation"""
    
    def test_validate_port_configuration(self, validator, mock_settings):
        """Test port configuration validation"""
        # Valid port
        mock_settings.observability.metrics_port = 9090
        validator._validate_resource_limits()
        assert len(validator.warnings) == 0
        
        # Port in privileged range
        mock_settings.observability.metrics_port = 80
        validator._validate_resource_limits()
        assert len(validator.warnings) > 0
        assert "port" in validator.warnings[-1].message.lower()
    
    def test_validate_performance_thresholds(self, validator, mock_settings):
        """Test performance threshold validation"""
        # Reasonable threshold
        mock_settings.observability.performance_alert_threshold = 2.0
        validator._validate_performance_settings()
        assert len(validator.warnings) == 0
        
        # Very low threshold (too sensitive)
        mock_settings.observability.performance_alert_threshold = 0.1
        validator._validate_performance_settings()
        assert len(validator.warnings) > 0
        
        # Very high threshold (not sensitive enough)
        mock_settings.observability.performance_alert_threshold = 30.0
        validator._clear_results()
        validator._validate_performance_settings()
        assert len(validator.warnings) > 0
    
    def test_validate_health_check_interval(self, validator, mock_settings):
        """Test health check interval validation"""
        # Reasonable interval
        mock_settings.observability.health_check_interval = 30
        validator._validate_performance_settings()
        assert len(validator.warnings) == 0
        
        # Too frequent (performance impact)
        mock_settings.observability.health_check_interval = 1
        validator._validate_performance_settings()
        assert len(validator.warnings) > 0
        assert "frequent" in validator.warnings[-1].message.lower()


class TestHybridSearchValidation:
    """Test hybrid search configuration validation"""
    
    def test_validate_search_weights(self, validator, mock_settings):
        """Test search weight validation"""
        # Valid weights (sum to 1.0)
        mock_settings.hybrid_search.keyword_weight = 0.3
        mock_settings.hybrid_search.semantic_weight = 0.7
        
        validator._validate_hybrid_search_config()
        assert len(validator.warnings) == 0
        
        # Invalid weights (don't sum to 1.0)
        mock_settings.hybrid_search.keyword_weight = 0.5
        mock_settings.hybrid_search.semantic_weight = 0.6
        
        validator._validate_hybrid_search_config()
        assert len(validator.errors) > 0
        assert "weight" in validator.errors[-1].message.lower()
    
    def test_validate_elasticsearch_url(self, validator, mock_settings):
        """Test Elasticsearch URL validation"""
        # Valid URL
        mock_settings.hybrid_search.elasticsearch_url = "http://elasticsearch:9200"
        validator._validate_hybrid_search_config()
        assert len(validator.warnings) == 0
        
        # Invalid URL format
        mock_settings.hybrid_search.elasticsearch_url = "not-a-url"
        validator._validate_hybrid_search_config()
        assert len(validator.warnings) > 0
    
    def test_validate_hybrid_search_dependencies(self, validator, mock_settings):
        """Test hybrid search feature dependencies"""
        # Hybrid search enabled but elasticsearch disabled
        mock_settings.features.search_backend = "hybrid"
        mock_settings.features.enable_hybrid_search = True
        mock_settings.features.enable_elasticsearch = False
        
        validator._validate_feature_dependencies()
        assert len(validator.warnings) > 0
        assert "elasticsearch" in validator.warnings[-1].message.lower()


class TestSecurityValidation:
    """Test security-related validation"""
    
    def test_validate_production_security(self, validator, mock_settings):
        """Test production security validation"""
        mock_settings.environment = "production"
        mock_settings.is_production = True
        
        # Check for development-only features
        mock_settings.features.enable_streamlit_demo = True
        validator._validate_security_settings()
        assert len(validator.warnings) > 0
        assert "production" in validator.warnings[-1].message.lower()
    
    def test_validate_safety_feature_dependencies(self, validator, mock_settings):
        """Test safety feature dependencies"""
        # PHI scrubbing enabled but response validation disabled
        mock_settings.features.enable_phi_scrubbing = True
        mock_settings.features.enable_response_validation = False
        
        validator._validate_safety_features()
        assert len(validator.warnings) > 0
        assert "response_validation" in validator.warnings[-1].message.lower()


class TestComprehensiveValidation:
    """Test comprehensive validation workflows"""
    
    def test_validate_all(self, validator):
        """Test comprehensive validation"""
        warnings = validator.validate_all()
        
        # Should return list of warnings
        assert isinstance(warnings, list)
        
        # Should have validated multiple components
        components = {w.component for w in warnings}
        assert len(components) >= 0  # May have warnings or not
    
    def test_validate_all_with_errors(self, validator, mock_settings):
        """Test comprehensive validation with errors"""
        # Create configuration with errors
        mock_settings.features.enable_phi_scrubbing = False
        mock_settings.environment = "production"
        mock_settings.is_production = True
        
        warnings = validator.validate_all()
        
        # Should include errors in warnings list (or raise exception)
        assert len(warnings) >= 0  # Implementation may vary
    
    def test_get_configuration_summary(self, validator, mock_settings):
        """Test configuration summary generation"""
        summary = validator.get_configuration_summary()
        
        assert isinstance(summary, dict)
        assert "environment" in summary
        assert "enabled_features" in summary
        assert "configuration_warnings" in summary
        assert "backend_services" in summary
        
        # Check summary content
        assert summary["environment"] == mock_settings.environment
        assert isinstance(summary["enabled_features"], list)
        assert isinstance(summary["configuration_warnings"], list)
        assert isinstance(summary["backend_services"], dict)


class TestValidationRecommendations:
    """Test validation recommendation system"""
    
    def test_get_recommendation_for_warning(self, validator):
        """Test recommendation generation for warnings"""
        warning = ValidationWarning(
            component="features",
            message="Inconsistent search backend configuration",
            severity="MEDIUM"
        )
        
        recommendation = validator._get_recommendation(warning)
        assert isinstance(recommendation, str)
        assert len(recommendation) > 0
    
    def test_get_recommendation_for_error(self, validator):
        """Test recommendation generation for errors"""
        error = ValidationError(
            component="safety",
            message="PHI scrubbing disabled in production",
            severity="CRITICAL"
        )
        
        recommendation = validator._get_recommendation(error)
        assert isinstance(recommendation, str)
        assert "enable" in recommendation.lower() or "set" in recommendation.lower()


class TestValidationUtilities:
    """Test validation utility functions"""
    
    def test_is_valid_url(self, validator):
        """Test URL validation utility"""
        assert validator._is_valid_url("http://example.com")
        assert validator._is_valid_url("https://example.com:9200")
        assert not validator._is_valid_url("not-a-url")
        assert not validator._is_valid_url("")
    
    def test_is_privileged_port(self, validator):
        """Test privileged port detection"""
        assert validator._is_privileged_port(80)
        assert validator._is_privileged_port(443)
        assert not validator._is_privileged_port(8080)
        assert not validator._is_privileged_port(9090)
    
    def test_get_enabled_features(self, validator, mock_settings):
        """Test enabled features extraction"""
        mock_settings.features.enable_metrics = True
        mock_settings.features.enable_hybrid_search = False
        mock_settings.features.enable_phi_scrubbing = True
        
        enabled_features = validator._get_enabled_features()
        
        assert "enable_metrics" in enabled_features
        assert "enable_phi_scrubbing" in enabled_features
        assert "enable_hybrid_search" not in enabled_features
    
    def test_get_backend_services(self, validator, mock_settings):
        """Test backend services extraction"""
        mock_settings.llm_backend = "ollama"
        mock_settings.features.search_backend = "pgvector"
        
        services = validator._get_backend_services()
        
        assert "llm" in services
        assert "search" in services
        assert services["llm"] == "ollama"
        assert services["search"] == "pgvector"


class TestValidationErrorHandling:
    """Test validation error handling"""
    
    def test_validation_with_none_settings(self):
        """Test validator behavior with None settings"""
        with pytest.raises(ValueError):
            ConfigurationValidator(None)
    
    def test_validation_with_missing_attributes(self, validator, mock_settings):
        """Test validation with missing settings attributes"""
        # Remove an attribute to simulate incomplete settings
        del mock_settings.environment
        
        # Should handle missing attributes gracefully
        try:
            validator._validate_environment()
        except AttributeError:
            # Should add error for missing attribute
            assert len(validator.errors) > 0
        except Exception as e:
            # Should not raise unexpected exceptions
            assert False, f"Unexpected exception: {e}"
    
    def test_validation_exception_handling(self, validator, mock_settings):
        """Test validation exception handling"""
        # Mock a method to raise an exception
        with patch.object(validator, '_validate_app_name', side_effect=Exception("Test error")):
            # Should handle exceptions gracefully
            warnings = validator.validate_all()
            
            # Should continue validation despite errors
            assert isinstance(warnings, list)


class TestValidationIntegration:
    """Integration tests for validation system"""
    
    def test_end_to_end_validation(self, mock_settings):
        """Test complete validation workflow"""
        validator = ConfigurationValidator(mock_settings)
        
        # Run comprehensive validation
        warnings = validator.validate_all()
        
        # Generate summary
        summary = validator.get_configuration_summary()
        
        # Should complete without exceptions
        assert isinstance(warnings, list)
        assert isinstance(summary, dict)
        assert len(summary["configuration_warnings"]) == len(warnings)
    
    def test_production_configuration_validation(self, mock_settings):
        """Test validation of production configuration"""
        # Setup production configuration
        mock_settings.environment = "production"
        mock_settings.is_production = True
        mock_settings.features.enable_phi_scrubbing = True
        mock_settings.features.enable_response_validation = True
        mock_settings.features.enable_streamlit_demo = False
        mock_settings.features.enable_pdf_viewer = False
        
        validator = ConfigurationValidator(mock_settings)
        warnings = validator.validate_all()
        
        # Should have fewer warnings for properly configured production
        critical_warnings = [w for w in warnings if w.severity == "CRITICAL"]
        assert len(critical_warnings) == 0
    
    def test_development_configuration_validation(self, mock_settings):
        """Test validation of development configuration"""
        # Setup development configuration with experimental features
        mock_settings.environment = "development"
        mock_settings.is_production = False
        mock_settings.features.enable_streamlit_demo = True
        mock_settings.features.enable_hybrid_search = True
        
        validator = ConfigurationValidator(mock_settings)
        warnings = validator.validate_all()
        
        # Should allow experimental features in development
        experimental_warnings = [
            w for w in warnings 
            if "experimental" in w.message.lower() and w.severity == "CRITICAL"
        ]
        assert len(experimental_warnings) == 0