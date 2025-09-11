#!/usr/bin/env python3
"""
Complete development environment setup script for ED Bot v8.
Combines database initialization, sample data creation, and document seeding.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from create_sample_data import create_data_directories, create_placeholder_pdfs
from seed_documents import DocumentSeeder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_database_migrations():
    """Run database migrations."""
    logger.info("Running database migrations...")
    try:
        # Change to project root directory
        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        
        # Run alembic upgrade
        subprocess.run(
            ["python", "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("Database migrations completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Database migration failed: {e}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during migration: {e}")
        return False

def setup_complete_environment():
    """Set up complete development environment."""
    logger.info("Starting complete ED Bot v8 development environment setup...")
    
    try:
        # Step 1: Create data directories and placeholder files
        logger.info("Step 1: Creating sample data structure...")
        create_data_directories()
        create_placeholder_pdfs()
        
        # Step 2: Run database migrations
        logger.info("Step 2: Running database migrations...")
        if not run_database_migrations():
            logger.error("Database migration failed, continuing anyway...")
        
        # Step 3: Seed document registry
        logger.info("Step 3: Seeding document registry...")
        seeder = DocumentSeeder()
        seeder.seed_all()
        
        logger.info("🎉 Development environment setup completed successfully!")
        logger.info("Next steps:")
        logger.info("1. Start services: make up")
        logger.info("2. Test API: curl http://localhost:8001/health")
        logger.info("3. Test query: curl -X POST http://localhost:8001/api/v1/query -H 'Content-Type: application/json' -d '{\"query\": \"show me the blood transfusion form\"}'")
        
        return True
        
    except Exception as e:
        logger.error(f"Environment setup failed: {e}")
        return False

def verify_environment():
    """Verify the development environment is properly set up."""
    logger.info("Verifying development environment...")
    
    checks = []
    
    # Check data directories exist
    base_path = Path(__file__).parent.parent / "data"
    for directory in ["forms", "protocols", "criteria", "references"]:
        dir_path = base_path / directory
        checks.append(("Data directory exists", str(dir_path), dir_path.exists()))
    
    # Check sample PDFs exist
    sample_files = [
        "data/forms/blood_transfusion_consent.pdf",
        "data/protocols/stemi_protocol.pdf", 
        "data/criteria/ottawa_ankle_rules.pdf"
    ]
    
    project_root = Path(__file__).parent.parent
    for file_path in sample_files:
        full_path = project_root / file_path
        checks.append(("Sample PDF exists", str(file_path), full_path.exists()))
    
    # Check src modules can be imported
    try:
        from models.entities import Document
        checks.append(("Models import", "Document model", True))
    except ImportError:
        checks.append(("Models import", "Document model", False))
    
    # Print verification results
    logger.info("Environment verification results:")
    all_passed = True
    for check_name, item, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {status} {check_name}: {item}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("🎉 All environment checks passed!")
    else:
        logger.warning("⚠️ Some environment checks failed")
    
    return all_passed

def main():
    """Main setup function."""
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_environment()
    else:
        setup_complete_environment()

if __name__ == "__main__":
    main()