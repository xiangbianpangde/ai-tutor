# 依赖清单

> 所有 Python 包 + Docker 镜像 + 外部服务依赖  
> 版本号策略：主版本锁定，次版本用 `>=`

---

## 一、Python 依赖

### 核心框架

```toml
# pyproject.toml [project.dependencies]
python = ">=3.12"

# MCP 框架
fastmcp = ">=2.0"                # FastMCP server 框架

# 数据验证
pydantic = ">=2.0"

# 数据库
sqlalchemy = ">=2.0"
alembic = ">=1.14"
# 开发用 SQLite (Python 内置)
# 生产用: psycopg2-binary = ">=2.9"

# 缓存
redis = ">=5.0"                  # Python redis client

# 日志
structlog = ">=24.0"

# HTTP (插件调用 + health check)
httpx = ">=0.27"

# 异步
anyio = ">=4.0"
```

### L4 知识工程

```toml
# PDF 解析 (plugin: pymupdf4llm fallback)
pymupdf4llm = ">=0.0.17"

# Markdown 处理
python-frontmatter = ">=1.0"
markdown = ">=3.6"

# 向量索引 (本地)
chromadb = ">=0.5"

# 语义相似度 (轻量 embedding)
sentence-transformers = ">=3.0"  # 含 all-MiniLM-L6-v2 模型

# 去重
simhash = ">=2.1"

# HTTP 客户端 (web_collect)
beautifulsoup4 = ">=4.12"
lxml = ">=5.0"
```

### L3 长期记忆

```toml
# 数值计算 (遗忘曲线拟合)
numpy = ">=1.26"
scipy = ">=1.12"                 # least-squares 拟合
```

### L5 学习者建模 (Phase 3+)

```toml
# DKT 模型训练
torch = ">=2.2"                  # CPU 版本; CUDA 可选
```

### L6 教学引擎

```toml
# 图算法 (拓扑排序、BFS)
networkx = ">=3.3"
```

### L7 课件生成 (digest-mcp)

```toml
# 幻灯片
python-pptx = ">=0.6"
img2pdf = ">=0.5"

# 笔记 PDF
reportlab = ">=4.1"

# 音频
edge-tts = ">=6.1"

# 思维导图
# mermaid-cli 通过 Docker 或 npm 全局安装，非 Python 包
```

### sync-mcp

```toml
# GitHub
PyGithub = ">=2.3"

# Obsidian 监听
watchdog = ">=4.0"
```

### LLM API

```toml
# 多 provider 统一接口
openai = ">=1.50"                # DeepSeek 兼容 OpenAI SDK
# anthropic = ">=0.40"           # 可选: Anthropic SDK
```

### 开发与测试

```toml
# pyproject.toml [project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-mock>=3.14",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.11",
    "freezegun>=1.5",            # 时间 mock
    "httpx-mock>=0.2",           # HTTP mock
]
```

---

## 二、Docker 镜像

```yaml
# docker-compose.yml 中的 services

services:
  # PDF 解析（二选一或全安装）
  pdf2zh:
    image: xiangbianpangde/pdf2zh:latest
    # GPU: 需要 nvidia runtime
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
    ports:
      - "8081:8080"

  mineru:
    image: opendatalab/mineru:latest
    # GPU: 需要 nvidia runtime
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
    ports:
      - "8082:8080"

  # 语音转写
  whisper:
    image: onerahmet/openai-whisper-asr-webservice:latest
    # 或用 faster-whisper:
    # image: fedirz/faster-whisper-server:latest
    environment:
      - ASR_MODEL=base
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/health"]
    ports:
      - "9000:9000"

  # 缓存
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # 应用 server（4 个）
  knowledge-mcp:
    build:
      context: .
      dockerfile: Dockerfile
      target: knowledge-mcp
    environment:
      - TRANSPORT=http
      - DATABASE_URL=postgresql://...  # 生产
      - REDIS_URL=redis://redis:6379
      - PDF_PARSE_PROVIDER=auto
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    depends_on:
      redis:
        condition: service_healthy

  tutoring-mcp:
    build:
      context: .
      dockerfile: Dockerfile
      target: tutoring-mcp
    environment:
      # 同上
    depends_on:
      redis:
        condition: service_healthy

  digest-mcp:
    build:
      context: .
      dockerfile: Dockerfile
      target: digest-mcp
    environment:
      # 同上

  sync-mcp:
    build:
      context: .
      dockerfile: Dockerfile
      target: sync-mcp
    environment:
      # 同上

volumes:
  redis_data:
```

---

## 三、Dockerfile 模板

```dockerfile
# Dockerfile (multi-stage, 4 个 target)
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/

# --- knowledge-mcp ---
FROM base AS knowledge-mcp
COPY servers/knowledge_mcp/ ./servers/knowledge_mcp/
RUN uv sync --package knowledge-mcp
EXPOSE 8001
CMD ["uv", "run", "python", "-m", "servers.knowledge_mcp.server", "--transport", "http"]

# --- tutoring-mcp ---
FROM base AS tutoring-mcp
COPY servers/tutoring_mcp/ ./servers/tutoring_mcp/
RUN uv sync --package tutoring-mcp
EXPOSE 8002
CMD ["uv", "run", "python", "-m", "servers.tutoring_mcp.server", "--transport", "http"]

# --- digest-mcp ---
FROM base AS digest-mcp
COPY servers/digest_mcp/ ./servers/digest_mcp/
RUN uv sync --package digest-mcp
EXPOSE 8003
CMD ["uv", "run", "python", "-m", "servers.digest_mcp.server", "--transport", "http"]

# --- sync-mcp ---
FROM base AS sync-mcp
COPY servers/sync_mcp/ ./servers/sync_mcp/
RUN uv sync --package sync-mcp
EXPOSE 8004
CMD ["uv", "run", "python", "-m", "servers.sync_mcp.server", "--transport", "http"]
```

---

## 四、pyproject.toml 结构

```toml
[project]
name = "ai-tutor"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = [
    "shared",
    "servers/knowledge_mcp",
    "servers/tutoring_mcp",
    "servers/digest_mcp",
    "servers/sync_mcp",
]

[tool.uv.sources]
# 每个 package 的 source 路径

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 五、外部 API 依赖总览

| 服务 | provider | 用途 | key 环境变量 | 免费额度 |
|------|---------|------|-------------|---------|
| LLM | DeepSeek | 知识抽取 + 教学交互 | `DEEPSEEK_API_KEY` | 付费（极便宜） |
| LLM (备选) | OpenAI | 同上 | `OPENAI_API_KEY` | 付费 |
| PDF 解析 | pdf2zh (Docker) | PDF→MD | 无 | 免费（本地） |
| PDF 解析 (备选) | MinerU (Docker) | PDF→MD | 无 | 免费（本地） |
| 语音转写 | faster-whisper (Python) | 音频→文本 | 无 | 免费（本地） |
| 语音转写 (备选) | OpenAI Whisper | 音频→文本 | `OPENAI_API_KEY` | 付费 |
| TTS | edge-tts (Python) | 文本→语音 | 无 | 免费 |
| TTS (备选) | OpenAI TTS | 文本→语音 | `OPENAI_API_KEY` | 付费 |
| 图像生成 | Gemini Imagen | 课件配图 | `GEMINI_API_KEY` | 付费 |
| 图像生成 (默认) | mock (内置) | 开发占位图 | 无 | 免费 |
| 搜索 | DuckDuckGo (Python) | web_collect | 无 | 免费 |
| 搜索 (备选) | Tavily | web_collect | `TAVILY_API_KEY` | 付费 |
| Embedding | all-MiniLM (本地) | 概念向量化 | 无 | 免费（本地） |
| 教材检索 | Anna's Archive | fetch_textbook | 无 | 免费（仅元数据） |

**零成本最小配置**：DeepSeek API key（约 $2/科目）+ 本地 Docker。

---

## 六、系统要求

```
最低 (开发):
  Python 3.12+
  Docker 24+
  8 GB RAM
  10 GB 磁盘 (不含模型)
  GPU 可选（不装则 PDF 解析和 whisper 用 CPU，速度慢但可用）

推荐 (生产):
  Python 3.12+
  Docker 24+ with nvidia-container-toolkit
  16 GB RAM
  NVIDIA GPU 8GB+ VRAM (pdf2zh + whisper 加速)
  50 GB 磁盘 (含模型)
  Redis 7+
  PostgreSQL 15+
```
