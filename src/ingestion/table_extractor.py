"""Table extraction from documents using Unstructured (PRP 19)."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    from unstructured.documents.elements import Table
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

from src.config.settings import Settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TableExtractor:
    """Extract and structure tables from documents."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = getattr(settings, 'enable_table_extraction', False)
        
        if self.enabled and not UNSTRUCTURED_AVAILABLE:
            logger.error("Table extraction enabled but Unstructured library not available")
            self.enabled = False
        
    async def extract_tables(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """Extract all tables from document."""
        if not self.enabled:
            return []
            
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []
            
        if file_type.lower() == "pdf":
            return await self._extract_pdf_tables(str(file_path))
        elif file_type.lower() in ["docx", "doc"]:
            return await self._extract_word_tables(str(file_path))
        else:
            logger.warning(f"Table extraction not supported for {file_type}")
            return []
            
    async def _extract_pdf_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract tables from PDF using Unstructured."""
        try:
            logger.info(f"Extracting tables from PDF: {file_path}")
            
            # Use Unstructured for initial extraction
            elements = partition_pdf(
                filename=file_path,
                strategy="hi_res",  # Better table detection
                infer_table_structure=True,
                include_page_breaks=True,
                extract_images_in_pdf=False  # Focus on tables
            )
            
            tables = []
            current_page = 1
            table_index = 0
            
            for i, element in enumerate(elements):
                if element.category == "PageBreak":
                    current_page += 1
                    table_index = 0
                elif isinstance(element, Table) or element.category == "Table":
                    # Parse table structure
                    table_data = await self._parse_table_element(element)
                    
                    if table_data and table_data["headers"] and table_data["rows"]:
                        # Infer table title from surrounding elements
                        title = self._infer_table_title(element, elements, i)
                        
                        # Classify table type
                        table_type = self._classify_table_type(table_data)
                        
                        # Extract units from headers/data
                        units = self._extract_units(table_data["headers"], table_data["rows"])
                        
                        # Flatten table for search
                        content_text = self._flatten_table(table_data)
                        
                        # Get bounding box if available
                        bbox = None
                        if hasattr(element, 'metadata') and hasattr(element.metadata, 'coordinates'):
                            coords = element.metadata.coordinates
                            bbox = {
                                "x": coords.points[0][0],
                                "y": coords.points[0][1],
                                "width": coords.points[2][0] - coords.points[0][0],
                                "height": coords.points[2][1] - coords.points[0][1]
                            }
                        
                        # Get confidence score
                        confidence = 1.0
                        if hasattr(element, 'metadata') and hasattr(element.metadata, 'detection_score'):
                            confidence = element.metadata.detection_score
                        
                        tables.append({
                            "page_number": current_page,
                            "table_index": table_index,
                            "headers": table_data["headers"],
                            "rows": table_data["rows"],
                            "title": title,
                            "table_type": table_type,
                            "units": units,
                            "content_text": content_text,
                            "bbox": bbox,
                            "confidence": confidence
                        })
                        
                        table_index += 1
                        logger.debug(f"Extracted table {table_index} on page {current_page}: {table_type}")
                        
            logger.info(f"Extracted {len(tables)} tables from {file_path}")
            return tables
            
        except Exception as e:
            logger.error(f"Table extraction failed for {file_path}: {e}")
            return []
            
    async def _parse_table_element(self, table_element) -> Optional[Dict[str, Any]]:
        """Parse Unstructured Table element into structured format."""
        try:
            # First try to get HTML table if available
            table_html = None
            if hasattr(table_element, 'metadata') and hasattr(table_element.metadata, 'text_as_html'):
                table_html = table_element.metadata.text_as_html
            
            if table_html and "<table" in table_html.lower():
                return await self._parse_html_table(table_html)
            
            # Fallback: parse raw text
            if hasattr(table_element, 'text'):
                return await self._parse_text_table(table_element.text)
            
            return None
                
        except Exception as e:
            logger.warning(f"Failed to parse table element: {e}")
            return None
            
    async def _parse_html_table(self, table_html: str) -> Optional[Dict[str, Any]]:
        """Parse HTML table using pandas."""
        try:
            # Use pandas to parse HTML table
            dfs = pd.read_html(table_html, header=0)
            if not dfs:
                return None
                
            df = dfs[0]
            
            # Extract headers
            headers = [str(col).strip() for col in df.columns]
            
            # Clean headers (remove NaN, etc.)
            headers = [h if h != 'nan' else f"Column_{i}" for i, h in enumerate(headers)]
            
            # Extract rows
            rows = []
            for _, row in df.iterrows():
                row_data = [str(cell).strip() if pd.notna(cell) else "" for cell in row]
                # Skip empty rows
                if any(cell for cell in row_data):
                    rows.append(row_data)
            
            if not rows:
                return None
                
            return {
                "headers": headers,
                "rows": rows
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse HTML table: {e}")
            return None
            
    async def _parse_text_table(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse table from raw text."""
        try:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if len(lines) < 2:
                return None
            
            # Try different delimiters
            delimiters = ['\t', '|', '  ', ',']
            best_result = None
            max_cols = 0
            
            for delimiter in delimiters:
                # Split first line as headers
                headers = [h.strip() for h in lines[0].split(delimiter) if h.strip()]
                if len(headers) < 2:
                    continue
                
                # Split remaining lines as rows
                rows = []
                for line in lines[1:]:
                    if delimiter == '  ':
                        # Handle multiple spaces
                        row = [cell.strip() for cell in re.split(r'\s{2,}', line) if cell.strip()]
                    else:
                        row = [cell.strip() for cell in line.split(delimiter) if cell.strip()]
                    
                    if row and len(row) >= 2:
                        # Pad row to match header length
                        while len(row) < len(headers):
                            row.append("")
                        rows.append(row[:len(headers)])
                
                if rows and len(headers) > max_cols:
                    max_cols = len(headers)
                    best_result = {
                        "headers": headers,
                        "rows": rows
                    }
            
            return best_result
            
        except Exception as e:
            logger.warning(f"Failed to parse text table: {e}")
            return None
            
    def _classify_table_type(self, table_data: Dict[str, Any]) -> str:
        """Classify table type based on content."""
        headers_lower = [h.lower() for h in table_data["headers"]]
        headers_text = ' '.join(headers_lower)
        
        # Also look at first few rows for classification clues
        sample_text = headers_text
        if table_data["rows"]:
            sample_rows = table_data["rows"][:3]
            for row in sample_rows:
                sample_text += ' ' + ' '.join(str(cell).lower() for cell in row)
        
        # Dosage table indicators
        dosage_keywords = ["dose", "dosage", "mg", "mcg", "units", "medication", "drug", "route", "frequency"]
        if any(keyword in sample_text for keyword in dosage_keywords):
            return "dosage"
            
        # Protocol table indicators
        protocol_keywords = ["step", "time", "action", "procedure", "protocol", "minute", "hour"]
        if any(keyword in sample_text for keyword in protocol_keywords):
            return "protocol"
            
        # Lab reference table
        lab_keywords = ["reference", "range", "normal", "lab", "test", "value", "min", "max"]
        if any(keyword in sample_text for keyword in lab_keywords):
            return "reference"
            
        # Contact table
        contact_keywords = ["contact", "phone", "pager", "name", "department", "extension"]
        if any(keyword in sample_text for keyword in contact_keywords):
            return "contact"
            
        # Vital signs / monitoring
        vital_keywords = ["bp", "hr", "temp", "o2", "sat", "vital", "monitor"]
        if any(keyword in sample_text for keyword in vital_keywords):
            return "vitals"
            
        return "general"
        
    def _infer_table_title(self, table_element, all_elements: List, table_idx: int) -> Optional[str]:
        """Try to find table title from surrounding elements."""
        try:
            # Look for title/heading element before table
            for i in range(max(0, table_idx - 3), table_idx):
                element = all_elements[i]
                if hasattr(element, 'category') and element.category in ["Title", "Header"]:
                    if hasattr(element, 'text') and element.text:
                        return element.text.strip()
                        
            # Check if table has a caption
            if hasattr(table_element, 'metadata') and hasattr(table_element.metadata, 'table_summary'):
                return table_element.metadata.table_summary
                
            # Look at the table text for title patterns
            if hasattr(table_element, 'text'):
                lines = table_element.text.split('\n')
                for line in lines[:2]:  # Check first two lines
                    line = line.strip()
                    # If line is short and doesn't contain table delimiters, might be title
                    if line and len(line) < 100 and '\t' not in line and '|' not in line:
                        # Make sure it's not just a header row
                        if not any(word in line.lower() for word in ['dose', 'step', 'time', 'name']):
                            return line
                
        except Exception as e:
            logger.warning(f"Failed to infer table title: {e}")
            
        return None
        
    def _flatten_table(self, table_data: Dict[str, Any]) -> str:
        """Flatten table to searchable text."""
        lines = []
        
        # Add headers
        lines.append(" | ".join(table_data["headers"]))
        
        # Add rows
        for row in table_data["rows"]:
            lines.append(" | ".join(str(cell) for cell in row))
            
        return "\n".join(lines)
        
    def _extract_units(self, headers: List[str], rows: List[List[str]]) -> Dict[str, str]:
        """Extract units from headers or first data row."""
        units = {}
        
        for i, header in enumerate(headers):
            # Check if unit in header (e.g., "Dose (mg)")
            match = re.search(r'\(([^)]+)\)', header)
            if match:
                clean_header = header.split('(')[0].strip()
                units[clean_header] = match.group(1)
            else:
                # Check if consistent unit pattern in column
                if rows and i < len(rows[0]):
                    col_values = [row[i] for row in rows[:5] if i < len(row)]
                    unit_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)')
                    found_units = set()
                    
                    for val in col_values:
                        val_str = str(val)
                        match = unit_pattern.search(val_str)
                        if match:
                            found_units.add(match.group(2))
                    
                    if len(found_units) == 1:
                        units[header] = found_units.pop()
                    
        return units
        
    async def _extract_word_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract tables from Word documents."""
        # TODO: Implement Word table extraction
        logger.warning("Word table extraction not yet implemented")
        return []