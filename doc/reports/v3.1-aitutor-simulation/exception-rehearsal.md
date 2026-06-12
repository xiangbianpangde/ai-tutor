# 异常分支演练 — AI-Tutor V3.1（3 个代表性场景）

> 角色：⑧ 系统运行模拟与闭环
> 异常场景清单锚点：`04-整体结构设计/SA-EX-AITutor-V3.1-20260602.md`（EX-001~EX-024，共 24 条）
> 异常处理详细策略：`06-详细设计/EX-AITutor-V3.1-20260602.md`
> NFR3 错误处理原则：明确报错不静默（NFR-3 / PRD §4 NFR-3）
> 异常码体系：E00x0y 业务 / E00101~E00299 客户端 / E00701~E00799 平台 / E00801~E00899 资源 / E01001~E01099 状态机 / E01201~E01499 推理与存储

---

## 场景 A：EX-008 视频无字幕 + Whisper 失败 + ffmpeg 缺失（最常见 + 最长链）

**对应 P-07 拍**（详见 `end-to-end-trace.md`）

### 触发条件

```
P-06 字幕 API 返回 {"subtitle": {"subtitles": []}}
P-07 fallback 路径：M-014.collect → 调用 ffmpeg 抽音轨
    ├─ 子条件 1：ffmpeg 未安装 → shutil.which("ffmpeg") = None
    │   → raise FFMpegNotFoundError
    └─ 子条件 2：ffmpeg 存在但 audio 抽离成功
        → 调 whisper.transcribe()，但模型未下载 / 磁盘满 → raise WhisperRuntimeError
```

### 哪个模块捕获

`M-014/collect.py` 的 `run()` 方法（参见 `07-文件框架/M-014/FF-M-014`）。捕获点在 try/except（EX-008 策略）。

### 报错信息（终端 + 日志 + 事件总线三路投递）

```
[ERROR] trace_id=7f3a...b29c code=E00801 msg="ffmpeg not found in PATH"
  hint: "请先安装 ffmpeg（macOS: brew install ffmpeg / Ubuntu: sudo apt install ffmpeg / Windows: choco install ffmpeg）"
        "或显式指定已抽离的音频：ai-tutor research run ... --audio-source ./local.wav"
  retryable: false
  stage: COLLECT
  raw_dir: data/raw/{trace_id}/  (已创建空目录)
  log: data/monitor_log/2026-06-02.jsonl
  event: research.run.failed
```

### 用户可执行的下一步

1. 安装 ffmpeg（或用 `--audio-source` 跳过抽离）
2. 重跑命令（trace_id 重生或显式 `--resume {trace_id}`）
3. 高级：编辑 `~/.ai-tutor/config.toml` 显式设置 `[research] ffmpeg_path = "/custom/path/ffmpeg"`

### 流程是否优雅退出

**是**。NFR3 满足：
- 错误码唯一（E00801）
- 三路投递完整（终端 stderr / JSONL 日志 / EventBus）
- trace_id 全程贯穿，可关联监控与重跑
- 不静默吞错；不破坏已有 raw 目录（已落空目录 + manifest.json 含 `status=FAILED`）
- WS 推送 `research.run.failed` 事件（M-006），客户端可订阅

### 涉及代码位置（`07-文件框架/M-014/src/aitutor/pipeline/collect.py`）

- 函数 `_extract_audio()`（缺 ffmpeg → raise FFMpegNotFoundError）
- 函数 `_transcribe_audio()`（whisper 失败 → raise WhisperRuntimeError）
- 函数 `_handle_collect_error()` → EX-008 策略 → emit E00801

来源标注：[DD-001:EX-008] + [PRD:§4 NFR-3 错误处理] + [SA:EX-007/008 资源失败] + [M-014 FF + API 文档]

---

## 场景 B：EX-007 平台不支持（最快识别 + 用户可控）

**对应 P-05 拍**

### 触发条件

```
用户输入：ai-tutor research run "..." --video-url "https://vimeo.com/123456"
P-05 M-007 PREPROCESS → M-008.routing URL Platform Adapter
    → _detect_platform("vimeo.com/123456") 返回 "vimeo"
    → 查 platform_registry 白名单：["bilibili", "youtube", "douyin", "xiaohongshu"]
    → "vimeo" 不在白名单 → raise PlatformNotSupportedError
```

### 哪个模块捕获

`M-008/routing.py` 的 `URLPlatformAdapter.detect()`（参见 `07-文件框架/M-008/FF-M-008`）。捕获后转交 M-007 orchestrator 统一处理。

### 报错信息

```
[ERROR] trace_id=... code=E00701 msg="platform 'vimeo' not in registry"
  supported: ["bilibili", "youtube", "douyin", "xiaohongshu"]
  hint: "若需新增平台，请提交 platform adapter 插件（参见 doc/runbooks/platform-adapter.md）"
        "或本地转写后用 --audio-source 指定"
  retryable: false
  stage: PREPROCESS
```

### 用户可执行的下一步

1. 切换到支持的平台（白名单列表已给出）
2. 用 `--audio-source` 跳过平台检测
3. 开发者：编写 `m008/routing/adapters/vimeo.py` 并在 `platform_registry` 注册

### 流程是否优雅退出

**是**。P-05 在状态机 PREPROCESS 阶段最早失败，不污染后续 P-06~P-15。`pipeline_state` 写入 `status=FAILED, failed_stage=PREPROCESS, error_code=E00701`，供后续 `--resume` 时跳过。

### 涉及代码位置（`07-文件框架/M-008/src/aitutor/routing/url_platform_adapter.py`）

- 类 `URLPlatformAdapter` 方法 `detect()`
- 异常类 `PlatformNotSupportedError(ResearchError)`
- EX-007 策略：`raise + log + emit + return None` 四联动

来源标注：[DD-001:EX-007] + [SA:BP-005 平台白名单] + [BR-001 平台扩展] + [M-008 FF]

---

## 场景 C：EX-012 NLI 连续 3 轮 < 0.7（最复杂 + 横跨多模块）

**对应 P-11 拍**

### 触发条件

```
P-11 EXTRACT 阶段：M-007.stages.llm.py 调 LLM 生成实体/关键词/摘要
  → M-007.stages.rerank.py 用 M-008.nli 给 chunk 评分
  → 第 1 轮：round=1，nli_score=0.52 < 0.7 → 触发重检索 rag_state.round=2
  → 第 2 轮：nli_score=0.61 < 0.7 → 触发重检索 rag_state.round=3
  → 第 3 轮：nli_score=0.43 < 0.7 → 触发 BR-017 兜底（10% LLM 兜底 + audit）
  → raise NLIFallbackExhausted
```

### 哪个模块捕获

- 主捕获点：`M-007/fallback.py` 的 `FallbackStrategy.execute_fallback()`（参见 `07-文件框架/M-007/FF-M-007`）
- 联动点：`M-008.nli`（评分）+ `M-006 事件总线`（emit `research.run.llm_fallback`）

### 报错信息

```
[WARN] trace_id=... code=E01201 msg="NLI score < 0.7 for 3 consecutive rounds, fallback engaged"
  rag_state: {round: 3, last_score: 0.43, threshold: 0.7}
  fallback_action: "heuristic_extraction + explicit_uncertainty_label"
  audit_log: data/audit/llm_fallback/{trace_id}.jsonl
  hint: "提取的实体已用启发式方法兜底；'无法确认'的事实已显式标注于 report.md"
  retryable: true (--force-rerun)
  stage: EXTRACT
```

### 用户可执行的下一步

1. 查看 `report.md` 中标注 `⚠️ 无法确认` 的事实
2. 检查 NLI 模型是否需要更新（`ai-tutor doctor` 查 NLI 状态）
3. 强制重跑：`--force-rerun`（清 rag_state，从 round=0 重起）
4. 提供更明确的 query（`--query-hint "..."`）以提升 chunk 相关性

### 流程是否优雅退出

**是**，且**不阻断**：
- E01201 是 WARN 级（不是 ERROR），流程继续到 P-12/P-13/P-14/P-15
- 兜底审计写入 `data/audit/llm_fallback/{trace_id}.jsonl`（DE-019 rest_log 子集）
- 报告 `report.md` 中所有 NLI < 0.7 的事实显式标"无法确认"（SA:BR-018 "显式无法确认"）
- 知识树节点写入时附 `confidence=<avg_nli_score>` 字段，便于后续重检索
- 90% FSM + 10% LLM 兜底（SA:BR-009）原则被严格遵守

### 涉及代码位置

- `M-007/src/aitutor/pipeline/fallback.py::FallbackStrategy.execute_fallback()`（主捕获）
- `M-007/src/aitutor/pipeline/state.py::PipelineState`（FSM 跃迁 EXTRACT → LLM_FALLBACK）
- `M-007/src/aitutor/pipeline/stages/rerank.py::_nli_score()`（评分源）
- `M-008/src/aitutor/nli/scoring.py::score_triple()`（NLI 评分）
- `M-006/src/aitutor/monitor/logger.py` + `M-006/src/aitutor/monitor/event_bus.py`（audit + emit）

来源标注：[DD-001:EX-012] + [SA:BR-009 90% FSM] + [SA:BR-016/017/018 NLI 评分] + [SA:CE-004 兜底审计] + [M-007 FF + M-008 FF + M-006 FF]

---

## 三场景对比总结

| 维度 | 场景 A（ffmpeg 缺失） | 场景 B（平台不支持） | 场景 C（NLI 兜底） |
|------|---------------------|---------------------|-------------------|
| 异常 ID | EX-008 | EX-007 | EX-012 |
| 触发拍 | P-07 | P-05 | P-11 |
| 捕获模块 | M-014 | M-008 | M-007 fallback + M-008 + M-006 |
| 错误级别 | ERROR | ERROR | WARN（兜底不阻断） |
| 错误码 | E00801 | E00701 | E01201 |
| 优雅退出 | ✅ 落空目录 + manifest.FAILED | ✅ 状态机最早失败 | ✅ 兜底审计 + 显式标注 |
| 重试建议 | 装 ffmpeg 重跑 | 换平台 / 加 adapter | `--force-rerun` 或优化 query |
| NFR3 满足 | ✅ 明确报错 + 修复手册 + 三路投递 | ✅ 明确白名单 + 扩展路径 | ✅ 审计 + 显式标注 + 90% FSM 兜底 |

**结论**：3 个场景均满足 NFR3 "明确报错不静默"，且都提供了用户可执行的下一步（修复/扩展/重跑）。异常链路覆盖 M-007/M-008/M-014/M-006 四模块的异常处理策略，验证 EX-001~024 的 24 条异常策略中至少 3 条（EX-007/008/012）的端到端可执行性。

来源标注：[PRD §4 NFR-3] + [SA-EX-AITutor §异常清单] + [DD-001 EX-AITutor §策略表] + [M-007/008/014 FF + API + IC]
