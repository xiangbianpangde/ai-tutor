# FDR-M-015 框架决策记录 — AITutor V3.1（M-015 打包调度）

> 作者: DD-M-015 / 2026-06-02
> 来源: [DD-001:MD-M015] + [DD-001:IC-005] + [DD-001:FS-M015]

---

## FDR-M015-001 文件按子模块四分离（orchestrator/nuitka/upx/verifier）

- **决策状态**: 已接受
- **决策内容**: 采用 [DD-001:FS-M015 line 514-526] 的 4 文件结构（外加 __init__），不拆分至 5+ 文件
- **决策理由**:
  - DD-001 FS 已明确 build/ 目录下 4 文件结构（orchestrator/nuitka/upx/verifier）+ 1 个 __init__
  - 每个文件 ≤200 行（含注释），未达到 R14 过度拆分阈值
  - 4 文件正好对应 MD-M015 的 4 个类（BuildOrchestrator/NuitkaBuilder/UPXCompressor/ArtifactVerifier），职责单一
- **拒绝的替代方案**:
  - **方案 B**: 将 NuitkaBuilder 按平台拆为 nuitka_windows.py / nuitka_linux.py / nuitka_macos.py
    - 拒绝理由: 平台差异仅在 _build_args 一处（约 20 行），拆分增加文件数但未提升内聚度，违反 R14 过度拆分
- **影响范围**: aitutor/build/ 目录全部 5 个 Python 文件
- **来源标注**: [DD-001:FS-M015 line 514-526]

---

## FDR-M015-002 UPX 压缩软降级（不抛异常）

- **决策状态**: 已接受
- **决策内容**: UPX 不可用、压缩失败、体积超目标 均不抛异常，仅写 WARN 日志
- **决策理由**:
  - [DD-001:ADR-009] 已明确"体积是软约束"
  - [DD-001:EX-020] 处理流程：UPX 压缩 + 标 ⚠️（warn only）
  - [DD-001:IC-005 E01501] 错误码处理：UPX 压缩+⚠️（warn only）
  - 强制抛异常会阻塞 CI 流水线，违反 ADR-009 软约束语义
- **拒绝的替代方案**:
  - **方案 B**: UPX 失败时抛 BuildError 阻塞流水线
    - 拒绝理由: 与 ADR-009 软约束相悖，违反 R21 注释与契约不一致
- **影响范围**: upx.py · UPXCompressor.compress / compress_artifact / orchestrator FSM WARN_SIZE 分支
- **相关 FDR**: FDR-M015-003（体积门禁同为软约束）
- **来源标注**: [DD-001:ADR-009] + [DD-001:EX-020] + [DD-001:IC-005 E01501]

---

## FDR-M015-003 体积门禁阈值（CLI 50MB / GUI 200MB）

- **决策状态**: 已接受
- **决策内容**: 在 ArtifactVerifier 中硬编码 _size_limit_cli=50MB / _size_limit_gui=200MB
- **决策理由**:
  - [DD-001:IC-005 E01501] 明确 "CLI>50MB / GUI>200MB"
  - 阈值为部署需求驱动，非配置项；硬编码可避免误配置
- **拒绝的替代方案**:
  - **方案 B**: 从 pyproject.toml 或 env 读取阈值
    - 拒绝理由: 增加配置复杂度，且阈值与部署平台耦合，非用户运行时关注项
- **影响范围**: verifier.py · ArtifactVerifier._size_limit_cli/_size_limit_gui
- **相关 FDR**: FDR-M015-002（同为软约束）
- **来源标注**: [DD-001:IC-005 line 184] + [DD-001:EX-020]

---

## FDR-M015-004 Command + Factory 联合模式分离

- **决策状态**: 已接受
- **决策内容**: BuildCommand 仅作为不可变请求载体（@dataclass(frozen=True)）；NuitkaBuilderFactory 作为静态工厂方法负责实例化
- **决策理由**:
  - MD-M015 设计模式明确 "Command + Factory"，需两者协同
  - frozen Command 保证幂等键(platform+tag+sha)一致性（IC-005 line 197）
  - 静态 Factory 避免在 BuildOrchestrator 中硬编码平台分支，遵循开闭原则
- **拒绝的替代方案**:
  - **方案 B**: BuildOrchestrator 内置 if/elif/else 平台分支
    - 拒绝理由: 违反开闭原则；新增平台需修改 orchestrator，扩散修改面
- **影响范围**: orchestrator.py · BuildCommand + NuitkaBuilderFactory + BuildOrchestrator
- **来源标注**: [DD-001:MD-M015 line 428 设计模式] + [DD-M推断:依据=Command/Factory 经典实现]

---

## FDR-M015-005 FSM 状态用 str-Enum 而非纯字符串

- **决策状态**: 已接受
- **决策内容**: BuildState 继承 (str, Enum)，既可序列化为字符串（日志/审计）又有类型校验
- **决策理由**:
  - 状态需 publish_event 至 M-006 monitor 总线（必须可序列化）
  - 纯字符串易拼写错误，违反 CS-001 mypy --strict
  - str-Enum 同时满足序列化与类型安全
- **拒绝的替代方案**:
  - **方案 B**: 用 typing.Literal 字符串字面量
    - 拒绝理由: 缺少枚举集中维护；状态新增时易遗漏
- **影响范围**: orchestrator.py · BuildState
- **来源标注**: [DD-001:CS-001 §3.4 类型注解强制] + [DD-M推断:依据=Python 3.11 StrEnum 模式]

---

## FDR-M015-006 测试不依赖真实 Nuitka/UPX 工具链

- **决策状态**: 已接受
- **决策内容**: test_orchestrator/test_nuitka/test_upx 全部 Mock subprocess.run，CI 不需要安装 Nuitka 和 UPX
- **决策理由**:
  - 真实 Nuitka 编译耗时数分钟，CI 单元测试目标 ≤30s
  - Mock 边界清晰：测试 Python 层逻辑（参数生成/FSM 转换/异常处理），不测试 Nuitka 本身
  - 真实工具链测试由 CI 集成阶段（GitHub Actions release.yml）覆盖
- **拒绝的替代方案**:
  - **方案 B**: 单元测试中真实调用 Nuitka 编译 hello world
    - 拒绝理由: CI 时间爆炸，违反 MD-M015 测试策略 70% 覆盖率快速反馈目标
- **影响范围**: tests/unit/test_build/ 全部测试文件
- **来源标注**: [DD-001:CS-001 §6 测试规范 Mock 策略] + [DD-001:MD-M015 测试策略]

---

## FDR 汇总

| FDR | 标题 | 状态 |
|-----|------|------|
| FDR-M015-001 | 文件按子模块四分离 | 已接受 |
| FDR-M015-002 | UPX 压缩软降级 | 已接受 |
| FDR-M015-003 | 体积门禁阈值硬编码 | 已接受 |
| FDR-M015-004 | Command + Factory 联合模式 | 已接受 |
| FDR-M015-005 | FSM 状态 str-Enum | 已接受 |
| FDR-M015-006 | 测试不依赖真实工具链 | 已接受 |

**6 条 FDR / 全部已接受 / 0 取代 / 0 拒绝**
