# 插件注册表完整定义

> 与 L1-infrastructure.md 中的 PLUGIN_REGISTRY 配套，为每个插件定义完整的 provider spec、健康检查和降级策略

---

## 一、Provider Type 定义

```python
from typing import Literal, List, Optional, Dict, Any

ProviderType = Literal["docker", "python", "api", "mock"]

class ProviderSpec:
    """单个 provider 的完整规格"""
    name: str                           # provider 名称
    type: ProviderType
    # Docker type
    image: Optional[str] = None         # Docker 镜像名
    health_endpoint: Optional[str] = None
    # Python type
    package: Optional[str] = None       # pip 包名
    # API type
    key_env: Optional[str] = None       # API key 环境变量名
    base_url: Optional[str] = None
    endpoint: Optional[str] = None
    model: Optional[str] = None
    # 通用
    capabilities: List[str] = []
    cost: str = "free"                  # free | paid
    gpu_support: bool = False
    languages: List[str] = []
    description: str = ""

class PluginSpec:
    """一个插件类型的完整规格"""
    plugin_type: str                    # pdf_parse, transcription, tts, image_gen, web_search, llm
    providers: Dict[str, ProviderSpec]
    selection: Literal["auto", "manual"] = "auto"
    fallback: str                       # fallback provider name
    default: Optional[str] = None       # 默认 provider
```

---

## 二、完整注册表

```python
PLUGIN_REGISTRY: Dict[str, PluginSpec] = {
    "pdf_parse": {
        "providers": {
            "pdf2zh": {
                "type": "docker",
                "image": "xiangbianpangde/pdf2zh:latest",
                "health_endpoint": "/api/health",
                "convert_endpoint": "/api/convert",
                "capabilities": ["native_pdf", "scanned_pdf", "math_formula", "multi_lang", "ocr"],
                "gpu_support": True,
                "cost": "free",
                "description": "PDF mathematical document translation, math formula preservation",
            },
            "mineru": {
                "type": "docker",
                "image": "opendatalab/mineru:latest",
                "health_endpoint": "/health",
                "convert_endpoint": "/api/v1/parse",
                "capabilities": ["native_pdf", "scanned_pdf", "table", "math_formula", "ocr"],
                "gpu_support": True,
                "cost": "free",
                "description": "OpenDataLab document parsing, excellent table and formula handling",
            },
            "pymupdf4llm": {
                "type": "python",
                "package": "pymupdf4llm",
                "capabilities": ["native_pdf", "table"],
                "gpu_support": False,
                "cost": "free",
                "description": "Lightweight PDF→Markdown conversion, no OCR",
            },
        },
        "selection": "auto",
        "fallback": "pymupdf4llm",
    },

    "transcription": {
        "providers": {
            "faster_whisper": {
                "type": "python",
                "package": "faster-whisper",
                "model_config": {
                    "size": "base",
                    "compute_type": "int8",      # int8 | float16 | float32
                    "device": "auto",            # auto | cpu | cuda
                },
                "capabilities": ["zh", "en", "ja", "auto_detect", "local"],
                "gpu_support": True,
                "cost": "free",
                "description": "Local whisper inference via CTranslate2, fast and free",
            },
            "openai_whisper": {
                "type": "api",
                "key_env": "OPENAI_API_KEY",
                "model": "whisper-1",
                "capabilities": ["zh", "en", "ja", "multi_lang", "cloud"],
                "gpu_support": False,
                "cost": "paid",
                "description": "OpenAI hosted whisper API",
            },
        },
        "selection": "auto",
        "fallback": "faster_whisper",
        "default": "faster_whisper",
    },

    "text_to_speech": {
        "providers": {
            "edge": {
                "type": "python",
                "package": "edge-tts",
                "capabilities": ["zh-CN", "en-US", "ja-JP", "streaming"],
                "gpu_support": False,
                "cost": "free",
                "description": "Microsoft Edge TTS, free and high quality",
            },
            "openai_tts": {
                "type": "api",
                "key_env": "OPENAI_API_KEY",
                "model": "tts-1",
                "capabilities": ["multi_lang", "hd"],
                "cost": "paid",
                "description": "OpenAI TTS API",
            },
            "elevenlabs": {
                "type": "api",
                "key_env": "ELEVENLABS_API_KEY",
                "base_url": "https://api.elevenlabs.io",
                "capabilities": ["multi_lang", "voice_cloning"],
                "cost": "paid",
                "description": "ElevenLabs high-quality voice synthesis",
            },
        },
        "selection": "auto",
        "fallback": "edge",
        "default": "edge",
    },

    "image_generation": {
        "providers": {
            "mock": {
                "type": "mock",
                "capabilities": ["placeholder", "text_overlay"],
                "cost": "free",
                "description": "Generates placeholder images with text annotations for development",
            },
            "gemini": {
                "type": "api",
                "key_env": "GEMINI_API_KEY",
                "model": "imagen-3",
                "capabilities": ["scientific_diagram", "concept_illustration", "text_in_image"],
                "cost": "paid",
                "description": "Google Imagen 3, great for scientific diagrams",
            },
            "openai_image": {
                "type": "api",
                "key_env": "OPENAI_API_KEY",
                "model": "dall-e-3",
                "capabilities": ["creative", "realistic", "illustration"],
                "cost": "paid",
                "description": "OpenAI DALL-E 3",
            },
        },
        "selection": "auto",
        "fallback": "mock",
        "default": "mock",
    },

    "web_search": {
        "providers": {
            "duckduckgo": {
                "type": "python",
                "package": "duckduckgo-search",
                "capabilities": ["web", "news", "instant_answers"],
                "cost": "free",
                "description": "DuckDuckGo search, no API key needed",
            },
            "tavily": {
                "type": "api",
                "key_env": "TAVILY_API_KEY",
                "base_url": "https://api.tavily.com",
                "capabilities": ["web", "news", "ai_optimized"],
                "cost": "paid",
                "description": "Tavily AI-optimized search API",
            },
        },
        "selection": "auto",
        "fallback": "duckduckgo",
        "default": "duckduckgo",
    },

    "llm": {
        "providers": {
            "deepseek": {
                "type": "api",
                "key_env": "DEEPSEEK_API_KEY",
                "base_url": "https://api.deepseek.com",
                "models": {
                    "cheap": "deepseek-chat",
                    "reasoning": "deepseek-reasoner",
                },
                "capabilities": ["chat", "reasoning", "long_context", "code"],
                "cost": "paid",
                "description": "DeepSeek, best cost-effectiveness",
            },
            "openai": {
                "type": "api",
                "key_env": "OPENAI_API_KEY",
                "models": {
                    "cheap": "gpt-4o-mini",
                    "strong": "gpt-4o",
                },
                "capabilities": ["chat", "vision", "function_calling", "code"],
                "cost": "paid",
                "description": "OpenAI GPT models",
            },
            "anthropic": {
                "type": "api",
                "key_env": "ANTHROPIC_API_KEY",
                "models": {
                    "strong": "claude-sonnet-4-20250514",
                },
                "capabilities": ["chat", "vision", "long_context", "reasoning"],
                "cost": "paid",
                "description": "Anthropic Claude models",
            },
        },
        "selection": "manual",       # 用户必须在 env 中指定
        "default": "deepseek",       # 如果用户没指定，默认
    },
}
```

---

## 三、健康检查逻辑

```python
class PluginHealthChecker:
    """启动时检查所有已选 provider 的健康状态"""
    
    def check_all(self) -> HealthReport:
        """
        返回每个 plugin_type 的健康状态:
        {
            "pdf_parse": {"selected": "pdf2zh", "status": "healthy", "latency_ms": 45},
            "transcription": {"selected": "faster_whisper", "status": "healthy"},
            "tts": {"selected": "edge", "status": "healthy"},
            "image_gen": {"selected": "mock", "status": "healthy"},
            "web_search": {"selected": "duckduckgo", "status": "healthy"},
            "llm": {"selected": "deepseek", "status": "healthy", "latency_ms": 320},
        }
        """
    
    def check_docker(self, provider: ProviderSpec) -> HealthResult:
        """curl health_endpoint, timeout 5s"""
    
    def check_python(self, provider: ProviderSpec) -> HealthResult:
        """import package, 成功即 healthy"""
    
    def check_api(self, provider: ProviderSpec) -> HealthResult:
        """检查 key_env 是否设置，可选: 发送最小请求验证"""
```

---

## 四、降级链

```
pdf_parse:
  pdf2zh (docker, GPU) → mineru (docker, GPU) → pymupdf4llm (python, CPU)
  降级条件: health check fail | OOM | timeout > 30s

transcription:
  faster_whisper (local, GPU) → openai_whisper (API)
  降级条件: model load fail | CUDA OOM

tts:
  edge (python, free) → openai_tts → elevenlabs
  降级条件: package import fail (edge-tts not installed)

image_gen:
  gemini → openai_image → mock
  降级条件: key not set | API error | rate limit

web_search:
  tavily → duckduckgo
  降级条件: key not set | API error

llm:
  不自动降级（用户必须显式选择）
  如果 key 未设置 → FriendlyError("请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
```

---

## 五、环境变量映射

```bash
# LLM Provider (用户必须设置至少一个)
LLM_PROVIDER=deepseek        # deepseek | openai | anthropic
DEEPSEEK_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# PDF Parse (可选，auto 模式下自动检测)
PDF_PARSE_PROVIDER=auto      # auto | pdf2zh | mineru | pymupdf4llm

# 其他可选
TTS_PROVIDER=edge            # edge | openai_tts | elevenlabs
IMAGE_PROVIDER=mock          # mock | gemini | openai_image
SEARCH_PROVIDER=duckduckgo   # duckduckgo | tavily
WHISPER_PROVIDER=faster_whisper  # faster_whisper | openai_whisper
```
