Jannat Faisal
K19016525

# Cyber Tutor
The application is also running here--> https://cyber-tutor.streamlit.app/
## Requirements

- Python 3.11 or later
- A Groq API key (free tier is sufficient) from https://console.groq.com/keys

Packages, all installed by step 1 below:

| Package | Version | Needed for |
|---|---|---|
| streamlit | 1.59.0 | the application |
| chromadb | 1.5.9 | the vector store |
| groq | 1.5.0 | the generation API |
| pillow | 12.1.0 | the app icon |
| pysqlite3-binary | linux only | hosts shipping sqlite3 older than 3.35 |
| python-docx | 1.2.0 | knowledge base construction, `build/` only |
| python-pptx | 1.0.2 | knowledge base construction, `build/` only |
| pypdf | 6.14.2 | knowledge base construction, `build/` only |
| lxml | 6.1.1 | knowledge base construction, `build/` only |
| openpyxl | 3.1.5 | evaluation and tests only |
| pytest | 9.1.1 | evaluation and tests only |

## Steps to run

STEP 1. Install the dependencies**

```bash
py -m pip install -r requirements.txt
```

STEP 2. Set the API key for the session**

```bash
$env:GROQ_API_KEY='key-here'
```

On bash or zsh use `export GROQ_API_KEY="key-here"` instead.
STEP 3. Start the application**

```bash
py -m streamlit run streamlit_app.py
```

STEP 4. Open it in the browser**

Streamlit prints a local URL, normally http://localhost:8501, and opens it
automatically.

The vector store is committed under `data/chroma_db`, so there is no build step
and nothing else to prepare.
