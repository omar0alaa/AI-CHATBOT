/**
 * YouLearnt Chat Widget Embed Script        return `
            <div id="youlearnt-chat-widget" data-lang="${lang}">`* This script automatically loads and initializes the chat widget
 * Usage: <script src="youlearnt-embed.js" data-api-url="your-api-url"></script>
 */

(function () {
    'use strict';

    // Get configuration from script tag data attributes
    const currentScript = document.currentScript || document.querySelector('script[src*="youlearnt-embed"]');
    const config = {
        apiUrl: currentScript?.dataset.apiUrl || 'http://161.97.147.7:11434',
        userName: currentScript?.dataset.userName || 'User',
        autoOpen: currentScript?.dataset.autoOpen === 'true',
        enableNotifications: currentScript?.dataset.enableNotifications !== 'false',
        primaryColor: currentScript?.dataset.primaryColor || '#2B4C8C',
        position: currentScript?.dataset.position || 'bottom-right',
        lang: currentScript?.dataset.lang || 'en'
    };

    // Get the base URL for assets
    const scriptSrc = currentScript?.src || '';
    const baseUrl = scriptSrc.substring(0, scriptSrc.lastIndexOf('/'));

    // Create widget HTML
    function createWidgetHTML() {
        const texts = {
            en: {
                online: 'Online',
                placeholder: 'Type your message...',
                sendTitle: 'Send message'
            },
            ar: {
                online: 'متصل',
                placeholder: 'اكتب رسالتك...',
                sendTitle: 'إرسال الرسالة'
            }
        };
        
        const lang = config.lang || 'en';
        const t = texts[lang] || texts.en;
        
        return `
            <div id="youlearnt-chat-widget" data-lang="en">
            <!-- Chat Toggle Button -->
            <div id="chat-toggle-btn" class="chat-toggle">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M20 2H4C2.9 2 2 2.9 2 4V16C2 17.1 2.9 18 4 18H6L10 22L14 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2Z" fill="white"/>
                </svg>
                <div class="notification-badge" id="notification-badge" style="display: none;">1</div>
            </div>

            <!-- Chat Window -->
            <div id="chat-window" class="chat-window">
                <!-- Close Button -->
                <button id="close-chat" class="close-btn">
                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                        <path d="M12 4L4 12M4 4L12 12" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
                
                <!-- Chat Header -->
                <div class="chat-header">
                    <div class="header-left">
                        <div class="logo-squares">
                            <div class="square red-circle"></div>
                            <div class="square blue-circle"></div>
                            <div class="square red-square"></div>
                            <div class="square blue-square"></div>
                        </div>
                        <div class="brand-text">
                            <span class="brand-name">Ask<span class="brand-yl">YL</span>.AI</span>
                            <div class="status-text">
                                <span class="status-bullet">•</span>
                                <span id="online-status">Online</span>
                            </div>
                        </div>
                    </div>
                    <div class="header-right">
                        <div class="language-toggle">
                            <button id="lang-ar" class="lang-btn">ع</button>
                            <button id="lang-en" class="lang-btn active">En</button>
                        </div>
                    </div>
                </div>

                <!-- Chat Messages -->
                <div class="chat-messages" id="chat-messages">
                    
                </div>

                <!-- Chat Input -->
                <div class="chat-input-container">
                    <div class="chat-input-wrapper">
                        <input type="text" id="chat-input" placeholder="Write your message" autocomplete="off">
                        <button id="send-btn" class="send-btn" title="Send message">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" fill="currentColor"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>
        `;
    }

    // Load CSS file
    function loadCSS() {
        // Load Font Awesome
        const fontAwesome = document.createElement('link');
        fontAwesome.rel = 'stylesheet';
        fontAwesome.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css';
        document.head.appendChild(fontAwesome);
        
        // Load widget CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = baseUrl.replace('/js', '/css') + '/chat-widget.css';
        link.onerror = function () {
            console.warn('YouLearnt Chat Widget: Could not load CSS from', link.href);
        };
        document.head.appendChild(link);
    }

    // Load JavaScript file and initialize widget
    function loadJS() {
        const script = document.createElement('script');
        script.src = baseUrl + '/chat-widget.js';
        script.onload = function () {
            initializeWidget();
        };
        script.onerror = function () {
            console.error('YouLearnt Chat Widget: Could not load JS from', script.src);
        };
        document.head.appendChild(script);
    }

    // Initialize the widget
    function initializeWidget() {
        // Set global config
        window.YouLearntConfig = config;

        // Initialize widget if class is available
        if (typeof YouLearntChatWidget !== 'undefined') {
            window.youLearntChat = new YouLearntChatWidget(config);
        } else {
            console.error('YouLearnt Chat Widget: Widget class not found');
        }
    }

    // Main initialization function
    function init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        // Check if widget already exists
        if (document.getElementById('youlearnt-chat-widget')) {
            console.warn('YouLearnt Chat Widget: Widget already exists on page');
            return;
        }

        // Create widget HTML
        const widgetHTML = createWidgetHTML();
        document.body.insertAdjacentHTML('beforeend', widgetHTML);

        // Load CSS and JS
        loadCSS();
        loadJS();
    }

    // Start initialization
    init();

    // Expose global methods for external control
    window.YouLearntWidget = {
        open: function () {
            if (window.youLearntChat) {
                window.youLearntChat.open();
            }
        },
        close: function () {
            if (window.youLearntChat) {
                window.youLearntChat.close();
            }
        },
        sendMessage: function (message) {
            if (window.youLearntChat) {
                window.youLearntChat.sendPredefinedMessage(message);
            }
        },
        clear: function () {
            if (window.youLearntChat) {
                window.youLearntChat.clearChat();
            }
        },
        updateConfig: function (newConfig) {
            if (window.youLearntChat) {
                window.youLearntChat.updateConfig(newConfig);
            }
        }
    };

})();
