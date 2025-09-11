#!/usr/bin/env python3
"""
Validation script for Streamlit demo implementation (PRP 21).

Verifies that all components are properly implemented and functional.
"""

import sys
from pathlib import Path


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists and report status."""
    path = Path(filepath)
    if path.exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ Missing {description}: {filepath}")
        return False


def check_content_in_file(filepath: str, content: str, description: str) -> bool:
    """Check if specific content exists in a file."""
    path = Path(filepath)
    if not path.exists():
        print(f"❌ File not found for {description}: {filepath}")
        return False
    
    with open(path, 'r') as f:
        file_content = f.read()
        if content in file_content:
            print(f"✅ {description} found in {filepath}")
            return True
        else:
            print(f"❌ {description} not found in {filepath}")
            return False


def validate_streamlit_structure():
    """Validate Streamlit app directory structure."""
    print("\n📁 Validating Streamlit App Structure")
    print("=" * 50)
    
    checks = [
        ("streamlit_app/main.py", "Main Streamlit application"),
        ("streamlit_app/Dockerfile", "Streamlit Dockerfile"),
        ("streamlit_app/requirements.txt", "Streamlit requirements"),
        ("streamlit_app/pages/1_🔍_Advanced_Search.py", "Advanced Search page"),
        ("streamlit_app/pages/2_🗄️_Cache_Management.py", "Cache Management page"),
    ]
    
    results = []
    for filepath, description in checks:
        results.append(check_file_exists(filepath, description))
    
    return all(results)


def validate_streamlit_features():
    """Validate Streamlit app features."""
    print("\n✨ Validating Streamlit Features")
    print("=" * 50)
    
    checks = [
        ("streamlit_app/main.py", "EDBotClient", "API client class"),
        ("streamlit_app/main.py", "health_check", "Health check functionality"),
        ("streamlit_app/main.py", "get_cache_stats", "Cache statistics"),
        ("streamlit_app/main.py", "sample_queries", "Sample queries"),
        ("streamlit_app/main.py", "highlighted_sources", "Source highlighting support"),
        ("streamlit_app/pages/1_🔍_Advanced_Search.py", "SearchComparison", "Search comparison"),
        ("streamlit_app/pages/1_🔍_Advanced_Search.py", "Table Extraction", "Table extraction feature"),
        ("streamlit_app/pages/2_🗄️_Cache_Management.py", "CacheManager", "Cache management"),
        ("streamlit_app/pages/2_🗄️_Cache_Management.py", "invalidate_type", "Cache invalidation"),
    ]
    
    results = []
    for filepath, content, description in checks:
        results.append(check_content_in_file(filepath, content, description))
    
    return all(results)


def validate_docker_integration():
    """Validate Docker integration."""
    print("\n🐳 Validating Docker Integration")
    print("=" * 50)
    
    checks = [
        ("docker-compose.v8.yml", "streamlit:", "Streamlit service definition"),
        ("docker-compose.v8.yml", 'profiles: ["ui"]', "UI profile configuration"),
        ("docker-compose.v8.yml", "8501:8501", "Streamlit port mapping"),
        ("docker-compose.v8.yml", "edbot-streamlit", "Streamlit container name"),
    ]
    
    results = []
    for filepath, content, description in checks:
        results.append(check_content_in_file(filepath, content, description))
    
    return all(results)


def validate_makefile_commands():
    """Validate Makefile commands."""
    print("\n🔧 Validating Makefile Commands")
    print("=" * 50)
    
    checks = [
        ("Makefile.v8", "up-ui:", "up-ui command"),
        ("Makefile.v8", "ui-logs:", "ui-logs command"),
        ("Makefile.v8", "ui-build:", "ui-build command"),
        ("Makefile.v8", "ui-restart:", "ui-restart command"),
        ("Makefile.v8", "ui-stop:", "ui-stop command"),
    ]
    
    results = []
    for filepath, content, description in checks:
        results.append(check_content_in_file(filepath, content, description))
    
    return all(results)


def validate_configuration():
    """Validate configuration settings."""
    print("\n⚙️ Validating Configuration")
    print("=" * 50)
    
    checks = [
        ("src/config/settings.py", "enable_streamlit_demo", "Streamlit demo setting"),
        ("src/config/settings.py", "Streamlit demo UI (dev only)", "Streamlit setting description"),
    ]
    
    results = []
    for filepath, content, description in checks:
        results.append(check_content_in_file(filepath, content, description))
    
    return all(results)


def validate_tests():
    """Validate test files."""
    print("\n🧪 Validating Tests")
    print("=" * 50)
    
    checks = [
        ("tests/integration/test_streamlit_integration.py", "TestStreamlitIntegration", "Integration test class"),
        ("tests/integration/test_streamlit_integration.py", "test_streamlit_health", "Health test"),
        ("tests/integration/test_streamlit_integration.py", "test_api_connectivity", "API connectivity test"),
        ("tests/integration/test_streamlit_integration.py", "TestStreamlitFeatures", "Feature tests"),
    ]
    
    results = []
    for filepath, content, description in checks:
        results.append(check_content_in_file(filepath, content, description))
    
    return all(results)


def main():
    """Run all validation checks."""
    print("=" * 50)
    print("🎯 PRP 21: Streamlit Demo Validation")
    print("=" * 50)
    
    validation_functions = [
        validate_streamlit_structure,
        validate_streamlit_features,
        validate_docker_integration,
        validate_makefile_commands,
        validate_configuration,
        validate_tests,
    ]
    
    results = []
    for func in validation_functions:
        results.append(func())
    
    print("\n" + "=" * 50)
    print("📊 Validation Summary")
    print("=" * 50)
    
    total_checks = len(validation_functions)
    passed_checks = sum(results)
    
    print(f"Passed: {passed_checks}/{total_checks}")
    
    if all(results):
        print("\n✅ All validation checks passed!")
        print("\n📚 Next Steps:")
        print("1. Build the Streamlit container: make ui-build")
        print("2. Start the stack with UI: make up-ui")
        print("3. Access the demo at: http://localhost:8501")
        print("4. View logs: make ui-logs")
        print("\n🔒 Security Notes:")
        print("- UI is disabled by default (profiles: [ui])")
        print("- Never enable in production")
        print("- Read-only access to API")
        print("- No authentication (dev-only)")
        return 0
    else:
        print("\n❌ Some validation checks failed!")
        print("Please review the errors above and fix any missing components.")
        return 1


if __name__ == "__main__":
    sys.exit(main())