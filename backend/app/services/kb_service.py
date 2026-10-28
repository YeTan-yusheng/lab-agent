import chromadb
from chromadb.api.models.Collection import Collection
from app.config import BASE_DIR

KB_DIR = BASE_DIR / "data" / "kb"
CHROMA_DIR = BASE_DIR / "data" / "chroma"

_collection = None


def get_collection() -> Collection:
    """向量库初始化"""
    global _collection
    if _collection is not None:
        return _collection
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    KB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = client.get_or_create_collection(name="lab_kb")
    if col.count() == 0:
        ids = []
        docs = []
        metadatas = []
        for path in sorted(KB_DIR.glob("*.md")):
            text = path.read_text(encoding="UTF-8").strip()
            if not text:
                continue
            docs.append(text)
            ids.append(path.stem)
            metadatas.append({"source": path.name})
            if docs:
                col.add(ids=ids, documents=docs, metadatas=metadatas)
    _collection = col
    return col


def search(query: str):
    """根据关键字检索向量库"""
    col = get_collection()
    if col.count() == 0:
        return ""

    limit = min(5, col.count())
    res = col.query(query_texts=[query], n_results=limit)
    docs = (res.get("documents") or [[]])[0]
    metadatas = (res.get("metadatas") or [[]])[0]
    distances = (res.get("distances") or [[]])[0]
    score_parts = []
    for doc, metadata, dist in zip(docs, metadatas, distances):
        score = 1 / (1 + dist)
        name = metadata.get("source") or ""
        score_parts.append({"score": score, "content": f"[{name}]\n{doc}"})

    score_parts.sort(key=lambda x: x["score"], reverse=True)
    final_parts = [item["content"] for item in score_parts[:2]]
    return "\n\n".join(final_parts)
