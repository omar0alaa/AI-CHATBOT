# Chat service - Handles all chat-related business logic

import time
import json
import os
import requests
from langdetect import detect
from persona import get_persona_prompt
from postprocess import contains_forbidden_phrase, get_fallback_message, contains_inappropriate_content, get_inappropriate_response, contains_inappropriate_content, get_inappropriate_response
from logger import log_debug, log_info, log_warning, log_error
from .database_service import get_answer_from_db


class ChatService:
    #Service class for handling chat operations    
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
        self.model_name = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    
    def process_message(self, user_message, ui_lang, chat_history):
        #Process a user message and return AI response
        log_info("========== NEW CHAT REQUEST ==========")
        log_debug(f"Received message: {user_message}")
        log_debug(f"UI Language: {ui_lang}")
        
        # Language detection
        user_lang = self._detect_language(user_message, ui_lang)
        log_debug(f"Final language: {user_lang}")
        
        # Check for inappropriate content first
        if contains_inappropriate_content(user_message, user_lang):
            log_warning(f"Inappropriate content detected, blocking request")
            inappropriate_response = get_inappropriate_response(user_lang)
            
            # Update chat history with user message and inappropriate response
            updated_history = self._update_chat_history(chat_history, user_message, user_lang)
            final_history = self._finalize_chat_history(updated_history, inappropriate_response)
            
            return inappropriate_response, final_history
        
        # Update chat history with system prompt
        updated_history = self._update_chat_history(chat_history, user_message, user_lang)
        
        # Get knowledge base context
        contexts = self._get_knowledge_context(user_message, user_lang)
        
        # Generate AI response
        answer = self._generate_ai_response(user_message, user_lang, contexts)
        
        # Post-process the response
        processed_answer = self._post_process_response(answer, user_message, user_lang)
        
        # Update chat history with response
        final_history = self._finalize_chat_history(updated_history, processed_answer)
        
        # Save debug information
        self._save_debug_info(final_history, user_message, answer, processed_answer)
        
        log_debug(f"Final answer: {len(processed_answer)} characters")
        return processed_answer, final_history
    
    def _detect_language(self, user_message, ui_lang):
        #Detect user message language
        if ui_lang == 'ar':
            return 'ar'
        elif ui_lang == 'en':
            return 'en'
        else:
            try:
                user_lang = detect(user_message)
                log_debug(f"Auto-detected language: {user_lang}")
                return user_lang
            except Exception as e:
                log_error(f"Language detection failed: {e}")
                return 'en'
    
    def _update_chat_history(self, chat_history, user_message, user_lang):
        #Update chat history with system prompt and user message
        lang_instruction = get_persona_prompt(user_lang)
        
        # Remove old system prompts and add new one
        history = [msg for msg in chat_history if msg['role'] != 'system']
        history.insert(0, {"role": "system", "content": lang_instruction})
        history.append({"role": "user", "content": user_message})
        
        return history
    
    def _get_knowledge_context(self, user_message, user_lang):
        #Retrieve relevant context from knowledge base
        try:
            contexts = get_answer_from_db(user_message, user_lang)
            log_debug(f"Found {len(contexts)} contexts from database")
            if contexts:
                for i, ctx in enumerate(contexts):
                    log_debug(f"Context {i+1}: {ctx[:100]}...")
            else:
                log_debug(f"No relevant contexts found for message: {user_message}")
            return contexts
        except Exception as e:
            log_error(f"Database query failed: {e}")
            return []
    
    def _generate_ai_response(self, user_message, user_lang, contexts):
        #Generate AI response using Ollama
        log_debug(f"Ollama URL: {self.ollama_url}")
        log_debug(f"Model: {self.model_name}")
        
        fallback_message = get_fallback_message(user_lang)
        lang_instruction = get_persona_prompt(user_lang)
        
        # Check if it's a simple greeting
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'مرحبا', 'أهلا', 'السلام عليكم', 'صباح الخير', 'مساء الخير']
        help_requests = ['help', 'can you help', 'i need help', 'مساعدة', 'هل يمكنك مساعدتي', 'أحتاج مساعدة']
        
        user_lower = user_message.lower().strip()
        is_greeting = any(greeting in user_lower for greeting in greetings)
        is_help_request = any(help_req in user_lower for help_req in help_requests)
        
        # Build prompt based on whether we have context
        if not contexts:
            if is_greeting or is_help_request:
                log_debug("Processing greeting/help request with fallback prompt")
                from persona import get_persona_fallback_prompt
                prompt = get_persona_fallback_prompt(user_lang, user_message)
            else:
                log_debug("No context found and not a greeting - returning fallback message")
                return fallback_message
        else:
            log_debug(f"Using knowledge base prompt with {len(contexts)} contexts")
            context_str = "\n".join([f"- {c}" for c in contexts])
            prompt = f"{lang_instruction}\n\nAvailable Information:\n{context_str}\n\nUser Question: {user_message}\n\nIMPORTANT: Only answer if the question can be fully answered using the above information. If not, respond with the standard fallback message."
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        log_debug(f"Sending request to Ollama at {self.ollama_url}...")
        log_debug(f"Prompt length: {len(payload['prompt'])} characters")
        
        try:
            return self._make_ollama_request(payload, fallback_message)
        except Exception as e:
            log_error(f"AI generation failed: {e}")
            return fallback_message
    
    def _make_ollama_request(self, payload, fallback_message):
        #Make request to Ollama API
        start_time = time.time()
        
        # Test connectivity first
        try:
            test_resp = requests.get(self.ollama_url.replace('/api/generate', '/api/tags'), timeout=5)
            log_debug(f"Ollama connectivity test: {test_resp.status_code}")
        except Exception as conn_e:
            log_error(f"Ollama connectivity test failed: {conn_e}")
            log_warning(f"Make sure Ollama is running: ollama serve")
            raise Exception(f"Ollama not accessible: {conn_e}")
        
        # Make the actual request
        resp = requests.post(self.ollama_url, json=payload, timeout=120)
        end_time = time.time()
        
        log_debug(f"Response time: {end_time - start_time:.2f} seconds")
        log_debug(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log_error(f"Ollama error {resp.status_code}: {resp.text}")
            return fallback_message
        
        try:
            result = resp.json()
            log_debug(f"Response keys: {list(result.keys())}")
            
            raw_response = result.get("response", "")
            if not raw_response or raw_response.strip() == "":
                log_error(f"Empty response from Ollama")
                return fallback_message
            
            log_debug(f"Got valid response ({len(raw_response)} chars)")
            return raw_response
            
        except json.JSONDecodeError as json_e:
            log_error(f"JSON parse error: {json_e}")
            log_debug(f"Raw response: {resp.text}")
            return fallback_message
    
    def _post_process_response(self, answer, user_message, user_lang):
        #Apply post-processing filters to the response
        log_debug(f"Starting post-processing...")
        fallback_message = get_fallback_message(user_lang)
        
        try:
            from rewrite import rewrite_to_compliant
            log_debug(f"Rewrite module available")
        except ImportError:
            log_warning(f"Rewrite module not available")
            def rewrite_to_compliant(a, b, c, d):
                return a
        
        try:
            if contains_forbidden_phrase(answer, user_lang):
                log_debug(f"Forbidden phrase detected, rewriting...")
                rewritten = rewrite_to_compliant(answer, user_message, user_lang, fallback_message)
                if not rewritten or rewritten == answer:
                    log_warning(f"Rewrite failed, using fallback")
                    return fallback_message
                else:
                    log_debug(f"Rewrite successful")
                    return rewritten
            else:
                log_debug(f"No forbidden phrases detected")
                return answer
        except Exception as pp_e:
            log_error(f"Post-processing failed: {pp_e}")
            return answer
    
    def _finalize_chat_history(self, chat_history, processed_answer):
        #Add AI response to chat history and maintain size limit
        chat_history.append({"role": "assistant", "content": processed_answer})
        
        # Keep only the last 5 messages (excluding system prompt)
        system_msgs = [msg for msg in chat_history if msg['role'] == 'system']
        non_system_msgs = [msg for msg in chat_history if msg['role'] != 'system']
        return system_msgs + non_system_msgs[-5:]
    
    def _save_debug_info(self, chat_history, user_message, original_response, processed_response):
        #Save debug information to file
        try:
            with open('last_prompt.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': __import__('datetime').datetime.now().isoformat(),
                    'chat_history': chat_history,
                    'user_message': user_message,
                    'original_ai_response': original_response,
                    'postprocessed_response': processed_response
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_error(f"Failed to save debug info: {e}")


# Create a singleton instance
chat_service = ChatService()
