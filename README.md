# FOFA Query Compiler

一个本地运行、可审计的自然语言到 FOFA 查询语句编译器。CLI 与 Web 界面共享同一套领域模型、工作区和业务服务；项目不包含部署或自动提交答卷功能。

> [!IMPORTANT]
> 项目目前处于早期开发阶段，功能尚未完成。实现范围与进度以
> [`specs/001-fofa-query-compiler/`](specs/001-fofa-query-compiler/) 中的规范、计划和任务为准。

## 开发环境

- Python 3.12 或更高版本
- 建议使用独立虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

## 项目结构

- `src/fofa_compiler/`：领域、应用、基础设施及 Web 适配层
- `tests/`：自动化测试
- `specs/`：功能规格、设计与实现任务
- `题目/`：原始题目及参赛资料

## 参与贡献

欢迎通过 Issue 报告问题或提交 Pull Request。提交代码前请运行测试及静态检查：

```bash
pytest
ruff check .
mypy src
```

## 许可证

本项目采用 [MIT License](LICENSE)。
