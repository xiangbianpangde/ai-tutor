# API-M-015 接口注释清单 — AITutor V3.1（M-015 打包调度）

> 来源: [DD-001:IC-005] / 实现文件: aitutor/build/orchestrator.py + upx.py + verifier.py
> 作者: DD-M-015 / 2026-06-02

---

## IC-005 打包构建（API-005 / IF-005）→ M-015 主接口

[接口编号] **API-005**（来自 AR-001）
[关联契约] **IC-005**（来自 [DD-001:IC-005 line 168-199]）
[实现文件] `aitutor/build/orchestrator.py`（主入口）+ `upx.py`（压缩子阶段）+ `verifier.py`（校验子阶段）

### 函数签名注释（主入口 build_artifact）

```python
def build_artifact(
    platform: Literal["windows", "linux", "macos"],  # 目标平台，[IC-005 line 174]
    format: Literal["cli", "gui"] = "cli",            # 形态，gui V3.5
    tag: str = "",                                     # semver 版本标签，[IC-005 line 175]
    push: bool = False,                                # 是否上传 artifact
) -> Artifact:                                         # 产物 [IC-005 出参 line 177-182]
    """触发完整打包流程（Nuitka → UPX → Verify）。

    Args:
        platform: "windows" | "linux" | "macos"，目标平台
        format: "cli" 或 "gui"（V3.5 决策），决定体积门禁阈值
        tag: semver 版本标签（如 "v3.1.0"）
        push: True 时上传至 GitHub Releases

    Returns:
        Artifact: 包含 artifact_path / size_bytes / sha256 / build_log / duration_ms

    Raises:
        BuildError: E01502 工具链不兼容 / E01503 sha256 不匹配
        BuildTimeoutError: E01504 CI 超时（>10min）

    Note:
        幂等性: 是 / 幂等键: (platform, tag, sha) / 重复: 跳过实际构建
        并发安全: 是（CI 矩阵并行 3 平台，每实例独立）
        性能约束: 单平台 ≤10min（IC-005 line 198）
        前置条件: CI runner 就绪、GitHub Secrets 已配置
        后置条件: artifact 已上传、metadata 已写入 SQLite

    Example:
        >>> artifact = build_artifact("linux", "cli", "v3.1.0", push=True)
        >>> assert len(artifact.sha256) == 64
    """
```

### 子阶段函数签名注释

```python
# COMPRESSING 阶段
def compress_artifact(artifact_path: str) -> Path:
    """UPX 压缩主可执行文件。

    Returns:
        Path: 压缩后产物（原地覆盖）

    Note:
        软降级 —— 失败仅写 WARN 日志不抛异常（ADR-009）
        性能: ≤120s
    """

# VERIFYING 阶段
def verify_artifact(
    artifact_path: str,
    format: Literal["cli", "gui"] = "cli",
    expected_sha256: str | None = None,
) -> VerifyResult:
    """校验 sha256 + 体积门禁。

    Returns:
        VerifyResult: passed / size_bytes / sha256 / warnings

    Raises:
        BuildError: E01503 sha256 不匹配

    Note:
        E01501 体积超目标仅 WARN（warn_size 字段非空）
    """
```

---

## 错误码注释覆盖（来源 [DD-001:IC-005 line 183-187]）

| 错误码 | 含义 | 触发条件 | 处理 | 注释位置 |
|--------|------|---------|------|---------|
| E01501 | 体积超目标 | CLI>50MB / GUI>200MB | UPX 压缩 + ⚠️（warn only）| verifier.py · ArtifactVerifier ✅ |
| E01502 | 工具链不兼容 | 锁版本破坏 | 锁版本回退 | nuitka.py · NuitkaBuilder._detect_toolchain ✅ |
| E01503 | sha256 不匹配 | 校验失败 | 重新构建 1 次 | verifier.py · ArtifactVerifier.verify ✅ |
| E01504 | CI 超时 | >10min | 拆分任务 | nuitka.py · NuitkaBuilder.build subprocess timeout ✅ |

**错误码注释覆盖率: 4/4 = 100%**

---

## 接口契约 → 注释映射验收

| IC-005 契约项 | 是否在注释中体现 |
|--------------|----------------|
| 入参 platform / format / tag / push | ✅ build_artifact docstring + 参数注释 |
| 出参 Artifact 全字段 | ✅ build_artifact Returns + Note |
| 4 错误码 E01501~E01504 | ✅ Raises + 各子模块异常处理段 |
| 时序图 GitHub Actions → AG-015 → 三阶段 | ✅ orchestrator.py 文件头功能描述 + 状态机注释 |
| 前置/后置条件 | ✅ build_artifact Note 段 |
| 并发安全 / 幂等性 | ✅ build_artifact Note 段 |
| 性能约束 ≤10min | ✅ build_artifact Note 段 + nuitka.py timeout 注释 |

**契约 → 注释完整映射: 7/7 = 100%（D4 接口契约注释化完整度）**

[来源标注] [DD-001:IC-005 line 168-199 全部 7 维度]
