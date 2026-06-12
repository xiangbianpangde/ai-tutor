# pdf2zh-core 拆分计划

目标：从 pdf2zh 项目中抽出轻量核心库，ai-tutor 直接 import 而非 subprocess
预估：1 天拆分 + 对接

---

## 现状

ai-tutor 当前通过 subprocess 调 pdf2zh：

```python
# pdf_parser.py
subprocess.run(["pdf2zh", str(pdf), "-lo", "zh", "-o", str(out_dir)])
```

问题：启动进程开销、无法获取 Python traceback、health check 靠 shutil.which

## 目标产物

pdf2zh 拆为两层：

```
pdf2zh/
├── pdf2zh-core/              ★ 新建：轻量核心库
│   ├── pyproject.toml        依赖：pymupdf + openai + httpx（无 gradio/onnx/huggingface）
│   └── src/pdf2zh_core/
│       ├── parser.py         PDF -> text/markdown (pymupdf)
│       ├── translator.py     文本翻译 (LLM API)
│       ├── writer.py         写回 PDF 或输出 .md
│       └── types.py
├── pdf2zh-web/               原 pdf2zh，依赖 pdf2zh-core + gradio
└── pdf2zh-v1.9.11-win64/    现有发布物，不动
```

ai-tutor 新接入方式：

```python
from pdf2zh_core import parse_pdf, translate_pdf

# health check: import pdf2zh_core 成功即可
```

## 实施步骤

### Step 1：审计（30 分钟）

在 pdf2zh 源码中回答：核心翻译逻辑在哪个文件/函数？依赖哪些库（哪些必需/哪些是 web 层）？输出一个"进 core / 留 web / 删"的清单。

### Step 2：建 pdf2zh-core 包（1 小时）

pyproject.toml 只依赖 pymupdf + openai + httpx。不碰 gradio/onnx/huggingface/babeldoc。

### Step 3：搬函数（2 小时）

从原 pdf2zh 搬核心逻辑到 pdf2zh-core：

- parser.py：打开 PDF、提取文本层（按页）、可选 OCR 回退
- translator.py：分块（按段落/页不超过 LLM context）、调 LLM API、组装译文
- writer.py：译版 PDF 写入或直接输出 .md
- types.py：PageText / TranslationChunk / TranslateResult

约束：函数签名与当前 CLI 行为对齐。translate_pdf(input_path, target_lang="zh") -> Path，保持与 pdf_parser.py 现有调用语义一致。

### Step 4：pdf2zh-web 依赖 core（30 分钟）

原 pdf2zh/pyproject.toml 加 pdf2zh-core 依赖。web/cli 层改为 from pdf2zh_core import ...。确保 web UI 原功能回归。

### Step 5：ai-tutor 对接（1 小时）

ai-tutor/pyproject.toml 加 pdf2zh-core 为 research extra 的本地路径依赖：

```toml
[tool.uv.sources]
pdf2zh-core = { path = "../pdf2zh/pdf2zh-core" }
```

pdf_parser.py 改造：

```python
# 原来 subprocess
def translate_pdf(pdf, out_dir, *, pdf2zh_cmd="pdf2zh", lang_out="zh"):
    if not _which(pdf2zh_cmd):
        raise TutorError(...)
    _run([pdf2zh_cmd, ...])

# 改为 import
def translate_pdf(pdf, out_dir, *, lang_out="zh"):
    try:
        from pdf2zh_core import translate as _core_translate
    except ImportError:
        raise TutorError("DEPENDENCY_MISSING", hint="uv sync --extra research")
    result = _core_translate(pdf, target_lang=lang_out, output_dir=out_dir)
    return result.output_path
```

MinerUPdfParser.health() 改为 import pdf2zh_core 探测。

### Step 6：测试（1 小时）

test_pdf_parser.py 现有 5 个 test，Mock 从 monkeypatch(_which) 改为 monkeypatch(sys.modules)。逻辑不变。加 1 个 BDD Scenario。全量 pytest 714 -> 715+ 回归。

### Step 7：清理（30 分钟）

pdf_parser.py 删 _which() / _run() / _PDF2ZH_INSTALL 等 subprocess 代码。acquisition_adapter.py 删 mineru_cmd 参数透传。mineru 部分不动（非你的项目，继续 CLI 隔离）。

## 不改动的部分

- mineru 相关代码（不是你的项目，CLI 隔离正确）
- MinerUPdfParser 类（保留 Plugin 接口，只改内部实现）
- acquisition_adapter.py 的 _acquire_file 调用链（仍返回 CorpusSource + Path）

## 排入总计划

原 INTEGRATED-IMPLEMENTATION-PLAN.md 中 pdf2zh 在 Stage 3 占 1.5 天。拆分后：

原：pdf2zh adapter + UI 1.5 天
现：拆分 1 天 + adapter 0.5 天（砍 tools-ui 的 pdf2zh 页）= 净增 0 天
