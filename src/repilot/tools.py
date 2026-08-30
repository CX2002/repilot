from __future__ import annotations
from .repository import Repository

def definitions():
    def schema(name, description, properties, required=[]):
        return {"type":"function", "function":{"name":name,"description":description,"parameters":{"type":"object","properties":properties,"required":required}}}
    return [schema("list_files","List source files",{"max_files":{"type":"integer"}}), schema("search_code","Search source text",{"query":{"type":"string"},"max_hits":{"type":"integer"}},["query"]), schema("read_file","Read file with line numbers",{"relative":{"type":"string"},"start":{"type":"integer"},"end":{"type":"integer"}},["relative"]), schema("find_symbol","Find definitions",{"symbol":{"type":"string"}},["symbol"]), schema("git_diff_summary","Summarize changed files and risk signals",{"base":{"type":"string"}}), schema("run_tests","Run allowlisted tests",{"command":{"type":"string"}},["command"])]

def execute(repo: Repository, name: str, args: dict):
    value = getattr(repo, name)(**args)
    if isinstance(value, list): return [getattr(x, "__dict__", x) for x in value]
    return value
