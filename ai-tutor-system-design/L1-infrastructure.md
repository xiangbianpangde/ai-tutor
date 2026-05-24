# L1 基础设施

> 职责：存储抽象、插件注册、认证、日志、监控、多模态工具链  
> 范围：所有上层共享的横切关注点

---

## 1. 存储层

### 1.1 四类存储抽象

```python
# === FileStore: 产物文件存储（PDF/图片/HTML等）===
class FileStore(Protocol):
    def put(self, path: str, content: bytes) -> ArtifactURI:
        """存储文件，返回 artifact:// URI"""
    
    def get(self, uri: ArtifactURI) -> bytes:
        """按 URI 读取文件"""
    
    def presign(self, uri: ArtifactURI, ttl_sec: int = 3600) -> str:
        """生成临时访问 URL（S3后端），本地后端返回 file://"""
    
    def archive(self, uri: ArtifactURI) -> ColdStorageLocation:
        """归档到冷存储（S3 Glacier / 本地压缩归档）"""
    
    def cleanup_expired(self, retention_days: int = 30):
        """清理过期文件"""

# 实现:
# - LocalFileStore: OUTPUT_DIR 本地目录
# - S3FileStore: boto3 S3 bucket (生产)

# === StateStore: Key-Value 会话/缓存存储 ===
class StateStore(Protocol):
    def session_get(self, session_id: str) -> Optional[SessionContext]:
        """获取会话上下文（L2）"""
    
    def session_put(self, session_id: str, context: SessionContext, ttl: int = 1800):
        """写入会话状态"""
    
    def user_profile_get(self, user_id: str) -> LearnerProfile:
        """获取学习者画像（L5）"""
    
    def user_profile_update(self, user_id: str, profile: LearnerProfile):
        """更新学习者画像"""
    
    def checkpoint_save(self, session_id: str, checkpoint: dict):
        """保存中断断点"""
    
    def checkpoint_load(self, session_id: str) -> Optional[dict]:
        """加载中断断点"""

# 实现:
# - RedisStateStore: 生产/开发（高性能）
# - MemoryStateStore: 单进程测试

# === RelationalStore: 关系型持久存储 ===
class RelationalStore(Protocol):
    """通过 SQLAlchemy ORM 操作"""
    
    # L3 复习数据
    def insert_review_record(self, record: ReviewRecord): ...
    def get_forgetting_curve(self, user_id, concept_id) -> ForgettingCurve: ...
    def get_daily_review_plan(self, user_id, date) -> DailyReviewPlan: ...
    
    # L5 知识状态
    def get_knowledge_snapshot(self, user_id, subject_id) -> KnowledgeSnapshot: ...
    def update_concept_mastery(self, user_id, concept_id, mastery): ...
    
    # L4 KG 数据
    def get_kg(self, kg_id) -> KnowledgeGraph: ...
    def save_kg(self, kg: KnowledgeGraph): ...
    def query_triples(self, kg_id, filters) -> List[Triple]: ...
    
    # 用户
    def get_user(self, user_id) -> User: ...
    def list_subjects(self, user_id) -> List[Subject]: ...

# 实现:
# - SQLite (本地开发，零配置)
# - PostgreSQL (生产，同 schema)

# === VectorStore: 向量语义检索 ===
class VectorStore(Protocol):
    def index_concepts(self, kg_id: str, embeddings: ndarray, ids: List[str]): ...
    def semantic_search(self, query: str, kg_id: str, k: int = 10) -> List[Concept]: ...
    def find_similar_errors(self, error: ErrorDiagnosis, k: int = 5) -> List[ErrorDiagnosis]: ...

# 实现:
# - ChromaDB: 本地（嵌入式，零配置）
# - PGVector: 生产（Postgres 扩展）
```

### 1.2 环境配置

```bash
# .env 示例（仅 Production 配置示例，不含真实密钥）
STORAGE_BACKEND=local          # local | s3
OUTPUT_DIR=./data/output
DATABASE_URL=sqlite:///data/tutor.db    # 开发
# DATABASE_URL=postgresql://...          # 生产
REDIS_URL=redis://localhost:6379        # 生产需要
VECTOR_BACKEND=chromadb                 # chromadb | pgvector
ARTIFACT_RETENTION_DAYS=30
LOG_LEVEL=info
```

---

## 2. 插件架构

### 2.1 插件注册表（非 entry_points）

```python
# 每个 server 启动时加载这个注册表
PLUGIN_REGISTRY = {
    "pdf_parse": {
        "providers": {
            "pdf2zh": {
                "type": "docker",           # docker | python | api
                "image": "xiangbianpangde/pdf2zh:latest",
                "health_endpoint": "/api/health",
                "convert_endpoint": "/api/convert",
                "capabilities": ["native", "scanned", "formula", "multi_lang"],
                "gpu_support": True,
            },
            "mineru": {
                "type": "docker",
                "image": "opendatalab/mineru:latest",
                "health_endpoint": "/health",
                "convert_endpoint": "/api/v1/parse",
                "capabilities": ["native", "scanned", "table", "formula"],
                "gpu_support": True,
            },
            "pymupdf4llm": {
                "type": "python",
                "package": "pymupdf4llm",
                "capabilities": ["native", "table"],
                "gpu_support": False,
            },
        },
        "selection": "auto",    # auto: 按 PDF 特征自动选; manual: env 指定
        "fallback": "pymupdf4llm",
    },
    
    "transcription": {
        "providers": {
            "faster_whisper": {
                "type": "python",
                "package": "faster-whisper",
                "model_size": "base",      # tiny/base/small/medium/large
                "capabilities": ["zh", "en", "auto_detect"],
            },
            "openai_whisper": {
                "type": "api",
                "key_env": "OPENAI_API_KEY",
                "model": "whisper-1",
            },
        },
    },
    
    "text_to_speech": {
        "providers": {
            "edge": {
                "type": "python",
                "package": "edge-tts",
                "cost": "free",
                "languages": ["zh-CN", "en-US", "ja-JP"],
            },
            "openai": {
                "type": "api",
                "key_env": "OPENAI_API_KEY",
                "model": "tts-1",
            },
            "elevenlabs": {
                "type": "api",
                "key_env": "ELEVENLABS_API_KEY",
            },
        },
        "default": "edge",
    },
    
    "image_generation": {
        "providers": {
            "mock": {
                "type": "local",
                "description": "生成占位图 + 文字标注，开发用",
                "cost": "free",
            },
            "gemini": {
                "type": "api",
                "key_env": "GEMINI_API_KEY",
                "model": "imagen-3",
            },
            "openai": {
                "type": "api",
                "key_env": "OPENAI_API_KEY",
                "model": "dall-e-3",
            },
        },
        "default": "mock",
    },
    
    "web_search": {
        "providers": {
            "duckduckgo": {
                "type": "python",
                "package": "duckduckgo-search",
                "cost": "free",
            },
            "tavily": {
                "type": "api",
                "key_env": "TAVILY_API_KEY",
                "endpoint": "https://api.tavily.com/search",
            },
        },
        "default": "duckduckgo",
    },
    
    "llm": {
        "providers": {
            "openai": {
                "type": "api",
                "key_env": "OPENAI_API_KEY",
                "models": ["gpt-4o", "gpt-4o-mini"],
            },
            "deepseek": {
                "type": "api",
                "key_env": "DEEPSEEK_API_KEY",
                "base_url": "https://api.deepseek.com",
                "models": ["deepseek-chat", "deepseek-reasoner"],
            },
            "anthropic": {
                "type": "api",
                "key_env": "ANTHROPIC_API_KEY",
                "models": ["claude-sonnet-4-20250514"],
            },
        },
        "default": "deepseek",     # 性价比最优
    },
}
```

### 2.2 插件加载逻辑

```python
class PluginLoader:
    """运行时按 env 和 capabilities 选择 provider"""
    
    def select_provider(self, plugin_type: str, required_caps: List[str] = None) -> Provider:
        """
        选择逻辑:
        1. 检查 PLUGIN_REGISTRY[plugin_type]
        2. 如果 env 中有指定（如 PDF_PARSE_PROVIDER=mineru），强制使用
        3. 否则 'auto': 按 required_caps 过滤 → 选第一个满足的
        4. 如果首选缺少 key_env → 自动降级到下一个
        5. 如果所有都不可用 → 返回 fallback
        6. 如果连 fallback 都不可用 → raise FriendlyError("请配置XXX_KEY")
        """
    
    def check_health(self, provider: Provider) -> bool:
        """Docker: curl health_endpoint; API: key 存在; Python: import 成功"""
```

---

## 3. 认证

```python
# stdio 模式: 无认证（MCP 规范: stdio 走进程间通信）
# HTTP/SSE 模式: Bearer Token

# 环境变量: MCP_AUTH_TOKEN
# 如果设置了，HTTP server 中间件验证 Authorization: Bearer <token>
# 如果未设置 + HTTP 模式 → WARNING 日志 + 跳过认证（开发模式）
```

---

## 4. 统一错误模型

```python
class TutorError(Exception):
    """所有错误的基类"""
    def __init__(self, 
                 code: str,           # 机器可读错误码
                 message: str,        # 人类可读消息
                 hint: Optional[str] = None,     # 修复建议
                 retryable: bool = False,        # 可重试？
                 details: Optional[dict] = None): # 额外上下文
        ...

# 预定义错误码
ERROR_CODES = {
    'PLUGIN_NOT_AVAILABLE':   "插件不可用，请检查配置",
    'DEPENDENCY_MISSING':     "缺少依赖 {dep}，请安装",
    'CORPUS_NOT_FOUND':       "语料库 {id} 不存在",
    'KG_NOT_BUILT':           "请先 build_knowledge_graph",
    'SESSION_EXPIRED':        "会话已过期，请重新开始",
    'COGNITIVE_OVERLOAD':     "检测到认知过载，建议休息",
    'RATE_LIMITED':           "请求频率过高，请稍后",
    'AUTH_REQUIRED':          "需要认证（HTTP模式）",
    'GPU_NOT_AVAILABLE':      "未检测到 GPU，将以 CPU 模式运行",
}

# 每个 server 的 tool 返回中使用此模型
# MCP host 收到 ToolError 时可以给用户展示友好的提示
```

---

## 5. 日志

```python
# structlog JSON 格式，统一配置
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if is_dev else structlog.processors.JSONRenderer(),
    ],
)

# 日志级别:
# - DEBUG: 内部状态变化（L6 策略切换、L5 知识状态更新）
# - INFO: tool 调用开始/结束、外部服务调用
# - WARNING: 插件降级、认知过载检测、质量门警告
# - ERROR: tool 失败、插件不可用、数据库连接失败

# HTTP 模式额外: access log（请求路径、耗时、状态码）
```

---

## 6. 并发模型

```python
# 所有 server 的 tool 设计为无状态（stateless）
# 状态全部通过 L2 StateStore 管理

# 这意味着:
# - 同一用户可以从不同 client 同时访问
# - 多实例部署无需会话亲和性
# - tool 调用之间无内存共享

# session 隔离:
# 每个 session_id 是独立的状态空间
# 同用户多个 session 之间通过 L3/L5 共享知识状态
```

---

## 7. 项目结构

```
ai-tutor/
├── shared/
│   ├── storage.py         # FileStore + StateStore + RelationalStore + VectorStore
│   ├── plugins.py         # PluginLoader + PLUGIN_REGISTRY
│   ├── auth.py            # Bearer token middleware
│   ├── errors.py          # TutorError + ERROR_CODES
│   ├── logging_config.py  # structlog setup
│   └── schemas.py         # 共享 Pydantic 模型
├── servers/
│   ├── knowledge_mcp/
│   │   ├── server.py      # FastMCP server
│   │   ├── acquisition.py # acquire_subject 实现
│   │   ├── extraction.py  # 知识抽取流水线（L4）
│   │   ├── fusion.py      # 知识融合引擎（L4）
│   │   └── kg_store.py    # KG 版本化存储
│   ├── tutoring_mcp/
│   │   ├── server.py      # FastMCP server
│   │   ├── session.py     # L2 会话管理
│   │   ├── tracer.py      # L5 知识追踪
│   │   ├── profiler.py    # L5 学习者画像
│   │   ├── engine.py      # L6 教学引擎
│   │   ├── strategies/    # L6 六种策略原语
│   │   │   ├── reduction.py
│   │   │   ├── feynman.py
│   │   │   ├── socratic.py
│   │   │   ├── pbl.py
│   │   │   ├── analogy.py
│   │   │   └── spaced_repetition.py
│   │   └── memory.py      # L3 长期记忆
│   ├── digest_mcp/
│   │   ├── server.py
│   │   ├── quiz.py
│   │   ├── slides.py
│   │   ├── mindmap.py
│   │   ├── audio.py
│   │   ├── simulation.py
│   │   ├── multi_agent.py
│   │   └── assets/        # quiz-template.html + 模板
│   └── sync_mcp/
│       ├── server.py
│       ├── github_sync.py
│       └── obsidian_sync.py
├── docker-compose.yml
├── pyproject.toml         # uv workspace
├── examples/
│   ├── claude_desktop.json
│   └── workflow_48h.md
└── tests/
    └── ...
```

*（注：完整的 `specs/` 子目录规格文档会在下一步写入）*
