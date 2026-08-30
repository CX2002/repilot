from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .agent import RepoAgent
from .config import settings

app = FastAPI(title="RepoPilot", version="0.2.0", description="Read-only code intelligence Agent")

class AnalyzeRequest(BaseModel):
    repository: str = Field(..., description="Local repository path or public Git URL")
    question: str = Field(..., min_length=2)

@app.get("/health")
def health(): return {"status": "ok", "service": "repilot"}

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="未配置 REPILOT_API_KEY，无法进行自然语言分析。请先配置 DeepSeek API Key。")
    try:
        result = RepoAgent(req.repository).run(req.question)
        return {"answer": result.answer, "citations": result.citations, "trace": result.trace}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
