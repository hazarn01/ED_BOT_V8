# PRP 19: Table Extraction Module

## Problem Statement
Medical documents contain critical structured data in tables (dosage charts, protocol steps, lab reference ranges) that need special extraction and storage. Current text chunking destroys table structure, making it difficult to accurately retrieve and present tabular information.

## Success Criteria
- Tables extracted with structure preserved (headers, rows, columns)
- Dosage tables searchable by medication name
- Protocol step tables maintain sequence
- Table sources traceable to document/page
- No regression when table extraction disabled

## Implementation Approach

### 1. Table Model
```python
# src/models/entities.py (addition)
class ExtractedTable(Base):
    """Store extracted tables from documents"""
    __tablename__ = "extracted_tables"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    table_index = Column(Integer, nullable=False)  # Index of table on page
    
    # Table metadata
    table_type = Column(String, nullable=True)  # "dosage", "protocol", "reference", etc.
    title = Column(Text, nullable=True)  # Extracted or inferred title
    caption = Column(Text, nullable=True)
    
    # Structured content
    headers = Column(JSON, nullable=False)  # ["Drug", "Dose", "Route", "Frequency"]
    rows = Column(JSON, nullable=False)  # [["Aspirin", "325mg", "PO", "Daily"], ...]
    units = Column(JSON, nullable=True)  # {"Dose": "mg", ...}
    
    # Search optimization
    content_text = Column(Text, nullable=False)  # Flattened for search
    content_vector = Column(Vector(1536), nullable=True)  # Embedding
    
    # Position info
    bbox = Column(JSON, nullable=True)
    confidence = Column(Float, default=1.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="tables")
    
    # Indexes
    __table_args__ = (
        Index('idx_table_document', 'document_id', 'page_number'),
        Index('idx_table_type', 'table_type'),
    )

# Add to Document model
Document.tables = relationship("ExtractedTable", back_populates="document", cascade="all, delete-orphan")
```

### 2. Table Extractor
```python
# src/ingestion/table_extractor.py
from typing import List, Dict, Optional, Tuple
from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import Table
import pandas as pd
import numpy as np

class TableExtractor:
    """Extract and structure tables from documents"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = settings.enable_table_extraction
        
    async def extract_tables(self, file_path: str, file_type: str) -> List[Dict]:
        """Extract all tables from document"""
        if not self.enabled:
            return []
            
        if file_type == "pdf":
            return await self._extract_pdf_tables(file_path)
        elif file_type in ["docx", "doc"]:
            return await self._extract_word_tables(file_path)
        else:
            logger.warning(f"Table extraction not supported for {file_type}")
            return []
            
    async def _extract_pdf_tables(self, file_path: str) -> List[Dict]:
        """Extract tables from PDF using Unstructured"""
        try:
            # Use Unstructured for initial extraction
            elements = partition_pdf(
                filename=file_path,
                strategy="hi_res",  # Better table detection
                infer_table_structure=True,
                include_page_breaks=True
            )
            
            tables = []
            current_page = 1
            table_index = 0
            
            for element in elements:
                if element.category == "PageBreak":
                    current_page += 1
                    table_index = 0
                elif isinstance(element, Table):
                    # Parse table structure
                    table_data = self._parse_table_element(element)
                    
                    if table_data:
                        tables.append({
                            "page_number": current_page,
                            "table_index": table_index,
                            "headers": table_data["headers"],
                            "rows": table_data["rows"],
                            "title": self._infer_table_title(element, elements),
                            "table_type": self._classify_table_type(table_data),
                            "content_text": self._flatten_table(table_data),
                            "bbox": element.metadata.coordinates if hasattr(element.metadata, 'coordinates') else None,
                            "confidence": element.metadata.detection_score if hasattr(element.metadata, 'detection_score') else 1.0
                        })
                        table_index += 1
                        
            return tables
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return []
            
    def _parse_table_element(self, table_element: Table) -> Optional[Dict]:
        """Parse Unstructured Table element into structured format"""
        try:
            # Get table HTML or text
            table_html = table_element.metadata.text_as_html if hasattr(table_element.metadata, 'text_as_html') else None
            
            if table_html:
                # Parse HTML table
                df = pd.read_html(table_html)[0]
                
                # Extract headers (first row or inferred)
                if df.iloc[0].notna().all():
                    headers = df.iloc[0].tolist()
                    rows = df.iloc[1:].values.tolist()
                else:
                    headers = [f"Column_{i}" for i in range(len(df.columns))]
                    rows = df.values.tolist()
                    
                # Clean data
                headers = [str(h).strip() for h in headers]
                rows = [[str(cell).strip() if pd.notna(cell) else "" for cell in row] for row in rows]
                
                return {
                    "headers": headers,
                    "rows": rows
                }
            else:
                # Fallback: parse raw text
                lines = table_element.text.split('\n')
                if len(lines) < 2:
                    return None
                    
                # Assume first line is headers
                headers = lines[0].split('\t')
                rows = [line.split('\t') for line in lines[1:] if line.strip()]
                
                return {
                    "headers": headers,
                    "rows": rows
                }
                
        except Exception as e:
            logger.warning(f"Failed to parse table: {e}")
            return None
            
    def _classify_table_type(self, table_data: Dict) -> str:
        """Classify table type based on content"""
        headers_lower = [h.lower() for h in table_data["headers"]]
        
        # Dosage table indicators
        dosage_keywords = ["dose", "dosage", "mg", "mcg", "units", "medication", "drug"]
        if any(keyword in ' '.join(headers_lower) for keyword in dosage_keywords):
            return "dosage"
            
        # Protocol table indicators
        protocol_keywords = ["step", "time", "action", "procedure", "protocol"]
        if any(keyword in ' '.join(headers_lower) for keyword in protocol_keywords):
            return "protocol"
            
        # Lab reference table
        lab_keywords = ["reference", "range", "normal", "lab", "test", "value"]
        if any(keyword in ' '.join(headers_lower) for keyword in lab_keywords):
            return "reference"
            
        # Contact table
        contact_keywords = ["contact", "phone", "pager", "name", "department"]
        if any(keyword in ' '.join(headers_lower) for keyword in contact_keywords):
            return "contact"
            
        return "general"
        
    def _infer_table_title(self, table_element, all_elements: List) -> Optional[str]:
        """Try to find table title from surrounding elements"""
        # Look for title/heading element before table
        table_idx = all_elements.index(table_element)
        
        for i in range(max(0, table_idx - 3), table_idx):
            element = all_elements[i]
            if element.category in ["Title", "Header"]:
                return element.text
                
        # Check if first row might be title
        if hasattr(table_element, 'text'):
            first_line = table_element.text.split('\n')[0]
            if len(first_line) < 100 and not '\t' in first_line:
                return first_line
                
        return None
        
    def _flatten_table(self, table_data: Dict) -> str:
        """Flatten table to searchable text"""
        lines = []
        
        # Add headers
        lines.append(" | ".join(table_data["headers"]))
        
        # Add rows
        for row in table_data["rows"]:
            lines.append(" | ".join(row))
            
        return "\n".join(lines)
        
    def _extract_units(self, headers: List[str], rows: List[List[str]]) -> Dict[str, str]:
        """Extract units from headers or first data row"""
        units = {}
        
        for i, header in enumerate(headers):
            # Check if unit in header (e.g., "Dose (mg)")
            import re
            match = re.search(r'\(([^)]+)\)', header)
            if match:
                units[header.split('(')[0].strip()] = match.group(1)
            # Check if consistent unit pattern in column
            elif rows:
                col_values = [row[i] for row in rows[:5] if i < len(row)]
                unit_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)')
                found_units = set()
                for val in col_values:
                    match = unit_pattern.search(val)
                    if match:
                        found_units.add(match.group(2))
                if len(found_units) == 1:
                    units[header] = found_units.pop()
                    
        return units
```

### 3. Enhanced Ingestion Pipeline
```python
# src/ingestion/tasks.py (modifications)
class DocumentIngestionTask:
    def __init__(self, ...):
        # ...
        self.table_extractor = TableExtractor(settings)
        
    async def ingest_document(self, file_path: str, content_type: str):
        # Existing document processing...
        
        # Extract tables if enabled
        if self.settings.enable_table_extraction:
            tables = await self.table_extractor.extract_tables(
                file_path, 
                content_type
            )
            
            for table_data in tables:
                # Generate embedding for table
                embedding = await self._generate_embedding(
                    table_data["content_text"]
                )
                
                # Store in database
                extracted_table = ExtractedTable(
                    document_id=document.id,
                    page_number=table_data["page_number"],
                    table_index=table_data["table_index"],
                    table_type=table_data["table_type"],
                    title=table_data.get("title"),
                    headers=table_data["headers"],
                    rows=table_data["rows"],
                    units=table_data.get("units"),
                    content_text=table_data["content_text"],
                    content_vector=embedding,
                    bbox=table_data.get("bbox"),
                    confidence=table_data.get("confidence", 1.0)
                )
                self.db_session.add(extracted_table)
                
        await self.db_session.commit()
```

### 4. Table-Aware Retrieval
```python
# src/pipeline/table_retriever.py
class TableRetriever:
    """Specialized retrieval for table data"""
    
    def __init__(self, db_session: Session, settings: Settings):
        self.db = db_session
        self.settings = settings
        
    async def retrieve_tables(
        self,
        query: str,
        query_type: QueryType,
        top_k: int = 5
    ) -> List[ExtractedTable]:
        """Retrieve relevant tables for query"""
        
        # Generate query embedding
        query_embedding = await generate_embedding(query)
        
        # Build filters based on query type
        filters = []
        if query_type == QueryType.DOSAGE_LOOKUP:
            filters.append(ExtractedTable.table_type == "dosage")
        elif query_type == QueryType.PROTOCOL_STEPS:
            filters.append(ExtractedTable.table_type.in_(["protocol", "procedure"]))
            
        # Similarity search
        tables = self.db.query(ExtractedTable).filter(
            *filters
        ).order_by(
            ExtractedTable.content_vector.cosine_distance(query_embedding)
        ).limit(top_k).all()
        
        return tables
        
    def format_table_response(self, table: ExtractedTable) -> str:
        """Format table for response"""
        lines = []
        
        if table.title:
            lines.append(f"**{table.title}**\n")
            
        # Format as markdown table
        lines.append("| " + " | ".join(table.headers) + " |")
        lines.append("|" + "|".join(["---"] * len(table.headers)) + "|")
        
        for row in table.rows:
            lines.append("| " + " | ".join(row) + " |")
            
        # Add source citation
        lines.append(f"\n*Source: {table.document.filename}, Page {table.page_number}*")
        
        return "\n".join(lines)
```

### 5. Integration with Router
```python
# src/pipeline/router.py (modifications)
class QueryRouter:
    def __init__(self, ...):
        # ...
        self.table_retriever = TableRetriever(db_session, settings)
        
    async def route_query(self, query: str) -> QueryResponse:
        classification = await self.classifier.classify_query(query)
        
        # Check if table retrieval would help
        if classification.query_type in [
            QueryType.DOSAGE_LOOKUP,
            QueryType.PROTOCOL_STEPS
        ] and self.settings.enable_table_extraction:
            
            # Retrieve relevant tables
            tables = await self.table_retriever.retrieve_tables(
                query,
                classification.query_type
            )
            
            if tables:
                # Format table response
                table_response = self.table_retriever.format_table_response(
                    tables[0]
                )
                
                # Combine with text retrieval if needed
                # ...
```

## Testing Strategy
```python
# tests/unit/test_table_extraction.py
def test_dosage_table_extraction():
    """Test extraction of dosage table"""
    table_html = """
    <table>
        <tr><th>Medication</th><th>Dose</th><th>Route</th></tr>
        <tr><td>Aspirin</td><td>325mg</td><td>PO</td></tr>
        <tr><td>Heparin</td><td>5000 units</td><td>SubQ</td></tr>
    </table>
    """
    
    extractor = TableExtractor(settings)
    result = extractor._parse_table_html(table_html)
    
    assert result["headers"] == ["Medication", "Dose", "Route"]
    assert len(result["rows"]) == 2
    assert result["rows"][0] == ["Aspirin", "325mg", "PO"]
    
def test_table_type_classification():
    """Test table type detection"""
    dosage_table = {
        "headers": ["Drug", "Dose", "Frequency"],
        "rows": [["Metoprolol", "25mg", "BID"]]
    }
    
    extractor = TableExtractor(settings)
    table_type = extractor._classify_table_type(dosage_table)
    assert table_type == "dosage"
```

## Performance Considerations
- Table extraction during ingestion (one-time cost)
- Indexed by type for fast filtering
- Vector similarity for semantic search
- Consider caching formatted tables

## Rollback Plan
1. Set `ENABLE_TABLE_EXTRACTION=false`
2. System ignores table data, uses text chunks
3. Existing tables remain in DB but unused
4. Can drop table if needed