// Proto AI Widget JS
// Basic logic for sending/receiving messages in the widget

document.addEventListener('DOMContentLoaded', function() {
    const fab = document.getElementById('widget-fab');
    const popup = document.getElementById('widget-chat-popup');
    const closeBtn = document.getElementById('widget-close-btn');
    const messages = document.getElementById('widget-chat-messages');
    const input = document.getElementById('widget-message-input');
    const sendBtn = document.getElementById('widget-send-button');

    // Show popup on FAB click
    fab.addEventListener('click', function() {
        popup.classList.add('open');
        input.focus();
        fab.style.display = 'none';
    });
    // Hide popup on close
    closeBtn.addEventListener('click', function() {
        popup.classList.remove('open');
        fab.style.display = 'flex';
    });

    function appendMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `widget-message ${sender}-message`;
        // Format AI (bot) messages as Markdown to HTML for better organization
        if (sender === 'bot') {
            msgDiv.innerHTML = window.marked ? window.marked.parse(text) : text.replace(/\n/g, '<br>');
        } else {
            msgDiv.textContent = text;
        }
        messages.appendChild(msgDiv);
        messages.scrollTop = messages.scrollHeight;
        return msgDiv;
    }

    function showTyping() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'widget-message bot-message typing';
        typingDiv.innerHTML = '<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>';
        messages.appendChild(typingDiv);
        messages.scrollTop = messages.scrollHeight;
        return typingDiv;
    }

    function removeTyping(typingDiv) {
        if (typingDiv && typingDiv.parentNode) {
            typingDiv.parentNode.removeChild(typingDiv);
        }
    }

    function typeText(element, text, speed = 18) {
        element.textContent = '';
        let i = 0;
        function typeChar() {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                setTimeout(typeChar, speed);
            }
        }
        typeChar();
    }

    function sendMessage() {
        const text = input.value.trim();
        if (!text) return;
        appendMessage(text, 'user');
        input.value = '';
        const typingDiv = showTyping();
        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        })
        .then(res => res.json())
        .then(data => {
            removeTyping(typingDiv);
            const msgDiv = appendMessage('', 'bot');
            typeText(msgDiv, data.message || data.error || 'No response');
        })
        .catch(() => {
            removeTyping(typingDiv);
            const msgDiv = appendMessage('', 'bot');
            typeText(msgDiv, 'Sorry, there was an error.');
        });
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') sendMessage();
    });
});
