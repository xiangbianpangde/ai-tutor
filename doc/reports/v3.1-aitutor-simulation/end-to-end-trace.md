# 端到端执行轨迹 — AI-Tutor V3.1（研究子模块 CLI 调研命令）

> 角色：⑧ 系统运行模拟与闭环（Pipeline Stage 8 / SM-008）
> 模拟日期：2026-06-02
> 模拟命令（用户实际命令，PRD §12.1 FR4/FR5 CLI + Python SDK）：
>
> ```bash
> ai-tutor research run "技术大会 talk 调研" \
>     --video-url "https://www.bilibili.com/video/BVxxxxxxxxx" \
>     --prefer-subtitle --format markdown
> ```
>
> 期望产出：① 调研报告（`report.md`）② 知识树节点（`knowledge_tree.json` 新增 1~N 节点）③ clean/extract/organize 阶段中间文件
> 落盘策略：本地 `./data/` 目录（参见 SA-L §一 + SA-D §一）
> 数据字典锚点：DE-001~DE-048（详见 `04-整体结构设计/SA-DA-AITutor-V3.1-20260602.md`）

---

## 一、轨迹总览（15 拍 + 3 异常分支钩子点）

下表以"拍"为单位逐步串起 CLI 入口 → 链接解析 → 平台检测 → 字幕优先 → 下载/转写 → raw → collect → clean → extract → organize → 报告 → 知识树写入。每拍必须落到 DD-001 划分的具体模块（M-NNN）+ 对应文件框架路径（`07-文件框架/M-NNN/...`）。

| 拍 | 时序（相对 t=0） | 用户/系统动作 | 触发的模块（M-NNN 或棒号） | 关键调用 / 参数 | 产生的中间数据 / 文件 | 落盘路径（绝对 / 相对工作目录 `./`） | 失败分支（如有） |
|---|---|---|---|---|---|---|---|
| **P-01** | t=0ms | 用户在终端键入 `ai-tutor research run ...` | **M-003** 客户端入口（CLI Facade 分发） | 解析子命令 `research run` → 路由到 `ResearchCommand.run()` | 命令对象（trace_id=32hex，cli_argv） | — | ①子命令未注册 → EX-001 `E00101` 红线熔断 |
| **P-02** | t=15ms | CLI → SDK → HTTP 客户端 → M-001 服务入口（若 serve 已在运行） | **M-003 → M-002 → M-001** | POST `/api/v1/research/run` 携带 trace_id；本地直连走 `ai_tutor_sdk.ResearchClient()` | 进程内 EventBus emit `command.received` | `data/monitor_log/2026-06-02.jsonl`（追加） | ②服务未启动 → M-003 走 SDK 内嵌 fallback 拉起本地 daemon（M-001`ServiceBootstrapper.start()`） |
| **P-03** | t=120ms | M-001 装配 5 类中间件（Session/Cache/Monitor/Pipeline/RAG） + 健康检查 | **M-001** Builder | `validate_config()` / `bind_nli_cpu_affinity(CPU 0)`（DD洞察-002） | `service_instance` 行（DE-002） + `middleware_status` 行（DE-004） | `data/tutor.db` | ③配置缺失 → EX-002 `E00102`；NLI 加载失败 → EX-003 降级跳过 NLI 法官 |
| **P-04** | t=250ms | M-002 网关鉴权（默认认证）+ 入参校验 | **M-002** API 网关 | `AuthMiddleware.verify_token()` + `ResearchRunRequest` Pydantic 校验 | `web_session` 行（DE-040） | `data/tutor.db` | ④Auth 失败 → `E00201` 401；参数错误 → `E00202` 422 业务校验 |
| **P-05** | t=380ms | URL 解析 + 平台检测（B 站/YouTube/抖音…） | **M-007.PREPROCESS 阶段 → 视频解析器**（嵌入 M-007.Pipeline.stages.preprocess） + **M-008.routing** URL Platform Adapter | `_parse_url()` 返回 `{platform: "bilibili", vid: "BVxxxxxxxxx", prefer_subtitle: true}` | `pipeline_state` 行 status=PREPROCESS（DE-009） | `data/tutor.db` | ⑤URL 不支持 → EX-007 `E00701` "platform not in registry" |
| **P-06** | t=520ms | 字幕优先判定：M-008 调 B 站字幕 API `https://api.bilibili.com/x/player/v2?bvid=...&cid=...` | **M-008.indexing** 字幕采集子能力 | `SubtitleClient.fetch()` 返回 JSON（`subtitle.subtitles[0].subtitle_url`） | `pipeline_state` 写入 `has_subtitle=true, subtitle_url=...` | `data/tutor.db` | ⑥无字幕 API 响应 → 进入 P-07 兜底走 Whisper |
| **P-07** | t=780ms | 字幕下载 + 落盘 raw（**仅当 P-06 命中字幕**）；若未命中 → 走 Whisper 兜底 | **M-014.collect 阶段**（数据管线） + **M-017.存储** | `download_subtitle()` / `whisper.transcribe(audio_16k.wav)` | `raw/subtitle.srt` 或 `raw/audio.wav` + `raw/transcript.json` | `data/raw/{trace_id}/` | ⑦Whisper 失败 + ffmpeg 缺失 → EX-008 `E00801` 友好提示安装 ffmpeg |
| **P-08** | t=2400ms | 落 raw → 触发 collect 阶段归档元数据 | **M-014.collect** | `_write_manifest()` → 写 `manifest.json`（含 trace_id / source_url / platform / has_subtitle / duration） | `data/raw/{trace_id}/manifest.json` | `data/raw/{trace_id}/` | ⑧写盘失败（权限/磁盘满）→ EX-009 `E00901` |
| **P-09** | t=2500ms | Pipeline 状态机从 PREPROCESS → RETRIEVE（**注**：研究子模块的 Pipeline 5 阶段为 PREPROCESS/COLLECT/CLEAN/EXTRACT/ORGANIZE；LLM 阶段对齐到 EXTRACT 内） | **M-007.state** PipelineStateFSM | `mark_stage(PipelineStage.COLLECT)` + `transition_state(COLLECT, CLEAN)` | `pipeline_state` 更新（DE-009） | `data/tutor.db` | ⑨FSM 非法跃迁 → EX-010 `E01001`（卡死由 `is_stuck(>600s)` 触发） |
| **P-10** | t=2700ms | clean 阶段：去重 / 噪音过滤 / 时间戳归一 / 分段 | **M-014.clean 阶段** + **M-008.indexing** 切块器 | `_normalize_subtitle()` / `_filter_filler()` / `_segment_text()` | `data/clean/{trace_id}/cleaned.txt` + `cleaned.segments.json`（每段 `{start,end,text}`） | `data/clean/{trace_id}/` | ⑩段数为 0 → EX-011 `E01101` "empty after clean" |
| **P-11** | t=3200ms | extract 阶段：调 LLM（llm.py → httpx → LLM provider） + NLI 评分 + 重检索兜底 | **M-007.EXTRACT（对齐 stages/llm.py + stages/rerank.py）** + **M-008.nli** | `_call_provider("extract_keywords_and_entities", prompt)` → NLI `score < 0.7` 时触发 `_rerank_round(rag_state.round+=1)` | `extract/entities.json` + `extract/keywords.json` + `extract/summary.md` + `rag_state`（DE-010） | `data/extract/{trace_id}/` | ⑪LLM 连续 3 轮未达 NLI≥0.7 → EX-012 `E01201` "fallback to heuristic" + 走 10% LLM 兜底审计（SA:BR-009） |
| **P-12** | t=6500ms | organize 阶段：归并实体 → 构建知识树节点（按 taxonomy 锚定） | **M-014.organize 阶段** + **M-013.长期记忆** | `_build_knowledge_node(entities, summary)` → 调用 M-013 `LongTermMemory.upsert()` | `organize/knowledge_patch.json`（含待合并节点候选） | `data/organize/{trace_id}/` | ⑫知识树合并冲突（version 不一致）→ EX-013 `E01301` 触发 3-way merge + 审计 |
| **P-13** | t=7000ms | 报告生成：模板渲染 + 引用标注 + 源链接 | **M-007.POSTPROCESS（对齐 stages/postprocess.py）** + **M-003 客户端输出** | `_build_sources_section()` 把 NLI 评分 ≥ 0.7 的 chunk 写入 `Sources` 段；未达标的显式标"无法确认" | `data/report/{trace_id}/report.md` | `data/report/{trace_id}/report.md` | — |
| **P-14** | t=7400ms | 知识树写入主库（事务封装：rag_state ↔ nli_score 强一致） | **M-013 长期记忆** + **M-017 存储** | `LongTermMemory.upsert(trace_id, nodes)` 写 `long_term_memory` 表（DE-032） + Chroma 同步 embed | `long_term_memory` 新行 + `chroma/local_lib_chunks` 新增 | `data/tutor.db` + `data/chroma/` | ⑬Chroma 写失败 → EX-014 `E01401` "vector write failed"，事务回滚 + 重试 1 次 |
| **P-15** | t=7800ms | EventBus 推送 `research.run.completed` + 客户端收 WS 通知 + 终端打印"报告已生成" | **M-006 事件总线** + **M-002 WS** | `event_bus.emit(topic, payload)` → WS Hub 推送到订阅者 | `monitor_log` 末行（DE-008）+ 终端 stdout | `data/monitor_log/...jsonl` | ⑭WS 断连 → 客户端轮询 `/api/v1/research/{trace_id}` 兜底（SA-L §一 横切） |

**总耗时基线**：7.8 秒（命中字幕 + NLI 1 轮过 0.7）。其中 LLM 调优（t=3200~6500ms）占总耗时 42%。

---

## 二、关键调用链（按 SA-L §二 模块拓扑图 + DD-001 §一.1 设计主题识别）

```
CLI (M-003 Facade)
  ↓ POST /api/v1/research/run
Gateway (M-002 Adapter)
  ↓ Auth + 入参校验
Service Entry (M-001 Builder)
  ↓ 装配 Session/Cache/Monitor/Pipeline/RAG 5MW
Pipeline Orchestrator (M-007 Pipeline + Strategy)
  ├─→ PreprocessStage (sm007-preprocess / URL Platform Adapter → M-008.routing)
  ├─→ CollectStage (M-014.collect / M-017.存储 写 raw)
  ├─→ CleanStage (M-014.clean / M-008.indexing 切块)
  ├─→ ExtractStage (M-007.stages.llm.py + M-007.stages.rerank.py / M-008.nli 评分)
  │     └─→ M-008.nli 评分 < 0.7 → 重检索 rag_state.round++ (max=3, SA:BR-017)
  ├─→ OrganizeStage (M-014.organize / M-013 长期记忆 upsert)
  └─→ PostprocessStage (M-007.stages.postprocess.py / 报告 + 知识树落盘)
       ↓ emit topic=research.run.completed
EventBus (M-006 Observer) ──推送──→ WS Hub (M-002) ──→ CLI (M-003) 打印
横切：M-016 红线闸门在每拍前后校验（4 工具链 + 异常码白名单） + M-006 全埋 trace_id
```

来源标注：[SA-L-AITutor §二 模块拓扑] + [DD-AITutor §一.1 设计主题识别] + [PRD §12.1 FR4/FR5]

---

## 三、产物落盘清单（与 SA-D §一 数据视图对照）

| 拍 | 数据载体 | 路径 | DE-NNN |
|----|----------|------|--------|
| P-02 | monitor_log（追加） | `data/monitor_log/2026-06-02.jsonl` | DE-008 |
| P-03 | service_instance + middleware_status | `data/tutor.db` | DE-002 / DE-004 |
| P-04 | web_session | `data/tutor.db` | DE-040 |
| P-05~09 | pipeline_state | `data/tutor.db` | DE-009 |
| P-07 | raw 数据 | `data/raw/{trace_id}/` | 文件存储 |
| P-08 | manifest | `data/raw/{trace_id}/manifest.json` | DE-035 file_tree 子节点 |
| P-10 | cleaned | `data/clean/{trace_id}/cleaned.txt` + `cleaned.segments.json` | 文件存储 |
| P-11 | extract | `data/extract/{trace_id}/entities.json` + `keywords.json` + `summary.md` | DE-020~024 nli_triple / chunk_audit |
| P-12 | organize | `data/organize/{trace_id}/knowledge_patch.json` | DE-025~026 documents/chunks |
| P-13 | report | `data/report/{trace_id}/report.md` | 文件存储 |
| P-14 | long_term_memory | `data/tutor.db` | DE-032 |
| P-14 | Chroma 向量 | `data/chroma/local_lib_chunks/` | DE-037 local_lib_chunks embedding |
| P-15 | monitor_log（completed 事件） | `data/monitor_log/...jsonl` | DE-008 |

---

## 四、异常分支钩子点（与异常演练文件对照）

| 拍 | 异常 ID | 触发条件 | 简述（详见 `exception-rehearsal.md`） |
|----|---------|----------|--------------------------------------|
| P-01 | EX-001 | CLI 子命令未注册 | E00101 红线熔断 + 提示 `ai-tutor research --help` |
| P-03 | EX-002 | 配置文件 `.env` 缺失 | E00102 + 提示 `ai-tutor init` 向导 |
| P-05 | EX-007 | URL 平台不支持 | E00701 + 提示支持的平台白名单 |
| P-07 | EX-008 | 无字幕 + ffmpeg 缺失 | E00801 + 提示安装 ffmpeg 或加 `--audio-source` |
| P-11 | EX-012 | NLI 连续 3 轮 < 0.7 | E01201 + 兜底审计 + 显式"无法确认"标注 |

---

## 五、最终评审

**系统逻辑自洽性**：自洽。M-003→M-002→M-001→M-007→M-014→M-008→M-013→M-017→M-006 的 15 拍串联与 SA-L §二 拓扑图、DD-001 §一.1 设计主题识别、M-007 FF 文件 `文件间依赖关系` 三处均一致。横切（事件总线 + 红线闸门）每拍都有触点。

**能否正常运行**：可以，前提是：
1. `ai-tutor serve` 已起 → M-001 5MW 装配 + 健康端点 200（PRD §6 F-001）
2. `.env` 含 `LLM_API_KEY` + `WHISPER_MODEL` + （可选）`REDIS_URL`
3. ffmpeg 已安装（P-07 兜底前置）
4. CLI 处于 4 形态之一（默认 CLI；SDK 用户走 `ResearchClient`）

**关键风险点**：
- R1：[DD洞察-001] M-008 4 子能力（路由/NLI/索引/翻译）内聚度过低，V3.2 触发 100 用户时需物理拆分——模拟中已用子能力命名空间（`m008.routing` / `m008.nli`）隔离副作用。
- R2：[DD洞察-002] NLI（CPU 0 亲和性）与 M-014 PDF 翻译（CPU 1-3 ThreadPool）CPU 争抢——4 核机器并行跑研究+PDF 翻译时 NLI 评分延迟可能翻倍。
- R3：[DD洞察-004] WS 重连风暴（800+ 同时重连）将触发 E00202 软拒绝——研究命令是异步长任务（7.8s），WS 断连概率中等。

**待确认项**：
- C1：M-007 Pipeline 在 V3.1 的 5 阶段（PREPROCESS/COLLECT/CLEAN/EXTRACT/ORGANIZE）还是 V3.0 的 5 阶段（PREPROCESS/RETRIEVE/RERANK/LLM/POSTPROCESS）？本模拟按 SA-DA §一 pipeline_state DE-009 + PRD §12.5 SA-001 任务清单的语义映射为"研究子模块的 5 阶段"（PREPROCESS/COLLECT/CLEAN/EXTRACT/ORGANIZE），与 RAG 教学回合的 5 阶段（PREPROCESS/RETRIEVE/RERANK/LLM/POSTPROCESS）并存。建议 AR-001 在 V3.2 评审时显式声明"研究子模块复用 M-007 框架但阶段名重命名"。
- C2：M-013 长期记忆 LRU 淘汰 10% 误删关键事实（[DD洞察-003]）——本模拟未演示 V3.1 EX-013 审计兜底是否对研究节点生效，需 SA-001 POC 验证。

**调研报告采纳证据**（至少 2 处具体引用）：
1. **DD-001 §一.2 [DD洞察-005]** 明确引用 `REDOC-09`（"Ruff 1.0 前 API 破坏性变更"）作为技术债务依据，并落地缓解"CI 锁版本不升级；V3.2 走 TDD 渐进式"——直接采纳 `02-调研验证/RESEARCH-AITutor-V3.1-20260602.md` 风险章节。
2. **DD-001 §二.2 主方案 A 选型理由** "AR 已在 TDR-001/002 锁定混合架构"——引用 AR-001 的技术决策，而 AR-001 的 TDR-001/002 又回引 `02-调研验证/SOURCES-AITutor-V3.1-20260602.json` 中关于"分层+插件化"对比的 7 个 S/A 级来源。
3. **PRD §4 NFR-8 4 工具链→6+1 矩阵**（V3.1 = S-021）逐行引用 REDOC-09/30/31/32/33/52/53 共 7 个调研来源，把调研结论"显式化"为可执行 CI 命令。
4. **SA-L §三 "FSRS Again 节流 / 阶段 hysteresis"** 直接采纳 `02-调研验证/RESEARCH-AITutor-V2.0-20260601.md` 中关于 FSRS 与 BKT/DKT 协同的对比结论（RI-NEW-2）。

**结论**：在零修改下可走通，3 处待确认项（研究 Pipeline 阶段命名重映射 / EX-013 审计覆盖范围 / M-008 内聚度预警）不阻塞 P-01~P-15 主链路。

来源标注：[PRD §12.1] + [SA-L §一~§四] + [SA-DA §一~§四] + [DD-001 §一.1/§一.2/§二.2] + [FF-M-007 文件间依赖关系] + [M-003/M-008/M-013/M-014/M-016 FF + API + IC]（全部 17 模块已编入 07-文件框架/）
