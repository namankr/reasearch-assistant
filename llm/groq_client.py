from groq import Groq
from config import GROQ_API_KEY

_groq = Groq(api_key=GROQ_API_KEY)

def groq_generate(prompt: str, system: str = "", model: str = "llama-3.3-70b-versatile") -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = _groq.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=2048
    )
    return resp.choices[0].message.content