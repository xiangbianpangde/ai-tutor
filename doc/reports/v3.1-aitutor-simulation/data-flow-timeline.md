# 数据流时间线 — AI-Tutor V3.1（主角：转写文本 + 知识树节点）

> 角色：⑧ 系统运行模拟与闭环
> 追踪对象 1：**一段转写文本**（"AI agent 的核心是 prompt + tool + memory 三件套"）
> 追踪对象 2：**一条知识树节点**（"AI Agent 三件套" 概念节点）
> 数据字典锚点：`04-整体结构设计/SA-DA-AITutor-V3.1-20260602.md`（DE-001~DE-048 + DS-001~009）
> 落盘策略：本地 `./data/` 目录（参见 SA-L §一 + SA-D §一）

---

## 主角 A：一段转写文本的 6 段旅程

### 旅程 1：视频源（t=-30s，外部）

| 项 | 值 |
|----|---|
| 数据形态 | 视频流（H.264 + AAC，~25 fps / 44.1 kHz） |
| 来源 | `https://www.bilibili.com/video/BVxxxxxxxxx` |
| 体积基线 | 25 分钟 × ~5 MB/分钟 = ~125 MB（DD-001 默认 NFR-3 网络占用） |
| 模块归属 | 外部资源 |
| 触发模块 | M-007 PREPROCESS + M-008.routing URLPlatformAdapter |

---

### 旅程 2：raw 落盘（t=780ms，P-07 拍）

| 项 | 值 |
|----|---|
| 数据形态 | `raw/audio.wav`（16kHz 单声道 PCM） + `raw/subtitle.srt`（若命中字幕） |
| 文件结构 | `data/raw/{trace_id}/audio.wav` (size~30MB) + `subtitle.srt` (size~50KB) |
| 关键字段 | `{trace_id, source_url, platform, duration, has_subtitle, audio_codec}` |
| 模块归属 | **M-014.collect 阶段** + **M-017.存储**（文件存储层） |
| 数据结构 | DS-005 文件元数据 + DE-035 file_tree 子节点 |
| 关联 SA-D 表 | file_tree（弱校验，warn only） |

**JSON 示例（manifest.json）**：
```json
{
  "trace_id": "7f3a9c2e8b1d4f6a8c0e2b4d6f8a1c3e",
  "source_url": "https://www.bilibili.com/video/BVxxxxxxxxx",
  "platform": "bilibili",
  "duration_sec": 1542,
  "has_subtitle": true,
  "subtitle_url": "https://aisubtitle.bilibili.com/.../subtitle.srt",
  "audio_codec": "aac",
  "audio_local_path": "data/raw/7f3a.../audio.wav",
  "subtitle_local_path": "data/raw/7f3a.../subtitle.srt",
  "status": "COLLECTED",
  "ts": "2026-06-02T10:23:45.123Z"
}
```

---

### 旅程 3：clean 阶段（t=2700ms，P-10 拍）

| 项 | 值 |
|----|---|
| 数据形态 | `clean/cleaned.txt`（纯文本） + `clean/cleaned.segments.json`（分段数组） |
| 文件结构 | `data/clean/{trace_id}/cleaned.txt` + `cleaned.segments.json` |
| 处理动作 | ① 去重 ② 噪音过滤（"嗯"/"啊"/"那个"） ③ 时间戳归一 ④ 分段（每段 ≤ 500 字） |
| 模块归属 | **M-014.clean 阶段** + **M-008.indexing** 切块器 |
| 数据结构 | DS-001 段落结构 + DS-002 段索引（每段 `{segment_id, start, end, text, word_count}`） |
| 关联 SA-D 表 | documents/chunks（DE-025/026 写后异步 embed 链路起点） |

**JSON 示例（cleaned.segments.json 摘录）**：
```json
[
  {
    "segment_id": 42,
    "start": 412.5,
    "end": 428.3,
    "text": "AI agent 的核心是 prompt 加 tool 加 memory 三件套。prompt 决定模型行为，tool 提供外部能力，memory 维持上下文连续性。",
    "word_count": 38,
    "nli_score": null,
    "source_segment": "raw/subtitle.srt#L42"
  }
]
```

**主角登场**：第 42 段就是我们的"转写文本"主角，文字为"AI agent 的核心是 prompt + tool + memory 三件套"。

---

### 旅程 4：extract 阶段（t=3200ms，P-11 拍）

| 项 | 值 |
|----|---|
| 数据形态 | `extract/entities.json` + `extract/keywords.json` + `extract/summary.md` |
| 文件结构 | `data/extract/{trace_id}/entities.json` 等 |
| 处理动作 | ① 调 LLM 抽实体 ② 调 LLM 抽关键词 ③ 调 LLM 写摘要 ④ NLI 评分每条事实 |
| 模块归属 | **M-007.stages.llm.py** + **M-007.stages.rerank.py**（NLI）+ **M-008.nli** 评分 |
| 数据结构 | DS-003 实体记录 + DS-004 关键词列表 |
| 关联 SA-D 表 | nli_triple（DE-020）/ nli_score（DE-021）/ chunk_audit（DE-023/024） |

**JSON 示例（entities.json 摘录）**：
```json
{
  "trace_id": "7f3a9c2e8b1d4f6a8c0e2b4d6f8a1c3e",
  "entities": [
    {
      "entity_id": "E-001",
      "name": "AI Agent",
      "type": "concept",
      "aliases": ["agent", "AI 代理"],
      "definition": "具备 prompt + tool + memory 三件套的智能体",
      "source_segment_ids": [42, 43, 44],
      "nli_score": 0.87,
      "nli_round": 1,
      "extracted_at": "2026-06-02T10:23:49.456Z"
    }
  ]
}
```

**主角变形**：第 42 段被 LLM 识别为 E-001 实体"AI Agent"的源段，NLI 评分 0.87（一次过 0.7 阈值，未触发重检索）。

---

### 旅程 5：organize 阶段（t=7000ms，P-12 拍）

| 项 | 值 |
|----|---|
| 数据形态 | `organize/knowledge_patch.json`（候选节点 patch） |
| 文件结构 | `data/organize/{trace_id}/knowledge_patch.json` |
| 处理动作 | ① 实体归并（去重、合并 alias） ② 锚定 taxonomy ③ 构造知识树 patch |
| 模块归属 | **M-014.organize 阶段** + **M-013 长期记忆**（候选 patch 准备） |
| 数据结构 | DS-006 知识树节点 + DS-007 patch 操作（add/update/merge） |
| 关联 SA-D 表 | long_term_memory（DE-032）+ documents（DE-025）patch 准备 |

**JSON 示例（knowledge_patch.json 摘录）**：
```json
{
  "patch_id": "P-7f3a...-001",
  "ops": [
    {
      "op": "add",
      "node": {
        "node_id": "N-2026-06-02-AI-Agent-3c-suit",
        "label": "AI Agent 三件套",
        "node_type": "concept",
        "parents": ["AI-Agent"],
        "children": ["Prompt Engineering", "Tool Use", "Memory Management"],
        "evidence_segment_ids": [42, 43, 44],
        "confidence": 0.87,
        "source_url": "https://www.bilibili.com/video/BVxxxxxxxxx",
        "extracted_at": "2026-06-02T10:23:51.789Z"
      }
    }
  ]
}
```

**主角再变形**：E-001 实体 → N-2026-06-02-AI-Agent-3c-suit 知识树节点，confidence=0.87（与 NLI 评分同源）。

---

### 旅程 6：知识树写入主库（t=7400ms，P-14 拍）

| 项 | 值 |
|----|---|
| 数据形态 | SQLite 行 + Chroma 向量 |
| 文件结构 | `data/tutor.db`（long_term_memory 表）+ `data/chroma/local_lib_chunks/` |
| 处理动作 | ① 事务封装（rag_state ↔ nli_score 强一致） ② 同步写 SQLite ③ 异步 embed + 写 Chroma |
| 模块归属 | **M-013 长期记忆** + **M-017 存储** |
| 数据结构 | DS-008 long_term_memory schema + DS-009 chroma chunk schema |
| 关联 SA-D 表 | long_term_memory（DE-032）+ Chroma local_lib_chunks（DE-037 embedding） |
| 一致性策略 | 强一致（事务封装，BR-008 弱一致 → 强一致升级） |

**SQLite 行示例**：
```sql
INSERT INTO long_term_memory (
  node_id, label, node_type, parents, children,
  evidence_segment_ids, confidence, source_url, source_trace_id,
  created_at, updated_at, version
) VALUES (
  'N-2026-06-02-AI-Agent-3c-suit', 'AI Agent 三件套', 'concept',
  '["AI-Agent"]', '["Prompt Engineering","Tool Use","Memory Management"]',
  '[42,43,44]', 0.87,
  'https://www.bilibili.com/video/BVxxxxxxxxx',
  '7f3a9c2e8b1d4f6a8c0e2b4d6f8a1c3e',
  '2026-06-02T10:23:51.890Z', '2026-06-02T10:23:51.890Z', 1
);
```

**Chroma 元数据示例**：
```python
collection.add(
    ids=["N-2026-06-02-AI-Agent-3c-suit"],
    embeddings=[[0.12, 0.34, ..., 0.56]],  # 384 维 sentence-transformers
    metadatas=[{
        "node_id": "N-2026-06-02-AI-Agent-3c-suit",
        "label": "AI Agent 三件套",
        "node_type": "concept",
        "confidence": 0.87,
        "source_url": "https://www.bilibili.com/video/BVxxxxxxxxx",
        "trace_id": "7f3a9c2e8b1d4f6a8c0e2b4d6f8a1c3e"
    }],
    documents=["AI agent 的核心是 prompt + tool + memory 三件套。prompt 决定模型行为，tool 提供外部能力，memory 维持上下文连续性。"]
)
```

**主角终态**：转写文本（旅程 3 第 42 段）→ 实体 E-001（旅程 4）→ 知识树节点 N-2026-06-02-AI-Agent-3c-suit（旅程 5/6），以双轨形态（SQLite + Chroma）落盘，可被后续 RAG 检索（旅程 7 见下）。

---

### 旅程 7（回看）：报告输出（t=7000ms，P-13 拍）

| 项 | 值 |
|----|---|
| 数据形态 | `report.md`（Markdown 报告） |
| 文件结构 | `data/report/{trace_id}/report.md` |
| 处理动作 | ① 模板渲染 ② 引用标注 ③ 源链接 ④ 不确定项显式标注 |
| 模块归属 | **M-007.stages.postprocess.py** |
| 数据结构 | DS-010 报告结构（标题/摘要/关键点/源/不确定项） |

**Markdown 示例**：
```markdown
# 技术大会 talk 调研 — AI Agent 三件套

## 摘要
视频提出了 AI Agent 的核心三件套：prompt、tool、memory ...

## 关键概念
- **AI Agent 三件套** (置信度 0.87)
  - 来源：BVxxxxxxxxx @ 412.5-428.3s
  - 子项：Prompt / Tool / Memory

## 源
- 视频 BVxxxxxxxxx（命中 NLI ≥ 0.7：4 段；未命中已省略）

## 不确定项
无
```

---

## 主角 B：知识树节点的全局视图

| 阶段 | 模块 | 数据形态 | 关键标识 | 数据结构 | 落盘位置 |
|------|------|----------|----------|----------|----------|
| 来源 | M-008.routing | URL | BVxxxxxxxxx | DS-011 URL 解析 | — |
| raw | M-014.collect + M-017 | manifest.json | trace_id=7f3a... | DS-005 | `data/raw/{trace_id}/manifest.json` |
| clean | M-014.clean + M-008.indexing | cleaned.segments.json | segment_id=42 | DS-002 | `data/clean/{trace_id}/` |
| extract | M-007.llm + M-008.nli | entities.json | entity_id=E-001 | DS-003 | `data/extract/{trace_id}/` |
| organize | M-014.organize + M-013 | knowledge_patch.json | node_id=N-... | DS-006 | `data/organize/{trace_id}/` |
| 写入 | M-013 + M-017 | long_term_memory 表 + chroma | node_id=N-... | DS-008 / DS-009 | `data/tutor.db` + `data/chroma/` |
| 报告 | M-007.postprocess | report.md | — | DS-010 | `data/report/{trace_id}/report.md` |
| 监控 | M-006 | monitor_log JSONL | trace_id=7f3a... | DE-008 | `data/monitor_log/` |

---

## 关键数据一致性观察

| 数据对 | 关系 | 一致性 | 处理策略 | 来源 |
|--------|------|--------|----------|------|
| segment_id ↔ entity_id | 1:N | 最终一致 | extract 后异步引用 | [SA-DA §二] |
| entity_id ↔ nli_score | 1:1 | 强一致 | 同步写 | [SA-DA §二] |
| node_id ↔ entity_id | N:1 | 强一致 | organize 阶段 1:1 映射 | [SA-DA §二] |
| node_id ↔ chroma embedding | 1:1 | 最终一致 | 写后异步 embed | [SA-DA §二] |
| rag_state ↔ nli_score | 1:N | 强一致 | 同步写（事务封装） | [SA-DA §二] |
| file_tree ↔ 实际文件 | 1:1 | 弱校验 | 扫描 + warn only | [SA-DA §二] |

---

## 关键落盘点总览（与 SA-D §一 数据视图对照）

| 数据 | 写模块 | 落盘位置 | DE-NNN | DS-NNN | 触发拍 |
|------|--------|----------|--------|--------|--------|
| 字幕原文 | M-014.collect | `data/raw/{tid}/subtitle.srt` | 文件 | — | P-07 |
| 音频 | M-014.collect | `data/raw/{tid}/audio.wav` | 文件 | — | P-07 |
| 清单 | M-014.collect | `data/raw/{tid}/manifest.json` | DE-035 | DS-005 | P-08 |
| 清洗文本 | M-014.clean | `data/clean/{tid}/cleaned.txt` | 文件 | DS-001 | P-10 |
| 分段 | M-014.clean | `data/clean/{tid}/cleaned.segments.json` | DE-025 | DS-002 | P-10 |
| 实体 | M-007.llm | `data/extract/{tid}/entities.json` | DE-020 | DS-003 | P-11 |
| 关键词 | M-007.llm | `data/extract/{tid}/keywords.json` | DE-021 | DS-004 | P-11 |
| 摘要 | M-007.llm | `data/extract/{tid}/summary.md` | — | — | P-11 |
| 知识 patch | M-014.organize | `data/organize/{tid}/knowledge_patch.json` | DE-026 | DS-006 | P-12 |
| 报告 | M-007.postprocess | `data/report/{tid}/report.md` | 文件 | DS-010 | P-13 |
| 知识节点 | M-013 + M-017 | `data/tutor.db` long_term_memory | DE-032 | DS-008 | P-14 |
| 向量 | M-013 + M-017 | `data/chroma/local_lib_chunks/` | DE-037 | DS-009 | P-14 |
| 监控 | M-006 | `data/monitor_log/2026-06-02.jsonl` | DE-008 | — | P-02/15 |

---

## 结论

- 转写文本从"视频流" → "raw/subtitle.srt" → "cleaned.segments.json[42]" → "entities.json[E-001]" → "knowledge_patch.json[N-...]" → "long_term_memory[N-...]" + "chroma[N-...]" → "report.md"，共 7 段旅程，跨 6 个模块，**数据标识 trace_id 全程贯穿**。
- 知识树节点以双轨形态（SQLite 结构化 + Chroma 向量）落盘，可被后续 RAG 检索（CONTRACT：M-008 检索时按 `node_id` 反查 SQLite + 按 embedding 召回 Chroma，合并排序）。
- 数据一致性策略遵循 SA-DA §二，关键写入点（rag_state ↔ nli_score、node_id ↔ embedding）均采用"强一致"（事务封装）以避免数据孤岛。
- 落盘路径完全符合 SA-D §一 存储拓扑，9 个存储位置（5 SQLite + 2 Chroma + 1 文件 + 1 JSONL）与 DS-001~010 数据结构一一对应。

来源标注：[SA-DA §一~§四] + [SA-D §一~§三] + [DD-001 §一.1] + [M-014 FF + M-007 FF + M-013 FF + M-017 FF]
