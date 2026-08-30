from __future__ import annotations
from dataclasses import dataclass, field
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from .repository import Repository
from .rag import VectorIndex
from .llm import OpenAICompatible
from .tools import definitions, execute
from .diagnostics import diagnose
from .config import settings

@dataclass
class AgentResult:
    answer: str
    citations: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)

class RepoAgent:
    def __init__(self, root: str, max_rounds: int = 6):
        self.repo = Repository(root); self.index = VectorIndex(self.repo); self.max_rounds = max_rounds; self.llm = OpenAICompatible()

    def run(self, question: str) -> AgentResult:
        if not self.llm.enabled:
            raise ValueError("未配置 REPILOT_API_KEY，无法进行自然语言分析。请先配置 DeepSeek API Key。")
        try:
            return self._run_llm(question)
        finally:
            self.repo.cleanup()

    def _run_llm(self, question: str) -> AgentResult:
        context = self.index.search(question, 5)
        rag_citations = [f"{d.path}:{d.start_line}-{d.end_line}" for d in context]
        rag_context = "\n\nRetrieved repository context (cite these path and line ranges when relevant):\n" + "\n\n".join(
            f"[{d.path}:{d.start_line}-{d.end_line}]\n{d.text[:5000]}" for d in context
        ) if context else ""
        messages = [{"role":"system","content":"You are RepoPilot, a read-only senior code analyst. Use tools to inspect the repository. Cite claims as path:line. Return a concise report with conclusion, evidence, tests, risks, and (when diagnosis fails) suggested repair steps for the developer to review. Never modify files or claim that you applied a fix."},{"role":"user","content":question + rag_context}]
        trace=[]; citations=[]
        for _ in range(self.max_rounds):
            msg = self.llm.complete(messages, definitions()); calls = msg.get("tool_calls", [])
            if not calls: return AgentResult(msg.get("content", "No answer generated"), list(dict.fromkeys(citations + rag_citations)), trace)
            messages.append(msg)
            for call in calls:
                args=json.loads(call["function"].get("arguments","{}")); name=call["function"]["name"]
                started=time.perf_counter()
                try:
                    result=execute(self.repo,name,args); event={"tool":name,"args":args,"status":"ok"}
                except Exception as exc:
                    event={"tool":name,"args":args,"status":"error","error":str(exc)}; raise
                finally:
                    event["duration_ms"]=round((time.perf_counter()-started)*1000,2); trace.append(event)
                if isinstance(result,list):
                    citations.extend(f"{x['path']}:{x['line']}" for x in result if isinstance(x,dict) and "path" in x and "line" in x)
                messages.append({"role":"tool","tool_call_id":call["id"],"content":json.dumps(result,ensure_ascii=False,default=str)[:12000]})
        messages.append({"role":"user","content":"工具调用轮数已达上限。请基于目前已经获得的工具结果，立即输出最终结构化报告，不要再调用工具。报告必须包含结论、证据、测试结果、风险和建议；引用已有的 path:line。"})
        try:
            final = self.llm.complete(messages, tools=[])
            return AgentResult(final.get("content", "无法生成最终报告"), citations, trace + [{"event":"max_rounds_summary"}])
        except Exception as exc:
            return AgentResult("已完成部分仓库检索，但最终总结服务暂时不可用。请查看下方 Trace 和引用，或稍后重试。", citations, trace + [{"event":"max_rounds_summary_error", "error":str(exc)}])

    def _run_local(self, question: str) -> AgentResult:
        q=question.lower(); trace=[]; citations=[]
        def call(name, **args):
            started=time.perf_counter(); event={"tool":name,"args":args}
            try: value=getattr(self.repo,name)(**args); event["status"]="ok"; return value
            except Exception as exc: event.update(status="error", error=str(exc)); raise
            finally: event["duration_ms"]=round((time.perf_counter()-started)*1000,2); trace.append(event)
        if any(x in q for x in ("功能", "作用", "能做什么", "项目介绍", "介绍一下", "介绍这个项目", "分析这个项目", "项目概述", "项目情况", "项目是做什么", "用途", "目的", "是什么项目", "overview", "what does")):
            files = call("list_files", max_files=300)
            top = sorted({p.split("/")[0] for p in files})
            readme = next((p for p in files if Path(p).name.lower().startswith("readme")), None)
            readme_excerpt = ""
            if readme:
                try:
                    readme_excerpt = call("read_file", relative=readme, start=1, end=40)
                    citations.append(f"{readme}:1")
                except (OSError, ValueError):
                    pass
            answer = (
                "项目功能概览：\n"
                "- 自动扫描本地目录或公开 Git 仓库，建立可检索的代码上下文；\n"
                "- 通过代码搜索、符号定位和 RAG 检索回答仓库问题，并返回文件与行号；\n"
                "- 可在白名单命令范围内运行测试，分析失败日志并给出建议；\n"
                "- 可总结 Git Diff，并通过 API 或 MCP 提供服务。\n\n"
                f"仓库主要目录/文件：{', '.join(top[:30]) or '未识别'}"
            )
            if readme_excerpt:
                answer += f"\n\nREADME 摘要（{readme}）：\n{readme_excerpt[:3000]}"
        elif any(x in q for x in ("目录","结构","文件","structure")):
            files = call("list_files", max_files=500)
            groups = {}
            for path in files:
                parts = path.split("/")
                key = parts[0]
                groups.setdefault(key, []).append(path)
            rows = []
            for key, members in sorted(groups.items()):
                if len(members) == 1:
                    rows.append(f"- {key}")
                else:
                    samples = ", ".join(members[:3])
                    suffix = " ..." if len(members) > 3 else ""
                    rows.append(f"- {key}/（{len(members)} 个文件；示例：{samples}{suffix}）")
            answer = "项目结构摘要：\n" + "\n".join(rows[:80])
            answer += f"\n\n共发现 {len(files)} 个可分析文件；已按顶层目录聚合，避免展开数据集和生成文件。"
        elif any(x in q for x in ("测试","test","失败","fail")):
            code,out=call("run_tests",command="python -m pytest -q" if "python" in q else "pytest -q", timeout=settings.test_timeout); d=diagnose(code,out); suggestion="建议：根据失败堆栈检查相关实现和依赖，修复后由开发者重新运行测试。" if code else "建议：保持现有测试并继续补充边界用例。"; answer=f"测试状态：{d.status}\n失败用例：{', '.join(d.failures) or '无'}\n源码位置：{', '.join(d.locations) or '未解析到'}\n可能原因：{', '.join(d.likely_causes) or '无'}\n{suggestion}\n```text\n{out}\n```"
        elif any(x in q for x in ("diff","变更","修改")):
            summary=call("git_diff_summary"); answer=f"Git Diff 报告：\n变更文件：{', '.join(summary['files']) or '无'}\n新增行：{summary['added']}，删除行：{summary['removed']}\n风险信号：{', '.join(summary['risks']) or '未发现明显信号'}\n\n```diff\n{summary['raw'][-12000:]}\n```"
        else:
            hits=call("search_code",query=question,max_hits=20)
            if not hits:
                for term in ("login", "auth", "user", "main", "agent"):
                    hits=call("search_code",query=term,max_hits=10)
                    if hits: break
            citations=[f"{h.path}:{h.line}" for h in hits]
            answer="代码检索结果：\n"+"\n".join(f"- `{h.path}:{h.line}` {h.text}" for h in hits) if hits else "未找到直接匹配。"
            context = self.index.search(question, 3)
            if context: answer += "\n\n向量检索上下文：\n" + "\n".join(f"- `{d.path}:{d.start_line}-{d.end_line}` (score={d.score:.3f})" for d in context)
        result = AgentResult(answer,citations,trace)
        try:
            path = self.repo.root / settings.trace_dir; path.mkdir(parents=True, exist_ok=True)
            (path / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')).write_text(json.dumps({'question':question,'result':result.__dict__}, ensure_ascii=False, default=str), encoding='utf-8')
        except OSError: pass
        return result
