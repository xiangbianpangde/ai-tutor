# 2026-06-13 · C2 起步（波前文档校准 + M-005 CacheLayer）

> 对应 STATUS 阶段 C · C2（v2 #3 中间件层）。本轮交付 = C2 波前文档去 sys.path 化（走向决议 §五-6）
> + M-005 SQLite 缓存层（首个 C2 中间件模块）。817 测试全绿。M-004/006/007/014 留后续轮。

---

## 一、C2 波前：pdf2zh 集成文档去 sys.path 化（走向决议 §五-6）

`doc/plan/design/设计文档-pdf2zh集成.md` 原写"直接调用 pdf2zh 完整管线 + `sys.path.insert` 注入"，
与 v1 现实不符（走向决议 §二-4：上游 AGPL 的 pdf2zh 包已移出依赖）。按现实重写：

- **方式 B（原 sys.path 注入）删除**：翻译核心 = 树内 MIT `servers/knowledge_mcp/md_translator.py`，
  普通 import，**不再 `sys.path.insert` 上游 pdf2zh、不依赖其 .venv**。
- **§1 premise 改写**：PDF 解析 = **mineru 子进程**（进程隔离 + 规避 AGPL）；翻译 = 树内 MIT 模块。
- 头部加 AGPL/MIT 现实校准声明 + M-015 不捆绑 mineru 红线。
- 验证：`grep sys.path doc/plan/design/` 仅剩"禁用 sys.path"的散文否定句，**可执行的 `sys.path.insert` 已清零**。

（注：`设计文档-数据管线.md` 经查本无 sys.path，无需改。）

## 二、M-005 CacheLayer（SQLite L1 LLM 缓存）

`backend/middleware/cache_layer.py`。**与 v1 `shared.llm_cache.CachedLLMProvider` 的关键区别**：
v1 是进程内 LRU（重启即失），本层落 **SQLite，跨进程/重启存活**——这是"v2 第一波过堂"挑战
（重复问题命中 + 进程重启可续）的缓存侧基础。

- 缓存键 = `sha256(provider+model+messages_json+temperature)`；TTL 默认 24h，按调用可覆盖。
- `get/set/stats/clear`；过期项 get 时顺手删除；stats = hits/misses/hit_rate/saved_tokens/entries。
- 落库表 `cache_entries`（CacheLayer 自建，CREATE IF NOT EXISTS，**不动 shared ORM 13 表**，同库第 14 表）。
- 接线：`backend/app.py` lifespan 建 `app.state.cache`；`backend/routers/meta.py` 暴露
  `GET /api/meta/cache/stats`（统一信封）。
- 架构契约新增：`backend.middleware ⊥ routers/app/main`（import-linter 第 4 契约 KEPT）。

### 测试（backend/ 20 passed，其中 cache 7 条）

| 用例 | 覆盖 |
|------|------|
| miss→hit + saved_tokens | spec 03 场景1（第二次命中不调 LLM）|
| key 区分 temperature/messages | 键稳定性，防碰撞 |
| TTL 过期（注入 now）| spec 03 场景2 |
| hit_rate 统计（7 命中/3 未命中→0.7）| spec 03 场景3 |
| **跨重启存活** | 新实例（计数归零）仍命中同库旧条目——挑战缓存侧 |
| clear | — |
| `GET /api/meta/cache/stats` 信封 | 端点接线 |

## 三、验证

```
backend/                20 passed（13 骨架 + 6 cache + 1 endpoint）
全量                    817 passed（810 + 7，0 回退）
ruff check .            All passed
lint-imports            4 kept 0 broken（+backend.middleware 契约）
真机                    GET /api/meta/cache/stats → {"ok":true,"data":{...}}；cache_entries 表实建（未碰演示数据）
```

## 四、留待（C2 续）
- M-004 SessionManager（list/switch/auto_summarize/cleanup_expired/token_usage + session_summaries 表）——可包 v1 `servers/tutoring_mcp/session.py` SessionStore。
- M-006 事件总线 / M-007 Pipeline 调度（含 build_kg 异步任务+进度可查——"v2 第一波过堂"硬骨头）/ M-014 数据管线。
- M-017 FileManager（`{user}/{subject}/{type}/` 人类可读目录，替 UUID 目录）。
- CacheLayer 接 LLM 调用路径（待引擎 endpoint 在 C2-C4 落地后，把 CachedLLMProvider 换成 SQLite 版/叠加）。
