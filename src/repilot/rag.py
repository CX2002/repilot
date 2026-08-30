from __future__ import annotations
from dataclasses import dataclass
import httpx
import math, re
from collections import Counter
from .repository import Repository

@dataclass
class Document:
    path: str
    text: str
    start_line: int = 1
    end_line: int = 1
    score: float = 0.0

class VectorIndex:
    """Embedding-based vector index with chunk-level source citations."""
    def __init__(self, repo: Repository, chunk_lines: int = 80):
        self.repo = repo; self.docs: list[Document] = []; self.vectors=[]; self.idf={}
        files = (p for p in repo.list_files() if p.endswith((".md", ".py", ".js", ".ts", ".yaml", ".yml", ".json")))
        for path in files:
            raw = repo.read_file(path, 1, 100000).splitlines()
            for offset in range(0, len(raw), chunk_lines):
                text = "\n".join(raw[offset:offset+chunk_lines]); self.docs.append(Document(path,text,offset+1,min(len(raw),offset+chunk_lines)))
        terms = [self._tokens(d.text) for d in self.docs]; df=Counter(t for ts in terms for t in set(ts)); n=max(1,len(self.docs)); self.idf={t:math.log((1+n)/(1+c))+1 for t,c in df.items()}
        for ts in terms:
            counts=Counter(ts); norm=math.sqrt(sum((counts[t]*self.idf.get(t,1))**2 for t in counts)) or 1; self.vectors.append({t:(c*self.idf.get(t,1))/norm for t,c in counts.items()})

    @staticmethod
    def _tokens(text): return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*|[\u4e00-\u9fff]+", text.lower())

    def search(self, query: str, k: int = 5) -> list[Document]:
        from .config import settings
        if settings.embedding_api_key:
            try:
                return self._embedding_search(query, k, settings)
            except (OSError, httpx.HTTPError, KeyError, ValueError):
                pass
        counts=Counter(self._tokens(query)); norm=math.sqrt(sum((counts[t]*self.idf.get(t,1))**2 for t in counts)) or 1
        q={t:(c*self.idf.get(t,1))/norm for t,c in counts.items()}; ranked=[]
        for doc,vec in zip(self.docs,self.vectors):
            score=sum(q.get(t,0)*v for t,v in vec.items())
            if score: ranked.append((score,doc))
        return [Document(d.path,d.text,d.start_line,d.end_line,s) for s,d in sorted(ranked,key=lambda x:x[0],reverse=True)[:k]]

    def _embedding_search(self, query, k, settings):
        texts = [d.text for d in self.docs]
        response = httpx.post(settings.embedding_base_url.rstrip("/") + "/embeddings",
            headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
            json={"model": settings.embedding_model, "input": [query] + texts}, timeout=60)
        response.raise_for_status()
        data = response.json()["data"]
        vectors = [x["embedding"] for x in sorted(data, key=lambda x: x["index"])]
        qv, dvs = vectors[0], vectors[1:]
        qnorm = math.sqrt(sum(x*x for x in qv)) or 1.0
        scored=[]
        for doc, vec in zip(self.docs, dvs):
            norm = math.sqrt(sum(x*x for x in vec)) or 1.0
            score = sum(a*b for a,b in zip(qv, vec)) / (qnorm * norm)
            scored.append((score, doc))
        return [Document(d.path,d.text,d.start_line,d.end_line,s) for s,d in sorted(scored,key=lambda x:x[0], reverse=True)[:k]]
