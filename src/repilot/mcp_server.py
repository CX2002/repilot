"""MCP stdio server exposing RepoPilot's read-only repository tools."""
from __future__ import annotations
import os
from .repository import Repository

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install the optional MCP dependency: pip install 'repilot[mcp]'") from exc

mcp = FastMCP("repilot")

def _repo():
    root = os.getenv("REPILOT_MCP_REPOSITORY")
    if not root: raise ValueError("REPILOT_MCP_REPOSITORY is required")
    return Repository(root)

@mcp.tool()
def list_files(max_files: int = 500) -> list[str]:
    return _repo().list_files(max_files)

@mcp.tool()
def search_code(query: str, max_hits: int = 30) -> list[dict]:
    return [x.__dict__ for x in _repo().search_code(query, max_hits)]

@mcp.tool()
def read_file(relative: str, start: int = 1, end: int = 240) -> str:
    return _repo().read_file(relative, start, end)

@mcp.tool()
def find_symbol(symbol: str) -> list[dict]:
    return [x.__dict__ for x in _repo().find_symbol(symbol)]

@mcp.tool()
def run_tests(command: str) -> dict:
    code, output = _repo().run_tests(command)
    return {"returncode": code, "output": output}

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
