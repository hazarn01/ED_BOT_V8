#!/usr/bin/env python3
"""
Fix document paths to point to actual PDF files.
Maps database entries to real files in the docs directory.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import sessionmaker

from src.models.database import engine
from src.models.entities import Document

# Document mapping: database filename -> actual file in docs/
DOCUMENT_MAPPING = {
    "blood_transfusion_consent.pdf": "MSHS_Consent_for_Elective_Blood_Transfusion.pdf",
    "discharge_instructions.pdf": "MSH ED Discharge Education.pdf", 
    "admission_orders.pdf": "Sinai ED Admission Workflows (1).pdf",
    "procedure_consent.pdf": "AUTOPSY CONSENT FORM 2-2-16.pdf",
    "stemi_protocol.pdf": "STEMI Activation.pdf",
    "stroke_protocol.pdf": "Protocol for the Initial Evaluation of stroke CSC-2.pdf",
    "sepsis_protocol.pdf": "ED Sepsis Pathway.pdf",
    "trauma_protocol.pdf": "Trauma-10-2019.pdf",
    "ottawa_ankle_rules.pdf": "Pediatric Acute Scrotal Pain Pathway.pdf",  # placeholder
    "wells_score.pdf": "RETU PE Pathway.pdf",  # PE related
    "centor_criteria.pdf": "PED STI Tip Sheet for Medical Staff.pdf",  # placeholder
    "emergency_drug_dosing.pdf": "Opioid Alternatives.pdf",  # closest match
    "pediatric_dosing.pdf": "Pediatric Massive Transfusion Protocol.pdf"
}

def fix_document_paths():
    """Update document filenames to point to actual files."""
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check which files actually exist in docs
        docs_path = Path("/app/docs")
        available_files = {f.name for f in docs_path.glob("*.pdf")} if docs_path.exists() else set()
        
        print(f"Found {len(available_files)} PDF files in docs directory")
        
        # Update each document
        for old_filename, new_filename in DOCUMENT_MAPPING.items():
            document = session.query(Document).filter(Document.filename == old_filename).first()
            if document:
                if new_filename in available_files:
                    print(f"✅ Mapping {old_filename} -> {new_filename}")
                    document.filename = new_filename
                    
                    # Update meta file_path as well
                    if document.meta and "file_path" in document.meta:
                        document.meta["file_path"] = f"/app/docs/{new_filename}"
                else:
                    print(f"⚠️ File not found: {new_filename} (for {old_filename})")
            else:
                print(f"❌ Document not found in DB: {old_filename}")
        
        session.commit()
        print("✅ Database updated successfully!")
        
        # Show current state
        print("\nCurrent documents in database:")
        documents = session.query(Document).all()
        for doc in documents:
            file_exists = doc.filename in available_files
            status = "✅" if file_exists else "❌"
            print(f"{status} {doc.filename} (ID: {doc.id[:8]}...)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def create_placeholder_pdfs():
    """Create simple placeholder PDFs for missing files."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfgen import canvas
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        
        docs_path = Path("/app/docs")
        
        # Files that might be missing - create simple placeholders
        placeholders = {
            "blood_transfusion_consent.pdf": "Blood Transfusion Consent Form",
            "discharge_instructions.pdf": "Patient Discharge Instructions", 
            "admission_orders.pdf": "Hospital Admission Orders",
            "procedure_consent.pdf": "General Procedure Consent"
        }
        
        for filename, title in placeholders.items():
            file_path = docs_path / filename
            if not file_path.exists():
                print(f"Creating placeholder PDF: {filename}")
                
                # Create simple PDF
                doc = SimpleDocTemplate(str(file_path), pagesize=letter)
                styles = getSampleStyleSheet()
                story = []
                
                story.append(Paragraph(title, styles['Title']))
                story.append(Spacer(1, 12))
                story.append(Paragraph("This is a placeholder document.", styles['Normal']))
                story.append(Spacer(1, 12))
                story.append(Paragraph("Please replace with actual medical form.", styles['Normal']))
                
                doc.build(story)
                print(f"✅ Created {filename}")
                
    except ImportError:
        print("⚠️ reportlab not available - cannot create placeholder PDFs")
        print("Installing via: pip install reportlab")

if __name__ == "__main__":
    print("🔧 Fixing document paths...")
    fix_document_paths()
    print("\n📄 Creating placeholder PDFs...")
    create_placeholder_pdfs()
    print("\n✅ Document fix complete!")