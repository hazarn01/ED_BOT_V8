#!/usr/bin/env python3
"""
Quick Setup Validator for ED Bot v8
Run this to verify your environment is ready for first-time setup.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
import json


class SetupValidator:
    """Validates environment for ED Bot v8 setup."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.checks_passed = []
        self.checks_failed = []
        self.fixes_needed = []
        
    def check_python(self) -> bool:
        """Check Python version."""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 10:
            self.checks_passed.append(f"Python {version.major}.{version.minor}")
            return True
        else:
            self.checks_failed.append("Python 3.10+ required")
            self.fixes_needed.append("Install Python 3.10 or higher")
            return False
    
    def check_docker(self) -> bool:
        """Check Docker is installed and running."""
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Check if Docker daemon is running
                result = subprocess.run(
                    ["docker", "ps"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.checks_passed.append("Docker running")
                    return True
                else:
                    self.checks_failed.append("Docker daemon not running")
                    self.fixes_needed.append("Start Docker: sudo systemctl start docker")
                    return False
            else:
                self.checks_failed.append("Docker not working")
                return False
        except FileNotFoundError:
            self.checks_failed.append("Docker not installed")
            self.fixes_needed.append("Install Docker: https://docs.docker.com/get-docker/")
            return False
        except subprocess.TimeoutExpired:
            self.checks_failed.append("Docker timeout")
            return False
    
    def check_docker_compose(self) -> bool:
        """Check Docker Compose is installed."""
        commands = ["docker-compose", "docker compose"]
        
        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd.split() + ["version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.checks_passed.append("Docker Compose available")
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        self.checks_failed.append("Docker Compose not found")
        self.fixes_needed.append("Install Docker Compose plugin")
        return False
    
    def check_environment_file(self) -> bool:
        """Check for environment configuration."""
        env_file = self.project_root / ".env"
        env_example = self.project_root / "EDBOTv8.env.example"
        
        if env_file.exists():
            self.checks_passed.append(".env file exists")
            return True
        elif env_example.exists():
            self.checks_failed.append(".env file missing")
            self.fixes_needed.append("cp EDBOTv8.env.example .env")
            return False
        else:
            self.checks_failed.append("No environment config found")
            self.fixes_needed.append("Create .env file with required variables")
            return False
    
    def check_directories(self) -> bool:
        """Check required directories exist."""
        required = ["src", "docs", "tests", "scripts", "alembic"]
        missing = []
        
        for dir_name in required:
            if not (self.project_root / dir_name).exists():
                missing.append(dir_name)
        
        if missing:
            self.checks_failed.append(f"Missing directories: {', '.join(missing)}")
            self.fixes_needed.append("Repository may be incomplete - re-clone")
            return False
        else:
            self.checks_passed.append("All directories present")
            return True
    
    def check_makefile(self) -> bool:
        """Check Makefile exists."""
        if (self.project_root / "Makefile").exists():
            self.checks_passed.append("Makefile present")
            return True
        else:
            self.checks_failed.append("Makefile missing")
            self.fixes_needed.append("Makefile required for setup commands")
            return False
    
    def check_documents(self) -> bool:
        """Check for medical documents."""
        docs_dir = self.project_root / "docs"
        if docs_dir.exists():
            pdf_count = len(list(docs_dir.rglob("*.pdf")))
            if pdf_count > 0:
                self.checks_passed.append(f"{pdf_count} PDF documents found")
                return True
            else:
                self.checks_failed.append("No PDF documents found")
                self.fixes_needed.append("Add medical PDFs to docs/ directory")
                return False
        else:
            self.checks_failed.append("docs/ directory missing")
            return False
    
    def run_validation(self) -> bool:
        """Run all validation checks."""
        print("\n🏥 ED BOT v8 - SETUP VALIDATOR")
        print("="*50)
        
        checks = [
            ("Python Version", self.check_python),
            ("Docker", self.check_docker),
            ("Docker Compose", self.check_docker_compose),
            ("Environment File", self.check_environment_file),
            ("Project Structure", self.check_directories),
            ("Makefile", self.check_makefile),
            ("Medical Documents", self.check_documents)
        ]
        
        all_passed = True
        
        print("\n📋 Running checks...\n")
        
        for name, check_func in checks:
            print(f"  Checking {name}...", end=" ")
            if check_func():
                print("✅")
            else:
                print("❌")
                all_passed = False
        
        # Display results
        print("\n" + "="*50)
        
        if self.checks_passed:
            print("\n✅ PASSED:")
            for check in self.checks_passed:
                print(f"  • {check}")
        
        if self.checks_failed:
            print("\n❌ FAILED:")
            for check in self.checks_failed:
                print(f"  • {check}")
        
        if self.fixes_needed:
            print("\n🔧 FIXES NEEDED:")
            for i, fix in enumerate(self.fixes_needed, 1):
                print(f"  {i}. {fix}")
        
        print("\n" + "="*50)
        
        if all_passed:
            print("\n✅ READY FOR SETUP!")
            print("\n📦 Next steps:")
            print("  1. make bootstrap    # Install Python dependencies")
            print("  2. make up          # Start Docker services")
            print("  3. make migrate     # Create database schema")
            print("  4. make upgrade     # Apply migrations")
            print("  5. make seed        # Load medical documents")
            print("\n🚀 Or run all at once: make dev-setup")
        else:
            print("\n⚠️  FIX ISSUES ABOVE BEFORE PROCEEDING")
            print("\nAfter fixing, run this validator again:")
            print("  python scripts/validate_setup.py")
        
        # Save results
        results = {
            "passed": self.checks_passed,
            "failed": self.checks_failed,
            "fixes": self.fixes_needed,
            "ready": all_passed
        }
        
        results_file = self.project_root / "setup_validation.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📝 Results saved to: {results_file}")
        
        return all_passed


def main():
    """Run the setup validator."""
    validator = SetupValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()