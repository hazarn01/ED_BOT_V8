"""PDF viewer endpoint with highlight overlays (PRP 18)."""

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session as get_db
from src.config.settings import Settings, get_settings
from src.models.entities import Document, QueryResponseCache
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/viewer", tags=["viewer"])


async def get_response_highlights(response_id: str, db: Session) -> dict:
    """Get stored response highlights."""
    cache_entry = db.query(QueryResponseCache).filter(
        QueryResponseCache.id == response_id
    ).first()
    
    if not cache_entry:
        return {}
    
    # Check if expired
    if cache_entry.expires_at and cache_entry.expires_at < datetime.utcnow():
        db.delete(cache_entry)
        db.commit()
        return {}
    
    return {
        "highlights": cache_entry.highlights or [],
        "response": cache_entry.response,
        "query": cache_entry.query
    }


@router.get("/pdf/{document_id}")
async def view_pdf_with_highlights(
    document_id: str,
    response_id: Optional[str] = Query(None),
    page: Optional[int] = Query(None),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db)
):
    """Serve PDF viewer with highlights."""
    
    # Check if viewer is enabled
    if not getattr(settings, 'enable_pdf_viewer', False):
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
        initial_page=page or 1
    )
    
    return HTMLResponse(content=viewer_html)


@router.get("/pdf-file/{document_id}")
async def serve_pdf_file(
    document_id: str,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db)
):
    """Serve raw PDF file."""
    if not getattr(settings, 'enable_pdf_viewer', False):
        raise HTTPException(403, "PDF viewer is disabled")
        
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(404, "Document not found")
    
    # Construct file path
    docs_path = getattr(settings, 'docs_path', '/app/docs')
    file_path = f"{docs_path}/{document.content_type}/{document.filename}"
    
    # Fallback path structure
    if not os.path.exists(file_path):
        file_path = f"{docs_path}/{document.filename}"
    
    if not os.path.exists(file_path):
        # Try without subdirectory
        file_path = f"{docs_path}/protocols/{document.filename}"
        
    if not os.path.exists(file_path):
        file_path = f"{docs_path}/forms/{document.filename}"
        
    if not os.path.exists(file_path):
        raise HTTPException(404, f"PDF file not found: {document.filename}")
        
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=document.filename
    )


def generate_viewer_html(
    document_id: str,
    document_name: str,
    highlights: list,
    initial_page: int = 1
) -> str:
    """Generate HTML for PDF viewer with highlights."""
    
    highlights_json = json.dumps(highlights, indent=2)
    
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
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f5f7fa;
                overflow: hidden;
            }}
            #header {{
                background: #2c3e50;
                color: white;
                padding: 10px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                z-index: 1000;
                position: relative;
            }}
            #pdf-container {{
                display: flex;
                height: calc(100vh - 60px);
                overflow: hidden;
            }}
            #pdf-viewer-area {{
                flex: 1;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
                overflow: auto;
                background: #ecf0f1;
            }}
            #pdf-viewer {{
                background: white;
                box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                position: relative;
                max-width: 100%;
                max-height: 100%;
            }}
            .highlight-overlay {{
                position: absolute;
                background: rgba(255, 235, 59, 0.4);
                border: 2px solid #FFC107;
                pointer-events: none;
                mix-blend-mode: multiply;
                transition: opacity 0.2s ease;
            }}
            .highlight-overlay.hidden {{
                opacity: 0;
            }}
            #controls {{
                display: flex;
                gap: 10px;
                align-items: center;
                flex-wrap: wrap;
            }}
            button {{
                background: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s ease;
            }}
            button:hover {{
                background: #2980b9;
            }}
            button:disabled {{
                background: #95a5a6;
                cursor: not-allowed;
            }}
            #page-info {{
                margin: 0 10px;
                font-weight: 500;
            }}
            #highlight-list {{
                width: 350px;
                background: white;
                border-left: 1px solid #ddd;
                padding: 20px;
                overflow-y: auto;
                max-height: 100%;
            }}
            #highlight-list h4 {{
                margin-top: 0;
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }}
            .highlight-item {{
                padding: 12px;
                margin: 8px 0;
                background: #f8f9fa;
                border-radius: 8px;
                cursor: pointer;
                border-left: 4px solid #3498db;
                transition: all 0.2s ease;
            }}
            .highlight-item:hover {{
                background: #e9ecef;
                transform: translateY(-1px);
            }}
            .highlight-item.active {{
                background: #d4e6f1;
                border-left-color: #2874a6;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            .highlight-page {{
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 5px;
            }}
            .highlight-snippet {{
                font-size: 13px;
                color: #5a6c7d;
                line-height: 1.4;
                margin: 5px 0;
            }}
            .highlight-confidence {{
                font-size: 11px;
                color: #7f8c8d;
                margin-top: 8px;
            }}
            .loading {{
                text-align: center;
                padding: 20px;
                color: #7f8c8d;
            }}
            .error {{
                text-align: center;
                padding: 20px;
                color: #e74c3c;
                background: #fdf2f2;
                border-radius: 6px;
                margin: 10px;
            }}
            #zoom-level {{
                min-width: 60px;
                text-align: center;
                font-weight: 500;
            }}
            .no-highlights {{
                text-align: center;
                padding: 20px;
                color: #7f8c8d;
                font-style: italic;
            }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    </head>
    <body>
        <div id="header">
            <div>
                <h3 style="margin: 0; font-size: 18px;">📄 {document_name}</h3>
            </div>
            <div id="controls">
                <button onclick="previousPage()" id="prev-btn">← Previous</button>
                <span id="page-info">Page <span id="current-page">1</span> of <span id="total-pages">-</span></span>
                <button onclick="nextPage()" id="next-btn">Next →</button>
                <span style="margin: 0 10px; color: #bdc3c7;">|</span>
                <button onclick="zoomOut()" id="zoom-out-btn">Zoom Out</button>
                <span id="zoom-level">100%</span>
                <button onclick="zoomIn()" id="zoom-in-btn">Zoom In</button>
                <span style="margin: 0 10px; color: #bdc3c7;">|</span>
                <button onclick="toggleHighlights()" id="highlight-toggle">Hide Highlights</button>
            </div>
        </div>
        
        <div id="pdf-container">
            <div id="pdf-viewer-area">
                <canvas id="pdf-viewer"></canvas>
                <div class="loading" id="loading">Loading PDF...</div>
            </div>
            
            <div id="highlight-list">
                <h4>📍 Source Highlights</h4>
                <div id="highlight-items">
                    <div class="loading">Loading highlights...</div>
                </div>
            </div>
        </div>
        
        <script>
            // PDF.js configuration
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
            
            // State
            let pdfDoc = null;
            let currentPage = {initial_page};
            let scale = 1.5;
            let highlights = {highlights_json};
            let showHighlights = true;
            let renderTask = null;
            
            // Load PDF
            const url = '/api/v1/viewer/pdf-file/{document_id}';
            
            console.log('Loading PDF from:', url);
            console.log('Highlights data:', highlights);
            
            pdfjsLib.getDocument(url).promise.then(function(pdf) {{
                pdfDoc = pdf;
                document.getElementById('total-pages').textContent = pdf.numPages;
                document.getElementById('loading').style.display = 'none';
                renderPage(currentPage);
                renderHighlightList();
                updateControls();
            }}).catch(function(error) {{
                console.error('Error loading PDF:', error);
                document.getElementById('loading').innerHTML = '<div class="error">Failed to load PDF: ' + error.message + '</div>';
            }});
            
            function renderPage(pageNum) {{
                if (renderTask) {{
                    renderTask.cancel();
                }}
                
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
                    
                    renderTask = page.render(renderContext);
                    renderTask.promise.then(function() {{
                        renderTask = null;
                        if (showHighlights) {{
                            renderHighlights(pageNum, viewport);
                        }}
                    }});
                    
                    document.getElementById('current-page').textContent = pageNum;
                    updateZoomDisplay();
                }});
            }}
            
            function renderHighlights(pageNum, viewport) {{
                // Clear existing overlays
                document.querySelectorAll('.highlight-overlay').forEach(el => el.remove());
                
                // Get highlights for this page
                const pageHighlights = highlights.filter(h => h.page_number === pageNum);
                
                const canvas = document.getElementById('pdf-viewer');
                const canvasRect = canvas.getBoundingClientRect();
                
                pageHighlights.forEach((highlight, index) => {{
                    if (highlight.bbox) {{
                        const overlay = document.createElement('div');
                        overlay.className = 'highlight-overlay';
                        overlay.id = `highlight-${{pageNum}}-${{index}}`;
                        
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
                
                if (!highlights || highlights.length === 0) {{
                    container.innerHTML = '<div class="no-highlights">No highlights available for this response.</div>';
                    return;
                }}
                
                container.innerHTML = '';
                
                // Group highlights by page
                const byPage = {{}};
                highlights.forEach(h => {{
                    if (!byPage[h.page_number]) byPage[h.page_number] = [];
                    byPage[h.page_number].push(h);
                }});
                
                Object.keys(byPage).sort((a, b) => parseInt(a) - parseInt(b)).forEach(pageNum => {{
                    byPage[pageNum].forEach((highlight, index) => {{
                        const item = document.createElement('div');
                        item.className = 'highlight-item';
                        if (parseInt(pageNum) === currentPage) {{
                            item.classList.add('active');
                        }}
                        
                        const confidencePercent = Math.round(highlight.confidence * 100);
                        const snippet = highlight.text_snippet || 'Source highlight';
                        const truncatedSnippet = snippet.length > 120 ? snippet.substring(0, 120) + '...' : snippet;
                        
                        item.innerHTML = `
                            <div class="highlight-page">📄 Page ${{pageNum}}</div>
                            <div class="highlight-snippet">${{truncatedSnippet}}</div>
                            <div class="highlight-confidence">Confidence: ${{confidencePercent}}%</div>
                        `;
                        
                        item.onclick = () => {{
                            if (currentPage !== parseInt(pageNum)) {{
                                currentPage = parseInt(pageNum);
                                renderPage(currentPage);
                            }}
                            updateActiveHighlight();
                        }};
                        
                        container.appendChild(item);
                    }});
                }});
            }}
            
            function updateActiveHighlight() {{
                document.querySelectorAll('.highlight-item').forEach(item => {{
                    item.classList.remove('active');
                }});
                
                // Find and activate items for current page
                document.querySelectorAll('.highlight-item').forEach(item => {{
                    const pageText = item.querySelector('.highlight-page').textContent;
                    const pageNum = parseInt(pageText.replace('📄 Page ', ''));
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
                    updateControls();
                }}
            }}
            
            function previousPage() {{
                if (currentPage > 1) {{
                    currentPage--;
                    renderPage(currentPage);
                    updateActiveHighlight();
                    updateControls();
                }}
            }}
            
            function toggleHighlights() {{
                showHighlights = !showHighlights;
                const button = document.getElementById('highlight-toggle');
                
                if (showHighlights) {{
                    button.textContent = 'Hide Highlights';
                    document.querySelectorAll('.highlight-overlay').forEach(el => {{
                        el.classList.remove('hidden');
                    }});
                }} else {{
                    button.textContent = 'Show Highlights';
                    document.querySelectorAll('.highlight-overlay').forEach(el => {{
                        el.classList.add('hidden');
                    }});
                }}
            }}
            
            function zoomIn() {{
                if (scale < 3.0) {{
                    scale += 0.25;
                    renderPage(currentPage);
                    updateControls();
                }}
            }}
            
            function zoomOut() {{
                if (scale > 0.5) {{
                    scale -= 0.25;
                    renderPage(currentPage);
                    updateControls();
                }}
            }}
            
            function updateZoomDisplay() {{
                const zoomPercent = Math.round(scale * 100);
                document.getElementById('zoom-level').textContent = zoomPercent + '%';
            }}
            
            function updateControls() {{
                document.getElementById('prev-btn').disabled = currentPage <= 1;
                document.getElementById('next-btn').disabled = !pdfDoc || currentPage >= pdfDoc.numPages;
                document.getElementById('zoom-out-btn').disabled = scale <= 0.5;
                document.getElementById('zoom-in-btn').disabled = scale >= 3.0;
            }}
            
            // Keyboard navigation
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {{
                    e.preventDefault();
                    previousPage();
                }}
                if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {{
                    e.preventDefault();
                    nextPage();
                }}
                if (e.key === 'h' || e.key === 'H') {{
                    e.preventDefault();
                    toggleHighlights();
                }}
                if (e.key === '=' || e.key === '+') {{
                    e.preventDefault();
                    zoomIn();
                }}
                if (e.key === '-' || e.key === '_') {{
                    e.preventDefault();
                    zoomOut();
                }}
            }});
            
            // Initialize
            updateZoomDisplay();
        </script>
    </body>
    </html>
    """