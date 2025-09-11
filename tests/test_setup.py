#!/usr/bin/env python3
"""
Comprehensive Setup Test Suite for ED Bot v8
Tests all components required for first-time setup and deployment.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
import psycopg2
import redis
import requests
from unittest import TestCase, main
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))


class SetupTestSuite(TestCase):
    """Comprehensive tests for first-time setup validation."""
    
    @classmethod
    def setUpClass(cls):
        """Initialize test suite with project paths."""
        cls.project_root = Path(__file__).parent.parent
        cls.docs_dir = cls.project_root / "docs"
        cls.src_dir = cls.project_root / "src"
        cls.results = {
            "timestamp": datetime.now().isoformat(),
            "tests_passed": 0,
            "tests_failed": 0,
            "warnings": [],
            "errors": []
        }
    
    def test_01_python_version(self):
        """Test Python version is 3.10+"""
        print("\n🔍 Checking Python version...")
        version_info = sys.version_info
        self.assertGreaterEqual(version_info.major, 3, "Python 3 required")
        self.assertGreaterEqual(version_info.minor, 10, "Python 3.10+ required")
        print(f"✅ Python {version_info.major}.{version_info.minor}.{version_info.micro}")
    
    def test_02_required_directories(self):
        """Test all required directories exist."""
        print("\n🔍 Checking required directories...")
        required_dirs = [
            "src",
            "docs",
            "tests",
            "alembic",
            "scripts",
            "src/api",
            "src/pipeline",
            "src/models",
            "src/cache",
            "src/ai"
        ]
        
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            self.assertTrue(
                dir_path.exists(),
                f"Required directory missing: {dir_name}"
            )
            print(f"  ✅ {dir_name}/")
    
    def test_03_environment_file(self):
        """Test environment configuration file exists."""
        print("\n🔍 Checking environment configuration...")
        env_file = self.project_root / ".env"
        env_example = self.project_root / "EDBOTv8.env.example"
        
        if not env_file.exists():
            self.assertTrue(
                env_example.exists(),
                "Neither .env nor EDBOTv8.env.example found"
            )
            print("  ⚠️  .env not found, but example exists")
            print("  📝 Run: cp EDBOTv8.env.example .env")
            self.results["warnings"].append("Environment file needs to be created from example")
        else:
            print("  ✅ .env file exists")
            
            # Check critical environment variables
            with open(env_file) as f:
                env_content = f.read()
                critical_vars = [
                    "DATABASE_URL",
                    "REDIS_URL",
                    "LLM_BACKEND",
                    "LOG_SCRUB_PHI",
                    "DISABLE_EXTERNAL_CALLS"
                ]
                for var in critical_vars:
                    if var not in env_content:
                        self.results["warnings"].append(f"Missing critical env var: {var}")
                        print(f"  ⚠️  Missing: {var}")
    
    def test_04_python_dependencies(self):
        """Test all required Python packages are installed."""
        print("\n🔍 Checking Python dependencies...")
        required_packages = [
            "fastapi",
            "sqlalchemy",
            "redis",
            "psycopg2-binary",
            "pydantic",
            "alembic",
            "numpy",
            "pytest",
            "uvicorn"
        ]
        
        missing = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                print(f"  ✅ {package}")
            except ImportError:
                missing.append(package)
                print(f"  ❌ {package} - NOT INSTALLED")
        
        if missing:
            self.results["errors"].append(f"Missing packages: {', '.join(missing)}")
            print(f"\n  📝 Run: pip install {' '.join(missing)}")
    
    def test_05_database_connection(self):
        """Test PostgreSQL database connectivity."""
        print("\n🔍 Testing PostgreSQL connection...")
        
        # Try to load database URL from environment
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/edbot")
        
        # Parse connection string
        try:
            # Extract components from URL
            if "@" in db_url:
                auth_part = db_url.split("@")[0].split("//")[1]
                host_part = db_url.split("@")[1]
                user_pass = auth_part.split(":")
                user = user_pass[0]
                password = user_pass[1] if len(user_pass) > 1 else ""
                host_db = host_part.split("/")
                host_port = host_db[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 5432
                database = host_db[1].split("?")[0] if len(host_db) > 1 else "edbot"
            else:
                # Default values
                host, port, user, password, database = "localhost", 5432, "postgres", "postgres", "edbot"
            
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                connect_timeout=5
            )
            conn.close()
            print(f"  ✅ Connected to PostgreSQL at {host}:{port}/{database}")
            
            # Check if tables exist
            conn = psycopg2.connect(
                host=host, port=port, user=user, 
                password=password, database=database
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count = cur.fetchone()[0]
            conn.close()
            
            if table_count == 0:
                print("  ⚠️  Database exists but has no tables")
                print("  📝 Run: make migrate && make upgrade")
                self.results["warnings"].append("Database needs migrations")
            else:
                print(f"  ✅ Database has {table_count} tables")
                
        except psycopg2.OperationalError as e:
            print(f"  ❌ Cannot connect to PostgreSQL: {e}")
            print("  📝 Run: docker-compose up -d postgres")
            self.results["errors"].append(f"PostgreSQL connection failed: {e}")
        except Exception as e:
            print(f"  ❌ Database test failed: {e}")
            self.results["errors"].append(f"Database test error: {e}")
    
    def test_06_redis_connection(self):
        """Test Redis connectivity."""
        print("\n🔍 Testing Redis connection...")
        
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            # Parse Redis URL
            if "://" in redis_url:
                host_part = redis_url.split("://")[1]
                host_port_db = host_part.split("/")
                host_port = host_port_db[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 6379
                db = int(host_port_db[1]) if len(host_port_db) > 1 else 0
            else:
                host, port, db = "localhost", 6379, 0
            
            r = redis.Redis(host=host, port=port, db=db, socket_connect_timeout=5)
            r.ping()
            print(f"  ✅ Connected to Redis at {host}:{port}/{db}")
            
            # Test basic operations
            r.set("test_key", "test_value", ex=10)
            value = r.get("test_key")
            self.assertEqual(value.decode() if value else "", "test_value")
            print("  ✅ Redis read/write working")
            
        except redis.ConnectionError as e:
            print(f"  ❌ Cannot connect to Redis: {e}")
            print("  📝 Run: docker-compose up -d redis")
            self.results["errors"].append(f"Redis connection failed: {e}")
        except Exception as e:
            print(f"  ❌ Redis test failed: {e}")
            self.results["errors"].append(f"Redis test error: {e}")
    
    def test_07_ollama_llm_service(self):
        """Test Ollama LLM service connectivity."""
        print("\n🔍 Testing Ollama LLM service...")
        
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        try:
            # Check if Ollama is running
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"  ✅ Ollama running at {ollama_url}")
                
                # Check for models
                models = response.json().get("models", [])
                if models:
                    print(f"  ✅ {len(models)} models available:")
                    for model in models[:3]:  # Show first 3
                        print(f"     - {model.get('name', 'unknown')}")
                else:
                    print("  ⚠️  No models installed")
                    print("  📝 Run: ollama pull llama3.1:13b")
                    self.results["warnings"].append("Ollama needs models installed")
            else:
                print(f"  ❌ Ollama not responding correctly")
                self.results["errors"].append("Ollama service not healthy")
                
        except requests.exceptions.ConnectionError:
            print(f"  ❌ Cannot connect to Ollama at {ollama_url}")
            print("  📝 Run: docker-compose up -d ollama")
            self.results["errors"].append("Ollama service not running")
        except Exception as e:
            print(f"  ❌ Ollama test failed: {e}")
            self.results["errors"].append(f"Ollama test error: {e}")
    
    def test_08_api_health_check(self):
        """Test API server health endpoint."""
        print("\n🔍 Testing API server...")
        
        api_url = "http://localhost:8001"
        
        try:
            response = requests.get(f"{api_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"  ✅ API server running at {api_url}")
                
                health_data = response.json()
                print(f"  ✅ Status: {health_data.get('status', 'unknown')}")
                
                # Check component health
                if "components" in health_data:
                    for component, status in health_data["components"].items():
                        icon = "✅" if status == "healthy" else "⚠️"
                        print(f"  {icon} {component}: {status}")
            else:
                print(f"  ❌ API server not healthy (status: {response.status_code})")
                self.results["errors"].append("API server not healthy")
                
        except requests.exceptions.ConnectionError:
            print(f"  ⚠️  API server not running at {api_url}")
            print("  📝 Run: make up or uvicorn src.api.app:app --reload")
            self.results["warnings"].append("API server not running")
        except Exception as e:
            print(f"  ❌ API test failed: {e}")
            self.results["errors"].append(f"API test error: {e}")
    
    def test_09_document_files(self):
        """Test medical document files are present."""
        print("\n🔍 Checking medical documents...")
        
        docs_dir = self.project_root / "docs"
        
        if not docs_dir.exists():
            print("  ❌ docs/ directory not found")
            self.results["errors"].append("Document directory missing")
            return
        
        # Count PDFs
        pdf_files = list(docs_dir.rglob("*.pdf"))
        print(f"  ✅ Found {len(pdf_files)} PDF documents")
        
        if len(pdf_files) < 100:
            print("  ⚠️  Expected 300+ medical documents")
            self.results["warnings"].append(f"Only {len(pdf_files)} documents found")
        
        # Check key document categories
        categories = {
            "protocols": 0,
            "forms": 0,
            "guidelines": 0,
            "criteria": 0
        }
        
        for pdf in pdf_files:
            for category in categories:
                if category in str(pdf).lower():
                    categories[category] += 1
        
        for category, count in categories.items():
            if count > 0:
                print(f"  ✅ {category}: {count} documents")
            else:
                print(f"  ⚠️  {category}: no documents found")
    
    def test_10_database_seeding(self):
        """Test if database has been seeded with documents."""
        print("\n🔍 Checking database seeding...")
        
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/edbot")
        
        try:
            # Parse and connect
            if "@" in db_url:
                auth_part = db_url.split("@")[0].split("//")[1]
                host_part = db_url.split("@")[1]
                user_pass = auth_part.split(":")
                user = user_pass[0]
                password = user_pass[1] if len(user_pass) > 1 else ""
                host_db = host_part.split("/")
                host_port = host_db[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 5432
                database = host_db[1].split("?")[0] if len(host_db) > 1 else "edbot"
            else:
                host, port, user, password, database = "localhost", 5432, "postgres", "postgres", "edbot"
            
            conn = psycopg2.connect(
                host=host, port=port, user=user,
                password=password, database=database,
                connect_timeout=5
            )
            cur = conn.cursor()
            
            # Check documents table
            cur.execute("SELECT COUNT(*) FROM documents WHERE 1=1")
            doc_count = cur.fetchone()[0]
            
            if doc_count > 0:
                print(f"  ✅ Database has {doc_count} documents")
                
                # Check chunks
                cur.execute("SELECT COUNT(*) FROM document_chunks WHERE 1=1")
                chunk_count = cur.fetchone()[0]
                print(f"  ✅ Database has {chunk_count} chunks")
            else:
                print("  ⚠️  Database has no documents")
                print("  📝 Run: make seed or python scripts/bulletproof_seeder.py")
                self.results["warnings"].append("Database needs seeding")
            
            conn.close()
            
        except psycopg2.ProgrammingError as e:
            if "does not exist" in str(e):
                print("  ⚠️  Tables not created yet")
                print("  📝 Run: make migrate && make upgrade")
                self.results["warnings"].append("Database tables need creation")
        except Exception as e:
            print(f"  ⚠️  Cannot check seeding: {e}")
            self.results["warnings"].append(f"Seeding check failed: {e}")
    
    def test_11_alembic_migrations(self):
        """Test Alembic migration status."""
        print("\n🔍 Checking database migrations...")
        
        alembic_ini = self.project_root / "alembic.ini"
        
        if not alembic_ini.exists():
            print("  ❌ alembic.ini not found")
            self.results["errors"].append("Alembic not configured")
            return
        
        try:
            # Check migration status
            result = subprocess.run(
                ["alembic", "current"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                if "head" in result.stdout or result.stdout.strip():
                    print("  ✅ Migrations are up to date")
                else:
                    print("  ⚠️  Migrations may need updating")
                    print("  📝 Run: make upgrade")
                    self.results["warnings"].append("Migrations may need updating")
            else:
                print("  ❌ Cannot check migration status")
                if "FAILED" in result.stderr:
                    print("  📝 Database connection issue")
                self.results["errors"].append("Migration check failed")
                
        except subprocess.TimeoutExpired:
            print("  ⚠️  Migration check timed out")
            self.results["warnings"].append("Migration check timeout")
        except FileNotFoundError:
            print("  ❌ Alembic not installed")
            print("  📝 Run: pip install alembic")
            self.results["errors"].append("Alembic not installed")
    
    def test_12_makefile_targets(self):
        """Test Makefile targets are available."""
        print("\n🔍 Checking Makefile targets...")
        
        makefile = self.project_root / "Makefile"
        
        if not makefile.exists():
            print("  ❌ Makefile not found")
            self.results["errors"].append("Makefile missing")
            return
        
        essential_targets = [
            "bootstrap", "up", "down", "migrate", 
            "upgrade", "seed", "test", "lint"
        ]
        
        with open(makefile) as f:
            content = f.read()
            found_targets = []
            for target in essential_targets:
                if f"{target}:" in content:
                    found_targets.append(target)
                    print(f"  ✅ make {target}")
                else:
                    print(f"  ❌ make {target} - NOT FOUND")
                    self.results["errors"].append(f"Missing make target: {target}")
        
        if len(found_targets) == len(essential_targets):
            print("\n  💡 Quick start: make dev-setup")
    
    def tearDown(self):
        """Track test results."""
        # Update counters based on test outcome
        pass
    
    @classmethod
    def tearDownClass(cls):
        """Generate final report."""
        print("\n" + "="*60)
        print("📊 SETUP TEST SUMMARY")
        print("="*60)
        
        if cls.results["errors"]:
            print(f"\n❌ {len(cls.results['errors'])} ERRORS:")
            for error in cls.results["errors"]:
                print(f"   - {error}")
        
        if cls.results["warnings"]:
            print(f"\n⚠️  {len(cls.results['warnings'])} WARNINGS:")
            for warning in cls.results["warnings"]:
                print(f"   - {warning}")
        
        if not cls.results["errors"] and not cls.results["warnings"]:
            print("\n✅ ALL SETUP TESTS PASSED!")
            print("\n🚀 Ready to start:")
            print("   1. make dev-setup  # Complete setup")
            print("   2. make up         # Start services")
            print("   3. make test       # Run tests")
        elif not cls.results["errors"]:
            print("\n✅ Setup mostly complete, address warnings above")
        else:
            print("\n❌ Setup incomplete, fix errors above")
            
        # Save results to file
        results_file = cls.project_root / "setup_test_results.json"
        with open(results_file, "w") as f:
            json.dump(cls.results, f, indent=2, default=str)
        print(f"\n📝 Results saved to: {results_file}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🏥 ED BOT v8 - SETUP TEST SUITE")
    print("="*60)
    print("Running comprehensive setup validation...\n")
    
    # Run tests
    main(argv=[''], exit=False, verbosity=0)