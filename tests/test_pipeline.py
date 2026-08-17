"""
test_pipeline.py
White-box unit tests for the deterministic components of the RAG pipeline, covering the confidence scoring, prerequisite detection,
MCQ scoring and response parsing logic

Only the deterministic functions are tested here. Anything that calls the Groq API is non-deterministic and is covered instead by the black-box
functional test table and by the gold set. Test design is equivalence partitioning plus boundary-value analysis, so each
function gets typical values from each partition and the exact boundaries where the behaviour changes.

Defect found by this suite:
test_two_of_three_passes_at_threshold failed on the first run. The pass mark was 0.67 but 2 out of 3 is 0.6667, which is strictly less, so a student
answering 2 of 3 correctly was failed and sent to a simplified explanation despite 2/3 being the intended pass mark. Corrected to 0.66. It was invisible
in manual testing because it only shows at the exact boundary, which is what boundary-value analysis is for

    py -m pytest tests/ -v
"""

import json

import pytest

from core.generate_answer import (
    confidence_band,
    compound_confidence,
    parse_answer_and_confidence,
    CONF_HIGH_THRESHOLD,
    CONF_MEDIUM_THRESHOLD,
)
from core.prerequisite_check import (
    detect_prerequisite,
    score_responses,
    prerequisite_passed,
    build_review,
    MCQ_BANK,
    DEPENDENCY_GRAPH,
)
from core import quiz
from core.quiz import validate_questions, score_quiz, band_for_percentage


#helpers

def make_chunks(distances: list[float]) -> list[dict]:
    """
    Build a minimal list of retrieved-chunk dicts with the given distances.
    Only the 'distance' key is read by confidence_band(), so the other fields
    are stubbed. This isolates the function under test from ChromaDB.
    """
    return [
        {
            "text": f"stub chunk {i}",
            "metadata": {
                "week": "1",
                "topic_label": "stub topic",
                "artefact_type": "lecture",
                "source_file": "stub.docx",
            },
            "distance": d,
        }
        for i, d in enumerate(distances)
    ]


#signal 1 - confidence_band(). partitions: mean dist < 0.85 (High) | < 1.10 (Medium) | >= 1.10 (Low)


class TestConfidenceBand:

    def test_low_mean_distance_returns_high(self):
        """Strong retrieval (all distances well below the High threshold)."""
        chunks = make_chunks([0.40, 0.45, 0.50, 0.55, 0.60])
        assert confidence_band(chunks) == "High"

    def test_mid_mean_distance_returns_medium(self):
        """Moderate retrieval, matching the observed stateful-firewall case."""
        chunks = make_chunks([1.00, 1.02, 1.09, 1.15, 1.20])
        assert confidence_band(chunks) == "Medium"

    def test_high_mean_distance_returns_low(self):
        """Weak retrieval, matching the observed CIA triad case (mean 1.183)."""
        chunks = make_chunks([1.07, 1.20, 1.21, 1.21, 1.21])
        assert confidence_band(chunks) == "Low"

    def test_boundary_just_below_high_threshold(self):
        """Boundary value: mean just under 0.85 must still be High."""
        chunks = make_chunks([0.84, 0.84, 0.84, 0.84, 0.84])
        assert confidence_band(chunks) == "High"

    def test_boundary_exactly_at_high_threshold_is_medium(self):
        """
        Boundary value: the comparison is strictly '<', so a mean of exactly
        0.85 falls into Medium, not High. This test pins that decision so a
        future refactor cannot silently flip it.
        """
        chunks = make_chunks([CONF_HIGH_THRESHOLD] * 5)
        assert confidence_band(chunks) == "Medium"

    def test_boundary_exactly_at_medium_threshold_is_low(self):
        """Boundary value: a mean of exactly 1.10 falls into Low."""
        chunks = make_chunks([CONF_MEDIUM_THRESHOLD] * 5)
        assert confidence_band(chunks) == "Low"

    def test_empty_chunk_list_returns_low(self):
        """
        Defensive case: no retrieved chunks must degrade to Low rather than
        raising a ZeroDivisionError on the mean calculation.
        """
        assert confidence_band([]) == "Low"

    def test_single_chunk_is_handled(self):
        """A single retrieved chunk should not break the mean calculation."""
        assert confidence_band(make_chunks([0.50])) == "High"


#compound_confidence() - conservative minimum rule

class TestCompoundConfidence:

    def test_both_signals_strong_gives_high(self):
        assert compound_confidence("High", 3) == "High"

    def test_both_signals_weak_gives_low(self):
        assert compound_confidence("Low", 1) == "Low"

    def test_strong_retrieval_weak_verify_downgrades_to_low(self):
        """
        Core design assertion: a strong Signal 1 must NOT override a poor
        Signal 2. This is the conservative-minimum rule that justifies the
        compound score.
        """
        assert compound_confidence("High", 1) == "Low"

    def test_weak_retrieval_strong_verify_stays_low(self):
        """
        The inverse: a self-verification score of 3 must not rescue a weak
        retrieval. This is the observed CIA triad case, where Signal 2
        returned 3 despite cross-week retrieval drift.
        """
        assert compound_confidence("Low", 3) == "Low"

    def test_medium_retrieval_with_partial_verify_gives_medium(self):
        assert compound_confidence("Medium", 2) == "Medium"

    def test_high_retrieval_with_partial_verify_gives_medium(self):
        assert compound_confidence("High", 2) == "Medium"

    def test_medium_retrieval_with_strong_verify_gives_medium(self):
        assert compound_confidence("Medium", 3) == "Medium"

    def test_unknown_band_defaults_to_low(self):
        """Defensive case: an unrecognised band must not raise."""
        assert compound_confidence("Unknown", 3) == "Low"

    @pytest.mark.parametrize("band,score,expected", [
        ("High",   3, "High"),
        ("High",   2, "Medium"),
        ("High",   1, "Low"),
        ("Medium", 3, "Medium"),
        ("Medium", 2, "Medium"),
        ("Medium", 1, "Low"),
        ("Low",    3, "Low"),
        ("Low",    2, "Low"),
        ("Low",    1, "Low"),
    ])
    def test_full_truth_table(self, band, score, expected):
        """
        Exhaustive check of all nine signal combinations. Documents the
        complete behaviour of the compound rule in a single test.
        """
        assert compound_confidence(band, score) == expected


#parse_answer_and_confidence() - merged single-call response parsing


class TestParseAnswerAndConfidence:

    def test_parses_well_formed_response(self):
        raw = "ARP spoofing poisons the ARP cache.\nCONFIDENCE: 3"
        answer, score = parse_answer_and_confidence(raw)
        assert score == 3
        assert "ARP spoofing poisons the ARP cache." in answer
        assert "CONFIDENCE" not in answer

    def test_confidence_line_is_stripped_from_answer(self):
        """The confidence marker must never be shown to the student."""
        raw = "Line one.\nLine two.\nCONFIDENCE: 2"
        answer, _ = parse_answer_and_confidence(raw)
        assert "CONFIDENCE" not in answer
        assert answer.endswith("Line two.")

    @pytest.mark.parametrize("digit", [1, 2, 3])
    def test_all_valid_scores_parse(self, digit):
        raw = f"Some answer text.\nCONFIDENCE: {digit}"
        _, score = parse_answer_and_confidence(raw)
        assert score == digit

    def test_missing_confidence_line_falls_back_to_two(self):
        """
        Fallback behaviour: if the model omits the CONFIDENCE line, the score
        degrades to 2 (partial) rather than defaulting to 3. A parse failure
        must never inflate confidence.
        """
        raw = "An answer with no confidence marker at all."
        answer, score = parse_answer_and_confidence(raw)
        assert score == 2
        assert answer == raw

    def test_malformed_confidence_line_falls_back_to_two(self):
        """A CONFIDENCE line with no valid digit must fall back to 2."""
        raw = "Some answer.\nCONFIDENCE: high"
        _, score = parse_answer_and_confidence(raw)
        assert score == 2

    def test_lowercase_confidence_marker_is_matched(self):
        """Matching is case-insensitive, so 'Confidence:' must still parse."""
        raw = "Some answer.\nConfidence: 3"
        _, score = parse_answer_and_confidence(raw)
        assert score == 3

    def test_multiline_answer_is_preserved(self):
        raw = "Para one.\n\nPara two.\n\nPara three.\nCONFIDENCE: 3"
        answer, score = parse_answer_and_confidence(raw)
        assert score == 3
        assert "Para one." in answer
        assert "Para three." in answer

    def test_trailing_whitespace_is_handled(self):
        raw = "  An answer.  \nCONFIDENCE: 1  \n\n  "
        answer, score = parse_answer_and_confidence(raw)
        assert score == 1
        assert answer.strip() == "An answer."


#detect_prerequisite() - keyword-based dependency detection


class TestDetectPrerequisite:

    def test_arp_spoofing_triggers_arp_prerequisite(self):
        assert detect_prerequisite("What is ARP spoofing?") == "ARP protocol"

    def test_syn_flood_triggers_tcp_prerequisite(self):
        assert detect_prerequisite("What is a SYN flood attack?") == "TCP handshake"

    def test_stateful_firewall_triggers_firewall_prerequisite(self):
        result = detect_prerequisite("What is a stateful firewall?")
        assert result == "packet filter firewall"

    def test_detection_is_case_insensitive(self):
        """Students type in mixed case; detection must not depend on it."""
        assert detect_prerequisite("WHAT IS ARP SPOOFING") == "ARP protocol"
        assert detect_prerequisite("what is arp spoofing") == "ARP protocol"

    def test_basic_question_triggers_no_prerequisite(self):
        """A foundational question must not gate behind an MCQ probe."""
        assert detect_prerequisite("What is a firewall?") is None

    def test_cia_triad_triggers_no_prerequisite(self):
        assert detect_prerequisite("What is the CIA triad?") is None

    def test_empty_question_returns_none(self):
        """Defensive case: empty input must not raise."""
        assert detect_prerequisite("") is None

    def test_keyword_embedded_in_sentence_is_detected(self):
        """Substring matching must find the keyword mid-sentence."""
        q = "Can you explain how an attacker performs arp spoofing on a LAN?"
        assert detect_prerequisite(q) == "ARP protocol"

    def test_known_limitation_paraphrase_is_missed(self):
        """
        Documents a known limitation rather than a bug: keyword matching
        cannot detect a paraphrase that avoids the trigger terms. This is
        reported in the limitations and listed as future work
        (semantic detection).
        """
        q = "How can someone poison the table that maps IPs to hardware addresses?"
        assert detect_prerequisite(q) is None

    @pytest.mark.parametrize("topic", set(DEPENDENCY_GRAPH.values()))
    def test_every_graph_topic_has_an_mcq_bank_entry(self, topic):
        """
        Integrity check: every prerequisite topic referenced by the dependency
        graph must have questions in the MCQ bank, or the probe would fire
        with nothing to ask.
        """
        assert topic in MCQ_BANK
        assert len(MCQ_BANK[topic]) > 0


#score_responses() and prerequisite_passed()


class TestScoreResponses:

    def test_all_correct_scores_full_marks(self):
        topic = "ARP protocol"
        correct = [q["answer"] for q in MCQ_BANK[topic]]
        score, total = score_responses(topic, correct)
        assert score == total == 3

    def test_all_wrong_scores_zero(self):
        topic = "ARP protocol"
        # Pick a deliberately wrong option for each question
        wrong = [
            next(o for o in q["options"] if o != q["answer"])
            for q in MCQ_BANK[topic]
        ]
        score, total = score_responses(topic, wrong)
        assert score == 0
        assert total == 3

    def test_partial_score_is_counted_correctly(self):
        topic = "TCP handshake"
        answers = [q["answer"] for q in MCQ_BANK[topic]]
        # Corrupt the last answer only, expecting 2/3
        answers[-1] = next(
            o for o in MCQ_BANK[topic][-1]["options"]
            if o != MCQ_BANK[topic][-1]["answer"]
        )
        score, total = score_responses(topic, answers)
        assert (score, total) == (2, 3)

    def test_lowercase_responses_are_scored(self):
        """Responses are upper-cased before comparison, so 'b' must match 'B'."""
        topic = "ARP protocol"
        lower = [q["answer"].lower() for q in MCQ_BANK[topic]]
        score, total = score_responses(topic, lower)
        assert score == total

    def test_unknown_topic_returns_zero_total(self):
        """Defensive case: an unrecognised topic must not raise."""
        score, total = score_responses("not a real topic", ["A"])
        assert (score, total) == (0, 0)


class TestPrerequisitePassed:

    def test_three_of_three_passes(self):
        assert prerequisite_passed(3, 3) is True

    def test_two_of_three_passes_at_threshold(self):
        """
        Boundary value, and the test that exposed the pass-threshold defect.

        2/3 evaluates to 0.6667. With the original threshold of 0.67 this
        comparison returned False, so a student answering 2 of 3 correctly was
        incorrectly failed and routed to a simplified explanation, despite 2/3
        being the intended pass mark. The threshold was corrected to 0.66.
        """
        assert prerequisite_passed(2, 3) is True

    def test_one_of_three_fails(self):
        assert prerequisite_passed(1, 3) is False

    def test_zero_of_three_fails(self):
        assert prerequisite_passed(0, 3) is False

    def test_zero_total_does_not_block(self):
        """
        Defensive case: if a topic has no questions, the student must not be
        blocked, and the division must not raise.
        """
        assert prerequisite_passed(0, 0) is True

    def test_custom_threshold_is_respected(self):
        """A stricter threshold must reject a score the default would accept."""
        assert prerequisite_passed(2, 3, threshold=0.9) is False
        assert prerequisite_passed(3, 3, threshold=0.9) is True


#build_review() - post-probe feedback


class TestBuildReview:

    def test_review_has_one_entry_per_question(self):
        topic = "ARP protocol"
        correct = [q["answer"] for q in MCQ_BANK[topic]]
        review = build_review(topic, correct)
        assert len(review) == len(MCQ_BANK[topic])

    def test_all_correct_marks_every_entry_correct(self):
        topic = "ARP protocol"
        correct = [q["answer"] for q in MCQ_BANK[topic]]
        review = build_review(topic, correct)
        assert all(r["correct"] for r in review)

    def test_wrong_answer_is_marked_incorrect_with_both_options(self):
        """
        An incorrect entry must carry what the student chose and what was
        correct, since the feedback shows both side by side.
        """
        topic = "ARP protocol"
        q0 = MCQ_BANK[topic][0]
        wrong_label = next(o for o in q0["options"] if o != q0["answer"])
        responses = [wrong_label] + [q["answer"] for q in MCQ_BANK[topic][1:]]

        review = build_review(topic, responses)
        first = review[0]
        assert first["correct"] is False
        assert first["chosen_label"] == wrong_label
        assert first["chosen_text"] == q0["options"][wrong_label]
        assert first["answer_label"] == q0["answer"]
        assert first["answer_text"] == q0["options"][q0["answer"]]

    def test_every_entry_carries_its_explanation(self):
        topic = "TCP handshake"
        correct = [q["answer"] for q in MCQ_BANK[topic]]
        review = build_review(topic, correct)
        for r, q in zip(review, MCQ_BANK[topic]):
            assert r["explanation"] == q["explanation"]

    def test_lowercase_response_is_matched(self):
        topic = "ARP protocol"
        lower = [q["answer"].lower() for q in MCQ_BANK[topic]]
        review = build_review(topic, lower)
        assert all(r["correct"] for r in review)

    def test_question_numbers_are_one_based(self):
        topic = "ARP protocol"
        correct = [q["answer"] for q in MCQ_BANK[topic]]
        review = build_review(topic, correct)
        assert [r["number"] for r in review] == [1, 2, 3]

    def test_passing_at_two_of_three_still_reports_the_mistake(self):
        """
        A student can pass at 2/3 while still holding one misconception. The
        review must surface it, otherwise passing would hide the gap the probe
        exists to find.
        """
        topic = "ARP protocol"
        answers = [q["answer"] for q in MCQ_BANK[topic]]
        last = MCQ_BANK[topic][-1]
        answers[-1] = next(o for o in last["options"] if o != last["answer"])

        score, total = score_responses(topic, answers)
        assert prerequisite_passed(score, total) is True

        review = build_review(topic, answers)
        wrong = [r for r in review if not r["correct"]]
        assert len(wrong) == 1
        assert wrong[0]["explanation"]

    def test_unknown_topic_returns_empty_review(self):
        assert build_review("not a real topic", ["A"]) == []


#mCQ bank data integrity


class TestMCQBankIntegrity:

    @pytest.mark.parametrize("topic", MCQ_BANK.keys())
    def test_every_question_has_required_fields(self, topic):
        for q in MCQ_BANK[topic]:
            assert "question" in q and q["question"].strip()
            assert "options" in q and len(q["options"]) >= 2
            assert "answer" in q
            assert "explanation" in q

    @pytest.mark.parametrize("topic", MCQ_BANK.keys())
    def test_every_question_has_a_substantive_explanation(self, topic):
        """
        A question without an explanation would render an empty feedback box
        after the probe, which is worse than showing nothing: the student would
        be told they were wrong with no indication why. The length floor guards
        against a placeholder being committed.
        """
        for q in MCQ_BANK[topic]:
            assert len(q["explanation"].strip()) > 40, (
                f"Explanation too short for: {q['question'][:50]}"
            )

    @pytest.mark.parametrize("topic", MCQ_BANK.keys())
    def test_answer_key_exists_in_options(self, topic):
        """
        Critical integrity check: if an answer key did not match any option,
        that question would be permanently unanswerable and would silently
        depress every student's prerequisite score.
        """
        for q in MCQ_BANK[topic]:
            assert q["answer"] in q["options"], (
                f"Answer '{q['answer']}' not in options for: {q['question'][:50]}"
            )

    @pytest.mark.parametrize("topic", MCQ_BANK.keys())
    def test_options_are_unique(self, topic):
        """Duplicate option text would make a question ambiguous."""
        for q in MCQ_BANK[topic]:
            texts = list(q["options"].values())
            assert len(texts) == len(set(texts))

    @pytest.mark.parametrize("topic", MCQ_BANK.keys())
    def test_each_topic_has_three_questions(self, topic):
        """The probe design specifies three questions per prerequisite topic."""
        assert len(MCQ_BANK[topic]) == 3


#the quiz generates its questions from the knowledge base at run time, so unlike MCQ_BANK there is no fixed bank to assert against.

GOOD_ITEM = {
    "question": "What does ARP resolve?",
    "options": {"A": "Names to IP addresses", "B": "IP addresses to MACs",
                "C": "MACs to port numbers", "D": "Nothing, it encrypts"},
    "answer": "B",
    "explanation": "ARP maps a Layer 3 address to a Layer 2 address.",
    "week": 3,
}


class TestQuizValidation:

    def test_well_formed_item_is_kept(self):
        assert len(validate_questions([GOOD_ITEM])) == 1

    def test_answer_key_must_name_an_option(self):
        """The generated-item equivalent of test_answer_key_is_valid."""
        assert validate_questions([{**GOOD_ITEM, "answer": "E"}]) == []

    def test_item_must_have_four_options(self):
        options = {k: v for k, v in GOOD_ITEM["options"].items() if k != "D"}
        assert validate_questions([{**GOOD_ITEM, "options": options}]) == []

    def test_duplicate_option_text_is_rejected(self):
        """Two identical options make the item ambiguous and unscoreable."""
        options = {"A": "same", "B": "same", "C": "other", "D": "third"}
        assert validate_questions([{**GOOD_ITEM, "options": options}]) == []

    def test_explanation_is_required(self):
        """Corrective feedback is the point of practice mode, not a nicety."""
        assert validate_questions([{**GOOD_ITEM, "explanation": "   "}]) == []

    def test_lowercase_answer_key_is_accepted(self):
        """Models are inconsistent about case; the item is otherwise sound."""
        kept = validate_questions([{**GOOD_ITEM, "answer": "b"}])
        assert len(kept) == 1 and kept[0]["answer"] == "B"

    def test_missing_week_does_not_reject_the_item(self):
        """The week is a citation aid, not a correctness property."""
        item = {k: v for k, v in GOOD_ITEM.items() if k != "week"}
        kept = validate_questions([item])
        assert len(kept) == 1 and kept[0]["week"] is None


class TestQuizParsing:
    """The prompt asks for a bare JSON object, but the reply is not reliably
    orthographic, which is the same class of defect as the confidence
    delimiter parsing."""

    def test_plain_object(self):
        raw = '{"questions": [%s]}' % json.dumps(GOOD_ITEM)
        assert len(quiz._parse(raw)) == 1

    def test_fenced_code_block(self):
        body = '{"questions": [%s]}' % json.dumps(GOOD_ITEM)
        raw = "```json\n" + body + "\n```"
        assert len(quiz._parse(raw)) == 1

    def test_preamble_before_the_object(self):
        body = '{"questions": [%s]}' % json.dumps(GOOD_ITEM)
        raw = "Certainly, here are the questions:\n" + body
        assert len(quiz._parse(raw)) == 1

    def test_bare_array(self):
        assert len(quiz._parse(json.dumps([GOOD_ITEM]))) == 1

    def test_unparseable_reply_yields_nothing(self):
        assert quiz._parse("I am unable to help with that") == []

    def test_empty_reply_yields_nothing(self):
        assert quiz._parse("") == []


class TestQuizScoring:

    def test_unanswered_counts_as_incorrect(self):
        """
        The denominator stays equal to the number of questions set, so a
        student who runs out of time in exam mode is scored on the whole
        paper rather than only on what they reached.
        """
        questions = [GOOD_ITEM, GOOD_ITEM, GOOD_ITEM]
        result = score_quiz(questions, {0: "B"})
        assert result["score"] == 1
        assert result["total"] == 3
        assert result["review"][2]["chosen"] is None
        assert result["review"][2]["correct"] is False

    def test_all_correct(self):
        result = score_quiz([GOOD_ITEM, GOOD_ITEM], {0: "B", 1: "B"})
        assert result["score"] == 2 and result["percentage"] == 100.0

    def test_empty_quiz_does_not_divide_by_zero(self):
        result = score_quiz([], {})
        assert result["total"] == 0 and result["percentage"] == 0.0


class TestQuizBands:
    """The result chip reuses the interface's three bands rather than
    introducing a fourth visual language for the same idea."""

    @pytest.mark.parametrize("percentage,expected", [
        (100.0, "High"), (80.0, "High"), (79.9, "Medium"),
        (50.0, "Medium"), (49.9, "Low"), (0.0, "Low"),
    ])
    def test_boundaries(self, percentage, expected):
        assert band_for_percentage(percentage) == expected


class TestQuizConfiguration:

    def test_question_range_matches_the_specification(self):
        assert quiz.MIN_QUESTIONS == 1 and quiz.MAX_QUESTIONS == 20

    def test_exam_allows_one_minute_per_question(self):
        assert quiz.estimated_seconds(10) == 600

    def test_every_topic_declares_a_week_and_retrieval_terms(self):
        for key, spec in quiz.QUIZ_TOPICS.items():
            assert spec["week"] in (1, 2, 3, 4, 5), key
            assert spec["terms"].strip(), key

    def test_every_topic_has_a_label_in_all_three_languages(self):
        """A topic without a label would render as its raw identifier."""
        from ui import i18n
        for key in quiz.QUIZ_TOPICS:
            entry = i18n.STRINGS.get(f"quiz.topic.{key}")
            assert entry, key
            for language in ("en", "it", "fr"):
                assert entry.get(language), (key, language)

    def test_topics_are_listed_in_teaching_order(self):
        weeks = [quiz.topic_week(k) for k in quiz.all_topic_keys()]
        assert weeks == sorted(weeks)


#quiz attempt history. these pin the isolation property rather than the feature working.


class _FakeSessionState(dict):
    """Minimal stand-in for st.session_state, which needs a live runtime"""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def session(monkeypatch):
    """Install a fresh fake Streamlit session for one test. quiz.py imports streamlit inside _history() rather than at module scope, so replacing the entry
    in sys.modules is enough and import order does not matter"""
    import sys
    import types

    def _make():
        module = types.ModuleType("streamlit")
        module.session_state = _FakeSessionState()
        return module

    module = _make()
    monkeypatch.setitem(sys.modules, "streamlit", module)
    return module


ATTEMPT = {"score": 4, "total": 5, "percentage": 80.0,
           "review": [{"number": 1, "correct": True}]}
CONFIG = {"difficulty": "medium", "mode": "practice", "count": 5,
          "topics": ["arp"]}


class TestQuizHistory:

    def test_recorded_attempt_is_readable_back(self, session):
        assert quiz.record_attempt(ATTEMPT, CONFIG, "en") is True
        rows = quiz.load_history()
        assert len(rows) == 1
        assert rows[0]["score"] == 4 and rows[0]["percentage"] == 80.0

    def test_history_is_most_recent_first(self, session):
        quiz.record_attempt({**ATTEMPT, "score": 1}, CONFIG, "en")
        quiz.record_attempt({**ATTEMPT, "score": 2}, CONFIG, "en")
        assert [r["score"] for r in quiz.load_history()] == [2, 1]

    def test_limit_is_applied_after_ordering(self, session):
        for n in range(4):
            quiz.record_attempt({**ATTEMPT, "score": n}, CONFIG, "en")
        assert [r["score"] for r in quiz.load_history(limit=2)] == [3, 2]

    def test_every_attempt_gets_a_distinct_id(self, session):
        """The review buttons key on this, so a collision would make one attempt unopenable"""
        for _ in range(10):
            quiz.record_attempt(ATTEMPT, CONFIG, "en")
        ids = [r["id"] for r in quiz.load_history()]
        assert len(set(ids)) == len(ids)

    def test_empty_history_reads_as_empty(self, session):
        assert quiz.load_history() == []

    def test_clear_empties_this_session(self, session):
        quiz.record_attempt(ATTEMPT, CONFIG, "en")
        assert quiz.clear_history() is True
        assert quiz.load_history() == []

    def test_history_is_not_shared_between_sessions(self, monkeypatch):
        """The property the file backed version violated. Two sessions must not see each other's attempts and clearing one must not touch the other.
        This is the test that would have caught it"""
        import sys
        import types

        def install():
            module = types.ModuleType("streamlit")
            module.session_state = _FakeSessionState()
            monkeypatch.setitem(sys.modules, "streamlit", module)

        install()
        quiz.record_attempt({**ATTEMPT, "score": 1}, CONFIG, "en")
        assert len(quiz.load_history()) == 1

        #a second participant connects
        install()
        assert quiz.load_history() == [], "second session saw the first's attempts"
        quiz.record_attempt({**ATTEMPT, "score": 2}, CONFIG, "en")
        quiz.clear_history()

        #back to the first, whose history must be untouched by either action
        install()
        assert quiz.load_history() == []

    def test_nothing_is_written_to_disk(self, session, tmp_path, monkeypatch):
        """the user study claims the app retains nothing about a participant, so recording an attempt must create no file anywhere under the working directory"""
        monkeypatch.chdir(tmp_path)
        quiz.record_attempt(ATTEMPT, CONFIG, "en")
        assert list(tmp_path.rglob("*")) == []

    def test_summary_over_recorded_attempts(self, session):
        for pct in (40.0, 80.0, 60.0):
            quiz.record_attempt({**ATTEMPT, "percentage": pct}, CONFIG, "en")
        summary = quiz.history_summary(quiz.load_history())
        assert summary["attempts"] == 3
        assert summary["average"] == 60.0
        assert summary["best"] == 80.0
