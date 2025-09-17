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
    const savedTheme = localStorage.getItem('theme') || 'light';
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
        if (sender === 'user') messageDiv.classList.add('user');

        // Avatar
        let avatarDiv;
            if (sender === 'bot') {
                avatarDiv = document.createElement('div');
                avatarDiv.className = 'bot-avatar';
                avatarDiv.innerHTML = `
                    <div class="logo-squares">
                        <div class="square red-circle"></div>
                        <div class="square blue-circle"></div>
                        <div class="square red-square"></div>
                        <div class="square blue-square"></div>
                    </div>
                `;
            } else {
                avatarDiv = document.createElement('div');
                avatarDiv.className = 'user-avatar';
                const lang = localStorage.getItem('protoai_lang') || 'en';
                avatarDiv.textContent = lang === 'ar' ? 'أنت' : 'You';
            }
        messageDiv.appendChild(avatarDiv);

        // Message content
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        // Message text
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        if (sender === 'bot') {
            textDiv.innerHTML = window.marked ? window.marked.parse(text) : text.replace(/\n/g, '<br>');
        } else {
            textDiv.textContent = text;
        }
        contentDiv.appendChild(textDiv);

        // Powered by AI (bot only)
        if (sender === 'bot') {
            const poweredDiv = document.createElement('div');
            poweredDiv.className = 'powered-by';
            poweredDiv.textContent = 'Powered by AI';
            contentDiv.appendChild(poweredDiv);
        }

        // Message time
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        const now = new Date();
        const minutes = now.getMinutes().toString().padStart(2, '0');
        const hours = now.getHours();
        const ampm = hours >= 12 ? 'PM' : 'AM';
        const displayHours = hours % 12 || 12;
        timeDiv.textContent = `${displayHours}:${minutes} ${ampm}`;
        contentDiv.appendChild(timeDiv);

        messageDiv.appendChild(contentDiv);
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