# How to Run the App & Install Dependencies

This guide explains how to set up, install dependencies, and run the AIChatBot-Python Flask app. It is formatted for GitHub Wiki usage.

---

## Prerequisites
- **Python 3.10+** (recommended)
- **pip** (Python package manager)
- **Git** (to clone the repository)
- **Ollama** (for LLM backend, see [Ollama documentation](https://ollama.com/))

---

## 1. Clone the Repository
```sh
git clone https://github.com/omar0alaa/AIChatBot-Python.git
cd AIChatBot-Python/AIChatBot-Python
```

---

## 2. Create a Virtual Environment (Recommended)
```sh
python -m venv venv
# Activate the environment:
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

---

## 3. Install Required Packages
```sh
pip install -r requirements.txt
```

---

## 4. Set Environment Variables
Create a `.env` file in the project root (optional, but recommended):
```
FLASK_SECRET_KEY=your-secret-key
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=gemma3:1b
```

---

## 5. Start Ollama (LLM Backend)
- Download and install Ollama from [ollama.com](https://ollama.com/).
- Start Ollama and ensure your chosen model (e.g., gemma3:1b) is available.

---

## 6. Initialize the Database
The app will automatically create the SQLite database (`youlearnt_bank.db`) and table on first run. No manual setup needed.

---

## 7. Run the Flask App
```sh
python app.py
```
- The app will start on `http://localhost:5000` by default.

---

## 8. Access the Web UIs
- **Main Chat:** [http://localhost:5000/](http://localhost:5000/)
- **Admin DB Editor:** [http://localhost:5000/admin/db](http://localhost:5000/admin/db)
- **Widget:** [http://localhost:5000/widget](http://localhost:5000/widget)

---

## 9. Troubleshooting
- If you see missing package errors, re-run `pip install -r requirements.txt`.
- For NLTK errors, the app will auto-download required data.
- Ensure Ollama is running and accessible at the URL in your `.env`.

---

## 10. Stopping the App
- Press `Ctrl+C` in the terminal to stop Flask.
- Deactivate the virtual environment with `deactivate`.

---

## 11. Additional Notes
- For API testing, see the [API Testing Guide](API_TESTING.md).
- For advanced deployment (Docker, cloud), see the main README.

---

Feel free to copy this page to your GitHub Wiki for easy onboarding and setup instructions.
