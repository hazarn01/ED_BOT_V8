#!/usr/bin/env python3
"""
Create sample data directory structure and placeholder PDF files.
"""

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_data_directories():
    """Create the data directory structure."""
    base_path = Path(__file__).parent.parent / "data"
    
    directories = [
        "forms",
        "protocols", 
        "criteria",
        "references"
    ]
    
    for directory in directories:
        dir_path = base_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {dir_path}")

def create_placeholder_pdfs():
    """Create placeholder PDF files for testing."""
    base_path = Path(__file__).parent.parent / "data"
    
    # Simple PDF placeholder content
    pdf_placeholder = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 5 0 R
>>
>>
>>
endobj

4 0 obj
<<
/Length 53
>>
stream
BT
/F1 12 Tf
100 700 Td
(ED Bot v8 Sample Document) Tj
ET
endstream
endobj

5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj

xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000053 00000 n 
0000000110 00000 n 
0000000271 00000 n 
0000000376 00000 n 
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
456
%%EOF"""

    files = {
        "forms": [
            "blood_transfusion_consent.pdf",
            "discharge_instructions.pdf", 
            "admission_orders.pdf",
            "procedure_consent.pdf"
        ],
        "protocols": [
            "stemi_protocol.pdf",
            "stroke_protocol.pdf",
            "sepsis_protocol.pdf", 
            "trauma_protocol.pdf"
        ],
        "criteria": [
            "ottawa_ankle_rules.pdf",
            "wells_score.pdf",
            "centor_criteria.pdf"
        ],
        "references": [
            "emergency_drug_dosing.pdf",
            "pediatric_dosing.pdf"
        ]
    }
    
    for directory, file_list in files.items():
        dir_path = base_path / directory
        for filename in file_list:
            file_path = dir_path / filename
            if not file_path.exists():
                with open(file_path, 'wb') as f:
                    f.write(pdf_placeholder)
                logger.info(f"Created placeholder PDF: {file_path}")

def main():
    """Main function."""
    logger.info("Creating sample data structure...")
    create_data_directories()
    create_placeholder_pdfs()
    logger.info("Sample data creation completed!")

if __name__ == "__main__":
    main()