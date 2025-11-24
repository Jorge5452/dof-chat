/**
 * Simple Markdown renderer for DOF Chat using Marked.js + DOMPurify
 */
class SafeMarkdownRenderer {
    
    static init() {
        if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
            console.warn('Marked.js or DOMPurify not loaded. Using fallback.');
            return false;
        }

        // Configure marked with simple safe renderer
        const renderer = new marked.Renderer();
        
        renderer.heading = (text, level) => {
            const className = level <= 2 ? 'heading-large' : 
                            level <= 4 ? 'heading-medium' : 'heading-small';
            return `<span class="${className}">${text}</span>\n`;
        };
        
        renderer.listitem = (text) => `<span class="list-item">• ${text}</span>\n`;
        renderer.blockquote = (quote) => `<span class="blockquote">${quote.trim()}</span>\n`;
        renderer.codespan = (code) => `<code class="inline-code">${code}</code>`;
        renderer.link = (href, title, text) => {
            const titleAttr = title ? ` title="${title}"` : '';
            return `<a href="${href}"${titleAttr} target="_blank" rel="noopener" class="chat-link">${text}</a>`;
        };
        
        marked.setOptions({
            renderer: renderer,
            gfm: true,
            breaks: true,
            sanitize: false
        });
        
        return true;
    }
    
    static render(markdown, options = {}) {
        if (!markdown || typeof markdown !== 'string') return '';

        const maxLength = options.maxLength || 5000;
        const allowLinks = options.allowLinks !== false;
        
        // Truncate if too long
        let text = markdown.length > maxLength 
            ? markdown.substring(0, maxLength) + '...' 
            : markdown;

        try {
            // Check libraries and initialize
            if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
                return this.fallbackRender(text);
            }

            if (!this._initialized) {
                this._initialized = this.init();
                if (!this._initialized) return this.fallbackRender(text);
            }

            // Convert and sanitize
            let html = marked.parse(text);
            const cleanHtml = DOMPurify.sanitize(html, {
                ALLOWED_TAGS: ['strong', 'em', 'code', 'a', 'br', 'span'],
                ALLOWED_ATTR: ['href', 'title', 'target', 'rel', 'class'],
                FORBID_TAGS: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote']
            });

            // Remove links if not allowed
            return allowLinks ? cleanHtml : cleanHtml.replace(/<a[^>]*>([^<]*)<\/a>/g, '$1');

        } catch (error) {
            console.warn('Markdown rendering failed:', error);
            return this.fallbackRender(text);
        }
    }

    static fallbackRender(text) {
        const escaped = this.escapeHtml(text);
        return escaped
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code class="inline-code">$1</code>')
            .replace(/\n/g, '<br>');
    }

    static renderChatMessage(markdown) {
        return this.render(markdown, { allowLinks: true, maxLength: 10000 });
    }

    static renderDocumentContext(markdown) {
        return this.render(markdown, { allowLinks: false, maxLength: 2000 });
    }

    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    static processDocumentContextHtml(contextHtml) {
        if (!contextHtml) return contextHtml;
        
        try {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = contextHtml;
            
            // Simple processing - look for text that might be markdown
            const textElements = tempDiv.querySelectorAll('*');
            textElements.forEach(element => {
                if (element.children.length === 0 && element.textContent) {
                    const text = element.textContent;
                    if (this.containsMarkdown(text)) {
                        element.innerHTML = this.renderDocumentContext(text);
                    }
                }
            });
            
            return tempDiv.innerHTML;
        } catch (error) {
            console.warn('Error processing context HTML:', error);
            return contextHtml;
        }
    }

    static containsMarkdown(text) {
        return /(\*\*.*?\*\*|\*.*?\*|`.*?`|^#{1,6}\s|^\s*[-*+]\s)/m.test(text);
    }
}

// Global access
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SafeMarkdownRenderer;
} else {
    window.SafeMarkdownRenderer = SafeMarkdownRenderer;
}