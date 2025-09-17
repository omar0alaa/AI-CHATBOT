/**
 * YouLearnt AI Chat Widget
 * Standalone chat widget that can be embedded in any website
 */

class YouLearntChatWidget {
    constructor(config = {}) {
        this.config = {
            apiUrl: config.apiUrl || 'http://161.97.147.7:5000',
            position: config.position || 'bottom-right',
            primaryColor: config.primaryColor || '#2B4C8C',
            userName: config.userName || 'You',
            autoOpen: config.autoOpen || false,
            enableNotifications: config.enableNotifications || true,
            lang: config.lang || 'en',
            ...config
        };

        // Language texts
        this.texts = {
            en: {
                welcomeMessage: 'Hello there! How can I assist you today?',
                timeAgo: 'just now',
                errorMessage: 'Sorry, I\'m having trouble connecting. Please try again.',
                connectionError: 'Connection error. Please check your internet.',
                sendingMessage: 'Sending...',
                placeholder: 'Write your message',
                sendTitle: 'Send message',
                online: 'Online',
                poweredBy: 'Powered by AI'
            },
            ar: {
                welcomeMessage: 'أهلاً بك! كيف يمكنني مساعدتك اليوم؟',
                timeAgo: 'الآن',
                errorMessage: 'عذراً، أواجه مشكلة في الاتصال. يرجى المحاولة مرة أخرى.',
                connectionError: 'خطأ في الاتصال. يرجى التحقق من الإنترنت.',
                sendingMessage: 'جاري الإرسال...',
                placeholder: 'اكتب رسالتك',
                sendTitle: 'إرسال الرسالة',
                online: 'متصل',
                poweredBy: 'مشغل بواسطة الذكاء الاصطناعي'
            }
        };

        this.isOpen = false;
        this.sessionId = this.generateSessionId();
        this.chatHistory = [];
        this.isTyping = false;

        this.init();
    }

    getText(key) {
        const lang = this.config.lang || 'en';
        return this.texts[lang]?.[key] || this.texts.en[key] || key;
    }

    init() {
        this.createWidget();
        this.attachEventListeners();
        
        if (this.config.autoOpen) {
            setTimeout(() => this.openChat(), 1000);
        }

        // Show notification after 5 seconds if chat hasn't been opened
        if (this.config.enableNotifications) {
            setTimeout(() => {
                if (!this.isOpen) {
                    this.showNotification();
                }
            }, 5000);
        }
    }

    createWidget() {
        // Widget is already created in HTML, just get references
        this.widget = document.getElementById('youlearnt-chat-widget');
        this.toggleBtn = document.getElementById('chat-toggle-btn');
        this.chatWindow = document.getElementById('chat-window');
        this.chatMessages = document.getElementById('chat-messages');
        this.chatInput = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('send-btn');
        this.closeBtn = document.getElementById('close-chat');
        this.typingIndicator = null; // Will be created dynamically
        this.notificationBadge = document.getElementById('notification-badge');
        this.langEnBtn = document.getElementById('lang-en');
        this.langArBtn = document.getElementById('lang-ar');

        if (!this.widget) {
            console.error('YouLearnt Chat Widget: Widget container not found');
            return;
        }

        // Get language from widget data attribute or config
        const widgetLang = this.widget.getAttribute('data-lang');
        if (widgetLang) {
            this.config.lang = widgetLang;
        }

        // Initialize UI text based on language
        this.initializeLanguage();
    }

    initializeLanguage() {
        const lang = this.config.lang || 'en';
        
        // Update placeholder
        if (this.chatInput) {
            this.chatInput.placeholder = this.getText('placeholder');
        }
        
        // Update send button title
        if (this.sendBtn) {
            this.sendBtn.title = this.getText('sendTitle');
        }
        
        // Update status text
        const statusSpan = document.getElementById('online-status');
        if (statusSpan) {
            statusSpan.textContent = this.getText('online');
        }
        
        // Update language buttons
        if (this.langEnBtn && this.langArBtn) {
            this.langEnBtn.classList.toggle('active', lang === 'en');
            this.langArBtn.classList.toggle('active', lang === 'ar');
        }
        
        // Update widget direction
        this.widget.setAttribute('data-lang', lang);
        
        // Update welcome message if it exists
        const welcomeText = document.getElementById('welcome-text');
        const welcomeTime = document.getElementById('welcome-time');
        if (welcomeText) {
            welcomeText.textContent = this.getText('welcomeMessage');
        }
        if (welcomeTime) {
            welcomeTime.textContent = this.getText('timeAgo');
        }
    }

    attachEventListeners() {
        // Toggle chat window
        this.toggleBtn?.addEventListener('click', () => this.toggleChat());
        this.closeBtn?.addEventListener('click', () => this.closeChat());

        // Language toggle
        this.langEnBtn?.addEventListener('click', () => this.switchLanguage('en'));
        this.langArBtn?.addEventListener('click', () => this.switchLanguage('ar'));

        // Send message
        this.sendBtn?.addEventListener('click', () => this.sendMessage());
        this.chatInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Input validation
        this.chatInput?.addEventListener('input', () => {
            const hasText = this.chatInput.value.trim().length > 0;
            this.sendBtn.disabled = !hasText;
            this.sendBtn.style.opacity = hasText ? '1' : '0.5';
        });

        // Close widget when clicking outside
        document.addEventListener('click', (e) => {
            if (this.isOpen && !this.widget.contains(e.target)) {
                this.closeChat();
            }
        });

        // Handle window resize
        window.addEventListener('resize', () => this.handleResize());
    }

    toggleChat() {
        if (this.isOpen) {
            this.closeChat();
        } else {
            this.openChat();
        }
    }

    openChat() {
        this.isOpen = true;
        this.chatWindow.classList.add('open');
        this.toggleBtn.classList.add('active');
        this.hideNotification();
        
        // Focus input
        setTimeout(() => {
            this.chatInput?.focus();
        }, 300);

        // Send initial greeting if no messages
        if (this.chatHistory.length === 0) {
            setTimeout(() => {
                this.addMessage(this.getText('welcomeMessage'), 'bot');
            }, 500);
            this.chatHistory.length +=1;
        }
    }

    closeChat() {
        this.isOpen = false;
        this.chatWindow.classList.remove('open');
        this.toggleBtn.classList.remove('active');
        this.hideTypingIndicator();
    }

    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message) return;

        // Clear input and disable send button
        this.chatInput.value = '';
        this.sendBtn.disabled = true;
        this.sendBtn.style.opacity = '0.5';

        // Add user message to chat
        this.addMessage(message, 'user');
        this.chatHistory.push({ role: 'user', content: message });

        // Show typing indicator
        this.showTypingIndicator();

        try {
            // Send message to API
            const response = await this.callAPI(message);
            
            // Hide typing indicator
            this.hideTypingIndicator();

            console.log('Full API response:', response);

            // Add bot response
            if (response && response.message) {
                console.log('Adding bot message:', response.message);
                this.addMessage(response.message, 'bot');
                this.chatHistory.push({ role: 'assistant', content: response.message });
            } else if (response && response.error) {
                console.error('API returned error:', response.error);
                this.addErrorMessage(response.error);
            } else {
                console.error('Invalid response format:', response);
                throw new Error('Invalid response format - no message property');
            }

        } catch (error) {
            console.error('Chat Widget Error:', error);
            this.hideTypingIndicator();
            this.addErrorMessage(this.getText('errorMessage'));
        }
    }

    async callAPI(message) {
        try {
            const requestData = {
                message: message,
                lang: this.config.lang || 'en'
            };

            console.log('Sending API request:', requestData);
            console.log('API URL:', `${this.config.apiUrl}/api/chat`);

            const response = await fetch(`${this.config.apiUrl}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include', // Include cookies for session handling
                body: JSON.stringify(requestData)
            });

            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('API Error Response:', response.status, errorText);
                throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
            }

            const result = await response.json();
            console.log('API Response JSON:', result);
            return result;

        } catch (error) {
            console.error('API Call Error:', error);
            throw error;
        }
    }

    addMessage(message, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        const avatar = document.createElement('div');
        avatar.className = `${sender}-avatar`;

        if (sender === 'bot') {
            avatar.innerHTML = `
                <div class="logo-squares">
                    <div class="square red-circle"></div>
                    <div class="square blue-circle"></div>
                    <div class="square red-square"></div>
                    <div class="square blue-square"></div>
                </div>
            `;
        } else {
            avatar.textContent = this.config.userName.charAt(0).toUpperCase();
        }

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerHTML = this.formatMessage(message);

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = this.getTimeStamp();

        // Add powered by text for bot messages
        if (sender === 'bot') {
            const poweredDiv = document.createElement('div');
            poweredDiv.className = 'powered-by';
            poweredDiv.textContent = this.getText('poweredBy');
            contentDiv.appendChild(textDiv);
            contentDiv.appendChild(poweredDiv);
            contentDiv.appendChild(timeDiv);
        } else {
            contentDiv.appendChild(textDiv);
            contentDiv.appendChild(timeDiv);
        }

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);

        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addErrorMessage(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        this.chatMessages.appendChild(errorDiv);
        this.scrollToBottom();

        // Remove error message after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }

    formatMessage(message) {
        // First, escape HTML to prevent XSS
        const escapeHtml = (text) => {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        };

        // Don't escape if already contains HTML tags
        if (/<[^>]*>/.test(message)) {
            return message;
        }

        // Escape the message first
        let formatted = escapeHtml(message);

        // Convert markdown-style formatting to HTML
        // Headers
        formatted = formatted.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        formatted = formatted.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        formatted = formatted.replace(/^# (.*$)/gm, '<h1>$1</h1>');

        // Bold text with **
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // Italic text with *
        formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // Bullet points - handle nested structure
        formatted = formatted.replace(/^\* (.*$)/gm, '<li>$1</li>');
        
        // Wrap consecutive list items in <ul> tags
        formatted = formatted.replace(/(<li>.*<\/li>\s*)+/g, (match) => {
            return '<ul>' + match + '</ul>';
        });

        // Line breaks - convert double line breaks to paragraphs
        formatted = formatted.replace(/\n\s*\n/g, '</p><p>');
        
        // Wrap content in paragraphs if it doesn't already have block elements
        if (!/<(h[1-6]|ul|ol|li|p|div|blockquote)/.test(formatted)) {
            formatted = '<p>' + formatted + '</p>';
        } else if (!formatted.startsWith('<')) {
            formatted = '<p>' + formatted;
            if (!formatted.endsWith('</p>')) {
                formatted += '</p>';
            }
        }

        // Convert single line breaks to <br> within paragraphs
        formatted = formatted.replace(/(?<!<\/[^>]+>)\n(?!<[^>]+>)/g, '<br>');

        // Convert URLs to links (after other formatting)
        const urlRegex = /(https?:\/\/[^\s<]+)/g;
        formatted = formatted.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
        
        return formatted;
    }

    showTypingIndicator() {
        this.isTyping = true;
        
        // Create typing indicator if it doesn't exist
        if (!this.typingIndicator) {
            this.typingIndicator = document.createElement('div');
            this.typingIndicator.className = 'typing-indicator';
            this.typingIndicator.innerHTML = `
                <div class="bot-avatar">
                    <div class="logo-squares">
                        <div class="square red-circle"></div>
                        <div class="square blue-circle"></div>
                        <div class="square red-square"></div>
                        <div class="square blue-square"></div>
                    </div>
                </div>
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            `;
        }
        
        // Add to messages container
        this.chatMessages.appendChild(this.typingIndicator);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.isTyping = false;
        
        // Remove typing indicator if it exists
        if (this.typingIndicator && this.typingIndicator.parentNode) {
            this.typingIndicator.parentNode.removeChild(this.typingIndicator);
        }
    }

    showNotification() {
        this.notificationBadge.style.display = 'flex';
    }

    hideNotification() {
        this.notificationBadge.style.display = 'none';
    }

    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }

    getTimeStamp() {
        const now = new Date();
        const minutes = now.getMinutes();
        const hours = now.getHours();
        
        if (this.config.lang === 'ar') {
            // Arabic time format (24-hour)
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        } else {
            // English time format (12-hour with AM/PM)
            const ampm = hours >= 12 ? 'PM' : 'AM';
            const displayHours = hours % 12 || 12;
            return `${displayHours}:${minutes.toString().padStart(2, '0')} ${ampm}`;
        }
    }

    generateSessionId() {
        return 'chat_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    handleResize() {
        // Handle responsive behavior if needed
        if (window.innerWidth <= 480) {
            // Mobile adjustments
            this.chatWindow.style.height = '70vh';
        } else {
            // Desktop
            this.chatWindow.style.height = '500px';
        }
    }

    // Public methods for external control
    open() {
        this.openChat();
    }

    close() {
        this.closeChat();
    }

    sendPredefinedMessage(message) {
        if (!this.isOpen) {
            this.openChat();
        }
        setTimeout(() => {
            this.chatInput.value = message;
            this.sendMessage();
        }, 300);
    }

    clearChat() {
        this.chatHistory = [];
        this.chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="bot-avatar">
                    <div class="youlearnt-mini-logo">
                        <div class="mini-square red"></div>
                        <div class="mini-square blue"></div>
                    </div>
                </div>
                <div class="message-content">
                    <div class="message-text">Hi, How can we help you?</div>
                    <div class="message-time">a few seconds ago</div>
                </div>
            </div>
        `;
    }

    switchLanguage(lang) {
        this.config.lang = lang;
        this.initializeLanguage();
        
        // Update existing bot messages
        this.updateExistingMessages();
    }

    updateExistingMessages() {
        const messages = this.chatMessages.querySelectorAll('.message.bot');
        messages.forEach(message => {
            const messageText = message.querySelector('.message-text');
            if (messageText) {
                const currentText = messageText.textContent;
                // Check if this is the welcome message
                if (currentText === this.texts.en.welcomeMessage || 
                    currentText === this.texts.ar.welcomeMessage) {
                    messageText.textContent = this.getText('welcomeMessage');
                }
            }
            
            // Update "Powered by AI" text
            const poweredBy = message.querySelector('.powered-by');
            if (poweredBy) {
                poweredBy.textContent = this.getText('poweredBy');
            }
        });
    }

    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
    }
}

// Auto-initialize if the widget HTML is present
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('youlearnt-chat-widget')) {
        // Check if configuration is provided via data attributes or global variable
        const widgetElement = document.getElementById('youlearnt-chat-widget');
        const config = {
            apiUrl: widgetElement.dataset.apiUrl || window.YouLearntConfig?.apiUrl || 'http://161.97.147.7:5000',
            userName: widgetElement.dataset.userName || window.YouLearntConfig?.userName || 'You',
            autoOpen: widgetElement.dataset.autoOpen === 'true' || window.YouLearntConfig?.autoOpen || false,
            enableNotifications: widgetElement.dataset.enableNotifications !== 'false',
            lang: widgetElement.dataset.lang || window.YouLearntConfig?.lang || 'en'
        };

        // Initialize the widget
        window.youLearntChat = new YouLearntChatWidget(config);
    }
});

// Export for use as module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = YouLearntChatWidget;
}
