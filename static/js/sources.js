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

        // Handle both array and string formats
        const sourceList = Array.isArray(sources) ? sources : [sources];
        
        const sourcesHtml = sourceList.map((source, index) => {
            const sourceId = `source-${Date.now()}-${index}`;
            const isExpanded = this.expandedSources.has(sourceId);
            
            return `
                <div class="source-item">
                    <div class="source-header" onclick="window.sourceRenderer.toggleSource('${sourceId}')">
                        <span>
                            <strong>📄 ${this.getDisplayName(source, index + 1)}</strong>
                        </span>
                        <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
                    </div>
                    <div id="${sourceId}" class="source-content ${isExpanded ? 'expanded' : ''}">
                        ${this.renderSourceContent(source, response, index)}
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="sources-section">
                <div class="sources-title">
                    📚 <strong>Sources</strong> (${sourceList.length})
                </div>
                ${sourcesHtml}
            </div>
        `;
    }

    /**
     * Get appropriate display name for a source
     */
    getDisplayName(source, fallbackIndex) {
        if (typeof source === 'string') {
            return source;
        }
        
        if (source && typeof source === 'object') {
            return source.display_name || 
                   source.filename || 
                   source.document_name || 
                   source.name || 
                   `Source ${fallbackIndex}`;
        }
        
        return `Source ${fallbackIndex}`;
    }

    /**
     * Render individual source content with excerpts and confidence
     */
    renderSourceContent(source, response, index) {
        let content = '';
        
        // Handle string sources (simple case)
        if (typeof source === 'string') {
            content = `
                <div class="source-meta">
                    <strong>Document:</strong> ${this.escapeHtml(source)}
                </div>
            `;
            return content;
        }

        // Handle object sources (detailed case)
        if (source && typeof source === 'object') {
            content += '<div class="source-meta">';
            
            if (source.filename) {
                content += `<strong>Document:</strong> ${this.escapeHtml(source.filename)}`;
            }
            
            if (source.content_type) {
                content += `<br><strong>Type:</strong> ${this.escapeHtml(source.content_type)}`;
            }
            
            if (source.page_number) {
                content += `<br><strong>Page:</strong> ${source.page_number}`;
            }
            
            if (source.section) {
                content += `<br><strong>Section:</strong> ${this.escapeHtml(source.section)}`;
            }
            
            content += '</div>';

            // Add excerpt if available
            if (source.text_snippet || source.excerpt || source.content) {
                const excerpt = source.text_snippet || source.excerpt || source.content;
                const truncatedExcerpt = this.truncateText(excerpt, 300);
                
                content += `
                    <div class="source-excerpt">
                        "${this.escapeHtml(truncatedExcerpt)}"
                    </div>
                `;
            }

            // Add confidence bar if available
            if (source.confidence !== undefined && source.confidence !== null) {
                const confidencePercent = Math.round(source.confidence * 100);
                content += `
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                    </div>
                    <small>Relevance: ${confidencePercent}%</small>
                `;
            } else if (source.relevance !== undefined) {
                const relevancePercent = Math.round(source.relevance * 100);
                content += `
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${relevancePercent}%"></div>
                    </div>
                    <small>Relevance: ${relevancePercent}%</small>
                `;
            }

            // Add download link if available
            if (source.pdf_path || source.file_path) {
                const pdfPath = source.pdf_path || source.file_path;
                const displayName = this.getDisplayName(source, index + 1);
                
                content += `
                    <div style="margin-top: 0.5rem;">
                        <button class="pdf-link" onclick="window.sourceRenderer.downloadPdf('${this.escapeHtml(pdfPath)}', '${this.escapeHtml(displayName)}')">
                            📄 Download PDF
                        </button>
                    </div>
                `;
            }
        }

        return content;
    }

    /**
     * Toggle source expansion
     */
    toggleSource(sourceId) {
        const sourceContent = document.getElementById(sourceId);
        if (!sourceContent) return;

        const expandIcon = sourceContent.parentElement.querySelector('.expand-icon');
        
        if (this.expandedSources.has(sourceId)) {
            this.expandedSources.delete(sourceId);
            sourceContent.classList.remove('expanded');
            if (expandIcon) expandIcon.textContent = '▶';
        } else {
            this.expandedSources.add(sourceId);
            sourceContent.classList.add('expanded');
            if (expandIcon) expandIcon.textContent = '▼';
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
            const isExpanded = this.expandedSources.has(highlightId);
            
            return `
                <div class="source-item highlighted">
                    <div class="source-header" onclick="window.sourceRenderer.toggleSource('${highlightId}')">
                        <span>
                            <strong>🔦 ${this.escapeHtml(highlight.document_name || `Highlight ${index + 1}`)}</strong> 
                            ${highlight.page_number ? `(Page ${highlight.page_number})` : ''}
                        </span>
                        <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
                    </div>
                    <div id="${highlightId}" class="source-content ${isExpanded ? 'expanded' : ''}">
                        <div class="source-excerpt">
                            "${this.escapeHtml(highlight.text_snippet || highlight.text || '')}"
                        </div>
                        ${highlight.confidence ? `
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${Math.round(highlight.confidence * 100)}%"></div>
                            </div>
                            <small>Confidence: ${Math.round(highlight.confidence * 100)}%</small>
                        ` : ''}
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

    /**
     * Render PDF links section
     */
    renderPdfLinks(pdfLinks) {
        if (!pdfLinks || pdfLinks.length === 0) {
            return '';
        }

        const linksHtml = pdfLinks.map((pdf, index) => {
            const displayName = pdf.display_name || pdf.name || `Document ${index + 1}`;
            const pdfPath = pdf.url || pdf.path || pdf.pdf_path;
            
            return `
                <button class="pdf-link" onclick="window.sourceRenderer.downloadPdf('${this.escapeHtml(pdfPath)}', '${this.escapeHtml(displayName)}')">
                    📄 ${this.escapeHtml(displayName)}
                </button>
            `;
        }).join('');

        return `
            <div class="pdf-links">
                <strong>Available Downloads:</strong><br>
                ${linksHtml}
            </div>
        `;
    }

    /**
     * Download PDF file
     */
    async downloadPdf(pdfPath, displayName) {
        try {
            await window.apiClient.downloadPdf(pdfPath, displayName);
        } catch (error) {
            console.error('PDF download failed:', error);
            alert('Failed to download PDF. Please try again.');
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Truncate text to specified length
     */
    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) {
            return text || '';
        }
        
        return text.substring(0, maxLength - 3) + '...';
    }

    /**
     * Clear all expanded sources (for new conversations)
     */
    clearExpanded() {
        this.expandedSources.clear();
    }

    /**
     * Auto-expand first source (for better UX)
     */
    autoExpandFirst() {
        const firstSource = document.querySelector('.source-item .source-header');
        if (firstSource) {
            // Find the source ID from the onclick attribute
            const onclick = firstSource.getAttribute('onclick');
            const match = onclick.match(/toggleSource\('([^']+)'\)/);
            if (match) {
                const sourceId = match[1];
                // Only expand if not already expanded
                if (!this.expandedSources.has(sourceId)) {
                    this.toggleSource(sourceId);
                }
            }
        }
    }

    /**
     * Handle source interaction analytics (optional)
     */
    trackSourceInteraction(sourceId, action) {
        // This could be used for analytics in the future
        console.debug('Source interaction:', { sourceId, action, timestamp: Date.now() });
    }
}

// Global instance
window.sourceRenderer = new SourceRenderer();