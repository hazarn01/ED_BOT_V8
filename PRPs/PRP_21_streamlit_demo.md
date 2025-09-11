# PRP 21: Optional Streamlit Demo App

## Problem Statement
Developers and stakeholders need an interactive UI to test and validate the enhanced retrieval features (hybrid search, source highlighting, table extraction) without building a full frontend. A Streamlit demo app can provide quick visual feedback while keeping production API unchanged.

## Success Criteria
- Interactive web UI for testing queries
- Visual display of search results and highlights
- Optional service behind compose profile
- Dev-only (disabled in production)
- No coupling to main API process

## Implementation Approach

### 1. Streamlit App Structure
```python
# streamlit_app/main.py
import streamlit as st
import requests
import json
import pandas as pd
from typing import Dict, List
import time

# Configure Streamlit page
st.set_page_config(
    page_title="EDBotv8 Demo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

class EDBotClient:
    """Client for EDBotv8 API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        
    def health_check(self) -> bool:
        """Check if API is healthy"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
            
    def query(self, query: str) -> Dict:
        """Submit query to API"""
        response = requests.post(
            f"{self.base_url}/api/v1/query",
            json={"query": query},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
        
    def get_documents(self) -> List[Dict]:
        """Get list of available documents"""
        response = requests.get(f"{self.base_url}/api/v1/documents")
        if response.status_code == 200:
            return response.json()
        return []
        
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/cache/stats")
            if response.status_code == 200:
                return response.json()
            return {}
        except:
            return {}

def main():
    st.title("🏥 EDBotv8 Medical AI Assistant Demo")
    st.markdown("Interactive demo for hybrid search and enhanced features")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        api_url = st.text_input(
            "API URL",
            value="http://localhost:8001",
            help="Base URL for EDBotv8 API"
        )
        
        client = EDBotClient(api_url)
        
        # Health check
        if st.button("Check API Health"):
            with st.spinner("Checking API health..."):
                healthy = client.health_check()
                if healthy:
                    st.success("✅ API is healthy")
                else:
                    st.error("❌ API is not responding")
                    
        st.divider()
        
        # Feature toggles (informational)
        st.header("Feature Status")
        features = {
            "Hybrid Search": True,
            "Source Highlighting": True,
            "Table Extraction": True,
            "Semantic Cache": True,
            "PDF Viewer": True
        }
        
        for feature, enabled in features.items():
            if enabled:
                st.success(f"✅ {feature}")
            else:
                st.warning(f"⚠️ {feature} (Disabled)")
                
        # Cache stats
        st.divider()
        st.header("Cache Statistics")
        cache_stats = client.get_cache_stats()
        if cache_stats.get("enabled"):
            for query_type, stats in cache_stats.get("stats", {}).items():
                st.metric(
                    query_type.replace("_", " ").title(),
                    f"{stats['entries']} entries",
                    f"{stats['total_hits']} hits"
                )
        else:
            st.info("Cache not enabled")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Query Interface")
        
        # Sample queries
        sample_queries = [
            "What is the ED STEMI protocol?",
            "Show me the blood transfusion form",
            "Who is on call for cardiology?",
            "What are the criteria for sepsis?",
            "What is the dosage for metoprolol?",
            "Summarize the chest pain workup"
        ]
        
        selected_sample = st.selectbox(
            "Sample Queries",
            [""] + sample_queries,
            help="Select a sample query or type your own"
        )
        
        # Query input
        query = st.text_area(
            "Your Question",
            value=selected_sample,
            height=100,
            placeholder="Ask a medical question..."
        )
        
        col_query, col_clear = st.columns([3, 1])
        with col_query:
            submit_query = st.button("Submit Query", type="primary")
        with col_clear:
            if st.button("Clear"):
                st.experimental_rerun()
                
        # Query processing
        if submit_query and query.strip():
            with st.spinner("Processing query..."):
                try:
                    start_time = time.time()
                    result = client.query(query.strip())
                    response_time = time.time() - start_time
                    
                    # Display response
                    st.subheader("Response")
                    st.write(result.get("answer", "No answer provided"))
                    
                    # Response metadata
                    col_meta1, col_meta2, col_meta3 = st.columns(3)
                    
                    with col_meta1:
                        st.metric("Response Time", f"{response_time:.2f}s")
                    with col_meta2:
                        st.metric("Confidence", f"{result.get('confidence', 0):.1%}")
                    with col_meta3:
                        query_type = result.get("query_type", "unknown")
                        st.metric("Query Type", query_type.replace("_", " ").title())
                        
                    # Cache hit indicator
                    if result.get("metadata", {}).get("cache_hit"):
                        st.info(f"🎯 Cache Hit (similarity: {result['metadata'].get('similarity', 0):.3f})")
                        
                    # Sources
                    st.subheader("Sources")
                    sources = result.get("sources", [])
                    if sources:
                        for i, source in enumerate(sources, 1):
                            st.markdown(f"{i}. {source}")
                    else:
                        st.info("No sources provided")
                        
                    # Highlighted sources (if available)
                    highlighted = result.get("highlighted_sources", [])
                    if highlighted:
                        st.subheader("Highlighted Sources")
                        for highlight in highlighted:
                            with st.expander(
                                f"📄 {highlight['document_name']} (Page {highlight['page_number']})",
                                expanded=False
                            ):
                                st.write(highlight["text_snippet"])
                                st.caption(f"Confidence: {highlight['confidence']:.1%}")
                                
                    # PDF Viewer link
                    viewer_url = result.get("viewer_url")
                    if viewer_url:
                        st.markdown(f"[📖 View with Highlights]({api_url}{viewer_url})")
                        
                except requests.exceptions.RequestException as e:
                    st.error(f"API Error: {e}")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    with col2:
        st.header("Document Library")
        
        # Get available documents
        try:
            documents = client.get_documents()
            if documents:
                doc_data = []
                for doc in documents:
                    doc_data.append({
                        "Name": doc.get("filename", "Unknown"),
                        "Type": doc.get("content_type", "Unknown"),
                        "Pages": doc.get("metadata", {}).get("page_count", "?")
                    })
                    
                df = pd.DataFrame(doc_data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No documents found")
                
        except Exception as e:
            st.warning(f"Could not load documents: {e}")
            
        # Query types help
        st.subheader("Query Types")
        query_types_help = {
            "CONTACT": "Who is on call for [specialty]?",
            "FORM": "Show me the [form name] form",
            "PROTOCOL": "What is the [protocol name] protocol?",
            "CRITERIA": "What are criteria for [condition]?",
            "DOSAGE": "What is the dosage for [medication]?",
            "SUMMARY": "Summarize [topic]"
        }
        
        for qtype, example in query_types_help.items():
            st.markdown(f"**{qtype}**: {example}")

if __name__ == "__main__":
    main()
```

### 2. Docker Configuration
```dockerfile
# streamlit_app/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```text
# streamlit_app/requirements.txt
streamlit==1.28.1
requests==2.31.0
pandas==2.1.3
plotly==5.17.0
```

### 3. Docker Compose Integration
```yaml
# docker-compose.v8.yml (additions)
services:
  # ... existing services ...
  
  streamlit:
    build: ./streamlit_app
    container_name: edbot-streamlit
    profiles: [ui]  # Optional profile
    ports:
      - "8501:8501"
    environment:
      - STREAMLIT_SERVER_HEADLESS=true
      - STREAMLIT_SERVER_ENABLE_CORS=false
    depends_on:
      - api
    networks:
      - edbot-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 4. Enhanced Demo Features
```python
# streamlit_app/pages/1_Advanced_Search.py
import streamlit as st

st.title("🔍 Advanced Search Features")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Hybrid Search Comparison")
    
    query = st.text_input("Test Query", value="STEMI protocol")
    
    if st.button("Compare Search Types"):
        # Test pgvector only
        # Test hybrid search
        # Display side-by-side comparison
        pass

with col2:
    st.subheader("Table Extraction")
    
    # Show extracted tables
    # Allow filtering by table type
    pass
```

```python
# streamlit_app/pages/2_Cache_Management.py
import streamlit as st

st.title("🗄️ Cache Management")

# Cache statistics visualization
# Cache invalidation controls
# Performance metrics
```

### 5. Makefile Integration
```makefile
# Makefile.v8 (additions)
up-ui:  ## Start stack with UI demo
	docker compose --profile cpu --profile ui up -d
	@echo "Demo UI available at http://localhost:8501"
	
ui-logs:  ## View Streamlit logs
	docker compose logs -f streamlit

ui-build:  ## Rebuild Streamlit container
	docker compose build streamlit
```

### 6. Configuration
```python
# src/config/settings.py (addition)
class Settings(BaseSettings):
    enable_streamlit_demo: bool = Field(
        default=False,
        description="Enable Streamlit demo UI (dev only)"
    )
```

## Testing Strategy
```python
# tests/integration/test_streamlit_integration.py
async def test_streamlit_health():
    """Test that Streamlit app is accessible"""
    response = requests.get("http://localhost:8501/_stcore/health")
    assert response.status_code == 200
    
async def test_api_connectivity():
    """Test that Streamlit can connect to API"""
    # Run sample query through Streamlit client
    # Verify response matches direct API call
    pass
```

## Security Considerations
- Demo disabled by default
- No authentication (dev-only)
- Read-only access to API
- No sensitive data display
- Consider basic auth for staging

## Performance Impact
- Separate container (no impact on API)
- Only runs when UI profile enabled
- ~100MB memory footprint
- Client-side only (no server state)

## Production Considerations
- Never enable in production
- Use `profiles: [ui]` to gate deployment
- Consider separate staging deployment
- Add authentication if needed

## Rollback Plan
1. Stop UI service: `docker compose stop streamlit`
2. Remove profile from compose command
3. UI completely decoupled from API
4. No data persistence to clean up

## Development Workflow
```bash
# Start with UI
make up-ui

# Access demo
open http://localhost:8501

# View logs
make ui-logs

# Rebuild after changes
make ui-build
```