"""Specialized retrieval for table data (PRP 19)."""

from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.config.settings import Settings
from src.models.entities import Document, ExtractedTable
from src.models.query_types import QueryType
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TableRetriever:
    """Specialized retrieval for table data."""
    
    def __init__(self, db_session: Session, settings: Settings):
        self.db = db_session
        self.settings = settings
        self.enabled = getattr(settings, 'enable_table_extraction', False)
        
    async def retrieve_tables(
        self,
        query: str,
        query_type: QueryType,
        top_k: int = 5,
        table_types: Optional[List[str]] = None
    ) -> List[ExtractedTable]:
        """Retrieve relevant tables for query."""
        
        if not self.enabled:
            return []
        
        try:
            # Build base query
            base_query = self.db.query(ExtractedTable).join(Document)
            
            # Build filters based on query type and table types
            filters = []
            
            # Filter by query type
            if query_type == QueryType.DOSAGE_LOOKUP:
                filters.append(ExtractedTable.table_type == "dosage")
            elif query_type == QueryType.PROTOCOL_STEPS:
                filters.append(ExtractedTable.table_type.in_(["protocol", "procedure"]))
            elif query_type == QueryType.CONTACT_LOOKUP:
                filters.append(ExtractedTable.table_type == "contact")
            elif query_type == QueryType.CRITERIA_CHECK:
                filters.append(ExtractedTable.table_type.in_(["reference", "criteria"]))
            
            # Additional table type filters
            if table_types:
                filters.append(ExtractedTable.table_type.in_(table_types))
            
            # Apply filters
            if filters:
                base_query = base_query.filter(or_(*filters))
            
            # For now, use text search until embeddings are available
            # TODO: Implement semantic similarity search when embeddings are ready
            query_lower = query.lower()
            text_filters = []
            
            # Search in content text
            text_filters.append(ExtractedTable.content_text.ilike(f'%{query_lower}%'))
            
            # Search in title
            text_filters.append(ExtractedTable.title.ilike(f'%{query_lower}%'))
            
            # Search in document filename
            text_filters.append(Document.filename.ilike(f'%{query_lower}%'))
            
            if text_filters:
                base_query = base_query.filter(or_(*text_filters))
            
            # Order by confidence and creation date
            tables = base_query.order_by(
                ExtractedTable.confidence.desc(),
                ExtractedTable.created_at.desc()
            ).limit(top_k).all()
            
            logger.info(f"Retrieved {len(tables)} tables for query: {query}")
            return tables
            
        except Exception as e:
            logger.error(f"Table retrieval failed: {e}")
            return []
    
    async def retrieve_tables_by_medication(self, medication: str, top_k: int = 3) -> List[ExtractedTable]:
        """Retrieve dosage tables for specific medication."""
        if not self.enabled:
            return []
            
        try:
            medication_lower = medication.lower()
            
            tables = self.db.query(ExtractedTable).filter(
                and_(
                    ExtractedTable.table_type == "dosage",
                    or_(
                        ExtractedTable.content_text.ilike(f'%{medication_lower}%'),
                        ExtractedTable.title.ilike(f'%{medication_lower}%')
                    )
                )
            ).order_by(
                ExtractedTable.confidence.desc()
            ).limit(top_k).all()
            
            logger.info(f"Retrieved {len(tables)} dosage tables for medication: {medication}")
            return tables
            
        except Exception as e:
            logger.error(f"Medication table retrieval failed: {e}")
            return []
    
    async def retrieve_protocol_tables(self, protocol_name: str, top_k: int = 3) -> List[ExtractedTable]:
        """Retrieve protocol tables for specific protocol."""
        if not self.enabled:
            return []
            
        try:
            protocol_lower = protocol_name.lower()
            
            tables = self.db.query(ExtractedTable).filter(
                and_(
                    ExtractedTable.table_type.in_(["protocol", "procedure"]),
                    or_(
                        ExtractedTable.content_text.ilike(f'%{protocol_lower}%'),
                        ExtractedTable.title.ilike(f'%{protocol_lower}%'),
                        ExtractedTable.document.has(Document.filename.ilike(f'%{protocol_lower}%'))
                    )
                )
            ).order_by(
                ExtractedTable.confidence.desc()
            ).limit(top_k).all()
            
            logger.info(f"Retrieved {len(tables)} protocol tables for: {protocol_name}")
            return tables
            
        except Exception as e:
            logger.error(f"Protocol table retrieval failed: {e}")
            return []
    
    def format_table_response(self, table: ExtractedTable, include_metadata: bool = True) -> str:
        """Format table for response."""
        try:
            lines = []
            
            # Add title if available
            if table.title:
                lines.append(f"**{table.title}**\n")
            
            # Format as markdown table
            if table.headers and table.rows:
                # Headers
                lines.append("| " + " | ".join(table.headers) + " |")
                
                # Separator
                lines.append("|" + "|".join(["---"] * len(table.headers)) + "|")
                
                # Rows (limit to reasonable number)
                max_rows = 10
                rows_to_show = table.rows[:max_rows]
                
                for row in rows_to_show:
                    # Ensure row has same length as headers
                    padded_row = row + [""] * (len(table.headers) - len(row))
                    padded_row = padded_row[:len(table.headers)]
                    lines.append("| " + " | ".join(str(cell) for cell in padded_row) + " |")
                
                # Add truncation notice if needed
                if len(table.rows) > max_rows:
                    lines.append(f"\n*({len(table.rows) - max_rows} additional rows not shown)*")
            
            # Add metadata if requested
            if include_metadata:
                lines.append("")
                if table.table_type:
                    lines.append(f"*Type: {table.table_type.title()}*")
                
                # Add source citation
                source_info = f"*Source: {table.document.filename}"
                if table.page_number:
                    source_info += f", Page {table.page_number}"
                if table.table_index > 0:
                    source_info += f", Table {table.table_index + 1}"
                source_info += "*"
                lines.append(source_info)
                
                # Add confidence if available
                if table.confidence and table.confidence < 1.0:
                    lines.append(f"*Confidence: {table.confidence:.2f}*")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to format table response: {e}")
            return f"Table from {table.document.filename} (formatting error)"
    
    def format_table_for_llm(self, table: ExtractedTable) -> str:
        """Format table as context for LLM processing."""
        try:
            context_parts = []
            
            # Add table identification
            table_id = f"Table from {table.document.filename}"
            if table.page_number:
                table_id += f", page {table.page_number}"
            if table.title:
                table_id += f": {table.title}"
            
            context_parts.append(table_id)
            
            # Add structured data
            if table.headers and table.rows:
                context_parts.append("Headers: " + " | ".join(table.headers))
                
                # Add sample rows for context
                max_rows = 5
                for i, row in enumerate(table.rows[:max_rows]):
                    row_str = " | ".join(str(cell) for cell in row)
                    context_parts.append(f"Row {i+1}: {row_str}")
                
                if len(table.rows) > max_rows:
                    context_parts.append(f"... ({len(table.rows) - max_rows} more rows)")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to format table for LLM: {e}")
            return f"Table from {table.document.filename}"
    
    async def get_table_statistics(self) -> Dict[str, Any]:
        """Get statistics about extracted tables."""
        try:
            stats = {}
            
            # Total tables
            stats["total_tables"] = self.db.query(ExtractedTable).count()
            
            # Tables by type
            type_counts = self.db.query(
                ExtractedTable.table_type,
                func.count(ExtractedTable.id)
            ).group_by(ExtractedTable.table_type).all()
            
            stats["by_type"] = {table_type: count for table_type, count in type_counts}
            
            # Tables by document
            doc_counts = self.db.query(
                Document.filename,
                func.count(ExtractedTable.id)
            ).join(ExtractedTable).group_by(Document.filename).all()
            
            stats["by_document"] = {filename: count for filename, count in doc_counts}
            
            # Average confidence
            avg_confidence = self.db.query(
                func.avg(ExtractedTable.confidence)
            ).scalar()
            
            stats["average_confidence"] = float(avg_confidence) if avg_confidence else 0.0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get table statistics: {e}")
            return {}
    
    async def search_table_content(self, search_term: str, table_types: Optional[List[str]] = None) -> List[ExtractedTable]:
        """Search for tables containing specific content."""
        if not self.enabled:
            return []
        
        try:
            query = self.db.query(ExtractedTable)
            
            # Filter by table types if provided
            if table_types:
                query = query.filter(ExtractedTable.table_type.in_(table_types))
            
            # Search in content text
            search_term_lower = search_term.lower()
            tables = query.filter(
                ExtractedTable.content_text.ilike(f'%{search_term_lower}%')
            ).order_by(
                ExtractedTable.confidence.desc(),
                ExtractedTable.created_at.desc()
            ).limit(10).all()
            
            logger.info(f"Found {len(tables)} tables containing: {search_term}")
            return tables
            
        except Exception as e:
            logger.error(f"Table content search failed: {e}")
            return []