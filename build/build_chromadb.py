"""Builds the vector store.

Reads the chunked knowledge base produced by extract_and_chunk.py, embeds each
chunk and writes it to a persistent ChromaDB collection for retrieval at query
time. Run this after any change to the source material.
"""

import json
import os

import chromadb

from config import CHUNKS_FILE, VECTOR_STORE_DIR, COLLECTION_NAME

#inserted in batches to bound memory use on large corpora
EMBEDDING_BATCH_SIZE = 100


def load_knowledge_base(jsonl_path) -> list:
    """Load the chunked knowledge base, one JSON object per line."""
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_metadata_record(chunk: dict) -> dict:
    """Build the metadata stored alongside a chunk's embedding.

    Keeping week, topic and artefact type in the store lets the retrieval layer
    filter on metadata as well as search by similarity, and lets an answer cite
    where each passage came from.
    """
    return {
        "week": chunk["week"],
        "topic_label": chunk["topic_label"],
        "artefact_type": chunk["artefact_type"],
        "source_file": chunk["source_file"],
        "chunk_index": chunk["chunk_index"],
        "total_chunks_in_file": chunk["total_chunks_in_file"],
        "word_count": chunk["word_count"],
    }


def populate_vector_store(collection, records: list, batch_size: int) -> None:
    """Embed and insert every chunk into the collection."""
    total = len(records)
    for start in range(0, total, batch_size):
        batch = records[start:start + batch_size]

        chunk_ids = [r["chunk_id"] for r in batch]
        chunk_texts = [r["text"] for r in batch]
        chunk_metadata = [build_metadata_record(r) for r in batch]

        collection.add(ids=chunk_ids, documents=chunk_texts,
                       metadatas=chunk_metadata)

        end = min(start + batch_size, total)
        print(f" [{end}/{total}] chunks embedded and stored")


def run_sanity_check(collection, query: str = "What is ARP spoofing") -> None:
    """Query the finished store to confirm it returns topically relevant chunks."""
    print(f"\nSanity check, query: \"{query}\"")
    results = collection.query(query_texts=[query], n_results=3)

    for rank, (meta, distance) in enumerate(
        zip(results["metadatas"][0], results["distances"][0]), start=1
    ):
        print(f"{rank}. [Week {meta['week']}, {meta['artefact_type']}] "
              f"{meta['topic_label']} (distance={distance:.3f})")


def main():
    print("=" * 70)
    print(" Network Security knowledge base, vector store construction")
    print("=" * 70)

    if not os.path.isfile(CHUNKS_FILE):
        print(f"\nERROR: could not find chunked knowledge base at:\n {CHUNKS_FILE}")
        print("Run extract_and_chunk.py first.")
        return

    print(f"\nLoading chunked knowledge base from:\n {CHUNKS_FILE}")
    records = load_knowledge_base(CHUNKS_FILE)
    print(f"Loaded {len(records)} chunks.")

    print(f"\nInitialising persistent ChromaDB store at:\n {VECTOR_STORE_DIR}")
    client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)

    #rebuilt from scratch each run, so reprocessing the knowledge base after a
    #correction never leaves stale entries behind
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Existing '{COLLECTION_NAME}' collection cleared for a fresh build.")
    except Exception:
        pass

    print(f"Creating collection '{COLLECTION_NAME}'...")
    print("(First run downloads the embedding model and needs internet access.)")
    collection = client.create_collection(name=COLLECTION_NAME)

    print("\nEmbedding and storing chunks:")
    populate_vector_store(collection, records, EMBEDDING_BATCH_SIZE)

    print("\n" + "-" * 70)
    print("Vector store build complete.")
    print(f" Total chunks stored: {collection.count()}")
    print(f" Storage location: {VECTOR_STORE_DIR}")

    run_sanity_check(collection)


if __name__ == "__main__":
    main()
