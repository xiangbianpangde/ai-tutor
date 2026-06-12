# 设计文档：pdf2zh 深度集成

> 涉及模块：`backend/pipeline/collector.py`、`backend/engines/knowledge/pdf_parser.py`
> 外部依赖：`C:/Users/yhn/pdf2zh/`（MinerU + 翻译管线）

## 背景

当前 AI-Tutor 的 PDF 处理 (`pdf_parser.py`) 存在以下问题（来自测试 #17, #19）：

1. **仅调用 mineru CLI**：`subprocess.run(["mineru", "-p", pdf, "-o", out_dir])`——简陋、无错误恢复
2. **pdf2zh 结合度差**："每次都用不好"。当前只是把 pdf2zh 的 `translate_md.py` 翻译逻辑树内复制了一份（`md_translator.py`），但 pdf2zh 的完整管线（并发翻译 / 多后端 / 断点续跑）未利用
3. **中文论文格式兼容差**：mineru 的 OCR 语言参数传递生硬（`"zh" → "ch"` 映射不完整）
4. **翻译与解析割裂**：PDF→MD 和 MD→中文是两个独立步骤，不能一次完成

## 目标

1. PDF → 中文 Markdown **一键完成**（解析 + 翻译一体化）
2. 利用 pdf2zh 的并发翻译能力（默认 8 并发），大幅提升翻译速度
3. 多翻译后端支持（DeepSeek / Ollama 本地 / LM Studio）
4. 断点续跑：已翻译的 PDF 自动跳过
5. 中英文 PDF 自动检测（中文 PDF 只解析不翻译）

## 方案

### 1. 直接复用 pdf2zh 的完整管线

不复制代码，而是直接调用 pdf2zh 的核心函数：

```python
# backend/pipeline/collector.py

class Pdf2ZhAdapter:
    """pdf2zh 适配器。直接调用 pdf2zh 的翻译管线，而非复制代码。"""

    def __init__(self, mineru_cmd: str = "mineru"):
        self.mineru_cmd = mineru_cmd

    def convert(self, pdf_path: Path, output_dir: Path,
                translate: bool = True, workers: int = 8,
                model: str = "deepseek-chat",
                base_url: str = "https://api.deepseek.com",
                api_key: str | None = None) -> Path:
        """PDF → 中文 Markdown，一步完成。

        Returns: _zh.md 路径（translate=True）或 .md 路径（translate=False）
        """

    def batch_convert(self, pdf_dir: Path, output_dir: Path, **kwargs) -> list[Path]:
        """批量转换整个文件夹的 PDF。"""
```

### 2. 与 AI-Tutor Pipeline 的集成点

```
AI-Tutor Pipeline                    pdf2zh 能力
─────────────────                    ──────────
Collector.collect_file(pdf)
  │
  ├── PDF 语言检测 ───────────────→ 中英文自动判断
  │     (前 500 字中文字符占比)
  │
  ├── MinerU 解析 ────────────────→ mineru CLI (pipeline/hybrid/vlm 三后端)
  │     (保留公式/表格/图片引用)
  │
  ├── 翻译（可选）─────────────────→ translate_md.py 并发管线
  │     并发 8 worker                chunk_markdown + translate_chunks_concurrent
  │     断点续跑                     检测 _zh.md 已存在→跳过
  │     多后端                        DeepSeek / Ollama / LM Studio
  │
  └── 输出 ───────────────────────→ <stem>_zh.md → Cleaner → KG Builder
```

### 3. 调用方式

#### 方式 A：subprocess（隔离，推荐）

```python
def _pdf2zh_convert(pdf: Path, out_dir: Path, translate: bool, workers: int) -> Path:
    """调用 pdf2zh 的 pdf_to_zh_md.py。"""
    cmd = [
        sys.executable, str(PDF2ZH_DIR / "pdf_to_zh_md.py"),
        str(pdf), "-o", str(out_dir),
        "--workers", str(workers),
    ]
    if not translate:
        cmd.append("--skip-translate")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise TutorError("PLUGIN_NOT_AVAILABLE", hint=result.stderr[-500:])
    # 找到 _zh.md 输出
    ...
```

#### 方式 B：Python import（深度集成，需要 pdf2zh 在 PYTHONPATH）

```python
# 将 pdf2zh 目录加入 sys.path
sys.path.insert(0, str(PDF2ZH_DIR))
from translate_md import chunk_markdown, translate_chunks_concurrent

def _pdf2zh_translate(md_path: Path, workers: int, client: OpenAI) -> Path:
    md = md_path.read_text(encoding="utf-8")
    chunks = chunk_markdown(md, chunk_size=3000)
    translated = translate_chunks_concurrent(client, chunks, workers=workers)
    zh_path = md_path.with_name(md_path.stem + "_zh.md")
    zh_path.write_text("\n\n".join(translated), encoding="utf-8")
    return zh_path
```

**推荐方式 A**：subprocess 隔离，不污染 AI-Tutor 的 Python 环境。pdf2zh 已自带 `.venv`，可通过 `PDF2ZH_PYTHON` 环境变量指定。

### 4. 多后端支持

```python
# 翻译后端选择逻辑
def _get_translation_client():
    config = get_config()

    if config.translation_backend == "deepseek":
        return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                      base_url="https://api.deepseek.com")
    elif config.translation_backend == "ollama":
        return OpenAI(api_key="ollama",
                      base_url="http://localhost:11434/v1")
    elif config.translation_backend == "lmstudio":
        return OpenAI(api_key="lm-studio",
                      base_url="http://localhost:1234/v1")
    else:
        raise TutorError("CONFIG_ERROR", hint=f"未知翻译后端: {config.translation_backend}")
```

### 5. 中英文自动检测

```python
def _detect_language(text: str, sample_size: int = 500) -> str:
    """检测文本主要语言。中文占比 > 30% → zh，否则保持源语言。"""
    sample = text[:sample_size]
    chinese_chars = sum(1 for c in sample if '\u4e00' <= c <= '\u9fff')
    ratio = chinese_chars / max(len(sample), 1)
    return "zh" if ratio > 0.3 else "en"
```

## 影响范围

| 文件 | 变更 |
|------|------|
| `backend/pipeline/collector.py` | 新增 `Pdf2ZhAdapter` 类 |
| `backend/engines/knowledge/pdf_parser.py` | 重写：委托 pdf2zh，保留旧 mineru 作为 fallback |
| `backend/engines/knowledge/md_translator.py` | 废弃：不再自己维护翻译逻辑 |
| `backend/core/config.py` | 新增 `translation_backend` / `pdf2zh_path` 配置项 |
| `pyproject.toml` | 移除 pdf2zh 相关依赖（subprocess 隔离，不需要） |

## 风险

| 风险 | 缓解 |
|------|------|
| pdf2zh 未安装时 PDF 功能不可用 | pip install 提示 + 回退到 PyMuPDF 纯文本提取（无公式保留） |
| pdf2zh API 变更导致 subprocess 调用失败 | 版本锁定 + CI 测试 pdf2zh 集成 |
| MinerU 模型下载大（~7GB） | 首次使用时提示下载，进度条展示 |
| 翻译 LLM 调用费用 | 中文 PDF 自动跳过翻译；可设置预算上限 |
| pdf2zh 的 .venv 路径不同 | 环境变量 `PDF2ZH_PATH` 配置，启动时自动探测 |
