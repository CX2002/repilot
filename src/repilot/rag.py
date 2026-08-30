from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import math, re
from .repository import Repository

@dataclass
class Document:
    path: str
    text: str
    start_line: int = 1
    end_line: int = 1
    score: float = 0.0

class VectorIndex:
    """Dependency-free TF-IDF vector index with chunk-level source citations."""
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
        counts=Counter(self._tokens(query)); norm=math.sqrt(sum((counts[t]*self.idf.get(t,1))**2 for t in counts)) or 1
        q={t:(c*self.idf.get(t,1))/norm for t,c in counts.items()}; ranked=[]
        for doc,vec in zip(self.docs,self.vectors):
            score=sum(q.get(t,0)*v for t,v in vec.items())
            if score: ranked.append((score,doc))
        return [Document(d.path,d.text,d.start_line,d.end_line,s) for s,d in sorted(ranked,key=lambda x:x[0],reverse=True)[:k]]
