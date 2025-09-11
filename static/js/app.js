class EDBotChat {
    constructor() {
        this.apiBaseUrl = '/api/v1';
        this.sessionId = this.generateSessionId();
        this.recentQueries = this.loadRecentQueries();
        
        console.log('ED Bot Chat initialized:', {
            apiBaseUrl: this.apiBaseUrl,
            sessionId: this.sessionId
        });
        
        this.initializeElements();
        this.setupEventListeners();
        this.checkApiHealth();
        this.updateRecentQueriesUI();
    }

    initializeElements() {
        this.statusElement = document.getElementById('status');
        this.messagesElement = document.getElementById('messages');
        this.queryInput = document.getElementById('queryInput');
        this.sendButton = document.getElementById('sendButton');
        this.charCount = document.getElementById('charCount');
        this.recentQueriesElement = document.getElementById('recentQueries');
    }

    setupEventListeners() {
        // Send button
        this.sendButton.addEventListener('click', () => this.sendQuery());
        
        // Enter key to send (Shift+Enter for new line)
        this.queryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendQuery();
            }
        });

        // Character counter
        this.queryInput.addEventListener('input', () => {
            const count = this.queryInput.value.length;
            this.charCount.textContent = count;
            this.sendButton.disabled = count === 0;
            
            if (count > 450) {
                this.charCount.style.color = '#dc3545';
            } else {
                this.charCount.style.color = '#6c757d';
            }
        });

        // Quick action buttons
        document.querySelectorAll('.quick-action').forEach(button => {
            button.addEventListener('click', () => {
                const query = button.dataset.query;
                this.queryInput.value = query;
                this.queryInput.dispatchEvent(new Event('input'));
                this.sendQuery();
            });
        });

        // Recent queries
        this.recentQueriesElement.addEventListener('click', (e) => {
            if (e.target.classList.contains('recent-item')) {
                const query = e.target.dataset.query;
                this.queryInput.value = query;
                this.queryInput.dispatchEvent(new Event('input'));
            }
        });
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    async checkApiHealth() {
        console.log('Checking API health...');
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
            
            const response = await fetch('/health', {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            console.log('Health response status:', response.status);
            const data = await response.json();
            console.log('Health response data:', data);
            
            if (data.status === 'healthy') {
                this.updateStatus('online', 'API Connected');
            } else {
                this.updateStatus('offline', 'API Issues');
            }
        } catch (error) {
            console.error('Health check failed:', error);
            if (error.name === 'AbortError') {
                this.updateStatus('offline', 'API Timeout');
            } else {
                this.updateStatus('offline', 'API Offline');
            }
        }
    }

    updateStatus(status, text) {
        this.statusElement.className = `status-indicator ${status}`;
        this.statusElement.querySelector('.status-text').textContent = text;
    }

    async sendQuery() {
        const query = this.queryInput.value.trim();
        if (!query) return;

        console.log('Sending query:', query);

        // Add to recent queries
        this.addRecentQuery(query);

        // Clear input
        this.queryInput.value = '';
        this.queryInput.dispatchEvent(new Event('input'));

        // Add user message
        this.addMessage('user', query);

        // Show loading
        const loadingId = this.addLoadingMessage();

        try {
            const startTime = Date.now();
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout for queries
            
            const response = await fetch(`${this.apiBaseUrl}/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    session_id: this.sessionId
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            const data = await response.json();
            const responseTime = Date.now() - startTime;

            // Remove loading message
            this.removeMessage(loadingId);

            // Add assistant response
            this.addMessage('assistant', data.response, {
                queryType: data.query_type,
                confidence: data.confidence,
                sources: data.sources,
                warnings: data.warnings,
                processingTime: data.processing_time || responseTime / 1000,
                pdfLinks: data.pdf_links
            });

        } catch (error) {
            console.error('Query failed:', error);
            this.removeMessage(loadingId);
            
            let errorMessage = "I'm sorry, I'm having trouble processing your request right now. Please try again.";
            if (error.name === 'AbortError') {
                errorMessage = "Query timed out. The request took too long to process. Please try again with a simpler query.";
            }
            
            this.addMessage('assistant', errorMessage, {
                error: true
            });
        }
    }

    addMessage(type, content, meta = {}) {
        const messageId = 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.id = messageId;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (meta.error) {
            contentDiv.classList.add('error');
        }
        
        // Format content with markdown-like styling
        const formattedContent = this.formatContent(content);
        contentDiv.innerHTML = formattedContent;
        
        messageDiv.appendChild(contentDiv);
        
        // Add metadata for assistant messages
        if (type === 'assistant' && !meta.error) {
            const metaDiv = this.createMessageMeta(meta);
            messageDiv.appendChild(metaDiv);
        }
        
        // Add PDF links if available
        if (meta.pdfLinks && meta.pdfLinks.length > 0) {
            const pdfDiv = this.createPdfLinks(meta.pdfLinks);
            messageDiv.appendChild(pdfDiv);
        }
        
        this.messagesElement.appendChild(messageDiv);
        this.scrollToBottom();
        
        return messageId;
    }

    addLoadingMessage() {
        const messageId = 'loading_' + Date.now();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.id = messageId;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = `
            <div class="loading">
                Thinking
                <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        messageDiv.appendChild(contentDiv);
        this.messagesElement.appendChild(messageDiv);
        this.scrollToBottom();
        
        return messageId;
    }

    removeMessage(messageId) {
        const messageElement = document.getElementById(messageId);
        if (messageElement) {
            messageElement.remove();
        }
    }

    formatContent(content) {
        // Basic markdown-like formatting
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold
            .replace(/\*(.*?)\*/g, '<em>$1</em>') // Italic
            .replace(/⚠️ \*\*(.*?)\*\*/g, '<div class="warning"><strong>⚠️ $1</strong></div>') // Warnings
            .replace(/(\d+\.\s.*?)(?=\n|$)/g, '<div style="margin: 8px 0;">$1</div>') // Numbered lists
            .replace(/\n/g, '<br>'); // Line breaks
    }

    createMessageMeta(meta) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';
        
        let confidenceClass = 'medium';
        let confidenceText = 'Medium';
        
        if (meta.confidence >= 0.8) {
            confidenceClass = 'high';
            confidenceText = 'High';
        } else if (meta.confidence < 0.5) {
            confidenceClass = 'low';
            confidenceText = 'Low';
        }
        
        // Create sources display with hover functionality
        const sourcesDisplay = this.createSourcesDisplay(meta.sources);
        
        metaDiv.innerHTML = `
            <span>
                Type: <strong>${meta.queryType || 'unknown'}</strong> • 
                Time: <strong>${(meta.processingTime || 0).toFixed(2)}s</strong>
                ${sourcesDisplay}
            </span>
            <span class="confidence-badge ${confidenceClass}">
                ${confidenceText} Confidence
            </span>
        `;
        
        return metaDiv;
    }
    
    createSourcesDisplay(sources) {
        if (!sources || sources.length === 0) {
            return '';
        }
        
        // Create a tooltip showing all source names
        const sourceNames = Array.isArray(sources) ? sources : [sources];
        const sourceList = sourceNames.map(source => `• ${source}`).join('\n');
        
        return ` • <span class="sources-info" title="${sourceList}">Sources: <strong>${sourceNames.length}</strong></span>`;
    }

    createPdfLinks(pdfLinks) {
        const pdfDiv = document.createElement('div');
        pdfDiv.className = 'pdf-links';
        
        const linksHtml = pdfLinks.map(pdf => `
            <a href="${pdf.url}" target="_blank" class="pdf-link" title="Download ${pdf.display_name}">
                📄 ${pdf.display_name}
            </a>
        `).join('');
        
        pdfDiv.innerHTML = `
            <strong>Available Downloads:</strong><br>
            ${linksHtml}
        `;
        
        return pdfDiv;
    }

    addRecentQuery(query) {
        // Avoid duplicates
        this.recentQueries = this.recentQueries.filter(q => q !== query);
        
        // Add to beginning
        this.recentQueries.unshift(query);
        
        // Keep only last 5
        this.recentQueries = this.recentQueries.slice(0, 5);
        
        // Save to localStorage
        this.saveRecentQueries();
        this.updateRecentQueriesUI();
    }

    updateRecentQueriesUI() {
        if (this.recentQueries.length === 0) {
            this.recentQueriesElement.innerHTML = '<p class="no-recent">No recent queries</p>';
            return;
        }
        
        const recentHtml = this.recentQueries.map(query => `
            <div class="recent-item" data-query="${this.escapeHtml(query)}" title="${this.escapeHtml(query)}">
                ${this.truncateText(query, 50)}
            </div>
        `).join('');
        
        this.recentQueriesElement.innerHTML = recentHtml;
    }

    loadRecentQueries() {
        try {
            const saved = localStorage.getItem('edbot_recent_queries');
            return saved ? JSON.parse(saved) : [];
        } catch (error) {
            console.error('Error loading recent queries:', error);
            return [];
        }
    }

    saveRecentQueries() {
        try {
            localStorage.setItem('edbot_recent_queries', JSON.stringify(this.recentQueries));
        } catch (error) {
            console.error('Error saving recent queries:', error);
        }
    }

    scrollToBottom() {
        this.messagesElement.scrollTop = this.messagesElement.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateText(text, maxLength) {
        if (text.length <= maxLength) return this.escapeHtml(text);
        return this.escapeHtml(text.substring(0, maxLength)) + '...';
    }
}

// Initialize the chat application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.edbotChat = new EDBotChat();
});

// Handle page visibility changes to refresh status
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && window.edbotChat) {
        window.edbotChat.checkApiHealth();
    }
});

// Global error handler
window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
});

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', (e) => {
    console.error('Unhandled promise rejection:', e.reason);
});