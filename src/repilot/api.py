from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .agent import RepoAgent

app = FastAPI(title="RepoPilot", version="0.2.0", description="Read-only code intelligence Agent")

@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>RepoPilot</title>
    <style>body{font:15px system-ui;max-width:1100px;margin:32px auto;padding:0 20px;color:#243447}input,textarea{width:100%;box-sizing:border-box;padding:10px;margin:6px 0 14px;border:1px solid #ccd6e0;border-radius:5px}textarea{height:80px}button{background:#1769aa;color:white;border:0;border-radius:5px;padding:10px 18px;cursor:pointer}section{margin-top:24px}pre{white-space:pre-wrap;background:#f5f7fa;padding:16px;border-radius:6px;line-height:1.55;overflow:auto}.muted{color:#697586}</style>
    <h1>RepoPilot</h1><p class='muted'>只读代码仓库分析 Agent。支持本地路径，也支持 GitHub/Git 仓库地址（可带或不带 .git，服务端自动浅克隆并在分析后清理）。</p>
    <label>仓库路径或 GitHub URL</label><input id='repo' value='https://github.com/deepseek-ai/DeepSeek-Coder' placeholder='例如：D:\\repos\\my-project 或 https://github.com/owner/project'>
    <label>问题</label><textarea id='question'>HTTP 异常在哪里定义？请给出文件和行号</textarea><button onclick='run()'>开始分析</button>
    <p class='muted'>示例：<a href='#' onclick="sample('https://github.com/deepseek-ai/DeepSeek-Coder','请定位模型推理入口并说明调用流程');return false">DeepSeek-Coder 推理入口</a> · <a href='#' onclick="sample('https://github.com/fastapi/fastapi','请分析路由注册的核心调用链');return false">FastAPI 路由调用链</a></p>
    <section><h2>分析报告</h2><pre id='answer'>等待提交问题...</pre><h3>引用</h3><pre id='citations'>-</pre><h3>工具调用 Trace</h3><pre id='trace'>-</pre></section>
    <script>function sample(r,q){document.getElementById('repo').value=r;document.getElementById('question').value=q}async function run(){const a=document.getElementById('answer');a.textContent='分析中...';try{const r=await fetch('/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({repository:document.getElementById('repo').value,question:document.getElementById('question').value})});const raw=await r.text();let d;try{d=JSON.parse(raw)}catch(_){throw Error('服务返回了非 JSON 错误：'+raw.slice(0,300))}if(!r.ok)throw Error(d.detail||'请求失败');a.textContent=d.answer;document.getElementById('citations').textContent=d.citations.length?d.citations.join('\\n'):'无';document.getElementById('trace').textContent=JSON.stringify(d.trace,null,2)}catch(e){a.textContent='错误：'+e.message}}</script></html>"""

class AnalyzeRequest(BaseModel):
    repository: str = Field(..., description="Local repository path or public Git URL")
    question: str = Field(..., min_length=2)

@app.get("/health")
def health(): return {"status": "ok", "service": "repilot"}

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    try:
        result = RepoAgent(req.repository).run(req.question)
        return {"answer": result.answer, "citations": result.citations, "trace": result.trace}
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
