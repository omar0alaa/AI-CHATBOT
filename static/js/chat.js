document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatMessages = document.getElementById('chat-messages');
    const themeToggle = document.getElementById('theme-toggle');
    const htmlElement = document.documentElement;
    
    // Theme management
    initTheme();
    
    // Event listeners
    messageInput.focus();
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', handleKeyPress);
    themeToggle.addEventListener('click', toggleTheme);
    
    /**
     * Initialize theme based on preferences
     */
    function initTheme() {
        const savedTheme = localStorage.getItem('theme') || 
            (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        setTheme(savedTheme);
    }
    
    /**
     * Toggle between light and dark themes
     */
    function toggleTheme() {
        const currentTheme = htmlElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
    }
    
    /**
     * Set the theme on the document
     */
    function setTheme(theme) {
        htmlElement.setAttribute('data-theme', theme);
        themeToggle.innerHTML = theme === 'dark' 
            ? '<i class="fas fa-sun"></i>' 
            : '<i class="fas fa-moon"></i>';
    }
    
    /**
     * Handle Enter key press for sending messages
     */
    function handleKeyPress(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    }

    /**
     * Send a message to the chatbot
     */
    function sendMessage() {
        const message = messageInput.value.trim();
        if (message) {
            addMessage(message, 'user');
            messageInput.value = '';
            showTypingIndicator();
            scrollToBottom();
            fetchBotResponse(message);
        }
    }

    /**
     * Add a message to the chat interface
     */
    function addMessage(text, sender) {
        removeTypingIndicator();
        
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
        
        // Format AI (bot) messages as Markdown to HTML for better organization
        if (sender === 'bot') {
            messageDiv.innerHTML = window.marked ? window.marked.parse(text) : text.replace(/\n/g, '<br>');
        } else {
            messageDiv.textContent = text;
        }
        
        chatMessages.appendChild(messageDiv);
        
        scrollToBottom();
    }
    
    /**
     * Show the typing indicator
     */
    function showTypingIndicator() {
        removeTypingIndicator();
        
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.classList.add('typing-indicator');
        typingDiv.innerHTML = '<span></span><span></span><span></span>';
        chatMessages.appendChild(typingDiv);
        
        setTimeout(() => {
            typingDiv.style.display = 'block';
            scrollToBottom();
        }, 10);
    }
    
    /**
     * Remove the typing indicator
     */
    function removeTypingIndicator() {
        const existingIndicator = document.getElementById('typing-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }
    }
    
    /**
     * Scroll the chat to the bottom
     */
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    /**
     * Fetch response from the chatbot API
     */
    function fetchBotResponse(message) {
        const lang = localStorage.getItem('protoai_lang') || 'en';
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message, lang: lang })
        })
        .then(response => response.json())
        .then(data => {
            removeTypingIndicator();
            
            if (data.error) {
                addMessage('Sorry, there was an error: ' + data.error, 'bot');
            } else {
                addMessage(data.message, 'bot');
            }
        })
        .catch(error => {
            removeTypingIndicator();
            addMessage('Sorry, there was an error connecting to the server.', 'bot');
            console.error('Error:', error);
        });
    }
});