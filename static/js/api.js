/**
 * API communication with ED Bot v8 backend
 */
class APIClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.sessionId = this.generateSessionId();
        this.requestTimeout = 15000; // 15 seconds
        this.healthTimeout = 5000;   // 5 seconds
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Send a query to the ED Bot API
     */
    async query(message, context = null) {
        const payload = { 
            query: message,
            session_id: this.sessionId
        };
        
        if (context) {
            payload.context = context;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.requestTimeout);

        try {
            const response = await fetch('/api/v1/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(`API Error: ${response.status} ${response.statusText} - ${errorData.detail || 'Unknown error'}`);
            }

            const data = await response.json();
            
            // Validate response structure
            if (!data.response) {
                throw new Error('Invalid response format from API');
            }

            return data;
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timeout - the query took too long to process');
            }
            
            throw error;
        }
    }

    /**
     * Check API health status
     */
    async health() {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.healthTimeout);

        try {
            const response = await fetch('/health', {
                method: 'GET',
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                return {
                    status: 'unhealthy',
                    message: `HTTP ${response.status}`,
                    details: null
                };
            }

            const data = await response.json();
            return {
                status: data.status === 'healthy' ? 'healthy' : 'unhealthy',
                message: data.message || 'API responsive',
                details: data
            };
        } catch (error) {
            clearTimeout(timeoutId);
            
            return {
                status: 'offline',
                message: error.name === 'AbortError' ? 'Timeout' : 'Offline',
                details: error
            };
        }
    }

    /**
     * Download a PDF file
     */
    async downloadPdf(pdfPath, displayName = null) {
        try {
            const response = await fetch(`/api/v1/pdf/${encodeURIComponent(pdfPath)}`, {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error(`PDF download failed: ${response.status} ${response.statusText}`);
            }

            // Create blob and download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = displayName || pdfPath.split('/').pop() || 'document.pdf';
            
            document.body.appendChild(a);
            a.click();
            
            // Cleanup
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            return true;
        } catch (error) {
            console.error('PDF download error:', error);
            throw error;
        }
    }

    /**
     * Get system metrics (if available)
     */
    async getMetrics() {
        try {
            const response = await fetch('/metrics', {
                method: 'GET',
                timeout: this.healthTimeout
            });

            if (!response.ok) {
                return null;
            }

            return await response.text(); // Metrics are usually in text format
        } catch (error) {
            console.debug('Metrics not available:', error);
            return null;
        }
    }

    /**
     * Validate query before sending
     */
    validateQuery(query) {
        if (!query || typeof query !== 'string') {
            return { valid: false, error: 'Query must be a non-empty string' };
        }

        const trimmed = query.trim();
        if (trimmed.length === 0) {
            return { valid: false, error: 'Query cannot be empty' };
        }

        if (trimmed.length > 1000) {
            return { valid: false, error: 'Query too long (max 1000 characters)' };
        }

        // Basic PHI detection (very simple - real implementation would be more sophisticated)
        const phiPatterns = [
            /\b\d{3}-\d{2}-\d{4}\b/, // SSN pattern
            /\b\d{3}-\d{3}-\d{4}\b/, // Phone pattern
            /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/ // Email pattern
        ];

        for (const pattern of phiPatterns) {
            if (pattern.test(trimmed)) {
                return { 
                    valid: false, 
                    error: 'Query may contain personal information. Please remove specific identifiers.' 
                };
            }
        }

        return { valid: true, query: trimmed };
    }

    /**
     * Format error message for user display
     */
    formatErrorMessage(error) {
        if (error.message.includes('timeout')) {
            return "Your query is taking longer than expected. Please try a simpler question or try again later.";
        }
        
        if (error.message.includes('404')) {
            return "The requested service is not available. Please contact support.";
        }
        
        if (error.message.includes('500')) {
            return "The system encountered an error processing your request. Please try again.";
        }
        
        if (error.message.includes('offline') || error.message.includes('network')) {
            return "Unable to connect to the medical database. Please check your connection and try again.";
        }

        // Generic fallback
        return "I'm having trouble processing your request right now. Please try again in a moment.";
    }
}

// Global instance
window.apiClient = new APIClient();