#!/usr/bin/env python3
"""
Document registry seeding script for ED Bot v8.
Seeds the database with sample documents for testing and development.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy.orm import sessionmaker

from src.models.database import engine
from src.models.entities import Base, Document, ExtractedEntity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentSeeder:
    """Seeds the database with sample documents."""
    
    def __init__(self):
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        
    def seed_all(self):
        """Seed all document types."""
        logger.info("Starting document registry seeding...")
        
        try:
            # Clear existing data
            self._clear_existing_data()
            
            # Seed different document types
            self._seed_forms()
            self._seed_protocols() 
            self._seed_criteria_documents()
            self._seed_dosage_references()
            
            # Create sample extracted entities
            self._seed_extracted_entities()
            
            self.session.commit()
            logger.info("Document registry seeding completed successfully!")
            
        except Exception as e:
            logger.error(f"Seeding failed: {e}")
            self.session.rollback()
            raise
        finally:
            self.session.close()
    
    def _clear_existing_data(self):
        """Clear existing documents and entities."""
        logger.info("Clearing existing data...")
        self.session.query(ExtractedEntity).delete()
        self.session.query(Document).delete()
        self.session.commit()
    
    def _seed_forms(self):
        """Seed form documents."""
        logger.info("Seeding form documents...")
        
        forms = [
            {
                "filename": "blood_transfusion_consent.pdf",
                "title": "Blood Transfusion Consent Form",
                "doc_type": "form",
                "category": "consent",
                "content": "Blood transfusion consent form for emergency department use. Contains patient information, risks, benefits, and consent signature areas.",
                "file_path": "/app/data/forms/blood_transfusion_consent.pdf"
            },
            {
                "filename": "discharge_instructions.pdf", 
                "title": "Patient Discharge Instructions",
                "doc_type": "form",
                "category": "discharge",
                "content": "Standard discharge instructions form with follow-up care, medications, and warning signs to watch for.",
                "file_path": "/app/data/forms/discharge_instructions.pdf"
            },
            {
                "filename": "admission_orders.pdf",
                "title": "Hospital Admission Orders",
                "doc_type": "form", 
                "category": "admission",
                "content": "Standardized admission orders form for emergency department to inpatient transfers.",
                "file_path": "/app/data/forms/admission_orders.pdf"
            },
            {
                "filename": "procedure_consent.pdf",
                "title": "General Procedure Consent",
                "doc_type": "form",
                "category": "consent",
                "content": "General consent form for emergency procedures including risks, benefits, alternatives.",
                "file_path": "/app/data/forms/procedure_consent.pdf"
            }
        ]
        
        for form_data in forms:
            # Map to correct Document fields
            doc_data = {
                "filename": form_data["filename"],
                "content_type": form_data["doc_type"],
                "file_type": "pdf",
                "content": form_data["content"],
                "meta": {
                    "title": form_data["title"],
                    "category": form_data["category"],
                    "file_path": form_data["file_path"]
                },
                "created_at": datetime.utcnow()
            }
            doc = Document(**doc_data)
            self.session.add(doc)
            logger.info(f"Added form: {form_data['title']}")
    
    def _seed_protocols(self):
        """Seed protocol documents."""
        logger.info("Seeding protocol documents...")
        
        protocols = [
            {
                "filename": "stemi_protocol.pdf",
                "title": "STEMI Treatment Protocol",
                "doc_type": "protocol",
                "category": "cardiology",
                "content": "ST-elevation myocardial infarction treatment protocol with time-sensitive interventions. Door-to-balloon time <90 minutes critical.",
                "file_path": "/app/data/protocols/stemi_protocol.pdf"
            },
            {
                "filename": "stroke_protocol.pdf",
                "title": "Acute Stroke Protocol", 
                "doc_type": "protocol",
                "category": "neurology",
                "content": "Acute stroke assessment and treatment protocol including tPA administration guidelines and time windows.",
                "file_path": "/app/data/protocols/stroke_protocol.pdf"
            },
            {
                "filename": "sepsis_protocol.pdf",
                "title": "Sepsis Management Protocol",
                "doc_type": "protocol",
                "category": "emergency",
                "content": "Early sepsis recognition and management protocol with bundle elements and timing requirements.",
                "file_path": "/app/data/protocols/sepsis_protocol.pdf"
            },
            {
                "filename": "trauma_protocol.pdf",
                "title": "Trauma Activation Protocol",
                "doc_type": "protocol",
                "category": "trauma",
                "content": "Trauma team activation criteria and initial assessment protocol for emergency department.",
                "file_path": "/app/data/protocols/trauma_protocol.pdf"
            }
        ]
        
        for protocol_data in protocols:
            # Map to correct Document fields
            doc_data = {
                "filename": protocol_data["filename"],
                "content_type": protocol_data["doc_type"],
                "file_type": "pdf",
                "content": protocol_data["content"],
                "meta": {
                    "title": protocol_data["title"],
                    "category": protocol_data["category"],
                    "file_path": protocol_data["file_path"]
                },
                "created_at": datetime.utcnow()
            }
            doc = Document(**doc_data)
            self.session.add(doc)
            logger.info(f"Added protocol: {protocol_data['title']}")
    
    def _seed_criteria_documents(self):
        """Seed criteria documents."""
        logger.info("Seeding criteria documents...")
        
        criteria = [
            {
                "filename": "ottawa_ankle_rules.pdf",
                "title": "Ottawa Ankle Rules",
                "doc_type": "criteria",
                "category": "orthopedics",
                "content": "Clinical decision rules for ankle and midfoot fractures. Helps determine need for radiography.",
                "file_path": "/app/data/criteria/ottawa_ankle_rules.pdf"
            },
            {
                "filename": "wells_score.pdf",
                "title": "Wells Score for PE",
                "doc_type": "criteria", 
                "category": "pulmonary",
                "content": "Wells clinical prediction rule for pulmonary embolism probability assessment.",
                "file_path": "/app/data/criteria/wells_score.pdf"
            },
            {
                "filename": "centor_criteria.pdf",
                "title": "Centor Criteria for Strep Throat",
                "doc_type": "criteria",
                "category": "infectious_disease",
                "content": "Clinical prediction rule for group A streptococcal pharyngitis likelihood.",
                "file_path": "/app/data/criteria/centor_criteria.pdf"
            }
        ]
        
        for criteria_data in criteria:
            # Map to correct Document fields
            doc_data = {
                "filename": criteria_data["filename"],
                "content_type": criteria_data["doc_type"],
                "file_type": "pdf",
                "content": criteria_data["content"],
                "meta": {
                    "title": criteria_data["title"],
                    "category": criteria_data["category"],
                    "file_path": criteria_data["file_path"]
                },
                "created_at": datetime.utcnow()
            }
            doc = Document(**doc_data)
            self.session.add(doc)
            logger.info(f"Added criteria: {criteria_data['title']}")
    
    def _seed_dosage_references(self):
        """Seed dosage reference documents."""
        logger.info("Seeding dosage references...")
        
        dosages = [
            {
                "filename": "emergency_drug_dosing.pdf",
                "title": "Emergency Department Drug Dosing Reference",
                "doc_type": "reference",
                "category": "pharmacology",
                "content": "Comprehensive drug dosing reference for emergency department medications including contraindications and monitoring.",
                "file_path": "/app/data/references/emergency_drug_dosing.pdf"
            },
            {
                "filename": "pediatric_dosing.pdf",
                "title": "Pediatric Drug Dosing Guide",
                "doc_type": "reference",
                "category": "pediatrics",
                "content": "Age and weight-based dosing calculations for pediatric emergency medications.",
                "file_path": "/app/data/references/pediatric_dosing.pdf"
            }
        ]
        
        for dosage_data in dosages:
            # Map to correct Document fields
            doc_data = {
                "filename": dosage_data["filename"],
                "content_type": dosage_data["doc_type"],
                "file_type": "pdf",
                "content": dosage_data["content"],
                "meta": {
                    "title": dosage_data["title"],
                    "category": dosage_data["category"],
                    "file_path": dosage_data["file_path"]
                },
                "created_at": datetime.utcnow()
            }
            doc = Document(**doc_data)
            self.session.add(doc)
            logger.info(f"Added dosage reference: {dosage_data['title']}")
    
    def _seed_extracted_entities(self):
        """Seed sample extracted entities."""
        logger.info("Seeding extracted entities...")
        
        # Get document IDs
        stemi_doc = self.session.query(Document).filter(
            Document.filename == "stemi_protocol.pdf"
        ).first()
        
        drug_doc = self.session.query(Document).filter(
            Document.filename == "emergency_drug_dosing.pdf"
        ).first()
        
        ankle_doc = self.session.query(Document).filter(
            Document.filename == "ottawa_ankle_rules.pdf"
        ).first()
        
        if stemi_doc:
            # STEMI protocol entity
            stemi_entity = ExtractedEntity(
                document_id=stemi_doc.id,
                entity_type="protocol",
                payload={
                    "name": "STEMI Protocol",
                    "steps": [
                        {"action": "Obtain 12-lead ECG", "timing": "within 10 minutes"},
                        {"action": "Activate cardiac catheterization lab", "timing": "immediate"},
                        {"action": "Administer aspirin 325mg", "timing": "immediate"},
                        {"action": "Administer loading dose clopidogrel 600mg", "timing": "immediate"},
                        {"action": "Transport to cardiac catheterization lab", "timing": "within 90 minutes"}
                    ],
                    "critical_timing": "Door-to-balloon time must be <90 minutes"
                },
                confidence=0.95,
                evidence_text="STEMI Protocol: Door-to-balloon time <90 minutes critical",
                page_no=1
            )
            self.session.add(stemi_entity)
        
        if drug_doc:
            # Epinephrine dosage entity
            epi_entity = ExtractedEntity(
                document_id=drug_doc.id,
                entity_type="dosage",
                payload={
                    "drug": "Epinephrine",
                    "dose": "1mg (1:10,000)",
                    "route": "IV/IO",
                    "frequency": "every 3-5 minutes",
                    "max_dose": "No maximum in cardiac arrest",
                    "contraindications": ["None in cardiac arrest"],
                    "monitoring": ["Heart rhythm", "Blood pressure", "Pulse"]
                },
                confidence=0.98,
                evidence_text="Epinephrine 1mg IV/IO every 3-5 minutes during cardiac arrest",
                page_no=15
            )
            self.session.add(epi_entity)
            
            # Amiodarone dosage entity  
            amio_entity = ExtractedEntity(
                document_id=drug_doc.id,
                entity_type="dosage",
                payload={
                    "drug": "Amiodarone",
                    "dose": "300mg IV",
                    "route": "IV",
                    "frequency": "once, then 150mg",
                    "max_dose": "450mg in 24 hours",
                    "contraindications": ["Severe bradycardia", "AV block"],
                    "monitoring": ["Heart rhythm", "Blood pressure", "Liver function"]
                },
                confidence=0.92,
                evidence_text="Amiodarone 300mg IV for VF/VT, then 150mg",
                page_no=23
            )
            self.session.add(amio_entity)
        
        if ankle_doc:
            # Ottawa ankle rules entity
            ankle_entity = ExtractedEntity(
                document_id=ankle_doc.id,
                entity_type="criteria",
                payload={
                    "name": "Ottawa Ankle Rules",
                    "thresholds": [
                        "Pain in malleolar zone AND bone tenderness at posterior edge or tip of lateral malleolus",
                        "Pain in malleolar zone AND bone tenderness at posterior edge or tip of medial malleolus", 
                        "Pain in midfoot zone AND bone tenderness at base of 5th metatarsal",
                        "Pain in midfoot zone AND bone tenderness at navicular",
                        "Inability to bear weight both immediately and in emergency department"
                    ],
                    "sensitivity": "97-99%",
                    "specificity": "40-79%"
                },
                confidence=0.96,
                evidence_text="Ottawa Ankle Rules have 97-99% sensitivity for detecting fractures",
                page_no=1
            )
            self.session.add(ankle_entity)
        
        logger.info("Added sample extracted entities")

def main():
    """Main seeding function."""
    seeder = DocumentSeeder()
    seeder.seed_all()

if __name__ == "__main__":
    main()