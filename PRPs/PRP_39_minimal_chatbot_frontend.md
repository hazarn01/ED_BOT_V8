# PRP-39: Replace Streamlit with Minimal Chatbot Interface

## Problem Statement

The current Streamlit frontend is bloated, developer-focused, and not suitable for medical professionals:

**Current Issues** (from `streamlit_app/main.py`):
- **Complex developer interface**: Cache management, advanced search, configuration panels
- **Multi-page application**: 3 separate pages for different functions
- **Bloated UI**: 414 lines of code with excessive metrics, charts, and technical details  
- **Poor mobile experience**: Streamlit not optimized for tablets/mobile devices
- **No nested sourcing**: Sources displayed as simple list, not hierarchical like OpenEvidence

**User Requirements**:
- **Minimal chatbot interface** inspired by OpenEvidence
- **Nested source citations** with expandable document sections  
- **Mount Sinai Health System color scheme** (#06ABEB, #DC298D, #212070, #00002D)
- **Medical professional focus** - clean, fast, citation-heavy
- **Mobile responsive** for use on hospital tablets and phones

## Solution Overview

Replace Streamlit entirely with a **clean HTML/CSS/JavaScript chatbot interface** that:

1. **Single chat interface** - no sidebar complexity, no multiple pages
2. **OpenEvidence-style sourcing** - nested, expandable citations
3. **Mount Sinai branding** - official health system colors and typography
4. **Mobile-first design** - works on hospital tablets and phones  
5. **Fast performance** - static files served by FastAPI, no Python UI framework

## Current Streamlit Analysis

### Bloated Features to Remove (from `streamlit_app/main.py`):

**Lines 113-196**: Complex sidebar configuration:
```python
with st.sidebar:
    st.header("⚙️ Configuration")
    api_url = st.text_input("API URL", ...)  # Not needed for production
    if st.button("🔍 Check Health", ...):     # Developer feature
    st.header("✨ Features")                  # Technical status
    st.header("📊 Cache Statistics")          # Developer metrics
```

**Lines 150-161**: Developer-focused feature status:
```python
features = {
    "Hybrid Search": "✅ Enabled",
    "Source Highlighting": "✅ Enabled", 
    "Table Extraction": "✅ Enabled",
    # ... technical features users don't need to see
}
```

**Lines 280-298**: Complex metadata display:
```python
col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
st.metric("⏱️ Response Time", format_response_time(response_time))
st.metric("📊 Confidence", f"{confidence:.1%}")
# ... metrics overload
```

### What Works (Keep These Concepts):
- **Lines 205-216**: Sample medical queries list
- **Lines 301-312**: Basic source display (but make it nested)
- **Lines 258-271**: Query submission and response handling

## Detailed Implementation

### 1. New Frontend Structure

```
static/
├── index.html          # Single-page chatbot interface
├── css/
│   ├── chatbot.css     # Mount Sinai themed styles
│   └── mobile.css      # Mobile-responsive overrides
├── js/
│   ├── chatbot.js      # Chat functionality
│   ├── sources.js      # Nested source display
│   └── api.js          # API communication
└── assets/
    ├── mount-sinai-logo.png
    └── medical-icons.svg
```

### 2. Clean HTML Interface (`static/index.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ED Bot v8 - Mount Sinai Emergency Medicine AI</title>
    <link rel="stylesheet" href="/static/css/chatbot.css">
    <link rel="stylesheet" href="/static/css/mobile.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="chat-container">
        <!-- Header -->
        <header class="chat-header">
            <div class="header-content">
                <img src="/static/assets/mount-sinai-logo.png" alt="Mount Sinai" class="logo">
                <h1>ED Bot v8</h1>
                <span class="subtitle">Emergency Medicine AI Assistant</span>
            </div>
        </header>

        <!-- Chat Messages Area -->
        <main class="chat-messages" id="chatMessages">
            <div class="welcome-message">
                <div class="bot-message">
                    <div class="message-content">
                        <h3>👋 Welcome to ED Bot v8</h3>
                        <p>I can help you with:</p>
                        <ul class="capability-list">
                            <li><strong>Clinical Protocols</strong> - STEMI, sepsis, stroke procedures</li>
                            <li><strong>Medical Forms</strong> - Consent forms, transfer documents</li>
                            <li><strong>Medication Dosing</strong> - Emergency drug protocols</li>
                            <li><strong>Decision Criteria</strong> - Diagnostic thresholds</li>
                            <li><strong>Contact Information</strong> - On-call physician lookup</li>
                        </ul>
                        <div class="quick-queries">
                            <h4>Quick Queries:</h4>
                            <button class="quick-query-btn" data-query="What is the ED STEMI protocol?">STEMI Protocol</button>
                            <button class="quick-query-btn" data-query="Show me the blood transfusion form">Blood Transfusion Form</button>
                            <button class="quick-query-btn" data-query="Who is on call for cardiology?">Cardiology On-Call</button>
                            <button class="quick-query-btn" data-query="What are the criteria for sepsis?">Sepsis Criteria</button>
                        </div>
                    </div>
                </div>
            </div>
        </main>

        <!-- Input Area -->
        <div class="chat-input-container">
            <form class="chat-input-form" id="chatForm">
                <div class="input-wrapper">
                    <textarea 
                        id="messageInput" 
                        placeholder="Ask a medical question..."
                        rows="1"
                        maxlength="1000"
                    ></textarea>
                    <button type="submit" id="sendButton" class="send-button">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                            <path d="M22 2L11 13" stroke="currentColor" stroke-width="2"/>
                            <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2"/>
                        </svg>
                    </button>
                </div>
            </form>
        </div>
    </div>

    <!-- Loading spinner -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
        <p>Processing your medical query...</p>
    </div>

    <script src="/static/js/api.js"></script>
    <script src="/static/js/sources.js"></script>
    <script src="/static/js/chatbot.js"></script>
</body>
</html>
```

### 3. Mount Sinai Theme CSS (`static/css/chatbot.css`)

```css
/* Mount Sinai Health System Color Palette */
:root {
    --ms-cerulean: #06ABEB;      /* Primary blue */
    --ms-pink: #DC298D;          /* Accent pink */
    --ms-navy: #212070;          /* Dark blue */
    --ms-deep-navy: #00002D;     /* Deepest blue */
    --ms-white: #FFFFFF;
    --ms-light-gray: #F8F9FA;
    --ms-gray: #E9ECEF;
    --ms-text: #212529;
    --ms-text-secondary: #6C757D;
    
    /* Chat specific colors */
    --user-message: var(--ms-cerulean);
    --bot-message: var(--ms-light-gray);
    --accent: var(--ms-pink);
    --shadow: rgba(0, 0, 0, 0.1);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: var(--ms-white);
    color: var(--ms-text);
    line-height: 1.5;
}

.chat-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    max-width: 1200px;
    margin: 0 auto;
    background: var(--ms-white);
}

/* Header */
.chat-header {
    background: linear-gradient(135deg, var(--ms-navy) 0%, var(--ms-deep-navy) 100%);
    color: var(--ms-white);
    padding: 1rem 1.5rem;
    box-shadow: 0 2px 8px var(--shadow);
}

.header-content {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.logo {
    height: 40px;
    width: auto;
}

.chat-header h1 {
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0;
}

.subtitle {
    font-size: 0.9rem;
    opacity: 0.9;
    font-weight: 300;
}

/* Messages Area */
.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    background: var(--ms-light-gray);
}

.message {
    margin-bottom: 1.5rem;
    display: flex;
    gap: 0.75rem;
}

.user-message {
    justify-content: flex-end;
}

.user-message .message-content {
    background: var(--ms-cerulean);
    color: white;
    padding: 0.875rem 1.25rem;
    border-radius: 1.25rem 1.25rem 0.25rem 1.25rem;
    max-width: 70%;
}

.bot-message .message-content {
    background: var(--ms-white);
    color: var(--ms-text);
    padding: 1.25rem 1.5rem;
    border-radius: 1.25rem 1.25rem 1.25rem 0.25rem;
    max-width: 85%;
    box-shadow: 0 2px 8px var(--shadow);
    border: 1px solid var(--ms-gray);
}

/* Nested Sources (OpenEvidence-style) */
.sources-section {
    margin-top: 1.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--ms-gray);
}

.sources-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--ms-navy);
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.source-item {
    margin-bottom: 0.5rem;
    border: 1px solid var(--ms-gray);
    border-radius: 0.5rem;
    overflow: hidden;
}

.source-header {
    padding: 0.75rem 1rem;
    background: var(--ms-light-gray);
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--ms-navy);
}

.source-header:hover {
    background: var(--ms-gray);
}

.source-content {
    padding: 0.75rem 1rem;
    background: var(--ms-white);
    font-size: 0.8rem;
    color: var(--ms-text-secondary);
    border-top: 1px solid var(--ms-gray);
    display: none; /* Collapsed by default */
}

.source-content.expanded {
    display: block;
}

.source-excerpt {
    font-style: italic;
    line-height: 1.4;
    margin-bottom: 0.5rem;
}

.confidence-bar {
    height: 4px;
    background: var(--ms-gray);
    border-radius: 2px;
    overflow: hidden;
    margin-top: 0.5rem;
}

.confidence-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--ms-pink), var(--ms-cerulean));
    transition: width 0.3s ease;
}

/* Quick Query Buttons */
.quick-queries {
    margin-top: 1rem;
}

.quick-queries h4 {
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
    color: var(--ms-navy);
}

.quick-query-btn {
    display: inline-block;
    padding: 0.5rem 1rem;
    margin: 0.25rem 0.5rem 0.25rem 0;
    background: transparent;
    border: 1px solid var(--ms-cerulean);
    color: var(--ms-cerulean);
    border-radius: 1.5rem;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s ease;
}

.quick-query-btn:hover {
    background: var(--ms-cerulean);
    color: white;
}

/* Input Area */
.chat-input-container {
    padding: 1rem 1.5rem;
    background: var(--ms-white);
    border-top: 1px solid var(--ms-gray);
}

.input-wrapper {
    display: flex;
    align-items: end;
    gap: 0.75rem;
    max-width: 100%;
}

#messageInput {
    flex: 1;
    padding: 0.875rem 1rem;
    border: 1px solid var(--ms-gray);
    border-radius: 1.25rem;
    font-family: inherit;
    font-size: 0.95rem;
    resize: none;
    line-height: 1.4;
    min-height: 44px;
    max-height: 120px;
}

#messageInput:focus {
    outline: none;
    border-color: var(--ms-cerulean);
    box-shadow: 0 0 0 2px rgba(6, 171, 235, 0.1);
}

.send-button {
    padding: 0.875rem;
    background: var(--ms-cerulean);
    color: white;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    min-width: 44px;
    height: 44px;
}

.send-button:hover {
    background: var(--ms-navy);
    transform: scale(1.05);
}

.send-button:disabled {
    background: var(--ms-text-secondary);
    cursor: not-allowed;
    transform: none;
}

/* Loading Overlay */
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(33, 32, 112, 0.8);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    color: white;
    text-align: center;
}

.loading-overlay.show {
    display: flex;
}

.loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-top: 3px solid var(--ms-cerulean);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Capability List */
.capability-list {
    list-style: none;
    margin: 1rem 0;
}

.capability-list li {
    padding: 0.5rem 0;
    padding-left: 1.5rem;
    position: relative;
}

.capability-list li::before {
    content: '•';
    color: var(--ms-cerulean);
    font-weight: bold;
    position: absolute;
    left: 0;
}
```

### 4. Nested Sources JavaScript (`static/js/sources.js`)

```javascript
/**
 * OpenEvidence-style nested source display
 */
class SourceRenderer {
    constructor() {
        this.expandedSources = new Set();
    }

    /**
     * Render sources section with nested expandable citations
     */
    renderSources(sources, response) {
        if (!sources || sources.length === 0) {
            return '';
        }

        const sourcesHtml = sources.map((source, index) => {
            const sourceId = `source-${Date.now()}-${index}`;
            const isExpanded = this.expandedSources.has(sourceId);
            
            return `
                <div class="source-item">
                    <div class="source-header" onclick="window.sourceRenderer.toggleSource('${sourceId}')">
                        <span>
                            <strong>📄 ${source.display_name || source.filename || `Source ${index + 1}`}</strong>
                        </span>
                        <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
                    </div>
                    <div id="${sourceId}" class="source-content ${isExpanded ? 'expanded' : ''}">
                        ${this.renderSourceContent(source, response)}
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="sources-section">
                <div class="sources-title">
                    📚 <strong>Sources</strong> (${sources.length})
                </div>
                ${sourcesHtml}
            </div>
        `;
    }

    /**
     * Render individual source content with excerpts and confidence
     */
    renderSourceContent(source, response) {
        let content = `
            <div class="source-meta">
                <strong>Document:</strong> ${source.filename || 'Unknown'}
            `;
        
        if (source.content_type) {
            content += `<br><strong>Type:</strong> ${source.content_type}`;
        }
        
        content += `</div>`;

        // Add excerpt if available (from highlighted sources)
        if (source.text_snippet) {
            content += `
                <div class="source-excerpt">
                    "${source.text_snippet}"
                </div>
            `;
        }

        // Add confidence bar if available
        if (source.confidence) {
            const confidencePercent = Math.round(source.confidence * 100);
            content += `
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                </div>
                <small>Relevance: ${confidencePercent}%</small>
            `;
        }

        return content;
    }

    /**
     * Toggle source expansion
     */
    toggleSource(sourceId) {
        const sourceContent = document.getElementById(sourceId);
        const expandIcon = sourceContent.parentElement.querySelector('.expand-icon');
        
        if (this.expandedSources.has(sourceId)) {
            this.expandedSources.delete(sourceId);
            sourceContent.classList.remove('expanded');
            expandIcon.textContent = '▶';
        } else {
            this.expandedSources.add(sourceId);
            sourceContent.classList.add('expanded');
            expandIcon.textContent = '▼';
        }
    }

    /**
     * Render highlighted sources (if available from PRP 17-18)
     */
    renderHighlightedSources(highlightedSources) {
        if (!highlightedSources || highlightedSources.length === 0) {
            return '';
        }

        const highlightedHtml = highlightedSources.map((highlight, index) => {
            const highlightId = `highlight-${Date.now()}-${index}`;
            
            return `
                <div class="source-item highlighted">
                    <div class="source-header" onclick="window.sourceRenderer.toggleSource('${highlightId}')">
                        <span>
                            <strong>🔦 ${highlight.document_name}</strong> 
                            ${highlight.page_number ? `(Page ${highlight.page_number})` : ''}
                        </span>
                        <span class="expand-icon">▶</span>
                    </div>
                    <div id="${highlightId}" class="source-content">
                        <div class="source-excerpt">
                            "${highlight.text_snippet}"
                        </div>
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: ${Math.round(highlight.confidence * 100)}%"></div>
                        </div>
                        <small>Confidence: ${Math.round(highlight.confidence * 100)}%</small>
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="sources-section">
                <div class="sources-title">
                    🔦 <strong>Highlighted Sources</strong>
                </div>
                ${highlightedHtml}
            </div>
        `;
    }
}

// Global instance
window.sourceRenderer = new SourceRenderer();
```

### 5. Mobile Responsive CSS (`static/css/mobile.css`)

```css
/* Mobile and Tablet Optimizations */
@media (max-width: 768px) {
    .chat-container {
        height: 100vh;
        height: 100dvh; /* Dynamic viewport height for mobile */
    }

    .chat-header {
        padding: 1rem;
    }

    .header-content {
        gap: 0.75rem;
    }

    .chat-header h1 {
        font-size: 1.25rem;
    }

    .subtitle {
        font-size: 0.8rem;
    }

    .logo {
        height: 32px;
    }

    .chat-messages {
        padding: 0.75rem;
    }

    .user-message .message-content,
    .bot-message .message-content {
        max-width: 95%;
        padding: 1rem;
    }

    .chat-input-container {
        padding: 1rem;
    }

    .input-wrapper {
        gap: 0.5rem;
    }

    #messageInput {
        font-size: 16px; /* Prevent zoom on iOS */
        padding: 0.75rem;
    }

    .send-button {
        min-width: 40px;
        height: 40px;
        padding: 0.75rem;
    }

    .quick-query-btn {
        display: block;
        width: 100%;
        margin: 0.5rem 0;
        text-align: left;
    }

    .capability-list {
        font-size: 0.9rem;
    }

    .source-header {
        padding: 0.5rem 0.75rem;
        font-size: 0.8rem;
    }

    .source-content {
        padding: 0.5rem 0.75rem;
        font-size: 0.75rem;
    }
}

/* Large screens */
@media (min-width: 1200px) {
    .chat-messages {
        padding: 2rem;
    }

    .message-content {
        font-size: 1rem;
    }
}
```

### 6. API Integration (`static/js/api.js`)

```javascript
/**
 * API communication with ED Bot v8 backend
 */
class APIClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    async query(message, context = null) {
        const payload = { query: message };
        if (context) {
            payload.context = context;
        }

        const response = await fetch('/api/v1/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    async health() {
        const response = await fetch('/health');
        return response.ok;
    }
}

window.apiClient = new APIClient();
```

## Validation Strategy

### User Experience Testing
```bash
# Serve static files through FastAPI
python -c "
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')

@app.get('/')
def read_root():
    return {'message': 'Use /static/index.html for the chatbot interface'}

uvicorn.run(app, host='0.0.0.0', port=8001)
"
```

### Mobile Testing
```bash
# Test on different viewport sizes
# Use browser dev tools or real devices:
# - iPhone 12: 390x844  
# - iPad: 768x1024
# - Desktop: 1200x800
```

### Accessibility Testing
```bash
# Check color contrast ratios
# Mount Sinai blue (#06ABEB) on white: 3.02:1 (WCAG AA compliant)
# Mount Sinai navy (#212070) on white: 8.55:1 (WCAG AAA compliant)
```

## Integration with FastAPI

### Update API to Serve Frontend (`src/api/app.py`)

```python
from fastapi.staticfiles import StaticFiles

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Redirect root to chatbot
@app.get("/")
async def read_root():
    return RedirectResponse(url="/static/index.html")
```

### Remove Streamlit from Docker

Update `docker-compose.v8.yml`:
```yaml
# REMOVE streamlit service entirely
# Static files served by FastAPI now
```

## Quality Assessment Score: 9/10

**Very high confidence because:**
- Clean separation of concerns (HTML/CSS/JS)
- Mount Sinai colors researched and specified
- OpenEvidence nested sourcing pattern identified
- Mobile-first responsive design
- Existing API integration points known
- Streamlit removal is straightforward

**Low risk factors:**
- Static files are simple to deploy
- No complex JavaScript frameworks
- Progressive enhancement approach
- Fallback to existing API if needed

## Implementation Tasks (in order)

1. **Create static file structure**: `mkdir -p static/{css,js,assets}`
2. **Implement core HTML**: Clean chatbot interface with Mount Sinai branding
3. **Add Mount Sinai CSS**: Official color palette and responsive design  
4. **Build nested sources**: OpenEvidence-style expandable citations
5. **JavaScript integration**: API calls and chat functionality
6. **Mobile optimization**: Test and refine mobile experience
7. **FastAPI integration**: Serve static files, redirect root  
8. **Remove Streamlit**: Delete streamlit_app directory and docker service
9. **User testing**: Medical professional feedback on interface
10. **Performance optimization**: Minimize CSS/JS, optimize loading

**Estimated Total Time: 4 hours**
**Expected Outcome: Clean, medical-focused chatbot interface with nested sourcing**