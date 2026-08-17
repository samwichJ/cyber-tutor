"""Retrieval and generation stage of the pipeline
For a student question this module:
  1.retrieves the top-k most similar chunks from the ChromaDB store
  2.derives Signal 1, a High/Medium/Low band, from their mean cosine distance
  3.builds a prompt restricting the model to those chunks and calls the model named in config.GROQ_MODEL
  4.reads Signal 2, a 1 to 3 self-verification score, off the last line of the same response
  5. combines both signals into one band and returns the answer with its sources

Can also be run directly:
    py -m core.generate_answer
    py -m core.generate_answer "What is ARP spoofing?"

IMPORTANT Needs GROQ_API_KEY set in the environment. A free key is available from https://console.groq.com/keys
"""

import os
import sys
import re
import time

from groq import Groq
import chromadb

from config import (VECTOR_STORE_DIR, COLLECTION_NAME, GROQ_MODEL,
                    RETRIEVAL_TOP_K, CONF_HIGH_THRESHOLD, CONF_MEDIUM_THRESHOLD)
from core.prerequisite_check import check_prerequisite


#raised from 550 after the gpt-oss-20b run truncated nine answers mid-sentence. the longest complete answer in that run was about 1,750 characters
MAX_ANSWER_TOKENS = 1200

#span Weeks 1, 3 and 5 so a passing run shows retrieval discriminates across the whole knowledge base rather than clustering on one week
DEFAULT_QUESTIONS = [
    "What is the CIA triad in network security?",
    "What is ARP spoofing and how does it work?",
    "What is the difference between a stateful and stateless firewall?",
]


def get_collection():
    """connect to the existing persistent ChromaDB collection"""
    if not os.path.isdir(VECTOR_STORE_DIR):
        sys.exit(
            f"\n[ERROR] ChromaDB store not found at:\n  {VECTOR_STORE_DIR}\n"
            "Run build_chromadb.py first.\n"
        )
    client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)
    return client.get_collection(COLLECTION_NAME)


def retrieve_context(collection, question: str, top_k: int = RETRIEVAL_TOP_K) -> list[dict]:
    """Retrieve the top-k most relevant chunks for a question.

    The distance of each chunk is kept rather than discarded after ranking,
    because it is the input to confidence_band() below.
    """
    results = collection.query(
        query_texts=[question],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    retrieved = []
    for text, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        retrieved.append({"text": text, "metadata": meta, "distance": distance})
    return retrieved



def confidence_band(retrieved_chunks: list[dict]) -> str:
    """Signal 1: a High/Medium/Low band from the mean cosine distance.

    A lower mean distance is a stronger semantic match. The thresholds are in
    config.py and were set against the distance distribution of the current
    knowledge base, so they need rechecking if the corpus is rebuilt.
    """
    if not retrieved_chunks:
        return "Low"
    mean_dist = sum(c["distance"] for c in retrieved_chunks) / len(retrieved_chunks)
    if mean_dist < CONF_HIGH_THRESHOLD:
        return "High"
    elif mean_dist < CONF_MEDIUM_THRESHOLD:
        return "Medium"
    else:
        return "Low"


def self_verify(client, answer: str, retrieved_chunks: list[dict]) -> int:
    """
    ask the model to rate how well its own answer is supported by the retrieved
    sources, in a separate API call. Returns 3, 2 or 1.

    Not used by the live pipeline. generate_answer() asks for the same rating on
    a final CONFIDENCE line of the answer instead, which removes one round trip
    per question. This version is kept as the two-call implementation the latency
    comparison was measured against, and as a fallback if the inline line proves
    unreliable.

    Scoring:
        3 = well supported, all key claims are directly in the sources
        2 = partially supported, some claims go beyond them
        1 = poorly supported, the answer leans on outside knowledge

    Returns 2 on unexpected output, so a parsing failure lowers confidence
    rather than inflating it.
    """
    context_block = "\n\n".join(
        f"[Source {i} | Week {c['metadata']['week']} | "
        f"{c['metadata']['topic_label']}]\n{c['text']}"
        for i, c in enumerate(retrieved_chunks, start=1)
    )

    verify_prompt = f"""You generated the answer below using only the course sources provided.
Rate how well the answer is supported by those sources.

Scoring:
3 = Well supported, all key claims are directly present in the sources
2 = Partially supported, most claims are backed but some go beyond the sources
1 = Poorly supported, the answer relies significantly on outside knowledge

Reply with ONLY the number 1, 2 or 3. No explanation, no other text.

SOURCES:
{context_block}

ANSWER:
{answer}

RATING:"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": verify_prompt}],
            max_tokens=5
        )

        score = int(response.choices[0].message.content.strip()[0])
        if score in (1, 2, 3):
            return score
        return 2  #fallback if out of range
    except Exception:
        return 2  #fallback on any parsing or API error

def compound_confidence(retrieval_band: str, verify_score: int) -> str:
    """Combine Signal 1 and Signal 2 into the band shown to the student.

    Takes the more conservative of the two, so both must be strong for a High
    band and either alone can lower it.

        High -> 3, Medium -> 2, Low -> 1
        combined = min(retrieval band, verify score)
    """
    band_to_int = {"High": 3, "Medium": 2, "Low": 1}
    int_to_band = {3: "High", 2: "Medium", 1: "Low"}
    combined = min(band_to_int.get(retrieval_band, 1), verify_score)
    return int_to_band[combined]


def build_prompt(question: str, retrieved_chunks: list[dict],
                 language_clause: str = "") -> str:
    """Build the grounded prompt sent to the model.

    The rules are given as a labelled list rather than one freeform instruction,
    and they restrict the model to the retrieved context and tell it to decline
    rather than guess when that context is thin.

    language_clause is supplied by the interface via
    i18n.answer_language_instruction() and asks for the answer in Italian or
    French while the course material stays in English. It defaults to empty, so
    an English question produces the same prompt the gold set was scored on.
    It sits after Rules rather than at the end, which leaves the CONFIDENCE
    instruction in final position where the model follows it most reliably.
    """
    context_block = "\n\n".join(
        f"[Source {i} | Week {c['metadata']['week']} | "
        f"{c['metadata']['topic_label']} ({c['metadata']['artefact_type']})]\n"
        f"{c['text']}"
        for i, c in enumerate(retrieved_chunks, start=1)
    )

    return f"""You are a teaching assistant for a postgraduate Network Security module at King's College London.
Answer the student's question using ONLY the course material provided below.

Rules:
- Base your answer strictly on the provided context. Do not use outside knowledge.
- If the context does not contain enough information to answer, say so clearly
  rather than guessing.
- Cite which week's material your answer draws from.
- Keep the answer clear and appropriately technical for a postgraduate student.
- Do not end by summarising what the sources contain. Answer the question and stop.
{language_clause}
COURSE MATERIAL:
{context_block}

STUDENT QUESTION:
{question}

Write your answer below. Then on a final separate line, rate how well the
course sources support your answer, in this exact format:
CONFIDENCE: X
where X is 3 (well supported), 2 (partially supported), or 1 (poorly supported).

ANSWER:"""


def parse_answer_and_confidence(raw: str) -> tuple[str, int]:
    """Split the response into the answer text and the self-verification score.

    The prompt asks the model to end with "CONFIDENCE: X". If that line is
    missing or unreadable the score falls back to 2, so a parse failure lowers
    confidence rather than inflating it.

    Matching is tolerant because an exact string match failed in testing: the
    model varied the wording and spacing of that line, so the search works
    backwards through the lines for anything starting CONF.
    """
    lines = raw.strip().splitlines()
    verify_score = 2  #fallback

    for i in range(len(lines) - 1, -1, -1):
        if re.search(r"CONF\w*\s*:", lines[i].upper()):
            digits = [ch for ch in lines[i] if ch in "123"]
            if digits:
                verify_score = int(digits[0])
            #drop the confidence line so it never shows up in the answer
            answer = "\n".join(lines[:i]).strip()
            return answer, verify_score

    #no CONFIDENCE line found, return the whole text with the fallback score
    return raw.strip(), verify_score




def generate_answer(client, question: str, collection) -> dict:
    """
    full retrieve then generate pipeline for a single question

    returns the answer alongside the retrieved sources (week, topic, artefact
    type, distance) so they can be shown to the student, which satisfies the
    "generates a cited answer" requirement in the project scope
    """
    start_time = time.time()
    retrieved_chunks = retrieve_context(collection, question)

    #Signal 1, retrieval distance band
    retrieval_band = confidence_band(retrieved_chunks)

    mean_dist = round(
        sum(c["distance"] for c in retrieved_chunks) / len(retrieved_chunks), 3
    )

    #the answer and Signal 2 come back in one call. the model writes the answer then a "CONFIDENCE: X" line, which parse_answer_and_confidence() strips out
    prompt = build_prompt(question, retrieved_chunks)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_ANSWER_TOKENS
    )
    message = response.choices[0].message
    raw = message.content or ""

    #reasoning models return their working in a separate field and occasionally leave content holding only the CONFIDENCE line, which the parser
    #strips and so yields an empty answer.
    if not raw.strip() or len(raw.strip()) < 20:
        reasoning = getattr(message, "reasoning", None)
        if reasoning and reasoning.strip():
            raw = reasoning.strip()

    answer, verify_score = parse_answer_and_confidence(raw)

    #compound confidence, the conservative minimum of both signals
    final_band = compound_confidence(retrieval_band, verify_score)
    elapsed = round(time.time() - start_time, 2)

    return {
        "question":        question,
        "answer":          answer,
        "confidence":      final_band,
        "retrieval_band":  retrieval_band,
        "verify_score":    verify_score,
        "mean_distance":   mean_dist,
        "latency_seconds": elapsed,
        "sources": [
            {
                "week":          c["metadata"]["week"],
                "topic":         c["metadata"]["topic_label"],
                "artefact_type": c["metadata"]["artefact_type"],
                "distance":      round(c["distance"], 3),
            }
            for c in retrieved_chunks
        ],
    }


def print_result(result: dict) -> None:
    """pretty print the question, confidence band, answer and sources"""
    band_label = {
        "High":   "HIGH",
        "Medium": "MEDIUM",
        "Low":    "LOW",
    }.get(result["confidence"], result["confidence"])

    verify_label = {3: "3 - well supported",
                    2: "2 - partially supported",
                    1: "1 - poorly supported"}.get(result["verify_score"], "?")

    print("\n" + "=" * 70)
    print(f"  Q: {result['question']}")
    print(f"  FINAL CONFIDENCE: {band_label}")
    print(f"  Signal 1 (retrieval): {result['retrieval_band']} "
          f"(mean dist: {result['mean_distance']})")
    print(f"  Signal 2 (self-verify): {verify_label}")
    print(f"  Response time: {result['latency_seconds']}s")
    print("-" * 70)
    print(result["answer"])
    print("-" * 70)
    print("  SOURCES RETRIEVED:")
    for s in result["sources"]:
        print(f"    Week {s['week']} | {s['topic']} "
              f"({s['artefact_type']})  dist={s['distance']}")
    print("=" * 70)


def main() -> None:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        sys.exit(
            "\n[ERROR] GROQ_API_KEY environment variable not set.\n"
            '  $env:GROQ_API_KEY="your-api-key-here"\n'
        )

    print("=" * 70)
    print(" Network Security RAG Pipeline - Retrieval + Generation")
    print("=" * 70)

    print("\nConnecting to knowledge base...")
    collection = get_collection()
    print(f"Connected. Collection contains {collection.count()} chunks.")

    client = Groq(api_key=api_key)

    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else DEFAULT_QUESTIONS

    for question in questions:
        #a failed prerequisite probe does not block the answer, it asks for a simpler one. the Streamlit front end does the same thing through
        #check_prerequisite() and render_mcq_probe()
        prereq = check_prerequisite(question)
        if prereq and not prereq["passed"]:
            question += (" Please give a simplified explanation suitable for "
                         "someone still building their foundational knowledge.")

        print(f"\n  Querying {GROQ_MODEL} for: '{question}' ...")
        result = generate_answer(client, question, collection)
        print_result(result)


if __name__ == "__main__":
    main()
