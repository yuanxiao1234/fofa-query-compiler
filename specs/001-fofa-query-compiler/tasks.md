---

description: "FOFA 自然语言查询编译器的依赖有序实施任务"
---

# Tasks: FOFA Natural-Language Query Compiler

**Input**: `specs/001-fofa-query-compiler/spec.md`、`specs/001-fofa-query-compiler/plan.md`、`.specify/memory/constitution.md` 与 `题目/` 下的当前参赛包

**实现假设**: 当前 `plan.md` 尚未填写。任务按章程约束采用 Python 3.12、Pydantic v2、pytest；首版为本机单用户应用，业务核心由 CLI 与 FastAPI/Jinja Web UI 共享，状态持久化为 UTF-8 JSON 文件，不引入数据库和部署设施。T001 必须先把这些决策补入计划。

**Tests**: 规格与章程明确要求独立验收、先失败后实现，因此各用户故事均包含测试任务。

**Organization**: 任务按用户故事组织；每个故事完成后均可按本阶段的独立测试标准验收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可与同阶段其他标记任务并行，涉及不同文件且不依赖未完成任务
- **[Story]**: 对应 `spec.md` 中的用户故事
- 所有任务均给出明确文件路径

## Phase 1: Setup（共享工程基础）

**Purpose**: 固化技术决策并建立可测试的 Python 项目骨架

- [X] T001 将 Python 3.12、Pydantic v2、FastAPI/Jinja、本地 JSON 工作区、CLI/Web 共享核心及真实目录结构补入 `specs/001-fofa-query-compiler/plan.md`
- [X] T002 创建项目元数据、运行依赖、开发依赖和 `fofa-compiler` CLI 入口于 `pyproject.toml`
- [X] T003 [P] 创建包与分层骨架于 `src/fofa_compiler/__init__.py`、`src/fofa_compiler/domain/__init__.py`、`src/fofa_compiler/application/__init__.py`、`src/fofa_compiler/infrastructure/__init__.py`、`src/fofa_compiler/web/__init__.py`
- [X] T004 [P] 配置 Ruff、mypy 与 pytest 的项目规则于 `pyproject.toml`
- [X] T005 [P] 创建测试共享 fixture 和临时工作区工厂于 `tests/conftest.py`

**Checkpoint**: 项目可安装，空测试套件、静态检查与 CLI 帮助命令可运行。

---

## Phase 2: Foundational（阻塞性公共能力）

**Purpose**: 建立所有故事共用的领域模型、工作区、错误和应用服务边界

**⚠️ CRITICAL**: 本阶段完成前不得开始用户故事实现。

- [X] T006 编写题目、参赛包、规范化意图、候选答案、验证结果、证据记录、复核记录、最终答案和答卷的 Pydantic v2 模型于 `src/fofa_compiler/domain/models.py`
- [X] T007 [P] 定义处理状态、风险级别、证据状态、匹配模式、逻辑运算符及固定拒绝文本于 `src/fofa_compiler/domain/enums.py`
- [X] T008 [P] 定义可定位到文件、JSON 路径和题号的领域错误层级于 `src/fofa_compiler/domain/errors.py`
- [X] T009 实现带格式版本、原子写入、确定性序列化和损坏检测的工作区仓储于 `src/fofa_compiler/infrastructure/workspace.py`
- [X] T010 [P] 定义生成器、证据读取器、时钟和工作区仓储端口于 `src/fofa_compiler/application/ports.py`
- [X] T011 实现共享应用服务容器与 CLI/Web 共用的用例装配于 `src/fofa_compiler/application/container.py`
- [X] T012 [P] 实现统一的结构化审计日志并过滤凭据、模型推理和未授权数据于 `src/fofa_compiler/infrastructure/audit_log.py`
- [X] T013 为领域模型往返、工作区重开和原子写入失败恢复编写单元测试于 `tests/unit/test_workspace.py`

**Checkpoint**: 领域对象可持久化并重载，CLI 与 Web 能通过同一容器调用同一业务服务。

---

## Phase 3: User Story 1 - 导入并核验参赛包（Priority: P1）🎯 MVP 基础

**Goal**: 安全导入题目、参赛包信息和答案模板，完整报告格式与题号集合问题且不修改原文件。

**Independent Test**: 分别导入真实题包与无效 JSON、缺题、重复题号、未知题号、BOM/换行差异样例；仅完整且题号集合一致的包被接受，并保留输入顺序与包编号。

### Tests for User Story 1

- [X] T014 [P] [US1] 为合法题包、UTF-8 BOM、空白与不同换行编写导入测试于 `tests/integration/test_package_import.py`
- [X] T015 [P] [US1] 为无效 JSON、缺失字段、缺题、重复与未知题号编写失败测试于 `tests/integration/test_package_import_errors.py`

### Implementation for User Story 1

- [X] T016 [P] [US1] 实现题目 JSON、答案模板 JSON 和参赛包文本的只读解析器于 `src/fofa_compiler/infrastructure/package_reader.py`
- [X] T017 [US1] 实现必需字段、包编号、数量、题号唯一性与集合一致性校验服务于 `src/fofa_compiler/application/import_package.py`
- [X] T018 [US1] 保存已核验参赛包、原始顺序和导入诊断到工作区于 `src/fofa_compiler/application/import_package.py`
- [X] T019 [US1] 添加 `package import` 与 `package status` 命令及可定位错误输出于 `src/fofa_compiler/cli.py`

**Checkpoint**: 真实 `题目/` 包可导入；所有结构错误一次性列全且原文件哈希不变。

---

## Phase 4: User Story 2 - 生成可执行的 FOFA 查询（Priority: P1）

**Goal**: 将每题转换为类型化 IR，经确定性规范化与渲染后得到唯一完整的 FOFA Query。

**Independent Test**: 使用按意图家族人工审阅的独立 fixture，覆盖基础字段、地理、协议、产品、响应、证书、TLS/JARM、哈希、正则、时间、域名关系、转义与嵌套布尔逻辑，并按原子语义断言结果。

### Tests for User Story 2

- [ ] T020 [P] [US2] 建立逐题来源说明与预期原子约束的基准 fixture 于 `tests/fixtures/intent_cases.json`
- [X] T021 [P] [US2] 编写字段、运算符、值类型、分组优先级和转义的 AST 渲染单元测试于 `tests/unit/test_renderer.py`
- [ ] T022 [P] [US2] 编写当前题包各意图家族的规则翻译集成测试于 `tests/integration/test_rule_translation.py`
- [X] T023 [P] [US2] 编写相同输入连续三次生成相同 IR、查询和审计状态的确定性测试于 `tests/integration/test_determinism.py`

### Implementation for User Story 2

- [X] T024 [P] [US2] 定义 Predicate、And、Or、Not 与 Group 的判别联合 IR 模型及来源引用于 `src/fofa_compiler/domain/ir.py`
- [X] T025 [P] [US2] 建立经证据标注的 FOFA 字段、合法运算符和值类型注册表于 `src/fofa_compiler/rules/fields.yaml`
- [X] T026 [P] [US2] 建立国家地区、云厂商、协议、产品类别和别名的版本化映射于 `src/fofa_compiler/rules/mappings.yaml`
- [X] T027 [US2] 实现 IR 规范化、稳定排序但不改变逻辑语义、字面量转义和显式括号渲染于 `src/fofa_compiler/domain/renderer.py`
- [X] T028 [US2] 实现基础资产、网络位置、端口协议和产品类别规则翻译器于 `src/fofa_compiler/application/translators/core.py`
- [X] T029 [P] [US2] 实现网页响应、状态码、标题、正文、响应头和 Banner 规则翻译器于 `src/fofa_compiler/application/translators/web.py`
- [X] T030 [P] [US2] 实现证书、TLS 版本、JARM、哈希和域名关系规则翻译器于 `src/fofa_compiler/application/translators/certificate.py`
- [X] T031 [P] [US2] 实现时间边界、正则、范围与嵌套布尔逻辑规则翻译器于 `src/fofa_compiler/application/translators/advanced.py`
- [X] T032 [US2] 实现窄接口语义解析适配器，使离线规则路径不依赖模型且模型只能产出待验证 IR 于 `src/fofa_compiler/infrastructure/semantic_parser.py`
- [X] T033 [US2] 编排逐题解析、IR 规范化、渲染、状态保存和单题失败隔离于 `src/fofa_compiler/application/generate_answers.py`
- [X] T034 [US2] 添加 `generate all` 与 `generate one` 命令于 `src/fofa_compiler/cli.py`

**Checkpoint**: 可转换基准题均产出仅含查询文本的确定性候选结果，原子约束可追溯到独立 fixture。

---

## Phase 5: User Story 3 - 安全拒绝不可转换需求（Priority: P1）

**Goal**: 对非法、矛盾、主观、不可观察或 FOFA 不支持的需求只返回精确固定拒绝文本。

**Independent Test**: 输入非法端口/IP/CIDR/时间/哈希、相斥条件、主观指标、运行时遥测与无法等价迁移的搜索语法，全部输出精确固定文本并记录非提交用原因。

### Tests for User Story 3

- [X] T035 [P] [US3] 编写 IP、CIDR、IP 闭区间、端口、ASN、时间、哈希和证书序列号的边界与性质测试于 `tests/unit/test_value_validation.py`
- [X] T036 [P] [US3] 编写矛盾、不可观察能力、主观条件和跨搜索引擎语义缺失的拒绝测试于 `tests/integration/test_safe_rejection.py`

### Implementation for User Story 3

- [X] T037 [P] [US3] 实现 IP/CIDR/范围、端口、ASN、时间、哈希和证书值验证器于 `src/fofa_compiler/domain/value_validation.py`
- [X] T038 [P] [US3] 实现互斥谓词、恒假组合和逻辑矛盾检测于 `src/fofa_compiler/domain/contradictions.py`
- [X] T039 [US3] 实现字段、运算符、括号、引号、转义、类型及语义完整性查询校验器于 `src/fofa_compiler/domain/query_validator.py`
- [X] T040 [US3] 实现不可表达能力分类与固定拒绝决策，并将原因只写入审计记录于 `src/fofa_compiler/application/reject_unsupported.py`
- [X] T041 [US3] 将校验失败和必要语义无法保留的结果接入逐题生成编排于 `src/fofa_compiler/application/generate_answers.py`

**Checkpoint**: 已知不可转换基准的拒绝准确率为 100%，提交值与固定文本逐字符一致。

---

## Phase 6: User Story 5 - 导出合规答卷（Priority: P1）

**Goal**: 仅在全部门禁满足时按输入顺序导出结构精确、无审计信息的 UTF-8 JSON 答卷。

**Independent Test**: 对 100 题状态验证包编号、题号集合、顺序、数量和查询字段；空答案、缺题、重复、未知题号或未确认题目均阻止写文件并列出全部问题。

### Tests for User Story 5

- [X] T042 [P] [US5] 编写 100 题合法答卷结构、UTF-8、顺序和确定性导出的端到端测试于 `tests/e2e/test_answer_export.py`
- [X] T043 [P] [US5] 编写空答案、ID 集合异常、未确认、证据阻塞和输出污染的门禁测试于 `tests/integration/test_export_gates.py`

### Implementation for User Story 5

- [X] T044 [US5] 实现完整性、逐题确认、高风险检查与证据阻塞的导出门禁聚合器于 `src/fofa_compiler/application/export_gates.py`
- [X] T045 [US5] 实现按原始顺序输出且只含选手名、包编号、题号和最终查询的原子 JSON 导出器于 `src/fofa_compiler/application/export_answers.py`
- [X] T046 [US5] 添加 `export` 命令、覆盖保护和全部阻塞项报告于 `src/fofa_compiler/cli.py`

**Checkpoint**: 合法状态生成标准解析器可读的答卷；任何门禁失败均不产生或覆盖目标文件。

---

## Phase 7: User Story 4 - 审阅高风险答案与证据（Priority: P2）

**Goal**: 逐题查看风险、验证与证据，支持修订、重新校验和双人语义验收，所有题确认后方可导出。

**Independent Test**: 对混合风险题检查标记、来源替代与阻塞；修改答案后旧确认失效；两名复核者分歧解决前不能形成通过结论。

### Tests for User Story 4

- [X] T047 [P] [US4] 编写复杂分组、正则、转义、外部资料、指纹与低置信度风险分类测试于 `tests/unit/test_risk_classification.py`
- [X] T048 [P] [US4] 编写原始来源、官方替代、存档、用户材料和不可访问阻塞的证据测试于 `tests/integration/test_evidence_review.py`
- [X] T049 [P] [US4] 编写修改失效旧确认、风险检查清单和双人分歧解决测试于 `tests/integration/test_manual_review.py`

### Implementation for User Story 4

- [X] T050 [P] [US4] 实现风险规则、强制检查项与原因分类于 `src/fofa_compiler/domain/risk.py`
- [X] T051 [P] [US4] 实现证据来源类型、内容摘要、提取事实、访问状态与替代来源合格性校验于 `src/fofa_compiler/application/evidence.py`
- [X] T052 [US4] 实现逐题修订、重新校验、旧确认失效和审计记录更新于 `src/fofa_compiler/application/review_answer.py`
- [X] T053 [US4] 实现两名独立复核者按字段、匹配方式、值、逻辑、否定和边界作出原子判定及分歧解决于 `src/fofa_compiler/application/semantic_acceptance.py`
- [X] T054 [US4] 添加 `review show`、`review amend`、`review confirm` 和 `evidence add` 命令于 `src/fofa_compiler/cli.py`

**Checkpoint**: 每题均有可审计确认状态；证据不足、高风险检查未完成或双人分歧时导出门禁保持关闭。

---

## Phase 8: User Story 6 - 使用本地 Web 界面完成作答（Priority: P1）

**Goal**: 浏览器覆盖导入、生成、进度、筛选、逐题复核、证据和导出，并与 CLI 使用完全相同的状态与规则。

**Independent Test**: 在全新本地环境只用浏览器完成真实 100 题流程；刷新后状态不丢失，生成中每 2 秒内更新进度，最终下载与 CLI 导出逐字节一致。

### Tests for User Story 6

- [X] T055 [P] [US6] 编写 Web 路由的导入、生成状态、筛选、复核、证据和导出门禁集成测试于 `tests/integration/test_web_routes.py`
- [ ] T056 [P] [US6] 编写本机绑定、状态恢复、失败隔离、2 秒进度轮询和 CLI/Web 导出一致性的浏览器测试于 `tests/e2e/test_web_workflow.py`

### Implementation for User Story 6

- [X] T057 [P] [US6] 实现仅绑定回环地址的 FastAPI 应用、依赖注入与安全响应头于 `src/fofa_compiler/web/app.py`
- [X] T058 [US6] 实现题包上传、导入诊断和工作区摘要路由于 `src/fofa_compiler/web/routes/packages.py`
- [X] T059 [US6] 实现批量生成、单题失败隔离及总数/完成/处理中/失败/阻塞进度路由于 `src/fofa_compiler/web/routes/generation.py`
- [X] T060 [P] [US6] 实现按状态、风险、证据、验证结果和题号筛选的题目与详情路由于 `src/fofa_compiler/web/routes/questions.py`
- [X] T061 [US6] 实现答案修订、证据补齐、风险核对、重新校验和确认路由于 `src/fofa_compiler/web/routes/review.py`
- [X] T062 [US6] 实现复用共享导出用例的门禁展示与文件下载路由于 `src/fofa_compiler/web/routes/export.py`
- [X] T063 [P] [US6] 创建导入、仪表盘、题目列表、逐题复核和导出页面于 `src/fofa_compiler/web/templates/import.html`、`src/fofa_compiler/web/templates/dashboard.html`、`src/fofa_compiler/web/templates/questions.html`、`src/fofa_compiler/web/templates/review.html`、`src/fofa_compiler/web/templates/export.html`
- [X] T064 [US6] 实现无构建步骤的筛选、保存反馈和至多 2 秒进度轮询于 `src/fofa_compiler/web/static/app.js` 与 `src/fofa_compiler/web/static/app.css`
- [X] T065 [US6] 添加 `web` 本地启动命令并拒绝非回环监听参数于 `src/fofa_compiler/cli.py`

**Checkpoint**: 核心工作流无需命令行即可完成，页面重开后进度保留，CLI/Web 业务结果一致。

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 完成全题包质量门禁、可复现说明与人工验收材料。

- [ ] T066 [P] 为安装、本地启动、CLI/Web 工作流、工作区备份和不部署边界编写操作说明于 `README.md`
- [ ] T067 [P] 建立 100 题逐题意图家族、来源、风险与覆盖追踪表于 `specs/001-fofa-query-compiler/question-coverage.md`
- [ ] T068 对当前 100 题逐题补齐独立来源证据与人工审阅原子约束于 `tests/fixtures/intent_cases.json`
- [ ] T069 运行并记录 Ruff、mypy、pytest、100 题结构校验和三次确定性验证结果于 `specs/001-fofa-query-compiler/validation-report.md`
- [ ] T070 检查答卷与仓库产物不含账号、密钥、推理痕迹、解释或未授权数据，并记录结果于 `specs/001-fofa-query-compiler/validation-report.md`
- [ ] T071 组织两名独立复核者完成 100 题语义全通过验收与分歧闭环于 `specs/001-fofa-query-compiler/review-ledger.json`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖；T001 先固化计划，T002 后可并行执行 T003-T005。
- **Foundational (Phase 2)**: 依赖 Phase 1，阻塞所有用户故事。
- **US1 / Phase 3**: 依赖 Phase 2；建立有效工作区后才可批量生成。
- **US2 / Phase 4**: 依赖 US1；T024-T026 可并行，T028-T031 在 T027 后按不同文件并行。
- **US3 / Phase 5**: 依赖 US2 的 IR 与生成编排；T037 与 T038 可并行。
- **US5 / Phase 6**: 依赖 US1-US3；先建立严格导出骨架，后续 US4 会补齐人工复核门禁状态。
- **US4 / Phase 7**: 依赖 US2、US3 和 US5 门禁；T050 与 T051 可并行。
- **US6 / Phase 8**: 依赖 US1-US5 的共享用例；各只读/展示路由可并行，写操作按共享服务串接。
- **Polish / Phase 9**: 依赖计划纳入交付范围的全部用户故事；T068 完成后才能执行 T069-T071。

### User Story Dependency Graph

```text
Setup → Foundation → US1 → US2 → US3 → US5 → US4 → US6 → Polish
                              └──────────────→ US6
```

- **US1** 独立验收题包结构，不依赖其他故事。
- **US2** 使用 US1 的题目和工作区，但查询生成可独立验收。
- **US3** 扩展 US2 的验证与拒绝路径，可独立用不可转换集验收。
- **US5** 使用已有最终结果并建立导出结构与基础门禁。
- **US4** 在 US5 门禁上增加逐题人工确认、证据和双人复核要求。
- **US6** 只编排已有共享用例，不复制 CLI 业务逻辑。

### Within Each User Story

1. 先提交测试并确认在实现前失败。
2. 领域模型/规则先于应用服务，应用服务先于 CLI/Web 入口。
3. 每次修改答案或证据后先重新校验，再更新确认状态。
4. 每个阶段到达 Checkpoint 后执行聚焦测试，再运行完整测试套件。

## Parallel Execution Examples

### User Story 2

```text
并行 A: T020 维护基准 fixture
并行 B: T021 编写渲染器测试
并行 C: T024 定义类型化 IR

T027 完成后：
并行 D: T028 核心资产翻译器
并行 E: T029 Web 响应翻译器
并行 F: T030 证书/TLS 翻译器
并行 G: T031 高级逻辑翻译器
```

### User Story 4

```text
并行 A: T047 风险分类测试 + T050 风险规则
并行 B: T048 证据测试 + T051 证据服务
完成以上后: T052 修订流程 → T053 双人验收 → T054 CLI
```

### User Story 6

```text
并行 A: T057 Web 应用骨架
并行 B: T063 页面模板
T057 完成后可并行: T058 导入路由、T059 生成路由、T060 查询路由
随后串行: T061 复核写操作 → T062 导出 → T064 前端交互 → T065 启动命令
```

## Implementation Strategy

### MVP First

最小可验证增量为 **Phase 1 + Phase 2 + US1**：能够可靠导入和核验真实参赛包。核心可用 MVP 再加入 **US2 + US3 + US5 + US4**，形成“生成/拒绝—逐题复核—合规导出”的闭环；US6 将同一闭环暴露为规格要求的本地 Web UI。

### Incremental Delivery

1. 完成 Setup 与 Foundation，确保状态模型和共享用例边界稳定。
2. 完成 US1，使用真实题包验证输入结构与顺序。
3. 完成 US2 与 US3，按意图家族逐批增加独立证据和测试，不用统一模板批量制造答案。
4. 完成 US5 与 US4，先锁定输出结构，再收紧人工确认、证据和风险门禁。
5. 完成 US6，只复用应用服务，验证与 CLI 输出一致。
6. 执行 100 题逐题人工复核、全套自动化检查和可复现性验证；保持本地，不部署、不上传答卷。

## Format Validation

- 所有可执行任务均使用 `- [ ] TNNN` 格式。
- 仅可安全并行的任务带 `[P]`。
- 用户故事阶段的每项任务均带对应 `[US1]` 至 `[US6]` 标签。
- Setup、Foundational 与 Polish 任务不带用户故事标签。
- 每项任务均指向一个或多个明确文件路径。
