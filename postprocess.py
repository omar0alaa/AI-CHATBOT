import re

#Post-processing filter for forbidden phrases
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

def contains_forbidden_phrase(answer: str, lang: str) -> bool:
    phrases = FORBIDDEN_PHRASES.get(lang, [])
    answer_check = answer.lower() if lang == 'en' else answer
    for phrase in phrases:
        # Only use direct substring match (exact)
        if phrase in answer_check:
            print(f"[FILTER] Matched exact: {phrase}")
            return True
    return False

def get_fallback_message(lang: str) -> str:
    return FALLBACK_MESSAGES.get(lang, FALLBACK_MESSAGES['en'])
