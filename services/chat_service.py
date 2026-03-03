# Chat service - Handles all chat-related business logic

import time
import json
import requests
from langdetect import detect
from .persona_service import get_persona_prompt, get_persona_fallback_prompt
from .content_service import contains_forbidden_phrase, get_fallback_message, contains_inappropriate_content, get_inappropriate_response
from .logging_service import log_debug, log_info, log_warning, log_error
from .database_service import get_answer_from_db
from .ai_config import ai_config


class ChatService:
    #Service class for handling chat operations    
    def __init__(self):
        self.api_url = ai_config.GROQ_API_URL
        self.model_name = ai_config.GROQ_MODEL
        self.api_key = ai_config.GROQ_API_KEY
    
    def process_message(self, user_message, ui_lang, chat_history, client_id='youlearnt'):
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
        contexts = self._get_knowledge_context(user_message, user_lang, client_id)
        
        # Generate AI response
        answer = self._generate_ai_response(user_message, user_lang, contexts, updated_history)
        
        # Post-process the response
        processed_answer = self._post_process_response(answer, user_message, user_lang)
        
        # Update chat history with response
        final_history = self._finalize_chat_history(updated_history, processed_answer)
        
        # Save debug information
        self._save_debug_info(final_history, user_message, answer, processed_answer)
        
        log_debug(f"Final answer: {len(processed_answer)} characters")
        return processed_answer, final_history

    def summarize_message(self, text, ui_lang=None):
        #Generate a concise summary for provided text
        if not text or not text.strip():
            return ""

        user_lang = self._detect_language(text, ui_lang)
        if user_lang == 'ar':
            prompt = (
                "لخّص النص التالي في 3-5 نقاط قصيرة وواضحة. "
                "لا تضف معلومات غير موجودة في النص:\n\n"
                f"{text}"
            )
            fallback_message = "تعذر إنشاء ملخص في الوقت الحالي."
        else:
            prompt = (
                "Summarize the following text in 3-5 short clear bullet points. "
                "Do not add facts not present in the text:\n\n"
                f"{text}"
            )
            fallback_message = "Unable to generate summary right now."

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a concise summarization assistant."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": min(max(ai_config.GROQ_MAX_TOKENS, 200), 500),
            "temperature": 0.3,
            "top_p": 0.9,
            "stream": False,
        }

        return self._make_groq_request(payload, fallback_message)
    
    def _detect_language(self, user_message, ui_lang):
        #Detect user message language
        # if ui_lang == 'ar':
        #     return 'ar'
        # elif ui_lang == 'en':
        #     return 'en'
        # else:
            try:
                user_lang = detect(user_message)
                log_debug(f"Auto-detected language: {user_lang}")
                return user_lang
            except Exception as e:
                log_error(f"Language detection failed: {e}")
                return ai_config.DEFAULT_LANGUAGE
    
    def _update_chat_history(self, chat_history, user_message, user_lang):
        #Update chat history with system prompt and user message
        lang_instruction = get_persona_prompt(user_lang)
        
        # Remove old system prompts and add new one
        history = [msg for msg in chat_history if msg['role'] != 'system']
        history.insert(0, {"role": "system", "content": lang_instruction})
        history.append({"role": "user", "content": user_message})
        
        return history
    
    def _get_knowledge_context(self, user_message, user_lang, client_id='youlearnt'):
        #Retrieve relevant context from knowledge base
        try:
            contexts = get_answer_from_db(user_message, user_lang, client_id)
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
    
    def _get_conversation_context(self, chat_history):
        #Extract relevant conversation context from chat history
        try:
            # Get last few AI responses for context (excluding system messages)
            ai_responses = []
            for msg in reversed(chat_history):
                if msg['role'] == 'assistant':
                    ai_responses.append(msg['content'])
                if len(ai_responses) >= ai_config.MAX_CONVERSATION_CONTEXT:  # Configurable number of AI responses
                    break
            
            if ai_responses:
                # Reverse to get chronological order
                ai_responses.reverse()
                context = " | ".join(ai_responses)
                log_debug(f"Conversation context: {context[:100]}...")
                return context
            else:
                log_debug("No conversation context found")
                return ""
        except Exception as e:
            log_error(f"Failed to extract conversation context: {e}")
            return ""
    
    def _is_follow_up_question(self, user_message, user_lang):
        #Check if the user message is a follow-up question about previous conversation
        if user_lang == 'ar':
            follow_up_indicators = [
                'ماذا قلت', 'ما قلته', 'رسالتك الأخيرة', 'إجابتك الأخيرة',
                'ذكرت أن', 'قلت إن', 'أخبرتني', 'الشيء الذي ذكرته',
                'ما تحدثنا عنه', 'عما قلته', 'حول ما ذكرت', 'بخصوص ما قلت',
                'المزيد عن', 'تفاصيل أكثر', 'اشرح لي أكثر'
            ]
        else:
            follow_up_indicators = [
                'what did you say', 'what you said', 'your last message', 'your previous response',
                'you mentioned', 'you said that', 'you told me', 'what you mentioned',
                'what we discussed', 'about what you said', 'regarding what you mentioned',
                'more about', 'tell me more', 'explain more', 'elaborate on',
                'your answer', 'your response', 'you just said', 'that you mentioned'
            ]
        
        user_lower = user_message.lower().strip()
        return any(indicator in user_lower for indicator in follow_up_indicators)
    
    def _is_general_business_question(self, user_message, user_lang):
        #Check if the user message is a general business/service question
        if user_lang == 'ar':
            business_keywords = [
                'خدمة', 'خدمات', 'منتج', 'منتجات', 'سعر', 'أسعار', 'تكلفة',
                'كيف', 'ماذا', 'متى', 'أين', 'لماذا', 'من',
                'سياسة', 'خصوصية', 'دعم', 'مساعدة', 'تواصل',
                'اشتراك', 'تسجيل', 'حساب', 'ملف', 'معلومات'
            ]
        else:
            business_keywords = [
                'service', 'services', 'product', 'products', 'price', 'pricing', 'cost',
                'how', 'what', 'when', 'where', 'why', 'who', 'can', 'do', 'does',
                'policy', 'privacy', 'support', 'help', 'contact', 'terms',
                'subscription', 'signup', 'account', 'profile', 'information',
                'features', 'benefits', 'plans', 'options', 'details',
                'about', 'learn', 'youlearnt', 'youlearn', 'company', 'business',
                'link', 'links', 'website', 'email', 'phone', 'address'
            ]
        
        user_lower = user_message.lower().strip()
        # If message contains business keywords and isn't too short, consider it a business question
        has_keywords = any(keyword in user_lower for keyword in business_keywords)
        is_reasonable_length = len(user_message.strip()) >= 3
        
        # Add debug logging to see what's happening
        log_debug(f"Business question check: '{user_message}' -> keywords: {has_keywords}, length: {is_reasonable_length}")
        
        return has_keywords and is_reasonable_length
    
    def _generate_ai_response(self, user_message, user_lang, contexts, chat_history):
        #Generate AI response using Groq
        log_debug(f"Groq URL: {self.api_url}")
        log_debug(f"Model: {self.model_name}")
        
        fallback_message = get_fallback_message(user_lang)
        lang_instruction = get_persona_prompt(user_lang)
        
        # Check if it's a simple greeting
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'مرحبا', 'أهلا', 'السلام عليكم', 'صباح الخير', 'هلا','مساء الخير']
        help_requests = ['help', 'help me', 'can you help', 'i need help', 'مساعدة', 'هل يمكنك مساعدتي', 'أحتاج مساعدة', 'ساعدني', 'ساعدنى']
        
        user_lower = user_message.lower().strip()
        is_greeting = any(greeting in user_lower for greeting in greetings)
        is_help_request = any(help_req in user_lower for help_req in help_requests)
        
        # Get conversation context from chat history
        conversation_context = self._get_conversation_context(chat_history)
        
        # Get AI restrictiveness setting
        restrictiveness = ai_config.get_restrictiveness()
        log_debug(f"Current restrictiveness level: {restrictiveness}")
        
        # Build prompt based on context availability and restrictiveness
        if not contexts:
            if is_greeting or is_help_request:
                log_debug("Processing greeting/help request with fallback prompt")
                prompt = get_persona_fallback_prompt(user_lang, user_message)
            elif conversation_context and self._is_follow_up_question(user_message, user_lang):
                log_debug("Processing follow-up question about previous conversation")
                # Allow follow-up questions about previous responses
                context_str = f"- Previous conversation: {conversation_context}"
                prompt = f"{lang_instruction}\n\nAvailable Information:\n{context_str}\n\nUser Question: {user_message}\n\nIMPORTANT: Answer based on our previous conversation if the question relates to it. For general business questions, provide helpful responses. If you cannot answer, respond with: 'You can try rephrasing your question or reach out to our support team for more detailed help.'"
            elif self._is_general_business_question(user_message, user_lang) and restrictiveness in ['balanced', 'open']:
                log_debug("Processing general business question - allowing AI to respond")
                # Allow general business-related questions in balanced or open mode
                prompt = f"{lang_instruction}\n\nUser Question: {user_message}\n\nIMPORTANT: This appears to be a general business question. Provide a helpful, professional response. If you cannot provide a good answer, say: 'You can try rephrasing your question or reach out to our support team for more detailed help.'"
            elif restrictiveness == 'open':
                log_debug("open mode - allowing AI to attempt any appropriate question")
                # In open mode, try to answer any appropriate question
                prompt = f"{lang_instruction}\n\nUser Question: {user_message}\n\nIMPORTANT: Provide a helpful response to this question. Be professional and informative. If you cannot provide a good answer, say: 'You can try rephrasing your question or reach out to our support team for more detailed help.'"
            else:
                log_debug(f"No context found and restrictiveness is {restrictiveness} - returning fallback message")
                return fallback_message
        else:
            log_debug(f"Using knowledge base prompt with {len(contexts)} contexts")
            
            # Include both knowledge base and conversation context
            all_context = []
            all_context.extend([f"Knowledge: {c}" for c in contexts])
            if conversation_context:
                all_context.append(f"Previous conversation: {conversation_context}")
            
            context_str = "\n".join([f"- {c}" for c in all_context])
            prompt = f"{lang_instruction}\n\nAvailable Information:\n{context_str}\n\nUser Question: {user_message}\n\nIMPORTANT: Answer based on the available information above. You can reference previous parts of our conversation if the question relates to something we discussed. Provide detailed and helpful responses."
        
        # Build OpenAI-compatible message payload for Groq
        messages = [
            {"role": "system", "content": lang_instruction},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": ai_config.GROQ_MAX_TOKENS,
            "temperature": ai_config.GROQ_TEMPERATURE,
            "top_p": ai_config.GROQ_TOP_P,
            "stream": ai_config.GROQ_STREAM,
        }
        
        log_debug(f"Sending request to Groq at {self.api_url}...")
        log_debug(f"Prompt length: {len(prompt)} characters")
        
        try:
            return self._make_groq_request(payload, fallback_message)
        except Exception as e:
            log_error(f"AI generation failed: {e}")
            return fallback_message
    
    def _make_groq_request(self, payload, fallback_message):
        #Make request to Groq API
        start_time = time.time()

        if not self.api_key:
            raise Exception("Missing GROQ_API_KEY environment variable")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=ai_config.GROQ_REQUEST_TIMEOUT,
        )
        end_time = time.time()
        
        log_debug(f"Response time: {end_time - start_time:.2f} seconds")
        log_debug(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log_error(f"Groq error {resp.status_code}: {resp.text}")
            return fallback_message
        
        try:
            result = resp.json()
            log_debug(f"Response keys: {list(result.keys())}")

            choices = result.get("choices", [])
            if not choices:
                log_error("Empty response from Groq (no choices)")
                return fallback_message

            message = choices[0].get("message", {})
            raw_response = message.get("content", "")

            if not raw_response or raw_response.strip() == "":
                log_error("Empty response content from Groq")
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
            from .content_service import rewrite_to_compliant
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
        
        # Keep only the last configured exchanges (user + assistant messages, excluding system prompt)
        system_msgs = [msg for msg in chat_history if msg['role'] == 'system']
        non_system_msgs = [msg for msg in chat_history if msg['role'] != 'system']
        
        # Keep last N messages (N exchanges) or all if less than N
        max_messages = ai_config.get_max_history_messages()
        if len(non_system_msgs) > max_messages:
            non_system_msgs = non_system_msgs[-max_messages:]
        
        return system_msgs + non_system_msgs
    
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
