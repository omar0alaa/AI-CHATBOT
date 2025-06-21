# AI Chatbot with Python and Ollama

A web-based AI chatbot built with Python Flask and Ollama for local LLM inference.

![image](https://github.com/user-attachments/assets/7d2b274e-5deb-4485-a039-927d001c111d)

## Features

- Web interface for chatting with the AI
- Backend API built with Flask
- Integration with Ollama for local LLM inference
- Responsive UI with modern design
- No API keys or cloud services required

## Prerequisites

1. Install [Ollama](https://ollama.com/) on your computer or server
2. Download a language model through Ollama (e.g., llama3, gemma2:2b, etc.)
3. Start the Ollama server

## Ollama Setup

1. Download and install Ollama from [ollama.com](https://ollama.com/)
2. Open a terminal and run:
   ```
   ollama run llama3
   ```
   Or replace `llama3` with your preferred model (e.g., `gemma2:2b`).
3. The server should be running on http://localhost:11434 by default

## Chatbot Setup

1. Clone the repository:
   ```
   git clone https://github.com/omar0alaa/AIChatBot-Python.git
   cd AIChatBot-Python
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. (Optional) Create a `.env` file to customize the Ollama API endpoint or model:
   ```
   OLLAMA_API_URL=http://localhost:11434/api/chat
   OLLAMA_MODEL=gemma2:2b
   ```

5. Run the application:
   ```
   python app.py
   ```

6. Open your browser and navigate to `http://127.0.0.1:5000`

## Project Structure

- `app.py`: Main Flask application
- `templates/index.html`: Chat interface
- `requirements.txt`: Project dependencies

## Customization

You can customize the AI behavior by modifying the system prompt in `app.py`:

```python
"messages": [
    {"role": "system", "content": "[Your description of the AI personality.]"},
    {"role": "user", "content": user_message}
]
```

You can also adjust the generation parameters:

```python
payload = {
    "messages": [...],
    "temperature": 0.7,  # Controls randomness (lower is more deterministic)
    "max_tokens": 500    # Maximum response length
}
```
## TO DO 
1. Implement Chat History backend database
2. Change backend to send AI Description only at the start of conversation ✅
3. Add Custom API for chatting and test with Postman
4. Enhance the reply speed 
5. Enhance the reply formatting ✅
6. Use better persona description
7. Better Token usage efficiency ✅
8. implement better session handling (for each user)
9. implement File handling

## Deployment

This application is designed to work with a local Ollama server. For production use, consider running both the Flask application and Ollama on the same server.

## License

See the LICENSE file for details.
