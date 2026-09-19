# 2026-06-13 · 阶段 B 收尾（B2 pre-commit / B3 版本锁定 / B4 快照）

> 对应 STATUS「下一步」第 1 项 = 阶段 B 收尾。B1 ✓（main 干净）/ B5 ✓（= 走向决议 §二）此前已完成。
> 本日落地 B2 + B3 + B4，797 测试保持全绿。下一步 = C1 第一波（目录名决断先行）。

---

## 一、B2 · pre-commit 质量门禁（核心交付）

### 关键发现：ruff 787 错是假象，真实只 246

引入门禁第一步跑 `ruff check .` 报 **787 错**，险些当成"代码烂"。排查发现 **541 错来自
`doc/plan/v3.1-aitutor-design/06-framework/.../src/` 下 291 份 v3.1 设计骨架 `.py` 桩文件**
——它们是 plan-writing 工作流的计划产物，不是生产代码。`exclude = ["doc", ...]` 后真实基线
**246 错 / 184 可自动修**。教训：lint 配置第一件事是把"设计产物 .py"排除，否则噪声淹没信号。

### 改动

- **`pyproject.toml [tool.ruff]`**：
  - `exclude = ["doc", "ai-tutor-system-design", "migrations", ".venv"]`
  - `select` 在 E/F/I/N/W/UP 上加红线规则 **T20（禁 print 入库）/ T100（禁调试断点）/ B（bugbear）**
  - `ignore`：E741（少量单字母循环变量）/ N806（项目惯用 `SUBJECT_ID` 等 UPPER_SNAKE 局部常量 + 数学单字母）/ N817（领域缩写导入）
  - `per-file-ignores`：scripts/data/examples/tests/BDD 放行 T201（合法 stdout）/E402（sys.path 后置）/F841（容忍读值中间变量）
- **`pyproject.toml [tool.importlinter]`**（架构契约，把 01-architecture 红线变成可拦截规则）：
  - 契约1 `forbidden`：`shared` 不得 import `servers`（领域层不依赖框架）→ **KEPT**
  - 契约2 `independence`：knowledge/tutoring/digest/sync 四引擎互不 import → **KEPT**
    - `ignore_imports = ["servers.*.tests.** -> servers.**"]`：集成测试合法跨 server（端到端跑教学全链需引别的 server），契约只管生产代码
  - 实测唯一跨 server 边即 `servers/dashboard -> tutoring_mcp`（dashboard 不在独立集内，v2 由前端替代，不违约）
- **`.pre-commit-config.yaml`**（新建）：**全部 local/system hook，不联网 clone**（规避死代理装钩失败）
  - ruff lint（--fix）/ import-linter / gitleaks（`git --pre-commit --staged --redact`）/ redocly OpenAPI（`files: openapi.(yaml|json)` → 当前无 spec **休眠**，C1 后端落地自动激活）
  - **ruff-format 默认注释关闭**：全仓 188/203 文件未格式化，开启会产生大 diff——见 §四决策点

### 清掉 246 错的过程（红→绿，非删规则刷绿）

1. `ruff check --fix` 自动修 **205** 条（import 排序/未用 import/f-string/注解现代化）。
2. 手工修剩余非自动项：
   - `digest_mcp/orchestrator.py`：8 个 generator import 原在 dataclass **之后**（E402）；核对各 generator 子模块**不** import orchestrator（无环）→ 安全上移到顶部 import 块。
   - 3 处测试 B007/E702：`for i→for _`（未用循环变量）+ 拆分 `s.add(...); s.add(...)` 分号双语句。
   - `test_review_scheduler.py` F821 `-> "BKTParams"`：函数体内局部 import 的前置引用，假阳性，加 `# noqa: F821 + 理由`。
3. 剩 5 个 UP038（isinstance `(X,Y)→X|Y`，py312 安全）：仅对 `concept_enricher.py` / `relation_extractor.py` 两个生产文件定向 `--unsafe-fixes`。
4. 11 个 F841（10 测试 + 1 demo）：**逐条核过来源**——多数是 `result = push_to_obsidian(...)` 等
   带副作用调用，盲删整句会丢副作用破坏测试 → 选 per-file-ignore（生产代码仍强制 F841）。
   ⚠️ **遗留待审**：其中 `test_update_kg_versioned.py:100 cid=` / `test_obsidian_push.py:62 result=` /
   `test_learning_plan_server.py:86 phase1_ids=` 等读值后未用，**可能是漏写的断言**，C 波测试加固时回看。

### 验证（全绿）

```
ruff check .            → All checks passed!
lint-imports            → Contracts: 2 kept, 0 broken.
pre-commit run --all-files → ruff/import-linter/gitleaks Passed；redocly Skipped(no files)
pytest -q               → 797 passed in 88s   （= 基线，0 回退）
pre-commit install      → 已挂 .git/hooks/pre-commit
```

## 二、B3 · 版本锁定 → `doc/reports/依赖版本锁定.md`

- `uv lock` 把本日新增 dev 依赖（import-linter 2.11 / pre-commit 4.6.0 / grimp 3.14）折入 uv.lock，
  **仅增量、既有 pin 0 漂移**。
- 记录三层：① 当前已锁（fastmcp/pydantic/sqlalchemy/openai/pymupdf/ruff…）；
  ② C 波新增（fastapi 0.115 @C1 / sqlite-vec 0.1.x @C2C3 锁死 / langgraph 1.0 @C3）现在不引入；
  ③ 外部工具 subprocess 隔离不进依赖：**mineru 3.2.0**（AGPL，M-015 打包不捆绑红线）/ md_translator 树内 MIT。
- 校准走向决议 §五-2：**B3 锁定对象由 pdf2zh 改为 mineru**（上游 AGPL pdf2zh 1.9.6 已移出依赖）。
- 暗坑记录：venv 现存 fastapi 0.115.5 系历史遗留，**既不在 pyproject 也不在 uv.lock**，C1 正式 `uv add`。

## 三、B4 · 历史快照 → `doc/plan/v3.1-aitutor-design/历史快照/README.md` + git tag

- 遵循 DEVELOPMENT-NORM §一「不轻易加新文件」：**不物理复制** `ai-tutor-system-design/`（59 文件）——
  git 历史本身即完整快照，物理副本只会陈旧 + 双倍占用。
- 改用 **git tag `v3.0-design-snapshot`** 冻结 C 波前的设计状态 + 一份 README 让快照从 v3.1 包内可发现。
- 用法：`git diff v3.0-design-snapshot..HEAD -- ai-tutor-system-design/ doc/plan/` 看 C 波改了哪些设计。
- ⚠️ 这是对"备份为目录"的**判断式落地**；若需 59 份物理副本，一句话即补。

## 四、留给下一任的决策点

1. **ruff-format 全仓格式化**（B2 半成品）：188/203 文件从未 `ruff format`。建议 **C1 首日**随
   `backend/` 新代码一起开：老代码单独一个"一次性格式化"提交 + 写进 `.git-blame-ignore-revs`，
   再把 `.pre-commit-config.yaml` 里注释的 `ruff-format` hook 取消注释。**不要**和逻辑改动混在一个 diff。
2. **C1 目录名决断**：backend/ vs src/aitutor/（走向决议 §四-5 建议 backend/，与 PRD 验收命令一致）。
3. **gitleaks/redocly 首跑**：gitleaks 已装（8.24.3）；redocly 经 npx 首跑联网取 `@redocly/cli`，
   死代理时设 NO_PROXY。
4. F841 测试遗留（§一）C 波回看是否漏断言。
