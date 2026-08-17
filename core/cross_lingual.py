"""Renders a non-English question into English for retrieval only.

The knowledge base is embedded with all-MiniLM-L6-v2, an English-only sentence
encoder, so an Italian or French question is mapped away from the English course
chunks. Nothing errors, because a nearest-neighbour search always returns
neighbours, but the chunks returned are the wrong ones and the confidence band
drops for the wrong reason. Translating the query keeps retrieval on the English
path while the interface and the generated answer stay in the student's language.
"""

from __future__ import annotations

import streamlit as st

from config import GROQ_MODEL
from ui.i18n import LANGUAGES

#the output is a search query, not prose. a low cap also discourages the model from answering the question instead of translating it
_MAX_TOKENS = 120

_TRANSLATION_PROMPT = """Translate the student's question into English.

Rules:
- Output ONLY the English translation. No preamble, no quotation marks, no notes.
- Keep protocol names, acronyms and technical terms exactly as they are
  (ARP, TCP, SYN, DMZ, MAC, DNS, CIA triad, stateful, stateless).
- Preserve the question's meaning precisely. Do not answer it, expand it, or
  add detail that is not there.
- If the question is already in English, repeat it back unchanged.

Question ({language}):
{question}

English translation:"""


@st.cache_data(show_spinner=False, max_entries=256)
def _translate(question: str, language_name: str, model: str) -> str:
    """Translate one question. Cached on the question text.

    Retrieval anchoring re-derives the query on every rerun, so without the cache
    a ten-turn conversation would re-translate every turn. The Groq client is
    built here rather than passed in because an unhashable argument would
    disable caching.
    """
    import os
    from groq import Groq

    client = Groq(api_key=os.environ.get("GROQ_API_KEY", "").strip())
    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": _TRANSLATION_PROMPT.format(
                language=language_name, question=question
            ),
        }],
        max_tokens=_MAX_TOKENS,
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip().strip('"').strip()


def to_english(question: str, lang: str) -> tuple[str, bool]:
    """Return (query_for_retrieval, was_translated).

    English questions return unchanged without an API call. Any failure falls
    back to the original text, since degraded retrieval is recoverable but a
    lost question mid-session is not.
    """
    if lang == "en" or lang not in LANGUAGES:
        return question, False

    stripped = question.strip()
    if not stripped:
        return question, False

    language_name = LANGUAGES[lang]["name_in_english"]

    try:
        english = _translate(stripped, language_name, GROQ_MODEL)
    except Exception:
        return question, False

    if not english:
        return question, False

    #a translation is roughly the length of its source.
    if len(english) > max(240, len(stripped) * 4):
        return question, False

    return english, english.lower() != stripped.lower()
