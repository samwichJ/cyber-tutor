'''
this .py holds the study facing layer that sits on top of the pipeline, the
suggested follow up questions, the session progress summary and the Markdown
export of a conversation

none of it is decorative, each one targets something from the literature review
that the plain retrieve then generate loop does not deal with on its own

follow up suggestions keep the student directing the enquiry instead of taking
one answer and stopping. Bastani et al. (2024) found students given an
unrestricted ChatGPT tutor outperformed a control group during practice and then
underperformed them on a later test without AI access, while a tutor with
built in safeguarding avoided that pattern, and Zhai et al. (2024) reach the
same conclusion across a wider literature. suggestions that push elaboration and
self testing are scaffolding rather than convenience

the progress summary makes coverage visible. Tang et al. (2025) describe the
"unknown unknown" problem, the student most in need of foundational correction
is precisely the one least equipped to go looking for it, and showing which
weeks a session has actually drawn on turns an invisible distribution into
something that can be looked at

export exists because the answers are revision material. Carpenter et al. (2022)
find retrieval practice beats passive review, and a conversation that disappears
when the tab closes cannot be come back to and practised against. the export
carries each answer's confidence band and sources with it, so the caveats travel
with the content instead of being stripped off by a copy and paste
'''

from __future__ import annotations

from datetime import datetime

from config import CONF_MEDIUM_THRESHOLD
from ui.i18n import t, topic_label
from ui.ui_theme import BAND_ORDER, BAND_STYLE

#Relevance presentation

#Cosine distance floor and ceiling used to turn a raw distance into the 0-1 figure shown on a source card.
_DISTANCE_FLOOR = 0.45
_DISTANCE_CEILING = CONF_MEDIUM_THRESHOLD + 0.30


def relevance(distance: float) -> float:
    """
    Map a cosine distance to a 0-1 figure for display.

    Presentational only. The confidence band is computed from raw mean distance
    in generate_answer.confidence_band() and is not derived from this; the two
    must not be confused, which is why this lives here rather than in the
    pipeline. The mapping is linear and its endpoints are stated above so the
    bar can be read against the thresholds in config.py rather than as an
    unexplained score.
    """
    span = _DISTANCE_CEILING - _DISTANCE_FLOOR
    return max(0.0, min(1.0, (_DISTANCE_CEILING - distance) / span))


#Follow-up suggestions


def suggest_followups(result: dict, lang: str,
                      prereq_topic: str | None = None,
                      already_tested: bool = False) -> list[dict]:
    """
    Propose up to three next moves after an answer.

    Each returned item is {"label", "prompt", "kind"}. "label" is what the
    button shows, "prompt" is the message submitted if it is clicked, and "kind"
    lets the caller special-case the retrieval-practice suggestion, which
    reopens a prerequisite probe instead of asking a question.

    Selection is conditioned on the confidence band. After a Low-band answer the
    worked-example suggestion is withheld: the band means the retrieved material
    was thin, and inviting the model to produce a concrete example from thin
    evidence is inviting it to invent one. That is the hallucination pathway
    Huang et al. (2025) describe, and it would be perverse for the interface to
    steer a student towards it precisely when the system has just said its
    evidence is weak. Simplification and connecting to a neighbouring topic stay
    available, because both are answerable from the material already retrieved.
    """
    suggestions: list[dict] = []
    band = result.get("confidence", "Medium")
    sources = result.get("sources", [])

    #Always available.
    suggestions.append({
        "label":  t("followups.simpler", lang),
        "prompt": t("followups.simpler", lang),
        "kind":   "simpler",
    })

    if band != "Low":
        suggestions.append({
            "label":  t("followups.example", lang),
            "prompt": t("followups.example", lang),
            "kind":   "example",
        })

    #A neighbouring topic drawn from the retrieved chunks.
    primary = sources[0]["topic"] if sources else None
    neighbour = next(
        (s["topic"] for s in sources if s["topic"] and s["topic"] != primary),
        None,
    )
    if neighbour:
        suggestions.append({
            "label":  t("followups.relate", lang, topic=neighbour),
            "prompt": t("followups.relate", lang, topic=neighbour),
            "kind":   "relate",
        })

    #Retrieval practice on the underlying prerequisite, offered only where one exists and has not already been probed in this thread.
    if prereq_topic and not already_tested:
        suggestions.append({
            "label":  t("followups.test_me", lang, topic=topic_label(prereq_topic, lang)),
            "prompt": prereq_topic,
            "kind":   "test_me",
        })

    return suggestions[:3]


#Session progress

def progress_snapshot(messages: list[dict]) -> dict:
    """
    Summarise the active thread.

    Weeks and topics are read from the retrieved sources rather than from the
    questions asked, because what a student typed is not evidence of what the
    material covered: a question phrased around Week 5 vocabulary may well have
    been answered from Week 2 chunks. The sources are what the answer was
    actually built from, so they are what coverage should be counted from.
    """
    questions = sum(1 for m in messages if m["role"] == "user")
    answers = [m["result"] for m in messages
               if m["role"] == "assistant" and "result" in m]

    weeks: set = set()
    topics: set = set()
    mix = {band: 0 for band in BAND_ORDER}
    latencies: list[float] = []

    for result in answers:
        mix[result.get("confidence", "Low")] = \
            mix.get(result.get("confidence", "Low"), 0) + 1
        latencies.append(result.get("latency_seconds", 0) or 0)
        for source in result.get("sources", []):
            if source.get("week") not in (None, ""):
                weeks.add(str(source["week"]))
            if source.get("topic"):
                topics.add(source["topic"])

    return {
        "questions":    questions,
        "answers":      len(answers),
        "weeks":        sorted(weeks, key=lambda w: (len(w), w)),
        "topic_count":  len(topics),
        "mix":          mix,
        "avg_latency":  round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
    }


#Export

def conversation_markdown(messages: list[dict], lang: str,
                          tested_topics: dict | None = None) -> str:
    """
    Render a thread as a Markdown revision document.

    The confidence band and the source list travel with every answer. An export
    that stripped them would hand the student a document indistinguishable from
    notes taken from a textbook, when the whole argument of this system is that
    a generated answer should not be read as if it were one. The band is written
    out in words as well as with its marker glyph, so it survives being pasted
    into a plain-text editor.
    """
    lines: list[str] = [
        f"# {t('export.heading', lang)}",
        "",
        f"*{t('export.exported_on', lang)}: "
        f"{datetime.now().strftime('%d %B %Y, %H:%M')}*",
        "",
        f"> {t('export.disclaimer', lang)}",
        "",
        "---",
        "",
    ]

    for turn in messages:
        if turn["role"] == "user":
            lines += [f"## {t('export.you', lang)}", "", turn["content"], ""]
            continue

        lines.append(f"### {t('export.tutor', lang)}")
        lines.append("")

        if "result" not in turn:
            lines += [turn.get("content", ""), ""]
            continue

        result = turn["result"]
        band = result.get("confidence", "Low")
        marker = BAND_STYLE.get(band, {}).get("marker", "")
        lines.append(
            f"**{marker} {t(f'band.{band}', lang)} {t('band.confidence', lang)}** - "
            f"{t(f'band.{band}.text', lang)}"
        )
        lines += ["", result.get("answer", ""), ""]

        sources = result.get("sources", [])
        if sources:
            lines.append(f"**{t('sources.title', lang, n=len(sources))}**")
            lines.append("")
            for source in sources:
                lines.append(
                    f"- {t('sources.week', lang, n=source['week'])} - "
                    f"{source['topic']} *({source['artefact_type']})*, "
                    f"{t('sources.relevance', lang)} "
                    f"{relevance(source['distance']):.0%}"
                )
            lines.append("")

    if tested_topics:
        lines += ["---", "", f"## {t('sidebar.prereqs', lang)}", ""]
        for topic, record in tested_topics.items():
            state = t("prereq.state_passed" if record["passed"]
                      else "prereq.state_review", lang)
            lines.append(
                f"- {topic_label(topic, lang)}: "
                f"{record['score']}/{record['total']} ({state})"
            )
        lines.append("")

    return "\n".join(lines)


def export_filename() -> str:
    """Timestamped filename, so successive exports in one session do not collide."""
    return f"cyber-tutor-{datetime.now().strftime('%Y%m%d-%H%M')}.md"
