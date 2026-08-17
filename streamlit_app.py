"""
streamlit_app.py
Browser-based chat front end for the tutor. Wraps the RAG pipeline (generate_answer.py) and the prerequisite check (prerequisite_check.py) in a
conversational Streamlit interface, and keeps the conversation state, the turn loop and the layout.

Module layout, presentation and study features split out so each concern has one place to be read and changed:
1)ui_theme.py=design tokens, the four-channel confidence encoding, CSS
2)i18n.py= EN/IT/FR interface catalogue and language handling
3)mcq_i18n.py=translated MCQ bank, answer key still canonical
4)cross_lingual.py=English rendering of a question, for retrieval only
5)study_tools.py=follow-up suggestions, progress summary, export
6)quiz.py=on demand quiz, generation and scoring

A follow-up such as "explain that more simply" carries no retrievable content, so build_retrieval_query() prepends the last substantive question before
retrieval. It is a heuristic rather than a learned rewriter and is reported as a limitation. Prerequisite probes fire once per topic per thread, since
re-testing on every ARP-related follow-up would undermine the retrieval-practice rationale (Carpenter et al., 2022).

Confidence bands are encoded four ways, by colour, shape marker, text label and filled meter segments, so colour is never the sole cue (WCAG 2.2 SC 1.4.1).
The palette is Paul Tol's high-contrast scheme (Tol, 2021). Contrast figures and the rationale are in ui_theme.py.

Usage:
    $env:GROQ_API_KEY="your-key-here"
    py -m streamlit run streamlit_app.py
"""

import streamlit as st
st.write("app started")
#chromadb needs sqlite3 3.35 or later and some hosting images ship an older one, which fails on the first chromadb import. chromadb has its own swap
#for this but only runs it on Colab. has to sit above the imports to beat chromadb to it, and does nothing at all where pysqlite3 is absent, so local
#runs are unaffected
try:
    import sys
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

import html
import os
import time
import uuid
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
import chromadb
from groq import Groq

from config import VECTOR_STORE_DIR, COLLECTION_NAME, APP_NAME, APP_ICON
from core.prerequisite_check import (
    detect_prerequisite,
    score_responses, prerequisite_passed, build_review,
)
from core.generate_answer import (
    retrieve_context, confidence_band,
    compound_confidence, build_prompt,
    parse_answer_and_confidence, GROQ_MODEL,
    MAX_ANSWER_TOKENS,
)

from ui import i18n
from ui.i18n import t, topic_label, answer_language_instruction
from ui.mcq_i18n import localised_questions, localised_review
from core.cross_lingual import to_english
from ui.study_tools import (
    suggest_followups, progress_snapshot, conversation_markdown,
    export_filename, relevance,
)
from core import quiz
from core.quiz import score_quiz
from ui import ui_theme
from ui.ui_theme import (
    BAND_STYLE, BAND_ORDER, band_colour, band_chip_html, review_item_html,
    relevance_bar_html, stat_row_html, confidence_mix_html, inject_css,
)

#Configuration



#page_icon takes the file itself, which Streamlit turns into the browser tab icon. str() because it expects a path or an image rather than a Path
#object, and it is wrapped because a missing icon should cost the tab picture, not the whole app
try:
    _PAGE_ICON = str(APP_ICON) if APP_ICON.is_file() else "◈"
except Exception:
    _PAGE_ICON = "◈"

st.set_page_config(
    page_title=APP_NAME,
    page_icon=_PAGE_ICON,
    layout="centered",
    initial_sidebar_state="expanded",
)



#Number of prior turns passed to the model as conversation context. Kept small to bound prompt size and latency; the retrieved chunks remain the
#dominant source of information.
HISTORY_TURNS = 3

#A message is treated as a follow-up rather than a new question if it contains one of the anaphoric markers in i18n.FOLLOWUP_MARKERS, o  r is shorter
#than this many words while naming no recognised topic. The limit is deliberately low: an over-eager rule misclassifies short but substantive
#questions such as "whats arp spoofing", which both pollutes retrieval and suppresses the prerequis=ite probe.
FOLLOWUP_WORD_LIMIT = 5

VERIFY_LABEL = {3: "verify.3", 2: "verify.2", 1: "verify.1"}


#Message guards
#These run before any API call, which is the whole point of them: an interjection should not cost a retrieval and a generation. Their vocabularies are
#language-aware (i18n.py) because the original English keyword lists misfire in Italian and French, where "perché?" would be intercepted as an
#interjection rather than answered.


def is_non_question(message: str, lang: str) -> bool:
    """
    Return True when a message is an interjection rather than a question
    (e.g. "wow", "baba", "lol") and should receive a short canned reply
    instead of invoking the retrieval pipeline.

    The rule is deliberately conservative - every branch errs toward letting
    the message through, since wrongly blocking a real question is worse
    than answering an interjection:
      * anything containing "?" passes;
      * anything matching a follow-up marker passes;
      * anything opening with a question/instruction word passes;
      * anything containing recognised module vocabulary passes;
      * anything longer than four words passes.
    Only a short message failing all five tests is intercepted.
    """
    text = message.lower().strip()
    if "?" in text:
        return False
    if any(marker in text for marker in i18n.followup_markers(lang)):
        return False
    words = text.split()
    if len(words) > 4:
        return False
    if words and words[0] in i18n.question_starters(lang):
        return False
    if any(term in text for term in i18n.MODULE_TERMS):
        return False
    return True


def is_bare_interrogative(message: str, lang: str) -> bool:
    """
    Return True for a message that is a single interrogative word (with or
    without punctuation), e.g. "how", "why?", "perché?". Two or more words -
    "why not", "how so" - pass through: those are genuine follow-ups that the
    retrieval anchoring answers well.

    Pure interrogatives carry no retrievable content, so the pipeline has
    nothing to anchor on and the model visibly flounders. Imperatives
    such as "explain" are excluded: alone they read as "explain that again",
    which the follow-up anchoring handles well.
    """
    words = message.lower().strip().rstrip("?!.").split()
    return len(words) == 1 and words[0] in i18n.bare_interrogatives(lang)


def has_prior_answer() -> bool:
    """
    True when the active thread already contains a substantive assistant
    answer (a turn carrying a pipeline result). Canned turns do not count.
    Used to decide whether a bare interrogative is a follow-up to something
    or arrived with nothing to follow up on.
    """
    return any(
        turn["role"] == "assistant" and "result" in turn
        for turn in st.session_state.messages
    )


#Cached resources

@st.cache_resource
def load_collection():
    """Load the ChromaDB collection once per session."""
    client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)
    return client.get_collection(COLLECTION_NAME)


def _api_key() -> str:
    """Read the Groq key from Streamlit secrets, falling back to the environment.

    Secrets are how a hosted deployment supplies the key; the environment
    variable is how it is supplied when running locally.
    """
    try:
        key = str(st.secrets.get("GROQ_API_KEY", "")).strip()
        if key:
            return key
    except Exception:
        #no secrets file configured, which is the normal local case
        pass
    return os.environ.get("GROQ_API_KEY", "").strip()


@st.cache_resource
def load_groq_client():
    """Initialise the Groq client once per session."""
    api_key = _api_key()
    if not api_key:
        st.error(
            "**GROQ_API_KEY is not set.**\n\n"
            "Locally, set it before launching:\n"
            "```\n$env:GROQ_API_KEY='your-key-here'\n```\n"
            "When hosted, add it under Settings, Secrets."
        )
        st.stop()
    return Groq(api_key=api_key)


#Session state




def init_state() -> None:
    """
    Initialise session state.

    messages          turns in the active thread. A user turn is
                      {"role": "user", "content": str}. An assistant turn is
                      {"role": "assistant", "id": str, "result": dict,
                       "prereq": dict|None} and carries the full pipeline result
                      so its metrics can be re-rendered on every rerun without
                      re-calling the API.
    archive           previous conversations, most recent first. Each entry is
                      {"title", "when", "messages", "tested_topics"}.
    pending_question  question awaiting an answer, held while an MCQ probe is
                      displayed.
    pending_topic     prerequisite topic currently being probed, or None.
    pending_prompt    message queued by a starter or follow-up button, consumed
                      on the next run exactly as if it had been typed.
    tested_topics     topics already probed in this thread, so a student is not
                      re-tested on the same foundation repeatedly.
    ratings           {assistant turn id: rating} for the study log, so a rating
                      survives reruns and a turn cannot be rated twice.
    language          interface and answer language, seeded from the browser
                      locale on first load.
    """
    defaults = {
        "messages": [],
        "archive": [],
        "pending_question": None,
        "pending_topic": None,
        "pending_prompt": None,
        "tested_topics": {},
        "app_mode": "tutor",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "language" not in st.session_state:
        st.session_state["language"] = i18n.default_language()

    #"dark_mode" is deliberately not seeded here. The theme lives in the browser rather than in session state, so render_theme_toggle() reads it back
    #from the client on every render and the widget only needs its key to detect a change. Seeding it would also make Streamlit reject the widget,
    #which refuses a key written through the Session State API when the widget is given an explicit value= as well.


def archive_current_thread() -> None:
    """
    Move the active thread into the archive so it can be reopened later.

    Reset previously discarded the conversation outright. Archiving preserves
    it for the session, which matters during the user study: a participant who
    starts a new line of enquiry should not lose the thread they may want to
    refer back to.
    """
    if not st.session_state.messages:
        return

    first_user = next(
        (m["content"] for m in st.session_state.messages if m["role"] == "user"),
        "Conversation",
    )
    title = first_user if len(first_user) <= 45 else first_user[:42] + "..."

    st.session_state.archive.insert(0, {
        "title": title,
        "when": datetime.now().strftime("%H:%M"),
        "messages": st.session_state.messages,
        "tested_topics": st.session_state.tested_topics,
    })


def start_new_conversation() -> None:
    """Archive the active thread, then clear it."""
    archive_current_thread()
    st.session_state.messages = []
    st.session_state.tested_topics = {}
    st.session_state.pending_question = None
    st.session_state.pending_topic = None
    st.session_state.pending_prompt = None


def reopen_conversation(index: int) -> None:
    """Archive whatever is open, then restore the archived thread at index."""
    if index >= len(st.session_state.archive):
        return
    entry = st.session_state.archive.pop(index)
    archive_current_thread()
    st.session_state.messages = entry["messages"]
    st.session_state.tested_topics = entry["tested_topics"]
    st.session_state.pending_question = None
    st.session_state.pending_topic = None
    st.session_state.pending_prompt = None


def queue_prompt(text: str) -> None:
    """Queue a message from a button so the next run handles it as typed input."""
    st.session_state.pending_prompt = text


def retest_topic(topic: str) -> None:
    """
    Reopen a prerequisite probe the student has already completed.

    tested_topics gates the probe to once per topic per thread, which is right
    as a default but wrong as a rule: a student who has just been told they got
    two of three wrong may reasonably want another attempt. Clearing the entry
    reopens the probe without asking a new question, so the outcome renders as
    its own turn rather than being attached to an answer.
    """
    st.session_state.tested_topics.pop(topic, None)
    st.session_state.pending_topic = topic
    st.session_state.pending_question = None


#Follow-up handling

def is_followup(message: str) -> bool:
    """
    Decide whether a message is a conversational follow-up rather than a new
    self-contained question.

    Three rules, applied in order:

    1.Nothing can follow up on nothing. If no answer has been given yet in this
         thread, the message is a new question by definition.
    2.An anaphoric marker ("explain that", "spiegalo", "développe") makes it a
      follow-up regardless of length.
    3.   A message naming a recognised topic is substantive, however short.
       "whats arp spoofing" is three words but is a new question, not a
       follow-up.

    Only if none of those apply does the word-count fallback decide, catching
    fragments such as "and?" or "go on".

    Rules 1 and 3 were added after a bare word-count
    rule classified the opening message of a thread as a follow-up. That both
    anchored retrieval to a non-existent prior question and suppressed the
    prerequisite probe, because the probe was gated on the message not being a
    follow-up.

    Rule 3 still tests the raw message rather than an English rendering of it.
    Translating here would put an API call inside a function called repeatedly
    during rendering. In practice the graph keys it matches are protocol names
    and attack names that are written identically in all three languages ("ARP
    spoofing", "SYN flood", "DMZ"), so the rule degrades gracefully rather than
    failing outright. This remains a heuristic rather than a learned query
    rewriter and is reported as a limitation.
    """
    #Rule 1: no prior answer means there is nothing to follow up on.
    prior_answer = any(
        turn["role"] == "assistant"
        for turn in st.session_state.get("messages", [])
    )
    if not prior_answer:
        return False

    text = message.lower().strip()

    #Rule 2: an explicit anaphoric marker, in any supported language.
    lang = i18n.current_language()
    if any(marker in text for marker in i18n.followup_markers(lang)):
        return True

    #Rule 3: naming a recognised topic makes it substantive.
    if detect_prerequisite(message):
        return False

    #Fallback: very short and topic-free.
    return len(text.split()) < FOLLOWUP_WORD_LIMIT


def last_substantive_question() -> str | None:
    """Return the most recent user message that was not itself a follow-up."""
    for turn in reversed(st.session_state.messages):
        if turn["role"] == "user" and not is_followup(turn["content"]):
            return turn["content"]
    return None


def build_retrieval_query(message: str) -> str:
    """
    Build the string used for vector retrieval.

    A follow-up such as "explain that more simply" carries no retrievable
    content. Embedding it directly returns unrelated chunks and collapses the
    confidence band. Where a follow-up is detected and a prior substantive
    question exists, the two are concatenated so retrieval stays anchored to
    the original topic.
    """
    if not st.session_state.messages:
        return message
    if is_followup(message):
        anchor = last_substantive_question()
        if anchor:
            return f"{anchor} {message}"
    return message


def build_history_block() -> str:
    """
    Render the last few turns as plain text for inclusion in the prompt so that
    pronouns in follow-ups resolve against what was actually said. Returns an
    empty string on the first turn.
    """
    turns = []
    for turn in st.session_state.messages[-(HISTORY_TURNS * 2):]:
        if turn["role"] == "user":
            turns.append(f"Student: {turn['content']}")
        else:
            answer = turn.get("result", {}).get("answer", "")
            if len(answer) > 600:
                answer = answer[:600] + " [...]"
            turns.append(f"Tutor: {answer}")
    if not turns:
        return ""
    return (
        "CONVERSATION SO FAR (for resolving references such as 'that' or 'it'; "
        "this is not course material and must not be treated as a source):\n"
        + "\n\n".join(turns)
        + "\n\n"
    )


#Pipeline




def run_pipeline(message: str, groq_client, collection,
                 simplify: bool = False) -> dict:
    """
    Run retrieve-then-generate for a single conversational turn.

    Two things happen here that do not happen in generate_answer.py's own
    entry point, both of them front-end concerns:

      * the retrieval query is rendered into English when the student is
        working in Italian or French, because the knowledge base is embedded
        with an English-only encoder (see cross_lingual.py);
      * a language clause is added to the prompt so the answer comes back in
        the student's language while the sources stay English.

    For an English session both are no-ops and the prompt is byte-identical to
    the one the gold-set evaluation was scored against.

    Not cached. The prompt varies with conversation history, so caching on the
    question string alone could return an answer built from a different thread.
    """
    start_time = time.time()
    lang = i18n.current_language()

    #Anchor first, in the student's own language, then translate the anchored string as a whole. Anchoring before translating keeps the follow-up
    #rules operating on the text the student actually wrote.
    anchored_query = build_retrieval_query(message)
    retrieval_query, was_translated = to_english(anchored_query, lang)

    retrieved_chunks = retrieve_context(collection, retrieval_query)

    #Signal 1: retrieval distance band
    retrieval_band = confidence_band(retrieved_chunks)
    mean_dist = round(
        sum(c["distance"] for c in retrieved_chunks) / len(retrieved_chunks), 3
    )

    question_for_model = message
    if simplify:
        question_for_model += (
            " Please give a simplified explanation suitable for someone still "
            "building their foundational knowledge."
        )

    prompt = build_history_block() + build_prompt(
        question_for_model, retrieved_chunks,
        language_clause=answer_language_instruction(lang),
    )

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_ANSWER_TOKENS,
    )
    reply = response.choices[0].message
    raw = reply.content or ""

    #reasoning models return their working in a separate field and occasionally leave content holding only the CONFIDENCE line, which the parser
    #strips and so yields an empty answer. fall back to the reasoning text in that case
    if not raw.strip() or len(raw.strip()) < 20:
        reasoning = getattr(reply, "reasoning", None)
        if reasoning and reasoning.strip():
            raw = reasoning.strip()

    #Signal 2 is parsed from the same response rather than a second call
    answer, verify_score = parse_answer_and_confidence(raw)
    final_band = compound_confidence(retrieval_band, verify_score)
    elapsed = round(time.time() - start_time, 2)

    return {
        "question":        message,
        "retrieval_query": retrieval_query,
        "was_translated":  was_translated,
        "language":        lang,
        "answer":          answer,
        "confidence":      final_band,
        "retrieval_band":  retrieval_band,
        "verify_score":    verify_score,
        "mean_distance":   mean_dist,
        "latency_seconds": elapsed,
        "was_followup":    is_followup(message),
        "simplified":      simplify,
        "sources": [
            {
                "week":          c["metadata"]["week"],
                "topic":         c["metadata"]["topic_label"],
                "artefact_type": c["metadata"]["artefact_type"],
                "distance":      round(c["distance"], 3),
                #The passage itself is kept so the citation can be checked rather than merely cited. the project scope promises a "cited answer"; a week
                #number alone is a reference a student cannot verify without going back to KEATS, which is exactly the friction the tutor exists to
                #remove.
                "excerpt":       c["text"],
            }
            for c in retrieved_chunks
        ],
    }


#Rendering: answer metadata

def build_details_lines(result: dict, lang: str) -> list[str]:
    """
    Build the signal-breakdown lines shown in the details dialog.

    The breakdown restates the question so that, when scrolling back through a
    long thread, an answer can be interpreted without scrolling to find the
    turn it responded to.
    """
    band = result["confidence"]
    band_name = t(f"band.{band}", lang)
    retrieval_name = t(f"band.{result['retrieval_band']}", lang)
    verify_name = t(VERIFY_LABEL.get(result["verify_score"], "verify.2"), lang)
    distance_note = t("details.signal1.note", lang, d=result["mean_distance"])

    lines = [
        f"**{t('details.you_asked', lang)}:** {result['question']}",
        "",
        f"**{t('details.final', lang)}:** {band_name}",
        f"**{t('details.signal1', lang)}:** {retrieval_name} ({distance_note})",
        f"**{t('details.signal2', lang)}:** {verify_name}",
        f"**{t('details.latency', lang)}:** {result['latency_seconds']}s",
        f"**{t('details.sources_n', lang)}:** {len(result['sources'])}",
    ]

    if result.get("simplified"):
        lines.append(t("details.simplified", lang))

    if result.get("was_followup") and \
            result["retrieval_query"] != result["question"]:
        lines.append(t("details.followup", lang))

    #Surfaced rather than hidden: a translated retrieval query is a step the student did not take, and if it went wrong it is the first place to look.
    if result.get("was_translated"):
        lines.append(t("details.translated", lang, q=result["retrieval_query"]))

    lines.append("")
    lines.append(t(f"band.{band}.text", lang))
    return lines



def show_details_dialog(result: dict, lang: str) -> None:
    """
    Modal breakdown of the confidence signals for one answer.

    Replaces the earlier hover-tooltip (title attribute) approach: a click-to-
    open modal is reachable on touch devices, is keyboard-accessible via the
    triggering button, and closes with the dialog's native close (X) control,
    whereas a hover tooltip is unavailable on touchscreens and cannot be
    dismissed explicitly.

    @st.dialog is applied inside the function rather than as a decorator on it.
    A decorator is evaluated at import, when no language has been chosen yet,
    which would pin the dialog's title to whatever the catalogue happened to
    return at module load. Applying it per call gives the modal a title in the
    student's language.
    """
    @st.dialog(t("details.title", lang))
    def _dialog() -> None:
        for line in build_details_lines(result, lang):
            if line:
                st.markdown(line)

    _dialog()


def render_band_row(result: dict, lang: str, key_suffix: str) -> None:
    """
    Render the confidence chip followed by a details control.

    The band is encoded four ways: a Tol high-contrast colour, a
    shape marker, a text label, and the number of filled segments in the meter.
    Any one of the four identifies the band, so it stays readable under any form
    of colour vision deficiency and in greyscale.

    The full signal breakdown, latency and the originating question are moved
    into a click-to-open modal rather than occupying the thread. In a
    conversational interface the answer is the primary content; the diagnostics
    are secondary and should be available on demand without displacing it. A
    native button triggers the dialog, so the breakdown is reachable by keyboard
    and on touch devices.
    """
    band = result["confidence"]
    if band not in BAND_STYLE:
        return

    label = f"{t(f'band.{band}', lang)} {t('band.confidence', lang)}"

    chip_col, info_col, _spacer = st.columns([6, 3, 3])
    with chip_col:
        st.markdown(band_chip_html(band, label), unsafe_allow_html=True)
    with info_col:
        if st.button(
            t("details.title", lang),
            key=f"details_{key_suffix}",
            help=t("details.help", lang),
            type="tertiary",
        ):
            show_details_dialog(result, lang)


def render_sources(result: dict, lang: str) -> None:
    """
    Render the retrieved passages as inspectable source cards.

    Previously this listed week, topic and cosine distance only. That is a
    citation a student cannot check: it names where the material came from
    without showing what was actually read, so the claim that answers are
    grounded has to be taken on trust. The passage the answer was written from
    is now shown in full, which turns the citation into something verifiable
    and lets a student notice when an answer has drifted beyond its sources.

    Each excerpt sits in a native <details> element rather than a nested
    st.expander, which Streamlit forbids inside another expander. <details> is
    keyboard operable and announced by screen readers without additional ARIA.

    The raw cosine distance is kept alongside the relevance bar. The bar is the
    readable form; the distance is the number the confidence band was actually
    computed from, and dropping it would make the details dialog impossible to
    reconcile with what is shown here.
    """
    sources = result["sources"]

    with st.expander(t("sources.title", lang, n=len(sources)), expanded=False):
        st.caption(t("sources.note", lang))

        if result.get("was_followup") and \
                result["retrieval_query"] != result["question"]:
            st.caption(t("details.followup", lang))
        elif result.get("was_translated"):
            st.caption(t("details.translated", lang, q=result["retrieval_query"]))

        for source in sources:
            score = relevance(source["distance"])
            excerpt = html.escape((source.get("excerpt") or "").strip())

            st.markdown(
                f'<div class="ns-source">'
                f'  <div class="ns-source__head">'
                f'    <span class="ns-week">'
                f'{html.escape(t("sources.week", lang, n=source["week"]))}</span>'
                f'    <span class="ns-source__topic">'
                f'{html.escape(str(source["topic"]))}</span>'
                f'    <span class="ns-tag">'
                f'{html.escape(str(source["artefact_type"]))}</span>'
                f'  </div>'
                f'  <div class="ns-source__meta">'
                f'    <span>{t("sources.relevance", lang)} {score:.0%}</span>'
                f'    {relevance_bar_html(score)}'
                f'    <span>{t("sources.distance", lang)} {source["distance"]}</span>'
                f'  </div>'
                f'  <details>'
                f'    <summary>{html.escape(t("sources.excerpt", lang))}</summary>'
                f'    <p class="ns-excerpt">{excerpt}</p>'
                f'  </details>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_followups(result: dict, lang: str, key_suffix: str) -> None:
    """
    Offer up to three next moves after the most recent answer.

    Shown only on the latest turn. Leaving stale suggestion rows attached to
    every earlier answer would clutter the thread and, worse, invite a student
    to branch backwards into a topic the conversation has already moved past.

    See study_tools.suggest_followups() for how the set is chosen, including why
    the worked-example suggestion is withheld after a Low-confidence answer.
    """
    prereq_topic = detect_prerequisite(result.get("retrieval_query", "")) \
        or detect_prerequisite(result["question"])
    already_tested = bool(prereq_topic) and \
        prereq_topic in st.session_state.tested_topics

    suggestions = suggest_followups(result, lang, prereq_topic, already_tested)
    if not suggestions:
        return

    st.caption(t("followups.title", lang))
    columns = st.columns(len(suggestions))

    for index, (column, suggestion) in enumerate(zip(columns, suggestions)):
        with column:
            if st.button(suggestion["label"],
                         key=f"followup_{key_suffix}_{index}",
                         use_container_width=True):
                if suggestion["kind"] == "test_me":
                    retest_topic(suggestion["prompt"])
                else:
                    queue_prompt(suggestion["prompt"])
                st.rerun()



def render_prereq_review(prereq: dict, lang: str) -> None:
    """
    Render the outcome of a prerequisite probe, with an explanation for every
    question answered incorrectly.

    Only incorrect answersa are explained. Carpenter et al. (2022) find that the
    benefit of retrieval practice comes from the corrective feedback that
    follows the attempt, not from the attempt alone, so a bare score would waste
    the probe. Repeating explanations for questions already answered correctly
    would add length without adding information, and would dilute the items the
    student actually needs to read.

    A student who passes still sees any individual mistakes explained, since
    passing at 2 of 3 still means one concept was misunderstood.

    The review is re-localised at render time rather than at scoring time, so a
    student who switches language after answering sees the feedback they have
    already earned rather than losing it (mcq_i18n.localised_review).
    """
    review = localised_review(prereq.get("review", []), prereq["topic"], lang)
    wrong = [item for item in review if not item["correct"]]
    label = topic_label(prereq["topic"], lang)

    if prereq["passed"]:
        st.success(t("prereq.passed", lang,
                     score=prereq["score"], total=prereq["total"]))
    else:
        st.warning(t("prereq.failed", lang, score=prereq["score"],
                     total=prereq["total"], topic=label))

    if not wrong:
        return

    heading = (t("prereq.review_one", lang) if len(wrong) == 1
               else t("prereq.review_many", lang, n=len(wrong)))

    labels = {
        "you_chose": t("prereq.you_chose", lang),
        "correct":   t("prereq.correct", lang),
        "no_answer": t("prereq.no_answer", lang),
    }

    #The whole review is emitted as one markup block rather than four Streamlit calls per question. Each of those calls carried its own block margin,
    #which is what made a three-question review scroll for a page and a half; the cards set their own spacing instead.
    with st.expander(heading, expanded=not prereq["passed"]):
        st.markdown(
            "".join(review_item_html(item, labels) for item in wrong),
            unsafe_allow_html=True,
        )

def render_answer_turn(turn: dict, lang: str, key_suffix: str,
                       is_last: bool) -> None:
    """Render one assistant turn: prerequisite review, answer, band, sources,
    rating control, and follow-up suggestions on the most recent turn only."""
    result = turn["result"]
    prereq = turn.get("prereq")

    if prereq:
        render_prereq_review(prereq, lang)

    st.markdown(result["answer"])

    render_band_row(result, lang, key_suffix)
    render_sources(result, lang)

    if is_last:
        render_followups(result, lang, key_suffix)


def render_thread(lang: str) -> None:
    """Re-render the full active conversation on each rerun."""
    messages = st.session_state.messages
    last_assistant = max(
        (i for i, m in enumerate(messages)
         if m["role"] == "assistant" and "result" in m),
        default=-1,
    )

    for index, turn in enumerate(messages):
        if turn["role"] == "user":
            with st.chat_message("user"):
                st.markdown(turn["content"])
            continue

        with st.chat_message("assistant"):
            if "result" in turn:
                render_answer_turn(turn, lang, str(index),
                                   is_last=(index == last_assistant))
            elif turn.get("prereq"):
                #A probe reopened from the follow-up suggestions, with no question attached: the review is the whole turn.
                render_prereq_review(turn["prereq"], lang)
            else:
                #Canned turn (e.g. non-question reply): plain content, no confidence band or sources.
                st.markdown(turn["content"])


#Rendering: probe



def render_mcq_probe(topic: str, lang: str) -> None:
    """
    Render the prerequisite MCQ probe inline in the chat thread.

    Presented as an assistant turn so the interruption reads as part of the
    conversation rather than as a modal blocking the interface. The framing
    matters pedagogically: Kuzminykh et al. (2021) show students cannot
    self-diagnose a missed threshold concept, so the probe has to feel like the
    tutor checking in rather than a gate refusing them entry.

    Radio groups deliberately have no preselected option (index=None). A default
    selection would be indistinguishable from a deliberate choice, and would
    silently score a student who submitted without reading.
    """
    questions = localised_questions(topic, lang)
    if not questions:
        st.session_state.pending_topic = None
        return

    with st.chat_message("assistant"):
        st.markdown(
            f'<div class="ns-checkpoint">'
            f'  <p class="ns-checkpoint__eyebrow">{t("mcq.eyebrow", lang)}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(t("mcq.intro", lang,
                      topic=topic_label(topic, lang), n=len(questions)))

        with st.form(f"mcq_form_{topic}", clear_on_submit=False):
            responses = []
            for index, question in enumerate(questions):
                st.markdown(
                    f'<p class="ns-qcount">'
                    f'{t("mcq.qcount", lang, i=index + 1, n=len(questions))}</p>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{question['question']}**")
                choice = st.radio(
                    label=t("mcq.qcount", lang, i=index + 1, n=len(questions)),
                    options=list(question["options"].keys()),
                    format_func=lambda key, q=question: f"{key})  {q['options'][key]}",
                    label_visibility="collapsed",
                    index=None,
                    key=f"mcq_{topic}_{index}",
                )
                responses.append(choice)
                if index < len(questions) - 1:
                    st.markdown("---")

            submitted = st.form_submit_button(t("mcq.submit", lang), type="primary")

        if submitted:
            #An unanswered question is scored as incorrect rather than skipped, which keeps the denominator equal to the number of questions asked and
            #stops a student passing by answering only what they were sure of. The placeholder never matches a valid option label.
            answers = [choice if choice else "-" for choice in responses]

            score, total = score_responses(topic, answers)
            passed = prerequisite_passed(score, total)
            st.session_state.tested_topics[topic] = {
                "topic":  topic,
                "score":  score,
                "total":  total,
                "passed": passed,
                "review": build_review(topic, answers),
            }
            st.session_state.pending_topic = None

            #A probe reopened from a follow-up suggestion has no question waiting behind it, so its outcome is appended as its own turn.
            if not st.session_state.pending_question:
                st.session_state.messages.append({
                    "role":   "assistant",
                    "id":     uuid.uuid4().hex,
                    "prereq": st.session_state.tested_topics[topic],
                })
            st.rerun()


#Rendering: page furniture


def render_masthead(lang: str) -> None:
    """Title, one-line description of what makes the tutor different, and the
    scope badge. The scope is stated up front because the knowledge base covers
    five weeks and a student who asks about Week 8 should learn that from the
    header rather than from a Low-confidence answer."""
    st.markdown(
        f'<div class="ns-masthead">'
        f'  <div class="ns-masthead__row">'
        f'    {ui_theme.app_mark_html(56)}'
        f'    <div class="ns-masthead__text">'
        f'      <div class="ns-masthead__line">'
        f'        <h1 class="ns-masthead__title">'
        f'{html.escape(t("app.title", lang))}</h1>'
        f'        <span class="ns-scope">{html.escape(t("app.scope", lang))}</span>'
        f'      </div>'
        f'      <p class="ns-masthead__sub">'
        f'{html.escape(t("app.subtitle", lang))}</p>'
        f'    </div>'
        f'  </div>'
        f'  <div class="ns-rule"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_welcome(lang: str) -> None:
    """
    Empty-state panel, shown only before the first question.

    It replaces a single st.info line. The three points are the three claims
    the system actually makes, stated before a student has to infer them from
    behaviour: answers are grounded in their own module, every answer carries a
    visible confidence band, and advanced questions trigger a check on the
    concept underneath. Xiao et al. (2024) find postgraduate cybersecurity
    students value feedback tied to their specific errors over generic
    explanations, and a student who does not know the tutor works that way has
    no reason to use it that way.

    The starter questions are clickable. Beyond removing the blank-page problem,
    they guarantee a first-time user and a study participant meet the
    prerequisite probe, which the third question triggers.
    """
    features = (
        ("hero.f1.title", "hero.f1.body"),
        ("hero.f2.title", "hero.f2.body"),
        ("hero.f3.title", "hero.f3.body"),
    )
    cards = "".join(
        f'<div class="ns-feature">'
        f'  <p class="ns-feature__title">{html.escape(t(title, lang))}</p>'
        f'  <p class="ns-feature__body">{html.escape(t(body, lang))}</p>'
        f'</div>'
        for title, body in features
    )

    st.markdown(
        f'<div class="ns-hero">'
        f'  <p class="ns-hero__lead">{html.escape(t("hero.lead", lang))}</p>'
        f'  <div class="ns-hero__grid">{cards}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.caption(t("hero.try", lang))
    starters = i18n.STARTER_QUESTIONS.get(lang, i18n.STARTER_QUESTIONS["en"])
    for index, (column, question) in enumerate(zip(st.columns(len(starters)), starters)):
        with column:
            if st.button(question, key=f"starter_{index}", use_container_width=True):
                queue_prompt(question)
                st.rerun()


#Sidebar

#Applied by render_theme_toggle(). Streamlit keeps the active theme in the browser's own storage rather than on the server, so switching it means
#writing that value and reloading. Every stActiveTheme- key present is rewritten instead of one hardcoded name, because the key embeds the app's base
#URL path and a deployment served from a subpath uses a different one.
_APPLY_THEME_JS = """
<script>
(function () {
  try {
    var store = window.parent.localStorage;
    var value = JSON.stringify("%s");
    var written = 0;
    for (var i = 0; i < store.length; i++) {
      var key = store.key(i);
      if (key && key.indexOf("stActiveTheme-") === 0) {
        store.setItem(key, value);
        written++;
      }
    }
    if (written === 0) { store.setItem("%s", value); }
    window.parent.location.reload();
  } catch (e) {
    /* Storage blocked, or the iframe is cross-origin. The toggle simply does
       not take, and resets to the real theme on the next render. */
  }
})();
</script>
"""


def render_theme_toggle(sidebar, lang: str) -> None:
    """
    Dark / light theme switch.

    """
    #What the browser is rendering right now, not what session state thinks. Since the theme lives in the browser, that is the only honest source.
    dark_now = ui_theme.client_theme() == "dark"
    glyph = "☾︎" if dark_now else "☀︎"   #crescent / sun
    label = t("sidebar.dark_mode" if dark_now else "sidebar.light_mode", lang)

    wants_dark = sidebar.toggle(f"{glyph}  {label}", value=dark_now,
                                key="dark_mode")

    if wants_dark != dark_now:
        theme_name = "Dark" if wants_dark else "Light"
        with sidebar:
            components.html(
                _APPLY_THEME_JS % (theme_name, ui_theme.THEME_STORAGE_KEY),
                height=0,
            )


def render_sidebar(lang: str) -> None:
    """Sidebar: theme, language, session controls, progress, archive, and the
    confidence key."""
    sidebar = st.sidebar

    sidebar.markdown(
        f'<div class="ns-side-head">'
        f'  {ui_theme.app_mark_html(26, "ns-mark--sm")}'
        f'  <p class="ns-side-title">{html.escape(t("app.title", lang))}</p>'
        f'</div>'
        f'<p class="ns-side-sub">{html.escape(t("sidebar.grounded", lang))}</p>',
        unsafe_allow_html=True,
    )

    #Tutor / Quiz
    #The two halves of the tool are separated rather than mixed into one scrolling page: asking a question and sitting a timed test are different
    #activities, and an exam timer running underneath a chat thread would be both confusing and, in exam mode, unfair.
    sidebar.markdown(
        f'<p class="ns-section" style="margin-top:0.9rem;">'
        f'{html.escape(t("nav.section", lang))}</p>',
        unsafe_allow_html=True,
    )
    if st.session_state.get("app_mode_picker") is None:
        st.session_state["app_mode_picker"] = st.session_state.get(
            "app_mode", "tutor")
    picked = sidebar.segmented_control(
        t("nav.section", lang),
        options=["tutor", "quiz"],
        format_func=lambda m: t(f"nav.{m}", lang),
        key="app_mode_picker",
        label_visibility="collapsed",
        width="stretch",
    )
    if picked and picked != st.session_state.get("app_mode"):
        st.session_state["app_mode"] = picked
        st.rerun()

    #Appeareance
    render_theme_toggle(sidebar, lang)

    #--- Language
    sidebar.markdown(
        f'<p class="ns-section">{html.escape(t("sidebar.language", lang))}</p>',
        unsafe_allow_html=True,
    )
    #The picker writes its own key rather than "language" directly. A single-select segmented control deselects when its active option is clicked
    #again, which would leave the language None and silently drop the interface back to English. Re-pinning the widget's value before it is
    #instantiated makes that self-correcting, and is only legal because the widget key and the state key are separate.
    if st.session_state.get("language_picker") is None:
        st.session_state["language_picker"] = lang

    choice = sidebar.segmented_control(
        t("sidebar.language", lang),
        options=i18n.language_options(),
        format_func=i18n.language_label,
        key="language_picker",
        label_visibility="collapsed",
        help=t("sidebar.language_help", lang),
        width="stretch",
    )
    if choice and choice != st.session_state["language"]:
        st.session_state["language"] = choice
        st.rerun()

    #--- Session controls
    sidebar.markdown('<div style="height:0.8rem"></div>', unsafe_allow_html=True)
    sidebar.button(
        t("sidebar.new", lang),
        on_click=start_new_conversation,
        use_container_width=True,
        type="primary",
    )

    if st.session_state.messages:
        sidebar.download_button(
            t("sidebar.export", lang),
            data=conversation_markdown(
                st.session_state.messages, lang, st.session_state.tested_topics
            ),
            file_name=export_filename(),
            mime="text/markdown",
            use_container_width=True,
            help=t("sidebar.export_help", lang),
        )

    #--- Progress
    render_progress(sidebar, lang)

    #--- Archive
    if st.session_state.archive:
        sidebar.markdown(
            f'<p class="ns-section">{html.escape(t("sidebar.previous", lang))}</p>',
            unsafe_allow_html=True,
        )
        for index, entry in enumerate(st.session_state.archive):
            sidebar.button(
                f"{entry['when']}  {entry['title']}",
                key=f"archive_{index}",
                on_click=reopen_conversation,
                args=(index,),
                use_container_width=True,
            )

    #--- Prerequisites cleared in the active thread
    if st.session_state.tested_topics:
        sidebar.markdown(
            f'<p class="ns-section">{html.escape(t("sidebar.prereqs", lang))}</p>',
            unsafe_allow_html=True,
        )
        for topic, record in st.session_state.tested_topics.items():
            band = "High" if record["passed"] else "Low"
            state = t("prereq.state_passed" if record["passed"]
                      else "prereq.state_review", lang)
            sidebar.markdown(
                f'<div class="ns-prereq">'
                f'  <span style="color:{band_colour(band)};">'
                f'{BAND_STYLE[band]["marker"]}</span>'
                f'  <span>{html.escape(topic_label(topic, lang))}</span>'
                f'  <span class="ns-prereq__state">'
                f'{record["score"]}/{record["total"]} · {html.escape(state)}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    #--- Confidence key
    #The key is shown rather than assumed. A four-channel encoding still has to be learned once, and a student meeting a triangle for the first time
    #should not have to infer that it sits between a circle and a square.
    sidebar.markdown(
        f'<p class="ns-section">{html.escape(t("sidebar.key", lang))}</p>',
        unsafe_allow_html=True,
    )
    for band in BAND_ORDER:
        colour = band_colour(band)
        sidebar.markdown(
            f'<div class="ns-key">'
            f'  <span style="color:{colour};">'
            f'{ui_theme.confidence_meter_html(band, colour)}</span>'
            f'  <span class="ns-key__name" style="color:{colour};">'
            f'{BAND_STYLE[band]["marker"]} {html.escape(t(f"band.{band}", lang))}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    #The data-collection notice that sat here was removed at the author's request. Participants are informed of what is recorded through the study
    #information sheet and consent form instead, which is where the ethics submission places it. the research ethics section was corrected to match.


def render_progress(sidebar, lang: str) -> None:
    """
    Session summary: how much has been asked, which weeks the answers actually
    came from, and how the confidence bands fell.

    Coverage is counted from the retrieved sources rather than from the
    questions typed, because the sources are what the answers were built from.
    Making the distribution visible addresses the "unknown unknown" problem
    described by Tang et al. (2025): a student who has spent an hour on Week 3
    without noticing cannot act on that until they can see it.
    """
    snapshot = progress_snapshot(st.session_state.messages)

    sidebar.markdown(
        f'<p class="ns-section">{html.escape(t("progress.title", lang))}</p>',
        unsafe_allow_html=True,
    )

    if not snapshot["answers"]:
        sidebar.markdown(
            f'<p class="ns-note" style="margin-top:0;">'
            f'{html.escape(t("progress.empty", lang))}</p>',
            unsafe_allow_html=True,
        )
        return

    rows = stat_row_html(t("progress.questions", lang), str(snapshot["questions"]))
    rows += stat_row_html(t("progress.topics", lang), str(snapshot["topic_count"]))
    rows += stat_row_html(t("progress.latency", lang), f"{snapshot['avg_latency']}s")
    sidebar.markdown(rows, unsafe_allow_html=True)

    if snapshot["weeks"]:
        chips = "".join(
            f'<span class="ns-chip">{html.escape(t("sources.week", lang, n=week))}</span>'
            for week in snapshot["weeks"]
        )
        sidebar.markdown(
            f'<div class="ns-stat" style="padding-bottom:0.1rem;">'
            f'<span class="ns-stat__label">'
            f'{html.escape(t("progress.weeks", lang))}</span></div>'
            f'<div class="ns-chips">{chips}</div>',
            unsafe_allow_html=True,
        )

    sidebar.markdown(
        f'<div class="ns-stat" style="padding-bottom:0;margin-top:0.6rem;">'
        f'<span class="ns-stat__label">'
        f'{html.escape(t("progress.mix", lang))}</span></div>'
        f'{confidence_mix_html(snapshot["mix"])}',
        unsafe_allow_html=True,
    )



#the tutor answers questions the student brings. The quiz is the other direction: the student asks to be tested. Carpenter et al. (2022) find
#retrieval practice outperforms passive review, and Bego et al. (2024) replicate that in undergraduate STEM courses, so a study tool that can only be
#asked things is leaving its most effective mode unavailable. State lives in st.session_state under quiz_* keys and moves through three stages: setup,
#running, results. Generation happens once, on the transition out of setup, so the questions do not change under the student mid attempt.



def init_quiz_state() -> None:
    """
    Quiz state, separate from the conversation state.

    quiz_stage      "setup", "running" or "results"
    quiz_questions  the generated items for the current attempt
    quiz_answers    {question index: chosen label}
    quiz_revealed   indices whose answer has been shown, practice mode only
    quiz_index      the item currently on screen
    quiz_deadline   wall-clock time the exam ends, or None outside exam mode
    quiz_config     the settings the attempt was generated with
    """
    defaults = {
        "quiz_stage": "setup",
        "quiz_questions": [],
        "quiz_answers": {},
        "quiz_revealed": set(),
        "quiz_index": 0,
        "quiz_deadline": None,
        "quiz_config": {},
        "quiz_result": None,
        "quiz_notice": None,
        "quiz_history_view": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_quiz() -> None:
    """Return to the setup screen, discarding the current attempt."""
    st.session_state.quiz_stage = "setup"
    st.session_state.quiz_questions = []
    st.session_state.quiz_answers = {}
    st.session_state.quiz_revealed = set()
    st.session_state.quiz_index = 0
    st.session_state.quiz_deadline = None
    st.session_state.quiz_result = None
    st.session_state.quiz_notice = None
    st.session_state.quiz_history_view = None


def finish_quiz() -> None:
    """
    Score the attempt, record it, and move to the results screen.

    The attempt is written here rather than on the results screen because the
    results screen re-renders on every interaction, and recording there would
    log the same quiz again each time the student expanded the review.
    """
    result = score_quiz(
        st.session_state.quiz_questions, st.session_state.quiz_answers
    )
    st.session_state.quiz_result = result
    st.session_state.quiz_stage = "results"
    st.session_state.quiz_deadline = None

    quiz.record_attempt(result, st.session_state.quiz_config,
                        i18n.current_language())


def render_quiz_setup(lang: str, groq_client, collection) -> None:
    """
    The setup screen.

    Difficulty and mode use segmented controls rather than checkboxes. The
    behaviour asked for was that selecting one option clears the others, which
    is single selection, and a segmented control gives exactly that while still
    announcing itself correctly to a screen reader. Three checkboxes wired to
    clear one another would look the same and read as three independent
    yes/no choices to anyone not using a mouse, which would undo the
    accessibility work in the accessibility design.
    """
    st.markdown(
        f'<p class="ns-quiz-eyebrow">{html.escape(t("quiz.title", lang))}</p>'
        f'<p class="ns-masthead__sub" style="margin-top:0;">'
        f'{html.escape(t("quiz.intro", lang))}</p>',
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        st.markdown(
            f'<p class="ns-setup-label">{html.escape(t("quiz.difficulty", lang))}</p>',
            unsafe_allow_html=True,
        )
        difficulty = st.segmented_control(
            t("quiz.difficulty", lang),
            options=list(quiz.DIFFICULTIES),
            format_func=lambda d: t(f"quiz.difficulty.{d}", lang),
            default=st.session_state.get("quiz_difficulty", "medium"),
            key="quiz_difficulty",
            label_visibility="collapsed",
            width="stretch",
        ) or "medium"
        st.markdown(
            f'<p class="ns-setup-hint">'
            f'{html.escape(t(f"quiz.difficulty.{difficulty}_help", lang))}</p>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            f'<p class="ns-setup-label">{html.escape(t("quiz.mode", lang))}</p>',
            unsafe_allow_html=True,
        )
        mode = st.segmented_control(
            t("quiz.mode", lang),
            options=list(quiz.MODES),
            format_func=lambda m: t(f"quiz.mode.{m}", lang),
            default=st.session_state.get("quiz_mode", "practice"),
            key="quiz_mode",
            label_visibility="collapsed",
            width="stretch",
        ) or "practice"
        st.markdown(
            f'<p class="ns-setup-hint">'
            f'{html.escape(t(f"quiz.mode.{mode}_help", lang))}</p>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<p class="ns-setup-label">{html.escape(t("quiz.count", lang))}</p>',
        unsafe_allow_html=True,
    )
    count = st.slider(
        t("quiz.count", lang),
        min_value=quiz.MIN_QUESTIONS,
        max_value=quiz.MAX_QUESTIONS,
        value=st.session_state.get("quiz_count", quiz.DEFAULT_QUESTIONS),
        key="quiz_count",
        label_visibility="collapsed",
        help=t("quiz.count_help", lang),
    )

    st.markdown(
        f'<p class="ns-setup-label">{html.escape(t("quiz.topics", lang))}</p>'
        f'<p class="ns-setup-hint">{html.escape(t("quiz.topics_help", lang))}</p>',
        unsafe_allow_html=True,
    )
    topics = st.multiselect(
        t("quiz.topics", lang),
        options=quiz.all_topic_keys(),
        format_func=lambda k: (
            f"W{quiz.topic_week(k)}  {t(f'quiz.topic.{k}', lang)}"
        ),
        default=st.session_state.get("quiz_topics", []),
        key="quiz_topics",
        label_visibility="collapsed",
        placeholder=t("quiz.topics_all", lang),
    )

    #Immediate reveal is a practice-mode affordance only. In exam mode the control is disabled rather than hidden, so the option stays discoverable
    #and the reason it is unavailable is stated next to it.
    #
    #The toggle is driven through session state rather than a value= argument. Streamlit gives a widget's stored key precedence over value=, so
    #passing both left the control switched on but greyed out in exam mode, which reads as "this is active and you may not change it" rather than
    #"this does not apply here". It is forced off on the transition into exam mode and restored to the student's practice preference on the way back
    #out, and between those transitions the widget owns its own state.
    exam = (mode == "exam")
    if "quiz_reveal" not in st.session_state:
        st.session_state["quiz_reveal"] = True
    if st.session_state.get("quiz_last_mode") != mode:
        st.session_state["quiz_last_mode"] = mode
        st.session_state["quiz_reveal"] = (
            False if exam else st.session_state.get("quiz_reveal_pref", True)
        )

    reveal = st.toggle(
        t("quiz.reveal", lang),
        key="quiz_reveal",
        disabled=exam,
        help=t("quiz.reveal_help", lang),
    )
    if not exam:
        st.session_state["quiz_reveal_pref"] = reveal
    if exam:
        minutes = quiz.estimated_seconds(count) // 60
        st.caption(f"{t('quiz.reveal_exam_note', lang)}  "
                   f"{t('quiz.time_left', lang)}: {minutes} min.")

    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)

    if st.button(t("quiz.start", lang), type="primary", key="quiz_start"):
        chosen = topics or quiz.all_topic_keys()
        status = st.empty()

        def report(done: int, target: int) -> None:
            #a long quiz is generated in batches, so without this the student watches a motionless spinner for the better part of a minute
            status.caption(t("quiz.generating_n", lang, n=done, total=target))

        try:
            with st.spinner(t("quiz.generating", lang)):
                questions = quiz.generate_quiz(
                    groq_client, collection, chosen, difficulty, count,
                    language_clause=answer_language_instruction(lang),
                    progress=report,
                )
        except quiz.QuizGenerationError as error:
            #the reason is classified in quiz.py and translated here, so a rate limit does not read the same as a bad key. the previous version
            #reported one generic sentence for every failure, which was true and told nobody anything
            status.empty()
            st.error(t(f"quiz.err.{error}", lang))
            return
        status.empty()

        st.session_state.quiz_questions = questions
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.session_state.quiz_index = 0
        st.session_state.quiz_result = None
        st.session_state.quiz_config = {
            "difficulty": difficulty,
            "mode": mode,
            "count": len(questions),
            "reveal": bool(st.session_state.get("quiz_reveal")) and not exam,
            "topics": chosen,
        }
        st.session_state.quiz_notice = (
            t("quiz.short", lang, n=len(questions))
            if len(questions) < count else None
        )
        st.session_state.quiz_deadline = (
            time.time() + quiz.estimated_seconds(len(questions))
            if exam else None
        )
        st.session_state.quiz_stage = "running"
        st.rerun()

    render_quiz_history(lang)


def quiz_review_cards(review: list[dict], lang: str) -> str:
    """
    Render a scored attempt as review cards.

    Shared by the results screen and the history, so a quiz reopened a week
    later looks exactly like it did the moment it was finished. The cards are
    the same ones the prerequisite probe uses, which keeps one visual language
    for "here is what you got wrong and why" across the whole application.
    """
    labels = {
        "you_chose": t("quiz.your_answer", lang),
        "correct": t("quiz.correct_answer", lang),
        "no_answer": t("quiz.no_answer", lang),
    }
    return "".join(
        review_item_html(
            {
                "number": item.get("number", index + 1),
                "question": item.get("question", ""),
                "chosen_label": item.get("chosen") or "-",
                "chosen_text": item.get("chosen_text") or "",
                "answer_label": item.get("answer", ""),
                "answer_text": item.get("answer_text", ""),
                "explanation": item.get("explanation", ""),
            },
            labels,
            correct=bool(item.get("correct")),
            week_note=(t("quiz.from_week", lang, n=item["week"])
                       if item.get("week") else None),
        )
        for index, item in enumerate(review)
    )




def render_history_review(lang: str) -> None:
    """One past attempt, reopened from the history."""
    attempt = st.session_state.get("quiz_history_view")
    if not attempt:
        return

    percentage = attempt.get("percentage") or 0
    band = quiz.band_for_percentage(percentage)
    colour = band_colour(band)
    when = str(attempt.get("timestamp", ""))[:16].replace("T", "  ")

    st.markdown(
        f'<p class="ns-quiz-eyebrow">'
        f'{html.escape(t("quiz.history_viewing", lang, when=when))}</p>'
        f'<div class="ns-result">'
        f'  <p class="ns-result__score" style="color:{colour};">'
        f'{percentage:.0f}%</p>'
        f'  <p class="ns-result__of">'
        f'{html.escape(t("quiz.score_line", lang, score=attempt.get("score", 0), total=attempt.get("total", 0)))}'
        f'</p>'
        f'  <span class="ns-result__bar"><span class="ns-result__fill" '
        f'style="width:{percentage:.1f}%;background:{colour};"></span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.caption(t("quiz.summary_line", lang,
                 count=attempt.get("total", 0),
                 difficulty=t(f"quiz.difficulty.{attempt.get('difficulty','medium')}", lang),
                 mode=t(f"quiz.mode.{attempt.get('mode','practice')}", lang)))

    review = attempt.get("review") or []
    if review:
        st.markdown(quiz_review_cards(review, lang), unsafe_allow_html=True)
    else:
        #attempts recorded before the questions were kept carry a score only
        st.info(t("quiz.history_no_review", lang))

    if st.button(t("quiz.history_back", lang), key="quiz_history_back",
                 type="primary"):
        st.session_state["quiz_history_view"] = None
        st.rerun()


def render_quiz_history(lang: str, limit: int = 8) -> None:
    """
    Completed attempts, listed under the start button.

    Spaced retrieval practice only works if it is actually repeated
    (Carpenter et al., 2022; Bego et al., 2024), and a student cannot judge
    whether they are improving, or which difficulty they have been avoiding,
    from memory alone. The score leads each row and is drawn in the same band
    colours the rest of the interface uses, so the column can be read down
    without parsing the text beside it.
    """
    #an attempt opened for review takes over the panel, rather than expanding in place, so a twenty question review does not push the setup controls off the screen
    if st.session_state.get("quiz_history_view"):
        render_history_review(lang)
        return

    rows = quiz.load_history()
    st.markdown(
        f'<p class="ns-section" style="margin-top:1.4rem;">'
        f'{html.escape(t("quiz.history", lang))}</p>',
        unsafe_allow_html=True,
    )

    if not rows:
        st.markdown(
            f'<p class="ns-setup-hint">{html.escape(t("quiz.history_empty", lang))}</p>',
            unsafe_allow_html=True,
        )
        return

    summary = quiz.history_summary(rows)

    #each row needs its own button, so the list cannot be one markdown blob any more. the row itself stays as markup and the control sits beside it in
    #a narrow column, which keeps the score column aligned down the page
    for index, row in enumerate(rows[:limit]):
        percentage = row.get("percentage") or 0
        band = quiz.band_for_percentage(percentage)
        colour = band_colour(band)

        when = str(row.get("timestamp", ""))[:16].replace("T", "  ")
        difficulty = t(f"quiz.difficulty.{row.get('difficulty', 'medium')}", lang)
        mode = t(f"quiz.mode.{row.get('mode', 'practice')}", lang)
        count = t("quiz.history_count", lang, n=row.get("total", 0))

        detail, action = st.columns([5, 1])
        with detail:
            st.markdown(
                f'<div class="ns-hist">'
                f'  <span class="ns-hist__score" style="color:{colour};'
                f'background:{ui_theme.band_tint(band)};border-color:{colour};">'
                f'{row.get("score", 0)}/{row.get("total", 0)}</span>'
                f'  <span class="ns-hist__meta">{html.escape(difficulty)} · '
                f'{html.escape(mode)} · {html.escape(count)}</span>'
                f'  <span class="ns-hist__when">{html.escape(when)}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with action:
            #the identifier falls back to the index for attempts recorded before ids were written, so an old history still gets its buttons
            key = row.get("id") or f"legacy{index}"
            if st.button(t("quiz.history_review", lang),
                         key=f"quiz_review_{key}", use_container_width=True):
                st.session_state["quiz_history_view"] = row
                st.rerun()

    tail = ""
    if len(rows) > limit:
        tail = (f'<p class="ns-setup-hint" style="margin-top:0.2rem;">'
                f'{html.escape(t("quiz.history_more", lang, n=len(rows) - limit))}</p>')

    st.markdown(
        tail +
        f'<div class="ns-hist-summary">'
        f'<span>{html.escape(t("quiz.history_attempts", lang))}: '
        f'<b>{summary["attempts"]}</b></span>'
        f'<span>{html.escape(t("quiz.history_average", lang))}: '
        f'<b>{summary["average"]:.0f}%</b></span>'
        f'<span>{html.escape(t("quiz.history_best", lang))}: '
        f'<b>{summary["best"]:.0f}%</b></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if st.button(t("quiz.history_clear", lang), key="quiz_clear_history",
                 type="tertiary"):
        quiz.clear_history()
        st.rerun()


@st.fragment(run_every="1s")
def render_quiz_timer(lang: str) -> None:
    """
    Exam countdown.

    Runs as an auto-refreshing fragment so that only the timer re-renders each
    second. Re-running the whole script every second would reset the radio
    group holding the student's current answer.

    The remaining time is recomputed from a wall-clock deadline rather than
    decremented, so a slow rerun or a moment of network trouble cannot give the
    student extra time.
    """
    deadline = st.session_state.get("quiz_deadline")
    if not deadline:
        return

    remaining = int(deadline - time.time())
    if remaining <= 0:
        finish_quiz()
        st.rerun()
        return

    minutes, seconds = divmod(remaining, 60)
    total = quiz.estimated_seconds(len(st.session_state.quiz_questions)) or 1
    low = remaining <= max(30, total * 0.2)

    band = "Low" if low else "High"
    colour = band_colour(band)
    st.markdown(
        f'<span class="ns-timer" style="color:{colour};'
        f'background:{ui_theme.band_tint(band)};'
        f'border-color:{colour};">'
        f'<span class="ns-timer__mark" aria-hidden="true">'
        f'{BAND_STYLE[band]["marker"]}</span>'
        f'{html.escape(t("quiz.time_left", lang))} {minutes:d}:{seconds:02d}'
        f'</span>',
        unsafe_allow_html=True,
    )


def render_quiz_running(lang: str) -> None:
    """One question at a time, with the controls the chosen mode allows."""
    questions = st.session_state.quiz_questions
    config = st.session_state.quiz_config
    index = st.session_state.quiz_index
    question = questions[index]
    total = len(questions)
    exam = config.get("mode") == "exam"
    reveal_enabled = config.get("reveal", False)
    revealed = index in st.session_state.quiz_revealed

    if st.session_state.quiz_notice:
        st.info(st.session_state.quiz_notice)

    head, timer = st.columns([3, 2])
    with head:
        st.markdown(
            f'<p class="ns-quiz-eyebrow">'
            f'{html.escape(t("quiz.progress", lang, i=index + 1, n=total))}</p>',
            unsafe_allow_html=True,
        )
    with timer:
        if exam:
            render_quiz_timer(lang)

    pct = (index / total) * 100
    st.markdown(
        f'<div class="ns-progress"><span class="ns-progress__fill" '
        f'style="width:{pct:.1f}%;"></span></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<p class="ns-quiz-q">{html.escape(question["question"])}</p>',
        unsafe_allow_html=True,
    )

    labels = list(question["options"].keys())
    stored = st.session_state.quiz_answers.get(index)
    choice = st.radio(
        t("quiz.progress", lang, i=index + 1, n=total),
        options=labels,
        format_func=lambda k: f"{k})  {question['options'][k]}",
        index=labels.index(stored) if stored in labels else None,
        key=f"quiz_choice_{index}",
        label_visibility="collapsed",
        disabled=revealed,
    )
    if choice and not revealed:
        st.session_state.quiz_answers[index] = choice

    # Feedback, practice mode only and only once the item has been checked.
    if revealed:
        correct = st.session_state.quiz_answers.get(index) == question["answer"]
        marker = ui_theme.CORRECT_MARK if correct else ui_theme.INCORRECT_MARK
        label = t("quiz.was_correct" if correct else "quiz.was_incorrect", lang)
        band = "High" if correct else "Low"
        st.markdown(
            f'<div class="ns-review__row" style="'
            f'color:{band_colour(band)};'
            f'background:{ui_theme.band_tint(band)};'
            f'border-left-color:{band_colour(band)};margin-top:0.6rem;">'
            f'<span class="ns-review__mark">{marker}</span>'
            f'<span class="ns-review__text"><strong>{html.escape(label)}.</strong> '
            f'{html.escape(t("quiz.correct_answer", lang))}: '
            f'<strong>{question["answer"]})</strong> '
            f'{html.escape(question["options"][question["answer"]])}</span></div>'
            f'<p class="ns-review__why">{html.escape(question["explanation"])}</p>',
            unsafe_allow_html=True,
        )
        if question.get("week"):
            st.caption(t("quiz.from_week", lang, n=question["week"]))

    st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

    last = index == total - 1
    check_col, next_col, _spacer, quit_col = st.columns([1.2, 1.3, 1.5, 1.1])

    with check_col:
        if reveal_enabled and not revealed:
            if st.button(t("quiz.check", lang), key=f"quiz_check_{index}",
                         use_container_width=True):
                if st.session_state.quiz_answers.get(index) is None:
                    st.warning(t("quiz.pick_one", lang))
                else:
                    st.session_state.quiz_revealed.add(index)
                    st.rerun()

    with next_col:
        advance_label = t("quiz.finish" if last else "quiz.next", lang)
        if st.button(advance_label, type="primary", key=f"quiz_next_{index}",
                     use_container_width=True):
            #An unanswered item is allowed to pass. Forcing an answer would turn a "not sure" into a guess, and score_quiz() already counts an omission as incorrect.
            if last:
                finish_quiz()
            else:
                st.session_state.quiz_index += 1
            st.rerun()

    with quit_col:
        if st.button(t("quiz.abandon", lang), key=f"quiz_quit_{index}",
                     use_container_width=True):
            reset_quiz()
            st.rerun()


def render_quiz_results(lang: str) -> None:
    """Score, then every question reviewed with its explanation and source."""
    result = st.session_state.quiz_result
    config = st.session_state.quiz_config
    band = quiz.band_for_percentage(result["percentage"])
    colour = band_colour(band)

    st.markdown(
        f'<div class="ns-result">'
        f'  <p class="ns-quiz-eyebrow" style="margin-bottom:0.5rem;">'
        f'{html.escape(t("quiz.results", lang))}</p>'
        f'  <p class="ns-result__score" style="color:{colour};">'
        f'{result["percentage"]:.0f}%</p>'
        f'  <p class="ns-result__of">'
        f'{html.escape(t("quiz.score_line", lang, score=result["score"], total=result["total"]))}'
        f'</p>'
        f'  <span class="ns-result__bar"><span class="ns-result__fill" '
        f'style="width:{result["percentage"]:.1f}%;background:{colour};"></span></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    unanswered = sum(1 for item in result["review"] if item["chosen"] is None)
    summary = t("quiz.summary_line", lang,
                count=result["total"],
                difficulty=t(f"quiz.difficulty.{config.get('difficulty','medium')}", lang),
                mode=t(f"quiz.mode.{config.get('mode','practice')}", lang))
    if unanswered:
        summary += "  ·  " + t("quiz.unanswered", lang, n=unanswered)
    st.caption(summary)

    with st.expander(t("quiz.review", lang), expanded=True):
        st.markdown(quiz_review_cards(result["review"], lang),
                    unsafe_allow_html=True)

    again, back = st.columns([1, 1])
    with again:
        if st.button(t("quiz.retry", lang), type="primary", key="quiz_again",
                     use_container_width=True):
            reset_quiz()
            st.rerun()
    with back:
        if st.button(t("nav.tutor", lang), key="quiz_to_tutor",
                     use_container_width=True):
            #The mode is requested rather than set. The sidebar picker is a widget that was already instantiated earlier in this run, so its stored
            #value cannot be written here, and setting app_mode alone would simply be overridden by the picker on the next pass, which sent this
            #button back to the quiz setup screen instead of the chat. main() applies the request before the picker is built.
            reset_quiz()
            st.session_state["pending_mode"] = "tutor"
            st.rerun()


def render_quiz(lang: str, groq_client, collection) -> None:
    """Dispatch to the stage the attempt is currently in."""
    init_quiz_state()
    stage = st.session_state.quiz_stage

    if stage == "running" and st.session_state.quiz_questions:
        render_quiz_running(lang)
    elif stage == "results" and st.session_state.quiz_result:
        render_quiz_results(lang)
    else:
        render_quiz_setup(lang, groq_client, collection)


#Submission



def handle_submission(prompt: str, lang: str) -> None:
    """
    Process one student message: guards, prerequisite detection, then queue it
    for the pipeline.

    The two guards run before anything that costs an API call, which is their
    point. They live in the interface layer so that the evaluated pipeline in
    generate_answer.py is unchanged by them.
    """
    prompt = prompt.strip()
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})

    #A single bare interrogative ("how", "why", "perché") is treated as a follow-up when the thread already holds an answer to follow up on, and is
    #otherwise intercepted with a clarification request, since with an empty thread retrieval has nothing to anchor to.
    if is_bare_interrogative(prompt, lang) and not has_prior_answer():
        st.session_state.messages.append({
            "role": "assistant",
            "id": uuid.uuid4().hex,
            "content": t("guard.bare", lang, msg=prompt),
        })
        st.rerun()

    #Interjections never reach the pipeline: a deterministic canned reply is appended instead.
    if is_non_question(prompt, lang):
        st.session_state.messages.append({
            "role": "assistant",
            "id": uuid.uuid4().hex,
            "content": t("guard.non_question", lang, msg=prompt),
        })
        st.rerun()

    #Prerequisite detection matches an English keyword graph, so a non-English question is rendered into English first. to_english() is memoised on
    #the question text, so the same call inside run_pipeline() is free.
    english_prompt, _ = to_english(prompt, lang)

    #Fire a probe for any topic not already tested in this thread. The is_followup() guard that previously sat here was removed as part of it was
    #redundant, since a genuine follow-up such as "explain that more simply" names no topic and so detect_prerequisite returns None anyway, and it
    #actively suppressed the probe for short opening questions. The tested_topics check alone does the work, and ensures a student is probed once per
    #topic rather than repeatedly.
    topic = detect_prerequisite(english_prompt)
    if topic and topic not in st.session_state.tested_topics:
        st.session_state.pending_topic = topic

    st.session_state.pending_question = prompt
    st.rerun()


#Main


def main() -> None:
    init_state()
    inject_css()

    #A mode change requested from inside the page (the "Tutor" button on the quiz results) is applied here, before render_sidebar() instantiates the
    #picker. Streamlit refuses a write to a widget's key once that widget has been created in the current run, so the request has to be honoured at
    #the top of the next one; both keys are set together so the picker and the active mode cannot disagree.
    pending_mode = st.session_state.pop("pending_mode", None)
    if pending_mode:
        st.session_state["app_mode"] = pending_mode
        st.session_state["app_mode_picker"] = pending_mode

    lang = i18n.current_language()

    collection = load_collection()
    groq_client = load_groq_client()

    render_masthead(lang)
    render_sidebar(lang)

    #The sidebar's language control writes st.session_state["language"] directly, so a change made this run is already visible. Re-read it after the
    #sidebar so the thread below renders in the newly chosen language on the same pass rather than one interaction late.
    lang = i18n.current_language()

    if st.session_state.get("app_mode") == "quiz":
        render_quiz(lang, groq_client, collection)
        return

    if not st.session_state.messages and not st.session_state.pending_topic:
        render_welcome(lang)

    render_thread(lang)

    #A prerequisite probe is outstanding: show it and hold the question.
    if st.session_state.pending_topic:
        render_mcq_probe(st.session_state.pending_topic, lang)

    #A question is waiting on an answer, either fresh or released by a completed probe. Generate, append to the thread, then rerun so the turn renders
    #through the normal thread path rather than being drawn twice.
    elif st.session_state.pending_question:
        question = st.session_state.pending_question
        st.session_state.pending_question = None

        topic = detect_prerequisite(to_english(question, lang)[0])
        prereq = None
        simplify = False
        if topic and topic in st.session_state.tested_topics:
            prereq = st.session_state.tested_topics[topic]
            simplify = not prereq["passed"]

        with st.chat_message("assistant"):
            with st.spinner(t("chat.retrieving", lang)):
                result = run_pipeline(
                    question, groq_client, collection, simplify=simplify
                )

        st.session_state.messages.append({
            "role": "assistant",
            "id": uuid.uuid4().hex,
            "result": result,
            "prereq": prereq,
        })
        st.rerun()

    #The input is rendered on every pass, including immediately after an answer, so the conversation can always be continued. It is disabled only
    #while an MCQ probe is awaiting a response.
    typed = st.chat_input(
        t("chat.placeholder", lang),
        disabled=bool(st.session_state.pending_topic),
    )

    #A starter or follow-up button queues its text rather than calling the pipeline directly, so a clicked suggestion and a typed message take exactly
    #the same path through the guards and the probe.
    queued = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

    submitted = typed or queued
    if submitted:
        handle_submission(submitted, lang)


if __name__ == "__main__":
    main()


#References
#
#
#Lewis, P. et al. (2020). Retrieval-augmented generation for knowledge- intensive NLP tasks. NeurIPS.
#-RAG architecture underpinning the retrieval and generation pipeline.
#
#Sahoo, P. et al. (2024). A systematic survey of prompt engineering in large language models. arXiv:2402.07927.
#-Basis for the structured grounding prompt in build_prompt().
#
#Huang, L. et al. (2025). A survey on hallucination in large language models.
#
#ACM Transactions on Information Systems, 43(2).
#-Motivates the self-verification signal and the grounded-only constraint,
#and the decision to show the retrieved passages rather than only cite them.
#
#Zheng, L. et al. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. arXiv:2306.05685.
#-Documents the self-enhancement bias relevant to Signal 2.
#
#Kuzminykh, I. et al. (2021). Investigating threshold concept and troublesome knowledge in cyber security. OT4ME 2021.
#-Motivates the prerequisite check design, and the three-point rating
#scale: students cannot reliably self-diagnose, so "not sure" has to be an option.
#
#Carpenter, S. K. et al. (2022). The science of effective learning with spacing and retrieval practice. Nature Reviews Psychology, 1(9).
#-Rationale for the MCQ probe as retrieval practice, for firing it once
#per topic rather than repeatedly, and for offering a re-test on request.
#
#Mishra, P., Henriksen, D., Woo, L. J. and Oster, N. (2025). Control vs. agency: exploring the history of AI in education. TechTrends.
#-Positions prerequisite checking as a lever for preserving learner
#agency: a system that tests rather than assumes prior knowledge gives the student meaningful control over their trajectory.
#
#Xiao, H. et al. (2024). Analysis of student preference to group work assessment in cybersecurity courses. CSE4IA 2024.
#-Postgraduate cybersecurity students value feedback tied to their
#specific errors, motivating the explicit framing in the welcome panel.
#
#Tang, J. et al. (2025). RPKT: recursive prerequisite knowledge tracing in conversational AI tutors. arXiv:2508.11892.
#-The "unknown unknown" problem behind the session coverage summary.
#
#Klimova, B. (2025). Use of machine translation in foreign language education.
#
#Cogent Arts & Humanities, 12(1).
#-Motivates translating the interface in place rather than leaving
#students to round-trip through an external translator.
#
#Tol, P. (2021). Colour schemes. SRON Technical Note SRON/EPS/TN/09-002.
#-Source of the high-contrast palette. See ui_theme.py.
#
#World Health Organization (2023). Blindness and vision impairment: colour blindness.
#-Prevalence figures motivating the redundant encoding of the bands.
#
#W3C (2023). Web Content Accessibility Guidelines (WCAG) 2.2, Success Criterion 1.4.1 Use of Colour.
#-Requirement that colour is not the only visual means of conveying
#information, satisfied here by the marker, the label and the meter.
#
#Groq (n.d.). GroqCloud. https://console.groq.com [Accessed July 2026]
#-Inference API used to run the generation model. The primary evaluation
#(the gold set chapter) was run on Llama 3.1 8B Instant; that model was decommissioned during the evaluation period and the system now runs
#gpt-oss-20b, with the migration reported in the results chapter. The model in use is config.GROQ_MODEL.
