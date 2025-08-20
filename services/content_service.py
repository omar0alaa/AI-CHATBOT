# Content service - Handles content filtering and rewriting

import re
from .logging_service import log_post_process
from .ai_config import ai_config

# Inappropriate topics that should be immediately rejected
INAPPROPRIATE_TOPICS = {
    'en': [
        'racism', 'hate speech', 'terrorism', 'violence', 'war', 'conflict',
        'suicide', 'self harm', 'drugs', 'illegal activities', 'weapons',
        'adult content', 'sexual content', 'pornography', 'sexuality',
        'politics', 'political', 'government', 'election', 'president',
        'religion', 'religious', 'controversial', 'extremism'
    ],
    'ar': [
        'العنصرية', 'خطاب الكراهية', 'الإرهاب', 'العنف', 'الحرب', 'الصراع',
        'الانتحار', 'إيذاء النفس', 'المخدرات', 'الأنشطة غير القانونية', 'الأسلحة',
        'محتوى للبالغين', 'محتوى جنسي', 'الإباحية', 'الجنسية',
        'السياسة', 'سياسي', 'الحكومة', 'الانتخابات', 'الرئيس',
        'الدين', 'ديني', 'مثير للجدل', 'التطرف',
    ]
}

# Post-processing filter for forbidden phrases
FORBIDDEN_PHRASES = {
    'ar': [
        "الوثيقة",
        "لا يمكنني",
        "بناءً على المعلومات المقدمة",
        "حسب المستندات",
        "في المستندات",
        "هذه الوثائق",
        "الوثيقة المقدمة",
        "النص المقدم",
        "المصدر المقدم",
        "المعلومات المقدمة",
        "تذكر المستندات",
        "وفقاً للسياق",
        "استناداً إلى المعلومات المقدمة",
        "استنادا إلى المعلومات المقدمة",
        "حسب المعلومات المتوفرة",
        "حسب النص المقدم",
        "وفقاً للمستندات",
        "حسب السياق",
        "حسب ما ورد في المستندات",
        "حسب ما هو مذكور في المستندات",
        "حسب ما هو متوفر في المستندات",
        "حسب ما هو متاح في المستندات",
        "حسب ما هو متوفر في المعلومات المقدمة",
        "حسب ما هو متاح في المعلومات المقدمة",
        "حسب ما هو مذكور في المعلومات المقدمة",
        "في المستندات المقدمة",
        "بالمستندات المقدمة",
        "ضمن المستندات المقدمة",
        "من خلال المستندات المقدمة",
        "استناداً للمستندات المقدمة",
        "استنادا للمستندات المقدمة"
    ],
    'en': [
        "i cannot",
        "provided text",
        "provided document",
        "provided context",
        "provided information",
        "The context",
        "the context",
        "The text",
        "the text",
        "The document",
        "the document",
        "according to the provided information",
        "according to the documents",
        "according to the context",
        "based on the provided information",
        "based on the documents",
        "based on the context",
        "according to the given information",
        "according to the available information",
        "according to the provided text",
        "according to the supplied information",
        "according to the supplied documents",
        "according to the supplied context",
        "based on the supplied information",
        "based on the supplied documents",
        "based on the supplied context",
        "according to what is mentioned in the documents",
        "according to what is available in the documents",
        "according to what is available in the provided information",
        "according to what is mentioned in the provided information"
    ]
}

FALLBACK_MESSAGES = {
    'ar': "يمكنك محاولة إعادة صياغة سؤالك أو التواصل مع فريق الدعم الخاص بنا للحصول على مساعدة أكثر تفصيلاً.",
    'en': "You can try rephrasing your question or reach out to our support team for more detailed help."
}

INAPPROPRIATE_RESPONSE = {
    'ar': "أعتذر، لا يمكنني مناقشة هذا الموضوع. يرجى طرح سؤال متعلق بخدماتنا.",
    'en': "I apologize, but I cannot discuss this topic. Please ask a question related to our services."
}


class ContentService:
    #Service class for content filtering and processing
    
    def contains_inappropriate_content(self, message: str, lang: str) -> bool:
        #Check if the user message contains inappropriate content
        inappropriate_topics = INAPPROPRIATE_TOPICS.get(lang, [])
        message_check = message.lower() if lang == 'en' else message.lower()
        
        for topic in inappropriate_topics:
            if topic.lower() in message_check:
                log_post_process(f"CONTENT FILTER - Inappropriate topic detected: {topic}")
                return True
        return False
    
    def get_inappropriate_response(self, lang: str) -> str:
        #Get the appropriate response for inappropriate content
        return INAPPROPRIATE_RESPONSE.get(lang, INAPPROPRIATE_RESPONSE['en'])
    
    def contains_forbidden_phrase(self, answer: str, lang: str) -> bool:
        #Check if answer contains forbidden phrases
        phrases = FORBIDDEN_PHRASES.get(lang, [])
        answer_check = answer.lower() if lang == 'en' else answer
        for phrase in phrases:
            # Only use direct substring match (exact)
            if phrase in answer_check:
                log_post_process(f"FILTER - Matched exact: {phrase}")
                return True
        return False
    
    def get_fallback_message(self, lang: str) -> str:
        #Get fallback message for the specified language
        return FALLBACK_MESSAGES.get(lang, FALLBACK_MESSAGES['en'])
    
    def rewrite_to_compliant(self, answer: str, user_question: str, lang: str, fallback_message: str) -> str:
        #Rewrite answer to be compliant (simplified version without transformers dependency)
        try:
            from transformers import pipeline
            
            # Rewriting model for generating compliant answers
            REWRITE_MODEL = "google/flan-t5-small"
            
            # Load the pipeline
            rewrite_pipe = pipeline("text2text-generation", model=REWRITE_MODEL)
            
            if lang == 'ar':
                prompt = (
                    f"سؤال المستخدم: {user_question}\nالإجابة: {answer}\n"
                    f"إذا كانت الإجابة غير ذات صلة بالسؤال أو لا تحتوي على معلومات حول السؤال، فقط أجب بهذا النص: {fallback_message}\n"
                    "لا تكرر ولا تعيد صياغة سؤال المستخدم في إجابتك ولا تذكره بأي شكل. إذا كانت الإجابة مفيدة ولكنها تذكر أو تلمح إلى المستندات أو السياق أو المعلومات المقدمة، فأعد صياغتها بحيث لا تذكر أو تلمح إلى ذلك واحتفظ بجميع التفاصيل المفيدة. أجب فقط بالإجابة المعدلة دون أي شرح إضافي."
                )
            else:
                prompt = (
                    f"User question: {user_question}\nAI answer: {answer}\n"
                    f"If the answer is not relevant to the question or does not provide information about it, respond only with this text: {fallback_message}\n"
                    "Never repeat or paraphrase the user question in your answer and do not mention it in any way. Otherwise, rewrite the answer so it does not mention or allude to documents, context, or provided information, but keeps all helpful details. Output only the compliant answer."
                )
            result = rewrite_pipe(prompt, 
                                max_new_tokens=ai_config.REWRITE_MAX_TOKENS, 
                                do_sample=ai_config.REWRITE_DO_SAMPLE)
            rewritten = result[0]['generated_text'].strip()
            # If the rewritten answer matches the user question (ignoring case/whitespace), return fallback
            if rewritten.strip().lower() == user_question.strip().lower():
                return fallback_message
            return rewritten
        except ImportError:
            # If transformers is not available, return the original answer
            log_post_process("Transformers not available, skipping rewrite")
            return answer
        except Exception as e:
            log_post_process(f"Rewrite failed: {e}")
            return answer


# Create singleton instance
content_service = ContentService()

# Convenience functions for backward compatibility
def contains_inappropriate_content(message: str, lang: str) -> bool:
    #Check if the user message contains inappropriate content
    return content_service.contains_inappropriate_content(message, lang)

def get_inappropriate_response(lang: str) -> str:
    #Get the appropriate response for inappropriate content
    return content_service.get_inappropriate_response(lang)

def contains_forbidden_phrase(answer: str, lang: str) -> bool:
    #Check if answer contains forbidden phrases
    return content_service.contains_forbidden_phrase(answer, lang)

def get_fallback_message(lang: str) -> str:
    #Get fallback message for the specified language
    return content_service.get_fallback_message(lang)

def rewrite_to_compliant(answer: str, user_question: str, lang: str, fallback_message: str) -> str:
    #Rewrite answer to be compliant
    return content_service.rewrite_to_compliant(answer, user_question, lang, fallback_message)
