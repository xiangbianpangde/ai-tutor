# 框架决策记录（FDR）— M-008 RAG 引擎（AITutor V3.1）

> 角色：DD-M-008 详细设计师（模块）
> 关联模块：M-008 RAG 引擎
> 来源标注：[DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-M推断:依据=4.13 FDR 模板]

---

## FDR-008-001 ChromaIndexAdapter 拆分为双层

- **决策状态**：已接受
- **决策内容**：将 MD-M-008 定义的 ChromaIndexAdapter 拆分为 `chroma.py`（原生封装）与 `adapter.py`（抽象基类 + ChromaIndexAdapter）
- **决策理由**：
  1. 4.7 文件结构合规要求文件职责单一
  2. MD-M-008 中 ChromaIndexAdapter 同时承担「原生操作」与「适配器抽象」两种职责，违反 SRP
  3. 拆分后未来新增 Qdrant / Milvus 索引后端时不影响 engine.py（OCP 原则）
  4. 抽象基类 IndexAdapter 与原生封装 ChromaCollection 分层清晰
- **拒绝的替代方案**：
  - 方案 B（拒绝）：保持 MD-M-008 原始 ChromaIndexAdapter 单文件 → 违反 4.7 单一职责
  - 方案 C（拒绝）：仅保留抽象基类，不提供 Chroma 原生封装 → V3.1 仍需 Chroma 实现，业务不可用
- **影响范围**：
  - 文件：`src/aitutor/rag/indexing/chroma.py`（新增）
  - 文件：`src/aitutor/rag/indexing/adapter.py`（拆分为抽象 + 默认实现）
  - 测试：`tests/unit/test_rag/test_indexing.py`（拆分为 7 个测试场景）
- **相关FDR**：无
- **来源标注**：[DD-001:MD-M-008 ChromaIndexAdapter] + [DD-M推断:依据=4.7 + OCP]

---

## FDR-008-002 翻译子能力仅依赖注入不直接 import M-014

- **决策状态**：已接受
- **决策内容**：TranslationAdapter 仅持有 M-014 翻译管线客户端对象（依赖注入），不直接 import M-014 内部模块
- **决策理由**：
  1. soul R28 禁止跨模块操作（DD-M 仅操作 M-008 内文件）
  2. soul R29 禁止模块职责扩散（在 M-008 中实现 M-014 业务逻辑）
  3. 依赖注入而非直接 import 符合 Adapter 模式最佳实践
  4. 测试时可通过 mock m014_pipeline_client 隔离跨模块依赖
- **拒绝的替代方案**：
  - 方案 B（拒绝）：直接 import M-014 translate 函数 → 触发 R28/R29 红线
  - 方案 C（拒绝）：在 M-008 内重新实现 PDF 翻译（pdf2zh/pdfplumber/lmstudio）→ 模块职责扩散 + 重复实现
- **影响范围**：
  - 文件：`src/aitutor/rag/translation/adapter.py`（仅依赖注入）
  - 文件：`src/aitutor/rag/engine.py`（PDFTranslationAdapter 构造时注入客户端）
  - 测试：`tests/unit/test_rag/test_translation.py`（mock M-014 客户端）
- **相关FDR**：无
- **来源标注**：[soul R28/R29] + [DD-001:MD-M-008 TranslationAdapter] + [DD-M推断:依据=Adapter 模式 + 模块边界]

---

## FDR-008-003 NLI 模型启动期 CPU 亲和性绑定

- **决策状态**：已接受
- **决策内容**：NLIModelLoader 提供 bind_cpu_affinity(cpu_id=0) 方法，启动期调用
- **决策理由**：
  1. AR INSIGHT-AR-001 明确记录 M-008 NLI 与 M-014 PDF 翻译存在 CPU 争抢（4 核环境）
  2. NLI 模型 1.5GB+ transformers 推理，CPU 密集
  3. 绑定到 CPU 0 后 M-014 PDF 翻译走 ThreadPool 走 CPU 1-3，缓解争抢
  4. 来源：[AC:INSIGHT-AR-001] + [DD-001:DD洞察-002]
- **拒绝的替代方案**：
  - 方案 B（拒绝）：不绑定亲和性 → 4 核下 NLI 与 PDF 翻译争抢，P95 延迟翻倍
  - 方案 C（拒绝）：NLI 走独立进程 → 进程间通信开销大，且 V3.1 单进程设计
- **影响范围**：
  - 文件：`src/aitutor/rag/nli/model.py`（新增 bind_cpu_affinity 方法）
  - 调用方：M-001 启动期（不在 M-008 范围）
  - 测试：`tests/unit/test_rag/test_nli.py`（测试场景 5：CPU 亲和性绑定）
- **相关FDR**：无
- **来源标注**：[AR:INSIGHT-AR-001] + [DD-001:DD洞察-002] + [DD-M推断:依据=CPU 亲和性]

---

## FDR-008-004 NLI 评分结果写入 M-005 缓存

- **决策状态**：已接受
- **决策内容**：NLIScorer.score() 在注释中标注「调用 M-005 CacheProxy.semantic_set(score)」，TTL 1h
- **决策理由**：
  1. IC-003 后置条件明确规定「NLI 评分缓存写入（TTL 1h）」
  2. 重检索 3 轮场景下，若 NLI 评分不缓存，3 轮总耗时 = 3 × NLI 推理时间
  3. 缓存命中时直接返回 0.1s，性能提升 10x
  4. 缓存键：query_hash + premise_hash
- **拒绝的替代方案**：
  - 方案 B（拒绝）：NLI 评分不缓存 → 3 轮重检索 P95 延迟 30s（违反 IC-003 ≤10s 约束）
  - 方案 C（拒绝）：M-008 自建缓存 → 重复实现，违反单一职责
- **影响范围**：
  - 文件：`src/aitutor/rag/nli/scorer.py`（注释中标注缓存调用）
  - 实际实现：开发工程师按注释调用 M-005 CacheProxy
  - 测试：`tests/unit/test_rag/test_nli.py`（mock M-005 缓存）
- **相关FDR**：无
- **来源标注**：[DD-001:IC-003 后置条件] + [DD-M推断:依据=性能约束]

---

## FDR-008-005 子能力命名空间隔离缓解内聚度过低

- **决策状态**：已接受
- **决策内容**：M-008 采用 `routing/` / `nli/` / `indexing/` / `translation/` 4 子能力目录
- **决策理由**：
  1. DD-001 洞察 001 记录 M-008 内聚度 3/6（最低），承担 4 大子能力
  2. 4 子能力目录隔离副作用，避免单文件膨胀
  3. Import Litter contract 6 独立声明 4 子能力，强制独立性
  4. 未来 V3.2 触发 100 用户时可直接物理拆分为 M-008a/M-008b/M-008c/M-008d
- **拒绝的替代方案**：
  - 方案 B（拒绝）：保持单目录（`rag/*.py`）→ 内聚度进一步下降，4 子能力互相干扰
  - 方案 C（拒绝）：现在就物理拆分为 4 模块 → V3.1 用户量不足，过度设计
- **影响范围**：
  - 目录结构：`rag/{routing,nli,indexing,translation}/`
  - Import Litter：`.importlinter.toml` contract 6
  - 后续演进：V3.2 触发 100 用户时拆分为 4 模块
- **相关FDR**：FDR-008-001（ChromaIndexAdapter 拆分与此一致）
- **来源标注**：[DD-001:DD洞察-001] + [DD-001:FS-M-008 特殊说明] + [DD-M推断:依据=模块边界]

---

## FDR-008-006 测试文件 6 大场景覆盖

- **决策状态**：已接受
- **决策内容**：每个测试文件覆盖 6+ 个测试场景：正常流程、边界、异常、并发、幂等、模块边界
- **决策理由**：
  1. soul 4.9 自评审清单要求测试文件注释完整
  2. MD-M-008 测试策略要求 20 用例（V3.1 全量）
  3. M-008 涉及重检索状态机，6 场景能覆盖核心状态转换
  4. 跨模块依赖（M-014）必须 mock，避免 R28 红线
- **拒绝的替代方案**：
  - 方案 B（拒绝）：仅 1-2 个正常流程测试 → 覆盖率不足
  - 方案 C（拒绝）：直接调用 M-014 真实接口 → 触发 R28 跨模块操作
- **影响范围**：
  - 5 个测试文件，每个 6-7 测试场景
  - 全部 mock 外部依赖（chromadb / transformers / M-014）
- **相关FDR**：无
- **来源标注**：[DD-001:MD-M-008 测试策略] + [soul 4.9] + [DD-M推断:依据=测试覆盖]

---

## FDR 状态汇总

| FDR 编号 | 状态 | 决策摘要 |
|---------|------|---------|
| FDR-008-001 | 已接受 | ChromaIndexAdapter 拆分双层 |
| FDR-008-002 | 已接受 | 翻译子能力仅依赖注入 |
| FDR-008-003 | 已接受 | NLI CPU 亲和性绑定 |
| FDR-008-004 | 已接受 | NLI 评分缓存 M-005 |
| FDR-008-005 | 已接受 | 子能力命名空间隔离 |
| FDR-008-006 | 已接受 | 测试 6 场景覆盖 |

**FDR 总数：6 条 | 已接受：6 条 | 已拒绝：0 条 | 已取代：0 条**

来源标注：[DD-001:FS-M-008] + [DD-001:MD-M-008] + [soul 4.13] + [DD-M推断:依据=FDR 模板]
