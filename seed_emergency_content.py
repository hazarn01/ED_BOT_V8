#!/usr/bin/env python3
"""Quick seed script for essential medical content."""

import os
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://edbot:edbot@localhost:5432/edbot_v8')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def seed_essential_content():
    """Seed essential medical content for testing."""
    session = Session()
    
    try:
        # Clear existing data
        session.execute(text("DELETE FROM document_chunks"))
        session.execute(text("DELETE FROM document_registry"))
        session.execute(text("DELETE FROM documents"))
        session.commit()
        
        print("🗑️  Cleared existing data")
        
        # Essential medical content
        medical_content = [
            {
                'name': 'STEMI Protocol',
                'content': """STEMI ACTIVATION PROTOCOL
                
Door-to-balloon goal: 90 minutes
STEMI Pager: (917) 827-9725
Cath Lab Direct: x40935

IMMEDIATE ACTIONS:
1. EKG within 10 minutes of arrival
2. Activate STEMI protocol if criteria met
3. Notify cath lab team via pager
4. Upgrade patient to RESUS
5. Administer STEMI pack medications

STEMI PACK:
- ASA 324mg (chewed)
- Brillinta 180mg
- Crestor 80mg  
- Heparin 4000 units IV bolus

KEY CONTACTS:
- STEMI Pager: (917) 827-9725
- Cath Lab: x40935
- Cardiology Fellow on call""",
                'type': 'protocol'
            },
            {
                'name': 'Sepsis Pathway',
                'content': """ED SEPSIS PATHWAY

SEVERITY CRITERIA:
- Severe sepsis: Lactate > 2
- Septic shock: Lactate > 4

INITIAL ACTIONS (0-60 minutes):
1. Draw lactate immediately
2. Start IVF and antibiotics based on verbal orders
3. Use Adult Sepsis Order Set
4. Document with Initial Sepsis Note template

3-HOUR REASSESSMENT:
- Repeat lactate measurement
- Post-fluid blood pressure check
- Focused re-examination including cardiovascular assessment
- Use Sepsis Reassessment Note template
- RN + PA/MD huddle required

CRITICAL ELEMENTS:
- Early recognition improves outcomes
- Bundle compliance tracked
- Handoff outstanding tasks in .edadmit note""",
                'type': 'protocol'
            },
            {
                'name': 'Anaphylaxis Treatment',
                'content': """ANAPHYLAXIS TREATMENT GUIDELINE

FIRST-LINE TREATMENT:
Adult: Epinephrine 1mg/mL (1:1000) injection, 0.5mg IM
Pediatric: 0.01mg/kg IM

DIAGNOSTIC CRITERIA:
1. Acute onset illness with skin/mucosal involvement plus respiratory compromise, reduced BP, or severe GI symptoms
2. Acute onset hypotension/bronchospasm/laryngeal involvement after known allergen exposure

SECOND-LINE TREATMENTS:
- Benadryl/Diphenhydramine (antihistamine)
- Prednisone or Methylprednisolone (steroid)
- Famotidine (H2 blocker)
- Albuterol nebulization if wheezing

REFRACTORY ANAPHYLAXIS:
- Epinephrine drip at 0.1 mcg/kg/min
- Consider glucagon for patients on beta-blockers
- Early intubation if airway involvement

MONITORING:
- Observe 4-6 hours after epinephrine
- Discharge with EpiPen and allergist referral""",
                'type': 'guideline'
            },
            {
                'name': 'Hypoglycemia Protocol',
                'content': """HYPOGLYCEMIA TREATMENT

DEFINITION: Blood glucose <70 mg/dL

CONSCIOUS PATIENTS WITH IV ACCESS:
- Give 50mL (25g) D50 IV over 2-5 minutes
- Repeat if POCG remains <100

CONSCIOUS PATIENTS - ORAL (not NPO):
- 15-20 grams rapid-acting carbohydrates
- Can repeat twice every 15 minutes until POCG>100
- Examples: 4 glucose tablets, 8 saltine crackers, 1/2 cup fruit juice

UNCONSCIOUS PATIENTS:
- Check ABCs, place on monitor
- Without IV: Glucagon 1mg IM, can repeat x1 every 15 minutes
- With IV: 50mL (25g) D50 IV over 2-5 minutes

SPECIAL CONSIDERATIONS:
- Malnourished: Glucagon may not work (no glycogen stores)
- Add thiamine but don't delay glucose
- If refractory: consider IV glucocorticoid for adrenal insufficiency""",
                'type': 'guideline'
            }
        ]
        
        # Insert documents
        for doc in medical_content:
            doc_id = str(uuid.uuid4())
            
            # Insert document
            session.execute(text("""
                INSERT INTO documents (id, filename, content, content_type, file_type, created_at)
                VALUES (:id, :filename, :content, :content_type, 'text', :created_at)
            """), {
                'id': doc_id,
                'filename': f"{doc['name']}.txt",
                'content': doc['content'],
                'content_type': doc['type'],
                'created_at': datetime.utcnow()
            })
            
            # Create chunks (split by paragraphs)
            chunks = [c.strip() for c in doc['content'].split('\n\n') if c.strip()]
            for i, chunk_text in enumerate(chunks):
                if len(chunk_text) > 10:  # Skip very short chunks
                    chunk_id = str(uuid.uuid4())
                    session.execute(text("""
                        INSERT INTO document_chunks (id, document_id, chunk_text, chunk_index, created_at)
                        VALUES (:id, :doc_id, :chunk_text, :chunk_index, :created_at)
                    """), {
                        'id': chunk_id,
                        'doc_id': doc_id,
                        'chunk_text': chunk_text,
                        'chunk_index': i,
                        'created_at': datetime.utcnow()
                    })
            
            print(f"✅ Seeded: {doc['name']} ({len(chunks)} chunks)")
        
        session.commit()
        
        # Verify seeding
        doc_count = session.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        chunk_count = session.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar()
        
        print("\n📊 Database Status:")
        print(f"  Documents: {doc_count}")
        print(f"  Chunks: {chunk_count}")
        
        # Test queries
        stemi_count = session.execute(text("""
            SELECT COUNT(*) FROM document_chunks 
            WHERE chunk_text ILIKE '%STEMI%'
        """)).scalar()
        
        sepsis_count = session.execute(text("""
            SELECT COUNT(*) FROM document_chunks 
            WHERE chunk_text ILIKE '%sepsis%'
        """)).scalar()
        
        print("\n🔍 Content Verification:")
        print(f"  STEMI chunks: {stemi_count}")
        print(f"  Sepsis chunks: {sepsis_count}")
        
        print("\n🎉 Seeding complete! Medical content is now available.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    seed_essential_content()
