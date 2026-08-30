# RepoPilot 架构说明

```text
                ┌──────────────┐
                │ Web / CLI API │
                └──────┬───────┘
                       │ question + repository
                ┌──────▼───────┐
                │   RepoAgent  │
                │ LLM / fallback│
                └──┬────────┬──┘
                   │        │
          ┌────────▼───┐ ┌──▼─────────────┐
          │ Tool Registry│ │ VectorIndex   │
          └────────┬───┘ └──┬─────────────┘
                   │        │ TF-IDF chunks
          ┌────────▼────────▼┐
          │ Repository Sandbox│
          │ files/tests/git   │
          └────────┬──────────┘
                   ▼
          structured report + citations + trace
```

## 请求生命周期

1. 校验本地路径或浅克隆公开 Git URL。
2. 扫描代码和文档，按行分块建立向量索引。
3. 本地模式按任务类型路由；模型模式由 Function Calling 选择工具。
4. 工具层执行只读文件操作、白名单测试或 Git Diff 摘要。
5. 解析测试输出和风险信号，生成带路径/行号的报告。
6. 将工具状态、错误和耗时写入结构化 Trace；远程临时目录自动清理。
