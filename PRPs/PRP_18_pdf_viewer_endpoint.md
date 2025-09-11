# PRP 18: Minimal PDF Viewer Endpoint

## Problem Statement
Developers need a way to visually verify that highlighted sources actually map to the correct locations in PDFs. This requires a lightweight viewer endpoint that serves PDFs with highlight overlays based on the response data.

## Success Criteria
- Endpoint serves PDFs with visual highlights
- Highlights correspond to chunks used in response
- Viewer accessible via link in API response
- Dev-only feature (disabled in production)
- Works without external dependencies

## Implementation Approach

### 1. Viewer Endpoint
```python
# src/api/endpoints/viewer.py
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from typing import Optional
import json
import base64

router = APIRouter(prefix="/viewer", tags=["viewer"])

@router.get("/pdf/{document_id}")
async def view_pdf_with_highlights(
    document_id: str,
    response_id: Optional[str] = Query(None),
    page: Optional[int] = Query(None),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db)
):
    """Serve PDF viewer with highlights"""
    
    # Check if viewer is enabled
    if not settings.enable_pdf_viewer:
        raise HTTPException(403, "PDF viewer is disabled")
        
    # Get document
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(404, "Document not found")
        
    # Get highlights for this response
    highlights = []
    if response_id:
        # Fetch stored response data
        response_data = await get_response_highlights(response_id, db)
        highlights = response_data.get("highlights", [])
        
    # Generate viewer HTML
    viewer_html = generate_viewer_html(
        document_id=document_id,
        document_name=document.filename,
        highlights=highlights,
        initial_page=page
    )
    
    return HTMLResponse(content=viewer_html)

@router.get("/pdf-file/{document_id}")
async def serve_pdf_file(
    document_id: str,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db)
):
    """Serve raw PDF file"""
    if not settings.enable_pdf_viewer:
        raise HTTPException(403, "PDF viewer is disabled")
        
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(404, "Document not found")
        
    file_path = f"{settings.docs_path}/{document.file_type}/{document.filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(404, "PDF file not found")
        
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=document.filename
    )

def generate_viewer_html(
    document_id: str,
    document_name: str,
    highlights: List[Dict],
    initial_page: Optional[int] = None
) -> str:
    """Generate HTML for PDF viewer with highlights"""
    
    highlights_json = json.dumps(highlights)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PDF Viewer - {document_name}</title>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: Arial, sans-serif;
                background: #2c3e50;
            }}
            #header {{
                background: #34495e;
                color: white;
                padding: 10px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            }}
            #pdf-container {{
                display: flex;
                justify-content: center;
                padding: 20px;
                overflow-y: auto;
                height: calc(100vh - 60px);
            }}
            #pdf-viewer {{
                background: white;
                box-shadow: 0 0 20px rgba(0,0,0,0.3);
                position: relative;
            }}
            .highlight-overlay {{
                position: absolute;
                background: rgba(255, 235, 59, 0.4);
                border: 2px solid #FFC107;
                pointer-events: none;
                mix-blend-mode: multiply;
            }}
            .highlight-tooltip {{
                position: absolute;
                background: #333;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
                white-space: nowrap;
                z-index: 1000;
                display: none;
            }}
            #controls {{
                display: flex;
                gap: 10px;
                align-items: center;
            }}
            button {{
                background: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
            }}
            button:hover {{
                background: #2980b9;
            }}
            #page-info {{
                margin: 0 10px;
            }}
            #highlight-list {{
                position: fixed;
                right: 20px;
                top: 80px;
                width: 300px;
                background: white;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                max-height: 70vh;
                overflow-y: auto;
            }}
            .highlight-item {{
                padding: 10px;
                margin: 5px 0;
                background: #f5f5f5;
                border-radius: 4px;
                cursor: pointer;
                border-left: 4px solid #3498db;
            }}
            .highlight-item:hover {{
                background: #e8e8e8;
            }}
            .highlight-item.active {{
                background: #d4e6f1;
                border-left-color: #2874a6;
            }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    </head>
    <body>
        <div id="header">
            <div>
                <h3 style="margin: 0;">{document_name}</h3>
            </div>
            <div id="controls">
                <button onclick="previousPage()">← Previous</button>
                <span id="page-info">Page <span id="current-page">1</span> of <span id="total-pages">-</span></span>
                <button onclick="nextPage()">Next →</button>
                <button onclick="toggleHighlights()">Toggle Highlights</button>
                <button onclick="zoomIn()">Zoom In</button>
                <button onclick="zoomOut()">Zoom Out</button>
            </div>
        </div>
        
        <div id="pdf-container">
            <canvas id="pdf-viewer"></canvas>
        </div>
        
        <div id="highlight-list">
            <h4>Highlighted Sources</h4>
            <div id="highlight-items"></div>
        </div>
        
        <script>
            // PDF.js configuration
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
            
            // State
            let pdfDoc = null;
            let currentPage = {initial_page or 1};
            let scale = 1.5;
            let highlights = {highlights_json};
            let showHighlights = true;
            
            // Load PDF
            const url = '/api/v1/viewer/pdf-file/{document_id}';
            
            pdfjsLib.getDocument(url).promise.then(function(pdf) {{
                pdfDoc = pdf;
                document.getElementById('total-pages').textContent = pdf.numPages;
                renderPage(currentPage);
                renderHighlightList();
            }});
            
            function renderPage(pageNum) {{
                pdfDoc.getPage(pageNum).then(function(page) {{
                    const canvas = document.getElementById('pdf-viewer');
                    const ctx = canvas.getContext('2d');
                    const viewport = page.getViewport({{scale: scale}});
                    
                    canvas.height = viewport.height;
                    canvas.width = viewport.width;
                    
                    const renderContext = {{
                        canvasContext: ctx,
                        viewport: viewport
                    }};
                    
                    page.render(renderContext).promise.then(function() {{
                        if (showHighlights) {{
                            renderHighlights(pageNum, viewport);
                        }}
                    }});
                    
                    document.getElementById('current-page').textContent = pageNum;
                }});
            }}
            
            function renderHighlights(pageNum, viewport) {{
                // Clear existing overlays
                document.querySelectorAll('.highlight-overlay').forEach(el => el.remove());
                
                // Get highlights for this page
                const pageHighlights = highlights.filter(h => h.page_number === pageNum);
                
                const container = document.getElementById('pdf-container');
                const canvas = document.getElementById('pdf-viewer');
                const canvasRect = canvas.getBoundingClientRect();
                
                pageHighlights.forEach(highlight => {{
                    if (highlight.bbox) {{
                        const overlay = document.createElement('div');
                        overlay.className = 'highlight-overlay';
                        
                        // Transform PDF coordinates to canvas coordinates
                        const x = highlight.bbox.x * scale;
                        const y = (viewport.height - (highlight.bbox.y + highlight.bbox.height)) * scale;
                        const width = highlight.bbox.width * scale;
                        const height = highlight.bbox.height * scale;
                        
                        overlay.style.left = x + 'px';
                        overlay.style.top = y + 'px';
                        overlay.style.width = width + 'px';
                        overlay.style.height = height + 'px';
                        
                        overlay.title = highlight.text_snippet || 'Highlighted source';
                        
                        canvas.parentElement.appendChild(overlay);
                    }}
                }});
            }}
            
            function renderHighlightList() {{
                const container = document.getElementById('highlight-items');
                container.innerHTML = '';
                
                // Group highlights by page
                const byPage = {{}};
                highlights.forEach(h => {{
                    if (!byPage[h.page_number]) byPage[h.page_number] = [];
                    byPage[h.page_number].push(h);
                }});
                
                Object.keys(byPage).sort((a, b) => a - b).forEach(pageNum => {{
                    byPage[pageNum].forEach(highlight => {{
                        const item = document.createElement('div');
                        item.className = 'highlight-item';
                        if (parseInt(pageNum) === currentPage) {{
                            item.classList.add('active');
                        }}
                        
                        item.innerHTML = `
                            <div style="font-weight: bold; margin-bottom: 5px;">Page ${{pageNum}}</div>
                            <div style="font-size: 12px; color: #666;">
                                ${{highlight.text_snippet ? highlight.text_snippet.substring(0, 100) + '...' : 'Source'}}
                            </div>
                            <div style="font-size: 11px; color: #999; margin-top: 5px;">
                                Confidence: ${{(highlight.confidence * 100).toFixed(0)}}%
                            </div>
                        `;
                        
                        item.onclick = () => {{
                            currentPage = parseInt(pageNum);
                            renderPage(currentPage);
                            updateActiveHighlight();
                        }};
                        
                        container.appendChild(item);
                    }});
                }});
            }}
            
            function updateActiveHighlight() {{
                document.querySelectorAll('.highlight-item').forEach((item, index) => {{
                    item.classList.remove('active');
                }});
                // Update active based on current page
                document.querySelectorAll('.highlight-item').forEach(item => {{
                    const pageText = item.querySelector('div').textContent;
                    const pageNum = parseInt(pageText.replace('Page ', ''));
                    if (pageNum === currentPage) {{
                        item.classList.add('active');
                    }}
                }});
            }}
            
            function nextPage() {{
                if (currentPage < pdfDoc.numPages) {{
                    currentPage++;
                    renderPage(currentPage);
                    updateActiveHighlight();
                }}
            }}
            
            function previousPage() {{
                if (currentPage > 1) {{
                    currentPage--;
                    renderPage(currentPage);
                    updateActiveHighlight();
                }}
            }}
            
            function toggleHighlights() {{
                showHighlights = !showHighlights;
                renderPage(currentPage);
            }}
            
            function zoomIn() {{
                scale += 0.25;
                renderPage(currentPage);
            }}
            
            function zoomOut() {{
                if (scale > 0.5) {{
                    scale -= 0.25;
                    renderPage(currentPage);
                }}
            }}
            
            // Keyboard navigation
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'ArrowLeft') previousPage();
                if (e.key === 'ArrowRight') nextPage();
                if (e.key === 'h') toggleHighlights();
            }});
        </script>
    </body>
    </html>
    """
```

### 2. Response Storage for Viewer
```python
# src/models/entities.py (addition)
class QueryResponseCache(Base):
    """Store response data for viewer"""
    __tablename__ = "query_response_cache"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    query = Column(Text, nullable=False)
    response = Column(JSON, nullable=False)
    highlights = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    # Index for cleanup
    __table_args__ = (
        Index('idx_response_expires', 'expires_at'),
    )
```

### 3. Integration with Router
```python
# src/pipeline/router.py (modifications)
import uuid
from datetime import datetime, timedelta

class QueryRouter:
    async def route_query(self, query: str) -> QueryResponse:
        # ... existing logic ...
        
        # Store response for viewer if highlights exist
        response_id = None
        if highlighted_sources and self.settings.enable_pdf_viewer:
            response_id = str(uuid.uuid4())
            
            # Store in cache table
            cache_entry = QueryResponseCache(
                id=response_id,
                query=query,
                response={
                    "answer": answer,
                    "sources": sources,
                    "query_type": query_type.value
                },
                highlights=[
                    {
                        "document_id": h.document_id,
                        "page_number": h.page_number,
                        "text_snippet": h.text_snippet,
                        "bbox": h.bbox,
                        "confidence": h.confidence
                    }
                    for h in highlighted_sources
                ],
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            self.db_session.add(cache_entry)
            await self.db_session.commit()
            
            # Generate viewer URL
            viewer_url = f"/api/v1/viewer/pdf/{highlighted_sources[0].document_id}?response_id={response_id}"
```

### 4. Configuration
```python
# src/config/settings.py (addition)
class Settings(BaseSettings):
    enable_pdf_viewer: bool = Field(
        default=False,
        description="Enable PDF viewer endpoint (dev only)"
    )
    
    viewer_cache_ttl_hours: int = Field(
        default=1,
        description="TTL for viewer response cache"
    )
```

### 5. Cleanup Task
```python
# src/tasks/cleanup.py
async def cleanup_expired_viewer_cache():
    """Remove expired viewer cache entries"""
    db = get_db_session()
    
    expired = db.query(QueryResponseCache).filter(
        QueryResponseCache.expires_at < datetime.utcnow()
    ).delete()
    
    db.commit()
    logger.info(f"Cleaned up {expired} expired viewer cache entries")
```

## Testing Strategy
```bash
# Manual testing
# 1. Enable viewer
export ENABLE_PDF_VIEWER=true

# 2. Make a query that returns highlights
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "STEMI protocol"}'

# 3. Get viewer URL from response and open in browser
# Should see PDF with yellow highlights on relevant sections

# 4. Test navigation
# - Arrow keys should change pages
# - Clicking highlights in sidebar should jump to page
# - Toggle highlights button should show/hide overlays
```

## Security Considerations
- Viewer disabled by default
- Only serves documents already in database
- Response cache expires after 1 hour
- No external resource loading (except PDF.js CDN)
- Consider adding authentication for production use

## Performance Impact
- Minimal: only active when viewer accessed
- Response caching prevents repeated computation
- PDF.js handles rendering client-side
- Cleanup task prevents cache growth

## Rollback Plan
1. Set `ENABLE_PDF_VIEWER=false`
2. Viewer endpoints return 403
3. No viewer URLs in responses
4. Can drop cache table if needed