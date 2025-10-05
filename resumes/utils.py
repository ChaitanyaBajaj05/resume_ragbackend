import os
import re
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader
from django.conf import settings

_model = None  # cache for model instance

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')  # model loaded only once
    return _model

def get_embedding(text):
    model = get_model()
    return model.encode(text).tolist()

def extract_text_from_pdf(path):
    text = ""
    try:
        reader = PdfReader(path)
        for p, page in enumerate(reader.pages, start=1):
            t = page.extract_text()
            if t:
                text += f"\n\n---PAGE {p}---\n\n" + t
    except Exception as e:
        print("pdf extract err", e)
    return text

RE_PII_EMAIL = re.compile(r"[A-Za-z0-9\._%+\-]+@[A-Za-z0-9\.\-]+\.[A-Za-z]{2,}")
RE_PII_PHONE = re.compile(r"(\+?\d{2,3}[-.\s]?)?(\d{10}|\d{3}[-.\s]\d{3}[-.\s]\d{4})")

def redact_pii(text):
    text = RE_PII_EMAIL.sub("[REDACTED_EMAIL]", text)
    text = RE_PII_PHONE.sub("[REDACTED_PHONE]", text)
    return text

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    i = 0
    order = 0
    while i < len(words):
        chunk_words = words[i:i+chunk_size]
        chunk_text = " ".join(chunk_words)
        chunks.append({"text": chunk_text, "order": order})
        i += (chunk_size - overlap)
        order += 1
    return chunks

# FAISS related helpers and paths
INDEX_DIR = settings.BASE_DIR / "faiss_index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)
FAISS_INDEX_PATH = INDEX_DIR / "resume_chunks.faiss"
ID_MAP_PATH = INDEX_DIR / "id_map.json"

def ensure_faiss_index(d=384):
    if FAISS_INDEX_PATH.exists():
        index = faiss.read_index(str(FAISS_INDEX_PATH))
        id_map = json.loads(open(ID_MAP_PATH).read())
        return index, id_map
    else:
        index = faiss.IndexFlatIP(d)
        id_map = {}
        return index, id_map

def save_faiss(index, id_map):
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    with open(ID_MAP_PATH, "w") as f:
        json.dump(id_map, f)

def build_embeddings_for_chunks(chunks):
    model = get_model()
    texts = [c["text"] for c in chunks]
    vecs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    faiss.normalize_L2(vecs)
    return vecs

def add_chunks_to_index(chunk_objs):
    index, id_map = ensure_faiss_index()
    d = index.d if hasattr(index, "d") else (index.ntotal and index.reconstruct(0).shape[0]) or 384
    texts = [c.chunk_text for c in chunk_objs]
    model = get_model()
    vecs = model.encode(texts, convert_to_numpy=True)
    faiss.normalize_L2(vecs)
    start_id = index.ntotal
    index.add(vecs)
    for i, c in enumerate(chunk_objs):
        gid = start_id + i
        id_map[str(gid)] = str(c.id)
    save_faiss(index, id_map)
    return True

def query_index(query_text, k=5):
    index, id_map = ensure_faiss_index()
    model = get_model()
    qvec = model.encode([query_text], convert_to_numpy=True)
    faiss.normalize_L2(qvec)
    D, I = index.search(qvec, k)
    scores = D[0].tolist()
    ids = I[0].tolist()
    results = []
    for score, idx in zip(scores, ids):
        if idx < 0: continue
        chunk_id = id_map.get(str(idx))
        results.append({"chunk_index": idx, "chunk_id": chunk_id, "score": float(score)})
    return results
