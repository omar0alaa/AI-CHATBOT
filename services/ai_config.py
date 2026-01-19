"""Centralized configuration for AI chat settings."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded even if this module is imported before app.py
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / '.env')


class AIConfig:
    # === Groq AI Settings ===
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_API_URL = os.getenv(
        "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"
    )
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

    # === Core Generation Settings ===
    GROQ_STREAM = False                 # Streaming not used in current UI
    GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "220"))
    GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.7"))
    GROQ_TOP_P = float(os.getenv("GROQ_TOP_P", "0.9"))

    # === Request Timeouts ===
    GROQ_REQUEST_TIMEOUT = int(os.getenv("GROQ_REQUEST_TIMEOUT", "120"))

    # === Knowledge Base Settings ===
    SIMILARITY_THRESHOLD = 0.7          # minimum similarity for knowledge base matches (0.0-1.0)
    MAX_KNOWLEDGE_CONTEXTS = 3          # maximum number of knowledge base results to use

    # === Chat History Settings ===
    MAX_CHAT_EXCHANGES = 5              # number of user-AI exchanges to keep in history
    MAX_CONVERSATION_CONTEXT = 2        # number of previous AI responses to include as context

    # === Content Rewriting Settings ===
    REWRITE_MAX_TOKENS = 256            # maximum tokens for content rewriting
    REWRITE_DO_SAMPLE = False           # whether to use sampling in rewriting

    # === Content Filtering Settings ===
    RESTRICTIVENESS_LEVEL = "open"  # restrictive, balanced, or open

    # === Debug Settings ===
    SHOW_DEBUG = os.environ.get("SHOW_DEBUG", "false").lower() == "true"

    # === Language Detection ===
    DEFAULT_LANGUAGE = "en"             # fallback language when detection fails

    @classmethod
    def get_max_history_messages(cls):
        #Get maximum total messages in chat history (exchanges * 2)
        return cls.MAX_CHAT_EXCHANGES * 2

    @classmethod
    def get_groq_params(cls):
        #Get Groq generation parameters as a dictionary
        return {
            "model": cls.GROQ_MODEL,
            "max_tokens": cls.GROQ_MAX_TOKENS,
            "temperature": cls.GROQ_TEMPERATURE,
            "top_p": cls.GROQ_TOP_P,
            "stream": cls.GROQ_STREAM,
        }

    @classmethod
    def update_similarity_threshold(cls, new_threshold):
        #Update similarity threshold for knowledge base matching
        if 0.0 <= new_threshold <= 1.0:
            cls.SIMILARITY_THRESHOLD = new_threshold
            return True
        return False

    @classmethod
    def update_temperature(cls, new_temperature):
        #Update Groq temperature setting
        if 0.0 <= new_temperature <= 2.0:
            cls.GROQ_TEMPERATURE = new_temperature
            return True
        return False

    @classmethod
    def update_max_tokens(cls, new_max_tokens):
        #Update maximum tokens to generate
        if new_max_tokens == -1 or new_max_tokens > 0:
            cls.GROQ_MAX_TOKENS = new_max_tokens
            return True
        return False

    @classmethod
    def set_restrictiveness(cls, level):
        #Set AI restrictiveness level
        valid_levels = ['restrictive', 'balanced', 'open']
        if level in valid_levels:
            cls.RESTRICTIVENESS_LEVEL = level
            return True
        return False

    @classmethod
    def get_restrictiveness(cls):
        #Get current AI restrictiveness level
        return cls.RESTRICTIVENESS_LEVEL

    @classmethod
    def get_config_summary(cls):
        #Get a summary of current configuration
        return {
            "groq_api_url": cls.GROQ_API_URL,
            "groq_model": cls.GROQ_MODEL,
            "groq_max_tokens": cls.GROQ_MAX_TOKENS,
            "groq_temperature": cls.GROQ_TEMPERATURE,
            "groq_top_p": cls.GROQ_TOP_P,
            "similarity_threshold": cls.SIMILARITY_THRESHOLD,
            "max_contexts": cls.MAX_KNOWLEDGE_CONTEXTS,
            "max_exchanges": cls.MAX_CHAT_EXCHANGES,
            "request_timeout": cls.GROQ_REQUEST_TIMEOUT,
            "restrictiveness_level": cls.RESTRICTIVENESS_LEVEL,
            "debug_enabled": cls.SHOW_DEBUG,
        }


# Create a singleton instance for easy importing
ai_config = AIConfig()
