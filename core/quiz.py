'''this .py holds the on demand quiz, the part of the system a student starts themselves rather than one that fires at them

- the questions generated from the knowledge base rather than hand written. nine hand written items cannot cover thirteen topics at three 
difficulties up to twenty questions, and a fixed bank would be exhausted after two sittings, which defeats the point of repeat practice

-generation is grounded exactly the way answers are. chunks are retrieved for the chosen topics, the model is told to write items answerable from those
chunks alone

-exam mode and practice mode:
practice mode can reveal the answer immediately after each item, which is the corrective feedback Carpenter et al. identify as the thing that converts a
retrieval attempt into learning. exam mode withholds it until the end and runs a timer at one minute per question, which is roughly the pace of the module's
own multiple choice assessments. immediate reveal is deliberately unavailable in exam mode, since an exam that tells you the answer as you go is not an exam
'''

from __future__ import annotations

import json
import random
import re
import secrets
import time
from datetime import datetime

from config import GROQ_MODEL
from core.generate_answer import retrieve_context

#one minute per question, matching the pace of the module's own MCQ papers
SECONDS_PER_QUESTION = 60

MIN_QUESTIONS = 1
MAX_QUESTIONS = 20
DEFAULT_QUESTIONS = 5

DIFFICULTIES = ("easy", "medium", "hard")
MODES = ("practice", "exam")

#how many chunks to pull per selected topic. enough that the model has room to write distinct questions without the same passage producing near duplicates
CHUNKS_PER_TOPIC = 4

#request sizing, and the reason it matters
MAX_CHUNK_CHARS = 1000
MAX_CONTEXT_CHUNKS = 8
BATCH_SIZE = 5

#a rate limited request is retried rather than abandoned, matching the exponential backoff already used by gold_set_eval.py
MAX_RETRIES = 3
BACKOFF_BASE = 4.0
PAUSE_BETWEEN_BATCHES = 1.5

class QuizGenerationError(RuntimeError):
    """
    Raised when a quiz cannot be produced, carrying a reason worth showing.

    The first version returned an empty list on every failure, so a rate limit,
    a missing API key and a malformed reply were indistinguishable to the
    student and to whoever had to debug it. The reason is classified here and
    surfaced by the interface.
    """

#topic catalogue
QUIZ_TOPICS: dict[str, dict] = {
    "foundations": {
        "week": 1,
        "terms": "CIA triad confidentiality integrity availability security "
                 "services authentication non-repudiation threat vulnerability",
    },
    "network_attacks": {
        "week": 1,
        "terms": "network attack categories active passive attacks network "
                 "structure topology",
    },
    "physical_layer": {
        "week": 2,
        "terms": "attacking the physical network layer cabling physical "
                 "interception",
    },
    "interception": {
        "week": 2,
        "terms": "data interception packet sniffing promiscuous mode network "
                 "commands",
    },
    "arp": {
        "week": 3,
        "terms": "ARP protocol ARP spoofing ARP cache poisoning gratuitous "
                 "ARP address resolution",
    },
    "dhcp": {
        "week": 3,
        "terms": "DHCP protocol DHCP attacks rogue DHCP server starvation "
                 "lease",
    },
    "dos": {
        "week": 3,
        "terms": "denial of service TCP SYN flooding half-open connections "
                 "amplification attack",
    },
    "bgp": {
        "week": 4,
        "terms": "BGP protocol BGP hijacking autonomous system routing "
                 "advertisement",
    },
    "dns": {
        "week": 4,
        "terms": "DNS name resolution DNS cache poisoning resolver",
    },
    "session_hijacking": {
        "week": 4,
        "terms": "TCP session hijacking sequence number prediction Cain and "
                 "Abel",
    },
    "firewall_types": {
        "week": 5,
        "terms": "types of firewalls firewall topologies DMZ bastion host "
                 "proxy",
    },
    "packet_filter": {
        "week": 5,
        "terms": "packet filter firewall rules default deny iptables rule "
                 "ordering",
    },
    "stateful": {
        "week": 5,
        "terms": "stateful firewall state table connection tracking "
                 "established sessions ephemeral ports",
    },
}

#what each difficulty asks of the student.
DIFFICULTY_BRIEF = {
    "easy": "Recall and recognition. The student should be able to answer "
            "from a single definition or a single stated fact in the "
            "material. Distractors should be clearly wrong to someone who "
            "has read the topic.",
    "medium": "Application and comparison. The student must connect two "
              "facts, distinguish two similar mechanisms, or apply a "
              "definition to a described situation. Distractors should be "
              "plausible to someone with partial understanding.",
    "hard": "Analysis and reasoning. The student must reason about why a "
            "mechanism behaves as it does, work out the consequence of a "
            "change, or identify which of several defensible-sounding "
            "statements is actually correct. Distractors should each be "
            "wrong for a specific, identifiable reason.",
}

OPTION_LABELS = ("A", "B", "C", "D")


def topic_week(key: str) -> int:
    return QUIZ_TOPICS.get(key, {}).get("week", 0)

def all_topic_keys() -> list[str]:
    """Topic keys in week order, which is the order they are taught in."""
    return sorted(QUIZ_TOPICS, key=lambda k: (QUIZ_TOPICS[k]["week"], k))


def estimated_seconds(count: int) -> int:
    return count * SECONDS_PER_QUESTION


#generation 

_PROMPT = """You are setting a multiple choice test for postgraduate students on a Network Security module.

Write exactly {count} multiple choice questions at the "{difficulty}" level.

Difficulty definition:
{brief}

Rules:
- Every question must be answerable from the COURSE MATERIAL below. Do not use outside knowledge.
- Exactly four options per question, labelled A, B, C and D.
- Exactly one option is correct. The other three must be wrong, not merely less good.
- Vary which label is correct across the set. Do not make A correct every time.
- Do not write "all of the above", "none of the above", or "both A and B".
- Each question must stand alone. Do not refer to "the passage", "the text" or "the source".
- Give a one or two sentence explanation of why the correct option is correct.
- Set "week" to the week number shown on the source you used.
- Do not repeat a question you have already written in this set.

COURSE MATERIAL:
{context}

Return ONLY a JSON object of this exact shape, with no commentary:
{{"questions": [
  {{"question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "answer": "B",
    "explanation": "...",
    "week": 3}}
]}}"""


def _gather_context(collection, topic_keys: list[str],
                    limit: int = MAX_CONTEXT_CHUNKS) -> str:
    """
    Retrieve chunks for the selected topics and render them for the prompt.

    Chunks are pulled per topic rather than as one big query so that a quiz spanning several topics is not dominated by whichever topic happens to sit
    closest to the combined query vector. Two bounds are applied, both of which exist because of the rate limit noted
    at the top of this module. Each chunk is truncated, since a question only needs the passage's substance and
    not its last paragraph, and the number of chunks is capped. The pool is shuffled before the cap so that repeated
    quizzes draw on different passages and therefore produce different questions, which is the whole point of a quiz you can retake.
    """
    blocks: list[str] = []
    seen: set[str] = set()

    for key in topic_keys:
        spec = QUIZ_TOPICS.get(key)
        if not spec:
            continue
        try:
            chunks = retrieve_context(collection, spec["terms"],
                                      top_k=CHUNKS_PER_TOPIC)
        except Exception:
            continue
        for chunk in chunks:
            text = chunk["text"].strip()
            fingerprint = text[:120]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            if len(text) > MAX_CHUNK_CHARS:
                #cut at a sentence end where one is close by, so the passage does not stop mid-clause and invite a question about a half-stated fact
                cut = text.rfind(". ", 0, MAX_CHUNK_CHARS)
                text = text[:cut + 1] if cut > MAX_CHUNK_CHARS * 0.6 \
                    else text[:MAX_CHUNK_CHARS]
            meta = chunk["metadata"]
            blocks.append(
                f"[Week {meta.get('week')} | {meta.get('topic_label')}]\n{text}"
            )

    random.shuffle(blocks)
    return "\n\n".join(blocks[:limit])


def _parse(raw: str) -> list[dict]:
    """
    Pull the question list out of the model response.

    Tolerant by design. The model is asked for a bare JSON object but will sometimes wrap it in a fenced code block or prepend a sentence, and losing
    a whole generated quiz to a stray backtick would be a poor trade.
    """
    text = (raw or "").strip()

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()

    def unwrap(payload):
        #the prompt asks for {"questions": [...]}, but a bare array is a common and perfectly usable variation, so both shapes are accepted
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("questions", "items", "quiz"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    #the whole response first, since that is what a well behaved reply is
    try:
        return unwrap(json.loads(text))
    except json.JSONDecodeError:
        pass

    #otherwise carve out the outermost object or array and retry, which recovers a reply carrying a sentence of preamble
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start == -1 or end == -1 or end < start:
            continue
        try:
            return unwrap(json.loads(text[start:end + 1]))
        except json.JSONDecodeError:
            continue

    return []


def validate_questions(items: list[dict]) -> list[dict]:
    """
    Keep only structurally sound items.

    This checks shape, not pedagogy: four distinct options, an answer label
    that names one of them, and non-empty text. An item that is ambiguous or
    has two defensible answers passes this and is caught only by a human, which
    is the limitation recorded in the module docstring.
    """
    clean: list[dict] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        question = str(item.get("question", "")).strip()
        options = item.get("options")
        answer = str(item.get("answer", "")).strip().upper()[:1]
        explanation = str(item.get("explanation", "")).strip()

        if not question or not isinstance(options, dict) or not explanation:
            continue
        if set(options) != set(OPTION_LABELS):
            continue
        values = [str(v).strip() for v in options.values()]
        if any(not v for v in values):
            continue
        if len({v.lower() for v in values}) != len(values):
            continue          #duplicated option text makes the item unanswerable
        if answer not in OPTION_LABELS:
            continue

        week = item.get("week")
        try:
            week = int(week)
        except (TypeError, ValueError):
            week = None

        clean.append({
            "question": question,
            "options": {label: str(options[label]).strip()
                        for label in OPTION_LABELS},
            "answer": answer,
            "explanation": explanation,
            "week": week,
        })

    return clean



def _classify(error: Exception) -> str:
    """
    Turn a client exception into a reason a student can act on.
    The status code is read from whatever the client exposes, since the Groq SDK does not guarantee a single attribute across
    versions, and the string
    form is checked as a fallback.
    """
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    text = str(error).lower()

    if status == 429 or "rate limit" in text or "429" in text:
        return "rate_limit"
    if status in (401, 403) or "api key" in text or "unauthor" in text:
        return "auth"
    if status == 404 or "model" in text and "not found" in text:
        return "model"
    if "context" in text and ("length" in text or "window" in text):
        return "too_long"
    return "unknown"


def _request_batch(groq_client, prompt: str, max_tokens: int) -> str:
    """
    One generation request, retried with backoff on a rate limit.

    JSON mode is attempted first and a plain call is used if the deployment
    rejects the response_format argument, which not every model supports.
    """
    last: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        for json_mode in (True, False):
            kwargs = {
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.4,   #variety between sittings, not chaos
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                response = groq_client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as error:      # noqa: BLE001 - reclassified below
                last = error
                reason = _classify(error)
                if reason == "rate_limit":
                    break               #retrying without JSON mode will not help
                if json_mode:
                    continue            #fall through to the plain call
                break

        if _classify(last) == "rate_limit" and attempt < MAX_RETRIES:
            time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
            continue
        break

    raise QuizGenerationError(_classify(last) if last else "unknown") from last


def generate_quiz(groq_client, collection, topic_keys: list[str],
                  difficulty: str, count: int,
                  language_clause: str = "",
                  progress=None) -> list[dict]:
    """
    Build a quiz. Returns the validated question list, which may be shorter than count if the model produced items that failed validation.

    Raises QuizGenerationError with a classified reason if nothing could be
    generated at all.
    Long quizzes are produced in batches of BATCH_SIZE rather than in one request.
    Asking for twenty questions in a single call meant a prompt large enough to be rejected outright by the free tier
    and it also produced noticeably repetitive items towards the end of the set.
    Each batch draws a freshly shuffled context, so the later questions are not written from the same passages as the earlier ones.

    Progress, if given, is called with (questions_so_far, target) so theinterface can show movement during what is otherwise a long silence."""
    topic_keys = [k for k in topic_keys if k in QUIZ_TOPICS] or all_topic_keys()
    count = max(MIN_QUESTIONS, min(MAX_QUESTIONS, int(count)))
    difficulty = difficulty if difficulty in DIFFICULTIES else "medium"

    collected: list[dict] = []
    failure: QuizGenerationError | None = None
    remaining = count
    batch_number = 0

    while remaining > 0:
        batch_number += 1
        batch = min(BATCH_SIZE, remaining)

        context = _gather_context(collection, topic_keys)
        if not context:
            raise QuizGenerationError("no_context")

        prompt = _PROMPT.format(
            count=batch,
            difficulty=difficulty,
            brief=DIFFICULTY_BRIEF[difficulty],
            context=context,
        ) + language_clause

        #roughly 220 tokens per item plus headroom for the JSON envelope
        max_tokens = 300 + batch * 260

        try:
            raw = _request_batch(groq_client, prompt, max_tokens)
        except QuizGenerationError as error:
            failure = error
            break

        fresh = validate_questions(_parse(raw))

        #a batch can legitimately repeat an earlier question, since each batch is written without sight of the previous one
        seen = {q["question"].strip().lower() for q in collected}
        for item in fresh:
            key = item["question"].strip().lower()
            if key not in seen:
                seen.add(key)
                collected.append(item)

        if progress:
            progress(len(collected), count)

        remaining = count - len(collected)

        #a batch that returned nothing usable will not do better on a retry with the same settings, so the loop stops rather than spinning
        if not fresh:
            break

        if remaining > 0:
            time.sleep(PAUSE_BETWEEN_BATCHES)

    if not collected:
        raise failure or QuizGenerationError("no_valid_questions")

    return collected[:count]


#Scoring


def score_quiz(questions: list[dict], answers: dict[int, str]) -> dict:
    """
    Score a completed attempt.
    An unanswered question counts as incorrect rather than being dropped, so the denominator stays equal to the number of questions set.
    A student whoruns out of time in exam mode is scored on the whole paper, which is how the module's own assessments work.
    """
    review = []
    correct = 0

    for index, question in enumerate(questions):
        chosen = answers.get(index)
        is_correct = chosen == question["answer"]
        correct += int(is_correct)
        review.append({
            "number": index + 1,
            "question": question["question"],
            "options": question["options"],
            "chosen": chosen,
            "chosen_text": question["options"].get(chosen) if chosen else None,
            "answer": question["answer"],
            "answer_text": question["options"][question["answer"]],
            "explanation": question["explanation"],
            "week": question.get("week"),
            "correct": is_correct,
        })

    total = len(questions)
    return {
        "score": correct,
        "total": total,
        "percentage": round(100 * correct / total, 1) if total else 0.0,
        "review": review,
    }

#attempt history, held in the session and never written to disk. one shared file would show every participant everyone else's attempts and would break the
#claim that the app retains nothing about anyone

_HISTORY_KEY = "quiz_history"




def _history() -> list[dict]:
    """the attempt list for this session, created on first use. streamlit is imported in here rather than at the top so the unit tests can import this
    module with no session context"""
    import streamlit as st

    if _HISTORY_KEY not in st.session_state:
        st.session_state[_HISTORY_KEY] = []
    return st.session_state[_HISTORY_KEY]


def record_attempt(result: dict, config: dict, language: str) -> bool:
    """Record one completed attempt, with its questions, so it can be reopened"""
    record = {
        #a random identifier rather than the timestamp alone, because two attempts finishing in the same second would otherwise collide and the
        #interface keys its review buttons on this
        "id": secrets.token_hex(4),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "score": result.get("score"),
        "total": result.get("total"),
        "percentage": result.get("percentage"),
        "difficulty": config.get("difficulty"),
        "mode": config.get("mode"),
        "topics": config.get("topics", []),
        "language": language,
        "review": result.get("review", []),
    }
    try:
        _history().append(record)
        return True
    except Exception:
        #a history that cannot be recorded must not cost the student the result they have just earned, so this is swallowed rather than raised
        return False

def load_history(limit: int | None = None) -> list[dict]:
    """Most recent attempt first"""
    try:
        rows = list(reversed(_history()))
    except Exception:
        return []
    return rows[:limit] if limit else rows



def history_summary(rows: list[dict]) -> dict:
    """Attempts, mean percentage and best percentage over the given rows."""
    scored = [r for r in rows if isinstance(r.get("percentage"), (int, float))]
    if not scored:
        return {"attempts": len(rows), "average": 0.0, "best": 0.0}
    percentages = [float(r["percentage"]) for r in scored]
    return {
        "attempts": len(rows),
        "average": round(sum(percentages) / len(percentages), 1),
        "best": round(max(percentages), 1),
    }

def clear_history() -> bool:
    """Discard this session's attempts, affects no other session"""
    try:
        _history().clear()
        return True
    except Exception:
        return False


def band_for_percentage(percentage: float) -> str:
    """
    Map a percentage to one of the interface's three bands, so the result chip
    reuses the same colour, marker and meter encoding as everything else rather
    than introducing a fourth visual language for the same idea.
    """
    if percentage >= 80:
        return "High"
    if percentage >= 50:
        return "Medium"
    return "Low"
