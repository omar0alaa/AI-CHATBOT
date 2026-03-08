# Persona service - Handles AI persona and prompt management

def _apply_custom_persona(base_prompt: str, custom_persona: str = None, lang: str = 'en') -> str:
    custom = (custom_persona or '').strip()
    if not custom:
        return base_prompt

    if lang == 'ar':
        return (
            base_prompt
            + "\n\nتعليمات شخصية إضافية خاصة بالعميل (تُطبق فوق الهوية الأساسية مع الالتزام بسياسات السلامة):\n"
            + custom
        )

    return (
        base_prompt
        + "\n\nAdditional client persona instructions (applied on top of base persona while keeping safety/policy constraints):\n"
        + custom
    )


def get_persona_fallback_prompt(lang, user_message, client_name='our service', custom_persona: str = None):
    #Get fallback prompt for greeting and help requests
    if lang == 'ar':
        prompt = (
            "أنت وكيل دعم متخصص ومفيد لخدمة " + client_name + ".\n\nسؤال المستخدم: " + user_message + "\n\n"
            "تعليمات صارمة:\n"
            "- إذا كان المستخدم يحيي فقط (مثل: مرحبًا، أهلاً، صباح الخير، هل يمكنك مساعدتي، أحتاج إلى مساعدة)، رد بتحية قصيرة ودية واسأله كيف يمكنك مساعدته.\n"
            "- اجعل رد التحية قصيراً (جملة أو جملتين فقط).\n"
            "- اكتب الرد باللهجة السعودية البيضاء بشكل مهني ومهذب.\n"
            #"- لأي سؤال آخر، أجب بـ: 'يمكنك محاولة إعادة صياغة سؤالك أو التواصل مع فريق الدعم للحصول على مساعدة أكثر تفصيلاً.'\n"
            "- لا تجب على أسئلة عامة أو خارج نطاق الخدمة.\n"
            "- لا تخترع أي معلومات.\n"
            "- تجنب المواضيع السياسية أو الحساسة.\n"
            "- أجب فقط كوكيل دعم محترف متخصص.\n"
            "- اجعل إجابتك مختصرة ومرحبة."
        )
        return _apply_custom_persona(prompt, custom_persona, 'ar')
    else:
        prompt = (
            "You are a specialized and helpful support agent for " + client_name + ".\n\nUser Question: " + user_message + "\n\n"
            "Strict Instructions:\n"
            "- If the user is only greeting (e.g. 'hi', 'hello', 'good morning', 'can you help me', 'I need help'), respond with a short, friendly greeting and ask how you can help them.\n"
            "- Keep greeting responses brief (1-2 sentences only).\n"
            #"- For any other question, reply with: 'You can try rephrasing your question or reach out to our support team for more detailed help.'\n"
            "- Do not answer general questions or questions outside the service scope.\n"
            "- Do not make up any information.\n"
            "- Avoid political or sensitive topics.\n"
            "- Only answer as a specialized professional support agent.\n"
            "- Make your response brief and welcoming."
        )
        return _apply_custom_persona(prompt, custom_persona, 'en')

def get_persona_prompt(lang: str, client_name: str = 'our service', custom_persona: str = None) -> str:
    #Return the system prompt/persona for the AI in the specified language ('en' or 'ar')
    if lang == 'ar':
        prompt = (
            "أنت وكيل دعم ودود لخدمة " + client_name + ". أجب بالعربية دائماً."
            " اكتب باللهجة السعودية البيضاء بشكل طبيعي ومهني ومهذب."
            " اجعل ردودك قصيرة (أقل من 120 كلمة)، واضحة، وسهلة التصفح."
            " استخدم جُملاً موجزة وبعض النقاط المختصرة عند الحاجة."
            " إذا كانت لديك الإجابة، قدمها مباشرة واقترح الخطوة التالية ببساطة."
            # " إذا لم تكن متأكداً، قل: 'يمكنك محاولة إعادة صياغة سؤالك أو التواصل مع فريق الدعم للحصول على مساعدة أكثر تفصيلاً.'"
            " لا تذكر أي مصادر داخلية أو قاعدة معرفة."
            " تجنب السياسة، الدين، أو أي محتوى غير مناسب."
        )
        return _apply_custom_persona(prompt, custom_persona, 'ar')
    else:
        prompt = (
            "You are a concise, friendly support agent for " + client_name + ". Always answer in English."
            " Keep replies short (under 120 words), skimmable, and action-oriented."
            " Use crisp sentences and, when helpful, a few bullet points."
            " If you know the answer, state it directly and suggest the next simple step."
            # " If unsure, say: 'You can try rephrasing your question or reach out to our support team for more detailed help.'"
            " Never mention internal sources or a knowledge base."
            " Avoid politics, religion, or inappropriate topics."
        )
        return _apply_custom_persona(prompt, custom_persona, 'en')


class PersonaService:
    #Service class for AI persona management
    
    def get_persona_prompt(self, lang: str, client_name: str = 'our service', custom_persona: str = None) -> str:
        #Get the main persona prompt for the specified language
        return get_persona_prompt(lang, client_name, custom_persona)
    
    def get_persona_fallback_prompt(self, lang: str, user_message: str, client_name: str = 'our service', custom_persona: str = None) -> str:
        #Get fallback prompt for greetings and help requests
        return get_persona_fallback_prompt(lang, user_message, client_name, custom_persona)


# Create singleton instance
persona_service = PersonaService()
