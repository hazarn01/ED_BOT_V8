/**
 * Main ED Bot v8 Chatbot Interface
 * Mount Sinai Emergency Medicine AI Assistant
 */
class EDBotChatbot {
    constructor() {
        console.log('ED Bot v8 Chatbot initializing...');
        
        this.initializeElements();
        this.setupEventListeners();
        this.setupAutoResize();
        
        // Check API health on startup
        this.checkApiHealth();
        
        console.log('ED Bot v8 Chatbot ready!');
    }

    initializeElements() {
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.chatForm = document.getElementById('chatForm');
        this.loadingOverlay = document.getElementById('loadingOverlay');
    }

    setupEventListeners() {
        // Form submission
        if (this.chatForm) {
            this.chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }

        // Send button click
        if (this.sendButton) {
            this.sendButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }

        // Enter key to send (Shift+Enter for new line)
        if (this.messageInput) {
            this.messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            // Input validation and button state
            this.messageInput.addEventListener('input', () => {
                this.updateSendButton();
            });
        }

        // Quick query buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-query-btn')) {
                const query = e.target.dataset.query;
                if (query) {
                    this.messageInput.value = query;
                    this.updateSendButton();
                    this.sendMessage();
                }
            }
        });

        // Handle page visibility for health checks
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.checkApiHealth();
            }
        });
    }

    setupAutoResize() {
        if (this.messageInput) {
            this.messageInput.addEventListener('input', () => {
                this.autoResizeTextarea();
            });
        }
    }

    autoResizeTextarea() {
        const textarea = this.messageInput;
        if (!textarea) return;

        // Reset height to auto to get the correct scrollHeight
        textarea.style.height = 'auto';
        
        // Set height based on scrollHeight, but cap at max-height
        const maxHeight = 120; // pixels
        const newHeight = Math.min(textarea.scrollHeight, maxHeight);
        
        textarea.style.height = newHeight + 'px';
    }

    updateSendButton() {
        if (!this.sendButton || !this.messageInput) return;

        const query = this.messageInput.value.trim();
        const validation = window.apiClient.validateQuery(query);
        
        this.sendButton.disabled = !validation.valid;
        
        // Visual feedback for validation
        if (query.length > 0 && !validation.valid) {
            this.messageInput.style.borderColor = '#dc3545';
            this.messageInput.title = validation.error;
        } else {
            this.messageInput.style.borderColor = '';
            this.messageInput.title = '';
        }
    }

    async sendMessage() {
        const query = this.messageInput.value.trim();
        if (!query) return;

        // Validate query
        const validation = window.apiClient.validateQuery(query);
        if (!validation.valid) {
            this.showError(validation.error);
            return;
        }

        console.log('Sending query:', query);

        // Clear input and reset
        this.messageInput.value = '';
        this.autoResizeTextarea();
        this.updateSendButton();

        // Add user message
        this.addUserMessage(query);

        // Show loading
        this.showLoading(true);

        try {
            const startTime = Date.now();
            const response = await window.apiClient.query(validation.query);
            const responseTime = (Date.now() - startTime) / 1000;

            // Hide loading
            this.showLoading(false);

            // Add bot response
            this.addBotMessage(response, responseTime);

            // Auto-expand first source for better UX
            setTimeout(() => {
                window.sourceRenderer.autoExpandFirst();
            }, 100);

        } catch (error) {
            console.error('Query failed:', error);
            this.showLoading(false);
            
            const errorMessage = window.apiClient.formatErrorMessage(error);
            this.addErrorMessage(errorMessage);
        }
    }

    addUserMessage(message) {
        const messageElement = this.createMessageElement('user-message', message);
        this.appendMessage(messageElement);
    }

    addBotMessage(response, responseTime) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Format the main response
        const formattedResponse = this.formatResponse(response.response);
        contentDiv.innerHTML = formattedResponse;
        
        messageDiv.appendChild(contentDiv);

        // Add sources if available
        if (response.sources && response.sources.length > 0) {
            const sourcesHtml = window.sourceRenderer.renderSources(response.sources, response.response);
            if (sourcesHtml) {
                contentDiv.innerHTML += sourcesHtml;
            }
        }

        // Add highlighted sources if available
        if (response.highlighted_sources && response.highlighted_sources.length > 0) {
            const highlightedHtml = window.sourceRenderer.renderHighlightedSources(response.highlighted_sources);
            if (highlightedHtml) {
                contentDiv.innerHTML += highlightedHtml;
            }
        }

        // Add PDF links if available
        if (response.pdf_links && response.pdf_links.length > 0) {
            const pdfLinksHtml = window.sourceRenderer.renderPdfLinks(response.pdf_links);
            if (pdfLinksHtml) {
                contentDiv.innerHTML += pdfLinksHtml;
            }
        }

        // Add metadata
        if (response.query_type || response.confidence !== undefined || response.processing_time) {
            const metaDiv = this.createMetadata(response, responseTime);
            messageDiv.appendChild(metaDiv);
        }

        // Add warnings if any
        if (response.warnings && response.warnings.length > 0) {
            const warningsDiv = this.createWarnings(response.warnings);
            messageDiv.appendChild(warningsDiv);
        }

        this.appendMessage(messageDiv);
    }

    addErrorMessage(errorText) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content error';
        contentDiv.innerHTML = `
            <strong>⚠️ Error</strong><br>
            ${this.escapeHtml(errorText)}
        `;
        
        messageDiv.appendChild(contentDiv);
        this.appendMessage(messageDiv);
    }

    createMessageElement(className, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${className}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;
        
        messageDiv.appendChild(contentDiv);
        return messageDiv;
    }

    createMetadata(response, responseTime) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';
        
        let metaContent = '<span>';
        
        if (response.query_type) {
            metaContent += `Type: <strong>${response.query_type.toUpperCase()}</strong>`;
        }
        
        const processingTime = response.processing_time || responseTime;
        if (processingTime) {
            metaContent += ` • Time: <strong>${processingTime.toFixed(2)}s</strong>`;
        }
        
        if (response.sources && response.sources.length > 0) {
            metaContent += ` • Sources: <strong>${response.sources.length}</strong>`;
        }
        
        metaContent += '</span>';
        
        // Add confidence badge
        if (response.confidence !== undefined) {
            const confidence = response.confidence;
            let confidenceClass = 'medium';
            let confidenceText = 'Medium';
            
            if (confidence >= 0.8) {
                confidenceClass = 'high';
                confidenceText = 'High';
            } else if (confidence < 0.5) {
                confidenceClass = 'low';
                confidenceText = 'Low';
            }
            
            metaContent += `
                <span class="confidence-badge ${confidenceClass}">
                    ${confidenceText} Confidence
                </span>
            `;
        }
        
        metaDiv.innerHTML = metaContent;
        return metaDiv;
    }

    createWarnings(warnings) {
        const warningsDiv = document.createElement('div');
        warningsDiv.className = 'warnings';
        warningsDiv.style.marginTop = '1rem';
        warningsDiv.style.padding = '0.75rem';
        warningsDiv.style.backgroundColor = '#fff3cd';
        warningsDiv.style.border = '1px solid #ffeaa7';
        warningsDiv.style.borderRadius = '0.5rem';
        warningsDiv.style.color = '#856404';
        
        const warningsList = warnings.map(w => `<li>${this.escapeHtml(w)}</li>`).join('');
        warningsDiv.innerHTML = `
            <strong>⚠️ Warnings:</strong>
            <ul style="margin: 0.5rem 0 0 1rem;">${warningsList}</ul>
        `;
        
        return warningsDiv;
    }

    appendMessage(messageElement) {
        if (this.chatMessages) {
            this.chatMessages.appendChild(messageElement);
            this.scrollToBottom();
            
            // Add entrance animation
            messageElement.style.opacity = '0';
            messageElement.style.transform = 'translateY(10px)';
            
            requestAnimationFrame(() => {
                messageElement.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                messageElement.style.opacity = '1';
                messageElement.style.transform = 'translateY(0)';
            });
        }
    }

    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    showLoading(show) {
        if (this.loadingOverlay) {
            if (show) {
                this.loadingOverlay.classList.add('show');
            } else {
                this.loadingOverlay.classList.remove('show');
            }
        }
    }

    async checkApiHealth() {
        try {
            const health = await window.apiClient.health();
            console.log('API Health:', health);
            
            // Could update UI with health status if needed
            // For now, just log it
            
        } catch (error) {
            console.warn('Health check failed:', error);
        }
    }

    formatResponse(responseText) {
        if (!responseText) return '';
        
        // Basic markdown-like formatting
        let formatted = responseText
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold
            .replace(/\*(.*?)\*/g, '<em>$1</em>') // Italic
            .replace(/`(.*?)`/g, '<code style="background: #f8f9fa; padding: 2px 4px; border-radius: 3px; font-family: monospace;">$1</code>') // Inline code
            .replace(/\n/g, '<br>'); // Line breaks

        // Handle numbered lists
        formatted = formatted.replace(/^\d+\.\s(.+)$/gm, '<div style="margin: 8px 0;">$&</div>');
        
        // Handle bullet points
        formatted = formatted.replace(/^[-•]\s(.+)$/gm, '<div style="margin: 4px 0; padding-left: 16px;">• $1</div>');
        
        // Handle warnings
        formatted = formatted.replace(/⚠️\s*\*\*(.*?)\*\*/g, '<div class="warning" style="margin: 8px 0; padding: 8px; background: #fff3cd; border-radius: 4px;"><strong>⚠️ $1</strong></div>');
        
        return formatted;
    }

    showError(message) {
        // Could show a toast or inline error
        console.error('Validation error:', message);
        alert(message); // Simple for now
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the chatbot when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing ED Bot v8...');
    window.edbotChatbot = new EDBotChatbot();
});

// Global error handlers
window.addEventListener('error', (e) => {
    console.error('Global JavaScript error:', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
    console.error('Unhandled promise rejection:', e.reason);
});