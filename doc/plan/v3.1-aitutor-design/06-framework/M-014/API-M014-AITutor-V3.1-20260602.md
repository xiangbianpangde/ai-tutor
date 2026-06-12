# API-M014-AITutor-V3.1-20260602 — M-014 接口注释清单

> **模块**: M-014 数据管线
> **关联接口契约**: IC-004（数据入库，API-004/IF-004）
> **日期**: 2026-06-02
> **作者**: DD-M-014-20260602
> **来源**: [DD-001:IC-004] + [DD-M推断:依据=DD-001:soul 3.6 接口注释清单模板]

---

## 一、IC-004 → M-014 函数映射

### 1.1 IC-004 入参契约 → DataPipeline.process_pdf()

```python
def process_pdf(
    pdf_path: str,             # [DD-001:IC-004] 文件: UploadFile → 本地路径
    *,
    user_id: str,              # [DD-001:IC-004] 必填，强校验
    trace_id: Optional[str] = None,  # [DD-001:IC-004] 可选，默认生成 32hex
) -> ProcessResult:
    """处理单个 PDF（公开入口）

    [DD-001:IC-004] POST /api/v1/ingest 主入口
    [DD-001:MD-M014] DataPipeline.run() 业务实现
    """
```

### 1.2 IC-004 出参契约 → ProcessResult 模型

```python
class ProcessResult(BaseModel):
    doc_id: str                 # [DD-001:IC-004] 必填 UUIDv4
    status: ProcessStatus       # [DD-001:IC-004] READY/FAILED/PARTIAL
    chunk_count: int            # [DD-001:IC-004] 必填
    translation_backend: TranslationBackend  # [DD-001:IC-004] 必填
    duration_ms: int            # [DD-001:IC-004] 必填
    trace_id: str               # [DD-001:IC-004] 必填 32hex
    error_code: Optional[str]   # [DD-001:IC-004] FAILED 时填充
    error_message: Optional[str] # [DD-001:IC-004] FAILED 时填充
```

### 1.3 IC-004 错误码 → exceptions.py

| 错误码 | 含义 | 异常类 | 触发条件 | 处理 |
|--------|------|--------|---------|------|
| E01401 | pdf2zh 失败 | TranslationFailedError | PDF 解析异常 | pdfplumber→LM Studio 3 降级 |
| E01402 | LLM 超时 | LLMTimeoutError | 30s 未响应 | 重试 1 次 |
| E01403 | clean 重复率>30% | CleanDedupExceededError | 去重不足 | 增强 clean + WARN（不阻塞） |
| E01404 | 文件超大 | FileTooLargeError | >100MB | 拒绝（status=FAILED） |
| E01405 | 文件类型非法 | InvalidFileTypeError | 非 PDF | 拒绝（status=FAILED） |

---

## 二、M-014 公开 API 注释清单

| API 编号 | 函数签名 | 关联契约 | 实现文件 | 注释状态 |
|---------|---------|---------|---------|---------|
| API-M014-001 | `DataPipeline.process_pdf(pdf_path, user_id, trace_id) → ProcessResult` | IC-004 | `pipeline.py` | ✅ 完整 |
| API-M014-002 | `TextCleaner.clean(text) → str` | IC-004 内部 | `clean.py` | ✅ 完整 |
| API-M014-003 | `TextCleaner.detect_dedup_ratio(text) → float` | IC-004 内部 | `clean.py` | ✅ 完整 |
| API-M014-004 | `Chunker.chunk(text, doc_id) → List[Chunk]` | IC-004 内部 | `chunk.py` | ✅ 完整 |
| API-M014-005 | `Ingester.ingest(chunks, doc_id) → int` | IC-004 内部 | `ingester.py` | ✅ 完整 |
| API-M014-006 | `BaseTranslator.translate(pdf_path) → str` | IC-004 内部 | `translate/base.py` | ✅ 完整 |
| API-M014-007 | `PDF2ZhTranslator.translate(pdf_path) → str` | IC-004 内部 | `translate/pdf2zh.py` | ✅ 完整 |
| API-M014-008 | `PDFPlumberTranslator.translate(pdf_path) → str` | IC-004 内部 | `translate/pdfplumber.py` | ✅ 完整 |
| API-M014-009 | `LMStudioTranslator.translate(pdf_path) → str` | IC-004 内部 | `translate/lmstudio.py` | ✅ 完整 |
| API-M014-010 | `create_translator(backend, config, trace_id) → BaseTranslator` | IC-004 内部 | `translate/__init__.py` | ✅ 完整 |
| API-M014-011 | `PipelineStateMachine.transition(event) → PipelineStage` | IC-004 内部 | `state_machine.py` | ✅ 完整 |
| API-M014-012 | `PipelineStateMachine.is_terminal() → bool` | IC-004 内部 | `state_machine.py` | ✅ 完整 |
| API-M014-013 | `PipelineStateMachine.force_fail(reason) → PipelineStage` | IC-004 内部 | `state_machine.py` | ✅ 完整 |

**13/13 公开 API 100% 注释化**（D4 = 100%）

---

## 三、IC-004 契约完整覆盖校验

| IC-004 字段 | 在 M-014 中体现位置 | 状态 |
|------------|-------------------|------|
| 入参 file（PDF ≤100MB） | DataPipeline._validate_input | ✅ |
| 入参 user_id（强校验） | DataPipeline.process_pdf 注释 | ✅ |
| 入参 clean_dedup | DataPipeline.process_pdf（DD-M推断:实现） | ✅ |
| 入参 chunk_size [500, 4000] | Chunker 构造器 | ✅ |
| 入参 overlap [0, 500] | Chunker 构造器 | ✅ |
| 出参 doc_id | ProcessResult.doc_id | ✅ |
| 出参 status | ProcessResult.status | ✅ |
| 出参 chunk_count | ProcessResult.chunk_count | ✅ |
| 出参 translation_backend | ProcessResult.translation_backend | ✅ |
| 出参 duration_ms | ProcessResult.duration_ms | ✅ |
| 出参 trace_id | ProcessResult.trace_id | ✅ |
| 错误码 E01401 | TranslationFailedError | ✅ |
| 错误码 E01402 | LLMTimeoutError | ✅ |
| 错误码 E01403 | CleanDedupExceededError | ✅ |
| 错误码 E01404 | FileTooLargeError | ✅ |
| 错误码 E01405 | InvalidFileTypeError | ✅ |
| 时序图 | pipeline.py 流程注释 | ✅ |
| 前置条件 | DataPipeline.process_pdf 注释 | ✅ |
| 后置条件 | DataPipeline.process_pdf 注释 | ✅ |
| 并发安全 | ProcessResult 注释 | ✅ |
| 幂等性 | DataPipeline.process_pdf 注释（非幂等） | ✅ |
| 性能约束 | DataPipeline.process_pdf 注释（10 页 ≤60s） | ✅ |

**IC-004 完整覆盖：22/22 字段**（D4 = 100%）

---

## 来源标注

[DD-001:IC-004/MD-M014] + [DD-M推断:依据=DD-001:soul 3.6 接口注释清单模板]
