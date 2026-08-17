"""
prerequisite_check.py
=====================
Implements the prerequisite-checking component of the RAG pipeline described in
the dissertation methodology (design of the prerequisite layer).

When a student asks an advanced question, this module:
  1. Scans the question for keywords indicating an advanced topic that depends
     on foundational knowledge (detect_prerequisite).
  2. If a dependency is detected, presents 3 MCQs testing the required
     foundational concept (run_mcq_probe, or the Streamlit form).
  3. Scores the responses and returns a pass/fail result (score_responses,
     prerequisite_passed).
  4. Returns per-question feedback so the student is told which answers were
     wrong and why (build_review).
  5. The result is used to decide whether to deliver a full explanation or a
     simplified one with a study hint.

Design rationale:
The prerequisite graph is intentionally hardcoded for this prototype.
Kuzminykh et al. (2021) show that threshold concepts in cybersecurity modules
are common and that students cannot self-diagnose when they have missed one.
Network Security has several such chains: ARP must be understood before ARP
spoofing makes sense; the TCP handshake must be understood before SYN flooding
makes sense. This module encodes those chains explicitly rather than inferring
them, following Pan et al. (2017), who demonstrate that hand-curated graphs
produce coherent learning paths. Automatic extraction is future work (6.3).

Feedback design:
Each question carries an explanation, shown after the probe is submitted.
Carpenter et al. (2022) find that the benefit of retrieval practice depends on
corrective feedback following the retrieval attempt: being tested and then told
only a score teaches nothing, whereas being told why an answer was wrong
converts the attempt into learning. Explanations are therefore shown for
incorrect answers, so a student who fails the probe leaves knowing what the
gap was rather than only that a gap exists. This also serves the "specific,
meaningful, timely and actionable" feedback criteria set out by Williams
(2024).

Explanations are grounded in the Weeks 1-5 course material that was chunked and
embedded into the knowledge base, so the probe and the tutor agree.

Usage (standalone CLI):
    py prerequisite_check.py

Usage (imported):
    from core.prerequisite_check import check_prerequisite, build_review
"""

#dependency graph

DEPENDENCY_GRAPH: dict[str, str] = {
    # ARP spoofing and related attacks gate on knowing ARP basics
    "arp spoofing":      "ARP protocol",
    "arp poisoning":     "ARP protocol",
    "arp cache":         "ARP protocol",
    "arp flood":         "ARP protocol",
    "dns poisoning":     "ARP protocol",
    "gratuitous arp":    "ARP protocol",

    # SYN flooding and TCP attacks gate on knowing the handshake
    "syn flood":         "TCP handshake",
    "syn flooding":      "TCP handshake",
    "syn spoofing":      "TCP handshake",
    "tcp spoofing":      "TCP handshake",
    "session hijacking": "TCP handshake",
    "tcp hijack":        "TCP handshake",
    "half-open":         "TCP handshake",

    # Stateful and advanced firewall topics gate on packet filtering basics
    "stateful firewall": "packet filter firewall",
    "stateful packet":   "packet filter firewall",
    "iptables":          "packet filter firewall",
    "firewall rules":    "packet filter firewall",
    "firewall topology": "packet filter firewall",
    "dmz":               "packet filter firewall",
}


#mCQ bank Each question is a dict with: question     the question text options      {label: text}, labels are "A" to "D" answer       the correct
#label explanation  why the correct answer is correct, shown as feedback after the probe.

MCQ_BANK: dict[str, list[dict]] = {

    "ARP protocol": [
        {
            "question": "What does the Address Resolution Protocol (ARP) do?",
            "options": {
                "A": "Maps domain names to IP addresses",
                "B": "Maps IP addresses to MAC addresses",
                "C": "Maps MAC addresses to port numbers",
                "D": "Encrypts traffic between two hosts",
            },
            "answer": "B",
            "explanation": (
                "ARP resolves a known IP address (Layer 3) to the MAC address "
                "(Layer 2) of the host that holds it, so a frame can actually be "
                "addressed on the local network. Mapping domain names to IP "
                "addresses is DNS, not ARP, and ARP provides no encryption at "
                "all. That absence of any authentication or encryption is "
                "exactly what ARP spoofing exploits."
            ),
        },
        {
            "question": (
                "ARP is described as a stateless protocol. What does this mean "
                "in the context of how it handles replies?"
            ),
            "options": {
                "A": "It only works on wired networks",
                "B": "It discards replies that arrive out of order",
                "C": "It accepts and overwrites cache entries even without a prior request",
                "D": "It requires authentication before updating the cache",
            },
            "answer": "C",
            "explanation": (
                "Stateless means ARP keeps no record of which requests it sent, "
                "so it cannot tell a solicited reply from an unsolicited one. A "
                "host will accept an ARP reply it never asked for and overwrite "
                "an existing cache entry with it, even before that entry has "
                "expired. This is the specific property an attacker abuses: the "
                "spoofed reply does not need to win a race or wait for a "
                "request, it simply has to arrive."
            ),
        },
        {
            "question": (
                "Where does a host store the IP-to-MAC mappings it learns from "
                "ARP replies?"
            ),
            "options": {
                "A": "The DNS resolver cache",
                "B": "The routing table",
                "C": "The ARP cache (ARP table)",
                "D": "The firewall rule set",
            },
            "answer": "C",
            "explanation": (
                "Learned mappings are held in the ARP cache, sometimes called the "
                "ARP table. Entries expire after roughly 40 seconds, which is why "
                "an attacker must keep re-sending spoofed replies to sustain an "
                "attack. The routing table holds next-hop decisions for Layer 3 "
                "forwarding and is a different structure entirely. 'Poisoning the "
                "ARP cache' names this table directly."
            ),
        },
    ],

    "TCP handshake": [
        {
            "question": "What is the correct sequence of the TCP three-way handshake?",
            "options": {
                "A": "SYN, ACK, SYN-ACK",
                "B": "SYN, SYN-ACK, ACK",
                "C": "ACK, SYN, SYN-ACK",
                "D": "SYN-ACK, SYN, FIN",
            },
            "answer": "B",
            "explanation": (
                "The client sends SYN, the server replies SYN-ACK, and the client "
                "confirms with ACK. The order matters for understanding SYN "
                "flooding: the server commits resources when it sends the "
                "SYN-ACK, which is before the client has proved it exists. That "
                "asymmetry, where the server pays first, is the whole basis of "
                "the attack."
            ),
        },
        {
            "question": (
                "What state is a connection in after the server receives the "
                "initial SYN but before the client's final ACK arrives?"
            ),
            "options": {
                "A": "ESTABLISHED",
                "B": "CLOSED",
                "C": "HALF-OPEN",
                "D": "LISTEN",
            },
            "answer": "C",
            "explanation": (
                "The connection is half-open: the server has allocated state and "
                "sent its SYN-ACK, but the handshake is incomplete. It only "
                "becomes ESTABLISHED once the final ACK arrives. LISTEN is the "
                "state the socket sits in before any SYN is received. A SYN flood "
                "works by manufacturing large numbers of half-open connections "
                "that never complete."
            ),
        },
        {
            "question": (
                "Which resource does a TCP SYN flood attack aim to exhaust on "
                "the server?"
            ),
            "options": {
                "A": "Disk storage space",
                "B": "DNS cache entries",
                "C": "CPU cycles used for encryption",
                "D": "The connection table storing half-open connections",
            },
            "answer": "D",
            "explanation": (
                "Each half-open connection occupies an entry in the server's "
                "connection table. The table is finite, so once it fills, "
                "legitimate SYNs are refused and the service is denied. Note that "
                "the attack does not need high bandwidth or heavy computation: it "
                "targets a bookkeeping structure, not raw capacity, which is why "
                "a modest attacker can affect a large server."
            ),
        },
    ],

    "packet filter firewall": [
        {
            "question": (
                "A packet filter firewall makes filtering decisions based on "
                "which of the following?"
            ),
            "options": {
                "A": "Individual packet headers only, without tracking connection state",
                "B": "The full content of application-layer payloads",
                "C": "Whether a connection exists in the firewall state table",
                "D": "The user account associated with the packet",
            },
            "answer": "A",
            "explanation": (
                "A packet filter inspects each packet's headers in isolation: "
                "source and destination address, port, and protocol. It holds no "
                "memory of what came before, so it cannot tell whether a packet "
                "belongs to a conversation the host started. Option C describes a "
                "stateful firewall, and option B an application-level proxy. The "
                "distinction matters because it is precisely this blindness to "
                "context that stateful inspection was introduced to fix."
            ),
        },
        {
            "question": (
                "In a packet filter rule set, what happens when a packet does "
                "not match any rule and the policy is 'default deny'?"
            ),
            "options": {
                "A": "The packet is forwarded and logged",
                "B": "The packet is returned to sender with an error",
                "C": "The packet is dropped",
                "D": "The packet is queued for manual review",
            },
            "answer": "C",
            "explanation": (
                "Default deny means anything not explicitly permitted is dropped, "
                "which is the more secure default because a rule you forgot to "
                "write fails closed rather than open. The opposite policy, default "
                "permit, forwards anything not explicitly blocked. Rules are "
                "evaluated top to bottom, and the default action applies only "
                "when no rule has matched."
            ),
        },
        {
            "question": (
                "Which limitation of a stateless packet filter does a stateful "
                "firewall address?"
            ),
            "options": {
                "A": "Stateless firewalls cannot inspect source IP addresses",
                "B": "Stateless firewalls must allow all high-numbered inbound ports for return traffic, creating a vulnerability",
                "C": "Stateless firewalls can only filter UDP, not TCP",
                "D": "Stateless firewalls require a separate proxy per application",
            },
            "answer": "B",
            "explanation": (
                "Because a stateless filter cannot recognise return traffic as "
                "belonging to a connection the host initiated, permitting normal "
                "outbound TCP forces it to leave the whole ephemeral port range "
                "(1024-65535) open inbound. That is a large exposed surface. A "
                "stateful firewall tracks connections in a state table, so it can "
                "admit an inbound packet solely because it matches an established "
                "session, and keep those ports closed otherwise."
            ),
        },
    ],
}


#detection


def detect_prerequisite(question: str) -> str | None:
    """
    Scan the student question for keywords indicating an advanced topic that
    requires prerequisite knowledge. Returns the prerequisite topic label (a key
    in MCQ_BANK) or None.

    Keyword matching is case-insensitive. Limitation: paraphrases and novel
    phrasings will be missed. Semantic detection using the embedding model is
    listed as a future extension.
    """
    q_lower = question.lower()
    for keyword, prereq_topic in DEPENDENCY_GRAPH.items():
        if keyword in q_lower:
            return prereq_topic
    return None


#probe


def run_mcq_probe(topic: str) -> tuple[int, int, list[str]]:
    """
    Present the MCQs for a topic via CLI, with feedback after each answer.
    Returns (score, total, responses).

    The Streamlit front end imports MCQ_BANK directly and renders the questions
    as radio buttons, scoring via score_responses() and rendering feedback via
    build_review(), so this function is used only for standalone testing.
    """
    questions = MCQ_BANK.get(topic, [])
    if not questions:
        return 0, 0, []

    print(f"\n{'-' * 66}")
    print(f"  Prerequisite check: {topic}")
    print(f"  Answer {len(questions)} questions before we continue.")
    print(f"{'-' * 66}")

    score = 0
    responses: list[str] = []

    for i, q in enumerate(questions, start=1):
        print(f"\nQ{i}. {q['question']}")
        for label, text in q["options"].items():
            print(f"   {label}) {text}")

        while True:
            raw = input("   Your answer: ").strip().upper()
            if raw in q["options"]:
                break
            print("   Please enter A, B, C or D.")

        responses.append(raw)

        if raw == q["answer"]:
            score += 1
            print("   Correct.")
        else:
            print(f"   Not quite. You chose {raw}) {q['options'][raw]}")
            print(f"   Correct answer: {q['answer']}) {q['options'][q['answer']]}")

        print(f"   {q['explanation']}")

    return score, len(questions), responses


def score_responses(topic: str, responses: list[str]) -> tuple[int, int]:
    """
    Score a pre-collected list of responses (used by the Streamlit front end).
    responses is a list of label strings, e.g. ["B", "C", "A"].
    Returns (score, total).
    """
    questions = MCQ_BANK.get(topic, [])
    score = sum(
        1 for response, q in zip(responses, questions)
        if response.upper() == q["answer"]
    )
    return score, len(questions)

def build_review(topic: str, responses: list[str]) -> list[dict]:
    """
    Build per-question feedback for a completed probe.

    Returns one dict per question:
        {
            "number":         1-based question number,
            "question":       the question text,
            "correct":        True if the student answered correctly,
            "chosen_label":   the label the student picked,
            "chosen_text":    the text of the option they picked,
            "answer_label":   the correct label,
            "answer_text":    the text of the correct option,
            "explanation":    why the correct answer is correct,
        }

    Feedback is returned for every question so the caller can choose what to
    show. The interface shows explanations for incorrect answers, since telling
    a student why they were wrong is what converts a retrieval attempt into
    learning (Carpenter et al., 2022), while repeating explanations for answers
    they already got right adds length without adding information.
    """
    questions = MCQ_BANK.get(topic, [])
    review: list[dict] = []

    for i, (q, response) in enumerate(zip(questions, responses), start=1):
        chosen = response.upper()
        review.append({
            "number":       i,
            "question":     q["question"],
            "correct":      chosen == q["answer"],
            "chosen_label": chosen,
            "chosen_text":  q["options"].get(chosen, "(no answer)"),
            "answer_label": q["answer"],
            "answer_text":  q["options"][q["answer"]],
            "explanation":  q["explanation"],
        })

    return review


#pass / fail

def prerequisite_passed(score: int, total: int,
                        threshold: float = 0.66) -> bool:
    """
    Return True if score meets or exceeds the threshold proportion.

    Default threshold 0.66, which passes 2 out of 3. The value is 0.66 rather
    than 0.67 because 2/3 evaluates to 0.6667, which is strictly less than 0.67:
    a threshold of 0.67 silently failed students at the exact intended pass mark
    (caught by boundary-value analysis in test_pipeline.py).
    """
    if total == 0:
        return True
    return (score / total) >= threshold


# ==============================================================================
#  Full pipeline
# ==============================================================================



def check_prerequisite(question: str) -> dict | None:
    """
    Run the full prerequisite check for a question.

    Returns a result dict if a prerequisite was detected, else None:
        {
            "topic":     prerequisite topic label,
            "score":     number correct,
            "total":     total questions,
            "passed":    True if score >= threshold,
            "responses": the labels the student chose,
            "review":    per-question feedback from build_review(),
        }
    """
    topic = detect_prerequisite(question)
    if topic is None:
        return None

    print(f"\n  [Prerequisite detected] Topic: {topic}")
    score, total, responses = run_mcq_probe(topic)
    passed = prerequisite_passed(score, total)

    outcome = (
        "PASSED - full answer incoming."
        if passed else
        "NEEDS REVIEW - simplified answer with study hint."
    )
    print(f"\n  Result: {score}/{total} - {outcome}")

    return {
        "topic":     topic,
        "score":     score,
        "total":     total,
        "passed":    passed,
        "responses": responses,
        "review":    build_review(topic, responses),
    }


#main

def main() -> None:
    test_questions = [
        "How does ARP spoofing work?",
        "What is a SYN flood attack?",
        "What is the difference between a stateful and stateless firewall?",
    ]

    print("=" * 66)
    print(" Prerequisite Check Module - Standalone Test")
    print("=" * 66)

    for question in test_questions:
        print(f"\n\nQuestion: '{question}'")
        result = check_prerequisite(question)
        if result is None:
            print("  No prerequisite detected.")
        else:
            status = "PASSED" if result["passed"] else "FAILED"
            print(f"  {status} ({result['score']}/{result['total']})")


if __name__ == "__main__":
    main()


"""
================================================================================
 References
================================================================================

 Pan, L., Li, C., Li, J. and Tang, J. (2017). Prerequisite relation learning for
    concepts in MOOCs. Proceedings of the 55th Annual Meeting of the Association
    for Computational Linguistics (ACL 2017), pp. 1447-1456.
    - Basis for encoding topic prerequisite relationships as a directed
      dependency graph; their finding that hand-curated graphs produce coherent
      learning paths justifies the hardcoded prototype approach.

 Kuzminykh, I., Ghita, B., Xiao, H., Yevdokymenko, M. and Yeremenko, O. (2021).
    Investigating threshold concept and troublesome knowledge in cyber security.
    1st Conference on Online Teaching for Mobile Education (OT4ME 2021),
    pp. 26-30.
    - Directly motivates the prerequisite check design: threshold concepts in
      cybersecurity are common and students cannot self-diagnose when they have
      missed one, making active testing more effective than self-reporting.

 Chen, P., Lu, Y., Zheng, V. W. and Pian, Y. (2018). Prerequisite-driven deep
    knowledge tracing. IEEE International Conference on Data Mining (ICDM 2018).
    - Shows that prerequisite-driven models predict student readiness for
      advanced content better than sequence-only models.

 Carpenter, S. K., Pan, S. C. and Butler, A. C. (2022). The science of effective
    learning with spacing and retrieval practice. Nature Reviews Psychology,
    1(9), pp. 496-511. https://doi.org/10.1038/s44159-022-00089-1
    - Retrieval practice outperforms passive re-reading, providing the
      pedagogical rationale for the MCQ probe, and the finding that its benefit
      depends on corrective feedback, which motivates the explanations shown
      after the probe rather than a bare score.

 Williams, A. (2024). Delivering effective student feedback in higher education.
    International Journal of Research in Education and Science, 10(2),
    pp. 473-501.
    - Feedback should be specific, meaningful, timely and actionable. The
      per-question explanations satisfy these criteria where a score alone would
      not.

 Mishra, P., Henriksen, D., Woo, L. J. and Oster, N. (2025). Control vs. agency:
    exploring the history of AI in education. TechTrends.
    - Positions prerequisite checking as a lever for preserving learner agency
      under AI assistance.
================================================================================
"""
