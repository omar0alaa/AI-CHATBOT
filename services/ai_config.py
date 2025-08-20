# AI Chat Configuration - Central place for all AI and chat-related settings

import os

class AIConfig:
    #Centralized configuration for AI chat settings
    
    # === Ollama AI Settings ===
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    
    # === Core Generation Settings ===
    OLLAMA_STREAM = False                # Enable streaming responses (True/False)
    OLLAMA_NUM_PREDICT = 400            # Maximum number of tokens to generate (increased for longer responses)
    OLLAMA_TEMPERATURE = 0.5             # Creativity/randomness (increased for more detailed responses)
    
    # === Advanced Sampling ===
    OLLAMA_TOP_K = 50                    # Limit next token selection to top K tokens (increased for variety)
    OLLAMA_TOP_P = 0.9                   # Nucleus sampling threshold (increased for more diverse vocabulary)
    OLLAMA_REPEAT_PENALTY = 1.05         # Penalty for repeating tokens (reduced to allow natural repetition)
    OLLAMA_REPEAT_LAST_N = 128           # Look back N tokens for repeat penalty (increased for longer context)
    OLLAMA_SEED = None                   # Random seed for reproducible outputs (None = random)
    
    # === Performance Settings ===
    OLLAMA_NUM_CTX = 2048               # Context window size (number of tokens)
    OLLAMA_NUM_BATCH = 512              # Batch size for processing
    OLLAMA_NUM_GPU = -1                 # Number of GPU layers (-1 = auto, 0 = CPU only)
    OLLAMA_MAIN_GPU = 0                 # Which GPU to use for processing
    OLLAMA_LOW_VRAM = False             # Optimize for low VRAM usage
    OLLAMA_NUM_THREAD = None            # Number of threads (None = auto)
    
    # === Memory Management ===
    OLLAMA_F16_KV = True                # Use 16-bit floats for key/value cache
    OLLAMA_VOCAB_ONLY = False           # Only load vocabulary, not weights
    OLLAMA_USE_MMAP = True              # Use memory mapping for faster loading
    OLLAMA_USE_MLOCK = False            # Lock memory to prevent swapping
    
    # === Request Timeouts ===
    OLLAMA_CONNECTIVITY_TIMEOUT = 5       # seconds - for testing if Ollama is running
    OLLAMA_REQUEST_TIMEOUT = 120          # seconds - for actual AI generation requests
    
    # === Knowledge Base Settings ===
    SIMILARITY_THRESHOLD = 0.7            # minimum similarity for knowledge base matches (0.0-1.0)
    MAX_KNOWLEDGE_CONTEXTS = 3            # maximum number of knowledge base results to use
    
    # === Chat History Settings ===
    MAX_CHAT_EXCHANGES = 5                # number of user-AI exchanges to keep in history
    MAX_CONVERSATION_CONTEXT = 2          # number of previous AI responses to include as context
    
    # === Content Rewriting Settings ===
    REWRITE_MAX_TOKENS = 256              # maximum tokens for content rewriting
    REWRITE_DO_SAMPLE = False             # whether to use sampling in rewriting
    
    # === Content Filtering Settings ===
    RESTRICTIVENESS_LEVEL = "balanced"    # restrictive, balanced, or open
    
    # === Debug Settings ===
    SHOW_DEBUG = os.environ.get("SHOW_DEBUG", "false").lower() == "true"
    
    # === Language Detection ===
    DEFAULT_LANGUAGE = "en"               # fallback language when detection fails
    
    @classmethod
    def get_max_history_messages(cls):
        #Get maximum total messages in chat history (exchanges * 2)
        return cls.MAX_CHAT_EXCHANGES * 2
    
    @classmethod
    def get_ollama_options(cls):
        #Get Ollama generation options as a dictionary
        options = {}
        
        # Only include non-None values
        if cls.OLLAMA_NUM_PREDICT is not None:
            options["num_predict"] = cls.OLLAMA_NUM_PREDICT
        if cls.OLLAMA_TEMPERATURE is not None:
            options["temperature"] = cls.OLLAMA_TEMPERATURE
        if cls.OLLAMA_TOP_K is not None:
            options["top_k"] = cls.OLLAMA_TOP_K
        if cls.OLLAMA_TOP_P is not None:
            options["top_p"] = cls.OLLAMA_TOP_P
        if cls.OLLAMA_REPEAT_PENALTY is not None:
            options["repeat_penalty"] = cls.OLLAMA_REPEAT_PENALTY
        if cls.OLLAMA_REPEAT_LAST_N is not None:
            options["repeat_last_n"] = cls.OLLAMA_REPEAT_LAST_N
        if cls.OLLAMA_SEED is not None:
            options["seed"] = cls.OLLAMA_SEED
        if cls.OLLAMA_NUM_CTX is not None:
            options["num_ctx"] = cls.OLLAMA_NUM_CTX
        if cls.OLLAMA_NUM_BATCH is not None:
            options["num_batch"] = cls.OLLAMA_NUM_BATCH
        if cls.OLLAMA_NUM_GPU is not None:
            options["num_gpu"] = cls.OLLAMA_NUM_GPU
        if cls.OLLAMA_MAIN_GPU is not None:
            options["main_gpu"] = cls.OLLAMA_MAIN_GPU
        if cls.OLLAMA_LOW_VRAM is not None:
            options["low_vram"] = cls.OLLAMA_LOW_VRAM
        if cls.OLLAMA_F16_KV is not None:
            options["f16_kv"] = cls.OLLAMA_F16_KV
        if cls.OLLAMA_VOCAB_ONLY is not None:
            options["vocab_only"] = cls.OLLAMA_VOCAB_ONLY
        if cls.OLLAMA_USE_MMAP is not None:
            options["use_mmap"] = cls.OLLAMA_USE_MMAP
        if cls.OLLAMA_USE_MLOCK is not None:
            options["use_mlock"] = cls.OLLAMA_USE_MLOCK
        if cls.OLLAMA_NUM_THREAD is not None:
            options["num_thread"] = cls.OLLAMA_NUM_THREAD
            
        return options
    
    @classmethod
    def update_similarity_threshold(cls, new_threshold):
        #Update similarity threshold for knowledge base matching
        if 0.0 <= new_threshold <= 1.0:
            cls.SIMILARITY_THRESHOLD = new_threshold
            return True
        return False
    
    @classmethod
    def update_temperature(cls, new_temperature):
        #Update Ollama temperature setting
        if 0.0 <= new_temperature <= 2.0:
            cls.OLLAMA_TEMPERATURE = new_temperature
            return True
        return False
    
    @classmethod
    def update_max_tokens(cls, new_max_tokens):
        #Update maximum tokens to generate
        if new_max_tokens == -1 or new_max_tokens > 0:
            cls.OLLAMA_NUM_PREDICT = new_max_tokens
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
            "ollama_url": cls.OLLAMA_API_URL,
            "ollama_model": cls.OLLAMA_MODEL,
            "ollama_stream": cls.OLLAMA_STREAM,
            "ollama_max_tokens": cls.OLLAMA_NUM_PREDICT,
            "ollama_temperature": cls.OLLAMA_TEMPERATURE,
            "ollama_top_k": cls.OLLAMA_TOP_K,
            "ollama_top_p": cls.OLLAMA_TOP_P,
            "ollama_context_size": cls.OLLAMA_NUM_CTX,
            "similarity_threshold": cls.SIMILARITY_THRESHOLD,
            "max_contexts": cls.MAX_KNOWLEDGE_CONTEXTS,
            "max_exchanges": cls.MAX_CHAT_EXCHANGES,
            "connectivity_timeout": cls.OLLAMA_CONNECTIVITY_TIMEOUT,
            "request_timeout": cls.OLLAMA_REQUEST_TIMEOUT,
            "restrictiveness_level": cls.RESTRICTIVENESS_LEVEL,
            "debug_enabled": cls.SHOW_DEBUG
        }


# Create a singleton instance for easy importing
ai_config = AIConfig()
