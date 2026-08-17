"""One-question smoke test, for checking a model change before a full batch run.

Prints the raw model response alongside the parsed answer, so any reasoning
content or format change that would break parse_answer_and_confidence() is
visible before fifty API calls are spent on it.

    py -m evaluation.smoke_test
    py -m evaluation.smoke_test "What is ARP spoofing?"
"""

import os
import sys
import time

from groq import Groq

from config import GROQ_MODEL
from core.generate_answer import (get_collection, retrieve_context, build_prompt,
                                  parse_answer_and_confidence, confidence_band,
                                  compound_confidence, MAX_ANSWER_TOKENS)

QUESTION = " ".join(sys.argv[1:]) or "What is the CIA triad in network security?"

api_key = os.environ.get("GROQ_API_KEY", "").strip()
if not api_key:
    sys.exit('GROQ_API_KEY not set.  $env:GROQ_API_KEY="your-key-here"')

print("=" * 70)
print(f" model:    {GROQ_MODEL}")
print(f" question: {QUESTION}")
print("=" * 70)

collection = get_collection()
chunks = retrieve_context(collection, QUESTION)
prompt = build_prompt(QUESTION, chunks)

client = Groq(api_key=api_key)
start = time.time()
response = client.chat.completions.create(
    model=GROQ_MODEL,
    messages=[{"role": "user", "content": prompt}],
    max_tokens=MAX_ANSWER_TOKENS,
)
elapsed = round(time.time() - start, 2)

message = response.choices[0].message
raw = message.content or ""

print(f"\nlatency: {elapsed}s   finish_reason: {response.choices[0].finish_reason}")
if getattr(response, "usage", None):
    u = response.usage
    print(f"tokens:  prompt={u.prompt_tokens} completion={u.completion_tokens}")

#gpt-oss style models may return chain-of-thought in a separate field
reasoning = getattr(message, "reasoning", None)
print(f"\nseparate 'reasoning' field present: {'YES, ' + str(len(reasoning)) + ' chars' if reasoning else 'no'}")

print("\n" + "-" * 70)
print("RAW RESPONSE")
print("-" * 70)
print(raw)

answer, verify = parse_answer_and_confidence(raw)
band = confidence_band(chunks)

print("\n" + "-" * 70)
print("PARSED")
print("-" * 70)
print(f"Signal 2 parsed:  {verify}   (2 means the CONFIDENCE line was NOT found)")
print(f"Signal 1 band:    {band}")
print(f"compound band:    {compound_confidence(band, verify)}")

print("\nchecks:")
#match the delimiter the parser looks for, not the bare word: "confidentiality"
#contains "conf" and would otherwise report a false failure
import re
DELIM = re.compile(r"CONF\w*\s*:", re.I)
found = DELIM.search(raw) is not None
print(f"  {'ok ' if found else 'FAIL'}  CONFIDENCE line present in the response")
leaked = DELIM.search(answer) is not None
print(f"  {'ok ' if not leaked else 'FAIL'}  delimiter stripped from the parsed answer")
truncated = response.choices[0].finish_reason == "length"
print(f"  {'FAIL' if truncated else 'ok '}  response not truncated by max_tokens")
print(f"\nANSWER AS THE STUDENT WOULD SEE IT\n{'-' * 70}\n{answer}")
