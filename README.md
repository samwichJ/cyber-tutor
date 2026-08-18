Jannat Faisal
K19016525


APP name: CYBER TUTOR


A retrieval-augmented tutoring agent for a postgraduate Network Security
module. It answers questions from the module's own material, cites the
passages each answer was written from, reports how far that answer is
grounded in them, and verifies foundational knowledge before explaining a
topic that depends on it.

The application is also running here, however, note that the live app goes
dormant after prolonged period of inactivity:

    https://cyber-tutor.streamlit.app/

REQUIREMENTS
  - Python 3.11 or later
  - A Groq API key (free tier is sufficient), from
    https://console.groq.com/keys

Packages, all installed by STEP 1 below:

  streamlit          1.59.0       the application
  chromadb           1.5.9        the vector store
  groq               1.5.0        the generation API
  pillow             12.1.0       the application icon
  pysqlite3-binary   linux only   hosts shipping sqlite3 older than 3.35
  python-docx        1.2.0        knowledge base construction, build/ only
  python-pptx        1.0.2        knowledge base construction, build/ only
  pypdf              6.14.2       knowledge base construction, build/ only
  lxml               6.1.1        knowledge base construction, build/ only
  openpyxl           3.1.5        evaluation and tests only
  pytest             9.1.1        evaluation and tests only


STEPS TO RUN:

STEP 1. Install the dependencies

    py -m pip install -r requirements.txt

STEP 2. Set the API key for the session

    $env:GROQ_API_KEY='key-here'

    On bash or zsh use  export GROQ_API_KEY="key-here"  instead.

STEP 3. Start the application

    py -m streamlit run streamlit_app.py

STEP 4. Open it in the browser

    Streamlit prints a local URL, normally http://localhost:8501, and
    opens it automatically.

The vector store is committed under data/chroma_db, so there is no build
step and nothing else to prepare.


CONTENTS OF THIS ARCHIVE

Third-party libraries are not included; they are listed under REQUIREMENTS
above and installed by STEP 1.


ROOT
....

  streamlit_app.py
      The front end, and the entry point. Holds conversation state, the
      per-turn loop, page layout, and the quiz screens.

  config.py
      Paths, the generation model name, retrieval k, and the two
      confidence thresholds. Every path derives from this file's own
      location, so the project runs from any folder.

  conftest.py
      Puts the project root on sys.path so the tests import correctly
      whichever directory pytest is invoked from.

  requirements.txt
      Pinned dependencies.

  README.txt
      This file.

  .streamlit/config.toml
      Interface theme. Carries the accessibility-verified colour palette
      and the contrast rationale behind it.

  assets/icon.png
      Application icon.


core/  -  THE EVALUATED PIPELINE
................................

Contains no interface code, so the pipeline the evaluation measures can be
run and tested independently of how it is displayed.

  generate_answer.py
      Retrieval, both confidence signals, prompt construction, and
      response parsing. Runnable standalone:
          py -m core.generate_answer "your question here"

  prerequisite_check.py
      The dependency graph, the MCQ bank, probe scoring, and construction
      of the per-question review shown after a probe.

  quiz.py
      On-demand quiz: generation from the knowledge base, structural
      validation of generated items, scoring, and session-scoped attempt
      history.

  cross_lingual.py
      Renders a non-English question into English for retrieval only, so
      the interface and the answer can be in another language while the
      corpus stays English.

  __init__.py
      Package marker.


ui/  -  PRESENTATION
....................

  ui_theme.py
      Design tokens, the four-channel confidence encoding (colour,
      marker, label, meter), and all CSS. The contrast figures and their
      derivation are documented here.

  i18n.py
      English, Italian and French interface catalogue, and language
      selection.

  mcq_i18n.py
      Translated MCQ bank. The answer key is never translated and stays
      canonical.

  study_tools.py
      Follow-up suggestions, the session progress summary, and Markdown
      export of a conversation.

  __init__.py
      Package marker.


build/  -  KNOWLEDGE BASE CONSTRUCTION
......................................

Not needed to run the application. Included as evidence for the content
preparation objective. The source course material is not redistributed, so
these scripts cannot be re-run from this archive.

  CleanMetadata.py
      Strips author names, comments and tracked changes from the source
      documents before any processing.

  extract_and_chunk.py
      Extracts text from Word, PowerPoint and PDF sources and divides it
      into chunks carrying week, topic and artefact type.

  build_chromadb.py
      Embeds the chunks and writes the persistent vector store.

  __init__.py
      Package marker.


evaluation/
...........

  gold_set_eval.py
      Batch harness running the 50-question gold set through the live
      pipeline and writing the machine-measurable columns back into the
      workbook. Imports the pipeline directly, so nothing is
      re-implemented.

  smoke_test.py
      Single-question check, for verifying a model change before
      spending 50 API calls on a batch run.

  gold_set_evaluation.xlsx
      The primary evaluation, run on Llama 3.1 8B. Contains the gold
      set, the scores, and the results summary.

  gold_set_evaluation_gptoss20b.xlsx
      The same gold set re-run after the provider decommissioned that
      model, giving a controlled comparison.

  __init__.py
      Package marker.


tests/
......

Run with:

    py -m pytest tests/ -q

No API key and no network are required. Only the deterministic components
are unit tested, and anything that would otherwise come from the API or the
vector store is stubbed.

  test_pipeline.py
      Confidence banding and the compound rule, prerequisite detection
      and scoring, response parsing, quiz validation and scoring, and
      attempt-history isolation.

  test_accessibility.py
      Contrast ratios in both themes, the redundant encoding of each
      confidence band, greyscale survival, and completeness of the
      translation catalogue.

  __init__.py
      Package marker.


data/
.....

  chroma_db/
      The committed vector store: 168 embedded chunks spanning Weeks 1
      to 5. REQUIRED TO RUN. The application reads this and nothing else
      at query time.

  knowledge_base_chunks.jsonl
      The chunked corpus with its metadata, produced by
      extract_and_chunk.py and consumed by build_chromadb.py.


NOT INCLUDED


  - Third-party libraries, per the submission guidance. They are listed
    under REQUIREMENTS above and installed by STEP 1.

  - The source course material. The Week 1 to 5 Network Security
    documents are the intellectual property of King's College London and
    are not redistributed. Only the embedded knowledge base derived from
    them is included, which is what the application needs to run.
