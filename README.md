# AI Chatbot with Python, LlamaIndex, and Ollama

A web-based AI chatbot built with Python Flask and Ollama for local LLM inference.

![image](https://github.com/user-attachments/assets/7d2b274e-5deb-4485-a039-927d001c111d)

## Features

- Web interface for chatting with the AI (bilingual: English/Arabic, with language switcher)
- Backend API built with Flask
- Integration with Ollama for local LLM inference (no cloud, no API keys)
- Uses LlamaIndex for document Q&A over admin and user-uploaded files
- Local HuggingFace embeddings (BAAI/bge-small-en-v1.5)
- File upload: users can upload PDF, DOCX, TXT, and image files for Q&A
- Admin document is always loaded as the base knowledge
- Uploaded files are deleted after each answer (admin doc is never deleted)
- Professional support agent persona, always answers in the website's selected language
- All answers formatted with clear paragraphs, bullet points, and bold for key terms
- Responsive, modern UI with dark mode and RTL support for Arabic
- Session-based chat history (per user, persists until session is cleared)

## Prerequisites

1. Install [Ollama](https://ollama.com/) on your computer or server
2. Download a language model through Ollama (e.g., llama3, gemma3:4b, etc.)
3. Start the Ollama server

## Ollama Setup

1. Download and install Ollama from [ollama.com](https://ollama.com/)
2. Open a terminal and run:
   ```
   ollama run gemma3:4b
   ```
   Or replace `gemma3:4b` with your preferred model.
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
   OLLAMA_MODEL=gemma3:4b
   ```

5. Run the application:
   ```
   python app.py
   ```

6. Open your browser and navigate to `http://127.0.0.1:5000`

## Usage Notes

- The admin document is always loaded and forms the base knowledge for the AI.
- When a user uploads files, the index is rebuilt to include both the admin doc and all uploaded files.
- After each answer, all user-uploaded files are deleted automatically (admin doc is never deleted).
- The AI always answers in the website's selected language (English or Arabic), regardless of the question's language.
- All answers are formatted for clarity and professionalism.

## Project Structure

- `app.py`: Main Flask application (backend, LlamaIndex/Ollama integration, endpoints)
- `templates/index.html`: Main chat interface (bilingual UI, file upload, language switcher)
- `static/js/chat.js`: Chat logic, markdown rendering
- `static/js/upload.js`: File upload logic
- `uploaded_docs/`: Directory for user-uploaded files (auto-cleaned after each answer)
- `llamaindex_storage/`: Persistent storage for LlamaIndex
- `requirements.txt`: Project dependencies

## TO DO 
1. Implement Chat History backend database
2. Change backend to send AI Description only at the start of conversation ✅
3. Add Custom API for chatting and test with Postman
4. Enhance the reply speed 
5. Enhance the reply formatting ✅
6. Use better persona description ✅
7. Better Token usage efficiency ✅
8. implement better session handling (for each user) ✅
9. implement File handling ✅
10. better prompt refactoring ✅
11. read whole file before answering ✅
12. Add post-processing filter

# content on the database question

## Deployment

This application is designed to work with a local Ollama server. For production use, consider running both the Flask application and Ollama on the same server.

### Production Deployment

1. **Start Ollama as a background service**
   - Make sure Ollama is running and your model is loaded:
     ```
     ollama serve &
     ollama run gemma3:4b &
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