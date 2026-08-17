from pathlib import Path

BASE_DIR = Path(__file__).parent

APP_NAME = "Cyber Tutor"
APP_ICON = BASE_DIR / "assets" / "icon.png"

#knowledge base
SOURCE_DIR = BASE_DIR / "data" / "Network security content"
CLEANED_DIR = BASE_DIR / "data" / "Network security content (Cleaned)"
CHUNKS_FILE = BASE_DIR / "data" / "knowledge_base_chunks.jsonl"

#vector store. chromadb.PersistentClient takes a string
VECTOR_STORE_DIR = str(BASE_DIR / "data" / "chroma_db")
COLLECTION_NAME = "network_security_kb"

#evaluation workbook. the gpt-oss-20b run, which is the model GROQ_MODEL names below.
#gold_set_evaluation.xlsx is the earlier Llama 3.1 run and the primary evaluation
GOLD_SET_FILE = BASE_DIR / "evaluation" / "gold_set_evaluation_gptoss20b.xlsx"
GOLD_SET_SHEET = "Gold Set"



#quiz attempts live in the session now, not on disk. see record_attempt() in core/quiz.py

#generation
GROQ_MODEL = "openai/gpt-oss-20b"
RETRIEVAL_TOP_K = 5

#confidence bands, set empirically against the distance distribution of the knowledge base
CONF_HIGH_THRESHOLD = 0.85    #mean distance below this gives High
CONF_MEDIUM_THRESHOLD = 1.10  #below this gives Medium, otherwise Low
