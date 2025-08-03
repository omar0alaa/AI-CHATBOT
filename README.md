# AI Chatbot with Python, SQLite Knowledge Base, and Ollama

A web-based AI chatbot built with Python Flask and Ollama for local LLM inference, powered by a SQLite knowledge base.

## Features

- Web interface for chatting with the AI (bilingual: English/Arabic, with language switcher)
- Backend API built with Flask
- Integration with Ollama for local LLM inference (no cloud, no API keys)
- Uses a SQLite database (`youlearnt_bank.db`) as the knowledge base for all answers
- Professional support agent persona, always answers in the website's selected language
- All answers formatted with clear paragraphs, bullet points, and bold for key terms
- Responsive, modern UI with dark mode and RTL support for Arabic
- Session-based chat history (per user, persists until session is cleared)

## Prerequisites

1. Install [Ollama](https://ollama.com/) on your computer or server
2. Download a language model through Ollama (e.g., gemma3:4b, gemma3:1b, phi3:mini, etc.)
3. Start the Ollama server

## Ollama Setup

1. Download and install Ollama from [ollama.com](https://ollama.com/)
2. Open a terminal and run:
   ```
   ollama run gemma3:1b
   ```
   Or replace `gemma3:1b` with your preferred model.
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
   OLLAMA_API_URL=http://localhost:11434/api/generate
   OLLAMA_MODEL=gemma3:1b
   ```

5. Run the application:
   ```
   python app.py
   ```

6. Open your browser and navigate to `http://127.0.0.1:5000`

## Usage Notes

- The SQLite database (`youlearnt_bank.db`) is the only source of knowledge for the AI. All answers are generated using the most relevant entries from this database.
- If the user's question does not match any database entry, the AI will respond with a friendly greeting for greetings/help requests, or with a fallback message for unknown questions.
- The AI always answers in the website's selected language (English or Arabic), regardless of the question's language.
- All answers are formatted for clarity and professionalism.

## Project Structure

- `app.py`: Main Flask application (backend, SQLite/Ollama integration, endpoints)
- `persona.py`: Persona logic for professional support agent
- `postprocess.py`: Post-processing filter for forbidden phrases
- `templates/index.html`: Main chat interface (bilingual UI, file upload, language switcher)
- `static/js/chat.js`: Chat logic, markdown rendering
- `static/js/upload.js`: File upload logic
- `youlearnt_bank.db`: SQLite knowledge base
- `requirements.txt`: Project dependencies

## TO DO
- Enhance reply speed
- Enhance reply formatting
- Use better persona description
- Better token usage efficiency
- Implement better session handling (for each user)
- Add post-processing filter

## Deployment

This application is designed to work with a local Ollama server. For production use, consider running both the Flask application and Ollama on the same server.

### Production Deployment

1. **Start Ollama as a background service**
   - Make sure Ollama is running and your model is loaded:
     ```
     ollama serve &
     ollama run gemma3:1b &
     ```
   - You may want to use a process manager (like `systemd` or `pm2`) to keep Ollama running.

2. **Running with Waitress (recommended for production)**
   - Install Waitress:
   ```
   pip install waitress
   ```
   - Run the Flask app with Waitress:
   ```
   waitress-serve --port=5000 app:app
   ```
   - You can change the port as needed.
   - Waitress is a good choice for production on Windows servers.
   ```