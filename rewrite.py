from difflib import SequenceMatcher
from transformers import pipeline

# Rewriting model for generating compliant answers
REWRITE_MODEL = "google/flan-t5-base"

# Load the pipeline once at startup
rewrite_pipe = pipeline("text2text-generation", model=REWRITE_MODEL)

def rewrite_to_compliant(answer: str, user_question: str, lang: str, fallback_message: str) -> str:
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
    result = rewrite_pipe(prompt, max_new_tokens=256, do_sample=False)
    rewritten = result[0]['generated_text'].strip()
    # Normalize for comparison
    rewritten_norm = rewritten.strip().lower()
    question_norm = user_question.strip().lower()
    # If the rewritten answer matches or contains the user question, or is very similar, return fallback
    if (
        rewritten_norm == question_norm
        or question_norm in rewritten_norm
        or rewritten_norm in question_norm
        # if the similarity ratio is n% or more return fallback
        or SequenceMatcher(None, rewritten_norm, question_norm).ratio() > 0.70
    ):
        #Debugging output
        print(f"[REWRITE] Similarity detected, returning fallback message")
        return fallback_message
    return rewritten
