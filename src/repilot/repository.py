from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import shlex
import tempfile
import shutil
from urllib.parse import urlparse
from .config import settings

IGNORED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".repilot", "dist", "build"}
TEXT_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".md", ".yaml", ".yml", ".json", ".toml", ".ini", ".sql"}

@dataclass
class SearchHit:
    path: str
    line: int
    text: str

class Repository:
    def __init__(self, root: str | Path):
        self._temp_root = None
        if isinstance(root, str) and self._is_remote_url(root):
            self._temp_root = Path(tempfile.mkdtemp(prefix="repilot-"))
            try:
                p = subprocess.run(["git", "clone", "--depth", "1", root, str(self._temp_root)], text=True, capture_output=True, timeout=120)
                if p.returncode != 0: raise ValueError(f"Remote repository clone failed: {p.stderr[-500:]}")
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.cleanup(); raise ValueError(f"Remote repository unavailable: {exc}") from exc
            requested = self._temp_root
        else:
            requested = Path(root).expanduser()
        self.root = requested.resolve()
        if not self.root.is_dir():
            raise ValueError(f"Repository does not exist: {self.root}")
        if settings.allowed_roots and not self.is_temporary:
            roots = [Path(x).expanduser().resolve() for x in settings.allowed_roots]
            if not any(self.root == r or r in self.root.parents for r in roots):
                raise ValueError("Repository is outside the configured allowed roots")

    @staticmethod
    def _is_remote_url(value: str) -> bool:
        """Recognize cloneable repository URLs, including GitHub URLs without .git."""
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https", "git") or not parsed.netloc or not parsed.path.strip("/"):
            return False
        # Most Git servers accept both /owner/repo and /owner/repo.git forms.
        if parsed.scheme == "git" or parsed.path.rstrip("/").endswith(".git"):
            return True
        return parsed.netloc.lower().split(":", 1)[0] in {
            "github.com", "gitlab.com", "bitbucket.org"
        }

    @property
    def is_temporary(self): return self._temp_root is not None

    def cleanup(self):
        if self._temp_root and self._temp_root.exists(): shutil.rmtree(self._temp_root, ignore_errors=True)

    def _safe(self, relative: str) -> Path:
        target = (self.root / relative).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("Path escapes repository root")
        return target

    def list_files(self, max_files: int = 500) -> list[str]:
        files = []
        for p in self.root.rglob("*"):
            if p.is_file() and not p.is_symlink() and not any(part in IGNORED or part.endswith(".egg-info") for part in p.relative_to(self.root).parts):
                files.append(p.relative_to(self.root).as_posix())
        return sorted(files)[:max_files]

    def read_file(self, relative: str, start: int = 1, end: int = 240) -> str:
        p = self._safe(relative)
        if Path(self.root / relative).is_symlink():
            raise ValueError("Symbolic links are not allowed")
        if not p.is_file():
            raise FileNotFoundError(relative)
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, start); end = min(len(lines), end)
        return "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1))

    def search_code(self, query: str, max_hits: int = 30) -> list[SearchHit]:
        terms = [query] if " " not in query else query.split()
        hits: list[SearchHit] = []
        for name in self.list_files():
            if Path(name).suffix.lower() not in TEXT_EXTENSIONS: continue
            try: lines = self._safe(name).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError: continue
            for i, line in enumerate(lines, 1):
                if all(t.lower() in line.lower() for t in terms):
                    hits.append(SearchHit(name, i, line.strip()[:240]))
                    if len(hits) >= max_hits: return hits
        return hits

    def find_symbol(self, symbol: str) -> list[SearchHit]:
        pattern = re.compile(rf"\b(def|class|function|func|interface|struct)\s+{re.escape(symbol)}\b")
        results = []
        for name in self.list_files():
            if Path(name).suffix.lower() not in TEXT_EXTENSIONS: continue
            try: lines = self._safe(name).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError: continue
            for i, line in enumerate(lines, 1):
                if pattern.search(line): results.append(SearchHit(name, i, line.strip()))
        return results

    def git_diff(self, base: str = "HEAD") -> str:
        try:
            p = subprocess.run(["git", "diff", base, "--"], cwd=self.root, text=True, capture_output=True, timeout=20)
            return p.stdout or p.stderr or "No changes found."
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"git diff unavailable: {exc}"

    def git_diff_summary(self, base: str = "HEAD") -> dict:
        raw = self.git_diff(base)
        files = re.findall(r"^\+\+\+ b/(.+)$", raw, re.MULTILINE)
        added = sum(1 for line in raw.splitlines() if line.startswith("+") and not line.startswith("+++") )
        removed = sum(1 for line in raw.splitlines() if line.startswith("-") and not line.startswith("---"))
        risks = []
        if any("test" in f.lower() for f in files) and removed: risks.append("测试文件发生变更，需确认覆盖率未下降")
        if any(any(k in f.lower() for k in ("requirements", "pyproject", "package.json", "dockerfile", "config")) for f in files): risks.append("依赖、部署或配置发生变更")
        if removed > added * 2: risks.append("删除行明显多于新增行，建议重点检查回归风险")
        return {"files": files, "added": added, "removed": removed, "risks": risks, "raw": raw}

    def run_tests(self, command: str, timeout: int = 60) -> tuple[int, str]:
        allowed = {"pytest", "python", "go", "npm"}
        tokens = shlex.split(command, posix=False)
        if not tokens or tokens[0].lower() not in allowed or any(x in command for x in ("|", ">", "<", "&", ";", "`")):
            raise ValueError("Command is not in the test allowlist")
        if tokens[0].lower() == "python" and len(tokens) < 3: raise ValueError("Only python -m pytest is allowed")
        if tokens[0].lower() == "python" and tokens[1:3] != ["-m", "pytest"]: raise ValueError("Only python -m pytest is allowed")
        if tokens[0].lower() == "go" and (len(tokens) < 2 or tokens[1] != "test"): raise ValueError("Only go test is allowed")
        if tokens[0].lower() == "npm" and (len(tokens) < 2 or tokens[1] != "test"): raise ValueError("Only npm test is allowed")
        try:
            env = None
            if tokens[0].lower() in ("pytest", "python"):
                import os
                env = os.environ.copy(); env["PYTHONPATH"] = str(self.root) + os.pathsep + env.get("PYTHONPATH", "")
            p = subprocess.run(tokens, cwd=self.root, shell=False, text=True, capture_output=True, timeout=timeout, env=env)
            return p.returncode, (p.stdout + "\n" + p.stderr)[-12000:]
        except subprocess.TimeoutExpired as exc:
            return 124, f"Test command timed out after {timeout}s\n{exc}"
