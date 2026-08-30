# 真实仓库演示

RepoPilot 不需要预置数据集即可分析任意本地或公开 Git 仓库。下面以公开、规模适中的仓库作为可复现演示入口；运行前请确认遵守对应仓库许可证。

## FastAPI

```text
仓库：https://github.com/fastapi/fastapi.git
问题：请分析路由注册的核心调用链，并指出相关测试文件
```

## Requests

```text
仓库：https://github.com/psf/requests.git
问题：HTTP 请求异常是如何定义和抛出的？请给出文件与行号
```

## 演示建议

```text
1. 调用 `POST /analyze`，提交 Git URL 和问题；
2. 先询问目录/入口，再询问具体调用链；
3. 运行“请执行测试并分析失败原因”（大型仓库可能超时）；
4. 查看返回结果中的 `citations` 和 `trace`。
```

远程仓库会浅克隆到临时目录，分析结束后自动清理；不会被复制进本项目。
