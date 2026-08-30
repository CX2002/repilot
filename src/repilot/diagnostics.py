from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass
class TestDiagnosis:
    status: str
    failures: list[str]
    likely_causes: list[str]
    locations: list[str]

def diagnose(returncode: int, output: str) -> TestDiagnosis:
    failures = re.findall(r"FAILED\s+([^\s]+)", output)
    causes = []
    for key, message in (("ModuleNotFoundError", "依赖或模块路径缺失"), ("ImportError", "导入依赖或循环依赖"), ("AssertionError", "实际结果与测试预期不一致"), ("Timeout", "执行超时或存在阻塞")):
        if key.lower() in output.lower(): causes.append(message)
    if not causes and returncode != 0: causes.append("需要结合失败测试堆栈检查实现逻辑")
    locations = sorted(set(re.findall(r"([\w./\\-]+\.py:\d+)", output)))
    return TestDiagnosis("passed" if returncode == 0 else "failed", failures, causes, locations)
