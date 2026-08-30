from repilot.repository import Repository

def test_list_and_read(tmp_path):
    (tmp_path / "main.py").write_text("def login():\n    return True\n")
    repo = Repository(tmp_path)
    assert "main.py" in repo.list_files()
    assert "1: def login" in repo.read_file("main.py")

def test_search_and_agent(tmp_path):
    (tmp_path / "main.py").write_text("def login():\n    return True\n")
    from repilot.agent import RepoAgent
    result = RepoAgent(str(tmp_path)).run("定位 login 函数")
    assert "main.py:1" in result.citations

def test_path_escape(tmp_path):
    repo = Repository(tmp_path)
    try:
        repo.read_file("../secret")
    except ValueError:
        pass
    else:
        assert False

def test_command_allowlist_rejects_shell_syntax(tmp_path):
    repo = Repository(tmp_path)
    import pytest
    with pytest.raises(ValueError):
        repo.run_tests("pytest -q; whoami")

def test_trace_contains_status_and_duration(tmp_path):
    (tmp_path / "main.py").write_text("def agent():\n    return True\n")
    from repilot.agent import RepoAgent
    trace = RepoAgent(str(tmp_path)).run("分析项目目录结构").trace
    assert trace[0]["status"] == "ok"
    assert "duration_ms" in trace[0]

def test_local_repository_is_not_temporary(tmp_path):
    repo = Repository(tmp_path)
    assert repo.is_temporary is False
    repo.cleanup()
