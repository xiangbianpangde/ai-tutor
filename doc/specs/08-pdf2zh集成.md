# BDD 规格：08 — pdf2zh 深度集成

> 对应功能点：#8 | 设计文档：[设计文档-pdf2zh集成](../plan/design/设计文档-pdf2zh集成.md)

## 功能 1：PDF → 中文 Markdown 一键完成

### 场景 1：中文教材 PDF 只解析不翻译
- 前置条件：pdf2zh 已安装，MinerU CLI 可用
- 操作步骤：
  1. 用户拖入中文教材 PDF（如《高等数学》）
  2. 系统自动检测语言（中文字符占比 > 30%）
- 预期结果：仅执行 MinerU 解析，输出 Markdown（含公式/表格/图片引用），不触发翻译

### 场景 2：英文论文 PDF 解析 + 翻译
- 前置条件：DEEPSEEK_API_KEY 已配置
- 操作步骤：
  1. 用户拖入英文论文 PDF
  2. 系统检测为英文 → 自动执行 MinerU 解析 + DeepSeek 翻译
- 预期结果：输出 `<stem>_zh.md`，公式/引用编号保留，翻译并发 ≥ 8 worker

### 场景 3：批量 PDF 处理
- 前置条件：用户拖入 5 个 PDF 文件
- 操作步骤：
  1. 批量转换
- 预期结果：5 个 PDF 依次处理，已存在 `_zh.md` 的自动跳过（断点续跑）

### 场景 4：翻译后端切换
- 前置条件：用户在设置中选择 Ollama 本地翻译
- 操作步骤：
  1. 拖入英文 PDF
  2. 系统使用 `http://localhost:11434/v1` + `qwen2.5:14b` 翻译
- 预期结果：翻译完成，不经外部 API

---

## 功能 2：pdf2zh 不可用时的优雅降级

### 场景 1：MinerU 未安装 → PyMuPDF fallback
- 前置条件：mineru CLI 不在 PATH
- 操作步骤：
  1. 用户拖入 PDF
- 预期结果：提示"MinerU 未安装，使用 PyMuPDF 提取纯文本（公式可能丢失）"→ 输出纯文本

### 场景 2：翻译 API key 未配置
- 前置条件：DeepSeek key 为空
- 操作步骤：
  1. 拖入英文 PDF
- 预期结果：输出英文 Markdown + 提示"翻译需要 API key，请前往设置配置"

---

## 功能 3：与 Pipeline 集成

### 场景 1：PDF 采集自动流入 KG 构建
- 前置条件：PDF 已转换为 clean Markdown
- 操作步骤：
  1. Pipeline Cleaner 接收 pdf2zh 输出的 `_zh.md`
  2. 清洗 → 结构化 → 喂入 KG Builder
- 预期结果：KG 概念数与 PDF 章节数匹配

### 场景 2：MinerU 后端选择
- 前置条件：用户在设置中选择 MinerU 后端
- 操作步骤：
  1. 可选 `pipeline`（低 VRAM）/ `vlm-auto-engine`（高精度）/ `hybrid-auto-engine`
- 预期结果：相应后端参数传给 mineru CLI
